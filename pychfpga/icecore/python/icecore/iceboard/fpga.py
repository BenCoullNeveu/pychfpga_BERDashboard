#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
fpga.py module
Provides access the basic functionnalities of the FPGA

 History:
        2014-03-07 JFC: Created
"""
#import time
import argparse
import logging
#import sys
import struct
import socket

# import re
import numpy as np
# from Module import Module_base, BitField
import fpga_mmi

# import Module
# import pychfpga.core.SPI as spi
import pychfpga.core.I2C as i2c
import pychfpga.core.GPIO as gpio
# import pychfpga.core.SYSMON as sysmon

from ..attribute_publisher import AttributePublisher

class FpgaException(Exception):
    pass


class FpgaFirmware(AttributePublisher):
    """
    Provides access to  the basic functionnalities of the FPGA.
    """
    BROADCAST_BASE_PORT = 41000

    SYSTEM_BASE_ADDR   = 0x00000 # This is always at zero so we can gather info from the FPGA before we know the number of antennas etc.

    SYSTEM_GPIO_BASE_ADDR     = SYSTEM_BASE_ADDR + 0x00000


    SYSTEM_GPIO_BASE_ADDR     = SYSTEM_BASE_ADDR + 0x00000
    SYSTEM_SYSMON_BASE_ADDR   = SYSTEM_BASE_ADDR + 0x02000
    SYSTEM_FREQ_CTR_BASE_ADDR = SYSTEM_BASE_ADDR + 0x04000
    SYSTEM_SPI_BASE_ADDR      = SYSTEM_BASE_ADDR + 0x06000
    SYSTEM_REFCLK_BASE_ADDR   = SYSTEM_BASE_ADDR + 0x08000
    SYSTEM_I2C_BASE_ADDR      = SYSTEM_BASE_ADDR + 0x0A000

    # GPIO Register addresses
    GPIO_COOKIE_REG = 0x080 # Register address of the firmware cookie
    FPGA_TIMESTAMP_ADDR = SYSTEM_GPIO_BASE_ADDR + 0x80 + 7
    FPGA_SERIAL_NUMBER_ADDR = SYSTEM_GPIO_BASE_ADDR + 0x80 + 12
    FPGA_IP_SETUP_BASE_ADDR = SYSTEM_GPIO_BASE_ADDR + 0x00 + 13 # (13-18): target MAC, (19-22): target IP, (23-24): target_base_port, (25-32) = Target FPGA serial, (33): bit 7 = trigger, bits 3:2: mac source select, 1:0: broadcast group
    GPIO_IPCONFIG_REG = SYSTEM_GPIO_BASE_ADDR + 0x08D # Register address of the first byte of the IP config word


    PLATFORM_ID_ML605 = 0
    PLATFORM_ID_KC705 = 1
    PLATFORM_ID_MGK7MB_REV0 = 2
    PLATFORM_ID_MGK7MB_REV2 = 3

    # PLATFORM_ID_LIST = {
    #     # ID: ( Board name, class to instantiate)
    #     PLATFORM_ID_ML605: ('Virtex 6 (XC6V240T-1 FFG1156) on Xilinx ML605 Evaluation board', None),
    #     PLATFORM_ID_KC705: ('Kintex 7 (XC7K325T-2 FFG900C) on Xilinx KC705 Evaluation board', None),
    #     # PLATFORM_ID_MGK7MB_REV0: ('Kintex 7 (XC7K420T-2 FFG901) on McGill MGK7MB / ICEBoard Rev0', mgk7mb.MGK7MB),
    #     # PLATFORM_ID_MGK7MB_REV2: ('Kintex 7 (XC7K420T-2 FFG901) on McGill MGK7MB / ICEBoard Rev2', mgk7mb.MGK7MB),
    # }

    @classmethod
    def discover_fpgas(cls, interface_ip_addr, source_subarrays = [0], timeout=0.1):
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
            logger.debug('Searching ICEBoards on subarray %i through interface %s' % (subarray, interface_ip_addr))

            with fpga_mmi.FpgaMmi(interface_ip_addr, fpga_mmi.FpgaMmi.BROADCAST, cls.BROADCAST_BASE_PORT + subarray) as mmi:
                mmi.flush()
                serials = mmi.broadcast_read(cls.FPGA_SERIAL_NUMBER_ADDR, type = np.dtype('>u8'), timeout = timeout)
            serial_list += serials

        # self.mmi.open()

        return serial_list

    @classmethod
    def set_networking_parameters(cls, serial_number, interface_ip_addr, ip_addr, port_number, broadcast_group=0):
        """
        Sets the FPGA firmwarein the specified ICEboard to use the specified ip address and port.
        The board will be searched on the Ethernet interface associated with 'if_addr'
        If no ip address or port is specified, a port/address will be automatically assigned based on the interface address.
        An exception will be raised if the board cannot be found on the network of if another board uses the same ip address.
        """

        logger = logging.getLogger(__name__)
        logger.debug('Broadcasting on port %i to configure FPGA S/N %016X with address %s:%i' % (cls.BROADCAST_BASE_PORT, serial_number, ip_addr, port_number))

        # Build the array of bytes to fill the network configuration register block
        ip_setup_string = struct.pack('>H4s4sHQ', 0x1234, socket.inet_aton(ip_addr), socket.inet_aton(ip_addr), port_number, serial_number)
        trig1 = chr(0x0C | broadcast_group)
        trig2 = chr(0x8C | broadcast_group)

        # Configure the FPGA through a UDP broadcast packet containing the target FPGA serial number
        with fpga_mmi.FpgaMmi(interface_ip_addr, fpga_mmi.FpgaMmi.BROADCAST, cls.BROADCAST_BASE_PORT ) as mmi:
            mmi.write(cls.FPGA_IP_SETUP_BASE_ADDR, ip_setup_string + trig1) # Send string with trigger flag cleared
            mmi.write(cls.FPGA_IP_SETUP_BASE_ADDR, ip_setup_string + trig2) # resend with trigger flag set. The 0-to-1 transition will load the desired networking parameters
            mmi.write(cls.FPGA_IP_SETUP_BASE_ADDR, [0] * len(ip_setup_string + trig2)) # Write zeros everywhere to make sure we stop latching data
        logger.debug('FPGA S/N %016X is configured with address %s:%i' % (serial_number, ip_addr, port_number))

    @classmethod
    def get_fpga_config(cls, interface_ip_addr, ip_addr, port_number, timeout = 0.1):
        """
        Returns basic information allowing to check if we talk to the right FPGA with the right firmware.
        Will not cause an exception if the FPGA fails to respond at the specified address. Instead, all fields will be None.
        """
        with fpga_mmi.FpgaMmi(interface_ip_addr, ip_addr, port_number, timeout = timeout ) as mmi:
            try:
                serial = mmi.read(cls.FPGA_SERIAL_NUMBER_ADDR, type = np.dtype('>u8'))
                timestamp = mmi.read(cls.FPGA_TIMESTAMP_ADDR, type = np.dtype('>u4'))
                result= (serial, timestamp)
            except mmi.TimeoutException:
                result= (None, None)
        return result

    def __init__(self, motherboard, ip_addr, port_number, interface_ip_addr=None, broadcast_group = 0, serial_number = 0):
        """
        Creates an FPGA object.

        We provide the serial number to configure the FPGA direct ethernet
        interface with the specified network parameters. This is not needed if
        access is done through the ARM.

        """
        self.motherboard = motherboard
        self.ip_addr  = ip_addr
        self.port_number = port_number
        self.serial_number = serial_number
        self.if_ip_addr = interface_ip_addr
        self.broadcast_group = broadcast_group


        self.logger = logging.getLogger(__name__)
        self.mmi = None


        if serial_number:
            self.set_networking_parameters(serial_number, interface_ip_addr, ip_addr, port_number, broadcast_group = broadcast_group)

        # self.open()



        # self.logger.debug('=== Instantiating SYSMON')
        # self.sysmon = sysmon.SYSMON_base(self.mmi, self.SYSTEM_SYSMON_BASE_ADDR)

        # self.logger.debug('=== Instantiating SPI')
        # self.spi = spi.SPI_base(self.mmi, self.SYSTEM_SPI_BASE_ADDR)

        # self.logger.info('=== Getting board info information')

        # return

        # self.PLATFORM_ID = self.base_gpio.PLATFORM_ID
        # if self.PLATFORM_ID not in self.PLATFORM_ID_LIST:
        #     raise FpgaException('Platform ID 0x%02X is not recognized' % self.PLATFORM_ID)
        # self.NUMBER_OF_FMC_SLOTS = None



    def open(self):
        if self.mmi:
            self.mmi.close()
        self.mmi = fpga_mmi.FpgaMmi(self.if_ip_addr, self.ip_addr, self.port_number)

        self.logger.debug('=== Instantiating GPIO')
        self.base_gpio = gpio.GPIO_base(self.mmi, self.SYSTEM_GPIO_BASE_ADDR)

        # Instantiate the I2C handler
        self.logger.debug('=== Instantiating I2C')
        self.base_i2c = i2c.I2C_base(self.mmi, self.SYSTEM_I2C_BASE_ADDR)

    def close(self):
        self.base_gpio = None
        self.base_i2c = None
        self.mmi.close()
        self.mmi = None

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



#    FPGA_IP_SETUP_BASE_ADDR = 0x00000+13 # (13-18): target MAC, (19-22): target IP, (23-24): target_base_port, (25-32) = Target FPGA serial, (33): bit 7 = trigger, bits 3:2: mac source select, 1:0: broadcast group

    # def check_serial_number(self, target_serial_number):
    #     """
    #     Confirms that the FPGA returns the expected serial number
    #     Assumes the MMI is open.
    #     """
    #     # with fpga_mmi.FpgaMmi(interface_ip_addr,  iceboard.fpga_ip_addr,  iceboard.fpga_port_number) as mmi:
    #     self.logger.debug('Checking configuration')
    #     # Now test communications woth the target address
    #     try:
    #        fpga_serial = self.get_serial_number()
    #     except self.mmi.TimeoutException:
    #        raise FpgaException('Unable to read FPGA serial number from address %s:%i' % (self.ip_addr, self.port_number))

    #     self.logger.debug('FPGA at %s:%i reported a serial number of %016X' % ( self.ip_addr, self.port_number, self.serial_number))
    #     if fpga_serial != self.serial_number:
    #             raise FpgaException('FPGA at address %s:%i returned the wrong serial number %16X. Expecting %16X' % (self.ip_addr, self.port_number, fpga_serial, self.serial_number))

    #     return True

    def get_serial_number(self):
           return self.mmi.read(self.FPGA_SERIAL_NUMBER_ADDR, type = np.dtype('>u8'))

    def get_fpga_cookie(self):
        """
        Reads the FPGA and returns the cookie that identifies the firmware.
        This method can be called before any FPGA modules are instatiated.
        """
        return self.read(self.SYSTEM_GPIO_BASE_ADDR + self.base_gpio_COOKIE_REG) & 0x7F

    def get_version(self):
        """
        Returns the firmware revion currenting running on the FPGA (which si the date and time of bitstream generation)
        """
        return self.base_gpio.get_bitstream_date()

    def i2c_write_read(self, *args, **kwargs):
        """
        Performs I2C read, write or SMB-compatible combined write/read operations
        (SMB or its subset PMB require the register address to be written and then data to be read immediately after an I2C restart. It cannot be done in separate write and read  operations)
        Writes up to 3 bytes to the addressed I2C device and/or reads up to 4 bytes from that device after a restart.
        See the FPGA I2C module for detailed method description.
        """
        return self.base_i2c.write_read(*args, **kwargs)

    def i2c_set_port(self, *args, **kwargs):
        """
        Sets the FPGA hardware port over which the i2c communications will be made after this call.
        This selects the FPGA pins over which the communications is done, *not* the bus selection done by an I2C switch.
        """
        return self.base_i2c.set_port(*args, **kwargs)

