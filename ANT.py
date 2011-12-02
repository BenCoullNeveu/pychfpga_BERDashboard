#!/usr/bin/python

"""
ANT.py module 
 Implements interface to Antenna processor
#
# History:
# 2011-07-12 : JFC : Created from test code in chFPGA.py
"""

import numpy as np
from Module import Module_base, BitField


class ADCDAQ_base(Module_base):
	""" Implements interface to the ADC data acquisisition logic within a procecessor pipeline"""
	# Create local variables for page numbers tomake the table more readable
	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS
	DRP=BitField.DRP

	BITS={
		# 0x00 - 0x07, bits 5:0: IODELAY values for bits 0:7
		# 0x08, bits 5:0: IODELAY values for the clock line

		'DELAY0' : 	BitField(CONTROL,0x00,0,5,doc='IODELAY value for the data line. Loaded the IODELAY_RST is pulsed.'),
		'CLK_DELAY' : 	BitField(CONTROL,0x08,0,5,doc='IODELAY value for the clock line. Loaded the CLK_IODELAY_RST is pulsed.'),

		'MMCM_RST' : 	BitField(CONTROL,0x09,7,doc='MCMM reset. Must be high when using DRP'),
		#'NC' : 	BitField(CONTROL,0x09,6,doc='Polarity of the word clock on the ISERDES'),
		'CLK_IODELAY_RESET' : 	BitField(CONTROL,0x09,5,doc='Resets the IODELAY element in the clock path. This loads the delay values into the delay lines'),
		'ENABLE_RAMP' : 	BitField(CONTROL,0x09,4,doc='Enables transmission of a ramp. 0=inactive, 1=active'),
		'IDELAYCTRL_RESET' : 	BitField(CONTROL,0x09,3,doc='Resets the IDELAYCTRL. Forces it to recalibrate. '),
		'BUFR_RESET' : 		BitField(CONTROL,0x09,2,doc='Resets the BUFR.'),
		'ISERDES_RESET' : 	BitField(CONTROL,0x09,1,doc='Resets the ISERDES.'),
		'IODELAY_RESET' : 	BitField(CONTROL,0x09,0,doc='Resets the IODELAY element. This loads the delay values into the delay lines'),

		'CAPTURE_TRIG' : 	BitField(CONTROL,0x0A,7,doc='A 0-to-1 transition triggers capturing of a 4-byte word'),
		'CAPTURE_ALIGN' : 	BitField(CONTROL,0x0A,6,doc='1: Next capture alignes the non-zero byte to byte 1. 0: Capture next word on a 11-word periodiciry'),
		'CAPTURE_SOURCE' : 	BitField(CONTROL,0x0A,5,doc='0: Word number is the one determined during the ALIGN process. 1: Word number is the one specified in USER_WORD_NUMBER'),
		'CAPTURE_USER_WORD_NUMBER' : 	BitField(CONTROL,0x0A,0,4,doc='0: Word number is the one determined during the ALIGN process. 1: Word number is the one specified in USER_WORD_NUMBER'),

		'IOCLK_POL' : 	BitField(CONTROL,0x0B,7,doc='Polarity of the data clock on the ISERDES'),
		'DIVCLK_POL' : 	BitField(CONTROL,0x0B,6,doc='Polarity of the word clock on the ISERDES'),

		'CLK_DELAY_STATUS':	BitField(STATUS,0x88,0,5,doc='Current delay value of the CLK line IODELAY'),
		'CAPTURE_DONE' : 	BitField(STATUS,0x89,7,doc="'1' when capture is complete"),
		'FIFO_OVERFLOW' : 	BitField(STATUS,0x89,6,doc="'1' if the FIFO has overflowed. Reset by SERDES_SYNC."),
		'FIFO_UNDERFLOW' : 	BitField(STATUS,0x89,5,doc="'1' if the FIFO has underflowed.  Reset by SERDES_SYNC."),
		'FIFO_EMPTY' : 		BitField(STATUS,0x89,4,doc="'1' if the FIFO has been empty. Reset by SERDES_SYNC."),
		'IDELAYCTRL_PRESENT':BitField(STATUS,0x89,1,doc='Indicate whether this ADCDAQ instantiated a IODELAYCTRL'),
		'IDELAYCTRL_RDY' : 	BitField(STATUS,0x89,0,doc='Indicate if the IODELAYCTRL has finished calibrating'),

		'CAPTURE_PATTERN0' : BitField(STATUS,0x8A,0,8,doc='Captured byte'),
		'CAPTURE_PATTERN1' : BitField(STATUS,0x8B,0,8,doc='Captured byte'),
		'CAPTURE_PATTERN2' : BitField(STATUS,0x8C,0,8,doc='Captured byte'),
		'CAPTURE_PATTERN3' : BitField(STATUS,0x8D,0,8,doc='Captured byte'),

		'CAPTURE_WORD_CTR' : BitField(STATUS,0x8E,4,4,doc='Free running word counter for the capture engine'),
		'CAPTURE_WORD_NUMBER' : BitField(STATUS,0x8E,0,4,doc='Word number determined by the automatic alignment process'),

		'RAMP_CTR' : BitField(STATUS,0x8F,0,6,doc='Free running word counter for readout interface, used to generate ramp at the ADCDAQ level'),

		'FIFO_WR_COUNT' : BitField(STATUS,0x90,0,8,doc='Number of words in the FIFO, as seen from the WR clock'),
		'FIFO_RD_COUNT' : BitField(STATUS,0x91,0,8,doc='Number of words in the FIFO, as seen from the RD clock (readout system)'),

		'ADC_CLK_SAMPLE' : BitField(STATUS,0x80+18,0,doc='Non-delayed 400 MHz ADC clock sampled by REFCLK'),

		'MMCM_FB_LOW' : 		BitField(DRP,0x14,0,6,doc='MCMM Feedback clock Low time (in VCO cycles)'),
		'MMCM_FB_HIGH' : 		BitField(DRP,0x14,6,6,doc='MCMM Feedback clock High time (in VCO cycles)'),
		'MMCM_FB_PHASE' : 		BitField(DRP,0x14,13,3,doc='MCMM Feedback clock phase in increments of 1/8 the VCO period'),

		'MMCM_DIVCLK_LOW' : 	BitField(DRP,0x0A,0,6,doc='MCMM DIVCLK clock Low time (in VCO cycles)'),
		'MMCM_DIVCLK_HIGH': 	BitField(DRP,0x0A,6,6,doc='MCMM DIVCLK clock High time (in VCO cycles)'),
		'MMCM_DIVCLK_PHASE':	BitField(DRP,0x0A,13,3,doc='MCMM DIVCLK clock phase in increments of 1/8 the VCO period'),
		'MMCM_DIVCLK_DELAY':	BitField(DRP,0x0B,0,6,doc='MCMM DIVCLK clock delay in increments of the VCO period'),

		'MMCM_ADCCLK_LOW' : 	BitField(DRP,0x0C,0,6,doc='MCMM DIVCLK clock Low time (in VCO cycles)'),
		'MMCM_ADCCLK_HIGH': 	BitField(DRP,0x0C,6,6,doc='MCMM DIVCLK clock High time (in VCO cycles)'),
		'MMCM_ADCCLK_PHASE':	BitField(DRP,0x0C,13,3,doc='MCMM DIVCLK clock phase in increments of 1/8 the VCO period'),
		'MMCM_ADCCLK_DELAY':	BitField(DRP,0x0D,0,6,doc='MCMM DIVCLK clock delay in increments of the VCO period'),

		'MMCM_POWER':	BitField(DRP,0x28,0,16,doc='MCMM Power bits. Must be set to 0xFFFF in order to successfully program the other MMCM registers'),

	}

	def __init__(self,ant_ch_instance):
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.ADCDAQ_MODULE)
		self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)

	def set_delay(self, dly=[0,0,0,0,0,0,0,0]):
		""" Sets the tap delays 
		WARNING: will work only if DIVCLK is clocking (i.e. ADC not in SYNC, and BUFR/PLL not in RESET)
		"""
		if isinstance(dly,int):
			dly=[dly]*8;
		elif len(dly)>9:
			raise Exception('Delay vector too long')

		self.write(self.BITS['DELAY0'].addr, dly) # Set delay in registers
		self.pulse_bit('IODELAY_RESET');

	def set_clk_delay(self, dly):
		""" Sets the tap delay on the clock line 
		WARNING: will work only if DIVCLK is clocking (i.e. ADC not in SYNC, and BUFR/PLL not in RESET)
		"""
		if not isinstance(dly,int):
			raise Exception('Delay on the clock line must be a scalar')

		self.write(self.BITS['CLK_DELAY'].addr, dly) # Set delay in registers
		self.pulse_bit('CLK_IODELAY_RESET');


	def read_delay(self):
		""" Reads the 8 delay tap values and return them as an array"""
		return self.read(0x00,length=8) # Reads the delay in registers

	def get_actual_delay(self):
		""" Reads the 8 actual delay tap values (returned by the IODELAY themselves, not the last delay set point) and return them as an array"""
		return self.read(0x80,length=8) # Reads the delay in registers

	def set_divclk_phase(self,phase):
		"""
		Sets DIVCLK phase on MCMM in inrements of 1/8 VCO cycles. Valid range is 0-512.
		"""
		self.MMCM_RST=1
		self.MMCM_POWER=0xFFFF
		self.MMCM_DIVCLK_PHASE=phase & 0x07
		self.MMCM_DIVCLK_DELAY=phase>>3
		self.MMCM_RST=0

	def set_adcclk_phase(self,phase):
		"""
		Sets ADC_CLK phase on MCMM in inrements of 1/8 VCO cycles. Valid range is 0-512.
		"""
		self.MMCM_RST=1
		self.MMCM_POWER=0xFFFF
		self.MMCM_ADCCLK_PHASE=phase & 0x07
		self.MMCM_ADCCLK_DELAY=phase>>3
		self.MMCM_RST=0

	delay=property(set_delay,read_delay)

