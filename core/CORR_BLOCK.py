#!/usr/bin/python

"""
CORR_BLOCK.py module 
 Implements interface to the correlator blocks

 History:
 2012-06-21 : JFC : Created 
"""
import CH_DIST	


class CORR_BLOCK_base(object):
	""" Implements interface to one of the correlator"""

	# Antenna processor module addresses
	CH_DIST_MODULE=0
	CORR_MODULE=0
	ACC_MODULE=0

	def __init__(self,corr_instance,corr_number):
		#super(ADC_chip,self).__init__(fpga)
		self.corr=corr_instance # store current ADC number for this instance
		self.corr_number=corr_number # store current ADC number for this instance
		self.fpga=self.corr.fpga;
		self.CH_DIST=CH_DIST.CH_DIST_base(self)

		
	def read(self,module,addr,*args,**kwargs): 
		return self.corr.read(self.corr_number,module,addr,*args,**kwargs)

	def write(self,module,addr,data,*args,**kwargs): 
		return self.corr.write(self.corr_number,module,addr,data,*args,**kwargs)



	def init(self):
		self.CH_DIST.init()


	def status(self):
		print '======= CORR NUMBER %i =============' % self.corr_number
		self.CH_DIST.status()



class CORR_base(object):
	""" Instantiates a container for all correlators """

	def __init__(self,fpga,verbose=0):
		self.fpga=fpga
		self.verbose=verbose
		# Create an instance of ADC_chip for each chip of the FMC board
		self.CORR=[]
		for i in range(fpga.NUMBER_OF_CORRELATORS):
			self.CORR.append(CORR_BLOCK_base(self,i))

	def __getitem__(self,key):
		"""	If the user indexes this object (ANT[n] instead of ANT) then return the antenna processor instance"""
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
		for corr in self.CORR:
			corr.init()

	def status(self):
		for corr in self.CORR:
			corr.status()
