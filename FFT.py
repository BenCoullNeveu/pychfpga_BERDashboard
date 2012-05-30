#!/usr/bin/python

"""
FFT.py module 
 Implements interface to the FFT or PFB
#
# History:
# 2011-07-12 : JFC : Created from test code in chFPGA.py
# 2012-05-29 JFC: Extracted frm ANT.py
"""
import time
import numpy as np
from Module import Module_base, BitField

	

class DSP_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""
	# Create local variables for page numbers tomake the table more readable
	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS
	BITS={
		'BYPASS': 		BitField(CONTROL,0x00,0, doc="Bypass the FFT"),
		'RESET_SYNC': 	BitField(CONTROL,0x00,1, doc="Reset the SYNC Module. Force it to re-learn the DSP block latency."),
		'OUT_SHIFT': 	BitField(CONTROL,0x01,4,4, doc="Number of bits to right-shift thr FFT data"),
		'FFT_SHIFT': 	BitField(CONTROL,0x02,0,10, doc="FFT shift enable bit for each of the FFT stage"),
		}

	def __init__(self,ant_ch_instance):
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.DSP_MODULE)
		
	def reset_sync(self):
		self.pulse_bit('RESET_SYNC')

	def status(self):
		print '-------------- ANT[%i].FFT STATUS --------------' % self.port_number 
		print ' No status info'