#	def get_iodelayctrl_present(self):
#		return self.IDELAYCTRL_PRESENT;

#	def get_iodelayctrl_ready(self):
#		return self.IDELAYCTRL_RDY;

#	iodelayctrl_present=property(get_iodelayctrl_present)
#	iodelayctrl_ready=property(get_iodelayctrl_ready)

	def capture_print(self):
		""" """
		self.CAPTURE_SOURCE=1
		self.CAPTURE_ALIGN=0
		for i in range(11):
			self.CAPTURE_USER_WORD_NUMBER=i
			self.pulse_bit('CAPTURE_TRIG')
			print 'Word number: %i : ' % i, self.read(self.BITS['CAPTURE_PATTERN0'].addr,length=4)
		self.CAPTURE_SOURCE=0

	def capture_phase(self):
		""" """
		self.CAPTURE_SOURCE=0
		self.CAPTURE_ALIGN=1
		for i in range(8):
			self.set_divclk_phase(i)
			#self.CAPTURE_USER_WORD_NUMBER=i
			self.pulse_bit('CAPTURE_TRIG')
			#self.CAPTURE_ALIGN=0
			print 'Word number: %i : ' % i, self.read(self.BITS['CAPTURE_PATTERN0'].addr,length=4)
		self.CAPTURE_SOURCE=0

	
