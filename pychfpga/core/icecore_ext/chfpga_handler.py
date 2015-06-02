""" Basic handler for chFPGA firmware.
"""

import logging
from datetime import datetime, timedelta
from calendar import timegm
import time

import socket
import struct

from ..icecore import IceBoardPlusHandler
from ..icecore import tuber  # Used to get TuberRemoteError
from ..icecore.hw.ipmi_fru import FRU, Board, Product, Chassis, MultiDict, CHASSIS_SUBCHASSIS


from .. import I2C as i2c
from .. import GPIO as gpio

from . import icecrate_handler  # this module is not referenced here, but loading it registers the handler with IceCrate.
from .iceboard_hardware import IceBoardHardware
from .iceboard_hardware import I2CInterface
from .backplane_hardware import BackplaneHardware
from .lib import udp

# import icebox # don't use from .. import ... because of circular import problems

class chFPGAHandler(IceBoardPlusHandler):
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
    _IRIGB_SAMPLE0_ADDR             = 4 * 10
    _IRIGB_SAMPLE1_ADDR             = 4 * 11
    _IRIGB_SAMPLE2_ADDR             = 4 * 12

    _IRIGB_TARGET0_ADDR             = 4 * 13
    _IRIGB_TARGET1_ADDR             = 4 * 14
    _IRIGB_TARGET2_ADDR             = 4 * 15
    _IRIGB_EVENT_CTR_ADDR           = 4 * 16
    _BP_BUCK_SYNC_ADDR              = 4 * 17
    _BP_BUCK_SYNC_ADDR2             = 4 * 18
    _SFP_STATUS_ADDR                = 4 * 19
    _REMOTE_IP_PORT_ADDR            = 4 * 20

    _XILINX_OUI = 0x000A35

    # ---------------------------------------
    # Instance attributes
    # ---------------------------------------

    fpga_ip_addr = None
    interface_ip_addr = None  # Is automatically detected by opening a TCP connection to the ARM


    class AutoOpen(object):
        """ Automatcally call the specified 'open' method that creates an
        attribute if the attribute is accessed and is not yet defined.
        """
        def __init__(self, open_method, attribute_name):
            self._open_method = open_method
            self._attribute_name = attribute_name

        def __get__(self, object, class_):
            print 'Auto-open %s' % self._attribute_name
            getattr(object, self._open_method)()  # Execute the open method
            return getattr(object, self._attribute_name)  # Get target object

    mmi       = AutoOpen('open_core', 'mmi')
    i2c       = AutoOpen('open_core', 'i2c')
    core_gpio = AutoOpen('open_core', 'core_gpio')
    core_i2c  = AutoOpen('open_core', 'core_i2c')
    hw        = AutoOpen('open_hw', 'hw')
    bp        = AutoOpen('open_bp', 'bp')

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
        self._is_core_open = None
        self._is_hw_open = None
        self._is_bp_open = None
        self._is_open = None

    # ------------------------------------------------------------------
    # CHIME-specific MMI interface
    # ------------------------------------------------------------------
    # Uses direct Ethernet link to the FPGA SFP port to read and write
    # firmware registers using UDP packets.
    #
    # As the CHIME Firmware pre-dates the ARM-to-FPGA communication link, we
    # generally do not use that (slower) link except for basic core functions.
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
        print '%r: opening core' % self

        # if not self.is_fpga_programmed():
        #     raise RuntimeError(
        #         'The FPGA is not programmed. Cannot access chFPGA-specific methods and resources.')

        if not self.is_fpga_programmed():
            raise RuntimeError(
                "%r: The FPGA is not programmed with a bitstream . "
                'Direct UDP link to FPGA and other chFPGA-specific methods and '
                'resources are not available.' % (self ))

        # Check the FPGA firmware cookie obtained through the ARM SPI interface to the FPGA
        cookie = self.get_fpga_application_cookie()
        if cookie != self._CHFPGA_COOKIE:
            raise RuntimeError(
                '%r: The firmware currently configured on the FPGA is not chFPGA (got cookie 0x%04X instead of 0x%04X). '
                'Direct UDP link to FPGA and other chFPGA-specific methods and '
                'resources are not available.' % (self, cookie, self._CHFPGA_COOKIE))

        # self.fpga_serial_number = self.get_fpga_serial_number()  # Get SN from the SPI link (slow)

        # Get the address of the interface through which we can access the
        # board over UDP by opening a TCP socket to the ARM and inspeting the
        # interface that was used. This assumes that both the ARM and FPGAs
        # are accessed through the same interface.
        if self.hostname:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.hostname, 80))
            (self.interface_ip_addr, _) = s.getsockname()
            s.close()
        else:
            self.interface_ip_addr = None

        # Compute the IP address to use for the FPGA UDP interface For now, we
        # replace a.b.c.d by a.b.3.d. We need to find a more generic mechanism
        # for this (like obtaining another IP from the DHCP server)
        ip_packed = socket.inet_aton(self._get_arm_ip())  #
        ip_packed = ip_packed[:2] + chr(3) + ip_packed[3]
        fpga_ip_addr = socket.inet_ntoa(ip_packed)

        # Set-up the FPGA networking parameters using the ARM-SPI link to the FPGA
        self.set_fpga_control_networking_parameters(fpga_ip_addr=fpga_ip_addr)


        # if the FPGA handler instance was not created, check if one exists
        # create it
        if self.is_core_open():
            self.logger.warning(
                '%.32r: Attempting to open core while it is already opened. '
                'Ignoring.' % (self))
            return

        # -------------------------------------------------------------------------
        # Open the UDP MMI interface
        # -------------------------------------------------------------------------
        from . import fpga_mmi
        self.mmi = fpga_mmi.FpgaMmi(
            ip_addr=self.fpga_ip_addr,
            port_number=self.fpga_port_number,
            interface_ip_addr=self.interface_ip_addr)
        self.mmi.open()
        self.local_port_number = self.mmi.local_port_number

        # -------------------------------------------------------------------------
        # Open FPGA's GPIO module interface
        # -------------------------------------------------------------------------
        self.core_gpio = gpio.GPIO_base(self.mmi, self._SYSTEM_GPIO_BASE_ADDR)

        # -------------------------------------------------------------------------
        # Check if we can communicate with the FPGA over the direct Ethernet
        # link by reading the UDP MMI cookie (not the SPI one) and check if
        # the cookie correspond to the chFPGA firmware.
        # -------------------------------------------------------------------------
        self.logger.info("%.32r: Attempting to communicate with the FPGA over direct Ethernet link" % self)
        try:
            cookie = self.get_fpga_firmware_cookie()  # Read the firmware version cookie from the GPIO subsystem (this is provided by the FPGA core firmware which is always present on all versions of the FPGA)
        except IOError as e:
            error_message = "%.32r: Unable to communicate with the FPGA at address %s:%i due to the following exception: %s" % (self, self.fpga_ip_addr, self.fpga_port_number, repr(e))
            self.close()
            self.logger.error(error_message)
            raise

        if cookie != self._CHFPGA_COOKIE:
            error_message = '%.32r: The firmware at %s:%i is not chFPGA. The magic cookie returned by the FPGA is 0x%02X, whereas we expected 0x%02X' % (self, self.fpga_ip_addr, self.fpga_port_number, cookie, self._CHFPGA_COOKIE)
            self.logger.error(error_message)
            self.close()
            raise RuntimeError(error_message)

        self.logger.info("%.32r: Established a UDP/Ethernet connection with the FPGA" % self)

        # -------------------------------------------------------------------------
        # Open FPGA's I2C interfaces
        # -------------------------------------------------------------------------
        self.core_i2c = i2c.I2C_base(self.mmi, self._SYSTEM_I2C_BASE_ADDR)
        # Create standardized I2C interface
        self.i2c = I2CInterface(
            self.fpga_i2c_write_read,
            self.fpga_i2c_set_port,
            IceBoardHardware.FPGA_I2C_BUS_LIST,
            IceBoardHardware._FPGA_I2C_SWITCH_ADDR)

        self._is_core_open = True

    def close_core(self):
        self.close_bp()
        self.close_hw()

        if self._is_core_open:
            self.mmi.close()
            # Make the AutoOpen data descriptior visible again
            del self.mmi, self.core_i2c, self.core_gpio, self.i2c
            self._is_core_open = False

    def is_core_open(self):
        # return self.iceboard_pk in type(self)._active_instances
        return bool(self._is_core_open)

    def open_hw(self):
        # Open IceBoard hardware manager object
        self.hw = IceBoardHardware(iceboard=self)
        self._is_hw_open = True
        self.hw.open()

    def close_hw(self):
        if self._is_hw_open:
            self.hw.close()
            del self.hw
            self._is_hw_open = False

    def open_bp(self):
        self.bp = BackplaneHardware(iceboard=self)
        self._is_bp_open = True
        self.bp.open()
        self.bp.init()

    def close_bp(self):
        if self._is_bp_open:
            self.bp.close()
            del self.bp
            self._is_bp_open = False

    def open(self):

        self.logger.info('%.32r: open() is called' % (self))
        self.open_core()

        self.hw.init()
        self.hw.set_led('GP_LED2', 1)  # Hardware link is on
        self.hw.set_led('GP_LED1', 0)  # Full FPGA firmware is not yet on

        self._is_open = True

    def close(self):
        self.close_core()
        self._is_open = False

    def is_open(self):
        return self._is_open

    def ping_fpga(self, timeout=0.3):
        # Open the core right now if needed so we don't mask IOError exceptions this could generate
        if not self.is_core_open():
            self.open_core()
        try:
            self.mmi_read(self._GPIO_COOKIE_REG, timeout=timeout)
            return True
        except IOError:
            return False

    def check_command_count(self, reset=False):
        """ Returns a boolen that checks if the number of command and replies sent to/from the FPGA
        by the Python memory mapped interface matches the counts tallied by the FPGA
        firmware.

        Since both ends drop packets that have invalid CRCs, this should
        detect any transmission error in addition to UDP packets dropped by
        the switches, routers or the networking stack on the host computer.

        The packet counts are modulo 256, so a loss of a multiple of 256 packets will not be detected.

        If 'reset' is True, the MMI counters are reset to the FPGA values in order to clear the error on future checks.
        """

        (cmd, rply) = self.core_gpio.get_command_count()
        valid = (cmd == self.mmi.send_counter & 0xFF) and (rply == self.mmi.recv_counter & 0xFF)
        if reset:
            self.mmi.send_counter = cmd
            self.mmi.recv_counter = rply
        return valid

    def set_fpga_control_networking_parameters(self, fpga_mac_addr=None, fpga_ip_addr=None, fpga_port_number=_FPGA_CONTROL_BASE_PORT, local_port=0):
        """ Set the FPGA UDP networking parameters using the ARM SPI MMI link.
        'fpga_ip_addr' is a mandatory string in the format of 'a.b.c.d', where a,b,c and d are decimal numbers.

        'fpga_port_number' is the port to which command packets are sent to on the FPGA. This port is 41000 by default.

        'fpga_mac_addr' is a string representing the MAC address of the FPGA in the format 'xx:xx:xx:xx:xx:xx, where
        'xx' is a hex number'. If fpga_mac_addr is None, an arbitrary MAC address is
        created using the IP address to ensure its uniqueness.

        'local port' is the port number to which command replies are sent
        back. If 'local_port' is 0 (default), the command reply packets will
        be sent back to source port number of the last command packet received
        by the FPGA (which presumably is the command that sollicited the
        reply) .
        """

        ip_packed = socket.inet_aton(fpga_ip_addr)  #

        # Compute a MAC address for the FPGA
        # mac = socket.inet_aton(self._get_arm_mac())  #
        if fpga_mac_addr is None:
            mac_packed = struct.pack('>H4s', 0x1234, ip_packed)
            fpga_mac_addr = ':'.join(['%02X' % ord(c) for c in mac_packed])
        else:
            mac_packed = [chr(int(s, 16)) for s in fpga_mac_addr.split(':')]

        self.fpga_mac_addr = fpga_mac_addr
        self.fpga_port_number = fpga_port_number
        self.fpga_ip_addr = fpga_ip_addr

        # Set the FPGA Networking parameters over the ARM-FPGA SPI interface
        self.fpga_mmi_write(self._FPGA_MAC_ADDR_LSW_ADDR, struct.unpack('>I', mac_packed[2:6])[0])
        self.fpga_mmi_write(self._FPGA_MAC_ADDR_MSW_IP_PORT_ADDR, (struct.unpack('>H', mac_packed[0:2])[0] << 16) | fpga_port_number)
        self.fpga_mmi_write(self._FPGA_IP_ADDR_ADDR, struct.unpack('>I', ip_packed)[0])

    def set_local_data_port_number(self, port):
        """ Sets the port number to which the FPGA is sending its captured data stream on the control network.

        If port==0, the data is sent to the control port number + 1.
        """
        word = self.fpga_mmi_read(self._REMOTE_IP_PORT_ADDR)
        self.fpga_mmi_write(self._REMOTE_IP_PORT_ADDR, (word & 0xFFFF) | (port << 16))

    def get_local_data_port_number(self):
        """ Return the port number to which the FPGA is sending its captured data stream on the control network.
        """
        return self.fpga_mmi_read(self._REMOTE_IP_PORT_ADDR) >> 16


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

    def _mezzanine_eeprom_read(self, mezzanine, addr, length, **kwargs):
        """ Reads the EEPROM on the specified mezzanine.

        If length == -1, the data is read from the specified address until the end of the EEPROM.

        NOTE: It would be nice if the ARM could provide this function.

        NOTE: Why not maintain the action_scope naming:
        _read_mezzanine_eeprom() to be consistent with the rest of the API
        """
        return self.hw.read_mezzanine_eeprom(mezzanine, addr, length, **kwargs)

    def _get_mezzanine_mcgill_ipmi(self, mezzanine, retry=3):
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
            return tuber.TuberObject.__getattr__(self,'_get_mezzanine_ipmi')(mezzanine)  # Try to get the ipmi data from tuber
        except tuber.TuberRemoteError:
            pass
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
        part_number = dict_out.pop('Model', 'MGADC08')
        serial_number = dict_out.pop('Serial #', 'Unknown')
        product_version = dict_out.pop('Rev #', 'Unknown')
        mfg_date_str = dict_out.get('Date of last test', None)
        try:
            mfg_date = datetime.strptime(mfg_date_str, '%d/%m/%Y')
        except ValueError:
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
        ipmi = self._get_mezzanine_mcgill_ipmi(mezzanine)
        if ipmi and hasattr(ipmi,'product') and hasattr(ipmi.product, 'part_number'):
            return ipmi.product.part_number
        else:
            return None

    def read_backplane_eeprom_ipmi(self):
        """ Return the IPMI data found on the backplane EEPROM.
        """
        return FRU.decode(self.bp.read_backplane_eeprom)

    class _IrigTimestamp(object):
        pass

    _IRIGB_SOURCE_TABLE = {
        'bp_trig': 0,
        'bp_time': 1
        }

    def set_irigb_source(self, source):
        """ Set the source of the IRIG-B signal."""
        if source not in self._IRIGB_SOURCE_TABLE:
            raise ValueError('Invalid IRIG-B source name. Valid names are %s' % ', '.join(self._IRIGB_SOURCE_TABLE.keys()))
        w2 = self.fpga_mmi_read(self._IRIGB_SAMPLE2_ADDR)
        self.fpga_mmi_write(self._IRIGB_SAMPLE2_ADDR, (w2 & 0x3FFFFFFF) | (self._IRIGB_SOURCE_TABLE[source] << 30))

    def get_irigb_source(self):
        """ Get the name of the current source of the IRIG-B signal."""
        source = self.fpga_mmi_read(self._IRIGB_SAMPLE2_ADDR) >> 30

        for (source_name, source_number) in self._IRIGB_SOURCE_TABLE.items():
            if source == source_number:
                return source_name
        raise ValueError('The IRIG-B module has an unknown source')

    _IRIGB_TIME_FORMAT = {
        'datetime': lambda ts: ts.datetime,
        'nano' : lambda ts: ts.nano,
        'datetime+': lambda ts: (ts.datetime, ts.nano % 1000000000),
        'raw': lambda ts: ts
        }


    def _get_irigb_time(self, trig=True, format='datetime', noerror=False):
        """ Reads the IRIG-B time from the time decoder and returns an object
        that contains all the time information gathered from it.

        If trig=True, the time of the next 10 MHz reference clock rising edge
        is measured and returned. Otherwise, the last captured time is returned.
        """

        if format not in self._IRIGB_TIME_FORMAT:
            raise ValueError('Invalid time format. Valid formats are: %s' % (', '.join(self._IRIGB_TIME_FORMAT.keys())))

        # Capture current time
        if trig:
            w2 = self.fpga_mmi_read(self._IRIGB_SAMPLE2_ADDR)
            self.fpga_mmi_write(self._IRIGB_SAMPLE2_ADDR, w2 & ~(1 << 29))
            self.fpga_mmi_write(self._IRIGB_SAMPLE2_ADDR, w2 | (1 << 29))  # Create a rising edge
            t0 = time.time()
            while not self.fpga_mmi_read(self._IRIGB_TARGET1_ADDR) & (1 << 29):
                if time.time() - t0 > 1:
                    raise RuntimeError('Timeout while waiting for a Reference clock edge')

        w0 = self.fpga_mmi_read(self._IRIGB_SAMPLE0_ADDR)
        w1 = self.fpga_mmi_read(self._IRIGB_SAMPLE1_ADDR)
        w2 = self.fpga_mmi_read(self._IRIGB_SAMPLE2_ADDR)

        # t0 = self.fpga_mmi_read(self._IRIGB_TARGET0_ADDR)
        # t1 = self.fpga_mmi_read(self._IRIGB_TARGET1_ADDR)
        # t2 = self.fpga_mmi_read(self._IRIGB_TARGET2_ADDR)
        # e0 = self.fpga_mmi_read(self._IRIGB_EVENT_CTR_ADDR)

        ts = self._IrigTimestamp()
        ts.pps = (w0 >> 26) & ((1 << 6) - 1)
        ts.sbs = (w0 >> 8) & ((1 << 18) - 1)
        ts.y = (w0 >> 0) & ((1 << 8) - 1)
        ts.d = (w1 >> 20) & ((1 << 9) - 1)
        ts.h = (w1 >> 14) & ((1 << 6) - 1)
        ts.m = (w1 >> 7) & ((1 << 7) - 1)
        ts.s = (w1 >> 0) & ((1 << 7) - 1)
        ts.ss = (w2 >> 0) & ((1 << 28) - 1)
        ts.source = (w1 >> 30) & ((1 << 2) - 1)
        ts.recent = (w1 >> 29) & 1
        ts.datetime = datetime(ts.y + 2000, 1, 1) + timedelta(ts.d-1, ts.s, ts.ss//100, 0, ts.m, ts.h)
        # ts.before_target = (t1 >> 31) & 1
        # ts.done = (t1 >> 30) & 1
        ts.nano = int(timegm((ts.y+2000, 1, 1, 0, 0, 0))*1e9) + (ts.d*24*3600 + ts.h*3600 + ts.m*60 + ts.s)*1000000000 + ts.ss*10
        # ts.event_ctr = e0
        if not ts.recent and not noerror:
            raise RuntimeError('Invalid IRIG-B signal')

        return self._IRIGB_TIME_FORMAT[format](ts)

    def set_irigb_trigger_time(self, datetime_=None, delay=None):
        """ Sets the time at which the IRIG-B module will generate a trigger
        that can be used to synchronize boards.

        'datetime_' is the base target time in the Python as a 'datetime' object.

        'delay' is a time offset in seconds that is added to 'datetime_' so set
        the target time. It defaults to zero.

        If the trigger is used for synchronizing boards, the delay should be a
        multiple of 100 ns in order to ensure alignment with the 10 MHz
        reference clock and ensure deterministic start of the syncronization
        state machine.

        If 'datetime_' and 'delay' are None, the trigger time is set 3 seconds after the current time.
        """
        if datetime_ is None:
            dt = self._get_irigb_time(trig=True, format='datetime')
            self.logger.info('%.32r: Current IRIGB time is %s' % (self, dt.isoformat()))
            if delay is None:
                delay = 3
        else:
            dt = datetime_
            if delay is None:
                delay = 0

        nano_delay = int(delay * 1e9) % 1000  # Get submicrosecond delay in nanosecond units
        delay = int(delay * 1e6)/1e6  # Round delay to the microsecond
        dt += timedelta(0, delay)
        self.logger.info('%.32r: Setting IRIGB target time to %s + %3i ns' % (self, dt.isoformat(), nano_delay))

        y = dt.year % 100
        d = (dt - datetime(dt.year, 1, 1)).days + 1
        h = dt.hour
        m = dt.minute
        s = dt.second
        ss = dt.microsecond * 100 + int(nano_delay/10)

        t0 = (y << 0)
        t1 = (d << 20) | (h << 14) | (m << 7) | (s << 0)
        t2 = (1 << 31) | (ss << 0)

        self.fpga_mmi_write(self._IRIGB_TARGET0_ADDR, t0)
        self.fpga_mmi_write(self._IRIGB_TARGET1_ADDR, t1)
        self.fpga_mmi_write(self._IRIGB_TARGET2_ADDR, t2)

    def is_irigb_before_trigger_time(self):
        """ Is true if the current IRIGB is before the target trigger time that was previously set-up.
        """
        t1 = self.fpga_mmi_read(self._IRIGB_TARGET1_ADDR)
        return bool((t1 >> 31) & 1)

    def capture_frame_time(self, trig=True, format='nano'):
        """ Captures the IRIG-B of the first sample of the next frame coming
        out of the ADC data acquisition module.

        The returned time is (frame_number, time), where frame_number is the
        number of the frame that was measured, and time is the IRIG-B time in
        a format specified by 'format' (see get_irigb_time() for available
        formats).

        NOTE1: floats do not have enough resolution to represent the current
        time down to nanoseconds (as opposed to Pythin int's which have
        infinite resolution), so beware of conversions.

        NOTE2: The method will generate a timeout error if there is no data
        coming out of the data acquisition module.

        NOTE3: There is a delay between the time the first sample of a packet
        is taken and the time the packet comes out of the data acquistion
        module (due to initial dropping of a few frames and the FIFO filling-
        delay).
        """


        if trig:
            w2 = self.fpga_mmi_read(self._IRIGB_SAMPLE2_ADDR)
            self.fpga_mmi_write(self._IRIGB_SAMPLE2_ADDR, w2 & ~(1 << 28))
            self.fpga_mmi_write(self._IRIGB_SAMPLE2_ADDR, w2 | (1 << 28))
            t0 = time.time()
            while not self.fpga_mmi_read(self._IRIGB_TARGET1_ADDR) & (1 << 30):
                    if time.time() - t0 > 1:
                        raise RuntimeError('Timeout while waiting for a Frame. Is data flowing out of the ADC data acquisition module?')
        event_number = self.fpga_mmi_read(self._IRIGB_EVENT_CTR_ADDR)
        captured_time = self._get_irigb_time(trig=0, format=format)  # The event trigger will automatically trig IRIGB
        return (event_number, captured_time)

    def capture_refclk_time(self, trig=True, format='nano'):
        """ Measures the time at which the next 10MHz reference clock rising
        edge occurs.

        The returned time is an integer representing the number of nanoseconds
        since Jan 1st 2000.

        This can be used to measure the drift of the 10 MHz clock relative to
        the IRIG-B time.
        """
        return self._get_irigb_time(trig=trig, format=format)  #

    def get_irigb_time(self, trig=True, format='datetime'):
        """ Return the current time as decoded on the IRIG-B input. The time
        is returned in a format specified by 'format':

        'datetime': Python 'datetime' object (with a microsecond resolution)
        'datetime+': A (dt,nano) tuple where dt is a datetime object, and nano is the number of nanoseconds within the second.
        'nano': An integer representing the number of nanoseconds since Jan 1st 2000.
        """
        return self._get_irigb_time(trig=trig, format=format)


# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
