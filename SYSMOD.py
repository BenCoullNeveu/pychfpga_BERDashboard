#!/usr/bin/python

"""
SYSMOD.py module 
 Implements SYSTEM-level interface
#
# History:
# 2011-08-25 : JFC : Created 
"""

from Module import Module_base, BitDef

import numpy as np

class SYSMOD_base(Module_base):


	BITS={
		'GLOBAL_TRIG' : 	BitDef(0x00,7,doc='Global trigger'),
		'BUCK_SYNC_ENABLE' : BitDef(0x00,6,doc='Enable generation of the Buck SYNC signals'),
		'ADC_SYNC' : 		BitDef(0x00,1,doc='ADC SYNC line. Common to both ADCs.'),
		'ADC_RESET' : 		BitDef(0x00,0,doc='ADC RESET line. Common to both ADCs.'),
		'BUCK_CLK_DIV' : 	BitDef(0x01,0,8,doc='Clock divider to set the BUCK SYNC frequency (2-255). Relative to the internal ADC word clock (200 MHz)'),

		'MAJOR_VERSION' : 	BitDef(0x080+ 0x01,0,8,doc='Major revision number of the firmware'),
		'MINOR_VERSION' : 	BitDef(0x080+ 0x02,0,8,doc='Minor revision number of the firmware'),
		'BUILD_NUMBER' : 	BitDef(0x080+ 0x03,0,8,doc='Build number of the firmware'),
		'BUILD_YEAR' : 		BitDef(0x080+ 0x04,0,8,doc='Build year of the firmware'),
		'BUILD_MONTH' : 	BitDef(0x080+ 0x05,0,8,doc='Build month of the firmware'),
		'BUILD_DAY' : 		BitDef(0x080+ 0x06,0,8,doc='Build day of the firmware'),
	}


	def __init__(self,fpga):
		super(self.__class__,self).__init__(fpga,fpga.SYSTEM_PORT, fpga.SYSTEM_SYSMOD_MODULE)

	def init(self):
		pass

	def status(self):
		print '----------------------------------------------------------------------'
		print 'chFPGA Firmware version %i.%i, Build %i, Date: %04i-%02i-%02i' % (self.MAJOR_VERSION, self.MINOR_VERSION, self.BUILD_NUMBER, self.BUILD_YEAR+2000,self.BUILD_MONTH, self.BUILD_DAY)
		print '----------------------------------------------------------------------'


