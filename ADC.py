#!/usr/bin/python

"""
ADC.py module 
 Implements interface to ADC on the ADC FMC
#
# History:
# 2011-07-07 : JFC : Created from test code in chFPGA.py
	2011-09-29 JFC: Added set_test_mode()

"""

import numpy as np

class ADC_chip(object):
	# ADC-related constants
	REG_CHIP_ID=0x00
	REG_CONTROL=0x01
	REG_STATUS=0x02
	REG_SWRESET=0x04
	REG_TEST=0x05
	REG_SYNC=0x06
	REG_CHANNEL_SELECT=0x0F
	REG_CH_CAL_CTRL=0x10
	REG_CH_CAL_CTRL_MLBX=0x11
	REG_CH_STATUS=0x12

	def __init__(self,adc_instance,adc_number):
		#super(ADC_chip,self).__init__(fpga)
		self.adc=adc_instance # store current ADC number for this instance
		self.adc_number=adc_number # store current ADC number for this instance
		
	def read(self,addr): 
		return self.adc.read(self.adc_number,addr)

	def write(self,addr,value): 
		return self.adc.write(self.adc_number,addr,value)


	def init(self, test_mode=0):
		# CONTROL Register
		ADC_MODE=0 # 0-15, 0=4-channel mode
		STDBY=0 # 0-3, 0=Full active, 3=Full standby
		DMUX_RATIO=1; # 0=DMUX2:1, 1=DMUX1:1
		BG=0 # 0=Binary, 1=Gray code
		BDW=0 # 0-3, 0= 500 MHz, 1=600 MHz, 2=1.5 GHz, 3=2 GHz
		FS=0 # 0=500 mV full scale, 1=625 mV full scale
		TEST=bool(test_mode) # 0=No test mode, 1=test mode activated

		REG_CONTROL_Value=np.uint32((TEST<<12)+(FS<<10)+(BDW<<8)+(BG<<7)+(DMUX_RATIO<<6)+(STDBY<<4)+ADC_MODE)
		REG_TEST_Value=(0,0,1)[test_mode] # Select test pattern: test=0: no test mode, test=1:ramp, test=2: flashing 0xff
		REG_SYNC_Value=0x08 #0-15
		self.write(self.REG_CONTROL,REG_CONTROL_Value)
		self.write(self.REG_TEST, REG_TEST_Value) 
		self.write(self.REG_SYNC, REG_SYNC_Value) 

	channel=property(lambda s: s.read(s.REG_CHANNEL_SELECT), lambda s,value: s.write(s.REG_CHANNEL_SELECT,value));
	chip_id=property(lambda s: s.read(s.REG_CHIP_ID), lambda s,value: s.write(s.REG_CHIP_ID,value));
	temperature=property(lambda s: s.adc.temperature(s.adc_number));





class ADC_base(object):

	def __init__(self,fpga,verbose=0):
		self.fpga_instance=fpga
		self.verbose=verbose
		# Create an instance of ADC_chip for each chip of the FMC board
		self.ADC=[]
		for i in range(2):
			self.ADC.append(ADC_chip(self,i))

	def __getitem__(self,key):
		# if the user indexes this object (ADC[n] instead of ADC) then return the chip instance
		return self.ADC[key]

	# Low-level access functions

	def read(self,adc_number,addr):
		spi=self.fpga_instance.SPI; # use a shorter variable name to access the FPGA instance attributes
		data=spi.read_write(spi.SPI_ADC0_ADDR+adc_number, data=[0x00+addr,0x00,0x00], type=np.dtype('>u2'))
		return data

	def write(self,adc_number,addr=0,data=0):
		spi=self.fpga_instance.SPI; # use a shorter variable name to access the FPGA instance attributes
		spi.read_write(spi.SPI_ADC0_ADDR+adc_number, data=[0x80+addr,data>>8,data&0xFF])

	# High level functions
	def temperature(self, adc_number):
		"""Reads the external temperature sensor connected to the sensing diode in the specified ADC chip"""

		spi=self.fpga_instance.SPI; # use a shorter variable name to access the FPGA instance attributes
		data= spi.read_write(spi.SPI_ADC0_TEMP_ADDR+adc_number, [0,0], type=np.dtype('>u2'));
		temp= (data>>3)/16.0;
		if self.verbose:
			print 'ADC%i Temperature is %.2f C (raw data=0x%04x)' % (adc_number,temp,data)
		return temp #110918 JFC

	# Class functions (applies to all ADCs)
	def reset(self):
		""" Resets both ADCs"""
		sysmod=self.fpga_instance.SYSMOD; # use a shorter variable name to access the FPGA instance attributes
		sysmod.pulse_bit('ADC_RESET')

	def sync(self):
		""" Resyncs both ADCs"""
		#sysmod=self.fpga_instance.SYSMOD; # use a shorter variable name to access the FPGA instance attributes
		#sysmod.pulse_bit('ADC_SYNC')

		refclk=self.fpga_instance.REFCLK; # use a shorter variable name to access the FPGA instance attributes
		refclk.local_sync()

	def init(self,test_mode=0):
		self.reset() # Send reset pulse on both ADCs
		for adc in self.ADC:
			adc.init(test_mode)
			adc.channel=0
		#self.sync() # Send sync pulse -- reates problems. to be debugged.

	def set_test_mode(self,test_mode=0):
		REG_TEST_Value=(0,0,1)[test_mode] # Select test pattern: test=0: no test mode, test=1:ramp, test=2: flashing 0xff
		for adc in self.ADC:
			adc.write(adc.REG_TEST, REG_TEST_Value) 
		self.sync();
