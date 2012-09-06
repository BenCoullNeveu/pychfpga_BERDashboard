#!/usr/bin/python

"""
BiasADC.py module 
 Implements the interface to the Laser Bias Current ADC on the ADC FMC
#
# History:
# 2011-07-09 : JFC : Created from test code in chFPGA.py
"""
import numpy as np

class BiasADC_base(object):
	def __init__(self,fpga,verbose=1):
		self.fpga_instance=fpga
		self.verbose=verbose

	def init(self):
		pass


	def read(self,addr):
		""" 
		Reads the raw word from the Laser current Bias ADC on the ADC FMC
		"""
		spi=self.fpga_instance.SPI
		return spi.read_write(spi.SPI_ADC_BIAS_ADDR, data=[addr<<3,0x00],type=np.dtype('>u2'))

	def voltage(self,addr):
		data=self.read(addr)
		return data
