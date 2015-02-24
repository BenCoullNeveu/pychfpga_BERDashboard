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
from sqlalchemy.orm import reconstructor, class_mapper
from sqlalchemy.orm.collections import attribute_mapped_collection

from . import hardware_map
from . import tuber
from . import handler

from hw import ipmi_fru


class _IceCrate(hardware_map.HWMResource):
    __tablename__ = 'icecrates'
    __table_args__ = (
        UniqueConstraint('serial'),
    )
    __mapper_args__ = {'polymorphic_identity': __package__}

    _pk = Column(Integer, primary_key=True)
    serial = Column(String,
                    doc="The serial number written on the board (verbatim!)")

    slots = relationship(
        "IceBoard",
        lazy="dynamic",
        query_class=hardware_map.HWMQuery,
        doc='''A SQLAlchemy subquery corresponding to this IceCrate's
            IceBoards. If you want to index this array using slot index,
            you should use 'iceboard' instead.''')

    slot = relationship(
        "IceBoard",
        backref=backref("crate"),
        collection_class=attribute_mapped_collection('slot'),
        doc="The IceCrate's IceBoards, indexed as you would expect.")

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.serial)

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


class IceCrate(_IceCrate, handler.HandlerObject):
    __mapper_args__ = {
        'polymorphic_on': '_cls',
        'polymorphic_identity': 'MGK7BP'
    }
    _cls = Column(String, nullable=False)

    def init_handler(self):
        """ Create or re-attach a handler to this HWM object.
        """
        self.set_handler(object_id=self._pk, handler_name=self._cls)

