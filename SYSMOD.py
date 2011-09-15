#!/usr/bin/python

"""
SYSMOD.py module 
 Implements SYSTEM-level interface
#
# History:
	2011-08-25 JFC : Created 
	2011-08-30 JFC: Added read_bitstream_* functions and status() 
	2011-09-08 JFC: Added TIMESTAMP_VALID and ADC_SYNC_READBACK in field definitions
	2011-09-14 JFC: Added USER_RESET bit to match firmware
"""

from Module import Module_base, BitDef

import numpy as np

class SYSMOD_base(Module_base):


	BITS={
		'GLOBAL_TRIG' : 	BitDef(0x00,7,doc='Global trigger'),
		'BUCK_SYNC_ENABLE' : BitDef(0x00,6,doc='Enable generation of the Buck SYNC signals'),
		'GLOBAL_RESET' : 		BitDef(0x00,5,doc='Resets the whole FPGA'),
		'ADC_SYNC' : 		BitDef(0x00,1,doc='ADC SYNC line. Common to both ADCs.'),
		'ADC_RESET' : 		BitDef(0x00,0,doc='ADC RESET line. Common to both ADCs.'),
		'BUCK_CLK_DIV' : 	BitDef(0x01,0,8,doc='Clock divider to set the BUCK SYNC frequency (2-255). Relative to the internal ADC word clock (200 MHz)'),

		'TIMESTAMP_VALID' : BitDef(0x080+ 0x00,7,doc='Timestamp data valid (i.e. can be read)'),
		'ADC_SYNC_READBACK' : BitDef(0x080+ 0x00,0,doc='Reads back the SYNC bit for debugging'),

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

	def read_bitstream_data(self):
		return self.read(0x80+0x07, type=np.dtype('>u4'))

	def read_bitstream_date(self):
		data=self.read_bitstream_data()
		sec=(data>>0) & 0x3F
		min=(data>>6) & 0x3F
		hour=(data>>12) & 0x1F
		year=(data>>17) & 0x3F
		month=(data>>23) & 0x0F
		day=(data>>27) & 0x1F
		str='%04i-%02i-%02i %02i:%02i:%02i' % (year+2000,month,day,hour,min,sec)
		return str



	def status(self):
		print '----------------------------------------------------------------------'
		print 'chFPGA Firmware version %i.%i, Build %i, Date: %04i-%02i-%02i' % (self.MAJOR_VERSION, self.MINOR_VERSION, self.BUILD_NUMBER, self.BUILD_YEAR+2000,self.BUILD_MONTH, self.BUILD_DAY)
		print 'Bistream timestamp is: %s' % self.read_bitstream_date()
		print '----------------------------------------------------------------------'