class FR_DIST_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""
	# Create local variables for page numbers tomake the table more readable
	CONTROL=BitField.CONTROL
	STATUS=BitField.STATUS

	# Register definition
	BITS={
		'ENABLE_RAMP' : 	BitField(CONTROL,0x00,6,doc='Enables transmission of a ramp. 0=inactive, 1=active'),
		'DUAL_FRAME': 		BitField(CONTROL,0x00,5,doc="When '1', allows buffering of two frames before it is transmitted."),
		'SYNC_RAMP': 		BitField(CONTROL,0x00,4,doc="When '1', synchronizes the ramp generator with the ADC data value. Must be set to zero for the ramp to increment naturallly. This might change the SYNC pulses spacing and will require resyncing or resseting the downstream modules"),
		'FIFO_RESET': 		BitField(CONTROL,0x00,3, doc="When '1', resets the data FIFO"),
		'TRIG_FRAME': 		BitField(CONTROL,0x00,2, doc="When a 0 to 1 transition is detected, force transmission of 'TRIG_FRAME_COUNT' data frame"),
		'DSP_DATA_SRC_ADC': BitField(CONTROL,0x00,1, doc="Selects the data source: 0=Internal (Ramp or FIFO), 1=ADC"),
		'DSP_CLK_SRC_ADC': 	BitField(CONTROL,0x00,0, doc="Selects the clock source for the antenna processor. Not used: ADC clock is always selected."),
		'TRIG_FRAME_COUNT': BitField(CONTROL,0x01,0,8, doc="Sets the number of frame to transmit. 0= COntinuous transmission, 1-255 = Trigerred transmission."),
		'SYNC_PERIOD': 		BitField(CONTROL,0x02,0,16, doc="Number of clock cycles between SYNC pulses. See CASPER documentation for minimum SYNC spacing."),

		'RAMP_MISMATCH': 	BitField(STATUS,0x80,2, doc="Active high if the ramp value does not match the ADC value. used for testing the ADC data acquisition when the ADC is set in ramp generation mode"),
		'CTRL_FIFO_EMPTY': 	BitField(STATUS,0x80,1, doc="Active high  when the data FIFO is empty"),
		'CTRL_FIFO_OVERFLOW': BitField(STATUS,0x80,0, doc="Active high if the data FIFO is overflowing"),
		'CTRL_FIFO_LENGTH': BitField(STATUS,0x81,0,8, doc="Number of samples currently in the data FIFO (last 8 bits only)"),
		'TRIG_COUNT': 		BitField(STATUS,0x82,0,8, doc="Number trigger events received")
		}

	def __init__(self,ant_ch_instance):
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.FR_DIST_MODULE)

	# Specialized functions

	def reset_fifo(self):
		self.pulse_bit('FIFO_RESET')

	def inject_frame(self,length=None, data=None):

		if data==None: # Send ramp
			if length==None:
				length=1024
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
				
		self.write(0x200, s,incr=0) # Write to FIFO

	def trig_frame(self,number_of_frames=1):
		self.TRIG_FRAME_COUNT=number_of_frames
		self.pulse_bit('TRIG_FRAME')

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

	def __init__(self,ant_ch_instance):
		self.ant_ch=ant_ch_instance.ant_number
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.CH_DIST_MODULE)

	def reset(self):
		self.RESET=1
		self.RESET=0

	def select_words(self,words_to_enable=1024/4):
		"""
		Selects which words* are going to be transmitted at the output of the antenna processing pipeline.
		If 'pattern' is an integer, the work 0 to (pattern-1) are transmitted.
		If pattern is an array, the word numbers indicated in the arrays are transmitted.
		* NOTE: a word is 4 bytes. If the FFT is bypassed, each word contains 4 8-bit ADC samples. 
			If the FFT is enabled, each word contains 2 complex values, one for the even and odd frequency bin. Each complex value is two 8-bit values (real and imaginary)
		"""
		# Initialize filter mask (8 flags per byte)
		mask=np.zeros(1024/4/8, np.uint8)

		if isinstance(words_to_enable, int):
			words_to_enable=range(words_to_enable)

		# Set the bits in mask
		for j in words_to_enable:
			#print 'setting bit %i of byte %i' % ((j % 8), j//8)
			mask[j//8] |= (1<<(j % 8))

		self.write_ram(0x00,mask); # Enable transmission of selected bytes 

	def status(self):
		print '-------------- ANT[%i].CH_DIST STATUS --------------' % (self.ant_ch)
		print 'RESET: %i' % self.RESET
		print 'FIFO EMPTY: %i' % self.FIFO_EMPTY
		print 'FIFO OVERFLOW: %i' % self.FIFO_OVERFLOW
		print 'VALID FRAME CTR: %i' % self.FRAME_VALID_CTR



class ANT_channel(object):
	""" Implements interface to one of the antenna processor pipeline"""

	# Antenna processor module addresses
	ADCDAQ_MODULE=0
	FR_DIST_MODULE=1
	DSP_MODULE=2
	CH_DIST_MODULE=3

	def __init__(self,ant_instance,ant_number):
		#super(ADC_chip,self).__init__(fpga)
		self.ant=ant_instance # store current ADC number for this instance
		self.ant_number=ant_number # store current ADC number for this instance
		self.fpga=self.ant.fpga;
		self.ADCDAQ=ADCDAQ_base(self)
		self.FR_DIST=FR_DIST_base(self)
		self.DSP=DSP_base(self)
		self.CH_DIST=CH_DIST_base(self)
		
	def read(self,module,addr,*args,**kwargs): 
		return self.ant.read(self.ant_number,module,addr,*args,**kwargs)

	def write(self,module,addr,data,*args,**kwargs): 
		return self.ant.write(self.ant_number,module,addr,data,*args,**kwargs)



	def init(self):
		self.ADCDAQ.init()
		self.FR_DIST.init()
		self.DSP.init()
		self.CH_DIST.init()


	def status(self):
		pass



class ANT_base(object):
	""" Instantiates a container for all antenna processors available on the FPGA """

	def __init__(self,fpga,verbose=0):
		self.fpga=fpga
		self.verbose=verbose
		# Create an instance of ADC_chip for each chip of the FMC board
		self.ANT=[]
		for i in range(8):
			self.ANT.append(ANT_channel(self,i))

	def __getitem__(self,key):
		"""	If the user indexes this object (ANT[n] instead of ANT) then return the antenna processor instance"""
		return self.ANT[key]

	# Low-level access functions

	def read(self,ant_number,module_number,addr,*args,**kwargs):
		""" Reads from the register of a module of a specified antenna processor"""
		fpga=self.fpga
		data=fpga.Read(fpga.ANT_PORT[ant_number],module_number, addr,*args,**kwargs)
		return data

	def write(self,ant_number, module_number, addr,data,*args,**kwargs):
		""" Writes to the register of a module of a specified antenna processor"""
		fpga=self.fpga
		fpga.Write(fpga.ANT_PORT[ant_number],module_number, addr, data,*args,**kwargs)

	def init(self):
		for ant in self.ANT:
			ant.init()

		self.ANT[1].ADCDAQ.set_divclk_phase(1) # Adjust phase of the DIVCLK signal to allow proper sampling of the deserialized words

	def set_delays(self,adc_delay_table):
		"""
		Sets the delays for all ADC data lines using the provided array.
		'adc_delay-table'  consists of a list of 8 arrays comprising 8 delay values each.
		"""
		for i,dly in enumerate(adc_delay_table):	
			self.ANT[i].ADCDAQ.set_delay(dly); 
