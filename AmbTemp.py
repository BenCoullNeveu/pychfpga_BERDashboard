#!/usr/bin/python

"""
AmbTemp.py module 
 Implements the interface to the FMC Ambient Temperature monitor chip
#
# History:
# 2011-07-09 : JFC : Created from test code in chFPGA.py
"""
import numpy as np

class AmbTemp_base(object):

	def __init__(self,fpga,verbose=0):
		self.fpga_instance=fpga
		self.verbose=verbose

	def init(self):
		pass


	def read(self):
		""" 
		Reads the raw word from the SPI Ambient temperature monitor on the ADC FMC
		"""
		spi=self.fpga_instance.SPI
		return spi.read_write(spi.SPI_AMB_TEMP_ADDR, [0,0], type=np.dtype('>u2')) # Read 16 bit word

	def get_temperature(self):
		"""
		Returns the ambient temperature of the FMC ambient temperature monitor chip in Celcius
		"""
		data= self.read()
		data=np.int16(data<<2)>>2 # sign-extend bit 13 to bits 14 and 15 to obtain a 16-bit signed value
		temp= data /32.0;
		if self.verbose:
			print 'FMC Board Temperature is %.2f C' % (temp)
		return temp

	temperature=property(get_temperature)

	def status(self):
		print 'Ambient Temperature of the FMC board: %.1f C' % (self.temperature)

