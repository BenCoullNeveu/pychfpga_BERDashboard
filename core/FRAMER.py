#!/usr/bin/python

"""
FRAMER.py module 
 Implements interface to the antenna FRAMER
#
# History:
# 2011-07-12 JFC : Created from test code in chFPGA.py
# 2012-05-29 JFC: Extracted from ANT.py
"""

import time
import numpy as np
from Module import Module_base, BitField


	
class FR_DIST_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""
	# Create local variables for page numbers tomake the table more readable
	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS

	# Register definition
	BITS={
		'ENABLE_RAMP' : 	BitField(CONTROL,0x00,6,doc='Enables transmission of a ramp. 0=inactive, 1=active'),
		'DUAL_FRAME': 		BitField(CONTROL,0x00,5,doc=" ** Obsolete ** When '1', allows buffering of two frames before it is transmitted."),
		'SYNC_RAMP': 		BitField(CONTROL,0x00,4,doc="When '1', synchronizes the ramp generator with the ADC data value. Must be set to zero for the ramp to increment naturallly. This might change the SYNC pulses spacing and will require resyncing or resseting the downstream modules"),
		'FIFO_RESET': 		BitField(CONTROL,0x00,3, doc="When '1', resets the data FIFO"),
		'TRIG_BURST': 		BitField(CONTROL,0x00,2, doc="When a 0 to 1 transition is detected, force transmission of 'BURST_LENGTH' data frame"),
		'DSP_DATA_SRC': 	BitField(CONTROL,0x00,0,2, doc="Selects the data source: 0=ADC, 1 = Injection FIFO, 2 = Ramp, 3= Zeros"),

		'BURST_LENGTH': 	BitField(CONTROL,0x01,0,8, doc="Sets the number of frame to transmit in a burst. 0= Continuous transmission, 1-255 = Trigerred transmission."),
		'SYNC_PERIOD': 		BitField(CONTROL,0x02,0,16, doc="Number of clock cycles between SYNC pulses. See CASPER documentation for minimum SYNC spacing."),
		'BURST_NUMBER': 	BitField(CONTROL,0x04,0,8, doc="Sets the number of bursts to transmit. 0-255, 0= Continuous transmission."),
		'BURST_PERIOD2': 	BitField(CONTROL,0x05,0,8, doc="8 bit MSB of number of frames between bursts"),
		'BURST_PERIOD1': 	BitField(CONTROL,0x06,0,8, doc="8 bit middle byte of Number of frames between bursts "),
		'BURST_PERIOD0': 	BitField(CONTROL,0x07,0,8, doc="8 bit LSB of number of frames between bursts"),

		'BURST_ACTIVE': 	BitField(STATUS,0x80,3, doc="Active high if a burst transmission is currently ongoing"),
		'RAMP_MISMATCH': 	BitField(STATUS,0x80,2, doc="Active high if the ramp value does not match the ADC value. used for testing the ADC data acquisition when the ADC is set in ramp generation mode"),
		'CTRL_FIFO_EMPTY': 	BitField(STATUS,0x80,1, doc="Active high  when the data FIFO is empty"),
		'CTRL_FIFO_OVERFLOW': BitField(STATUS,0x80,0, doc="Active high if the data FIFO is overflowing"),
		'CTRL_FIFO_LENGTH': BitField(STATUS,0x81,0,8, doc="Number of samples currently in the data FIFO (last 8 bits only)"),
		'TRIG_COUNT': 		BitField(STATUS,0x82,0,8, doc="Number trigger events received")
		}

	def __init__(self,ant_ch_instance):
		self.ant=ant_ch_instance
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.FR_DIST_MODULE)
		self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)
	# Specialized functions

	def reset_fifo(self):
		self.pulse_bit('FIFO_RESET')

	def set_burst(self,number_of_frames=1, number_of_bursts=1, period=1, source=None):
		"""
		Configure burst mode for tagging a number of frames for capture over the ethernet link.
			number_of_frames: number of contihuous frames to send in a burst (default=1)
			number_of_bursts: number of bursts of 'number_of_frames' frames to send (default=1)
			period: delay between bursts in seconds
			source: if specified, changes the data source to the specified source
		"""
		if source is not None:
			self.DSP_DATA_SRC=source # Data source 

		frame_period=1.0/850e6*self.ant.frame_length
		burst_period=int(period/frame_period)
		if burst_period<number_of_frames : burst_period=number_of_frames
		if burst_period>=2**24: 
			raise SystemError('Burst period is too long. maximum value is %.3f s' % (2**24*frame_period))
		self.BURST_PERIOD0=burst_period & 0xff
		self.BURST_PERIOD1=(burst_period >>8) & 0xff
		self.BURST_PERIOD2=(burst_period >>16) & 0xff
		self.BURST_LENGTH=number_of_frames
		self.BURST_NUMBER=number_of_bursts

	def trig_frame(self,number_of_frames=1, number_of_bursts=1, period=1, source=None):
		"""
		Triggers tagging a number of frames for transmission the ethernet link.
			number_of_frames: number of contihuous frames to send in a burst (default=1)
			number_of_bursts: number of bursts of 'number_of_frames' frames to send (default=1)
			period: delay between bursts in seconds
			source: if specified, changes the data source to the specified source
		"""
		self.set_burst(number_of_frames=number_of_frames, number_of_bursts=number_of_bursts, period=period, source=source)
		self.pulse_bit('TRIG_BURST')

	def inject_frame(self,length=None, data=None):


		self.DSP_DATA_SRC=1 # Data source = Data Injection FIFO
		self.pulse_bit('FIFO_RESET') # clear FIFO to make sure we do not sent data that was previously lingering in the FIFO

		if data==None: # Send ramp
			if length==None:
				length=self.ant.frame_length
			s=[(i % 256) for i in range(length)]
		else:
			if length==None:
				length=len(data)
			
			if type(data)==str :
				data_length=len(data);
				s=[ord(data[i % data_length]) for i in range(length)]
				#print 'Sending string:',s
			elif type(data)==np.ndarray or type(data)==list:
				data_length=len(data);
				data=np.uint8(data);
				s=[data[i % data_length] for i in range(length)]
				#print 'Sending string:',s
			elif type(data)==int:
				s=[data]*length
			else:
				print 'Data should be an integer, a list, or numpy array'
				
		self.write_ram(0x00, s,incr=0) # Write to FIFO


	def init(self, **kwargs):
		# Do nothing if the FMC is not present
		if not self.fpga.FMC_present:
			self.DSP_DATA_SRC=2 # use FRAMER-generated ramp if the ADC is not present
		else:
			self.DSP_DATA_SRC=0 # use the ADC data

	def status(self):
		print '-------------- ANT[%i].FRAMER STATUS --------------' % self.port_number 
		print ' Data source: %s' % ('ADC','Inject','Ramp','Zero')[self.DSP_DATA_SRC]
		print ' TRIG_COUNT=: %i' % self.TRIG_COUNT

