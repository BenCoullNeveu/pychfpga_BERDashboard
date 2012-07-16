#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
FRAMER.py module 
 Implements interface to the antenna FRAMER
#
# History:
# 2011-07-12 JFC : Created from test code in chFPGA.py
# 2012-05-29 JFC: Extracted from ANT.py
"""

import numpy as np
from Module import Module_base, BitField


	
class FR_DIST_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""
	# Create local variables for page numbers tomake the table more readable
	CONTROL = BitField.CONTROL
	STATUS = BitField.STATUS

	DATA_SOURCE_NAMES = {
		'zero' : 0, # All bytes are zero
		'one' : 1, # All bytes are one
		'ramp' : 2, # Successive bytes generate a repeating ramp from 0 to 255
		'real_ramp' : 3, # Generates a complex ramp from 0+0i to 255+0i on each successive (8+8) bits complex values (the imaginary part is always zero). 
		'unused' : 4, # Not defined yet
		'prbs' : 5, # Not defined yet. reserfed for a future noise generator
		'fifo' : 6, # Takes the data from the data injection FIFO
		'adcdaq' : 7, # takes the data from the ADCDAQ
		}	
	
	# Register definition
	BITS = {
		'RESET' : 		BitField(CONTROL, 0x00 ,7, doc='Resets this module'),
		'FIFO_RESET': 		BitField(CONTROL, 0x00, 6, doc="When '1', resets the data FIFO"),
		'CAPTURE_FLAG':	BitField(CONTROL, 0x00, 5, doc="When '1', forces the CAPURE flag of the outgoing frames to be '1'. Could be used downstream."),
		'DATA_SOURCE':		BitField(CONTROL, 0x00, 0,3, doc="Selects the Antenna processing block data source"),

		'SYNC_PERIOD': 	BitField(CONTROL, 0x02, 0,16, doc="Number of clock cycles between SYNC pulses. See CASPER documentation for minimum SYNC spacing."),

		'FIFO_OVERFLOW': 	BitField(STATUS, 0x00, 0, doc="Active high if the data FIFO is overflowing"),
		'FIFO_EMPTY': 		BitField(STATUS, 0x00, 1, doc="Active high  when the data FIFO is empty"),
		'FIFO_LENGTH': BitField(STATUS, 0x01, 0, 8, doc="Number of samples currently in the data FIFO (last 8 bits only)"),
		'RAMP_CTR': BitField(STATUS, 0x02, 0, width=8, doc="Last 8 bits of the ramp counter (for debuging)"),
		}

	def __init__(self, ant_ch_instance):
		self.ant = ant_ch_instance
		super(self.__class__, self).__init__(ant_ch_instance.fpga, ant_ch_instance.ant_number, ant_ch_instance.FR_DIST_MODULE)
		self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)
	# Specialized functions

	def reset_fifo(self):
		""" Resets the data injection FIFO"""
		self.pulse_bit('FIFO_RESET')

#	def start_frame_transmission(self, number_of_frames=1, number_of_bursts=1, period=1, source=None):
#		"""
#		Triggers tagging a number of frames for transmission the ethernet link.
#			number_of_frames: number of contihuous frames to send in a burst (default=1)
#			number_of_bursts: number of bursts of 'number_of_frames' frames to send (default=1)
#			period: delay between bursts in seconds
#			source: if specified, changes the data source to the specified source
#		"""
#		self.set_burst(number_of_frames=number_of_frames, number_of_bursts=number_of_bursts, period=period, source=source)
#		self.pulse_bit('TRIG_BURST')

	def inject_frame(self, length=None, data=None):
		""" Inject a frame of data in the antenna processing pipeline"""

		#self.DSP_DATA_SRC = 1 # Data source = Data Injection FIFO
		#self.pulse_bit('FIFO_RESET') # clear FIFO to make sure we do not sent data that was previously lingering in the FIFO

		if data == None: # Send ramp
			if length == None:
				length = self.ant.frame_length
			frame = [(i % 256) for i in range(length)]
		else:
			if length == None:
				length = len(data)
			
			if type(data) == str :
				data_length = len(data)
				frame = [ord(data[i % data_length]) for i in range(length)]
				#print 'Sending string:',s
			elif isinstance(data, np.ndarray) or isinstance(data, list):
				data_length = len(data)
				data = np.uint8(data)
				frame = [data[i % data_length] for i in range(length)]
				#print 'Sending string:',s
			elif type(data) == int:
				frame = [data]*length
			else:
				print 'Data should be an integer, a list, or numpy array'
				
		self.write_ram(0x00, frame, incr=0) # Write to FIFO


	def init(self):
		""" Initializes the antenna processing chain data source module """
		# Do nothing if the FMC is not present
		if not self.fpga.FMC_present:
			self.DATA_SOURCE = self.DATA_SOURCE_NAMES['ramp'] # use FRAMER-generated ramp if the ADC is not present
		else:
			self.DATA_SOURCE = self.DATA_SOURCE_NAMES['adcdaq'] # use the ADC data

	def status(self):
		""" Displays the status of the antenna processing chain data source module """
		print '-------------- ANT[%i].FRAMER STATUS --------------' % self.port_number 
		print ' Data source: %i' % self.DATA_SOURCE

