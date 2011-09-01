#!/usr/bin/python

"""
ANT.py module 
 Implements interface to Antenna processor
#
# History:
# 2011-07-12 : JFC : Created from test code in chFPGA.py
"""

import numpy as np
from Module import Module_base, BitDef


class ADCDAQ_base(Module_base):
	""" Implements interface to the ADC data acquisisition logic within a procecessor pipeline"""
	BITS={
		'ENABLE_RAMP' : 	BitDef(0x08,4,doc='Enables transmission of a ramp. 0=inactive, 1=active'),
		'IDELAYCTRL_RESET' : 	BitDef(0x08,3,doc='Resets the IDELAYCTRL. Forces it to recalibrate. '),
		'BUFR_RESET' : 		BitDef(0x08,2,doc='Resets the BUFR.'),
		'ISERDES_RESET' : 	BitDef(0x08,1,doc='Resets the ISERDES.'),
		'IODELAY_RESET' : 	BitDef(0x08,0,doc='Resets the IODELAY element. This loads the delay values into the delay lines'),

		'RAMP_CTR' : 		BitDef(0x88,2,6,doc=''),
		'IDELAYCTRL_PRESENT' : 	BitDef(0x88,1,doc='Indicate whether this ADCDAQ instantiated a IODELAYCTRL'),
		'IDELAYCTRL_RDY' : 	BitDef(0x88,0,doc='Indicate if the IODELAYCTRL has finished calibrating'),
	}

	def __init__(self,ant_ch_instance):
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.ADCDAQ_MODULE)

	def set_delay(self, data=[0,0,0,0,0,0,0,0],reset=1):
		""" Sets the tap delays """
#		if type(data)==int:
#			data=[data]*8;
		self.write(0x00,data) # Set delay in registers
		self.pulse_bit(0x08,0);
		if reset:
			self.write_mask(0x08,0x06,0x06) # Reset SERDES and BUFR
			self.write_mask(0x08,0x06,0x02) # Reset SERDES 
			self.write_mask(0x08,0x06,0x00) # Stop reset

	def read_delay(self):
		""" Reads the 8 delay tap values and return them as an array"""
		return self.read(0x00,length=8) # Reads the delay in registers

	delay=property(set_delay,read_delay)

	def get_iodelayctrl_present(self):
		return self.read_bit(0x88,1);

	def get_iodelayctrl_ready(self):
		return self.read_bit(0x88,0);

	iodelayctrl_present=property(get_iodelayctrl_present)
	iodelayctrl_ready=property(get_iodelayctrl_ready)

class FR_DIST_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""

	# Register definition
	BITS={
		'ENABLE_RAMP' : 	BitDef(0x00,6,doc='Enables transmission of a ramp. 0=inactive, 1=active'),
		'DUAL_FRAME': 		BitDef(0x00,5,doc="When '1', allows buffering of two frames before it is transmitted."),
		'SYNC_RAMP': 		BitDef(0x00,4,doc="When '1', synchronizes the ramp generator with the ADC data value. Must be set to zero for the ramp to increment naturallly. This might change the SYNC pulses spacing and will require resyncing or resseting the downstream modules"),
		'FIFO_RESET': 		BitDef(0x00,3, doc="When '1', resets the data FIFO"),
		'TRIG_FRAME': 		BitDef(0x00,2, doc="When a 0 to 1 transition is detected, force transmission of 'TRIG_FRAME_COUNT' data frame"),
		'DSP_DATA_SRC_ADC': 	BitDef(0x00,1, doc="Selects the data source: 0=Internal (Ramp or FIFO), 1=ADC"),
		'DSP_CLK_SRC_ADC': 		BitDef(0x00,0, doc="Selects the clock source for the antenna processor. Not used: ADC clock is always selected."),
		'TRIG_FRAME_COUNT': BitDef(0x01,0,8, doc="Sets the number of frame to transmit. 0= COntinuous transmission, 1-255 = Trigerred transmission."),
		'SYNC_PERIOD': 		BitDef(0x02,0,16, doc="Number of clock cycles between SYNC pulses. See CASPER documentation for minimum SYNC spacing."),

		'RAMP_MISMATCH': 	BitDef(0x80,2, doc="Active high if the ramp value does not match the ADC value. used for testing the ADC data acquisition when the ADC is set in ramp generation mode"),
		'CTRL_FIFO_EMPTY': 	BitDef(0x80,1, doc="Active high  when the data FIFO is empty"),
		'CTRL_FIFO_OVERFLOW': BitDef(0x80,0, doc="Active high if the data FIFO is overflowing"),
		'CTRL_FIFO_LENGTH': BitDef(0x81,0,8, doc="Number of samples currently in the data FIFO (last 8 bits only)")
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
	BITS={
		'BYPASS': 	BitDef(0x00,0, doc="Bypass the FFT"),
		'RESET_SYNC': 	BitDef(0x00,1, doc="Reset the SYNC Module. Force it to re-learn the DSP block latency."),
		'OUT_SHIFT': 	BitDef(0x01,4,4, doc="Number of bits to right-shift thr FFT data"),
		'FFT_SHIFT': 	BitDef(0x02,0,10, doc="FFT shift enable bit for each of the FFT stage"),
		}

	def __init__(self,ant_ch_instance):
		super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.DSP_MODULE)
		
	def reset_sync(self):
		self.pulse_bit('RESET_SYNC')

class CH_DIST_base(Module_base):
	""" Implements interface to the FR_DIST within a procecessor pipeline"""
	BITS={
		'RESET': 	BitDef(0x00,7, doc="Reset the CH_DIST. Clears FIFO."),
		'FIFO_EMPTY': 	BitDef(0x80,7, doc="Active high when the data FIFO is empty"),
		'FIFO_OVERFLOW': BitDef(0x80,6, doc="Active high if the data FIFO is overflowing"),
		'FRAME_VALID_CTR': BitDef(0x80,0,6, doc="Number of valid frames seen since last reset")
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
		pass

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
		pass

	def set_delays(self,adc_delay_table):
		"""
		Sets the delays for all ADC data lines using the provided array.
		'adc_delay-table'  consists of a list of 8 arrays comprising 8 delay values each.
		"""
		for i,dly in enumerate(adc_delay_table):	
			self.ANT[i].ADCDAQ.set_delay(dly); 
