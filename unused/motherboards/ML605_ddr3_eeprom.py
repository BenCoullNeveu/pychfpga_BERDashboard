#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
ddr3_eeprom.py module

 History:
 2013-08-08 : JFC : Created
"""
import logging

class ddr3_eeprom(object):
    """
    Provides access to the ML605 DDR3 memory embedded EEPROM.
    """

    def read_DDR3_reg(self, addr):
        """ Reads from the EEPROM"""
        i2c = self.fpga_instance.I2C
        i2c_addr = 0x1b

        i2c.select_buses('DDR3')
        i2c.write_read(i2c_addr, [addr]) # sets the address
        data = i2c.write_read(i2c_addr, length=2) # reads a word
        return data
