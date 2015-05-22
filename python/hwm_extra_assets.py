""" Base object for IceCrate (McGill Model MGK7BP).
"""
import logging
import inspect
import base64
import zlib  # used to compute crc32

from sqlalchemy import Column, String, Integer

from . import handler
from . import session
# from .hwm_assets import _IceCrateCore
from .hwm_assets import IceBoard, IceBoardHandler
# from .hwm_assets import _FMCMezzanineCore, _FMCMezzaninePythonSupport


@session.register_yaml_object()
class IceBoardPlus(IceBoard):
    """ Hardware map object that describes the basic properties of an IceBoard
    and give access to the methods to operate its hardware and FPGA firmware.

    This object differs from the basic IceBoard in that is can support
    multiple user-defined handler that define the functionnality of various
    FPGA firmware or mezzanines.

    All methods and attributes provided by the handler (in the handler itself
    or through Tuber) are accessible as if they belonged to this ORM object.

    The IceBoard object can be associated with multiple handlers in order to
    represent boards runing different FPGA firmware. The handler are
    identified by the 'handler_name' column.

    Project-specific classes are meant to be derived from this class.
    """

    __mapper_args__ = {'polymorphic_identity': "IceBoardPlus"}

    handler_name = Column(
        String, doc="The name of the handler to use for this resource.")

    subarray = Column(
        Integer,
        doc="Arbitrary string used to group and select subsets of Iceboard")

    def __init__(self, hostname=None, handler_name='IceBoardPlusHandler',
                 **kwargs):
        """ Create a new Iceboard object from scratch. """

        # As a convenience, we can pass a Handler object as the
        # app_handler_name and we'll extract the name from it.
        if handler_name and inspect.isclass(handler_name) and \
                issubclass(handler_name, handler.Handler):
            handler_name = handler_name.get_handler_name()

        # Populate the object instrumented attributes
        super(IceBoardPlus, self).__init__(
            hostname=hostname, handler_name=handler_name, **kwargs)

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


@session.register_yaml_object()
class IceBoardPlusHandler(IceBoardHandler):
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
    subclass of this handler if the firmware supports it.
    """


    __handler_for__ = IceBoardPlus # register this class (and any subclass)
    tuber_objname = 'IceBoard'

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
    # *** JFC:  Suggested method renaming
    def _write_motherboard_spi_eeprom_ipmi(self, *args, **kwargs):
        return self._eeprom_write_ipmi(*args, **kwargs)
    # *** JFC: Proposed renaming
    def _write_backplane_eeprom_ipmi(self, *args, **kwargs):
        return self._backplane_eeprom_write_ipmi(*args, **kwargs)


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

# @session.register_yaml_object
# @tuber.TuberCategory("Mezzanine", lambda m: m.iceboard,
#                      mezzanine=lambda m: m.mezzanine)
# # class CoreMezzanineHandler(_FMCMezzaninePythonSupport, handler.Handler):
#     """
#     Provides the methods needed to operate a mezzanine.
#     """
#     __handler_for__ = FMCMezzanine

#     def hwm_update(self, parent):
#         """ Import from the HWM object the main attributes needed to
#         operate the mezzanine.
#         """
#         self.iceboard = parent.iceboard.handler
#         self.mezzanine = parent.mezzanine

#     def __repr__(self):
#         # return '%s(%s)' % (self.__class__.__name__, self.serial)
#         return "%r.%s(%r,%r)" % (
#             self.iceboard,
#             self.__class__.__name__,
#             self.mezzanine,
#             self.serial)

#     def is_present(self):
#         """ returns a boolean indicating whether the ADC board is present"""
#         return self.iceboard.is_mezzanine_present(self.mezzanine)

