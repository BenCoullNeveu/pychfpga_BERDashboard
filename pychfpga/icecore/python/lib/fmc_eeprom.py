#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
FMC_EEPROM.py module
 Implements the FMC EEPROM interface
 History:
    2012-03-29 JFC : Created
    2012-08-27 JFC : Fixed reference to common.util as pychfpga.common.util
"""
import logging
import numpy as np

class FMC_EEPROM(object):
    """ Implements the MGADC08 FMC EEPROM interface """
    # I2C addresses
    FMC_EPPROM_ADDR = 0x50    # 0x50 and 0x51 are the two pages.
    FMC_EPPROM_PORT = 0    #
    FMC_EEPROM_ADDR_WIDTH = 17
    def __init__(self, i2c_handler, fmc_name, verbose=1, address=FMC_EPPROM_ADDR, address_width= FMC_EEPROM_ADDR_WIDTH):
        self.i2c = i2c_handler
        self.fmc_name = fmc_name
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.address = address
        self.address_width = address_width

    def _get_addr_bytes(self, addr):
        """
        Return a list of bytes corresponding to the EEPROM address.

        """
        addr_bytes = self.address_width // 8 +1 # add an extra byte for the part that falls in the I2c address field
        bytes = [((addr >> (8*i)) & 0xff) for i in range(addr_bytes-1, -1, -1)]
        bytes[0] &= 2**(self.address_width % 8)-1 # mask the bits not used for data address in the i2c command byte
        return bytes

    def read(self, addr, length=1, retry=0, **kwargs):
        """ Reads from the EEPROM"""

        if addr is not None:
            if (addr <0 or (addr+length-1) > (2**self.address_width-1)):
                raise ValueError('Invalid EEPROM address range. All reads must be from adress 0x%x and 0x%x' % (0, (2**self.address_width-1)))

        trial = 0
        while True:
            try:
                self.i2c.select_bus(self.fmc_name)
                break
            except:
                self.logger.warning('I2C Error while setting I2C switch to %s. Retrying...' % self.fmc_name)
                trial +=1
                if trial>retry:
                    self.logger.error('Failed to set I2C switch to %s.' % (self.fmc_name))
                    raise
        data = np.array([], np.uint8)
        while length:
            # print '.',
            block_length = min(length, 4)
            if addr is None:
                addr_bytes = [0]
            else:
                addr_bytes = self._get_addr_bytes(addr)
            trial = 0
            while True:
                try:

                    block_data = self.i2c.write_read(self.address + addr_bytes[0], addr_bytes[1:], read_length=block_length, **kwargs) # reads a byte
                    break
                except:
                    self.logger.warning('I2C Error while reading EEPROM at memory address %i. Retrying...' % addr)
                    trial +=1
                    if trial>retry:
                        self.logger.error('Failed to read EEPROM at memory address %i after %i retries.' % (addr, retry))
                        raise
            data = np.hstack((data, block_data))
            # print 'data=', data
            length -= block_length
            if addr is not None:
                addr += block_length
            # print length
        return data

    def write(self, addr, data, **kwargs):
        """ Writes to the EEPROM"""
        self.i2c.select_bus(self.fmc_name)
        addr_bytes = self._get_addr_bytes(addr)
        if isinstance(data, int):
            data = [data]
        while data:
            block_length = min(len(data), 3)
            self.i2c.write_read(self.address + addr_bytes[0], addr_bytes[1:]+data[:block_length], read_length = 0, **kwargs) # sets the address
            data = data[block_length+1:]

    def set_addr(self, addr, **kwargs):
        """ Sets the current read/write address of the EEPROM"""
        self.i2c.select_bus(self.fmc_name)
        addr_bytes = self._get_addr_bytes(addr)
        self.i2c.write_read(self.address + addr_bytes[0], addr_bytes[1:], read_length = 0, **kwargs) # sets the address

    def init(self):
        """ Initializes the EEPROM handling module (the EEPROM is not accecssed)"""
        pass

    def status(self):
        """ Shows EEPROM data"""
        self.logger.info('-- FMC EEPROM ')
        try:
            self.logger.info('FMC EEPROM data at address 0x00-0x03 is: %s' % ' '.join([hex(x) for x in self.read(0, length=4)]))
        except:
            self.logger.info('FMC EEPROM did not respond')

