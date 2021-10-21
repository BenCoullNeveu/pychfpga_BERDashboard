""" Defines the class to operate the ZCU111.
"""
# Standard Python packages
import logging
from datetime import datetime, timedelta
from calendar import timegm
import time
import struct
import base64
from collections import OrderedDict
import socket
import asyncio

import nest_asyncio
# External private packages

from wtl.metrics import Metrics

# Local packages

from .motherboard import Motherboard
from .async_utils import run_async, async_to_sync
from .tcpipe import TCPipe
from .lib.bsb_mmi import BSB_MMI
from ..icecore.hardware_assets import IceBoardBase
from ..icecore.hardware_assets import FMCMezzanineBase
from ..icecore.tuber import TuberError, TuberNetworkError, TuberRemoteError
from .hardware_map import HardwareMap
from .icecrate_ext import IceCrate
from .ccoll import Ccoll
from ..chFPGA_controller import chFPGA

from .. import I2C as i2c
from .. import GPIO as fpga_gpio

# from lib import tmp100  # I2C Temperature sensor
from .lib.pca9575 import pca9575  as tca9575a # I2C 16-bit IO Expander
from .lib.tca9548a import tca9548a as tca9548a  # I2C switch
from .lib.tca9544a import tca9544a as pca9544a # I2C switch
from .lib.sc18is602b import sc18is602b # I2C-to-SPI bridge
from .lib.tca6416a import tca6416a
from .lib.lmk04208spi import lmk04208spi # RF dual PLL
from .lib.lmx2594spi import lmx2594spi # ADC/DAC PLL

# from .lib import ina230  # I2C Voltage and current monitor
from .lib.eeprom import eeprom
# from .lib import qsfp
# from .lib import gpio


class TCPipe_BSB_MMI(BSB_MMI):
    """
    Provides read/write functions for accessing the FPGA's memory-map registers through a
    Byte-serial Bus interface through the TCPipe interface.

    """

    def __init__(self, tcpipe):

        super().__init__()
        self.tcpipe = tcpipe
        self.send_counter = 0
        self.recv_counter = 0

    def _send_command(self, cmd, expected_reply_length, retry=1, resync=False, **kwargs):
        reply = self.tcpipe.bsb_write_read(cmd)
        if len(reply) != expected_reply_length + 1:
            raise IOError('Unexpected number of reply bytes')
        return reply[1:]

class TCPipe_I2C:
    """
    This class wraps all that is needed to access an I2C device in
    a standardized way, whether the access is done through the
    FPGA or through the ARM.

    AN instance of this object is passed to the I2C drivers to provide them the methods to access their hardware.
    """

    I2CException = IOError  # Exception object to expect from I2C communication errors

    def __init__(self, tcpipe, verbose=None):
        super().__init__()
        self.tcpipe = tcpipe
        self._logger = logging.getLogger(__name__)
        self.current_port = None;  # I2C port currently in use
        self.current_switch_params = {}  # keep track of switch params so we don't set the switch needlessly

    def select_bus(self, bus_info, retry=1):
        """
        Configure the I2C port and I2C switches so the following
        communications will access the desired I2C bus. 'bus_id'
        can be a bus name or bus number, or a list of those if
        multiple buses are to be accessed at the same time. An
        error will be provided if all the buses are not accessible
        through the same FPGA I2C port. This function assumes that
        each FPGA I2C port has an identical I2C switch.

        Parameters:

            bus_info (dict): Describes the port, switch and switch parameter
                - port (int): I2C port to use
                - switch (instance): switch instance
                - switch_params (int or dict): arguments to pass to the switch instance

            args, kwargs: passed to the bus select function

        Exceptions:

            IOError: Raised by an FPGA-based I2C controller in case of transaction errors

        """
        self.current_port = bus_info['port']
        switch = bus_info['switch']
        if not switch:
            return
        switch_params = bus_info['switch_params']
        if self.current_switch_params.setdefault(switch, None) == switch_params:
            return
        if isinstance(switch_params, dict):
            switch.set_port(**switch_params)
        else:
            switch.set_port(switch_params)
        self.current_switch_params[switch] = switch_params

    # def write_read(self, *args, **kwargs):
    def write_read(self, addr=0, data=[0], read_length=0, verbose=1, noerror=False, retry=1):
        """
        Writes and read to/from I2C device at address `addr`.


        Parameters:

            addr (int): I2C address

            data (list of int): list of bytes to write before the read operation. If ``None``, no write is performed.

            read_length (int): Number of bytes to read. Can be 0-4 after the a
                preceding write operation, or 0-3 without a write operation.

            verbose (int): verbosity level

            noerror (bool): if True, no exception will be raised

            retry (int): Number of times to retry a transfer before raising an exception

        Returns:
            bytearray containing the read bytes

        Exceptions:

            IOError: Raised by an FPGA-based I2C controller in case of transaction errors
            ValueError: Is raised when `addr`, `read>_length` or `write_length` are out of range.

        """
        # self._logger.debug("Accessing I2C bus...")

        addr |= 0x80 if self.current_port else 0

        if not data:  # if we have no data to write, just read
            return list(self.tcpipe.i2c_read(addr,read_length)) # list for backwards compatibility
        elif not read_length:  # if we have data to write but nothing to read
            return self.tcpipe.i2c_write(addr, data)
        else:  # if we both write and read
            return list(self.tcpipe.i2c_write_read(addr, data, read_length))

    def is_present(self, addr, bus_name=None):
        """ Test the presence of an I2C device at the specified address.

        Parameters:

            addr (int): I2C address of the device to query

            bus_name (str, int, or list of str or int): I2C bus(es) to activate

        """
        if bus_name:
            self.select_bus(bus_name, retry=3)
        try:
            self.write_read(addr, data=[], read_length=0, retry=0)  # dummy I2C acces
        except IOError:
            return False
        return True

class iic_dummy:
    def __init__(self, *args, **kwargs):
        pass


