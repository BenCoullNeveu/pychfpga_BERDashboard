"""Base object for IceBoard objects.

To specialize an IceBoard object for a particular experiment, you're
encouraged to create a subclass. There should be good examples
available.
"""

import tornado.gen
import select
import socket
import contextlib
import logging
import functools
import time
import inspect
import datetime
import base64
import zlib  # used to compute crc32

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.collections import attribute_mapped_collection

from . import hardware_map
from . import tuber
from . import handler

from hw import ipmi_fru


class IceCrate(hardware_map.HWMResource, handler.HandlerObject):
    __tablename__ = 'icecrates'
    __table_args__ = (
        UniqueConstraint('serial'),
    )
    __mapper_args__ = {'polymorphic_identity': __package__}

    _pk = Column(Integer, primary_key=True)
    serial = Column(String,
                    doc="The serial number written on the board (e.g. '001')")

    slots = relationship(
        "IceBoard",
        lazy="dynamic",
        query_class=hardware_map.HWMQuery,
        doc='''A SQLAlchemy subquery corresponding to this IceCrate's
            IceBoards. If you want to index this array using slot index,
            you should use 'slot' instead.''')

    slot = relationship(
        "IceBoard",
        back_populates="crate",
        collection_class=attribute_mapped_collection('slot'),
        doc="The IceCrate's IceBoards, indexed as you would expect.")

    handler_name = 'IceCrateHandler'

    def __repr__(self):
        return '%s(SN%s)' % (self.__class__.__name__,
                             self.serial)

    # This method tampers with the hardware map, so it must live in the HWM
    # object, not its handler
    def resolve(self, timeout=5, bail_on_unexpected=True):
        '''Automatically detect boards in a crate.

        We want to support hardware maps like this:

            - !IceCrate
                serial: "001"
                slots:
                    1:  !IceBoard {}
                    3:  !IceBoard {}
                    13: !IceBoard {}

        ...this is a good compromise between underspecified and overspecified
        HWMs. We know how many boards to expect, but can swap them without
        altering the HWM.

        By itself, however, this HWM snippet does not include enough
        information to contact IceBoards. Python needs a hostname or serial
        number for each board.

        The "resolve" method discovers boards using DNS-SD (pybonjour), and
        assigns their serial numbers. It does so by watching for IceBoards to
        advertise themselves. When an IceBoard's advertised slot and backplane
        serial match, we update its serial in the HWM.
        '''

        import pybonjour  # only needed here, and not always installed

        logger = logging.getLogger(__name__)
        fds = []

        if self.slots.count() == 0:
            # Either no boards are present (silly!), or they're unspecified (we
            # don't know when discovery is complete.) Bail.
            raise ValueError("Can't resolve() iceboards in an empty crate!")

        if all(self.slots.serial):
            # We know each slot's serial number, so no need to resolve().
            return

        def resolve_callback(sdRef, flags, iface, err, fullname,
                             host, port, txtRecord, io_loop):
            if err != pybonjour.kDNSServiceErr_NoError:
                return

            # Parse TXT records. That's where the IceBoard publishes data.
            tr = pybonjour.TXTRecord.parse(txtRecord)

            # If this motherboard didn't tell us its serial, we can't proceed.
            if 'motherboard-serial' not in tr:
                return

            mb_serial = tr['motherboard-serial']

            logger.debug("DNS-SD discovered IceBoard serial %s at %s" % (
                mb_serial, host))

            if 'backplane-slot' not in tr:
                ib = IceBoard(serial=mb_serial)
                with ib.tuber_context() as ctx:
                    ctx._initialize_backplane()
                    ipmi = ctx._get_backplane_ipmi()
                    slot = ctx.get_backplane_slot()

                tr['backplane-slot'] = slot.result()
                tr['backplane-serial'] = ipmi.result().product.serial_number

                logger.debug("Patched up an IceBoard that didn't know about "
                             "its backplane IPMI data. Result: crate serial "
                             "%s, slot %s" % (tr['backplane-serial'],
                                              tr['backplane-slot']))

            # If the discovered board is in a backplane...
            if 'backplane-slot' in tr:
                bp_serial = tr['backplane-serial']
                slot = int(tr['backplane-slot'])

                logger.info("IceBoard %s is slot %s in backplane %s" % (
                    mb_serial, slot, bp_serial))

                # If this isn't our serial number, these aren't our boards.
                if bp_serial != self.serial:
                    logger.debug("Skipping IceBoard %s (Pondering crate %s, "
                                 "but this board is in crate %s.)" %
                                 (mb_serial, bp_serial, self.serial))
                    return

                # Is the discovered board in the HWM?
                if slot not in self.slots.slot:
                    if bail_on_unexpected:
                        # Eek!
                        raise NameError("Discovered unexpected IceBoard "
                                        "serial %s in IceCrate serial %s "
                                        "slot %s!" % (mb_serial, bp_serial,
                                                      slot))
                    # Otherwise, just don't continue.
                    return

                logger.info("Discovered IceBoard serial %s in slot %s of "
                            "backplane %s" % (mb_serial, slot, bp_serial))

                ib = self.slot[slot]
                ib.serial = tr['motherboard-serial']
                ib.update_handler()
                # Break out of loop if we know everything we need to
                if all(self.slots.serial):
                    io_loop.stop()

        def browse_callback(sdRef, flags, iface, err, service,
                            regtype, replyDomain, io_loop):

            if (err != pybonjour.kDNSServiceErr_NoError) or \
                    not (flags & pybonjour.kDNSServiceFlagsAdd):
                return

            resolver = pybonjour.DNSServiceResolve(
                0, iface, service, regtype, replyDomain,
                callBack=functools.partial(resolve_callback, io_loop=io_loop)
            )
            fds.append(resolver)
            io_loop.add_handler(
                resolver.fileno(),
                lambda fd, events: pybonjour.DNSServiceProcessResult(resolver),
                io_loop.READ)

        # Create a local, captive IOLoop. We use this to epoll() on
        # Bonjour file descriptors.
        io_loop = tornado.ioloop.IOLoop()
        io_loop.add_timeout(time.time()+timeout, lambda: io_loop.stop())

        browser = pybonjour.DNSServiceBrowse(
            regtype='_tuber-jsonrpc._tcp',
            callBack=functools.partial(browse_callback, io_loop=io_loop)
        )
        fds.append(browser)
        io_loop.add_handler(
            browser.fileno(),
            lambda fd, events: pybonjour.DNSServiceProcessResult(browser),
            io_loop.READ)

        # Go!
        io_loop.start()

        # Clean up after Bonjour
        for fd in fds:
            fd.close()

        # Make sure we resolved all the boards in this crate
        if not all(self.slots.serial):
            missing = [ib.slot for ib in self.slots if not ib.serial]
            raise socket.timeout("IceBoards missing in slots %s!" %
                                 missing)


