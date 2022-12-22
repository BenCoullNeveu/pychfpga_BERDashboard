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

from pychfpga.hardware import Motherboard
from pychfpga.common import run_async, async_to_sync, Ccoll
from pychfpga.hardware.interfaces import TCPipe, TCPipe_I2C, TCPipe_SPI
from pychfpga.fpga_firmware import FPGAFirmware

# from ..i2c_devices.pca9575 import pca9575  as tca9575a # I2C 16-bit IO Expander
from ..i2c_devices.pca9546a import pca9546a  # I2C switch
from ..i2c_devices.tmp421 import tmp421  # Temperature sensor
from ..i2c_devices.ina230 import ina230 as ina231  # Temperature sensor
# from ..i2c_devices.sc18is602b import sc18is602b # I2C-to-SPI bridge
# from ..i2c_devices.tca6416a import tca6416a
# from ..i2c_devices.lmk04208spi import lmk04208spi # RF dual PLL
# from ..i2c_devices.lmx2594spi import lmx2594spi # ADC/DAC PLL
from ..i2c_devices.eeprom import eeprom
from ..i2c_devices.hmc7044 import hmc7044  # Dual PLL


class iic_dummy:
    def __init__(self, *args, **kwargs):
        pass

# ina226 = iic_dummy
# irps5401 = iic_dummy
# zynq_sysmon = iic_dummy
# si5341b = iic_dummy
# si570 = iic_dummy
# si5382 = iic_dummy


