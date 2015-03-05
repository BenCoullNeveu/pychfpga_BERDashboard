""" Basic handler for chFPGA firmware.
"""

import logging
from datetime import datetime
import socket
import struct

from ..icecore.hwm_handler_assets import IceBoardHandler
from ..icecore import tuber  # Used to get TuberRemoteError
from ..icecore.hw.ipmi_fru import FRU, Board, Product, Chassis, MultiDict, CHASSIS_SUBCHASSIS


from .. import I2C as i2c
from .. import GPIO as gpio

from . import icecrate_handler  # this module is not referenced here, but loading it registers the handler with IceCrate.
from .iceboard_hardware import IceBoardHardware
from .iceboard_hardware import I2CInterface
from .backplane_hardware import BackplaneHardware
# import icebox # don't use from .. import ... because of circular import problems

class chFPGAHandler(IceBoardHandler):
    """ Provides basic access to CHIME-specific basic IceBoard firmware and
    hardware resources.

    Differences with the standard Iceboard handler:

    - A direct FPGA Ethernet-based 8-bit Memory Map Interface is provided
    - Access to the IceBoard hardware is provided through the FPGA I2C
      interface. Most of the equivalent methods are provided by the ARM, but
      missing methods are offered through this FPGA interface.
    - Acces to the backplane hardware. This is used by the IceCrate handler to
      provide backplane services.
    - The standard ARM mezzanine identification methods are intecepted to
      allow support for non-IPMI McGill ADC mezzanine boards.

     Python-based application-specific FPGA firmware and hardware handler are
     meant to be derived from this class.
    """

    _FPGA_CONTROL_BASE_PORT = 41000
    _BROADCAST_BASE_PORT = 41000

    _SYSTEM_BASE_ADDR      = 0x00000 # This is always at zero so we can gather info from the FPGA before we know the number of antennas etc.
    _SYSTEM_GPIO_BASE_ADDR = _SYSTEM_BASE_ADDR + 0x00000
    _SYSTEM_I2C_BASE_ADDR  = _SYSTEM_BASE_ADDR + 0x05000

    # Match those with what is used by Module
    _CONTROL_BASE_ADDR = 0x000000
    _STATUS_BASE_ADDR  = 0x080000
    _RAM_BASE_ADDR     = 0x100000

    _CHFPGA_COOKIE = 0x42 # Expected cookie value for chFPGA, both on the SPI and UDP MMI

    # GPIO Register addresses
    _GPIO_COOKIE_REG         = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR  # Register address of the firmware cookie
    _FPGA_TIMESTAMP_ADDR     = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 7
    _FPGA_SERIAL_NUMBER_ADDR = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 12
    _FPGA_IP_SETUP_BASE_ADDR = _CONTROL_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 13 # (13-18): target MAC, (19-22): target IP, (23-24): target_base_port, (25-32) = Target FPGA serial, (33): bit 7 = trigger, bits 3:2: mac source select, 1:0: broadcast group
    # _GPIO_IPCONFIG_REG       = _CONTROL_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 0x08D # Register address of the first byte of the IP config word

    # SPI Application registers
    _FPGA_MAC_ADDR_LSW_ADDR         = 4 * 7
    _FPGA_MAC_ADDR_MSW_IP_PORT_ADDR = 4 * 8
    _FPGA_IP_ADDR_ADDR              = 4 * 9
    _IRIGB_ADDR                     = 4 * 10
    _XILINX_OUI = 0x000A35

    # ---------------------------------------
    # Instance attributes
    # ---------------------------------------
    # mmi = None # Memory-mapped interface object
    _is_core_open = None

    fpga_ip_addr = None
    fpga_serial_number = None  # will be obsolete when we can get this from the ARM

    def set_auto_open_attributes(self, attribute_names, open_method):
        """ Create a number of attributes that will be created by
        'open_method' only when one of them is accessed.

        This is useful since hardware map queries can instantiate boards that
        we do not actually want to communicate with and may not event be
        physically present. With this method, we can delay communications with
        those iceboards until really need it.
        """
        class AutoOpen(object):
            """ This class takes the place of an object, and will call
            'open_method' on the fly whenever one of its attributes is
            accessed.
            """
            def __init__(self, parent, attribute_name, open_method):
                self._parent = parent
                self._attribute_name = attribute_name
                self._open_method = open_method

            def __getattr__(self, name):
                self._open_method()
                # setattr(self._parent, self._attribute_name, obj)
                return getattr(
                    getattr(self._parent, self._attribute_name), name)

            def __nonzero__(self):
                return False  # act as if this class was None

        for attribute_name in attribute_names:
            setattr(self,
                    attribute_name,
                    AutoOpen(self, attribute_name, open_method))

    def __init__(self, **kwargs):
        """
        Creates an Iceboard that is accessed through the networking parameters
        specified in the database.

        The created object does not have any fpga or hardware handlers yet.
        Those will be created when the Iceboard is opened.
        """
        super(chFPGAHandler, self).__init__(**kwargs)
        self.logger = logging.getLogger(__name__)
        self._mezzanine_ipmi_cache = {1: None, 2: None}
        self._is_open = None
        self._is_core_open = None
        self._core_auto_open_attributes = \
            ['mmi', 'hw', 'bp', 'i2c', 'core_gpio', 'core_i2c']
        self.set_auto_open_attributes(
            self._core_auto_open_attributes, self.open_core)

    def hwm_update(self, hwm_object):
        """ Is called when the Hardware Map object might have changed to
        reflect those changes in the handler.
        """
        super(chFPGAHandler, self).hwm_update(hwm_object)
        self.logger.info('chFPGAHandler: %r.hwm_update()' % (self))

    # ------------------------------------------------------------------
    # CHIME-specific MMI interface
    # ------------------------------------------------------------------
    # Uses direct Ethernet link to the FPGA SFP port to send commands in a UDP
    # packet.
    #
    # As the Chime Firmware pre-dates the icecore firmware, we do not use the
    # standard icecore interface to the FPGA, but that might change in the
    # future if warranted.
    # ------------------------------------------------------------------

    def mmi_read(self, *args, **kwargs):
        """ Read bytes at specified byte address through direct access to the
        FPGA."""
        return self.mmi.read(*args, **kwargs)

    def mmi_write(self, *args, **kwargs):
        """ Write bytes at specified byte address through direct access to the
        FPGA."""
        self.mmi.write(*args, **kwargs)

    # def spi_mmi_read(self, addr): """ Read a single 32-bit word at specified
    #     byte address through the ARM<->FPGA SPI link.""" return
    #     self._fpga_spi_peek(addr)

    # def spi_mmi_write(self, addr, value): """ Write a single 32-bit word at
    #     specified byte address through the ARM<->FPGA SPI link."""
    #     self._fpga_spi_poke(addr, value)

    def open_core(self):
        """
        Establishes the connection with the hardware and firmware on the
        IceBoard and create all appropriate handling classes.
        """

        cookie = self.get_fpga_application_cookie()
        if cookie != self._CHFPGA_COOKIE:
            raise RuntimeError(
                'The firmware currently configured on the FPGA is not chFPGA. '
                'Cannot access chFPGA-specific methods and resources.')

        self.fpga_serial_number = self.get_fpga_serial_number()  # Get SN from the SPI link

        # Get the address of the interface through which we can access the board over UDP
        if self.hostname:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.hostname, 80))
            (self.interface_ip_addr, _) = s.getsockname()
            s.close()
        else:
            self.interface_ip_addr = None

        # Compute the IP address to use for the FPGA UDP interface
        # For now, we replace a.b.c.d by a.b.3.d
        ip_packed = socket.inet_aton(self._get_arm_ip())  #
        ip_packed = ip_packed[:2] + chr(3) + ip_packed[3]
        self.fpga_ip_addr = socket.inet_ntoa(ip_packed)

        # Compute a MAC address for the FPGA
        # mac = socket.inet_aton(self._get_arm_mac())  #
        mac_packed = struct.pack('>H4s', 0x1234, ip_packed)

        self.fpga_port_number = self._FPGA_CONTROL_BASE_PORT

        # Set the FPGA Networking parameters over the ARM-FPGA SPI interface
        self.fpga_mmi_write(self._FPGA_MAC_ADDR_LSW_ADDR, struct.unpack('>I', mac_packed[2:6])[0])
        self.fpga_mmi_write(self._FPGA_MAC_ADDR_MSW_IP_PORT_ADDR, (struct.unpack('>H', mac_packed[0:2])[0] << 16) | self.fpga_port_number)
        self.fpga_mmi_write(self._FPGA_IP_ADDR_ADDR, struct.unpack('>I', ip_packed)[0])

        if not self.is_fpga_programmed():
            raise RuntimeError(
                "%r: Attempting to access the FPGA's Memory-mapped interface "
                "while the FPGA is not yet programmed with a bitstream"
                % (self))

        # if the FPGA handler instance was not created, check if one exists
        # create it
        if self.is_core_open():
            self.logger.warning(
                '%r: Attempting to open core while it is already opened. '
                'Ignoring.' % (self))
            return

        self.logger.info(
            '%r: core_open() is called' % (self))

        # Open MMI interface
        from . import fpga_mmi
        self.mmi = fpga_mmi.FpgaMmi(
            ip_addr=self.fpga_ip_addr,
            port_number=self.fpga_port_number,
            fpga_serial_number=self.fpga_serial_number,
            interface_ip_addr=self.interface_ip_addr,
            set_fpga_networking_parameters=False)
        self.mmi.open()
        self.local_port_number = self.mmi.local_port_number


        # Preallocate consecutive port numbers for data and correlator streaming
        from .lib import udp
        for i in [1, 2, 3]:
            udp.Udp(
                remote_ip_addr=self.fpga_ip_addr,
                remote_port_number=self.fpga_port_number,
                local_port_number=self.local_port_number + i,
                if_ip_addr=self.interface_ip_addr)


        # Open FPGA's GPIO interfaces and check if we have basic communications
        self.core_gpio = gpio.GPIO_base(self.mmi, self._SYSTEM_GPIO_BASE_ADDR)


        # -------------------------------------------------------------------------
        # Check if we can communicate with the FPGA over the direct Ethernet link by reading the mmi cookie (not the SPI one)
        # -------------------------------------------------------------------------
        self.logger.info("%r: Attempting to communicate with the FPGA over direct Ethernet link" % self)
        try:
            cookie = self.get_fpga_firmware_cookie()  # Read the firmware version cookie from the GPIO subsystem (this is provided by the FPGA core firmware which is always present on all versions of the FPGA)
        except Exception as e:
            error_message = "%r: Unable to communicate with the FPGA at address %s:%i due to the following exception: %s" % (self, self.fpga_ip_addr, self.fpga_port_number, repr(e))
            self.close()
            self.logger.error(error_message)
            raise

        # -------------------------------------------------------------------------
        # Double check the mmi cookie is corect
        # -------------------------------------------------------------------------

        if cookie != self._CHFPGA_COOKIE:
            error_message = '%r: The firmware at %s:%i is not chFPGA. The magic cookie returned by the FPGA is 0x%02X, whereas we expected 0x%02X' % (self, self.fpga_ip_addr, self.fpga_port_number, cookie, self._CHFPGA_COOKIE)
            self.logger.error(error_message)
            self.close()
            raise RuntimeError(error_message)

        self.logger.info("%r: Direct ethernet connection with the FPGA established" % self)

        # Open FPGA's I2C interfaces

        self.core_i2c = i2c.I2C_base(self.mmi, self._SYSTEM_I2C_BASE_ADDR)

        # Create standardized I2C interface
        self.i2c = I2CInterface(
            self.fpga_i2c_write_read,
            self.fpga_i2c_set_port,
            IceBoardHardware.FPGA_I2C_BUS_LIST,
            IceBoardHardware._FPGA_I2C_SWITCH_ADDR)

        # Open IceBoard hardware manager object
        self.hw = IceBoardHardware(iceboard=self)
        self.hw.open()

        self.bp = BackplaneHardware(iceboard=self)
        self.bp.open()

        self._is_core_open = True

    def close_core(self):

        if self.mmi:
            self.mmi.close()
        if self.hw:
            self.hw.close()
        if self.bp:
            self.bp.close()
        self.set_auto_open_attributes(self._core_auto_open_attributes,
                                      self.open_core)
        self._is_core_open = False

    def is_core_open(self):
        # return self.iceboard_pk in type(self)._active_instances
        return bool(self._is_core_open)

    def open(self):

        self.logger.info('chFPGAHandler: %r.open() is called' % (self))
        self.hw.init()

        self.hw.set_led('GP_LED2', 1)  # Hardware link is on
        self.hw.set_led('GP_LED1', 0)  # Full FPGA firmware is not yet on

        # ----------------------------------
        # Read basic backplane information (backplane S/N, slot number) so we
        # know where this board is in the array
        self.slot_number = self.get_slot_number()  # this method is provided by hw or arm
        # (self.backplane_serial, __) = icebox.IceBox.get_backplane_info(iceboard = self)

        # Detect the mezzanines
        # self.detect_mezz(force_type_string=forced_mezz_type)

        self._is_open = True

    def close(self):
        self.close_core()
        self._is_open = False

    def is_open(self):
        return self._is_open

    def get_fpga_firmware_cookie(self):
        """
        Reads the FPGA and returns the cookie that identifies the firmware.
        This method can be called before any FPGA modules are instatiated.
        """
        return self.mmi_read(self._GPIO_COOKIE_REG) & 0x7F

    def get_fpga_firmware_version(self):
        """
        Returns the firmware revion currenting running on the FPGA (which si
        the date and time of bitstream generation)
        """
        return self.core_gpio.get_bitstream_date()

    def fpga_i2c_write_read(self, *args, **kwargs):
        """
        Performs I2C read, write or SMB-compatible combined write/read
        operations (SMB or its subset PMB require the register address to be
        written and then data to be read immediately after an I2C restart. It
        cannot be done in separate write and read  operations).

        Writes up to 3 bytes to the addressed I2C device and/or reads up to 4
        bytes from that device after a restart.

        See the FPGA I2C module for detailed method description.
        """
        return self.core_i2c.write_read(*args, **kwargs)

    def fpga_i2c_set_port(self, *args, **kwargs):
        """
        Sets the FPGA hardware port over which the i2c communications will be
        made after this call.

        This selects the FPGA pins over which the communications is done,
        *not* the bus selection done by an I2C switch.
        """
        return self.core_i2c.set_port(*args, **kwargs)

    def _mezzanine_eeprom_read(self, mezzanine, addr, length,**kwargs):
        """ Reads the EEPROM on the specified mezzanine.

        NOTE: It would be nice if the ARM could provide this function.

        NOTE: Why not maintain the action_scope naming:
        _read_mezzanine_eeprom() to be consistent with the rest of the API
        """
        return self.hw.read_mezzanine_eeprom(mezzanine, addr, length, **kwargs)

    def _get_mezzanine_ipmi(self, mezzanine):
        """ Returns the IMPI data for the mezzanine located on slot
        'mezzanine' (1 or 2). Returns None if no mezzanine is present.

        This method overrides the ARM method of the same name so we can
        correctly read MGADC08 mezzanines which have a non-standard EEPROM
        data structure.
        """
        if not self.is_mezzanine_present(mezzanine):  # Check mezzanine presence using the FMC PRSNT line.
            return None

        try:
            # *** JFC: broken now. fixme
            return self.core_handler._get_mezzanine_ipmi(mezzanine)  # Try to get the ipmi data from tuber
        except tuber.TuberRemoteError:
            return self._get_mezzanine_mcgill_ipmi(mezzanine)

    def _get_mezzanine_mcgill_ipmi(self, mezzanine, retry=10):
        """ Loads the info data block from the mezzanine EEPROM using the old
        proprietary McGill format (not the FMC standard), and return the data
        converted into the standard FRU object..

        The ad-hoc McGill format is deprecated. It consists of a ID byte (0x0d
        for MGADC08) followed by a ASCII-pickeled dictionary of properties. The
        end of the dictionary is detected by the closing curly brace '}'.
        """
        import struct
        import zlib
        import ast  # used for safe McGill-format mezzanine EEPROM parsing

        if self._mezzanine_ipmi_cache[mezzanine]:
            return self._mezzanine_ipmi_cache[mezzanine]

        self._mezzanine_ipmi_cache[mezzanine] = None

        id_byte = ord(
            self._mezzanine_eeprom_read(
                mezzanine, addr=0, length=1, noerror=True)[0]
            )

        if id_byte != 0x0d:
            self.logger.error(
                'The EEPROM on mezzanine %i dies not have a valid ID'
                % mezzanine)
            return None

        # Read the eeprom block by block until we detect the end of the
        # dictionary
        block_size = 32
        string = ''
        for i in range(512 / block_size):  # read 32 blocks of 16 bytes
            data_block = self._mezzanine_eeprom_read(
                mezzanine, addr=i*block_size, length=block_size, retry=retry)
            string += data_block
            if ('}' in data_block) or (chr(255) in data_block):
                break

        last_char = string.find('}')
        if last_char < 0:
            self.logger.error(
                'No dictionary found on EEPROM. Did the board pass '
                'the quality control tests?')
            return None

        string = string[1:last_char+1]  # keep only the dict definition string: remove first char (board ID) and stop at last '}'.

        # Read checksum
        crc_string = self._mezzanine_eeprom_read(
            mezzanine, last_char+1, length=4, retry=retry)
        crc = struct.unpack('i', crc_string)[0]
        computed_crc = zlib.crc32(string)
        if computed_crc != crc:
            raise RuntimeError(
                'FMC EEPROM CRC is invalid. Read crc = %08X, '
                'computed crc = %08X' % (crc, computed_crc))
        dict_out = ast.literal_eval(string)  # safer than using eval

        # Extract standard FRU information from McGill data structure
        part_number = dict_out.pop('Model', 'Unknown')
        serial_number = dict_out.pop('Serial #', 'Unknown')
        product_version = dict_out.pop('Rev #', 'Unknown')
        mfg_date_str = dict_out.get('Date of last test', None)
        if mfg_date_str:
            mfg_date = datetime.strptime(mfg_date_str, '%d/%m/%Y')
        else:
            mfg_date = None

        fru = FRU(
            board=Board(
                mfg_date=mfg_date,
                manufacturer="Winterland",
                product_name="McGill Mezzanine",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=Product(
                manufacturer="Winterland",
                product_name="McGill Mezzanine",
                part_number=part_number,
                product_version=product_version,
                serial_number=serial_number,
                asset_tag="",
                fru_file="",
            ),
            multi=MultiDict(dict_out)
        )

        self._mezzanine_ipmi_cache[mezzanine] = fru
        return fru

    def _get_mezzanine_type(self, mezzanine):
        """ Returns the type of mezzanine located on slot 'mezzanine' (1 or 2).
        Returns None if no mezzanine is present.

        This method overrides the ARM method of the same name so we can call
        our own _get_mezzanine_ipmi() which can correctly read non-standard
        MGADC08 EEPROM data structure.
        """
        ipmi = self._get_mezzanine_ipmi(mezzanine)
        if ipmi and hasattr(ipmi,'product') and hasattr(ipmi.product, 'part_number'):
            return  ipmi.product.part_number
        else:
            return None

    # Backplane management

    # # Now supported by the ARM
    # def get_slot_number(self):
    #     """ Reads the slot number from the IO Expander. This is not
    #     necessarily the slot number stored in the hardware map. Slots numbers
    #     range from 1 to 16. A slot number of 0 or None indicates that the
    #     board is not connected to a backplane.

    #     NOTE: It would be nice if the ARM could provide this function.
    #     """
    #     if self.is_backplane_present():
    #         return self.hw.get_slot_number()
    #     else:
    #         return None

    # # Now supported by the ARM
    # def is_backplane_present(self):
    #     """ Checks if the Iceoard is connected to a backplane by probing the
    #     backplane's EEPROM.
    #     """
    #     return self.bp.is_backplane_present()

    def read_backplane_eeprom_ipmi(self):
        """ Return the IPMI data found on the backplane EEPROM.
        """
        return FRU.decode(self.bp.read_backplane_eeprom)


# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