@tuber.TuberCategory("Backplane", lambda b: b.master_iceboard)
class IceCrateHandler(handler.Handler):
    """
    Basic Python handler for the IceCrate.
    """
    __handler_for__ = IceCrate

    @property
    def master_iceboard(self):
        iceboards = self.get_parent().slot.items()
        return (sorted(iceboards)[0][1] if iceboards else None)

    def __repr__(self):
        parent = self.get_parent()
        return '%s(SN%s)' % (self.__class__.__name__, parent.serial)


class IceBoard(hardware_map.HWMResource, handler.HandlerObject):
    """ Provides access to the basic functions of an IceBoard.

    This object inherits from a generic Hardware Map Resource (HWMResource),
    which allows the iceboard objects to be added to the hardware
    map database.

    This object also inherits from a Hardware Map Handler Manager
    (HWMHandlerManager) which always keeps this object connected to the
    appropriate Handler object instance that persists in memory.

    All methods and attributes provided by the handler (in the handler itself
    or through Tuber) are accessible as if they belonged to this ORM object.

    The IceBoard object can be associated with multiple handlers in order to
    represent boards runing different FPGA firmware. The handler are
    identified by the app_handler_name column, of the '_cls_ column if the
    former is not defined.

    Project-specific classes are meant to be derived from this class.
    """
    __tablename__ = 'iceboards'
    __table_args__ = (
        UniqueConstraint('serial'),
    )
    __mapper_args__ = {
        'polymorphic_identity': "IceBoard",
        'polymorphic_on': '_cls'
    }

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    _icecrate_pk = Column(Integer, ForeignKey('icecrates._pk'), index=True)

    hostname = Column(String,
                      doc="The hostname (or IP) to use for this resource.")
    serial = Column(String,
                    doc="The serial number written on the board (verbatim!)")

    slot = Column(Integer, doc="The IceCrate slot occupied by this board")

    crate = relationship(
        "IceCrate",
        back_populates="slot",
        doc="The IceCrate in which this Iceboard is connected.")

    mezzanines = relationship(
        "FMCMezzanine",
        lazy="dynamic",
        query_class=hardware_map.HWMQuery,
        doc='''A SQLAlchemy subquery corresponding to this IceBoard's
            mezzanines. If you want to index this array using logical
            keys (1 or 2), you should use 'mezzanine' instead.''')

    mezzanine = relationship(
        "FMCMezzanine",
        backref=backref("iceboard"),
        collection_class=attribute_mapped_collection('mezzanine'),
        doc='''The IceBoard's mezzanines, indexed as you would expect
            (1 for mezzanine A, 2 for mezzanine B).''')

    subarray = Column(
        Integer,
        doc="Arbitrary string used to group and select subsets of Iceboard")

    handler_name = Column(
        String,
        doc="The name of the handler to use for this resource. If not specified, the top handler will be used.")

    # Define a unique key to represent this instance
    @property
    def handler_id(self):
        return (
            self.hostname if self.hostname else
            'iceboard%s.local' % self.serial if self.serial else
            None)

    def __repr__(self):
        """ Provides a concise string representation of this Iceboard that is
        informative enough to be used for logs.
        """
        if self.crate and self.slot:
            return "%s(C%s.S%02i)" % (self.__class__.__name__,  self.crate.serial, self.slot)
        if self.serial:
            return "%s(SN%s)" % (self.__class__.__name__,  self.serial)
        if self.hostname:
            return "%s(%s)" % (self.__class__.__name__,  self.hostname)
        return "%s(?)" % (self.__class__.__name__)

    def __init__(self, hostname=None, handler_name='IceBoardHandler', **kwargs):
        """ Create a new Iceboard object from scratch. """

        # As a convenience, we can pass a Handler object as the
        # app_handler_name and we'll extract the name from it.
        if handler_name and inspect.isclass(handler_name) and issubclass(handler_name, handler.Handler):
            handler_name = handler_name.__handler_name__

        # Populate the object instrumented attributes
        super(IceBoard, self).__init__(
            hostname=hostname,
            handler_name=handler_name,
            **kwargs)

        self.logger = logging.getLogger(__name__)
        self.logger.info('%r: Created instance with args %r' % (self, kwargs))

    def set_handler(self, handler=None, bitstream=None,
                    configure_fpga=False, force=False, tag=None):
        """ Helper function used to specify the handler and bitstream
        associated with this IceBoard.

        Example:
            ib = hwm.query(Iceboards)
            ib.set_handler(ChannelizerIceBoardHandler, chan_bistream_v20, tag='2.0', configure_fpga=True)
            ib.some_channelizer_method(...)  # the iceboard runs as a channelizer ...
            ib.set_handler(CorrelatorIceBoardHandler, corr_bistream_v17, tag='1.7', configure_fpga=True)
            ib.some_correlator_method(...)  # .. and now it runs as a correlator
        """
        if handler:
            self.handler_name = handler.__handler_name__
            self.update_handler()
        if bitstream:
            self.register_fpga_bitstream(bitstream, tag=tag)
        if configure_fpga:
            self.set_fpga_bitstream(tag=tag, force=force)


