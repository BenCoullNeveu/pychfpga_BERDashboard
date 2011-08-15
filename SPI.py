#!/usr/bin/python

"""
SPI.py module 
 Implements SPI interface of chFPGFA
#
# History:
# 2011-07-07 : JFC : Created from test code in chFPGA.py
# 2011-07-13 JFC: added read_reg() and write_reg() to make code more manageable and reader-friendly
"""

import numpy as np
__reload__=True

class SPI_base(object):
	# SPI addresses
	SPI_ADC0_ADDR=0	# ADC. R/W device. 8 bit address+RW, 16 bit data.
	SPI_ADC1_ADDR=1 # ADC. R/W device. 8 bit address+RW, 16 bit data.
	SPI_ADC0_TEMP_ADDR=2 # ADC temperature sensor chip. Read only
	SPI_ADC1_TEMP_ADDR=3 # ADC temperature sensor chip. Read only
	SPI_AMB_TEMP_ADDR=4 # Board temperature sensor chip. Read/Write device
	SPI_ADC_BIAS_ADDR=5 # Bias measurement ADC.  Read/Write device
	SPI_IO_EXP_ADDR=6 # IO Expander. Read/Write device
	SPI_PLL2_ADDR=7 # GBT PLL. Write only.
	SPI_PLL1_ADDR=10 # ADC PLL. One of the other devices is enabled while we write to the PLL, so that default device must be read only.

	def __init__(self,fpga):
		self.fpga_instance=fpga;

	def read_reg(self, addr, length=1,  type=np.uint8):
		""" Reads from the SPI control register"""
		fpga=self.fpga_instance; # use a shorter variable name to access the FPGA instance attributes
		data=fpga.Read(fpga.SYSTEM_PORT,fpga.SYSTEM_SPI_MODULE,addr, length=length, type=type)
		return data
	def write_reg(self, addr, data,  type=np.uint8):
		""" Writes to the SPI control register"""
		fpga=self.fpga_instance; # use a shorter variable name to access the FPGA instance attributes
		length=fpga.Write(fpga.SYSTEM_PORT,fpga.SYSTEM_SPI_MODULE,addr,data);
		return length

	def read_write(self, device=2, data=[0x00,0x00,0x00,0x00],  type=np.uint8, verbose=0):
		""" Serially writes a word (1-4 bytes long) to the specified device on the SPI bus while reading serial data put the bus at the same time
		The written word must be padded so its total length covers the whole SPI transaction (read and write bits). 
		"""
		word_length=self.write_reg(0x000+0x00,data);
		self.write_reg(0x000+0x04,[0x00+(device<<4)+(word_length-1)]);
		self.write_reg(0x000+0x04,[0x04+(device<<4)+(word_length-1)]);
		while not self.read_reg(0x080+0x04)&0x01: 
			if verbose:
				print '.',
		data=self.read_reg(0x080+0x00, length=word_length, type=np.uint8)
		read_length=np.dtype(type).itemsize
		data=data[-read_length:]
		data.dtype=np.dtype(type)
		return data[0]

	def init(self):
		DEFAULT_ADDR=2 # Default SPI_ADDR<2:0> when not accessing the SPI devices or interfacing devices with addresses >=8

		REG5_VALUE=(DEFAULT_ADDR<<4)
		self.write_reg(0x000+0x05,REG5_VALUE)


