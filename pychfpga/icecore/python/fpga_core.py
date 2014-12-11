#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
fpga_core.py module
Provides access the basic functionnalities of the FPGA

 History:
        2014-03-07 JFC: Created
"""
import logging
import struct
import socket
import numpy as np

import pychfpga.core.I2C as i2c # to be fixed: tese modules should live in icecore.lib
import pychfpga.core.GPIO as gpio
from iceboard_hardware import I2CInterface
from iceboard_hardware import IceBoardHardware

class FpgaException(Exception):
    pass

class FpgaCoreFirmware(object):
    """
    Provides access to the functionnalities that are present in all FPGA
    firmware using the common VHDL IceBoard code base, such as:

        - Low-level access to the memory-mapped registers in the FPGA firmware
          (through the FPGA Ethernet port or through the ARM processor)
        - Power Switcher phase and frequency controls
        - low-level I2C interface to the IceBoard and backplane hardware
        - Configure and establish direct Ethernet communication with the FPGA
        - Basic post-configuration information:
             - FPGA serial number
             - Firmware version
             - Firmware timestamp
             - Firmware cookie
             - FPGA internal voltage and temperature monitoring
             - etc.
        - Control and monitoring of FMC Mezzanines

    """

    # ---------------------------------------
    # Class attributes (common to all instances)
    # ---------------------------------------
    MMI_FPGA_ETHERNET = "fpga_ethernet"
    MMI_ARM_SPI = "arm_spi"
    MMI_ARM_ETHERNET = "arm_ethernet"

    interface_ip_addr = None # This is a class attribute, common to all instances.
    _BROADCAST_BASE_PORT = 41000

    _SYSTEM_BASE_ADDR      = 0x00000 # This is always at zero so we can gather info from the FPGA before we know the number of antennas etc.
    _SYSTEM_GPIO_BASE_ADDR = _SYSTEM_BASE_ADDR + 0x00000
    _SYSTEM_I2C_BASE_ADDR  = _SYSTEM_BASE_ADDR + 0x05000

    # Match those with what is used by Module
    _CONTROL_BASE_ADDR = 0x000000
    _STATUS_BASE_ADDR  = 0x080000
    _RAM_BASE_ADDR     = 0x100000


    # GPIO Register addresses
    _GPIO_COOKIE_REG         = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR  # Register address of the firmware cookie
    _FPGA_TIMESTAMP_ADDR     = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 7
    _FPGA_SERIAL_NUMBER_ADDR = _STATUS_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 12
    _FPGA_IP_SETUP_BASE_ADDR = _CONTROL_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 13 # (13-18): target MAC, (19-22): target IP, (23-24): target_base_port, (25-32) = Target FPGA serial, (33): bit 7 = trigger, bits 3:2: mac source select, 1:0: broadcast group
    # _GPIO_IPCONFIG_REG       = _CONTROL_BASE_ADDR + _SYSTEM_GPIO_BASE_ADDR + 0x08D # Register address of the first byte of the IP config word

    # ---------------------------------------
    # Instance attributes
    # ---------------------------------------
    mmi = None # Memory-mapped interface object
    _is_core_open = None


    class AutoOpen(object):
        """ This class is a placeholder for the unopened MMI interface object. Whenever
        someone tried to access an MMI attribute, the parent's open() function
        is called to establish the MMI link.
        """
        def __init__(self, core):
            self.core = core
        def __getattr__(self, name):
            self.core.open_core()
            return getattr(self.core.mmi, name)
        def close(self): pass

    def __init__(self, **kwargs):
        """ Initializes the object providing the core FPGA firmware functionalities
        """
        self.logger = logging.getLogger(__name__)

        super(FpgaCoreFirmware, self).__init__(**kwargs) # pass all arguments to superclasses. All superclass must call super() to be collaborative. We use keywords arguments only because we don't want to assume what parameters the subclasses need.

        if self.is_core_open():
            self.logger.error('Attempting to create a firmware instance for Iceboard S/N %s while an instance already exists' % self.iceboard_pk)

        self.fpga_mmi_type = self.MMI_FPGA_ETHERNET # This type of MMI interface requires self.fpga_ip_addr, self.fpga_port_number and self.fpga_serial_number
        self.mmi = self.AutoOpen(self) # open the MMI interface automatically if we try to access it.
        self.i2c = None

    def open_core(self):
        """
        Opens the communication link with the core FPGA firmware.
        This is called during the establishment of the link with the IceBoard (IceBoard.open()).

        The application-specific code should use the 'open' method if needed,
        which is called when the links to the IceBoard hardware are finished
        establishing.

       """

        # Store networking parameters for easy future reference
        # self.ip_addr  = ip_addr
        # self.port_number = port_number
        # # self.serial_number = serial_number # FPGA serial number
        # self.interface_ip_addr = interface_ip_addr # # interface IP address, needed to setup UDP communications and UDB broadcasts
        # self._broadcast_group = broadcast_group

        if not self.is_fpga_programmed():
            raise FpgaException("Attempting to access the  Iceboard S/N %s FPGA's Memory-mapped interface while the FPGA is not yet programmed with a bitstream" % self.serial_number)

        # Close any previously opened memory-mapped interface to free the sockets
        if self.mmi:
            self.mmi.close()

        # Open communications with the FPGA memory mapped-interface
        if self.fpga_mmi_type == self.MMI_FPGA_ETHERNET:
            from lib.fpga_mmi import FpgaMmi
            self.mmi = FpgaMmi(self.fpga_ip_addr, self.fpga_port_number, fpga_serial_number = self.fpga_serial_number, set_fpga_networking_parameters = True)

        self.mmi.open()

        self.logger.debug('=== Instantiating core GPIO')
        self._base_gpio = gpio.GPIO_base(self.mmi, self._SYSTEM_GPIO_BASE_ADDR)

        # Instantiate the I2C handler
        self.logger.debug('=== Instantiating core I2C')
        self._base_i2c = i2c.I2C_base(self.mmi, self._SYSTEM_I2C_BASE_ADDR)

        # Create a standardized I2C interface to the IceBoard hardware through the FPGA
        if not self.i2c: # If i2c interface not already provided my the ARM
            self.i2c = I2CInterface(self.fpga_i2c_write_read, self.fpga_i2c_set_port, IceBoardHardware.FPGA_I2C_BUS_LIST, IceBoardHardware._FPGA_I2C_SWITCH_ADDR)

        self._is_core_open = True

    def close_core(self):
        """
        Closes the link to the core FPGA firmware.
        """

        self._base_gpio = None
        self._base_i2c = None
        if self.mmi:
            self.mmi.close()
            self.mmi = self.AutoOpen(self) # open the MMI interface automatically if we try to access it.
        self._is_core_open = False

    def is_core_open(self):
        # return self.iceboard_pk in type(self)._active_instances
        return bool(self._is_core_open)

    def mmi_read(self, *args, **kwargs):
        return self.mmi.read(*args, **kwargs)

    def mmi_write(self, *args, **kwargs):
        self.mmi.write(*args, **kwargs)

    def get_fpga_serial_number(self):
           return self.mmi.read(self._FPGA_SERIAL_NUMBER_ADDR, type = np.dtype('>u8'))

    def get_fpga_firmware_cookie(self):
        """
        Reads the FPGA and returns the cookie that identifies the firmware.
        This method can be called before any FPGA modules are instatiated.
        """
        return self.mmi.read(self._GPIO_COOKIE_REG) & 0x7F

    def get_fpga_firmware_version(self):
        """
        Returns the firmware revion currenting running on the FPGA (which si the date and time of bitstream generation)
        """
        return self._base_gpio.get_bitstream_date()

    def fpga_i2c_write_read(self, *args, **kwargs):
        """
        Performs I2C read, write or SMB-compatible combined write/read operations
        (SMB or its subset PMB require the register address to be written and then data to be read immediately after an I2C restart. It cannot be done in separate write and read  operations)
        Writes up to 3 bytes to the addressed I2C device and/or reads up to 4 bytes from that device after a restart.
        See the FPGA I2C module for detailed method description.
        """
        return self._base_i2c.write_read(*args, **kwargs)

    def fpga_i2c_set_port(self, *args, **kwargs):
        """
        Sets the FPGA hardware port over which the i2c communications will be made after this call.
        This selects the FPGA pins over which the communications is done, *not* the bus selection done by an I2C switch.
        """
        return self._base_i2c.set_port(*args, **kwargs)

