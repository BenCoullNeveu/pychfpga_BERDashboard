""" Base object for IceBoard (McGill Model MGK7MB) objects.

To specialise an IceBoard object for a particular experiment, you can simply
change the 'app_handler_name' field in the hardware map to your specific
application, and the object will connect to the appropriate code either on the
on-board ARM processor or to local Python objects, assuming those exist. If no
application is provided, the board will provide only its core
functionnalities.

Alternatively, you can subclass IceBoard to hard-code the application handler
name and add additional hardware map properties if needed.
"""

import logging
import base64
import zlib  # used to compute crc32

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import reconstructor, class_mapper
from sqlalchemy.orm.collections import attribute_mapped_collection

import hardware_map
import tuber
import fmc_mezzanine  # used import x to avoid circular import problem
import icecrate
import handler

# *** JFC:To be removed
class IceBoardException(Exception):
    pass


class IceBoard(hardware_map.HWMResource, handler.HWMHandlerManager):
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

    # ** JFC: Should be arm_ip_address or arm_hostname?
    hostname = Column(String)  # The host name of the ARM on the IceBoard

    # *** JFC: app_handler_name is used to allow the hardware map to specify
    #     which type of handler (i.e. FPGA firmware) is associated with this
    #     board without having to hard-code this in a subclass. Having the
    #     user to specify the '_cls' seems dangerous as it plays with the
    #     SQLAlchemy innards and will cause obscure error messaged.
    #
    #     This parameter could be renamed 'handler_name', 'handler',
    #     'personality', 'application' etc.
    #
    app_handler_name = Column(String)

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

    def __init__(self, app_handler_name=None, **kwargs):
        """ Create a new Iceboard object from scratch and link it with its
        handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('%r: Creating instance' % (self))

        # As a convenience, we can pass a Handler object as the
        # app_handler_name and we'll extract the name from it.
        if issubclass(type(app_handler_name), handler.Handler):
            app_handler_name = app_handler_name.__handler_name__

        super(IceBoard, self).__init__(app_handler_name=app_handler_name,
                                       **kwargs)

    # *** JFC: just used for logging during debugging. will be removed. Unless
    #     we want to rely on the instance to always have a logger.
    @reconstructor
    def _init_from_database(self, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.logger.info('%r: Recreating instance from database' % (self))

    def init_handler(self):
        """ Create or re-attach a handler to this HWM object.

        This is called whenever this instance of an HWM object has been
        created, recreated from the database, or changed.

        The default action is to connect to a handler class that is registered
        under the name specified in 'app_handler_name'.

        The handler instances are uniquely identified by the primary key
        '_pk'. The handler is passed the 'hostname' column value to allow its
        Tuber machinery to connect to the ARM.

        The default handler for IceBoard is IceBoardHandler, which provides
        Tuber's 'IceBoard' methods and properties in addition to basic Pyhton
        helper methods. A subclass of IceBoard can or course redefine this
        method to connect to any other handler and Tuber object.
        """
        # *** JFC: Concerning the handler name, I would recommend using
        #     'app_handler_name' or any better-named user column rather than
        #     '_cls'. Having two options is confusing. We still can do
        #     polymorphism-based handler selection by having the superclasses
        #     redefine their own default for 'app_handler_name'
        self.set_handler(object_id=self._pk,
                         handler_name=self.app_handler_name,
                         hostname=self.hostname)

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
            ('hostname=%s' % self.hostname)
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
            self.init_handler()
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

    # The following attributes must be redefined in every subclasses
    __handler_for__ = IceBoard

    # Core FPGA firmware registers
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
    # _bitstream_crc = None  # CRC32 of the currently configured bitstream

    serial_number = None
    mezzanine = {}

    def __init__(self, hostname=None, tuber_object='IceBoard', **kwargs):
        super(IceBoardHandler, self).__init__(
            hostname=hostname, objname=tuber_object, **kwargs)

    def __repr__(self):
        """ Get an unique string representation for this handler instance.

        It should preferably stay below 32 characters long to fit in syslog tag fields.
        """
        return '%s(SN%s)' % (
            self.__class__.__name__,
            self.serial_number)

    def hwm_update(self, hwm_object):
        """ Is called when the Hardware Map object might have changed to
        reflect those changes in the handler.
        """
        super(IceBoardHandler, self).hwm_update(hwm_object)
        self.logger.info('%r: hwm_update()' % (self))
        self.serial_number = hwm_object.serial_number
        self.mezzanine = {
            key: hwm_mezz.handler for (key, hwm_mezz) in
            hwm_object.mezzanine.items()
            }
        self.logger.info(
            '%r: hwm_update(): has mezzanines %r' % (self, self.mezzanine))

    #---------------------
    # Bitstream management
    #----------------------
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

    #---------------------
    # Memory-mapped interface
    #----------------------

    # *** JFC: Those methods can be updated one day to use the direct (non-
    #     Tuber) links to the FPGA (on separate socket, forwarded to the FPGA
    #     through SPI or PCIe). Otherwise we fallback to the slower tuber MMI
    #     interface.
    def fpga_mmi_read(self, addr):
        """ Read a single 32-bit word at specified byte address through the
        SPI interface.
        """
        return self.fpga_tuber_mmi_read(addr) & 0xFFFFFFFF

    def fpga_mmi_write(self, addr, value):
        """ Write a single 32-bit word at specified byte address through the
        SPI interface.
        """
        self.fpga_tuber_mmi_write(addr, value)

    # *** JFC: Proposed new names for the Tuber MMI access
    def fpga_tuber_mmi_read(self, addr):
        """ Read a single 32-bit word at specified byte address through the
        SPI interface.
        """
        return self._fpga_spi_peek(addr)

    def fpga_tuber_mmi_write(self, addr, value):
        """ Write a single 32-bit word at specified byte address through the
        SPI interface.
        """
        self._fpga_spi_poke(addr, value)

    #---------------------
    # Python-specific core methods
    #----------------------

    #---------------------
    # ARM Core methods (Should be implemented by the ARM)
    #----------------------
    # *** JFC: I suggest we rename _eeprom_write_ipmi to
    #     __write_motherboard_spi_eeprom_ipmi
    def _eeprom_write_ipmi(self, *args, **kwargs):
        return self._write_motherboard_spi_eeprom_ipmi(*args, **kwargs)

    # *** JFC:  I suggest we rename _motherboard_eeprom_write_base64 to
    #     _write_motherboard_spi_eeprom_base64
    def _write_motherboard_spi_eeprom_base64(self, *args, **kwargs):
        return self._motherboard_eeprom_write_base64(*args, **kwargs)

    def _write_motherboard_spi_eeprom_ipmi(
            self, part_number, serial_number, product_version):
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

        from hw.ipmi_fru import FRU, Board, Product
        from datetime import datetime

        fru = FRU(
            board=Board(
                mfg_date=datetime.now(),
                manufacturer="Winterland",
                product_name="IceBoard",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=Product(
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
        return self._write_motherboard_spi_eeprom_base64(b64_string)

    # Backplane management

    def is_backplane_present(self):
        """ Checks if the Iceoard is connected to a backplane by probing the
        backplane's EEPROM.
        """
        raise NotImplementedError()

    def read_backplane_eeprom_ipmi(self):
        """ Return the IPMI data found on the backplane EEPROM.
        """
        raise NotImplementedError()

    def write_backplane_eeprom_ipmi(self):
        """ Return the IPMI data found on the backplane EEPROM.
        """
        raise NotImplementedError()

    def get_slot_number(self):
        """ Reads the GPIO to determine in which slot number this IceBoard is
        connected.

        Will return None of the board is not connected to a backplane (i.e. if
        the backplane I2C EEPROM does not respond).

        NOTE: It would be nice if the ARM could provide this function.
        """
        raise NotImplementedError()

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
        serial_number = (
            self.fpga_mmi_read(self.FPGA_SERIAL_NUMBER_LSW_ADDR) |
            (self.fpga_mmi_read(self.FPGA_SERIAL_NUMBER_MSW_ADDR) << 32)
            )

        return serial_number

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
        string = '%04i-%02i-%02i %02i:%02i:%02i' % (
            year + 2000, month, day, hour, minutes, seconds)
        return string

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
