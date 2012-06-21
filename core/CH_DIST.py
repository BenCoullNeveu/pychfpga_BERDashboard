#!/usr/bin/python

"""
CH_DIST.py module 
 Implements interface to the channel filter
#
# History:
# 2011-07-12 JFC : Created from test code in chFPGA.py
# 2012-05-29 JFC: Extracted frm ANT.py
"""
import time
import numpy as np
from Module import Module_base, BitField
	

class CH_DIST_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""
	# Create local variables for page numbers tomake the table more readable
	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS
	BITS={
		'RESET': 			BitField(CONTROL,0x00,7, doc="Reset the CH_DIST. Clears FIFO."),
		'FIFO_EMPTY': 		BitField(STATUS,0x80,7, doc="Active high when the data FIFO is empty"),
		'FIFO_OVERFLOW': 	BitField(STATUS,0x80,6, doc="Active high if the data FIFO is overflowing"),
		'FRAME_VALID_CTR': 	BitField(STATUS,0x80,0,6, doc="Number of valid frames seen since last reset")
		}

	def __init__(self,corr_instance):
		self.corr=corr_instance
		super(self.__class__,self).__init__(corr_instance.fpga,corr_instance.corr_number, corr_instance.CH_DIST_MODULE)

	def reset(self):
		self.RESET=1
		self.RESET=0

	def select_words(self,words_to_enable=1024/4):
		"""
		Selects which words* are going to be transmitted at the output of the antenna processing pipeline.
		If 'pattern' is an integer, words 0 to (pattern-1) are transmitted.
		If pattern is an array, the word numbers indicated in the arrays are transmitted.
		* NOTE: a word is 4 bytes. If the FFT is bypassed, each word contains 4 8-bit ADC samples. 
			If the FFT is enabled, each word contains 2 complex values, one for the even and odd frequency bin. Each complex value is two 8-bit values (real and imaginary)
		"""
		# Initialize filter mask (8 flags per word)
		mask=np.zeros(self.corr.fpga.FRAME_LENGTH/4/8, np.uint8)

		if isinstance(words_to_enable, int):
			words_to_enable=range(words_to_enable)

		# Set the bits in mask
		for j in words_to_enable:
			#print 'setting bit %i of byte %i' % ((j % 8), j//8)
			mask[j//8] |= (1<<(j % 8))

		self.write_ram(0x00,mask); # Enable transmission of selected bytes 

	def init(self):
		self.select_words(self.corr.fpga.FRAME_LENGTH//4) # enable tranmission of all words by default

	def status(self):
		print '-------------- CORR[%i].CH_DIST STATUS --------------' % (self.port_number)
		print '   RESET: %i' % self.RESET
		print '   FIFO EMPTY: %i' % self.FIFO_EMPTY
		print '   FIFO OVERFLOW: %i' % self.FIFO_OVERFLOW
		print '   VALID FRAME CTR: %i' % self.FRAME_VALID_CTR


