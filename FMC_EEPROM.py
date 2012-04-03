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

	def read_PMBus(self,command_code,length=2):
		""" Reads from the EEPROM"""
		i2c=self.fpga_instance.I2C
		i2c_addr=53
		i2c_port=1
		data=i2c.i2c_write_read(i2c_port,i2c_addr,[command_code],length=length) # sets the command
		#data=i2c.i2c_read(1,i2c_addr,length=2) # reads two bytes
		return data