class IceBoardHandler(handler.Handler, tuber.TuberObject):
    """ Basic Python handler for the IceBoard.

    It provides:
       - access to the methods and attributes provided by the ARM-based
             software through Tuber
       - offers a standardized memory-mapped interface to the FPGA firmware
         through the fpga_mmi_read() and fpga_mmi_write() methods.

    Firmware-specific application handlers should subclass this class.

    Any object provided by this this handler can be accessed at any
    hierarchical level. However, objects that are probided by Tuber have these
    restrictions:

       - attributes and methods whise name begin with '_' are not accessible
       - modification to the object attributes must be done by a setter
         function provided by the object.
       - methods or attribute access can only return string or numeric values,
         or lists or dictionnary thereof

    NOTE 1: For now, the MMI interface is provided through Tuber using its
    peek/poke methods, but the interface may transparenly offer faster access
    methods by redefining the fpga_mmi_read/write methods. For example, the
    MMI commands might one day bypass Tuber's HTTP/JSON overhead and go
    through a separate ARM port that forwards the packets directly to the FPGA
    through SPI or PCIe for maximum speed.

    NOTE 2: This handler does not define a MMI interface that uses the FPGA's
    ethernet port (e.g. CHIME) . Such functionnality is to be provided by a
    superclass of this handler if the firmware supports it.
    """

    # Make this class (and any subclass) register with IceBoard
    __handler_for__ = IceBoard

    # Core FPGA firmware registers (delete when moved to the ARM)
    FPGA_CORE_FIRMWARE_COOKIE_ADDR        = 4 * 0
    FPGA_APPLICATION_FIRMWARE_COOKIE_ADDR = 4 * 1
    FPGA_APPLICATION_FLAGS_ADDR           = 4 * 2
    FPGA_FIRMWARE_CRC32_ADDR              = 4 * 3
    FPGA_FIRMWARE_TIMESTAMP_ADDR          = 4 * 4
    FPGA_SERIAL_NUMBER_LSW_ADDR           = 4 * 5
    FPGA_SERIAL_NUMBER_MSW_ADDR           = 4 * 6

    # _bitstream_register contains a list of bitstreams that are associated
    # with this object. Format: tag: bitstream_object
    _bitstream_register = {}

    tuber_objname = 'IceBoard'

    @property
    def tuber_uri(self):
        '''Smarter, IceBoard-aware tuber_uri.

        The version of 'tuber_uri' in tuber.py doesn't know about calculating
        hostnames from serials, for instance.
        '''
        parent = self.get_parent()
        if parent.hostname:
            # We have a hostname; just use it.
            return 'http://{}/tuber'.format(parent.hostname)

        if parent.serial:
            # We have a serial number; compute the hostname.
            return 'http://iceboard{}.local/tuber'.format(parent.serial)

        if parent.slot and parent.crate:
            # We're in a specified slot in a crate. For now, that means we
            # need IceCrate.resolve() to be called. When I2C contention on the
            # backplane isn't an issue, this is also enough to compute the
            # hostname (i.e. slot3.crate001.local).
            raise NameError("Slot and crate supplied, but you haven't called "
                            "'resolve' on the crate yet. Until you do, I "
                            "don't know how to talk to boards.")

        raise NameError("Couldn't figure out a Tuber URI for this object! "
                        "I need serial or crate information.")

    def __init__(self, **kwargs):
        self.logger = logging.getLogger(__name__)
        super(IceBoardHandler, self).__init__(**kwargs)
        # self.hostname = self.parent.hostname

    # def hwm_update(self, parent):
    #     """ Is called when the Hardware Map object might have changed to
    #     reflect those changes in the handler.

    #     Note: This might be called when accessing an attribute from
    #     parent. Make sure we access only existing attributes.
    #     """
    #     # parent = self.parent
    #     super(IceBoardHandler, self).hwm_update(parent)
    #     self.hostname = parent.hostname
    #     self.serial = parent.serial
    #     self.slot = parent.slot
    #     self.crate = parent.crate.handler if parent.crate else None
    #     self.mezzanine = {
    #         key: hwm_mezz.handler for (key, hwm_mezz) in
    #         parent.mezzanine.items()
    #         }

    def __repr__(self):
        """ Provides a concise string representation of this Iceboard that is
        informative enough to be used for logs.
        This string is typically used in syslog tags (32 characters max,
        alphanumeric characters only).
        """
        # logger = logging.getLogger(__name__)
        # print ("%s: calling __repr__, stack=\n%s" % (type(self).__name__,  '\n\n'.join("%25s:%3i in %15s(...) --> %s" % (ss[1][-25:],ss[2],ss[3],ss[4]) for ss in inspect.stack()[1:15])))
        parent = self.get_parent()

        if parent.crate and parent.slot:
            return "%s(C%s.S%02i)" % (self.__class__.__name__,  parent.crate.serial, parent.slot)
        if parent.serial:
            return "%s(SN%s)" % (self.__class__.__name__,  parent.serial)
        if parent.hostname:
            return "%s(%s)" % (self.__class__.__name__,  parent.hostname)
        return "%s(?)" % (self.__class__.__name__)

    #----------------------------
    # Python Bitstream management
    #----------------------------
    @classmethod
    def register_fpga_bitstream(cls, bitstream, tag=None):
        """ Register a bitstream that is associated with this application
        handler.

        'bitstream' can be any object whose str() property returns a valid
              bitstream (e.g. a string, a buffer or a FpgaBitstream object).

        This is to provide to host-based Python application a functionnality
        equivalent to that of the ARM-based applications handlers which can
        also access the relevant bitstream.
        """
        cls._bitstream_register[tag] = bitstream

    def set_fpga_bitstream(self, buf=None, tag=None, force=False):
        '''
        Configures the FPGA with the specified bitstream.

        The bitstream associated with the current handler with the specifiec
        'tag' will be loaded. However, if a buffer 'buf' is explicitely
        provided, that bitstream will be used instead.,

        The 'buf' can be any an object where str(buf) returns the content of a
        .BIT or .BIN file (which includes a buffer, a string, or other objects
        defining __str__()).

        By default, the FPGA will not be reconfigured it already has a
        bitstream with the same CRC signature. That behavior can be changed by
        specifying the 'force' argument:

            force = True: FPGA will always be configured
            force = False: FPGA will be configured if it is not configured or
                    if bitstream CRC differ
            force = None: FPGA will be configured only if it is not configured
        '''
        if hasattr(self, 'close'):
            self.close()

        # If the bitstream is not explicitely provided, ask the handler to
        # provide it. The str() of the returned object must yield the valid
        # bitstream buffer in a string.
        if buf is None:
            buf = str(self.get_fpga_bitstream(tag))
        else:
            buf = str(buf)

        crc32 = zlib.crc32(buf) & 0xFFFFFFFF  # compute CRC32 of the data

        if not self.is_fpga_programmed() or force \
           or (force is not None and (self.get_fpga_bitstream_crc() != crc32)):
            self.logger.info('%r: Configuring FPGA' % self)
            b64_string = base64.b64encode(str(buf))
            self._set_fpga_bitstream_base64(b64_string)
            self.set_fpga_bitstream_crc(crc32)
            self.logger.info('%r: Done configuring FPGA' % self)
        else:
            self.logger.info(
                '%r: FPGA is already configured. Skipping configuration' % self
                )

    def get_fpga_bitstream(self, tag=None):
        """ Return the bitstream associated with this handler for the supplied
        tag as a string.

        If no bitstream is registered for this Handler or if no bitstream match
        the tag, the method attempts to obtain the bitstream through Tuber.
        """
        if tag in self._bitstream_register:
            return self._bitstream_register[tag]
        else:
            return tuber.TuberObject.get_fpga_bitstream(self, tag)

    #------------------------------------
    # Python FPGA Memory-mapped interface
    #------------------------------------

    # *** JFC: Those methods can be updated one day to use the direct (non-
    #     Tuber) links to the FPGA (on separate socket, forwarded to the FPGA
    #     through SPI or PCIe). Otherwise we fallback to the slower tuber MMI
    #     interface.
    def fpga_mmi_read(self, addr):
        """ Read a single 32-bit word from the FPGA at the specified byte address.
        This uses the fastest interface available (currently the ARM-FPGA SPI link)
        """
        return self.fpga_tuber_spi_mmi_read(addr)

    def fpga_mmi_write(self, addr, value):
        """ Write a single 32-bit word to the FPGA at specified byte address.
        This uses the fastest interface available (currently the ARM-FPGA SPI link)
        """
        self.fpga_tuber_spi_mmi_write(addr, value)

    # *** JFC: Proposed new names for the Tuber MMI access
    def fpga_tuber_spi_mmi_read(self, addr):
        """ Read a single 32-bit word at specified byte address through the
        SPI interface.
        """
        return self._fpga_spi_peek(addr) & 0xFFFFFFFF

    def fpga_tuber_spi_mmi_write(self, addr, value):
        """ Write a single 32-bit word at specified byte address through the
        SPI interface.
        """
        self._fpga_spi_poke(addr, value)

    #-------------------------------------
    # Python Motherboard EEPROM management
    #-------------------------------------

    # *** JFC:  Suggested method renaming
    def _write_motherboard_spi_eeprom_ipmi(self, *args, **kwargs):
        return self._eeprom_write_ipmi(*args, **kwargs)

    def _eeprom_write_ipmi(self, part_number, serial_number, product_version):
        '''Write IPMI-formatted EEPROM for IceBoards.

        These fields are read back and parsed by software, so you have
        to get them right or things will misbehave. This method currently
        expects the following formatting:

        >>> m._eeprom_write_ipmi(
        ...     part_number="MGK7MB",
        ...     serial_number="0004",
        ...     product_version="2")

        DON'T fill incorrect values unless they're visibly incorrect,
        since this data tends to be useful when debugging physical
        problems (e.g. tracing board history). Incorrect data that
        pretends to be valid can make this kind of debugging very painful.
        '''

        fru = ipmi_fru.FRU(
            board=ipmi_fru.Board(
                mfg_date=datetime.datetime.now(),
                manufacturer="Winterland",
                product_name="IceBoard",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=ipmi_fru.Product(
                manufacturer="Winterland",
                product_name="IceBoard",
                part_number=part_number,
                product_version=product_version,
                serial_number=serial_number,
                asset_tag="",
                fru_file="",
            ),
            # multi=Multi(...), when it's supported by this code
        )
        b64_string = base64.b64encode(fru.encode())
        return self._motherboard_eeprom_write_base64(b64_string)

    #-----------------------------------
    # Python Backplane EEPROM management
    #-----------------------------------

    # *** JFC: Proposed renaming
    def write_backplane_eeprom_ipmi(self, *args, **kwargs):
        return self._backplane_eeprom_write_ipmi(*args, **kwargs)


    def _backplane_eeprom_write_ipmi(self,
                                     part_number,
                                     serial_number,
                                     product_version):
        '''Write IPMI-formatted EEPROM for IceCrates.

        These fields are read back and parsed by software, so you have
        to get them right or things will misbehave. This method currently
        expects the following formatting:

        >>> m._backplane_eeprom_write_ipmi(
        ...     part_number="MGK7BP",
        ...     serial_number="001",
        ...     product_version="0")

        DON'T fill incorrect values unless they're visibly incorrect,
        since this data tends to be useful when debugging physical
        problems (e.g. tracing board history). Incorrect data that
        pretends to be valid can make this kind of debugging very painful.

        This method is attached to an IceBoard instead of an IceCrate since
        you can't properly address an IceCrate unless its EEPROM has already
        been programmed. Chickens and eggs.
        '''
        chassis_type = CHASSIS_SUBCHASSIS

        fru = ipmi_fru.FRU(
            chassis=Chassis(
                type_code=chassis_type,
                part_number=part_number,
                serial_number=serial_number
            ),
            board=ipmi_fru.Board(
                mfg_date=datetime.datetime.now(),
                manufacturer="Winterland",
                product_name="IceCrate",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=ipmi_fru.Product(
                manufacturer="Winterland",
                product_name="IceCrate",
                part_number=part_number,
                product_version=product_version,
                serial_number=serial_number,
                asset_tag="",
                fru_file="",
            ),
            # multi=Multi(...), when it's supported by this code
        )
        b64_string = base64.b64encode(fru.encode())
        return self._backplane_eeprom_write_base64(b64_string)


    #--------------------------------------------------------------------------
    # ARM Core methods (Should be implemented by the ARM and removed from here)
    #--------------------------------------------------------------------------

    # Mezzanine management

    # Backplane management

    # *** JFC: method rename
    def _write_motherboard_spi_eeprom_base64(self, *args, **kwargs):
        return self._motherboard_eeprom_write_base64(*args, **kwargs)

    def read_backplane_eeprom_ipmi(self):
        """ Return the IPMI data found on the backplane EEPROM.
        """
        raise NotImplementedError()

    # *** JFC: We now have the equivalent ARM method. Will delete this when we confirm it behaves the same.
    def get_slot_number(self):
        """ Reads the GPIO to determine in which slot number this IceBoard is
        connected.

        """
        if self.is_backplane_present():  # Is this test necessary?
            return self.get_backplane_slot()
        else:
            return None

    # Bitstream management

    def get_fpga_bitstream_crc(self):
        """ Return the signature of the firmware currently configured in the
        FPGA.

        Returns None if the FPGA is not configured.
        """
        if not self.is_fpga_programmed():
            return None
        return self.fpga_mmi_read(self.FPGA_FIRMWARE_CRC32_ADDR)
        # return self._bitstream_crc

    def set_fpga_bitstream_crc(self, crc32):
        """ Return the signature of the firmware currently configured in the
        FPGA.

        Returns None if the FPGA is not configured.
        """
        if self.is_fpga_programmed():
            # self._bitstream_crc = crc32
            self.fpga_mmi_write(self.FPGA_FIRMWARE_CRC32_ADDR, crc32)
        else:
            # self._bitstream_crc = None
            self.fpga_mmi_write(self.FPGA_FIRMWARE_CRC32_ADDR, 0)

    def clear_fpga_bitstream(self):
        """ Stop the operation of the FPGA.

        Could be used if we detect that we don't have the right kind of
        mezzanines.
        """
        raise NotImplementedError()

    # Core firmware functions

    def get_fpga_core_cookie(self):
        """ Return the core FPGA firmware cookie. Should always be 0xBEEFFACE.
        """
        if not self.is_fpga_programmed():
            return None
        return self.fpga_mmi_read(self.FPGA_CORE_FIRMWARE_COOKIE_ADDR)

    def get_fpga_application_cookie(self):
        """ Return the application-specific FPGA firmware cookie. """
        if not self.is_fpga_programmed():
            return None
        return self.fpga_mmi_read(self.FPGA_APPLICATION_FIRMWARE_COOKIE_ADDR)

    def get_fpga_serial_number(self):
        """ Return the FPGA serial number, as read from the FPGA's core
        firmware throught the MMI interface. """
        fpga_serial_number = (
            self.fpga_mmi_read(self.FPGA_SERIAL_NUMBER_LSW_ADDR) |
            (self.fpga_mmi_read(self.FPGA_SERIAL_NUMBER_MSW_ADDR) << 32)
            )

        return fpga_serial_number

    def get_fpga_firmware_timestamp(self):
        """ Returns a string containing the date-time of the currrent firmware
        bitstream.
        """
        timestamp = self.fpga_mmi_read(self.FPGA_FIRMWARE_TIMESTAMP_ADDR)
        seconds = (timestamp >> 0) & 0x3F
        minutes = (timestamp >> 6) & 0x3F
        hour = (timestamp >> 12) & 0x1F
        year = (timestamp >> 17) & 0x3F
        month = (timestamp >> 23) & 0x0F
        day = (timestamp >> 27) & 0x1F
        timestamp_string = '%04i-%02i-%02i %02i:%02i:%02i' % (
            year + 2000, month, day, hour, minutes, seconds)
        return timestamp_string

    # ----------------------------------------------------------------
    # Extra methods, possible candidates for deletion if no longer used
    # ----------------------------------------------------------------

    # *** JFC: Changed to have the default behavior to only return the
    #     mezzanines that were detected.
    # *** JFC: We could put the update part in a separate function, maybe
    #     outside IceBoard
    # *** JFC: Maybe we should add a check=True option to raise an error if
    #     the hardware map does not match reality
    def detect_mezzanines(self, update=False):
        '''Detect mezzanines attached to the Iceboard, and instantiate them if
        update=True.

        This method uses IPMI data on the mezzanine's EEPROMs to guide
        itself.

        You do NOT need to use this method if the mezzanines present in the
        system are already explicitely specified in the YAML hardware maps.
        '''

        mezz_class = {}
        for m in range(1, self.NUM_MEZZANINES + 1):

            # MezzClass = MissingMezzanine # Used by Graeme
            part_number = None
            serial = None
            mezz_class[m] = None
            # If a mezzanine is present, ask it (from EEPROM) what kind
            # of mezzanine it is. Try to instantiate a mezz-specific
            # class.
            if self.is_mezzanine_present(m):
                ipmi = self._get_mezzanine_ipmi(m)
                part_number = ipmi.product.part_number
                serial = ipmi.product.serial_number
                self.logger.info(
                    '%r: detect_mezzanines(): Detected Mezzanine '
                    'Model: %s Serial %s in Mezzanine %i'
                    % (self, part_number, serial, m))
                for sc in class_mapper(FMCMezzanine).self_and_descendants:
                    if sc.polymorphic_identity == part_number:
                        mezz_class[m] = sc.class_

            if not mezz_class[m]:
                self.logger.warning(
                    "IceBoard SN%r detect_mezzanines(): There is no known "
                    "FMC Mezzanine object with polymorphic map name '%r' "
                    "for Mezzanine %r" % (self.serial_number, part_number, m))

            if update:
                if not self.hwm:
                    raise SystemError(
                        '%r: detect_mezzanines(): Attempt to add new '
                        'mezzanine objects while the IceBoard is not yet '
                        'added to the  hardware map. ' % self)

                if m in self.mezzanine:
                    del(self.mezzanine[m])

                if mezz_class[m]:
                    self.logger.info(
                        '%r: detect_mezzanines(): Creating Mezzanine '
                        'Serial %s in Mezzanine %i' % (self, serial, m))
                    new_mezz = mezz_class[m](
                        mezzanine=m,
                        serial=serial,
                        type=''  # 'type' cannnot be None
                        )
                    self.hwm.add(new_mezz)
                    self.hwm.flush()
                    self.mezzanine[m] = new_mezz
                else:
                    self.logger.warning(
                        "IceBoard SN%r detect_mezzanines(): There is no known "
                        "FMC Mezzanine object with polymorphic map name '%r' "
                        "for Mezzanine %r"
                        % (self.serial_number, part_number, m))
                    # self.mezzanine[m] = None

        if update:
            self.update_handler()  # Let the handlers update for the new mezz
        return mezz_class

    # *** JFC: detect_icecrate would be a more consistent name
    def detect_backplane(self, update=False):
        '''Detect the Icecrate on which the Iceboard is attached, and
        instantiate them if update=True. If an IceCrate with the same serial
        number already exists, this IceBoard is added to it on the
        corresponding slot number.

        This method uses IPMI data on the backplane's EEPROMs to guide
        itself.

        You do NOT need to use this method if the backplane is
        already explicitely specified in the YAML hardware maps.
        '''

        icecrate_class = {}
        part_number = None
        serial = None
        if self.is_backplane_present():
            ipmi = self.read_backplane_eeprom_ipmi()
            part_number = ipmi.product.part_number
            serial = ipmi.product.serial_number
            slot_number = self.get_slot_number()
            self.logger.info(
                '%r: detect_backplane(): '
                'Detected Backplane Model: %s Serial %s'
                % (self, part_number, serial)
                )

            for sc in class_mapper(IceCrate).self_and_descendants:
                if sc.polymorphic_identity == part_number:
                    icecrate_class = sc.class_

        if not icecrate_class:
            self.logger.warning(
                "%r:  detect_backplane(): "
                "There is no known backplane object with "
                "polymorphic map name '%r'"
                % (self.serial_number, part_number))

        if icecrate_class and update:
            if not self.hwm:
                raise SystemError(
                    '%r: detect_backplane(): Attempt to update new backplane '
                    'object while the IceBoard is not yet added to the '
                    'hardware map. ' % self)

            # Assign slot number to IceBoard because the IceCrate will grab
            # that info upon IceBoard assignment to a slot
            self.slot_number = slot_number
            self.hwm.flush()

            if self.crate:  # if there is already an icecrate
                if isinstance(self.crate, icecrate_class) \
                        and self.crate.serial == serial:
                    self.crate.slot[slot_number] = self
                else:
                    del(self.crate)

            if not self.crate:
                self.logger.info(
                    '%r: detect_backplane(): Creating IceCrate %s'
                    % (self, serial))
                new_crate = icecrate_class(serial=serial)
                self.hwm.add(new_crate)
                self.crate = new_crate
                self.hwm.flush()

            # Assign this iceboard to the proper crate slot. Note that the
            # 'slot_number' index is ignored after the flush. The
            # IceBoard.slot_number is the real index.
            self.crate.slot[slot_number] = self
            self.hwm.flush()
            # Let the handlers update for the new crate info
            self.update_handler()
        return icecrate_class

    def print_tuber_methods(self):
        ''' Print all the methods provided by tuber, with a shoirt
        description
        '''
        for method_name, method_properties in \
                sorted(self._tuber_meta_methods.items()):
            print '%-30s: %s' % (method_name, method_properties.summary)


class FMCMezzanine(hardware_map.HWMResource, handler.HandlerObject):
    """FMC Mezzanine schema object.

    This is an abstract class. To specialize it for a particular FMC
    mezzanine, create a subclass. There should be some good examples
    to borrow from; you should refer to them rather than this code.
    """

    __tablename__ = 'fmc_mezzanines'
    __mapper_args__ = {
        'polymorphic_identity': 'fmc_mezzanine',
        'polymorphic_on': '_cls'
    }
    __table_args__ = (
        CheckConstraint(
            'mezzanine >= 1 and mezzanine <= 2',
            name='check_mezz_number'
        ),
    )

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    _iceboard_pk = Column(Integer, ForeignKey('iceboards._pk'), index=True)

    serial = Column(String)
    mezzanine = Column(Integer)


@tuber.TuberCategory(
   "Mezzanine",
   lambda m: m.iceboard,
   mezzanine=lambda m: m.mezzanine)
class FMCMezzanineHandler(handler.Handler):
    """
    Provides the methods needed to operate a mezzanine.
    """
    __handler_for__ = FMCMezzanine

    def hwm_update(self, parent):
        """ Import from the HWM object the main attributes needed to
        operate the mezzanine.
        """
        self.iceboard = parent.iceboard.handler
        self.mezzanine = parent.mezzanine

    def __repr__(self):
        # return '%s(%s)' % (self.__class__.__name__, self.serial)
        return "%r.%s(%r,%r)" % (
            self.iceboard,
            self.__class__.__name__,
            self.mezzanine,
            self.serial)

    def eeprom_write(self, buf):
        '''Writes a collection of bytes to the internal EEPROM.

        Don't do this unless you're at McGill, and you're commissioning
        and testing a new mezzanine! This method makes it trivial to
        delete non-volatile data. Figuring out how to re-write the original
        data is a tougher nut to crack.

        According to FMC specs, the EEPROM is required to contain an
        IPMI FRU descriptor. If you want to insert this kind of data,
        you should use the 'ipmi_fru' module included in this Python
        repository.

        Since EEPROM contents are parsed by machine and used during
        board bring-up, it's important that the data you write is valid.
        You should refer to reference code (likely in the QC suite) rather
        than trying to guess what structures belong in here.
        '''
        b64_string = base64.b64encode(buf)
        self.iceboard._mezzanine_eeprom_write_base64(
            self.mezzanine,
            b64_string,
            0
        )

    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self.iceboard.is_mezzanine_present(self.mezzanine)

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
