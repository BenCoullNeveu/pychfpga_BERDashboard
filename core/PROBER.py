#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
PROBER.py module 
 Implements interface to a data PROBER

 History:
 2012-06-21 JFC: Created
"""

import time
import numpy as np
from Module import Module_base, BitField


	
class PROBER_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""
	# Create local variables for page numbers tomake the table more readable
	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS

	# Register definition
	BITS={
		#'RESET': 			BitField(CONTROL, 0x00, 7, doc="Resets the module (including the FIFO)"),
		'FIFO_RESET': 		BitField(CONTROL, 0x00, 6, doc="When '1', resets the data FIFO"),

		'BURST_LENGTH': 	BitField(CONTROL, 0x01, 0, 8, doc="Sets the number of frame to transmit in a burst. 0= Continuous transmission, 1-255 = Trigerred transmission."),
		'BURST_PERIOD2': 	BitField(CONTROL, 0x02, 0, 8, doc="8 bit MSB of number of frames between bursts"),
		'BURST_PERIOD1': 	BitField(CONTROL, 0x03, 0, 8, doc="8 bit middle byte of Number of frames between bursts "),
		'BURST_PERIOD0': 	BitField(CONTROL, 0x04, 0, 8, doc="8 bit LSB of number of frames between bursts"),
		'BURST_NUMBER': 	BitField(CONTROL, 0x05, 0, 8, doc="Sets the number of bursts to transmit. 0-255, 0= Continuous transmission."),
		'PROBE_ID': 		BitField(CONTROL, 0x05, 0, 8, doc="Arbitrary 8-bit number that shows in the header of the transmitted frames to identify the source"),

		'CAPTURE_ACTIVE': 	BitField(STATUS,0x80, 0, doc="Active high if data capture is in progress (cleared when BURST_NUMBER bursts have been sent)"),
		}
	
	def __init__(self,ant_ch_instance):
		self.ant=ant_ch_instance
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.FR_DIST_MODULE)
		self.RESET = bitfield_property(CONTROL, 0x00, 7, doc="Resets the module (including the FIFO)")
		self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)
	# Specialized functions

	def reset(self):
		""" Resets the module"""
		self.pulse_bit('RESET')

	def reset_fifo(self):
		""" Clears the data FIFO"""
		self.pulse_bit('FIFO_RESET')

	def set_burst_period(self, burst_period):
		""" Sets the interval between data capture bursts. The period is specified in number of frames. This method is used because the property does not yet handle multi-byte values well."""
		self.BURST_PERIOD0 = burst_period & 0xff
		self.BURST_PERIOD1 = (burst_period >>8) & 0xff
		self.BURST_PERIOD2 = (burst_period >>16) & 0xff

	def get_burst_period(self):
		""" Returns the interval between data capture bursts. The period is specified in number of frames. This method is used because the property does not yet handle multi-byte values well."""
		return self.BURST_PERIOD0 + (self.BURST_PERIOD1 << 8) + (self.BURST_PERIOD2 <<16)

	def config_capture(self,frames_per_burst=1, burst_period=100, number_of_bursts=0):
		"""
		Configure the capture of data frames for transmisssion over the ethernet link.
			frames_per_burst: number of contihuous frames to send in a burst (default=1)
			burst_period: delay between bursts in seconds
			number_of_bursts: number of bursts to send. '0' means that bursts are sent continuously as long as frames are tagged for capture at the source . Default is '0'.
		"""

		#frame_period=1.0/850e6*self.ant.frame_length
		#burst_period=int(period/frame_period)
		if burst_period<frames_per_burst : burst_period = frames_per_burst
		if burst_period>=2**24: 
			raise SystemError('Burst period of %i frames is too long. Maximum value is %.3f s' % (burst_period, 2**24-1))
		self.BURST_LENGTH = frames_per_burst
		self.set_burst_period(burst_period)
		self.BURST_NUMBER = number_of_bursts


	def init(self, **kwargs):
		""" Initialize the data capture module"""
		self.config_capture(1, 100) # Capture 1 frame every 100 frames

	def status(self):
		print '-------------- ANT[%i] data capture --------------' % self.port_number 
		print ' Capture %i frames every %i frames' % (self.BURST_LENGTH, self.get_burst_period()), 
		if self.BURST_NUMBER:
			print ' for %i bursts' % self.BURST_NUMBER
		else:
			print ' continuously while the frames are tagged for capture at the source'

