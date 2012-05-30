#!/usr/bin/python

"""
FreqCtr.py module 
 Implements the Frequency Counter interface

History:
	2011-07-13 : JFC : Created from test code in chFPGA.py
	2011-09-08 JFC: Added FMC_REFCLK
	2011-09-25 JFC: Added fan RPM readout
"""
import numpy as np

class FreqCtr_base(object):
	# Port definitions
	PORTS={
	'ADC_CLK0':0,
	'ADC_CLK1':1,
	'ADC_CLK2':2,
	'ADC_CLK3':3,
	'ADC_CLK4':4,
	'ADC_CLK5':5,
	'ADC_CLK6':6,
	'ADC_CLK7':7,
	'MGT_REFCLK':8,
	'MGT_USRCLK2':9,
	'FMC_REFCLK': 10,
	'CLK200':11,
	'CTRL_CLK':12,
	'FAN':13,
	'DSP_CLK':14,

	}



	# Registers

	def __init__(self,fpga,verbose=1):
		self.fpga_instance=fpga
		self.verbose=verbose

	def read(self,addr,type=np.uint8):
		""" Reads from the register of the frequency counter"""
		fpga=self.fpga_instance
		data=fpga.Read(fpga.SYSTEM_PORT,fpga.SYSTEM_FREQ_CTR_MODULE, addr,type)
		return data

	def write(self, addr,data):
		""" Writes to the register of the frequency counter"""
		fpga=self.fpga_instance
		fpga.Write(fpga.SYSTEM_PORT,fpga.SYSTEM_FREQ_CTR_MODULE, addr, data)

	def init(self):
		pass


	def read_frequency(self,port,gate_time=0.01):
		""" Reads the frequency (in Hz) of the specified frequency counter input port 
		"""
		ref_freq=200e6;
		gate_ctr=np.array([ref_freq*gate_time],np.dtype('>u4'))
		gate_ctr.dtype=np.uint8;
		#print gate_ctr
		self.write(0x00,gate_ctr); 

		if type(port) is str:
			port=self.PORTS[port]

		self.write(0x04,(port<<4)+0x00); # Reset frequency counter
		self.write(0x04,(port<<4)+0x01); # Start frequency counter
		while (self.read(0x84) & 0x01)==0: 
			pass
		freq=self.read(0x80,np.dtype('>u4'));
		return freq*2.0/gate_time

	def status(self):
		gate_time=0.05
		resolution=2.0/gate_time/1e6

		print 'System Frequencies:'
		print '   FPGA Board frequency:    %7.3f MHz' % (self.read_frequency('CLK200',gate_time=gate_time)/1e6) 
		print '   CTRL_CLK frequency:      %7.3f MHz' % (self.read_frequency('CTRL_CLK', gate_time=gate_time)/1e6) 
		print '   FMC Reference frequency: %7.3f MHz' % (self.read_frequency('FMC_REFCLK', gate_time=gate_time)/1e6) 
		print '   MGT Ref clock frequency: %7.3f MHz' % (self.read_frequency('MGT_REFCLK', gate_time=gate_time)/1e6) 
		print '   MGT word frequency:      %7.3f MHz' % (self.read_frequency('MGT_USRCLK2', gate_time=gate_time)/1e6) 
		for i in range(8):
			print '   ADC%i clock frequency:    %7.3f MHz' % (i,self.read_frequency('ADC_CLK%i' % i, gate_time=gate_time)/1e6) 
		print '   DSP_CLK frequency:      %7.3f MHz' % (self.read_frequency('DSP_CLK', gate_time=gate_time)/1e6) 
		print '   Resolution          :    %10.6f MHz' % (resolution) 
		print '   Gate time           :    %.3f s' % (gate_time) 
		print '   Fan speed:               %7.0f RPM (resolution %.0f RPM)' % (self.read_frequency('FAN', gate_time=gate_time)*60./2, resolution*1e6*60./2) # 1 Hz=60 RPM, divide by 2 because there is 2 pulses per fan turn  

		#for port_name in self.PORTS.keys():
		#	print '%s: %.3f MHz' % (port_name,self.read_frequency(port_name)/1e6) 
