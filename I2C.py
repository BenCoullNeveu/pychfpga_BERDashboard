#!/usr/bin/python

"""
I2C.py module 
 Implements I2C interface of chFPGFA
#
# History:
# 2012-03-29 : JFC : Created from SPI.py
"""

import numpy as np
from util import  hex

from Module import Module_base, BitField

__reload__=True

class I2C_base(Module_base):
	# I2C addresses
	I2C_FMC_HPC_EPPROM_ADDR=0	# ADC. R/W device. 8 bit address+RW, 16 bit data.


	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS

	BITS={
		'START' :   BitField(CONTROL,0x04,7,doc='A 0 to 1 transition on this bit starts I2C transaction'),
		'BYTES' :   BitField(CONTROL,0x04,0,2,doc='Number of bytes in the I2C communication (excluding the address byte) 1=1 Byte, 1=2 bytes, 2=3 bytes'),

		'ACK_STATUS' : 	BitField(STATUS,0x080+ 0x05,0,8,doc='Ack bits'),
		'COLLISION':BitField(STATUS,0x080+ 0x04,3,doc='Indicates if the transaction experienced a collision'),
		'SCK' : 	BitField(STATUS,0x080+ 0x04,2,doc='State of the SCK line'),
		'SDA' : 	BitField(STATUS,0x080+ 0x04,1,doc='State of the SDA line'),
		'DONE' : 	BitField(STATUS,0x080+ 0x04,0,doc='High when I2C transaction is completed'),
	}



	def __init__(self,fpga):
		self.fpga_instance=fpga;
		super(self.__class__,self).__init__(fpga,fpga.SYSTEM_PORT, fpga.SYSTEM_I2C_MODULE)

	# def read_reg(self, addr, length=1,  type=np.uint8):
		# """ Reads from the SPI control register"""
		# fpga=self.fpga_instance; # use a shorter variable name to access the FPGA instance attributes
		# data=fpga.read(fpga.SYSTEM_PORT,fpga.SYSTEM_SPI_MODULE,addr, length=length, type=type)
		# return data
	# def write_reg(self, addr, data,  type=np.uint8):
		# """ Writes to the SPI control register"""
		# fpga=self.fpga_instance; # use a shorter variable name to access the FPGA instance attributes
		# length=fpga.Write(fpga.SYSTEM_PORT,fpga.SYSTEM_SPI_MODULE,addr,data);
		# return length

	def i2c_read(self, port=0, addr=0, length=1,  type=np.uint8, verbose=0):
		""" Serially reads 0-3 bytes  bytes long) from the I2C bus at the specified I2C address 
		"""
		if port<0 or port>1:
			print 'I2C_read: port number is out of range'
			return
		self.write(0x000+0x05,port<<4)
		self.write(0x000+0x00,[(addr<<1) | 0x01])
		self.write(0x000+0x04,[0x00+length, 0x80+length], incr=0)
		#self.write(0x000+0x04,[0x80+length+(port<<5)])
		self.wait_for_bit('DONE')
		data=self.read(0x080+0x00, length=4, type=np.uint8)
		ack=self.ACK_STATUS
		if ack!=2**(length+1)-1: # 
			print 'I2C_read communication error: did not receive correct ACK bits, addr=%i, ack=%i' % (addr,ack)
			#print 'I2C communication: ACK byte is %02x' % ack
#		read_length=np.dtype(type).itemsize
		data=data[-length:]
		data.dtype=np.dtype(type)
		return data

	def i2c_write(self, port=0, addr=0, data=[0], verbose=0):
		""" Serially writes 1-3 bytes to the specified I2C node 
		The written word must be padded so its total length covers the whole SPI transaction (read and write bits). 
		"""
		#print 'i2c write called with addr-%i, data=%i' % (addr,data[0])
		length=len(data)
		self.write(0x000+0x05,port<<4)
		self.write(0x000+0x00,[(addr<<1)+0x00]+data)
		self.write(0x000+0x04,[0x00+length, 0x80+length],incr=0)
		#self.write(0x000+0x04,[0x80+length+(port<<5)]) # start transaction
		self.wait_for_bit('DONE')
		ack=self.ACK_STATUS
		print 'I2C_write communication: ACK byte is 0x%02x' % ack
		
		if ack!=2**(length+1)-1:
			print 'I2C_write communication error: did not receive correct ACK bits'
			print 'I2C_write communication: ACK byte is 0x%02x' % ack
		return

	def i2c_reset(self, port=0, verbose=0):
		""" 
		"""
		self.write(0x000+0x05,[0x80+(port<<5)])
		self.write(0x000+0x05,[0x00+(port<<5)])

	def i2c_status(self, verbose=0):
		s=self.read(0x04,length=2)
		print 'Current selected port: %i' % (s[0]&0b01100000)>>6
		print 'Reset state: %i' % bool(s[1]&0x80)
		print 'Force line SCK: %i, SDA: %i' % (bool(s[1]&0x02),bool(s[1]&0x01))
		s=self.read(0x80,length=9)
		print 'Read bytes:', hex(s[0:4])
		print 'last state:', hex(s[4]>>4)
		print 'SCK = %i, SDA= %i' %(bool(s[4]&0x02), bool(s[4]&0x01))
		print 'ACK bits:', bin(s[5])
		
	
	def i2c_write_read(self, port=0, addr=0, data=[0], length=1, verbose=0):
		""" Serially writes 1-3 bytes to the specified I2C node, send a restart condition and reads 'length' (0-4) bytes. 
		The written word must be padded so its total length covers the whole SPI transaction (read and write bits). 
		"""
		#print 'i2c write called with addr-%i, data=%i' % (addr,data[0])
		write_length=len(data)
		self.write(0x000+0x05,port<<4)
		self.write(0x000+0x00,[(addr<<1)+0x00]+data)
		#self.write(0x000+0x04,[0x00])
		self.write(0x000+0x04,[0x00+(length<<4)+write_length, 0x80+(length<<4)+write_length],incr=0) # start transaction
		self.wait_for_bit('DONE')
		data=self.read(0x080+0x00, length=4, type=np.uint8)
		ack=self.ACK_STATUS
		if ack!=2**(length+write_length+2)-1:
			print 'I2C_write_read communication error: did not receive correct ACK bits'
		#print 'I2C communication: ACK byte is 0x%02x' % ack
		data=data[-length:]
		#data.dtype=np.dtype(type)
		return data

	def init(self):
		pass
