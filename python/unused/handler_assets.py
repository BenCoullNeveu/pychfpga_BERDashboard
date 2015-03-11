""" Base object for IceCrate (McGill Model MGK7BP).
"""

from . import handler
from . import tuber
from .hwm_assets import IceCrate, IceBoard, FMCMezzanine


class IceCrateHandler(handler.Handler):
    """
    Basic Python handler for the IceCrate.
    """

    # The following attributes must be redefined in every subclasses
    __handler_for__ = IceCrate
    # Icecrate handlers are identified by polymorphic name
    __handler_name__ = IceCrate.__mapper__.polymorphic_identity

    serial_number = None
    iceboards = []

    def __init__(self, **kwargs):
        super(IceCrateHandler, self).__init__(**kwargs)

    def __repr__(self):
        return '%s (handler for %r SN%s)' % (self.__class__.__name__,
                                             self.__handler_for__.__name__,
                                             self.serial_number)
    def __getattr__(self, name):
        """ Fetches attributes from the master iceboard.
        """
        if self.master_iceboard:
            return getattr(self.master_iceboard, name)
        raise AttributeError("%r does not have an attribute '%s'" % (self, name))

    def __dir__(self):
        class_attributes = [item  for class_ in type(self).mro() for item in dir(class_)]
        instance_attributes = self.__dict__.keys()
        backplane_attributes = dir(self.master_iceboard) if self.master_iceboard else []
        return list(set(class_attributes + instance_attributes + backplane_attributes))

    def hwm_update(self, hwm_object):
        """Is called when the Hardware Map object might have changed to reflect
        those changes in the handler.
        """
        super(IceCrateHandler, self).hwm_update(hwm_object)
        self.logger.info('%r: hwm_update()' % (self))
        self.serial_number = hwm_object.serial
        self.iceboards = dict(hwm_object.slot)
        self.logger.info(' %r.hwm_update(): slots have %r' %
                         (self, self.iceboards))
        self.master_iceboard = self.get_master_iceboard()

    def get_master_iceboard(self):
        """ Return the IceBoard handler that is designated to talk to the
        backplane.
        """
        if self.iceboards:
            # Just return the IceBoard in the lowest slot number
            return sorted(self.iceboards.items())[0][1]
        else:
            return None
# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab

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
    hostname = None
    tuber_objname = 'IceBoard'
    mezzanine = {}

    def __init__(self):
        super(IceBoardHandler, self).__init__()

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



    def __repr__(self):
        """ Get an unique string representation for this handler instance.

        It should preferably stay below 32 characters long to fit in syslog tag fields.
        """
        return '%s(%s)' % (
            self.__class__.__name__,
            'SN'+self.serial_number if self.serial_number else self.hostname)

    def hwm_update(self, hwm_object):
        """ Is called when the Hardware Map object might have changed to
        reflect those changes in the handler.

        Note: This might be called when accessing an attribute from
        hwm_object. Make sure we access only existing attributes to avoid
        intinite recursion loops.
        """
        super(IceBoardHandler, self).hwm_update(hwm_object)
        self.logger.info('%r: hwm_update()' % (self))
        self.hostname = hwm_object.hostname
        self.serial_number = hwm_object.serial
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



class FMCMezzanineHandler(handler.Handler):
    """
    Defined a basic FMC Mezzanine Python handler.
    """
    __handler_for__ = FMCMezzanine
    __handler_name__= 'FMCMezzanine'

    def __repr__(self):
        return '%s' % self.__class__.__name__

    def hwm_update(self, hwm_object):
        """ Import the main Mezzanine properties needed by the handler to operate the mezzanine.
        """
        self.motherboard = hwm_object.iceboard.handler
        self.mezzanine_number = hwm_object.mezzanine

