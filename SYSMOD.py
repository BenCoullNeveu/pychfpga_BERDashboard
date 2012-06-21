#!/usr/bin/python

"""
SYSMOD.py module 
 Implements SYSTEM-level interface
#
# History:
	2011-08-25 JFC : Created 
	2011-08-30 JFC: Added read_bitstream_* functions and status() 
	2011-09-08 JFC: Added TIMESTAMP_VALID and ADC_SYNC_READBACK in field definitions
	2011-09-14 JFC: Added GLOBAL_RESET bit to match firmware
	2011-09-16 JFC: Added functions to pulse GLOBAL TRIG and GLOBAL RESET
	2011-09-19 JFC: Added ADC_DAQ_SYNC and FR_DIST_SYNC properties
	2011-09-27 JFC: Split ADC_DAQ_SYNC into ADC_DAQ_BUFR_SYNC and ADC_DAQ_SERDES_SYNC 
"""

from Module import Module_base, BitField

import time
import numpy as np

class SYSMOD_base(Module_base):

	# Create local variables for page numbers tomake the table more readable
	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS

	BITS={
		'GLOBAL_TRIG' : 	BitField(CONTROL,0x00,7,doc='Global trigger'),
		'BUCK_SYNC_ENABLE':	BitField(CONTROL,0x00,6,doc='Enable generation of the Buck SYNC signals'),
		'GLOBAL_RESET' : 	BitField(CONTROL,0x00,5,doc='Resets the whole FPGA'),
		'ADC_DAQ_BUFR_SYNC' : 	BitField(CONTROL,0x00,4,doc='ADC_DAQ SYNC line. Common to all ADC_DAQs.'),
		'ADC_DAQ_SERDES_SYNC' : BitField(CONTROL,0x00,3,doc='ADC_DAQ SYNC line. Common to all ADC_DAQs.'),
		'FR_DIST_SYNC' : 	BitField(CONTROL,0x00,2,doc='FR_DIST line. Common to all FR_DISTs.'),
		'ADC_SYNC' : 		BitField(CONTROL,0x00,1,doc='ADC SYNC line. Common to both ADCs.'),
		'ADC_RESET' : 		BitField(CONTROL,0x00,0,doc='ADC RESET line. Common to both ADCs.'),

		'BUCK_CLK_DIV' : 	BitField(CONTROL,0x01,0,8,doc='Clock divider to set the BUCK SYNC frequency (2-255). Relative to the internal ADC word clock (200 MHz)'),

		'LCD_E' : 			BitField(CONTROL,0x02,7,doc='LCD Enable'),
		'LCD_RS' : 			BitField(CONTROL,0x02,6,doc='LCD RS (0=command, 1=data)'),
		'LCD_RW' : 			BitField(CONTROL,0x02,5,doc='LCD Read/Write flag (0=write, 1=read)'),
		'LCD_DATA' : 		BitField(CONTROL,0x02,0,4,doc='LCD 4-bit data bus'),

		'TIMESTAMP_VALID' : BitField(STATUS,0x080+ 0x00,7,doc='Timestamp data valid (i.e. can be read)'),
		'ADC_SYNC_READBACK' : BitField(STATUS,0x080+ 0x00,0,doc='Reads back the SYNC bit for debugging'),

		'MAJOR_VERSION' : 	BitField(STATUS,0x080+ 0x01,0,8,doc='Major revision number of the firmware'),
		'MINOR_VERSION' : 	BitField(STATUS,0x080+ 0x02,0,8,doc='Minor revision number of the firmware'),
		'BUILD_NUMBER' : 	BitField(STATUS,0x080+ 0x03,0,8,doc='Build number of the firmware'),
		'BUILD_YEAR' : 	BitField(STATUS,0x080+ 0x04,0,8,doc='Build year of the firmware'),
		'BUILD_MONTH' : 	BitField(STATUS,0x080+ 0x05,0,8,doc='Build month of the firmware'),
		'BUILD_DAY' : 		BitField(STATUS,0x080+ 0x06,0,8,doc='Build day of the firmware'),

	}


	def __init__(self,fpga):
		super(self.__class__,self).__init__(fpga,fpga.SYSTEM_PORT, fpga.SYSTEM_SYSMOD_MODULE)
		self._lock() # prevent further property creation to avoid creating attrubutes by mistake

	def init(self):
		#self.lcd_init()
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

	def global_trig(self):
		self.pulse_bit('GLOBAL_TRIG')

	def global_reset(self):
		self.pulse_bit('GLOBAL_RESET')

	def lcd_read_write(self,dir=0, command=1, data=0):
		self.LCD_RW=0 # Always write for now
		self.LCD_RS=not command # 0 when a command

	def lcd_write_command(self, data):
		delay=2e-3 # Minimum delay to wait to ensure the LCD had time to process the command 
		self.LCD_RW=0 # Always write for now
		self.LCD_RS=0 # 0 when a command
		self.LCD_DATA= (data>>4) & 0x0F # Send High nibble
		self.pulse_bit('LCD_E')
		time.sleep(delay)
		self.LCD_DATA=(data & 0x0F) # Send Low nibble
		self.pulse_bit('LCD_E')
		time.sleep(delay)

	def lcd_write_data(self, data):
		delay=2e-3 # Minimum delay to wait to ensure the LCD had time to process the command 
		self.LCD_RW=0 # Always write for now
		self.LCD_RS=1 # 1 for data
		self.LCD_DATA=(data>>4) & 0x0F # Send High nibble
		self.pulse_bit('LCD_E')
		time.sleep(delay)
		self.LCD_DATA=(data & 0x0F) # Send Low nibble
		self.pulse_bit('LCD_E')
		time.sleep(delay)

	def lcd_print(self,str):
		for s in str:
			self.lcd_write_data(ord(s))

	def lcd_init(self):
		# At this point we do not know which nibble we are writing if the device is in 4 bit mode. We switch back to 8 bits to reset the nibble counter. Tis might take 2 commands in the worst case.
		self.lcd_write_command(0b00110011)

		# Now we are in 8 bit interface, and we know that the next nibble will be the MSB. 
		# We send a last 8 bit interface command followed by a 4-bit  4 bit interface command.
		self.lcd_write_command(0b00110010)

		# We configure the LCD 

		self.lcd_write_command(0b00101100) # 4 bit mode, 2 lines, large font
		self.lcd_write_command(0b00001101) # Display on, cursor off, blinking on
		self.lcd_write_command(0b00000001) # Clear display, set address to zero
		#self.lcd_write_command(0b00000010) # Move cursor to 1st digit
		self.lcd_write_command(0b00000110) # Cursor move = increase, Shift=off

		self.lcd_define_char(0,(
			0b00010000 ,
			0b00011010 ,
			0b00011100 ,
			0b00011100 ,
			0b00000111 ,
			0b00000000 ,
			0b00000000 ,
			0b00000000 ) )
		self.lcd_set_addr(0x00)
		self.lcd_print('\000CHIME Pathfinder')
		self.lcd_set_addr(0x40)
		self.lcd_print('Data acqusition')

	def lcd_clear(self):
		self.lcd_write_command(0b00000001) # Clear display, set address to zero

	def lcd_set_addr(self,addr):
		self.lcd_write_command(0x80+(addr & 0x7F)) # set address

	def lcd_define_char(self,char_number, bitmap):
		self.lcd_write_command(0x40+(char_number<<3)) # set CG address
		for c in bitmap:
			self.lcd_write_data(c)

	def status(self):
		print '-------------------------SYSMOD--------------------------------------'
		print 'chFPGA Firmware version %i.%i, Build %i, Date: %04i-%02i-%02i' % (self.MAJOR_VERSION, self.MINOR_VERSION, self.BUILD_NUMBER, self.BUILD_YEAR+2000,self.BUILD_MONTH, self.BUILD_DAY)
		print 'Bistream timestamp is: %s' % self.read_bitstream_date()
		print '----------------------------------------------------------------------'


