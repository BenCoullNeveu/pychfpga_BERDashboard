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

	def __init__(self,fpga,adc_number):
		#super(ADC_chip,self).__init__(fpga)
		self.adc=fpga # store current ADC number for this instance
		self.adc_number=adc_number # store current ADC number for this instance
		
	def read(self,addr): 
		return self.adc.read(self.adc_number,addr)

	def write(self,addr,value): 
		return self.adc.write(self.adc_number,addr,value)

	def init(self,adc_mode=0, standby_mode=0, dmux=False, gray_code=False, bandwidth=2, full_scale=0, test_mode=0, sync_delay=0x08): 
		"""
		Writes the control and test register of the ADC
			adc_mode (0-15, default=0=4 channel mode): selects between 1,2 and 4 channel mode and which analog input is used
			standby_mode (0-3, default=0 full active): selects the active mode. 0=Full active, 3=full standby
			dmux (bool, default=false): selects whether the 2:1 DMUX mode is selected
			gray_code (bool, default=False): selects if output is in binary (false) or gray code (True)
			bandwidth (0-3, default=2), selects the analog bandwiddth of the ADC: 0= 500 MHz, 1=600 MHz, 2=1.5 GHz, 3=2 GHz
			full_scale (0-1, default=0), selects the full scale peak-to-peak voltage: 0=500 mV full scale, 1=625 mV full scale
			test_mode (0-2, default=0): test mode of the ADC: 0= Normal operation, 1=ramp, 2= 00/FF pulse
			sync_delay (0-15, default=8): Number of clocks to hold off the data clock after a SYNC event
		"""


		ADC_MODE=adc_mode # 0-15, 0=4-channel mode
		STDBY=standby_mode # 0-3, 0=Full active, 3=Full standby
		DMUX_RATIO=not dmux; # 0=DMUX2:1, 1=DMUX1:1
		BG=gray_code # 0=Binary, 1=Gray code
		BDW=bandwidth # 0-3, 0= 500 MHz, 1=600 MHz, 2=1.5 GHz, 3=2 GHz
		FS=full_scale # 0=500 mV full scale, 1=625 mV full scale
		TEST=bool(test_mode) # 0=No test mode, 1=test mode activated

		REG_CONTROL_Value=np.uint32((TEST<<12)+(FS<<10)+(BDW<<8)+(BG<<7)+(DMUX_RATIO<<6)+(STDBY<<4)+ADC_MODE)
		REG_TEST_Value=(0,0,1)[test_mode] # Select test pattern: test=0: no test mode, test=1:ramp, test=2: flashing 0xff
		REG_SYNC_Value=sync_delay #0-15

		self.write(self.REG_CONTROL,REG_CONTROL_Value)
		self.write(self.REG_TEST, REG_TEST_Value) 
		self.write(self.REG_SYNC, REG_SYNC_Value) 

 
	channel=property(lambda s: s.read(s.REG_CHANNEL_SELECT), lambda s,value: s.write(s.REG_CHANNEL_SELECT,value));
	chip_id=property(lambda s: s.read(s.REG_CHIP_ID), lambda s,value: s.write(s.REG_CHIP_ID,value));
	temperature=property(lambda s: s.adc.temperature(s.adc_number));

	def status(self):
		print '  ----ADC[%i]------------' % self.adc_number
		w=self.read(self.REG_CHIP_ID)
		print '  ADC Chip ID:'
		print '    Chip type: 0x%x' % (w>>8)
		print '    Version: %i.%i' % ( ((w>>2)&0x03), (w&0x03) )
		print '    Branch: %i' % ((w>>4)&0x0F)
		print '  ADC test mode active: %s' % bool(self.read(self.REG_CONTROL) & 0x1000)
		print '  ADC test mode: %i' % self.read(self.REG_TEST)




class ADC_base(object):

	def __init__(self,fpga,verbose=0):
		self.fpga=fpga
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
		spi=self.fpga.SPI; # use a shorter variable name to access the FPGA instance attributes
		data=spi.read_write(spi.SPI_ADC0_ADDR+adc_number, data=[0x00+addr,0x00,0x00], type=np.dtype('>u2'))
		return data

	def write(self,adc_number,addr=0,data=0):
		spi=self.fpga.SPI; # use a shorter variable name to access the FPGA instance attributes
		spi.read_write(spi.SPI_ADC0_ADDR+adc_number, data=[0x80+addr,data>>8,data&0xFF])

	# High level functions
	def temperature(self, adc_number,verbose):
		"""Reads the external temperature sensor connected to the sensing diode in the specified ADC chip"""

		spi=self.fpga.SPI; # use a shorter variable name to access the FPGA instance attributes
		data= spi.read_write(spi.SPI_ADC0_TEMP_ADDR+adc_number, [0,0], type=np.dtype('>u2'));
		temp= (data>>3)/16.0;
		if self.verbose or verbose:
			print 'ADC%i Temperature is %.2f C (raw data=0x%04x)' % (adc_number,temp,data)
		return temp #110918 JFC

	# Class functions (applies to all ADCs)
	def reset(self):
		""" Resets both ADCs"""
		sysmod=self.fpga.SYSMOD; # use a shorter variable name to access the FPGA instance attributes
		sysmod.pulse_bit('ADC_RESET')

	def sync(self):
		""" Resyncs both ADCs"""
		#sysmod=self.fpga.SYSMOD; # use a shorter variable name to access the FPGA instance attributes
		#sysmod.pulse_bit('ADC_SYNC')

		refclk=self.fpga.REFCLK; # use a shorter variable name to access the FPGA instance attributes
		refclk.local_sync()

	def init(self, **kwargs):
		# Do nothing if the FMC is not present
		if not self.fpga.FMC_present:
			return

		self.reset() # Send reset pulse on both ADCs
		for adc in self.ADC:
			adc.init(**kwargs)
			adc.channel=0
		#self.sync() # Send sync pulse -- creates problems. to be debugged.

	def set_test_mode(self,**kwargs):
		for adc in self.ADC:
			adc.init(**kwargs)
		self.sync();


	def status(self):
		print '---------------------FMC ADC------------------------------------'
		if not self.fpga.FMC_present:
			print 'FMC board not present'
			return
		for adc in self.ADC:
			adc.status()
		print '----------------------------------------------------------------------'
