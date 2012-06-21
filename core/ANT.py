#!/usr/bin/python

"""
ANT.py module 
 Implements interface to the Antenna processors

 History:
 2011-07-12 : JFC : Created from test code in chFPGA.py
"""
import ADCDAQ
import FRAMER
import FFT
#import CH_DIST	

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
		self.ADCDAQ=ADCDAQ.ADCDAQ_base(self)
		self.FR_DIST=FRAMER.FR_DIST_base(self)
		self.DSP=FFT.DSP_base(self)
		#self.CH_DIST=CH_DIST.CH_DIST_base(self)
		self.frame_length=self.ant.frame_length

		
	def read(self,module,addr,*args,**kwargs): 
		return self.ant.read(self.ant_number,module,addr,*args,**kwargs)

	def write(self,module,addr,data,*args,**kwargs): 
		return self.ant.write(self.ant_number,module,addr,data,*args,**kwargs)



	def init(self):
		self.ADCDAQ.init()
		self.FR_DIST.init()
		self.DSP.init()
#		self.CH_DIST.init()


	def status(self):
		print '======= ANTENNA NUMBER %i =============' % self.ant_number
		self.ADCDAQ.status()
		self.FR_DIST.status()
		self.DSP.status()
#		self.CH_DIST.status()



class ANT_base(object):
	""" Instantiates a container for all antenna processors available on the FPGA """
	frame_length=2048

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

	def init(self, delay_table=None):
		for ant in self.ANT:
			ant.init()

	
		if delay_table is not None:
			self.set_delays(delay_table)

	def status(self):
		for ant in self.ANT:
			ant.status()

		#self.ANT[1].ADCDAQ.set_divclk_phase(1) # Adjust phase of the DIVCLK signal to allow proper sampling of the deserialized words

	def set_delays(self,adc_delay_table):
		"""
		Sets the delays for all ADC data lines using the provided array.
		'adc_delay-table'  consists of a list of 8 arrays comprising 8 delay values each.
		"""
		for i,dly in enumerate(adc_delay_table):	
			self.ANT[i].ADCDAQ.set_delay(dly); 
