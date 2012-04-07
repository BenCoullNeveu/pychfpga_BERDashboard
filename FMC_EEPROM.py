#!/usr/bin/python

"""
FMC_EEPROM.py module 
 Implements the FMC EEPROM interface 
#
# History:
# 2012-03-29 : JFC : Created 
"""

import numpy as np


class FMC_EEPROM_base(object):
	# I2C addresses
	FMC_EPPROM_ADDR=0x50	# 0x50 and 0x51 are the two pages.
	FMC_EPPROM_PORT=0	# 

	def __init__(self,fpga,verbose=1):
		self.fpga_instance=fpga
		self.verbose=verbose

	def read(self,addr):
		""" Reads from the EEPROM"""
		i2c=self.fpga_instance.I2C

		#i2c.i2c_write(self.FMC_EPPROM_PORT,self.FMC_EPPROM_ADDR+((addr>>16)&1),[(addr>>8)&0xff, addr&0xff]) # sets the address
		#data=i2c.i2c_read(self.FMC_EPPROM_PORT, self.FMC_EPPROM_ADDR+((addr>>16)&1)) # reads a byte
		data=i2c.i2c_write_read(self.FMC_EPPROM_PORT, self.FMC_EPPROM_ADDR+((addr>>16)&1),[(addr>>8)&0xff, addr&0xff]) # reads a byte

		return data

	def write(self, addr,data):
		""" Writes to the EEPROM"""
		i2c=self.fpga_instance.I2C
		i2c.i2c_write(self.FMC_EPPROM_PORT,self.FMC_EPPROM_ADDR+((addr>>16)&1),[(addr>>8)&0xff, addr&0xff, data]) # sets the address

	def init(self):
		pass

	def read_DDR3_reg(self,addr):
		""" Reads from the EEPROM"""
		i2c=self.fpga_instance.I2C
		i2c_addr=0x1b
		i2c.i2c_write(0,i2c_addr,[addr]) # sets the address
		data=i2c.i2c_read(0,i2c_addr,length=2) # reads a byte
		return data

	PMBus_commands={
		'READ_VOUT': (0x8b,'LINEAR16'),
		'READ_VIN': (0x88,'LINEAR11'),
		'READ_IIN': (0x89,'LINEAR11'),		
		'READ_IOUT': (0x8C,'LINEAR11'),		
		'READ_PIN': (0x97,'LINEAR11'),		
		'READ_POUT': (0x96,'LINEAR11'),		
		#'READ_FREQUENCY': (0x95,'LINEAR11'),	# not supported	
		'READ_FAN_SPEED_1': (0x90,'LINEAR11'),		
		'READ_TEMPERATURE_1': (0x8D,'LINEAR11'),		
		'READ_TEMPERATURE_2': (0x8E,'LINEAR11'),		
		#'READ_TEMPERATURE_3': (0x8F,'LINEAR11'), # not supported		
		}
	PMBus_formats={
		'LINEAR16': (2,lambda x: float(x)*(2**-12)),
		'LINEAR11': (2,lambda x: float(x&0x7ff)*(2**(((x>>11)^0b10000)-16))),
	}
		
	def read_PMBus(self,controller,command,page=None,phase=None):
		""" Reads from the SMBus"""
		i2c=self.fpga_instance.I2C
		i2c_addr=52+controller
		i2c_port=1

		f=self.PMBus_commands[command]
		command_code=f[0]
		format=f[1]
		conversion_fn=self.PMBus_formats[format][1];
		length=self.PMBus_formats[format][0];

		if page is not None:
			i2c.i2c_write(i2c_port,i2c_addr,[0x00, page]) # sets the page
		if phase is not None:
			i2c.i2c_write(i2c_port,i2c_addr,[0x04, phase]) # sets the page
		
		data=i2c.i2c_write_read(i2c_port,i2c_addr,[command_code],length=length) # sets the command
		#data=i2c.i2c_read(1,i2c_addr,length=2) # reads two bytes
		if length==2:
			data.dtype=np.dtype('<u2'); # lsb is sent first
		data=data[0];
		print 'Raw value=',hex(data)
		val=conversion_fn(data)
		return val


