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
from lib import fpga_mmi
from fpga_firmware import FpgaFirmware
from hardware_map import HWMResource, Integer, Column, String, ForeignKey, UniqueConstraint, reconstructor

class FpgaException(Exception):
    pass

class FpgaCoreFirmware(FpgaFirmware):
    """
    Provides access to the basic functionnalities of the FPGA.

    This class is meant to to provide access to functionnalities that are
    present in all FPGA firmware using a common VHDL code base, such as:
        - Buck sync control
        - I2C interface to the hardware (if the ARM does not provide it)
        - Configure and establish direct Ethernet communication with the FPGA
        - Low-level access to the FPGA memory-mapped registers
        - Basic post-configuration information:
             - FPGA serial number
             - Firmware version
             - FPGA internal voltage and temperature monitoring
             - etc.
        - Control and monitoring of generic FMC Mezzanine I/O lines (I2C, etc.)
    """

    __mapper_args__ = {'polymorphic_identity': 'core_fpga_firmware'}

    # FPGA firmware-related definition
    # serial_number = Column(Integer)
    # ip_addr = Column(String)
    # port_number = Column(Integer)

    interface_ip_addr = None # This is a class attribute, common to all instances.
    mmi = None # Memory-mapped interface object

    _BROADCAST_BASE_PORT = 41000

    _SYSTEM_BASE_ADDR   = 0x00000 # This is always at zero so we can gather info from the FPGA before we know the number of antennas etc.
    _SYSTEM_GPIO_BASE_ADDR     = _SYSTEM_BASE_ADDR + 0x00000
    _SYSTEM_I2C_BASE_ADDR      = _SYSTEM_BASE_ADDR + 0x0A000

    # GPIO Register addresses
    _GPIO_COOKIE_REG = 0x080 # Register address of the firmware cookie
    _FPGA_TIMESTAMP_ADDR = _SYSTEM_GPIO_BASE_ADDR + 0x80 + 7
    _FPGA_SERIAL_NUMBER_ADDR = _SYSTEM_GPIO_BASE_ADDR + 0x80 + 12
    _FPGA_IP_SETUP_BASE_ADDR = _SYSTEM_GPIO_BASE_ADDR + 0x00 + 13 # (13-18): target MAC, (19-22): target IP, (23-24): target_base_port, (25-32) = Target FPGA serial, (33): bit 7 = trigger, bits 3:2: mac source select, 1:0: broadcast group
    _GPIO_IPCONFIG_REG = _SYSTEM_GPIO_BASE_ADDR + 0x08D # Register address of the first byte of the IP config word


    @classmethod
    def discover_fpgas(cls, source_subarrays = [0], timeout=0.1):
        """
        Get the serial numbers of all FPGA directly connected on the network (i.e. not accessed through the ARM processor)

        NOTE: This function should not be called when the MMI interface is opened.
        """
        logger = logging.getLogger(__name__)

        if isinstance(source_subarrays, int):
            source_subarrays = [source_subarrays]

        # preserves closes the current mmi to free the socket
        # if self.mmi:
        #     self.mmi.close()

        # resources = IceResourceTable() # create an empty resource list
        serial_list = []
         # for if_addr in interface_ip:
        for subarray in source_subarrays:
            logger.debug('Searching ICEBoards on subarray %i through interface %s' % (subarray, cls.interface_ip_addr))

            with fpga_mmi.FpgaMmi(cls.interface_ip_addr, fpga_mmi.FpgaMmi.BROADCAST, cls._BROADCAST_BASE_PORT + subarray, send_only=False) as mmi:
                mmi.flush()
                serials = mmi.broadcast_read(cls._FPGA_SERIAL_NUMBER_ADDR, type = np.dtype('>u8'), timeout = timeout)
            serial_list += serials

        # self.mmi.open()

        return serial_list

    @classmethod
    def set_networking_parameters(cls, serial_number, interface_ip_addr, ip_addr, port_number, broadcast_group=0, number_of_trials = 3, check=True):
        """
        Sets the FPGA firmwarein the specified ICEboard to use the specified ip address and port.
        The board will be searched on the Ethernet interface associated with 'if_addr'
        If no ip address or port is specified, a port/address will be automatically assigned based on the interface address.
        An exception will be raised if the board cannot be found on the network of if another board uses the same ip address.
        """

        logger = logging.getLogger(__name__)
        logger.debug('Broadcasting on port %i to configure FPGA S/N %016X with address %s:%i' % (cls._BROADCAST_BASE_PORT, serial_number, ip_addr, port_number))

        # Build the array of bytes to fill the network configuration register block
        ip_setup_string = struct.pack('>H4s4sHQ', 0x1234, socket.inet_aton(ip_addr), socket.inet_aton(ip_addr), port_number, serial_number)
        trig1 = chr(0x0C | broadcast_group)
        trig2 = chr(0x8C | broadcast_group)

        # Configure the FPGA through a UDP broadcast packet containing the target FPGA serial number
        trial = 0
        while trial < number_of_trials:
            with fpga_mmi.FpgaMmi(interface_ip_addr, fpga_mmi.FpgaMmi.BROADCAST, cls._BROADCAST_BASE_PORT, send_only=True) as mmi:
                mmi.write(cls._FPGA_IP_SETUP_BASE_ADDR, ip_setup_string + trig1) # Send string with trigger flag cleared
                mmi.write(cls._FPGA_IP_SETUP_BASE_ADDR, ip_setup_string + trig2) # resend with trigger flag set. The 0-to-1 transition will load the desired networking parameters
                mmi.write(cls._FPGA_IP_SETUP_BASE_ADDR, [0] * len(ip_setup_string + trig2)) # Write zeros everywhere to make sure we stop latching data
            # logger.debug('FPGA S/N %016X is configured with address %s:%i' % (serial_number, ip_addr, port_number))
            if not check:
                return
            (serial, timestamp) = cls.get_fpga_config(ip_addr = ip_addr, port_number = port_number)
            if serial and serial == serial_number:
                return
            else:
                logger.debug('Networking configuration of FPGA S/N %016X with address %s:%i failed.' % (serial_number, ip_addr, port_number))
                trial +=1
        logger.debug('Unable to configure FPGA S/N %016X with address %s:%i' % (serial_number, ip_addr, port_number))


    @classmethod
    def get_fpga_config(cls, ip_addr, port_number, timeout = 0.1, number_of_trials=3):
        """
        Returns basic information allowing to check if we talk to the right FPGA with the right firmware.
        Will not cause an exception if the FPGA fails to respond at the specified address. Instead, all fields will be None.
        """
        trial = 0
        with fpga_mmi.FpgaMmi(cls.interface_ip_addr, ip_addr, port_number, timeout = timeout ) as mmi:
            while trial < number_of_trials:
                try:
                    serial = mmi.read(cls._FPGA_SERIAL_NUMBER_ADDR, type = np.dtype('>u8'))
                    timestamp = mmi.read(cls._FPGA_TIMESTAMP_ADDR, type = np.dtype('>u4'))
                    return (serial, timestamp)
                except mmi.TimeoutException:
                    trial += 1
        return (None, None)

    def __init__(self, *args, **kwargs):
        """
        Creates an FPGA object.

        We provide the serial number to configure the FPGA direct ethernet
        interface with the specified network parameters. This is not needed if
        access is done through the ARM.

        """
        FpgaFirmware.__init__(self, *args, **kwargs)
        # super(type(self), self).__init__(*args, **kwargs)
        # self.motherboard = motherboard

    def get_core_attributes(self):
        """
        Returns a list of attributes published by the *core* fpga firmware
        only even if 'self' represents an instance of a superclass of
        FpgaCoreFirmware.
        """
        # core_attributes =  FpgaCoreFirmware.__dict__.keys() + self.__dict__.keys()
        # return [name for name in core_attributes if name[0] !='_']
        return []

    # def open_core(self, ip_addr, port_number, interface_ip_addr=None, broadcast_group = 0, serial_number = 0):
    def open_core(self, ip_addr, port_number, serial_number, broadcast_group = 0):
        """
        Opens the communication link with the core FPGA firmware.
        This is called during the establishment of the link with the IceBoard (IceBoard.open()).

        The application-specific code should use the 'open' method if needed,
        which is called when the links to the IceBoard hardware are finished
        establishing.
        """

        # Store networking parameters for easy future reference
        self.ip_addr  = ip_addr
        self.port_number = port_number
        self.serial_number = serial_number # FPGA serial number
        # self.interface_ip_addr = interface_ip_addr # # interface IP address, needed to setup UDP communications and UDB broadcasts
        self._broadcast_group = broadcast_group
        self._logger = logging.getLogger(__name__)

        # Close any previously opened memory-mapped interface to free the sockets
        if self.mmi:
            self.mmi.close()

        # Set the FPGA communication networking parameters
        if self.serial_number:
            self.set_networking_parameters(self.serial_number, self.interface_ip_addr, self.ip_addr, self.port_number, self._broadcast_group)

        # Open communications with the FPGA memory mapped-interface
        self.mmi = fpga_mmi.FpgaMmi(self.interface_ip_addr, self.ip_addr, self.port_number)

        self._logger.debug('=== Instantiating GPIO')
        self._base_gpio = gpio.GPIO_base(self.mmi, self._SYSTEM_GPIO_BASE_ADDR)

        # Instantiate the I2C handler
        self._logger.debug('=== Instantiating I2C')
        self._base_i2c = i2c.I2C_base(self.mmi, self._SYSTEM_I2C_BASE_ADDR)

    def close_core(self):
        """
        Closes the link to the core FPGA firmware.
        """

        self._base_gpio = None
        self._base_i2c = None
        if self.mmi:
            self.mmi.close()
            self.mmi = None

    def open(self):
        """
        Placeholder for the application-specific open method.
        """

    def close(self):
        """
        Placeholder for the application-specific close method.
        """

    def read(self, *args, **kwargs):
        return self.mmi.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        self.mmi.write(*args, **kwargs)

    def ping_mmi(self, ip_addr, timeout):
        """
        Verifies if the FPGA firmeware is responding using the IP address of the board.
        """
        raise NotImplementedError

    def ping_broadcast(self, fpga_serial_number, timeout):
        """
        Verifies if the FPGA firmeware is responding using a broadcast.
        """
        raise NotImplementedError

    def get_serial_number(self):
           return self.mmi.read(self._FPGA_SERIAL_NUMBER_ADDR, type = np.dtype('>u8'))

    def get_fpga_cookie(self):
        """
        Reads the FPGA and returns the cookie that identifies the firmware.
        This method can be called before any FPGA modules are instatiated.
        """
        return self.read(self._SYSTEM_GPIO_BASE_ADDR + self.base__gpio_COOKIE_REG) & 0x7F

    def get_version(self):
        """
        Returns the firmware revion currenting running on the FPGA (which si the date and time of bitstream generation)
        """
        return self._base_gpio.get_bitstream_date()

    def i2c_write_read(self, *args, **kwargs):
        """
        Performs I2C read, write or SMB-compatible combined write/read operations
        (SMB or its subset PMB require the register address to be written and then data to be read immediately after an I2C restart. It cannot be done in separate write and read  operations)
        Writes up to 3 bytes to the addressed I2C device and/or reads up to 4 bytes from that device after a restart.
        See the FPGA I2C module for detailed method description.
        """
        return self._base_i2c.write_read(*args, **kwargs)

    def i2c_set_port(self, *args, **kwargs):
        """
        Sets the FPGA hardware port over which the i2c communications will be made after this call.
        This selects the FPGA pins over which the communications is done, *not* the bus selection done by an I2C switch.
        """
        return self._base_i2c.set_port(*args, **kwargs)

