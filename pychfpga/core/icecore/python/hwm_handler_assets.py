""" Base object for IceCrate (McGill Model MGK7BP).
"""
import logging
import inspect
import base64
import zlib  # used to compute crc32

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import class_mapper

from . import tuber
from . import handler
from . import session
from .hwm_assets import _IceCrateCore
from .hwm_assets import _IceBoardCore, _IceBoardPythonSupport
from .hwm_assets import _FMCMezzanineCore, _FMCMezzaninePythonSupport


class HWMIceCrate(_IceCrateCore, handler.HandlerObject):
    __mapper_args__ = {
        'polymorphic_identity': "HWMIceCrate"
    }
    handler_name = 'IceCrateHandler'


@tuber.TuberCategory("Backplane", lambda ic: ic.master_iceboard)
class IceCrateHandler(handler.Handler):
    """
    Basic Python handler for the IceCrate.
    """
    __handler_for__ = HWMIceCrate
    __handler_parent_attributes__ = {'slot': None, 'serial': None}

    @property
    def master_iceboard(self):
        iceboards = self.slot.items()
        return (sorted(iceboards)[0][1] if iceboards else None)

    def __repr__(self):
        return '%s(SN%s)' % (self.__class__.__name__, self.serial)


class HWMIceBoard(_IceBoardCore, handler.HandlerObject):
    """ Provides access to the basic functions of an IceBoard.

    This object inherits from a generic Hardware Map Resource (HWMResource),
    which allows the iceboard objects to be added to the hardware
    map database.

    This object also inherits from a Hardware Map Handler Manager
    (HandlerObject) which always keeps this object connected to the
    appropriate Handler object instance that persists in memory.

    All methods and attributes provided by the handler (in the handler itself
    or through Tuber) are accessible as if they belonged to this ORM object.

    The IceBoard object can be associated with multiple handlers in order to
    represent boards runing different FPGA firmware. The handler are
    identified by the 'handler_name' column.

    Project-specific classes are meant to be derived from this class.
    """

    __mapper_args__ = {
        'polymorphic_identity': "HWMIceBoard"
    }

    handler_name = Column(
        String, doc="The name of the handler to use for this resource.")

    # Define a unique key to represent this instance
    @property
    def handler_id(self):
        return (
            self.hostname if self.hostname else
            'iceboard%s.local' % self.serial if self.serial else
            None)

    def __init__(self, hostname=None, handler_name='IceBoardHandler',
                 **kwargs):
        """ Create a new Iceboard object from scratch. """

        # As a convenience, we can pass a Handler object as the
        # app_handler_name and we'll extract the name from it.
        if handler_name and inspect.isclass(handler_name) and \
                issubclass(handler_name, handler.Handler):
            handler_name = handler_name.__handler_name__

        # Populate the object instrumented attributes
        super(HWMIceBoard, self).__init__(
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
                for sc in class_mapper(HWMFMCMezzanine).self_and_descendants:
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

            for sc in class_mapper(HWMIceCrate).self_and_descendants:
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


class IceBoardHandler(_IceBoardPythonSupport, handler.Handler,
                      tuber.TuberObject):
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
    __handler_for__ = HWMIceBoard
    __handler_parent_attributes__ = {
        'hostname': None,
        'serial': None,
        'slot': None,
        'crate': lambda ib: ib.crate.handler,
        'mezzanine': lambda ib: {key: hwm_mezz.handler
                                 for (key, hwm_mezz) in ib.mezzanine.items()}
        }

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

    # hostname = HWMAttribute
    @property
    def tuber_uri(self):
        '''Smarter, IceBoard-aware tuber_uri.

        The version of 'tuber_uri' in tuber.py doesn't know about calculating
        hostnames from serials, for instance.
        '''
        if self.hostname:
            # We have a hostname; just use it.
            return 'http://{}/tuber'.format(self.hostname)

        if self.serial:
            # We have a serial number; compute the hostname.
            return 'http://iceboard{}.local/tuber'.format(self.serial)

        if self.slot and self.crate:
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

    def __repr__(self):
        """ Provides a concise string representation of this Iceboard that is
        informative enough to be used for logs.
        This string is typically used in syslog tags (32 characters max,
        alphanumeric characters only).
        """

        if self.crate and self.slot:
            return "%s(C%s.S%02i)" % (self.__class__.__name__,
                                      self.crate.serial, self.slot)
        if self.serial:
            return "%s(SN%s)" % (self.__class__.__name__,  self.serial)
        if self.hostname:
            return "%s(%s)" % (self.__class__.__name__,  self.hostname)
        return "%s(?)" % (self.__class__.__name__)

    # ----------------------------
    # Python Bitstream management
    # ----------------------------
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

    # ------------------------------------
    # Python FPGA Memory-mapped interface
    # ------------------------------------

    # *** JFC: Those methods can be updated one day to use the direct (non-
    #     Tuber) links to the FPGA (on separate socket, forwarded to the FPGA
    #     through SPI or PCIe). Otherwise we fallback to the slower tuber MMI
    #     interface.
    def fpga_mmi_read(self, addr):
        """ Read a single 32-bit word from the FPGA at the specified byte
        address. This uses the fastest interface available (currently the ARM-
        FPGA SPI link)
        """
        return self.fpga_tuber_spi_mmi_read(addr)

    def fpga_mmi_write(self, addr, value):
        """ Write a single 32-bit word to the FPGA at specified byte address.
        This uses the fastest interface available (currently the ARM-FPGA SPI
        link)
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

    # --------------------------------------------------------------------------
    # ARM Core methods (Should be implemented by the ARM and removed from here)
    # --------------------------------------------------------------------------

    # Mezzanine management

    # Backplane management

    # *** JFC: method rename
    def _write_motherboard_spi_eeprom_base64(self, *args, **kwargs):
        return self._motherboard_eeprom_write_base64(*args, **kwargs)

    def read_backplane_eeprom_ipmi(self):
        """ Return the IPMI data found on the backplane EEPROM.
        """
        raise NotImplementedError()

    # *** JFC: We now have the equivalent ARM method. Will delete this when we
    #     confirm it behaves the same.
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

    def print_tuber_methods(self):
        ''' Print all the methods provided by tuber, with a shoirt
        description
        '''
        for method_name, method_properties in \
                sorted(self._tuber_meta_methods.items()):
            print '%-30s: %s' % (method_name, method_properties.summary)


class HWMFMCMezzanine(_FMCMezzanineCore,  handler.HandlerObject):
    """FMC Mezzanine schema object.
    """
    __mapper_args__ = {
        'polymorphic_identity': "HWMFMCMezzanine"
    }
    handler_name = 'FMCMezzanineHandler'


@tuber.TuberCategory("Mezzanine", lambda m: m.iceboard,
                     mezzanine=lambda m: m.mezzanine)
class FMCMezzanineHandler(_FMCMezzaninePythonSupport, handler.Handler):
    """
    Provides the methods needed to operate a mezzanine.
    """
    __handler_for__ = HWMFMCMezzanine

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

    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self.iceboard.is_mezzanine_present(self.mezzanine)

# ---------------------------------------------
# Register IceCore objects into the YAML parser

session.register_yaml_object(HWMIceCrate, transform=('slots', 'slot'))
session.register_yaml_object(IceCrateHandler)
session.register_yaml_object(HWMIceBoard, transform=('mezzanines', 'mezzanine'))
session.register_yaml_object(IceBoardHandler)
session.register_yaml_object(HWMFMCMezzanine)
