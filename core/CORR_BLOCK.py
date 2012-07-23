#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
CORR_BLOCK.py module 
 Implements interface to the correlator blocks

 History:
 2012-06-21 : JFC : Created 
"""
import CH_DIST
#import ACC


class CORR_BLOCK_channel(object):
	""" Implements interface to one of the correlator"""

	# Antenna processor module addresses
	CH_DIST_MODULE = 0
	CORR_MODULE = 1
	ACC_MODULE = 2

	def __init__(self, corr_instance, corr_number):
		#super(ADC_chip,self).__init__(fpga)
		self.corr = corr_instance # store current ADC number for this instance
		self.corr_number = corr_number # store current ADC number for this instance
		self.fpga = self.corr.fpga
		self.CH_DIST = CH_DIST.CH_DIST_base(self)
		#self.ACC = ACC.ACC_base(self)

		
	def read(self, module, addr, *args, **kwargs): 
		""" Reads a memory-mapped value at address 'addr' from the specified correlator number 'module'."""
		return self.corr.read(self.corr_number, module, addr, *args, **kwargs)

	def write(self, module, addr, data, *args, **kwargs): 
		""" Writes a memory-mapped value 'data' at address 'addr' to the specified correlator number 'module'."""
		return self.corr.write(self.corr_number, module, addr, data, *args, **kwargs)



	def init(self):
		""" Inisializes all modules of a correlator block.""" 
		self.CH_DIST.init()
		self.ACC.init()


	def status(self):
		"""Displays the status of al the correlator blocks"""
		print '======= CORR NUMBER %i =============' % self.corr_number
		self.CH_DIST.status()
		#self.ACC.status()



class CORR_BLOCK_base(object):
	""" Instantiates a container for all correlators blocks"""

	def __init__(self, fpga, verbose=0):
		self.fpga = fpga
		self.verbose = verbose
		# Create an instance of ADC_chip for each chip of the FMC board
		self.CORR = []
		for i in range(fpga.NUMBER_OF_CORRELATORS):
			self.CORR.append(CORR_BLOCK_channel(self, i))

	def __getitem__(self, key):
		"""	Returns the correlator instance specified by the index"""
		return self.CORR[key]

	# Low-level access functions

	# def read(self,ant_number,module_number,addr,*args,**kwargs):
		# """ Reads from the register of a module of a specified antenna processor"""
		# fpga=self.fpga
		# data=fpga.Read(fpga.ANT_PORT[ant_number],module_number, addr,*args,**kwargs)
		# return data

	# def write(self,ant_number, module_number, addr,data,*args,**kwargs):
		# """ Writes to the register of a module of a specified antenna processor"""
		# fpga=self.fpga
		# fpga.Write(fpga.ANT_PORT[ant_number],module_number, addr, data,*args,**kwargs)

	def init(self):
		""" Initializes all correlators"""
		for corr in self.CORR:
			pass#corr.init()

	def status(self):
		""" Displays the status of all correlators"""
		for corr in self.CORR:
			corr.status()