# @tuber.TuberCategory(
#     "Backplane",
#     lambda b: b.slots.first())
# class IceCrate(_IceCrate):
#     pass


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
        UniqueConstraint('serial_number'),
    )
    __mapper_args__ = {
        'polymorphic_identity': 'IceBoard',  # ***JFC: why core.iceboard.IceBoard
        'polymorphic_on': '_cls'
    }

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    _icecrate_pk = Column(Integer, ForeignKey('icecrates._pk'), index=True)

    serial_number = Column(
        String,
        doc="The serial number written on the board (verbatim!)")

    slot_number = Column(
        Integer,
        doc="The IceCrate slot occupied by this board")

    subarray = Column(Integer)

    hostname = Column(
        String,
        doc="The hostname (or IP) to use for this resource.")

    # # Specify which type of handler is associated with this firmware
    # handler_name = Column(String)

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


    # Define a unique key to represent this instance
    handler_id = property(lambda self: self.hostname)

    def __init__(self, hostname=None, handler_name='IceBoardHandler', **kwargs):
        """ Create a new Iceboard object from scratch. """

        # As a convenience, we can pass a Handler object as the
        # app_handler_name and we'll extract the name from it.
        if inspect.isclass(handler_name) and issubclass(handler_name, handler.Handler):
            handler_name = handler_name.__handler_name__

        # Populate the object instrumented attributes
        super(IceBoard, self).__init__(
            hostname=hostname,
            # handler_name=handler_name,
            **kwargs)

        self.logger = logging.getLogger(__name__)
        self.logger.info('%r: Creating instance with args %r' % (self, kwargs))


    # *** JFC: just used for logging during debugging. will be removed. Unless
    #     we want to rely on the instance to always have a logger.
    @reconstructor
    def _init_from_database(self, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.info('%r: Recreating instance from database' % (self))

   # @property
    # def handler_id(self):
    #     return self.hostname

    # @property
    # def handler_name(self):
    #     return self.app_handler_name


    # def get_handler(self):
    #     """ Return the handler for this HWM object.

    #     This method calls _get_handler(...) with the arguments to uniquely
    #     identify this IceBoard instance, which handler to use, and pass
    #     arguments to the handler constructor if one needs to be created.

    #     For the Iceboard, we override the default get_handler() to do the following:

    #         - The unique HWM instance id is based on the hostname. This allows
    #           the handler to exist even if the HWM object does not yet have a
    #           primary key or serial number.

    #         - The handler name is taken from the 'app_handler_name' column to
    #           allow the user to easily define and change what firmware
    #           and software the IceBoard should be running.

    #         - We pass the hostname as the argument to allow Tuber
    #           initialization when a new Handler is created

    #     get_handler() is only called whenever there is no cached handler
    #     object (when HWM object has been created, recreated from the database,
    #     or moved in memory).
    #     """
    #    return self._get_handler(
    #         object_id=self.hostname,
    #         handler_name=self.handler,
    #         hostname=self.hostname)

    # *** JFC: making __dir__ collaborative in multiple inheritance context is hard. This is a bad fix.
    # def __dir__(self):
    #     return list(set.union(set(tuber.TuberObject.__dir__(self)), set(handler.HandlerObject.__dir__(self))))

    def __repr__(self):
        """ Provides a concise string representation of this Iceboard that is
        informative enough to be used for logs.

        This string is typically used in syslog tags (32 characters max,
        alphanumeric characters only).
        """
        return "%s%s(%s)" % (
            repr(self.crate) + '.' if self.crate else '',
            self.__class__.__name__,
            ('slot=%s' % self.slot_number) if self.crate else
            ('SN%s' % self.serial_number) if self.serial_number else
            ('%s' % self.hostname)
            )

    # *** JFC: This was named set_application. Maybe another name would be better?
    def set_app_handler(self,
                        handler=None,
                        bitstream=None,
                        configure_fpga=False,
                        force=False,
                        tag=None):
        """ Helper function used to specify the handler and bitstream
        associated with this IceBoard.

        Example: To set all the boards on an array to now run Dfmux application with a specific firmware:
            iceboards = hwm.query(Iceboards)
            iceboards.set_app_handler(DfMuxHandler, dfmux_bistream_v20, tag='2.0', configure_fpga=True)
        """
        if handler:
            self.app_handler_name = handler.__handler_name__
            self.update_handler()
        if bitstream:
            self.register_fpga_bitstream(bitstream, tag=tag)
        if configure_fpga:
            self.set_fpga_bitstream(tag=tag, force=force)

    # *** JFC: The philosophy of this command is now more to configure the
    #     fpga than to specify which bitstream to use. With this change of
    #     paradigm, I wonder if we should rename it back to configure_fpga().
    def set_fpga_bitstream(self, buf=None, tag=None, force=False):
        ''' Configures the FPGA with the specified bitstream.

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
                for sc in class_mapper(fmc_mezzanine.FMCMezzanine).self_and_descendants:
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
                        type='' # 'type' cannnot be None so we give it an empty string
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

            for sc in class_mapper(icecrate.IceCrate).self_and_descendants:
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

    # serial = Column(String) # Used by Graeme
    serial = Column(Integer) # Used by JFC
    mezzanine = Column(Integer)

    # # Since there are two "mezz" references per ICEBoard, the backreference
    # # has to be smart enough to accept either in the join.
    # iceboard = relationship(
    #     "IceBoard",
    #     uselist=False,
    #     primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    # )

    type = Column(String, nullable=False) # should this be equivalent to _cls?
    revision = Column(Integer)

    class FMCMezzanineException(Exception):
        pass

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.serial)

    def __init__(self, **kwargs):
        """ Create a new Mezzanine object from scratch and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('Creating instance for Mezzanine %r' % (self))

        super(FMCMezzanine, self).__init__(**kwargs) # allow the superclasses to initialize
        # self.set_handler(app_handler_name=self._cls, object_id=self._pk)

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self, **kwargs):
        """ Create an Mezzanine object from database and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('Recreating instance from database for Mezzanine %r' % (self))
        # self.set_handler(app_handler_name=self._cls, object_id=self._pk)

    def init_handler(self):
        self.set_handler(app_handler_name=self._cls, object_id=self._pk)

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

        import base64

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