class CRS(Motherboard):
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
    part_number = 'CRS'
    _ipmi_part_numbers = ['CRS']

    NUMBER_OF_FMC_SLOTS = 0
    NUMBER_OF_CHANNELIZERS = 4

    port = 7  # port number on which to access the platform `hostname`

    # ---------------

    def __init__(self, hostname=None, serial=None, slot=None, subarray=None, **kwargs):
        super().__init__(
            hostname=hostname,
            serial=serial,
            slot=slot,
            subarray=subarray, **kwargs)

        self.iic = None
        self.spi = None
        self.mmi = None
        self.tcpipe = None
        self._is_open = None
        self.fpga = None  # firmware object

        self.firmware_crc = None  # temporary local storage of the CRC since we currently can't read it until the firmware is programmed.


    def open(self):
        run_async(self.open_async())


    async def open_platform_async(self, **kwargs):


        self.logger.debug(f'{self!r}: open() is called')


        # Open tcp communication with the board
        self.logger.debug(f'{self!r}: Opening TCP connection to the board')
        self.tcpipe = TCPipe(self.hostname, self.port)

        # create I2C interface
        self.iic = TCPipe_I2C(self.tcpipe)

        # create SPI interface
        self.spi = TCPipe_SPI(self.tcpipe)

        # I2C0, Switch 0x20
        # self.i2c0_switch = i2c0_switch = pca9544a(self.iic, address=0x75)
        # self.i2c_gpio = tca6416a(self.iic, address=0x20, port=dict(port=0, switch=i2c0_switch, switch_params=None))
        # self.i2c_ina226_0v85 = ina226(self.iic, address=0x41, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_1v8 = ina226(self.iic, address=0x42, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_vccintrf = ina226(self.iic, address=0x49, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_mgt1v2 = ina226(self.iic, address=0x47, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_vcc1v2 = ina226(self.iic, address=0x43, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_dacavtt = ina226(self.iic, address=0x4A, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_vadj = ina226(self.iic, address=0x45, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_mgt1v8 = ina226(self.iic, address=0x48, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_mgtavcc = ina226(self.iic, address=0x46, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_dac_vccaux = ina226(self.iic, address=0x71, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_adc_vccaux = ina226(self.iic, address=0x73, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_adc_vcc = ina226(self.iic, address=0x4c, port=dict(port=0, switch=i2c0_switch, switch_params=0))
        # self.i2c_ina226_dac_vcc = ina226(self.iic, address=0x4e, port=dict(port=0, switch=i2c0_switch, switch_params=0))

        # self.i2_irps5401a = irps5401(self.iic, address=0x43, port=dict(port=0, switch=i2c0_switch, switch_params=2))
        # self.i2_irps5401b = irps5401(self.iic, address=0x44, port=dict(port=0, switch=i2c0_switch, switch_params=2))
        # self.i2_fpga_sysmon = zynq_sysmon(self.iic, address="TBD", port=dict(port=0, switch=i2c0_switch, switch_params=3))


        # I2C1, Switch 0x74: EEPROM, clocks
        self.i2c1_switch = i2c1_switch = pca9546a(self.iic, address=0x70, port=1)
        # Switch port 0 devices
        self.i2c1_tmp421_5v0 = tmp421(self.iic, address=0x1C, port=(i2c1_switch, 0))
        self.i2c1_tmp421_3v3 = tmp421(self.iic, address=0x1D, port=(i2c1_switch, 0))
        self.i2c1_tmp421_2v5 = tmp421(self.iic, address=0x1E, port=(i2c1_switch, 0))
        self.i2c1_tmp421_1v8 = tmp421(self.iic, address=0x1F, port=(i2c1_switch, 0))

        self.i2c1_tmp421_1v2a = tmp421(self.iic, address=0x2A, port=(i2c1_switch, 0))

        self.i2c1_ina231_vbp = ina231(self.iic, address=0x40, port=(i2c1_switch, 0))
        self.i2c1_ina231_0v85a = ina231(self.iic, address=0x41, port=(i2c1_switch, 0))
        self.i2c1_ina231_0v85b = ina231(self.iic, address=0x42, port=(i2c1_switch, 0))
        self.i2c1_ina231_5v0 = ina231(self.iic, address=0x43, port=(i2c1_switch, 0))
        self.i2c1_ina231_3v3 = ina231(self.iic, address=0x44, port=(i2c1_switch, 0))
        self.i2c1_ina231_2v5 = ina231(self.iic, address=0x45, port=(i2c1_switch, 0))
        self.i2c1_ina231_1v8 = ina231(self.iic, address=0x46, port=(i2c1_switch, 0))
        self.i2c1_ina231_1v2a = ina231(self.iic, address=0x47, port=(i2c1_switch, 0))
        self.i2c1_ina231_1v4 = ina231(self.iic, address=0x4A, port=(i2c1_switch, 0))
        self.i2c1_ina231_1v2b = ina231(self.iic, address=0x4B, port=(i2c1_switch, 0))

        self.i2c1_tmp421_1v4 = tmp421(self.iic, address=0x4C, port=(i2c1_switch, 0))
        self.i2c1_tmp421_1v2b = tmp421(self.iic, address=0x4D, port=(i2c1_switch, 0))
        self.i2c1_tmp422_0v85 = tmp421(self.iic, address=0x4f, port=(i2c1_switch, 0))


        self.i2c1_eeprom_data = eeprom(self.iic, address=0x57, bus_name=(i2c1_switch, 0), address_width=7, max_read_length=255, max_write_length=8, write_page_size=8)
        self.i2c1_eeprom_serial = eeprom(self.iic, address=0x5F, bus_name=(i2c1_switch, 0), address_width=8, max_read_length=255)  # must read 16 bytes from memory address 0x80

        # Switch port 1 devices
        #   0x18: DDR4 SODIMM Temp sensor
        #   0x3x: DDR4 SODIMM Write protect settings
        #   0x50: DDR4 SODIMM EEPROM

        # Switch port 2 devices
        #   0x35: NVMe Basic management command (BMC)
        #   0x53: NVMe Virtual Product Data (VPD)

        # Switch port 3:
        #   External I2C header

        self.i2c1_switch = i2c1_switch = pca9546a(self.iic, address=0x71, port=1)
        # Switch port 0:
        #    QSFP26
        # Switch port 1-6
        #    SFP26

        # Switch port 7
        #   0x20: PCA9757 GPIO for SFP/QSFP
        #   0x21: PCA9757 GPIO for SFP/QSFP
        # self.i2c_fmc0 = eeprom(self.iic, address=0x50, bus_name=dict(port=1, switch=i2c1_switch1, switch_params=7), address_width=8, max_read_length=255)
        # self.i2c_fmc0a = eeprom(self.iic, address=0xAC//2, bus_name=dict(port=1, switch=i2c1_switch1, switch_params=7), address_width=8, max_read_length=255)


        # list of sensors
        self.i2c1_ina231_list = {
            'vbp': dict(device=self.i2c1_ina231_vbp, rshunt=0.01, imax=10),
            '0v85a': dict(device=self.i2c1_ina231_0v85a, rshunt=0.01, imax=40),
            '0v85b': dict(device=self.i2c1_ina231_0v85b, rshunt=0.01, imax=40),
            '5v0': dict(device=self.i2c1_ina231_5v0, rshunt=0.01, imax=16),
            '3v3': dict(device=self.i2c1_ina231_3v3, rshunt=0.01, imax=16),
            '2v5': dict(device=self.i2c1_ina231_2v5, rshunt=0.01, imax=16),
            '1v8': dict(device=self.i2c1_ina231_1v8, rshunt=0.01, imax=16),
            '1v2a': dict(device=self.i2c1_ina231_1v2a, rshunt=0.01, imax=16),
            '1v4': dict(device=self.i2c1_ina231_1v4, rshunt=0.01, imax=16),
            '1v2b': dict(device=self.i2c1_ina231_1v2b, rshunt=0.01, imax=16),
        }

        for name, info in self.i2c1_ina231_list.items():
            d = info['device']
            d.init(r_shunt=info['rshunt'], i_typ=info['imax'])
            time.sleep(0.010)  # wait for the first integration to complete
            print(f'Rail {name}: Vbus={d.get_bus_voltage()}V, I={d.get_current()}A, P={d.get_power()}W')






        self.pll = hmc7044(self.spi)

    def get_power_supply_status(self):
        """ Return the voltage, current and power use by each power supply rail """
        status = {}
        for name, info in self.i2c1_ina231_list.items():
            d = info['device']
            status[name] = dict(Vbus=d.get_bus_voltage(),I=d.get_current(), P=d.get_power(), Vshunt=d.get_shunt_voltage())
        return status


    def close_platform(self):
        if self.tcpipe:
            self.tcpipe.close()
            self.tcpipe = None
        self._is_open = False


    async def open_fpga_async(self, **kwargs):
        """ Open communication link with the FPGA. This creates the MMI interface, gather configuration information from the firmware, and instantiate the objects that will handle the firmware."""


        if False:
            # Before we start the firmware, make sure we have our clocks.
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

        # self.fpga = self.firmware(self)
        await self.fpga.open_async()

        # await self.open_hw()
        # await self.hw.init()
        # await self.hw.set_led('GP_LED2', 1)  # Hardware link is on
        # await self.hw.set_led('GP_LED1', 0)  # Full FPGA firmware is not yet on

        # If we want to use the FPGA's I2C firmware interface instead of the onboard processor's
        # if False:
        #     # -------------------------------------------------------------------------
        #     # Open FPGA's I2C interfaces
        #     # -------------------------------------------------------------------------
        #     self.core_i2c = i2c.I2C_base(self.fpga, self._SYSTEM_I2C_BASE_ADDR)
        #     await asyncio.sleep(0)
        #     # Create standardized I2C interface
        #     self.i2c = I2CInterface(
        #         write_read_fn=self.fpga_i2c_write_read,  # write-read function
        #         port_select_fn=self.fpga_i2c_set_port,
        #         bus_table=IceBoardHardware.FPGA_I2C_BUS_LIST,
        #         switch_addr=IceBoardHardware._FPGA_I2C_SWITCH_ADDR,
        #         parent=self)  # parent object, whose repr() is used to tag messages

    async def close_fpga_async(self):
        await self.fpga.close()

    async def init_fpga_async(self, **kwargs):
        await self.fpga.init_async(**kwargs)

    def is_open(self):
        return self._is_open

    def is_fmc_present(self, slot):
        return False

    async def ping_async(self, timeout=0.1):
        """
        Returns a boolean indicating whether the board is responding to network queries.
        """
        # print(f'{self!r} Ping_async()')
        self.logger.info('%r: Pinging %s' % (self, self.hostname))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        loop = asyncio.get_event_loop()
        try:
            await loop.sock_connect(s, (self.hostname, self.port))
            if_addr = s.getsockname()
            s.close()
        except (socket.timeout, Exception) as e:
            self.log.warn('Could not establish a TCP connection with %s:%s. Error is:\n %s' % (addr[0], addr[1], e))
            return False
        return True


    ###################################
    # Auto discovery methods
    ###################################
    # Called after open_platform_async(), but before the FPGA firmware is set.


    async def discover_serial_async(self, update=True):
        """
        Discover the serial number of this IceBoard from its IPMI data, and update the hardware map accordingly if `update=True`
        """
        self.logger.debug(f'{self!r}: discovering the serial number of board at {self.tuber_uri}')
        return "003"

    async def discover_slot_async(self, update=True):
        """ Discover the slot number of this IceBoard, and update the hardware map accordingly if `update=True`"""
        return None

    async def discover_mezzanines_async(self, update=True):
        """Detect mezzanines attached to the motherboard and update the hardware map accordingly if
        update=True.

        """
        return None


    async def discover_crate_async(self, update=True):
        """ Detect the crate in which the board is installed and update the hardware map accordingly.
        """
        return None



   ###################################
    # Firmware management
    ###################################
    # Called after open_platform_async(), but before the FPGA firmware is set.

    async def is_fpga_programmed_async(self):
        return True
        # return self.tcpipe.is_fpga_programmed()

    async def set_fpga_bitstream_async(self, firmware_mode=None, force=False, bitfile_override=None):
        """
        Configures the FPGA with the specified bitstream.


        Parameters:

            firmware (str or FPGABitstream): The firmware to program into the FPGA

                FPGABitstream: Use the specified bitstream object directly.

                str: if `firmware` has no special characters ('.', '/' etc) it is treated as a generic name that will used to be look up the firmware filename in the PLATFORM_SUPPORT table of all registered FPGAFirmware classes.
                Otherwise, the string is treated as a pathname and is passed to FPGABitstream directly.

            force (bool or None):

                force = True: FPGA will always be configured independent of the signature of the currently programmed firmware
                force = False: FPGA will be configured if it is not configured or
                        if its bitstream CRC differ from the provided bitstream
                force = None: FPGA will be configured only if it is not configured

        """


        t0 = time.time()
        self.logger.debug(f'{self!r}: called set_fpga_bitstream')

        if hasattr(self, 'close'):
            self.close()

        fw_cls, buf, fw_params = FPGAFirmware.get_firmware(self.part_number, firmware_mode, bitfile_override=bitfile_override)
        crc32 = buf.crc32
        bitstream = buf.raw_bitstream

        self.logger.debug(f'{self!r}: Getting is_programmed')
        is_fpga_programmed = await self.is_fpga_programmed_async()
        is_crc_valid = False
        if self.fpga and is_fpga_programmed:
            self.logger.debug(f'{self!r}: Getting FPGA crc')
            fpga_bitstream_crc = await self.get_fpga_bitstream_crc_async()
            self.logger.debug(
                f'{self!r}: fpga_programmed={is_fpga_programmed}, force={force}, '
                f'fpga_crc={fpga_bitstream_crc or 0:08X}, bitstream_crc={crc32 or 0:08X}')
            is_crc_valid = fpga_bitstream_crc == crc32

        if not is_fpga_programmed or force or (force is not None and not is_crc_valid):
            self.logger.debug(f'{self!r}: Configuring FPGA')
            self.tcpipe.set_fpga_bitstream(bitstream, crc=crc32)
        else:
            self.logger.debug(
                f'{self!r}: FPGA is already configured. Skipping configuration.')

        self.fpga = fw_cls(self, **fw_params)

    # Mezzanine management


    async def get_fpga_bitstream_crc_async(self):
        """ Return the signature of the firmware currently configured in the
        FPGA.

        Returns None if the FPGA is not configured.
        """
        fpga_is_programmed = await self.is_fpga_programmed_async()
        return self.tcpipe.get_fpga_bitstream_crc() if fpga_is_programmed else None

    async def set_fpga_bitstream_crc_async(self, crc32):
        """ Return the signature of the firmware currently configured in the
        FPGA.

        Returns None if the FPGA is not configured.
        """
        fpga_is_programmed = await self.is_fpga_programmed_async()
        self.tcpipe.get_fpga_bitstream_crc(crc32 if fpga_is_programmed else None)

    # def clear_fpga_bitstream(self):
    #     """ Stop the operation of the FPGA.

    #     Could be used if we detect that we don't have the right kind of
    #     mezzanines.
    #     """
    #     raise NotImplementedError()


    ###################################
    # Mezzanine EEPROM access methods
    ###################################

    async def _mezzanine_eeprom_read_async(self, mezzanine):
        """ Returns the contents of the specified mezzanine's EEPROM.
        """
        return None

    # Backplane/crate-related methods

    ###################################
    # Motherboard EEPROM access methods
    ###################################

    async def _write_motherboard_spi_eeprom_base64(self, *args, **kwargs):
        return None

    ###################################
    # Backplane info methods
    ###################################


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
        return None


    #################################
    # Metrics
    #################################

    async def get_metrics_async(self):
        """ Get the motherboard hardware monitoring information.

        Returns:
            a :cls:`Metrics` object.
        """

        metrics = await super().get_metrics_async()

        # Add ZCU111 monitoring data to metrics here

        return metrics

