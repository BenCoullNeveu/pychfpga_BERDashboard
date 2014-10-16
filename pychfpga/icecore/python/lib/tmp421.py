#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
tmp421: Implememnts access to a TEMP100 I2C temperature sensor.

 History:
 2014-03-04 JM: created
 2014-03-18 JM: Fixed read function to allow reading by register name, not only by register address
                Fixed masking in write function
                Added get_temperature
 2014-10-14 AJG: Modified for use with temp421
"""
# MGADC08 FMC ADC board device handlers
import logging
import numpy as np

class tmp421(object):
    """
    Implements the interface to the TEMP100 I2C temperature sensor.
    """
    REGISTER_TABLE = {
        'THIGH_LCL': 0x00, # Local temperature (High byte)  - 2 read compatible
        'THIGH_RMT': 0x01, # Remote Temperature (High byte) - 2 read compatible
        'STATUS': 0x08,    #Status register
        'CFG1': 0x09, #Config Register 1
        'CFG2': 0x0a, #Config Register 2
        'RATE': 0x0b, #Conversion rate register
        'ONESHOT': 0x0f, #One shot start register
        'TLOW_LCL': 0x10, # Local temperature (Low byte)
        'TLOW_RMT': 0x11, # Remote temperature (Low byte)
        'CORR' : 0x21, #Temperature correction
        'RST' : 0xFC, #Software reset
        'MID' : 0xFE, #Manufacture ID
        'DID' : 0xFF #Device ID
        }

    def __init__(self, i2c_interface, address, port = 'BP', verbose=0):
        """
        Creates an object that interfaces the TMP421 I2C temperature sensor.
        Access is done through the I2C object 'i2c_interface' at I2C address 'address' and on port 'port'.
        The i2c interface must provide the following methods:
            set_port()
            write_read()
        """
        self.i2c = i2c_interface
        self.address = address
        self.port = port

    def init(self, ShutDown=1, Range=0, RemoteCor=0x00):
        """
        Initialization of TEMP421 I2C temperature sensor object
        ShutDown=1 shuts the temp measure circuitry down so that conversions only performed after writing to the one shot register
        Range=0  is the default -40 to 127 degC, Range =1 is -55 to 150degC
        Cor=1 applies resistance correction
        """
        self.write('CFG1', (ShutDown<<6) | (Range<<2) , mask=0b01000100) #Writing shutdown and rate
        self.write('CFG2', 1<<4 | 1<<3 | 1<<2 , mask=0b00011100) # Local and remote enabled , correction enabeled
        self.write('CORR', RemoteCor, mask=0xFF);

    def select(self):
        """
        Selects the proper I2C port to talk to this device.
        """
        self.i2c.select_bus(self.port)

    def write(self, register, value, mask = 0xff, select = True):
        """
        Writes a byte to the specified register of the TEMP100 I2C temperature sensor.
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
            old_value = self.i2c.write_read(self.address, data=[register],read_length=1)
            new_value = (old_value & (~ mask)) | (value & mask)
        else:
            new_value = value

        self.i2c.write_read(self.address, data=[register, new_value])

    def read(self, register, select = True, read_length=1):
        """
        Read a value to the specified register
        """
        # Convert port name a port address if the name is in the table. Otherwise use the argument as a port address directly.
        if register in self.REGISTER_TABLE:
            register = self.REGISTER_TABLE[register]

        if select:
            self.select()

        return self.i2c.write_read(self.address, data=[register], read_length=read_length)


    def get_temperature(self):
        """
        Reads temperature (in degrees Celcius) from TEMP register
        """

        self.write('ONESHOT', 0xFF, 0xFF)
        while self.read('STATUS',read_length=1)>>8: # while BUSY=1
            print 'BUSY=1...'
            pass

        local_temp_high = self.read('THIGH_LCL',read_length=1)[0]
        local_temp_low = self.read('TLOW_LCL',read_length=1)[0]
        remote_temp_high = self.read('THIGH_RMT',read_length=1)[0]
        remote_temp_low = self.read('TLOW_RMT',read_length=1)[0]

        local_temp=np.int8(local_temp_high) + float(np.uint8(local_temp_low)>>4)/16
        remote_temp=np.int8(remote_temp_high) + float(np.uint8(remote_temp_low)>>4)/16
        remote_fault = bool(remote_temp_low & 0b00000011)
        return local_temp, remote_temp, remote_fault