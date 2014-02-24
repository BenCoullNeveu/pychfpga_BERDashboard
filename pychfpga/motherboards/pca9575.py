#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
pca9575: Implememnts access to a TCA9548A I2C switch.

 History:
 2013-08-08 : JFC : Created
 2014-02-23 JFC: Added register table, select(), masked write.
"""
# MGADC08 FMC ADC board device handlers
import logging

class pca9575(object):
    """
    Implements the interface to the PCS8575 I2C IO Extender.
    """
    REGISTER_TABLE = {
        'IN0': 0x00, # input port register
        'IN1': 0x01, 
        'INVRT0': 0x02,
        'INVRT1': 0x03,
        'BKEN0': 0x04,
        'BKEN1': 0x05,
        'PUPD0': 0x06,
        'PUPD1': 0x07,
        'CFG0': 0x08,
        'CFG1': 0x09,
        'OUT0': 0x0A,
        'OUT1': 0x0B,
        'MSK0': 0x0C,
        'MSK1': 0x0D,
        'INTS0': 0x0E,
        'INTS1': 0x0F
        }

    def __init__(self, i2c_interface, address, port = 'GPIO', verbose=0):
        """
        Creates an object that interfaces the PCS8575 I2C IO Extender. 
        Access is done through the I2C object 'i2c_interface' at I2C address 'address' and on port 'port'.
        The i2c interface must provide the following methods:
            set_port()
            write_read()
        """
        self.i2c = i2c_interface
        self.address = address
        self.port = port


    def select(self):
        """
        Selects the proper I2C port to talk to this device. 
        """
        self.i2c.select_bus(self.port)

    def write(self, register, value, mask = 0xff, select = True):
        """ 
        Writes a byte to the specified register of the IO Expander.
        'register' can be the register address or the register name taken from REGISTER_TABLE.
        The I2C port for this device is set prior to the operation if 'select' is True.
        If 'mask' is specified, only the bits position that are set in 'mask' are changed.
        """
        # Convert port name a port address if the name is in the table. Otherwise use the argument as a port address directly.
        if register in self.REGISTER_TABLE:
            register = self.REGISTER_TABLE[register]

        if select:
            self.select()

        if (mask & 0xFF)  != 0xff:
            old_value = self.i2c.write_read(self.address, read_length=1)
            new_value = (old_value & (~ mask)) | (value & mask)
        else:
            new_value = value

        self.i2c.write_read(self.address, data=[register, new_value])

    def read(self, register, select = True):
        """ 
        Read a value to the specified register
        """
        if select:
            self.select()

        return self.i2c.write_read(self.address, data=[register], read_length=1)