class ZCU111(Motherboard):
    """ Provide the basic code needed to operate the ZCU111


    If is assumed that the board is running the bridge software.

    Provides:
        - Lightweight list-based Hardware map management
        - Model, serial, slot, crate and mezzanine self discovery through the Iceboard (no mDNS required)
        - Access to the memory-mapped registers in the FPGA's firmware using the TCP link.

    Parameters:





    Old notes

       `IceBoardPlusHandler` can be created as a standard Python object initialized with a number of
    parameters which set corresponding attributes (see below). If a `parent_getter` function is
    provided, the value of these attributes will instead be fetched
    dynamically from the parent object. Note that any explicitely specified parameter overrides a
    parent parameter.

    Parameters:
        parent_getter (func): Function that returns the dynamically return the parent object from which the following parameters will be fetched. Is `None` if there is no parent.
        hostname (str): hostname or IP address of the ICEBoard ARM processor (mandatory)
        serial (str): Serial number of the board. Can be provided by the ARM.
        part_number (str): Part number of the IceBoard. Can be obtained from the ARM.
        crate (IceCrateHandler): = object that handle the backplane on which the board is connected. `None` if the board is not connected to a backplane.
        slot (int): Slot number in which the board is installed ona backplane. None if there is no backplane.
        mezzanine (dict): Map {mezzanine_number: Mezzanine Handler, ...} describing the installed mezzanines. Can be obtained from the ARM.
        tuber_objname (str): name of the set of software functions that will be provided by the ARM processor through the Tuber interface.



    .. Any object provided by this this handler can be accessed at any
    .. hierarchical level. However, objects that are probided by Tuber have these
    .. restrictions:
    ..
    ..    - attributes and methods whise name begin with '_' are not accessible
    ..    - modification to the object attributes must be done by a setter
    ..      function provided by the object.
    ..    - methods or attribute access can only return string or numeric values,
    ..      or lists or dictionnary thereof


    Notes:
        - The SPI MMI interface is currently provided by peek/poke methods accessed through Tuber.
          However, if one day the ARM supports it, a faster access could potentially be provided by
          overriding the fpga_spi_mmi_read_async/write methods to send the commands to a dedicated ARM port
          and thus bypass Tuber's HTTP/JSON overhead. Since the SPI link is relatively slow anyway, this might not be useful until a faster ARM-FPGA link is in place (such as the unused PCIe link).

        - This handler does *not* define a MMI interface that uses the FPGA's
          ethernet port directly through the SFP+ connector. Such functionnality is to be provided by a
          subclass of this class if the firmware supports it.

    """

    # Define model number for hardware map management and discovery
    part_number = 'ZCU111'
    _ipmi_part_numbers = ['ZCU111']

    NUMBER_OF_FMC_SLOTS = 0

    # ---------------

    FPGA_CONTROL_BASE_PORT = 41000
    _BROADCAST_BASE_PORT = 41000

    # Base address is always at zero so we can gather info from the FPGA
    # before we know the number of channelizers etc.
    _SYSTEM_BASE_ADDR = 0x00000
    _SYSTEM_GPIO_BASE_ADDR = _SYSTEM_BASE_ADDR + 0x00000
    _SYSTEM_FREQ_CTR_BASE_ADDR = _SYSTEM_BASE_ADDR + 0x02000
    _SYSTEM_I2C_BASE_ADDR = _SYSTEM_BASE_ADDR + 0x05000

    # Match those with what is used by Module
    _CONTROL_BASE_ADDR = TCPipe_BSB_MMI._CONTROL_BASE_ADDR
    _STATUS_BASE_ADDR = TCPipe_BSB_MMI._STATUS_BASE_ADDR
    _RAM_BASE_ADDR = TCPipe_BSB_MMI._RAM_BASE_ADDR

    _CHFPGA_COOKIE = 0x42  # Expected cookie value for chFPGA, both on the SPI and UDP MMI

    # GPIO Register addresses
    _GPIO_COOKIE_REG = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR  # Register address of the firmware cookie
    _FPGA_TIMESTAMP_ADDR = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 7
    _FPGA_SERIAL_NUMBER_ADDR = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 12
    _FPGA_IP_SETUP_BASE_ADDR = _CONTROL_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 13
    # Unused addresses:
    #   (13-18): target MAC,
    #   (19-22): target IP,
    #   (23-24): target_base_port,
    #   (25-32) = Target FPGA serial,
    #   (33): bit 7 = trigger, bits 3:2: mac source select, 1:0: broadcast group

    # # Register address of the first byte of the IP config word
    # _GPIO_IPCONFIG_REG       = _CONTROL_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 0x08D

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
    _IRIGB_EVENT_CTR_ADDR2          = 4 * 17
    _BP_BUCK_SYNC_ADDR              = 4 * 18
    _SFP_STATUS_ADDR                = 4 * 19
    _REMOTE_IP_PORT_ADDR            = 4 * 20
    _IRIGB_REFCLK_SAMPLE            = 4 * 21

    _XILINX_OUI = 0x000A35



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

    _backplane_initialized = False  # Indicate if we have initialized the backplane access yet
    _cached_repr = None





    def __init__(self, hostname=None, serial=None, slot=None, subarray=None, **kwargs):
        super().__init__(
            hostname=hostname,
            serial=serial,
            slot=slot,
            subarray=subarray, **kwargs)

        self.iic = None
        self.mmi = None
        self.tcp = None
        self._is_open = None
        self.fw = None  # firmware object


    def __getattr__(self, name):
        if self.fw:
            return getattr(self.fw, name)
        else:
            raise AttributeError(f'Unknown attribute {name}')

    def __dir__(self):
        return list(set(super().__dir__() +
                       (self.fw.__dir__() if self.fw else [])))


    def init(self):
        run_async(self.init_async())

    async def init_async(self):
        await self.open_async()


    async def open_async(self, **kwargs):

        self.logger.debug(f'{self!r}: open() is called')


        # Open tcp communication with the board
        self.logger.debug(f'{self!r}: Opening TCP connection to the board')
        self.tcp = TCPipe(self.hostname)

        # create a BSP-MMI
        self.mmi = TCPipe_BSB_MMI(self.tcp)

        # create I2C interface

        self.iic = TCPipe_I2C(self.tcp)

        # self.core_gpio.set_channelizer_reset(True)  # stop the channelizer from sending data while we initialize
        # await self.open_hw()
        # await self.hw.init()
        # await self.hw.set_led('GP_LED2', 1)  # Hardware link is on
        # await self.hw.set_led('GP_LED1', 0)  # Full FPGA firmware is not yet on

        ina226 = iic_dummy
        irps5401 = iic_dummy
        zynq_sysmon = iic_dummy
        si5341b = iic_dummy
        si570 = iic_dummy
        si5382 = iic_dummy
        # lmk04208spi = iic_dummy
        # lmx2594spi = iic_dummy

        self.i2c0_switch = i2c0_switch = pca9544a(self.iic, address=0x75)
        self.i2c_gpio = tca6416a(self.iic, address=0x20, port=dict(port=0, switch=i2c0_switch, switch_params=None))
        self.i2c_ina226_0v85 = ina226(self.iic, address=0x41, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_1v8 = ina226(self.iic, address=0x42, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_vccintrf = ina226(self.iic, address=0x49, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_mgt1v2 = ina226(self.iic, address=0x47, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_vcc1v2 = ina226(self.iic, address=0x43, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_dacavtt = ina226(self.iic, address=0x4A, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_vadj = ina226(self.iic, address=0x45, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_mgt1v8 = ina226(self.iic, address=0x48, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_mgtavcc = ina226(self.iic, address=0x46, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_dac_vccaux = ina226(self.iic, address=0x71, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_adc_vccaux = ina226(self.iic, address=0x73, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_adc_vcc = ina226(self.iic, address=0x4c, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        self.i2c_ina226_dac_vcc = ina226(self.iic, address=0x4e, port=dict(port=0, switch=i2c0_switch, switch_params=0))

        self.i2_irps5401a = irps5401(self.iic, address=0x43, port=dict(port=0, switch=i2c0_switch, switch_params=2))
        self.i2_irps5401b = irps5401(self.iic, address=0x44, port=dict(port=0, switch=i2c0_switch, switch_params=2))
        self.i2_fpga_sysmon = zynq_sysmon(self.iic, address="TBD", port=dict(port=0, switch=i2c0_switch, switch_params=3))

        self.i2c1_switch0 = i2c1_switch0 = tca9548a(self.iic, address=0x74)
        self.i2c1_switch1 = i2c1_switch1 = tca9548a(self.iic, address=0x75)
        self.i2c_eeprom = eeprom(self.iic, address=0x54, bus_name=dict(port=1, switch=i2c1_switch0, switch_params=0), address_width=8, max_read_length=255)
        self.i2c_fixed_clocks = si5341b(self.iic, address=0x36, port=dict(port=1, switch=i2c1_switch0, switch_params=1))
        self.i2c_fixed_clocks = si570(self.iic, address=0x5d, port=dict(port=1, switch=i2c1_switch0, switch_params=2))
        self.i2c_mgt_clocks = si570(self.iic, address=0x5d, port=dict(port=1, switch=i2c1_switch0, switch_params=3))
        self.i2c_recovery_clocks = si5382(self.iic, address=0x68, port=dict(port=1, switch=i2c1_switch0, switch_params=4))
        self.i2c_spi = sc18is602b(self.iic, address=0x2f, port=dict(port=1, switch=i2c1_switch0, switch_params=5))
        self.i2c_rf_pll = lmk04208spi(self.iic, address=0x2f, spi_port=1, port=dict(port=1, switch=i2c1_switch0, switch_params=5))
        self.i2c_adc0_pll = lmx2594spi(self.iic, address=0x2f, spi_port=3, port=dict(port=1, switch=i2c1_switch0, switch_params=5))
        self.i2c_adc1_pll = lmx2594spi(self.iic, address=0x2f, spi_port=2, port=dict(port=1, switch=i2c1_switch0, switch_params=5))
        self.i2c_dac_pll = lmx2594spi(self.iic, address=0x2f, spi_port=0, port=dict(port=1, switch=i2c1_switch0, switch_params=5))


        rf_pll_spi_port = 2
        # Set SPI mux to route PLL output mux pin to I2C-SPI MISO input
        self.i2c_gpio.select()
        # self.i2c_gpio.write_reg('CFG1',0b000, mask=0b00000110)  # set GPIO mux pins to output
        # self.i2c_gpio.write_reg('CFG1',rf_pll_spi_port << 1, mask=0b00000110)  # set mux pins to 0b10 (LMK04208)
        self.i2c_spi.select()
        self.i2c_rf_pll.init()
        self.i2c_adc0_pll.init()
        self.i2c_adc1_pll.init()
        # self.i2c_dac_pll.init()

        # from .. import FreqCtr, GPIO
        # self.GPIO = GPIO.GPIO_base(self, self._SYSTEM_GPIO_BASE_ADDR)
        # self.FreqCtr = FreqCtr.FreqCtr_base(self, self._SYSTEM_FREQ_CTR_BASE_ADDR)
        # self._is_open = True

        self.fw = chFPGA()



    def close(self):
        self.close_core()
        self._is_open = False

    def is_open(self):
        return self._is_open


    async def open_core(self):
        """
        Establishes connection with the board and instantiate
        the basic objects that are essential to communicate with the FPGA
        firmware and the board hardware, including I2C link through the FPGA.

        """

        # Check if core communications with the FPGA was already opened
        if self._is_open:
            self.logger.debug(
                f'{self!r}: Attempting to open core while it is already opened. '
                f'Ignoring.')
            return


        # Open tcp communication with the board
        self.tcp = TCPipe(self.hostname)

        # create a BSP-MMI
        self.mmi = TCPipe_BSB_MMI(self.tcp)

        # create I2C interface

        self.iic = TCPipe_I2C(self.tcp)

        # Check the FPGA firmware cookie obtained through the ARM SPI interface to the FPGA
        cookie = await self.get_fpga_application_cookie()
        if cookie != self._CHFPGA_COOKIE:
            raise RuntimeError(
                '%r: The firmware currently configured on the FPGA is not '
                'chFPGA (got cookie 0x%04X instead of 0x%04X). '
                'Direct UDP link to FPGA and other chFPGA-specific methods and '
                'resources are not available.' % (self, cookie, self._CHFPGA_COOKIE))

        # self.fpga_serial_number = self.get_fpga_serial_number()  # Get SN from the SPI link (slow)

        # Get the address of the interface through which we can access the
        # board over UDP by opening a TCP socket to the ARM and inspeting the
        # interface that was used. This assumes that both the ARM and FPGAs
        # are accessed through the same interface.
        if not self.interface_ip_addr:  # set the interface only of we haven't manually defined one
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
        if not self.fpga_ip_addr:
            ip_packed = socket.inet_aton(await self._tuber_get_arm_ip_async())
            ip_tuple = tuple(c for c in ip_packed)
            ip_packed = bytes(self.fpga_ip_addr_fn(*ip_tuple))
            # ip_packed = ip_packed[:2] + chr(3) + ip_packed[3]
            self.fpga_ip_addr = socket.inet_ntoa(ip_packed)

        # Compute the local port number if requested (self.local_control_port_number
        # is None) and if possible (there is a slot and crate number)
        if self.local_control_port_number is None:
            if not self.slot or not self.crate or self.crate.crate_number is None:
                self.local_control_port_number = 0
                self.logger.debug(
                    f'{self!r}: Cannot use slot/crate_number-based UDP port number '
                    f'for UDP control channel. There is no slot or crate_number'
                    f' info. Using OS-assigned random port')
            else:
                self.local_control_port_number = self._FPGA_CONTROL_BASE_PORT + 16*self.crate.crate_number + (self.slot-1)
                # self.logger.info('%r: Replies will be sent to %s:%i'
                #                  % (self, self.interface_ip_addr, self.local_control_port_number))

        # -------------------------------------------------------------------------
        # Open the UDP MMI interface
        # -------------------------------------------------------------------------
        from .lib import fpga_mmi
        self.logger.info(
            '%r: Opening FPGA MMI with FPGA=(%s:%s),  local=(%s:%s)' % (
                self,
                self.fpga_ip_addr,
                self.fpga_control_port_number,
                self.interface_ip_addr,
                self.local_control_port_number))

        self.mmi = fpga_mmi.FpgaMmi(
            fpga_ip_addr=self.fpga_ip_addr,
            fpga_port_number=self.fpga_control_port_number,  # none or 0: use local port number
            interface_ip_addr=self.interface_ip_addr,
            local_port_number=self.local_control_port_number,  # 0 = randomly assigned by os
            udp_retries=self.udp_retries,
            parent=self)

        self.mmi.open()
        self.local_control_port_number = self.mmi.local_port_number
        self.fpga_control_port_number = self.mmi.fpga_port_number

        # Select the fpga port number
        # if not self.fpga_control_port_number:
        #    self.fpga_control_port_number = self.local_control_port_number

        # Set-up the FPGA networking parameters using the ARM-SPI link to the FPGA
        self.fpga_mac_addr = await self.set_fpga_control_networking_parameters_async(
            fpga_ip_addr=self.fpga_ip_addr,
            fpga_port_number=self.fpga_control_port_number)

        # -------------------------------------------------------------------------
        # Open FPGA's GPIO module interface
        # -------------------------------------------------------------------------
        self.core_gpio = fpga_gpio.GPIO_base(self, self._SYSTEM_GPIO_BASE_ADDR)

        # -------------------------------------------------------------------------
        # Check if we can communicate with the FPGA over the direct Ethernet
        # link by reading the UDP MMI cookie (not the SPI one) and check if
        # the cookie correspond to the chFPGA firmware.
        # -------------------------------------------------------------------------
        self.logger.debug(f"{self!r}: Clearing FPGAs UDP communication stack")
        await self.reset_fpga_udp_stack()
        self.mmi.flush()

        self.logger.debug(
            f"{self!r}: Attempting to communicate with the FPGA over direct "
            f"Ethernet link")
        try:
            # Read the firmware version cookie from the GPIO subsystem (this
            # is provided by the FPGA core firmware which is always present on
            # all versions of the FPGA)
            cookie = await self.get_fpga_firmware_cookie(resync=True)
        except IOError as e:
            error_message = (
                "%r: Unable to communicate with the FPGA at address %s:%i "
                "due to the following exception: %s" % (
                    self,
                    self.fpga_ip_addr,
                    self.fpga_control_port_number,
                    repr(e)))
            self.close()
            self.logger.error(error_message)
            raise

        if cookie != self._CHFPGA_COOKIE:
            error_message = (
                '%r: The firmware at %s:%i is not chFPGA. The magic cookie '
                'returned by the FPGA is 0x%02X, whereas we expected 0x%02X' % (
                    self, self.fpga_ip_addr, self.fpga_control_port_number, cookie, self._CHFPGA_COOKIE))
            self.logger.error(error_message)
            self.close()
            raise RuntimeError(error_message)

        self.logger.debug(
            f"{self!r}: Established a UDP/Ethernet connection with "
            f"the FPGA at {self.fpga_ip_addr}:{self.fpga_control_port_number}")

        # -------------------------------------------------------------------------
        # Open FPGA's I2C interfaces
        # -------------------------------------------------------------------------
        self.core_i2c = i2c.I2C_base(self, self._SYSTEM_I2C_BASE_ADDR)
        await asyncio.sleep(0)
        # Create standardized I2C interface
        self.i2c = I2CInterface(
            write_read_fn=self.fpga_i2c_write_read,  # write-read function
            port_select_fn=self.fpga_i2c_set_port,
            bus_table=IceBoardHardware.FPGA_I2C_BUS_LIST,
            switch_addr=IceBoardHardware._FPGA_I2C_SWITCH_ADDR,
            parent=self)  # parent object, whose repr() is used to tag messages

        self._is_core_open = True

    def close_core(self):
        # self.close_bp()
        self.close_hw()

        if self._is_core_open:
            self.mmi.close()
            # Make the AutoOpen data descriptior visible again
            del self.mmi
            del self.core_i2c, self.core_gpio, self.i2c
        self._is_core_open = False

    def is_core_open(self):
        # return self.iceboard_pk in type(self)._active_instances
        return bool(self._is_core_open)

    async def open_hw(self):
        # Open IceBoard hardware manager object
        self.hw = IceBoardHardware(iceboard=self)
        self._is_hw_open = True
        await self.hw.open()

    def close_hw(self):
        if self._is_hw_open:
            self.hw.close()
            del self.hw
            self._is_hw_open = False

    NUMBER_OF_ANTENNAS = 8
    def is_fmc_present(self, slot):
        return False


    async def ping_async(self, timeout=0.1):
        """
        Returns a boolean indicating whether a tuber object is available at
        the specified ARM hostname.
        """
        # print(f'{self!r} Ping_async()')
        self.logger.info('%r: Pinging %s' % (self, self.tuber_uri))
        try:
            await self._tuber_get_meta_async()
            await self._tuber_sleep_async(0)
            return True
        except TuberError as e:
            self.logger.debug(
                f'{self!r}: Tuber Ping returned an error. '
                f'Board is considered to be absent. Error is \n{e!r}')
            return False

    ###################################
    # Auto discovery methods
    ###################################

    async def discover_serial_async(self, update=True):
        """
        Discover the serial number of this IceBoard from its IPMI data, and update the hardware map accordingly if `update=True`
        """
        self.logger.debug(f'{self!r}: discovering the serial number of board at {self.tuber_uri}')
        try:
            actual_serial = str((await self.tuber_get_motherboard_serial_async()))
        except Exception as e:  #  Deal with uninitialized boards
            self.logger.warning('%r: Error while attempring to read the board serial number. The exception is %r' % (self, e))
            actual_serial = None
        self.logger.debug(f'{self!r}: got the serial number of board at {self.tuber_uri} to be {actual_serial}')
        await asyncio.sleep(0)
        if update:
            if not actual_serial:
                self.logger.warning('%r: Could not read the board serial number from IPMI storage or serial number is null. Serial number is not updated.' % (self))
            elif self.serial and actual_serial != self.serial:
                self.logger.warning('%r: The discovered serial number differs from the current (hardware map) one. Updating to the discovered value.' % (self))
            self.update_instance(serial=actual_serial)
        self.logger.debug(f'{self!r}: finished discovering the serial number of board at {self.tuber_uri}')
        return(self.serial)

    async def discover_slot_async(self, update=True):
        """ Discover the slot number of this IceBoard, and update the hardware map accordingly if `update=True`"""
        actual_slot = await self.tuber_get_backplane_slot_async()
        if update:
            if not actual_slot:
                self.logger.warning('%r: The board is not connected to a backplane. Slot number is not updated.' % (self))
            elif self.slot and actual_slot != self.slot:
                self.logger.warning('%r: The discovered slot (%s) number differs from the current (hardware map) one (%s). Updating to the discovered slot.' % (self, actual_slot, self.slot))
            self.update_instance(slot=actual_slot)
        return(self.slot)

    async def discover_mezzanines_async(self, update=True):
        """Detect mezzanines attached to the motherboard and update the hardware map accordingly if
        update=True.

        """
        return None


    async def discover_crate_async(self, update=True):
        """ Detect the crate in which the board is installed and update the hardware map accordingly.
        """

        return None

    # ------------------------------------
    # FPGA Processor-based Memory-mapped interface
    # ------------------------------------
    # Those methods are used to access the 32-bit register set of the
    # firmware. Those registers are always accessible by the on-board
    # processor, and are used to set-up basic functions such as Ethernet
    # ports, and IRIG-B time management.

    async def fpga_spi_mmi_read_async(self, addr):
        """ Read a single 32-bit word from the FPGA at the specified byte
        address. This uses the fastest interface available (currently the ARM-
        FPGA SPI link)

        Value is returned as an unsigned integer.
        """
        word = await self._tuber_fpga_spi_peek_async(addr)
        return(word & 0xFFFFFFFF)

    async def fpga_spi_mmi_write_async(self, addr, value):
        """ Write a single 32-bit word to the FPGA at specified byte address.
        This uses the fastest interface available (currently the ARM-FPGA SPI
        link)
        """
        await self._tuber_fpga_spi_poke_async(addr, value)



    # Mezzanine management

    async def _mezzanine_eeprom_read_async(self, mezzanine):
        """ Returns the contents of the specified mezzanine's EEPROM.
        """
        return None

    # Backplane/crate-related methods

    async def _write_motherboard_spi_eeprom_base64(self, *args, **kwargs):
        return None

    async def is_backplane_present_async(self):
        return False

    async def get_slot_number(self):
        return None

    async def get_iceboard_clock_source_async(self):
        return "CRYSTAL"

    def get_iceboard_clock_source_sync(self):
        return "CRYSTAL"

    def get_motherboard_temperature(self, sensor):
        """ Synchronous wrapper to return motherboard temperature sensor value.
        """
        return run_async(self.tuber_get_motherboard_temperature_async(sensor))


    # ----------------------------
    # Python Bitstream management
    # ----------------------------
    # @classmethod
    # def register_fpga_bitstream(cls, bitstream, tag=None):
    #     """ Register a bitstream that is associated with this application
    #     handler.

    #     'bitstream' can be any object whose str() property returns a valid
    #           bitstream (e.g. a string, a buffer or a FpgaBitstream object).

    #     This is to provide to host-based Python application a functionnality
    #     equivalent to that of the ARM-based applications handlers which can
    #     also access the relevant bitstream.
    #     """
    #     cls._bitstream_register[tag] = bitstream

    async def is_fpga_programmed_async(self):
        return await self.tuber_is_fpga_programmed_async()


    async def set_fpga_bitstream_async(self, buf=None, tag=None, force=False):
        '''
        Configures the FPGA with the specified bitstream.

        The bitstream associated with the current handler with the specifiec
        'tag' will be loaded. However, if a buffer 'buf' is explicitely
        provided, that bitstream will be used instead.,

        The 'buf' can be  a ``bytes`` or object with .bytes or .base64 attributes
        .BIT or .BIN file.

        By default, the FPGA will not be reconfigured it already has a
        bitstream with the same CRC signature. That behavior can be changed by
        specifying the 'force' argument:

            force = True: FPGA will always be configured
            force = False: FPGA will be configured if it is not configured or
                    if bitstream CRC differ
            force = None: FPGA will be configured only if it is not configured
        '''

        t0 = time.time()
        self.logger.debug(f'{self!r}: called set_fpga_bitstream')

        if hasattr(self, 'close'):
            self.close()

        # If the bitstream is not explicitely provided, ask the handler to
        # provide it. The str() of the returned object must yield the valid
        # bitstream buffer in a string.
        if buf is None:
            buf = self.get_fpga_bitstream(tag)

        if hasattr(buf, 'crc32'):
            crc32 = buf.crc32
        else:
            crc32 = zlib.crc32(str(buf))  # compute CRC32 of the data if it not already precomputed in the 'buf' object
        crc32 &= 0xFFFFFFFF
        # buf = buf.bytes()

        self.logger.debug(f'{self!r}: Getting is_programmed')
        is_fpga_programmed = await self.tuber_is_fpga_programmed_async()
        t1 = time.time()
        self.logger.debug(f'{self!r}: Getting FPGA crc')
        fpga_bitstream_crc = await self.get_fpga_bitstream_crc_async()
        self.logger.debug(
            f'{self!r}: fpga_programmed={is_fpga_programmed}, force={force}, '
            f'fpga_crc={fpga_bitstream_crc or 0:08X}, bitstream_crc={crc32 or 0:08X}')
        t2 = time.time()
        if not is_fpga_programmed or force \
           or (force is not None and (fpga_bitstream_crc != crc32)):
            self.logger.debug(f'{self!r}: Configuring FPGA')
            if hasattr(buf, 'base64'):
                b64_bytes = buf.base64
            elif hasattr(buf, 'bytes'):
                b64_bytes = base64.b64encode(buf.bytes)
            elif isinstance(buf, bytes):
                b64_bytes = base64.b64encode(buf)
            else:
                raise TypeError('buf is not a bytes object')

            # self._set_fpga_bitstream_base64(b64_bytes)
            t3 = time.time()

            # Configure FPGA with the target bitstream. Use
            # tuber_use_json_cache() context to allow reuse the json encoding
            # of the command between instances to save time, but especially
            # memory on large arrays
            with self.tuber_use_json_cache():
                await self._tuber_set_fpga_bitstream_base64_async(b64_bytes)
            await self.set_fpga_bitstream_crc_async(crc32)
            t4 = time.time()
            self.logger.debug(f'{self!r}: Done configuring FPGA. '
                f'It took {t4-t0:.3f}s ({t1-t0:.3f}s, {t2-t1:.3f}s, {t3-t2:.3f}s, {t4-t3:.3f}s)')
        else:
            t4 = time.time()
            self.logger.debug(
                f'{self!r}: FPGA is already configured. Skipping configuration. Took {t4 - t0:.3f}s')

    def get_fpga_bitstream(self, tag=None):
        """ Return the bitstream associated with this handler for the supplied
        tag as a string.

        If no bitstream is registered for this Handler or if no bitstream match
        the tag, the method attempts to obtain the bitstream through Tuber.
        """
        if tag in self._bitstream_register:
            return self._bitstream_register[tag]
        else:
            raise ValueError("Unknown bitstream tag")

    async def get_fpga_bitstream_crc_async(self):
        """ Return the signature of the firmware currently configured in the
        FPGA.

        Returns None if the FPGA is not configured.
        """
        is_fpga_programmed = await self.is_fpga_programmed_async()
        if not is_fpga_programmed:
            return None
        crc = await self.fpga_spi_mmi_read_async(self.FPGA_FIRMWARE_CRC32_ADDR)
        return crc
        # return self._bitstream_crc

    async def set_fpga_bitstream_crc_async(self, crc32):
        """ Return the signature of the firmware currently configured in the
        FPGA.

        Returns None if the FPGA is not configured.
        """
        if (await self.is_fpga_programmed_async()):
            # self._bitstream_crc = crc32
            await self.fpga_spi_mmi_write_async(self.FPGA_FIRMWARE_CRC32_ADDR, crc32)
        else:
            # self._bitstream_crc = None
            await self.fpga_spi_mmi_write_async(self.FPGA_FIRMWARE_CRC32_ADDR, 0)


    # Bitstream management

    # Core firmware functions

    async def get_fpga_core_cookie(self):
        """ Return the core FPGA firmware cookie. Should always be 0xBEEFFACE.
        """
        if not (await self.is_fpga_programmed_async()):
            return(None)
        cookie = await self.fpga_spi_mmi_read_async(self.FPGA_CORE_FIRMWARE_COOKIE_ADDR)
        return(cookie)

    async def get_fpga_application_cookie(self):
        """ Return the application-specific FPGA firmware cookie. """
        if not (await self.is_fpga_programmed_async()):
            return(None)
        cookie = await self.fpga_spi_mmi_read_async(self.FPGA_APPLICATION_FIRMWARE_COOKIE_ADDR)
        return(cookie)

    async def get_fpga_serial_number(self):
        """ Return the FPGA serial number, as read from the FPGA's core
        firmware throught the MMI interface. """
        fpga_serial_number = (
            (await self.fpga_spi_mmi_read_async(self.FPGA_SERIAL_NUMBER_LSW_ADDR)) |
            (await (self.fpga_spi_mmi_read_async(self.FPGA_SERIAL_NUMBER_MSW_ADDR) << 32))
            )

        return(fpga_serial_number)

    async def get_fpga_firmware_timestamp(self):
        """ Returns a string containing the date-time of the currrent firmware
        bitstream.
        """
        timestamp = await self.fpga_spi_mmi_read_async(self.FPGA_FIRMWARE_TIMESTAMP_ADDR)
        seconds = (timestamp >> 0) & 0x3F
        minutes = (timestamp >> 6) & 0x3F
        hour = (timestamp >> 12) & 0x1F
        year = (timestamp >> 17) & 0x3F
        month = (timestamp >> 23) & 0x0F
        day = (timestamp >> 27) & 0x1F
        timestamp_string = '%04i-%02i-%02i %02i:%02i:%02i' % (
            year + 2000, month, day, hour, minutes, seconds)
        return(timestamp_string)

    async def check_tuber_version_async(self):
        """ Check if the ARM processor provides the methods required to run this code. """

        required_tuber_methods = [ # Use the unmangled name as published by the ARM
            'is_fpga_programmed']#, '_mezzanine_eeprom_read_base64']

        (meta, props, tuber_methods) = await self._tuber_get_meta_async()  # get the meta info
        if not tuber_methods:
            raise RuntimeError("%r: The ARM does not publish any methods under the object name '%s'. Was the right Tuber object name used for this ARM firmware?" % (self, self.tuber_objname))

        for method in required_tuber_methods:
            if method not in tuber_methods:
                raise RuntimeError("%r: The current version of the ARM firmware does not provide the method '%s' that is needed for this application" % (self, method))

        return True

    def print_tuber_methods(self):
        """ Print all the methods and properties provided by the Iceboard's
        ARM processor through the Tuber protocol.
        """
        (meta, props, methods) = self._tuber_get_meta()  # get the meta info
        print("Methods for tuber object '%s':" % self.tuber_objname)
        print('-----------------------------------------')
        for method_name, method_properties in sorted(methods.items()):
            print('%-30s: %s' % (method_name, method_properties.summary))
        print()
        print("Properties for tuber object '%s':" % self.tuber_objname)
        print('-----------------------------------------')
        for prop_name, prop_properties in sorted(props.items()):
            try:
                values = ', '.join('.%s' % p for p in prop_properties)
            except TypeError:
                values = '= %s' % prop_properties
            print('%-30s: %s' % (prop_name, values))

########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
#
# dP                    888888ba                                   dP  88888888b            dP
# 88                    88    `8b                                  88  88                   88
# 88 .d8888b. .d8888b. a88aaaa8P' .d8888b. .d8888b. 88d888b. .d888b88 a88aaaa    dP.  .dP d8888P
# 88 88'  `"" 88ooood8  88   `8b. 88'  `88 88'  `88 88'  `88 88'  `88  88         `8bd8'    88
# 88 88.  ... 88.  ...  88    .88 88.  .88 88.  .88 88       88.  .88  88         .d88b.    88
# dP `88888P' `88888P'  88888888P `88888P' `88888P8 dP       `88888P8  88888888P dP'  `dP   dP
#
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################

class IceBoardExt:
    """ Extends the basic IceBoard class by providing additional SPI MMI -based firmware features, direct UDP MMI
    with the FPGA,  and methods to access to IceBoard hardware directly via the FPGA.

    This class provides:

    - UDP/IP/Ethernet-based direct Memory Map Interface (MMI) to the FPGA using its Ethernet port. Note
      that this accesses an address space that is separate from the one accessed throughthe ARM SPI interface.
      Methods to initialize the Ethernt networking parameters through the ARM SPI interface are provided.

    - Alternate access to the IceBoard and Backplane hardware through the FPGA I2C interface through
      the `hw` object. Access to the hardware is normally done through the high-level ARM-provided
      methods, but these methods are useful for development and debugging. The exception is the the
      IceCrate handler which uses the FPGA to access backplane resources.

    - Overriden mezzanine identification methods that support non-IPMI McGill ADC mezzanine boards.

    - IRIG-B subsystem operation (through the ARM SPI interface)

    `IceBoardExtHandler` can be created as a standard Python object
    initialized with a number of parameters which set corresponding attributes
    (see below). If a `parent_getter` function is provided, the value of some
    of these attributes will instead be fetched dynamically from the parent
    object unless explicit values (i.e. not None) are provided here. An
    explicittly provided parameter will always use the provided value and will
    no longer be fetched from the parent, nor will it be set on the parent.


    Parameters:

        parent_getter (func): Function that dynamically return the parent object from which the
            following parameters will be fetched. Is `None` if there is no parent.

        hostname (str): hostname or IP address of the ICEBoard ARM processor (mandatory)

        serial (str): Serial number of the board. Can be provided by the ARM.

        part_number (str): Part number of the IceBoard. Can be obtained from the ARM.

        crate (IceCrateHandler): = object that handle the backplane on which the board is connected.
            `None` if the board is not connected to a backplane.

        slot (int): Slot number in which the board is installed ona backplane. None if there is no
            backplane.

        mezzanine (dict): Map {mezzanine_number: Mezzanine Handler, ...} describing the installed
            mezzanines. Can be obtained from the ARM.

        tuber_objname (str): name of the set of software functions that will be provided by the ARM
            processor through the Tuber interface.

        fpga_ip_address (str): FPGA's listening IP address in the form
            'xx.xx.xx.xx'. If None (default), the address will be obtained by
            converting the ARM address using the function provided in
            fpga_ip_addr_fn.

        fpga_ip_addr_fn (function): function (A,B,C,D) = fn(a,b,c,d) which
            generates the FPGA address (A,B,C,D) based on the ARM IP address
            (a,b,c,d).

        fpga_control_port_number (int): FPGA's listening port number for commands. Defaults to 41000. If None,
            the local port number is used.

        local_port_number (int): UDP port number to use to receive command
            replies. If 0, the number is allocated randomly by the OS. If
            None, a fixed number based on the crate_number and a slot number
            will be used if available.

        interface_ip_addr (str): IP address of the interface to be used to
            communicate with both the ARM and FPGA. If `None`, the interface
            will be detected automatically by establishing a connection with
            the ARM.


    Python-based application-specific FPGA firmware and hardware handler are meant to be derived
    from this class.
    """


    def __init__(
            self,

            hostname=None,
            serial=None,
            slot=None,
            subarray=None,

            fpga_ip_addr=None,
            fpga_ip_addr_fn=lambda a, b, c, d: (a, b, 3, d),
            fpga_control_port_number=None,
            local_control_port_number=None,
            interface_ip_addr=None,
            udp_retries=10
            ):
        """
        Creates an Iceboard that is accessed through the networking parameters
        specified in the database.

        The created object does not have any fpga or hardware handlers yet.
        Those will be created when the Iceboard is opened.
        """
        super().__init__(
            hostname=hostname,
            serial=serial,
            slot=slot,
            subarray=subarray)
        # self.logger = logging.getLogger(__name__)

        # Store object-specific local paramaters

        self.fpga_ip_addr = fpga_ip_addr
        self.fpga_ip_addr_fn = fpga_ip_addr_fn
        self.udp_retries = udp_retries
        self.fpga_control_port_number = fpga_control_port_number
        self.local_control_port_number = local_control_port_number
        self.interface_ip_addr = interface_ip_addr

        # Initialize local variables

        self._mezzanine_ipmi_cache = {1: None, 2: None}
        self._is_core_open = None
        self._is_hw_open = None
        # self._is_bp_open = None
        self._is_open = None


    async def ping_fpga_async(self, timeout=0.3):
        # Open the core right now if needed so we don't mask IOError exceptions this could generate
        if not self.is_core_open():
            await self.open_core()
        try:
            self.mmi_read(self._GPIO_COOKIE_REG, timeout=timeout)
            return True
        except IOError:
            return False

    UDP_STATUS_VECT_BITS = [
            # Name, lsb pos, width
            ('tx_fifo_overflow', 17, 1),
            ('rx_fifo_overflow', 16, 1),
            ('sfp_remote_fault', 13, 1),
            ('sfp_duplex_mode', 12, 1),
            ('sfp_speed', 10, 2),
            ('rxnotintable',6, 1),
            ('rxdisperr', 5, 1),
            ('link_sync', 1, 1),
            ('link_status', 0, 1)]

    async def get_fpga_udp_metrics_async(self):
        metrics = Metrics(
            type='GAUGE',
            slot=(self.slot or 0) - 1,
            id=self.get_string_id(),
            crate_id=self.crate.get_string_id() if self.crate else None,
            crate_number=self.crate.crate_number if self.crate else None)

        if not self.is_open():
            return(metrics)
        try:
            # await self.check_command_count_async(reset=True)
            metrics.add('fpga_udp_error_current_count', value=self.mmi.error_counter)
            vect = await self.fpga_spi_mmi_read_async(self._SFP_STATUS_ADDR)
            for name, pos, width in self.UDP_STATUS_VECT_BITS:
                metrics.add('fpga_udp_' + name, value= (vect >> pos) & (2**width-1))
        except IOError as e:
            self.logger.error('%r: Error getting FPGA udp metrics. Error is %r' % (self, e))
        return(metrics)

    async def get_udp_status_async(self):
        vect = await self.fpga_spi_mmi_read_async(self._SFP_STATUS_ADDR)
        return {name: ((vect >> pos) & (2**width-1)) for name, pos, width in self.UDP_STATUS_VECT_BITS}

    async def clear_fpga_udp_errors(self, force=False, no_reset=False, max_trials=3):
        """ Attempts to clear the FPGA UDP communication errors.

        Parameters:

            force (bool): If True, the UDP stack is reset whether of not the
                current number of communication errors exceed the threshold or
                not.

        """
        trial = 1
        while True:
            if force or self.mmi.error_counter > 40:
                self.logger.warning(f'{self!r}: Resetting FPGA UDP stack (trial #{trial}/{max_trials})')

                if not no_reset:
                    await self.reset_sfp()
                    await asyncio.sleep(0.1)
                    await self.reset_fpga_udp_stack()
                    await asyncio.sleep(0.1)
                self.logger.debug(f'{self!r}: Trying to read from FPGA UDP stack')
                try:
                    self.mmi.flush()
                    self.mmi.read(0, length=1, retry=-1, resync=1)
                    self.mmi.read(0, length=1, resync=1)
                    self.mmi.flush()
                    (cmd, rply) = self.core_gpio.get_command_count()
                    self.mmi.send_counter = cmd
                    self.mmi.recv_counter = rply
                    break
                except IOError:
                    if trial >= max_trials:
                        # raise IOError(
                        #      '%r: cannot communicate with FPGA port after '
                        #      '%i FPGA UDP stack resets' % (self, trial))
                        self.logger.error(
                            f'{self!r}: cannot communicate with FPGA port '
                            f'after {trial} FPGA UDP stack resets')
                        break
                    else:
                        self.logger.warning(
                            f'{self!r}: Still obtaining FPGA UDP errors '
                            f'after {trial} FPGA UDP stack reset. Retrying...')
                    trial += 1
                finally:
                    self.mmi.error_counter = 0
                    self.logger.debug(f'{self!r}: Finished to attempt clearing FPGA UDP errors.')
            else:
                break

    async def check_command_count_async(self, reset=False):
        """ Check UDP communication command/reply synchronization and optionally reset counts.

        Checks if the number of command and replies sent to/from the FPGA
        by the Python memory mapped interface matches the counts tallied by the FPGA
        firmware.

        Parameters:
            reset (bool): If true, reset the counts so the counts will be synchronized for the next command

        Returns:
            True if the communication (before the optional reset) is in sync.


        Since both ends drop packets that have invalid CRCs, this should
        detect any transmission error in addition to UDP packets dropped by
        the switches, routers or the networking stack on the host computer.

        The packet counts are modulo 256, so a loss of a multiple of 256 packets will not be detected.

        If 'reset' is True, the MMI counters are reset to the FPGA values in order to clear the error on future checks.
        """

        for trial in range(2):
            try:
                await asyncio.sleep(0)
                self.logger.debug(f'{self!r}: Checking command counters')
                (cmd, rply) = self.core_gpio.get_command_count()
                await asyncio.sleep(0)
                valid = (cmd == self.mmi.send_counter & 0xFF) and (rply == self.mmi.recv_counter & 0xFF)
                if not valid:
                    self.logger.warning(
                        '%r: Command counters differ cmd/rply in FPGA is (%i, %i), '
                        'Python MMI is (%i, %i)'
                        % (self, cmd, rply, self.mmi.send_counter & 0xFF,
                           self.mmi.recv_counter & 0xFF))
                if reset:
                    self.mmi.send_counter = cmd
                    self.mmi.recv_counter = rply
                    valid = True
                break
            except IOError as e:
                self.logger.error(
                    "%r: UDP communinication error. Attempting to reset FPGA's"
                    " UDP stack via the ARM processor (trial %i).The error is:\n %s"
                    % (self, trial+1, e))
                await self.reset_fpga_udp_stack()
                valid = False
                reset = True
            except Exception as e:
                self.logger.error(
                    "%r: Unhandled error during UDP communinication check. "
                    "The error is:\n %r" % (self, e))
                raise
        else:  # executes if we exhausted the for loop iterations, i.e  no break
            errmsg = "%r: Could not re-establish UDP communinication with " \
                     "the FPGA. Raising an exception" % (self)
            self.logger.error(errmsg)
            raise IOError(errmsg)
        return(valid)

    async def reset_fpga_udp_stack(self):
        # self.logger.warning("%r: Resetting %s FPGA's UDP communication stack" % (self, self.hostname))
        await self.fpga_spi_mmi_write_async(self._SFP_STATUS_ADDR, 3 << 30)
        await self.fpga_spi_mmi_write_async(self._SFP_STATUS_ADDR, 0 << 30)
        self.mmi.send_counter = 0

    async def reset_sfp(self):
        self.logger.warning(
            "%r: Temporarily disconnecting the SFP to reset the %s FPGA's "
            "UDP communication stack" % (self, self.hostname))
        await self.tuber_set_pci_switch_direction_async('SEL_ARM')
        await self.tuber_set_pci_switch_direction_async('SEL_SFP')

    async def set_fpga_control_networking_parameters_async(
            self,
            fpga_mac_addr=None,
            fpga_ip_addr=None,
            fpga_port_number=None):
        """
        Set the FPGA listening UDP networking parameters for the FPGA's *incoming* control packets
        using the ARM SPI MMI link. Reply packets will be sent back over UDP transmit channel 0, i.e.
        back to the address and port from which the command originated..

        This method sets the FPGA's listening addresses while assuming that the FPGA's is in
        addressing mode "00" (the default addressing mode),  which means that the channel 0
        IP/PORT/MAC will be set through the ARM-FPGA SPI registers [Note1].

        Parameters:

            fpga_mac_addr (str): MAC address of the FPGA in the format
                'xx:xx:xx:xx:xx:xx, where 'xx' is a hex number'. If fpga_mac_addr is None, an
                arbitrary MAC address is created using the IP address to ensure its uniqueness.

            fpga_ip_addr (str):  Address at which the FPGA listens for commands. The address is in
                the format of 'a.b.c.d', where a,b,c and d are decimal numbers.

            fpga_port_number (int): Port on which the FPGA listens for commands. This port is 41000
                by default. It is independent from the port from which the host computer sends and
                receives packets, which can be any port.

        Returns:

            str: MAC address that was used/computed, in the form 'xx:xx:xx:xx:xx'

        This method sets up the FPGA's *incoming* traffic network parameters (in other words, the
        FPGA listening address). The  *outgoing* command reply packets are sent through either UDP
        transmit channels 0 or 1. The channel on which the *commands* are returned is set by the
        FPGA GPIO field CTRL_RPLY_IP_PORT_OFFSET. This is set to channel '0' by default, and should
        not be changed.

        UDP channel 0 sends packets with the following destination:

            * target mac address: Is hardwired to use the source MAC address of the last valid
              packet received
            * target ip address: Is hardwired to use the source IP of the last valid IP packet
              received
            * target port number: Is set in the in the lower 16-bits of the SPI register
              _REMOTE_IP_PORT_ADDR. The default is a value of 0, meaning that the target port will
              be the source port number of the last valid received packet. This default should
              normally not be changed. There is no direct method provided in this class to override
              the default. This method does not affect this parameter.

        With the default configuration, the user can bind a UDP socket to any port (or let the
        system choose by specifying port 0 to the bind() method).  The outgoing command packets will
        have the source IP and source port set to that value, and reply packets will automatically
        come back to this port without having to set up the return port manually. Letting the socket
        choose ports allows the system to easily connect to multiple boards without having to ensure
        the availability of specific ports. Note that is might be necessary to bind the socket to a
        specific interface address in case there are multiple interfaces in the system.


        UDP Channel 1 is generally used to send back data to the host computer. See
        `set_data_target_address` for a decription of that channel.



        [Note1] '00' is the default FPGA addressing mode. Other modes are designed to allow setting
        the FPGA networking address without the help of the ARM processor and are not used. The
        addressing mode is changed by causing a rising edge on the GPIO registers TARGET_LOAD while
        TARGET_FPGA_SERIAL_NUMBER matches the serial number of the FPGA. This is a feature meant to
        allow ARM-less configuring of the FPGA through broadcasting, but we don't use it here since
        it's much easier and reliable to go through the ARM, which can get its networking parameters
        automatically through DHCP.


        """

        ip_packed = socket.inet_aton(fpga_ip_addr)  #

        # Compute a MAC address for the FPGA
        # mac = socket.inet_aton(self._get_arm_mac())  #
        if fpga_mac_addr is None:
            mac_packed = struct.pack('>H4s', 0x1234, ip_packed)
            fpga_mac_addr = ':'.join(['%02X' % c for c in mac_packed])
        else:
            mac_packed = bytes([int(s, 16) for s in fpga_mac_addr.split(':')])

        # self.fpga_mac_addr = fpga_mac_addr
        # self.fpga_control_port_number = fpga_port_number
        # self.fpga_ip_addr = fpga_ip_addr

        # Set the FPGA Networking parameters over the ARM-FPGA SPI interface
        await self.fpga_spi_mmi_write_async(self._FPGA_MAC_ADDR_LSW_ADDR, struct.unpack('>I', mac_packed[2:6])[0])
        await self.fpga_spi_mmi_write_async(
            self._FPGA_MAC_ADDR_MSW_IP_PORT_ADDR,
            (struct.unpack('>H', mac_packed[0:2])[0] << 16) | fpga_port_number)
        await self.fpga_spi_mmi_write_async(self._FPGA_IP_ADDR_ADDR, struct.unpack('>I', ip_packed)[0])

        return fpga_mac_addr

    async def set_local_data_port_number_async(self, port):
        """
        Sets the port number to which the FPGA is sending the data for UDP channel 1. Use
        `set_data_target_address` instead.

        Parameters:

            port (int); target port number. If port==0, the data is sent to
                the source port number of the last received valid packet  + 1.

        Does not change the target MAC or IP address.
        """
        word = await self.fpga_spi_mmi_read_async(self._REMOTE_IP_PORT_ADDR)
        await self.fpga_spi_mmi_write_async(self._REMOTE_IP_PORT_ADDR, (word & 0xFFFF) | (port << 16))

    async def get_local_data_port_number_async(self):
        """ Return the port number to which the FPGA is sending its captured data stream on the control network.
        """
        return((await self.fpga_spi_mmi_read_async(self._REMOTE_IP_PORT_ADDR)) >> 16)

    async def set_data_target_address_async(self, ip_addr=None, port=None, mac_addr=None):
        """
        Sets the IP address, port number and MAC address to which data is sent back to the host comptuter.

        This method sets the target address for data sent back to the host computer through the UDP
        channel 1.

        UDP Channel 1 (a.k.a the data channel) is generally used to send data back to the host
        computer through the control Ethernet interface but on a different port. This channel is
        usually used to send low-bandwidth data, and is not to be confussed with dedicated data
        channels such as the 10G Ethernet links to GPU nodes.

        The GPIO fields `DATA_IP_PORT_OFFSET` and `CORR_IP_PORT_OFFSET` set on which UDP channels is
        sent the data generated by the raw data capture (PROBER) or correlator (CORR44) subsystems,
        respectively. Both are set to UDP Channel 1 by default.

        UDP Channe1 1 target address is set and behaves differnetly than UDP channel 0, and is
        networking parameters are set by the method parameters `ip_addr`, `port` and `eth_addr`.

        Parameters:

            ip_addr (str):  Destination IP Address to which the FPGA send the UDP Channel 1 packets. The address is
                in the format of 'a.b.c.d', where a,b,c and d are decimal numbers. If `ip_addr` is
                '0.0.0.0' or None, then data will be sent back to the source address of the last
                valid received control packet.

            port (int): Destination port to which the FPGA sends UDP Channel 1 packets. If `port` is
                0, the packets will be sent to the the source port of the last valid received
                control packet **plus one**.

            mac_addr (str): Destination MAC address to which the FPGA will sends UDP Channel 1
                packets. It is in the format 'xx:xx:xx:xx:xx:xx, where 'xx' is a hex number'. If
                fpga_mac_addr is None or '00:00:00:00:00:00', the packets will be sent to the the
                source MAC address of the last valid received control packet.

        After initializarion, all three parameters are set to zero, meaning that if the FPGA
        receives control packets from port x, data will be sent back to the same host on port x+1.
        This implies that the host was able to allocate two consecutive UDP port addresses for
        control and data sockets. It is usually easier to let the operating system assign a random
        port and set that pot number explicitely with a non-zero value.


        The Channel 1 addressing described above is valid for addressing mode '00' (the only mode
        available to this module, see [#f1]) In this mode, the IP address and MAC address are set by
        the GPIO registers TARGET_MAC_ADDR and TARGET_IP_ADDR. The port number is set by the lower
        16 bits of the SPI register _REMOTE_IP_PORT_ADDR  (GPIO's TARGET_IP_PORT is *not* used). The
        Channel 1 destination addresses are set differently in other addressing modes.

        """
        if not ip_addr:
            ip_addr_int = 0
        else:
            ip_addr_int = struct.unpack('>L', socket.inet_aton(ip_addr))[0]

        if not mac_addr:
            mac_addr_int = 0
        else:
            mac_addr_int = sum(int(s, 16) << (8 * i) for i, s in enumerate(reversed(mac_addr.split(':'))))

        self.logger.debug(
            f'{self!r}: setting data target address to '
            f'ip={ip_addr}({ip_addr_int}), port={port}({port}), '
            f'mac={mac_addr}({mac_addr_int})')
        # Set the UDP transmit channel 1 IP and MAC addresses
        self.core_gpio.TARGET_MAC_ADDR = mac_addr_int
        self.core_gpio.TARGET_IP_ADDR = ip_addr_int

        # Set the UDP  Channel 1 outgoing packet destination port number, on the ARM-FPGA SPI registers
        word = await self.fpga_spi_mmi_read_async(self._REMOTE_IP_PORT_ADDR)
        await self.fpga_spi_mmi_write_async(self._REMOTE_IP_PORT_ADDR, (word & 0xFFFF) | (port << 16))

    async def get_fpga_firmware_cookie(self, resync=False):
        """
        Get the FPGA firmware cookie.

        Reads the FPGA over the UDP link and returns the cookie that
        identifies the firmware. This method can be called before any FPGA
        modules are instatiated.

        If ``resync`` is True, the read command will reset the command
        sequence number to the value known by the FPGA. This should be is used
        by the first command sent to the FPGA to reset the communication link.
        """
        await asyncio.sleep(0)
        return((self.mmi_read(self._GPIO_COOKIE_REG, resync=resync) & 0x7F))

    def get_fpga_firmware_version(self):
        """
        Returns the firmware revion currenting running on the FPGA (which si
        the date and time of bitstream generation)
        """
        return self.core_gpio.get_bitstream_date()




class IceBoardHardware(object):
    """
    Provides access to the hardware of an IceBoard Rev2/Rev3, including:
        - LED control
        - GPIO input/output
        - Temperature sensors
        - Power monitoring for every rail (voltage,current)
        - Motherboard EEPROM

    This class implements these methods by issuring I2C commands
    through the I2C interface provided either by the FPGA or by the
    ARM.

    Part or all of of functionnalities described in this class might
    eventually be implemented in the ARM processor itself. In thise
    case, these those will be available through the ARM's Tuber
    interface.
    """

    # ------------------------------------
    # Define hardware-specific constants
    # ------------------------------------
    NUMBER_OF_FMC_SLOTS = 2  # Indicates the number of FMC slots supported by this platform

    # I2C switch addresses (visible on all buses on a specific port)
    _FPGA_I2C_SWITCH_ADDR = 0b1110100  # 0x74
    _ARM0_I2C_SWITCH_ADDR = 0b1110000  # 0x70
    _ARM1_I2C_SWITCH_ADDR = 0b1110001  # 0x71
    _ARM2_I2C_SWITCH_ADDR = 0b1110010  # 0x72
    _ARM3_I2C_SWITCH_ADDR = 0b1110011  # 0x73

    FPGA_I2C_BUS_LIST = {
        # Bus name, (FPGA I2C port, I2C switch enable bit)
        "FMC":   (0, 0),  # equivalent to FMCA. Included for backwards compatibility with single-FMC code
        "FMCA":  (0, 0),
        "FMCB":  (0, 1),
        "QSFPA": (0, 2),
        "QSFPB": (0, 3),
        "SFP":   (0, 4),
        "SMPS":  (0, 5),
        "BP":    (0, 6),
        "GPIO":  (0, 7)
        }

    # FMC EEPROM, on FMCA or FMCB
    _FMC_EEPROM_ADDR = 0x50  # 0x50 (0x51 is also used for the 2nd page of large eeprom with address width > 16 bits).
    _FMC_EEPROM_ADDR_WIDTH = 7  # FMC EEPROM internal addresses are 7 bits wide.
    _FMC_EEPROM_PAGE_SIZE = 8  #

    # Oversize , non-FMC-standard EEPROM found on some McGill Mezzanines

    # FMC EEPROM internal addresses are is 17 bits wide. (2 bytes as data, 1 bit in lsb of I2C address)
    _MCGILL_FMC_EEPROM_ADDR_WIDTH = 17
    _MCGILL_FMC_EEPROM_PAGE_SIZE = 256  #

    # Motherboard EEPROM
    _MOTHERBOARD_EEPROM_DATA_ADDR = 0x57  #
    _MOTHERBOARD_EEPROM_SERIAL_ADDR = 0x5F  #
    # EEPROM internal addresses are is 17 bits wide. (2 bytes as data, 1 bit in lsb of I2C address)
    _MOTHERBOARD_EEPROM_ADDR_WIDTH = 7
    _MOTHERBOARD_EEPROM_PAGE_SIZE = 8  #

    # IO Expanders, on GPIO bus
    _GPIO_POWER_I2C_ADDR = 0b0100000  # 0x20
    _GPIO_SFP_QSFP_I2C_ADDR = 0b0100001  # 0x21
    _GPIO_SW_LEDS_ADDR = 0b0100010  # 0x22
    _GPIO_ARM_PHY_LEDS_ADDR = 0b0100011  # 0x23

    # # Temperature sensors, on GPIO bus
    # _TMP_ARM_I2C_ADDR   = 0b1001010 #0x4A
    # _TMP_PHY_I2C_ADDR   = 0b1001100 #0x4C
    # _TMP_FPGA_I2C_ADDR  = 0b1001011 #0x4B
    # _TMP_POWER_I2C_ADDR = 0b1001000 #0x48

    # # Power monitors, on SMPS bus
    # _POWER_ICEVADJ_I2C_ADDR   = 0b1000011 #0x43
    _POWER_ICE12V0_I2C_ADDR = 0b1000111  # 0x47
    # _POWER_ICE5V0_I2C_ADDR    = 0b1001000 #0x48
    # _POWER_ICE3V3_I2C_ADDR    = 0b1001001 #0x49
    # _POWER_ICE1V5_I2C_ADDR    = 0b1001100 #0x4C
    # _POWER_ICE1V2_I2C_ADDR    = 0b1001101 #0x4D
    _POWER_ICE1V0_I2C_ADDR = 0b1001110  # 0x4E
    # _POWER_ICE1V8_I2C_ADDR    = 0b1001011 #0x4B
    # _POWER_ICE1V0GTX_I2C_ADDR = 0b1001111 #0x4F

    # _POWER_FMCA12V0_I2C_ADDR  = 0b1000000 #0x40
    # _POWER_FMCA3V3_I2C_ADDR   = 0b1000001 #0x41
    # _POWER_FMCAVADJ_I2C_ADDR  = 0b1000010 #0x42

    # _POWER_FMCB12V0_I2C_ADDR  = 0b1000100 #0x44
    # _POWER_FMCB3V3_I2C_ADDR   = 0b1000101 #0x45
    # _POWER_FMCBVADJ_I2C_ADDR  = 0b1000110 #0x46

    def __init__(self, iceboard):
        """
        Creates all the I2C objects needed to interface the hardware. In order
        to do this, the following methods will be required from the iceboard
        object:

            - i2c_set_port(...) # Port number 0 (connected to the FPGA I2C switch) is used for all accesses
            - i2c_write_read(...) # FPGA I2C engine

        Those methods can be provided either by the ARM or the core FPGA firmware.

        For FPGA-based I2C:
            - fpga_core is not Null
            - fpga_core provides the following methods
        """

        self._logger = logging.getLogger(__name__)
        self._logger.debug('%r: Initializing Iceboard hardware' % iceboard)
        self._iceboard = iceboard
        self._i2c = self._iceboard.i2c
        self._logger.debug('%r: Instantiating Motherboard EEPROM managers' % self._iceboard)
        self._motherboard_eeprom_data = eeprom.eeprom(
            self._i2c, self._MOTHERBOARD_EEPROM_DATA_ADDR, 'GPIO',
            self._MOTHERBOARD_EEPROM_ADDR_WIDTH,
            self._MOTHERBOARD_EEPROM_PAGE_SIZE)
        self._motherboard_eeprom_serial = eeprom.eeprom(
            self._i2c, self._MOTHERBOARD_EEPROM_SERIAL_ADDR, 'GPIO',
            self._MOTHERBOARD_EEPROM_ADDR_WIDTH,
            self._MOTHERBOARD_EEPROM_PAGE_SIZE)

        self._logger.debug('%r:  Instantiating FMC EEPROM managers' % self._iceboard)

        # We check if the EEPROM has multiple pages, and if so, we *assume* that
        # the EEPROM is a large (non-FMC compliant) EEPROM with 2-byte addresses.
        # Otherwise we assume the EEPROM has a single byte of addressing.
        #
        # If the EEPROM is multipage but has a single address byte (4Kbit,
        # 8kbit or 16kbit EEPROMs), then the EEPROM contents will be
        # corrupted, even by read operations, because the second address byte
        # will be interpreted as data to be written. It would be equally bad
        # if there has another I2C device at the address following the EEPROM
        # address.
        if self._i2c.is_present(self._FMC_EEPROM_ADDR+1, bus_name='FMCA'):
            self._logger.debug('%r: Detected multipage EEPROM on FMCA. Assuming >16-bit addressing.' % self._iceboard)
            self._fmca_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCA',
                self._MCGILL_FMC_EEPROM_ADDR_WIDTH,
                self._MCGILL_FMC_EEPROM_PAGE_SIZE)
        else:
            self._fmca_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCA',
                self._FMC_EEPROM_ADDR_WIDTH,
                self._FMC_EEPROM_PAGE_SIZE)

        if self._i2c.is_present(self._FMC_EEPROM_ADDR+1, bus_name='FMCB'):
            self._logger.debug('%r: Detected multipage EEPROM on FMCB. Assuming >16-bit addressing.' % self._iceboard)
            self._fmcb_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCB',
                self._MCGILL_FMC_EEPROM_ADDR_WIDTH, self._MCGILL_FMC_EEPROM_PAGE_SIZE)
        else:
            self._fmcb_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCB',
                self._FMC_EEPROM_ADDR_WIDTH, self._FMC_EEPROM_PAGE_SIZE)

        self._FMC_EEPROM_TABLE = {
            1: self._fmca_eeprom,
            2: self._fmcb_eeprom
            }

        self._logger.debug('%r: Instantiating I2C GPIO manager' % self._iceboard)
        self._gpio_power = pca9575.pca9575(self._i2c, self._GPIO_POWER_I2C_ADDR, 'GPIO')
        self._gpio_sw_leds = pca9575.pca9575(self._i2c, self._GPIO_SW_LEDS_ADDR, 'GPIO')
        self._gpio_arm_phy_leds = pca9575.pca9575(self._i2c, self._GPIO_ARM_PHY_LEDS_ADDR, 'GPIO')
        self._gpio_sfp_qsfp = pca9575.pca9575(self._i2c, self._GPIO_SFP_QSFP_I2C_ADDR, 'GPIO')

        self._gpio = gpio.GPIO(gpio_table={
            # name : (expander object, byte, lsb bit number,  width)
            'GP_SW1': (self._gpio_sw_leds, 0, 0, 1),
            'GP_SW2': (self._gpio_sw_leds, 0, 1, 1),
            'GP_SW3': (self._gpio_sw_leds, 0, 2, 1),
            'GP_SW4': (self._gpio_sw_leds, 0, 3, 1),
            'GP_SW5': (self._gpio_sw_leds, 0, 4, 1),
            'GP_SW6': (self._gpio_sw_leds, 0, 5, 1),
            'GP_SW7': (self._gpio_sw_leds, 0, 6, 1),
            'GP_SW8': (self._gpio_sw_leds, 0, 7, 1),
            'GP_LED1': (self._gpio_sw_leds, 1, 7, 1),
            'GP_LED2': (self._gpio_sw_leds, 1, 6, 1),
            'GP_LED3': (self._gpio_sw_leds, 1, 5, 1),
            'GP_LED4': (self._gpio_sw_leds, 1, 4, 1),
            'GP_LED5': (self._gpio_sw_leds, 1, 3, 1),
            'GP_LED6': (self._gpio_sw_leds, 1, 2, 1),
            'GP_LED7': (self._gpio_sw_leds, 1, 1, 1),
            'GP_LED8': (self._gpio_sw_leds, 1, 0, 1),
            'GP_LED9': (self._gpio_arm_phy_leds, 0, 0, 1),
            'GP_LED10': (self._gpio_arm_phy_leds, 0, 1, 1),
            'GP_LED11': (self._gpio_arm_phy_leds, 0, 2, 1),
            'GP_LED12': (self._gpio_arm_phy_leds, 0, 3, 1),
            'GTX1V8PowerFault': (self._gpio_arm_phy_leds, 0, 4, 1),
            'PHYAPowerFault': (self._gpio_arm_phy_leds, 0, 5, 1),
            'PHYBPowerFault': (self._gpio_arm_phy_leds, 0, 6, 1),
            'ArmPowerFault': (self._gpio_arm_phy_leds, 0, 7, 1),
            'BP_GPIO0': (self._gpio_arm_phy_leds, 1, 0, 1),
            'BP_GPIO1': (self._gpio_arm_phy_leds, 1, 1, 1),
            'BP_GPIO2': (self._gpio_arm_phy_leds, 1, 2, 1),
            'BP_GPIO3': (self._gpio_arm_phy_leds, 1, 3, 1),
            'BP_GPIO4': (self._gpio_arm_phy_leds, 1, 4, 1),
            'BP_GPIO5': (self._gpio_arm_phy_leds, 1, 5, 1),
            'BP_SLOT_NUMBER': (self._gpio_arm_phy_leds, 1, 0, 4),  # Also corresponds to BP_GPIO0-3
            'QSFPA_ModPrsL': (self._gpio_sfp_qsfp, 0, 0, 1),
            'QSFPA_ResetL': (self._gpio_sfp_qsfp, 0, 2, 1),
            'QSFPA_IntL': (self._gpio_sfp_qsfp, 0, 1, 1),
            'QSFPA_LPMode': (self._gpio_sfp_qsfp, 0, 4, 1),
            'QSFPA_ModSelL': (self._gpio_sfp_qsfp, 0, 3, 1),
            'QSFPB_ModPrsL': (self._gpio_sfp_qsfp, 0, 5, 1),
            'QSFPB_ResetL': (self._gpio_sfp_qsfp, 0, 7, 1),
            'QSFPB_IntL': (self._gpio_sfp_qsfp, 0, 6, 1),
            'QSFPB_LPMode': (self._gpio_sfp_qsfp, 1, 5, 1),
            'QSFPB_ModSelL': (self._gpio_sfp_qsfp, 1, 4, 1),
            'SFP_LOS': (self._gpio_power, 0, 7, 1),
            'SFP_TxFault': (self._gpio_sfp_qsfp, 1, 0, 1),
            'SFP_TxDisable': (self._gpio_sfp_qsfp, 1, 1, 1),
            'SFP_RS0': (self._gpio_sfp_qsfp, 1, 2, 1),
            'SFP_RS1': (self._gpio_sfp_qsfp, 1, 3, 1),
            'SFP_ModSelL': (self._gpio_power, 1, 7, 1),
            'FMCA_PG_M2C': (self._gpio_power, 0, 3, 1),
            'FMCB_PG_M2C': (self._gpio_power, 1, 3, 1)
        })

        self._qsfpa = qsfp.QSFP(self._i2c, bus_name='QSFPA', gpio_prefix='QSFPA_', gpio=self._gpio, parent=self)
        self._qsfpb = qsfp.QSFP(self._i2c, bus_name='QSFPB', gpio_prefix='QSFPB_', gpio=self._gpio, parent=self)

        self.qsfp = Ccoll((self._qsfpa, self._qsfpb))
        # self._logger.info(' Instantiating I2C temperature sensors')
        # self._tmp_power = tmp100.tmp100(self._i2c, self._TMP_POWER_I2C_ADDR, 'GPIO')
        # self._tmp_phy = tmp100.tmp100(self._i2c, self._TMP_PHY_I2C_ADDR, 'GPIO')
        # self._tmp_fpga = tmp100.tmp100(self._i2c, self._TMP_FPGA_I2C_ADDR, 'GPIO')
        # self._tmp_arm = tmp100.tmp100(self._i2c, self._TMP_ARM_I2C_ADDR, 'GPIO')

        # self._logger.info(' Instantiating I2C current/power monitors')
        # self._power_ice_3v3 = ina230.ina230(self._i2c, self._POWER_ICE3V3_I2C_ADDR, 'SMPS')
        self._power_ice_12v0 = ina230.ina230(self._i2c, self._POWER_ICE12V0_I2C_ADDR, 'SMPS')
        # self._power_ice_5v0 = ina230.ina230(self._i2c, self._POWER_ICE5V0_I2C_ADDR, 'SMPS')
        # self._power_ice_1v0_gtx = ina230.ina230(self._i2c, self._POWER_ICE1V0GTX_I2C_ADDR, 'SMPS')
        # self._power_ice_vadj = ina230.ina230(self._i2c, self._POWER_ICEVADJ_I2C_ADDR, 'SMPS')
        # self._power_ice_1v2 = ina230.ina230(self._i2c, self._POWER_ICE1V2_I2C_ADDR, 'SMPS')
        # self._power_ice_1v5 = ina230.ina230(self._i2c, self._POWER_ICE1V5_I2C_ADDR, 'SMPS')
        self._power_ice_1v0 = ina230.ina230(self._i2c, self._POWER_ICE1V0_I2C_ADDR, 'SMPS')
        # self._power_ice_1v8 = ina230.ina230(self._i2c, self._POWER_ICE1V8_I2C_ADDR, 'SMPS')

        # self._power_fmca_12v0 = ina230.ina230(self._i2c, self._POWER_FMCA12V0_I2C_ADDR, 'SMPS')
        # self._power_fmca_3v3 = ina230.ina230(self._i2c, self._POWER_FMCA3V3_I2C_ADDR, 'SMPS')
        # self._power_fmca_vadj = ina230.ina230(self._i2c, self._POWER_FMCAVADJ_I2C_ADDR, 'SMPS')

        # self._power_fmcb_12v0 = ina230.ina230(self._i2c, self._POWER_FMCB12V0_I2C_ADDR, 'SMPS')
        # self._power_fmcb_3v3 = ina230.ina230(self._i2c, self._POWER_FMCB3V3_I2C_ADDR, 'SMPS')
        # self._power_fmcb_vadj = ina230.ina230(self._i2c, self._POWER_FMCBVADJ_I2C_ADDR, 'SMPS')

        # self.TEMPERATURE_SENSOR_TABLE = {
        #     # sensor name: tmp object
        #     'TEMP_POWER': self._tmp_power,
        #     'TEMP_PHY': self._tmp_phy,
        #     'TEMP_FPGA': self._tmp_fpga,
        #     'TEMP_ARM': self._tmp_arm
        # }

        # self.POWER_SENSOR_TABLE = {
        #     # sensor name : (ina230 object, output voltage(volts), rshunt(inductor) (mohm), typical current(amps), current tolerance (0<tol<1))
        #     'ICE_3V3': (self._power_ice_3v3, 3., 2.36, 8., 0.5),         #SER1360-182L
        #     'ICE_12V0': (self._power_ice_12v0, 12., 5.5, 3., 0.5),       #SER1360-602L
        #     'ICE_5V0': (self._power_ice_5v0, 5., 2.36, 11., 0.5),        #SER1360-182L
        #     'ICE_1V0_GTX': (self._power_ice_1v0_gtx, 1., 0.77, 16., 0.5),#SER1360-331L
        #     'ICE_1V2': (self._power_ice_1v2, 1.2, 0.77, 8., 0.5),        #SER1360-651L
        #     'ICE_1V5': (self._power_ice_1v5, 1.5, 2.36, 3., 0.5),        #SER1360-182L
        #     'ICE_1V0': (self._power_ice_1v0, 1., 0.77, 16., 0.5),        #SER1360-331L
        #     'ICE_1V8': (self._power_ice_1v8, 1.8, 5.5, 1., 0.5),         #SER1360-602L
        #     'ICE_VADJ': (self._power_ice_vadj, 2.5, 2.36, 8., 0.5),
        #     'FMCA_12V0': (self._power_fmca_12v0, 12., 5, 2., 0.5),
        #     'FMCB_12V0': (self._power_fmcb_12v0, 12., 5, 2., 0.5),
        #     'FMCA_3V3': (self._power_fmca_3v3, 3., 5, 5., 0.5),
        #     'FMCB_3V3': (self._power_fmcb_3v3, 3., 5, 5., 0.5),
        #     'FMCA_VADJ': (self._power_fmca_vadj, 2.5, 5, 1., 0.5),
        #     'FMCB_VADJ': (self._power_fmcb_vadj, 2.5, 5, 1., 0.5)
        # }

    def __repr__(self):
        return "%r.%s" % (self._iceboard, self.__class__.__name__)

    async def open(self):
        """
        """
        pass

    def close(self):
        self._logger.debug('Closing Iceboard hardware')
        if self._i2c:
            self._i2c = None

    async def init(self):
        """Initializes the motherboard hardware to a known state.
        This will turn off FMC power.
        """
        await asyncio.sleep(0)
        self._init_gpio_expanders()
        # self._init_temperature_sensors()
        # self.set_fmc_power()
        # self._init_power_sensors()

        # Initialize the QSFPs. This sets the reset and LowPower mode. Some
        # QSFP+ modules (like the 3M AOCs) will not work without this.
        await asyncio.sleep(0)
        self._qsfpa.init()
        await asyncio.sleep(0)
        self._qsfpb.init()

    def _init_gpio_expanders(self):
        """
        Initializes GPIO expanders

        History

        140304 JM: created. todo: make more flexible for I/O pin configuration
        of each expander. Need to confirm I/O pin config with JF
        """
        self._gpio_power.init(cfg0_def=0b10101000,  # 1 = input, 0=output
                              cfg1_def=0b10101000,
                              out0_default=None,
                              out1_default=None,
                              bken0=0b00,  # We need to disable 100K internal
                              #       pull-ups/down so the PG_M2C can work
                              #       properly (there is another external 100K
                              #       pull up to VCC3V3 which pulls to GND
                              #       when there is no power. Pulling up
                              #       doesn't work when board is off , pull
                              #       down doesn't work when board is ON)
                              bken1=0b00,
                              pupd0=0b00001000,  # don't care, pullups not enabled
                              pupd1=0b00001000
                              )
        self._gpio_sw_leds.init(cfg1_def=0b00000000)
        self._gpio_arm_phy_leds.init(cfg0_def=0b11110000)
        self._gpio_sfp_qsfp.init(cfg0_def=0b01100011, cfg1_def=0b11001111)

    def get_i2c_interface(self):
        """
        Returns an I2C interface object that provides a standardized bus selection.
        """
        return self._i2c

    def get_number_of_fmc_slots(self):
        return self.NUMBER_OF_FMC_SLOTS

    # def get_slot_number(self):
    #     return self._gpio.read('BP_SLOT_NUMBER') + 1

    def read_motherboard_eeprom(self, addr, length, **kwargs):
        return self._motherboard_eeprom_data.read(addr, length, **kwargs)

    def write_motherboard_eeprom(self, addr, data, **kwargs):
        return self._motherboard_eeprom_data.write(addr, data, **kwargs)

    def read_mezzanine_eeprom(self, mezzanine, addr, length, **kwargs):
        eeprom_object = self._FMC_EEPROM_TABLE[mezzanine]
        return eeprom_object.read(addr, length, **kwargs)

    def write_mezzanine_eeprom(self, mezzanine, addr, data, **kwargs):
        eeprom_object = self._FMC_EEPROM_TABLE[mezzanine]
        return eeprom_object.write(addr, data, **kwargs)

    async def set_mezzanine_power_async(self, fmc_number=list(range(NUMBER_OF_FMC_SLOTS)), state=[True]*NUMBER_OF_FMC_SLOTS):
        """
        Enables or disables power of the specified FMC slot.

        Proper power sequencing is done to prevent the FMC board switchers to
        create too much a current spike when enabled.

        History:
            140223 JFC: Modified to use register names.

            140304 JM: Modified it so a state for every fmc can be specified.
                For now, state is either a boolean or a list of booleans with
                the same length as 'fmc_number' Todo: 140223 JFC: used masked
                writes to avoid side effects.
        """
        if isinstance(fmc_number, int):
            fmc_number = [fmc_number]

        if isinstance(state, (bool, int)):
            state = [state] * len(fmc_number)

        for (fmc, fmc_state) in zip(fmc_number, state):
            if fmc not in list(range(self.NUMBER_OF_FMC_SLOTS)):
                raise ValueError('FMC number %i is not a valid value' % fmc)
            else:
                # out_reg = 'OUT%i' % fmc # sets the register name to access based on the FMC number
                # cfg_reg = 'CFG%i' % fmc
                # Turn off all power signals before we enable the GPIO outputs
                # self._gpio_power.write(out_reg, 0b00000000)
                # self._gpio_power.write(cfg_reg, 0b10101000)

                # Bits are:
                #  7: SFP_LOS/SFM_ModPrsn
                #  6: FMC_CLK_DIR
                #  5: FMC_PRSNT
                #  4: FMC_PG_C2M
                #  3: FMC_PG_M2C
                #  2: FMC_EN_VADJ
                #  1: FMC_EN_3V3
                #  0: FMC_EN_12V
                if fmc_state:
                    # Turn on 12V, 3.3V and VADJ power to board
                    self._gpio_power.write(fmc, 0b00000010, mask=0b00000010)
                    # self._gpio_power.write(fmc, 0b00000110, mask=0b00000110)
                    await asyncio.sleep(0.010)
                    # Turn on 12V, 3.3V and VADJ power to board
                    self._gpio_power.write(fmc, 0b00000100, mask=0b00000100)
                    await asyncio.sleep(0.100)
                    # Turn on 12V, 3.3V and VADJ power to board
                    self._gpio_power.write(fmc, 0b00000001, mask=0b00000001)
                    await asyncio.sleep(0.050)
                    # Set Power Good (start switcher) and CLKDIR to 1
                    self._gpio_power.write(fmc, 0b01010000, mask=0b01010000)
                    await asyncio.sleep(0.050)
                else:
                    # Stop mezzanine switcher (PG=0)
                    self._gpio_power.write(fmc, 0b00000000, mask=0b01010000)
                    await asyncio.sleep(0.030)
                    # Turn off 12V
                    self._gpio_power.write(fmc, 0b00000000, mask=0b00000001)
                    await asyncio.sleep(0.030)
                    # Turn off rail
                    self._gpio_power.write(fmc, 0b00000000, mask=0b00000010)
                    await asyncio.sleep(0.030)
                    # Turn off rail
                    self._gpio_power.write(fmc, 0b00000000, mask=0b00000100)
                    await asyncio.sleep(0.100)

    async def set_led(self, led_name, state):
        """
        Set the LED(s) specified in 'led_name' to the the 'state'.
        'led_name' can be a list of LED names found in
        gpio object.  'state' can be a single boolean value, or
        an array with the same length as 'led_name'
        """
        if isinstance(led_name, str):
            led_name = [led_name]

        if isinstance(state, (bool, int)):
            state = [state] * len(led_name)

        await asyncio.sleep(0)
        for (led, led_state) in zip(led_name, state):
            self._gpio.write(led, led_state)

    async def get_led(self, led_name):
        """
        Returns the status of specified LED(s) in a dictionary
        led_status where each key is a led_name and the respective value
        is the led status.
        """
        led_status = {}
        if isinstance(led_name, str):
            led_name = [led_name]

        for led in led_name:
            led_status[led] = self._gpio.read(led)

        return(led_status)

    # def _init_temperature_sensors(self, temperature_sensor_name=None, bit_resolution=12):
    #     """ Initialize temperature sensors.

    #     'temperature_sensor_name' can be a list of temperature sensor names
    #     found in TEMPERATURE_SENSOR_TABLE. If temperature_sensor_name=None,
    #     all sensors in the list are initialized.

    #     'bit_resolution' is the number of bits of resolution of the
    #     temperature register. It can take values 9, 10, 11, 12

    #     History:
    #     140318 JM: created
    #     """
    #     if bit_resolution<9 or bit_resolution>12:
    #         raise self.ValueError('Bit_resolution is out of range. Must be 9,10,11 or 12 bits')
    #     else:
    #         if temperature_sensor_name == None:
    #             temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
    #         elif isinstance(temperature_sensor_name, str):
    #             temperature_sensor_name = [temperature_sensor_name]

    #         for temp_sensor in temperature_sensor_name:
    #             if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
    #                 raise ValueError(
    #                      'Invalid temperature sensor name. Valid names are %s'
    #                       % ','.join(self.TEMPERATURE_SENSOR_TABLE.keys()))
    #             else:
    #                 tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
    #                 try:
    #                     tmp_object.init(bit_resolution)
    #                 except:
    #                     self._logger.info(
    #                         '%r: Temperature sensor %s failed to initialize.'
    #                          % (self._iceboard, temp_sensor))

    # def _init_power_sensors(self, power_sensor_name=None):
    #     """
    #     initializes current/power monitors
    #
    #     'power_sensor_name' can be a list of current/power monitor names
    #     found in POWER_SENSOR_TABLE. If power_sensor_name=None, all sensors
    #     in POWER_SENSOR_TABLE are initialized.

    #     History:
    #     140320 JM: created
    #     """
    #     if power_sensor_name == None:
    #         power_sensor_name = self.POWER_SENSOR_TABLE.keys()
    #     elif isinstance(power_sensor_name, str):
    #         power_sensor_name = [power_sensor_name]

    #     for power_sensor in power_sensor_name:
    #         if power_sensor not in self.POWER_SENSOR_TABLE:
    #            raise ValueError(
    #                'Invalid power sensor name. Valid names are %s'
    #                % ','.join(self.POWER_SENSOR_TABLE.keys()))
    #         else:
    #             power_sensor_object, v_out, r_shunt, i_typ, tol_i = self.POWER_SENSOR_TABLE[power_sensor]
    #             try:
    #                 power_sensor_object.init(v_out=v_out, r_shunt=r_shunt, i_typ=i_typ, tol_i=tol_i)
    #             except:
    #                 self._logger.info('%r: Power sensor %s failed to initialize.' % (self._iceboard, power_sensor))

    # def get_temperature(self, temperature_sensor_name=None):
    #     """
    #     Returns the current temperature measured on the specified
    #     sensor(s).  NOTE: some temperatures are taken from the FPGA
    #     inetrnal SYSTEM monitor.

    #     initializes temperature expanders
    #     'temperature_sensor_name' can be a list of temperature sensor
    #     names found in TEMPERATURE_SENSOR_TABLE

    #     Returns a dictionary with keys corresponding to the temperature_sensor_name names.

    #     History:
    #     140318 JM: created
    #     """
    #     temperature_dict = {}
    #     if temperature_sensor_name == None:
    #         temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
    #     elif isinstance(temperature_sensor_name, str):
    #         temperature_sensor_name = [temperature_sensor_name]

    #     for temp_sensor in temperature_sensor_name:
    #         if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
    #             raise ValueError('Invalid temperature sensor name')
    #         else:
    #             tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
    #             temperature_dict[temp_sensor] = tmp_object.get_temperature()

    #     return temperature_dict

    # def get_power(self, power_sensor_name=None):
    #     """
    #     Returns the voltage, current and power of the power monitoring system.
    #     Includes power measured internally from  the FPGA's system monitor.
    #     Multiple targets can be specified.

    #     Arguments:

    #        'power_sensor_name' can be a list of temperature sensor
    #         names found in POWER_SENSOR_TABLE. If
    #         power_sensor_name=None, measurements of all sensors in
    #         TEMPERATURE_SENSOR_TABLE are returned.

    #     Returns dictionary with keys corresponding to the
    #     power_sensor_name names. The respective value is a (bus
    #     voltage (V), shunt voltage (V), current (A), power (W)) tuple.

    #     History:
    #     140320 JM: created
    #     """
    #     power_dict = {}
    #     if power_sensor_name == None:
    #         power_sensor_name = self.POWER_SENSOR_TABLE.keys()
    #     elif isinstance(power_sensor_name, str):
    #         power_sensor_name = [power_sensor_name]

    #     for power_sensor in power_sensor_name:
    #         if power_sensor not in self.POWER_SENSOR_TABLE:
    #             raise ValueError(
    #                    'Invalid power sensor name. Valid names are %s.'
    #                    % ','.join(self.POWER_SENSOR_TABLE.keys()))
    #         else:
    #             power_sensor_object = self.POWER_SENSOR_TABLE[power_sensor][0]

    #             try:
    #                 bus_voltage = power_sensor_object.get_bus_voltage()
    #                 shunt_voltage = power_sensor_object.get_shunt_voltage()
    #                 current = power_sensor_object.get_current()
    #                 power =  power_sensor_object.get_power()
    #             except:
    #                 bus_voltage = None
    #                 shunt_voltage = None
    #                 current = None
    #                 power = None
    #             power_dict[power_sensor]=(bus_voltage, shunt_voltage, current, power)

    #     return power_dict

    # def get_serial_number(self):
    #     """
    #     Returns the board's serial number. which is actually the FPGA's
    #     serial number.
    #     """
    #     return self._iceboard.get_serial_number(); # tentative code

    # def get_info(self):
    #     """Loads the info data on the motherboard"""
    #     pass

    # def status(self):
    #     """Displays the status of the motherboard"""


# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
