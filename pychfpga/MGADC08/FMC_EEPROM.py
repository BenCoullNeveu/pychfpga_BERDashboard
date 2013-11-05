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
from pychfpga.common import util


class FMC_EEPROM_base(object):
    """ Implements the MGADC08 FMC EEPROM interface """
    # I2C addresses
    FMC_EPPROM_ADDR = 0x50    # 0x50 and 0x51 are the two pages.
    FMC_EPPROM_PORT = 0    # 

    def __init__(self, i2c_handler, fmc_name, verbose=1):
        self.i2c = i2c_handler
        self.fmc_name = fmc_name
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

    def read(self, addr, length=1, **kwargs):
        """ Reads from the EEPROM"""
        self.i2c.select_bus(self.fmc_name)
        data = self.i2c.write_read(self.FMC_EPPROM_ADDR + ((addr >> 16) & 1), [(addr >> 8) & 0xff, addr & 0xff], read_length=length, **kwargs) # reads a byte
        return data

    def write(self, addr, data, **kwargs):
        """ Writes to the EEPROM"""
        self.i2c.select_bus(self.fmc_name)
        self.i2c.write_read(self.FMC_EPPROM_ADDR + ((addr >> 16) & 1), [(addr >> 8) & 0xff, addr & 0xff, data], read_length = 0, **kwargs) # sets the address

    def init(self):
        """ Initializes the EEPROM handling module (the EEPROM is not accecssed)"""
        pass



    
    def status(self):
        """ Shows EEPROM data"""
        self.logger.info('-- FMC EEPROM ')
        try:
            self.logger.info('FMC EEPROM data at address 0x00-0x03 is: %s' % util.hex(self.read(0, length=4)))
        except:
            self.logger.info('FMC EEPROM did not respond')
    
