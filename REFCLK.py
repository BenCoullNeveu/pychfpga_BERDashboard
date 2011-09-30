#!/usr/bin/python

"""
REFCLK.py module 
 Implements FMC Reference clock interface
#
# History:
	2011-09-22 JFC: Created
	2011-09-25 JFC: Modified to support new method on incrementing phase (pulse PS_EN unstead of PS_CLK) 
"""

from Module import Module_base, BitDef

import numpy as np

class REFCLK_base(Module_base):


	BITS={
		'PS_CLK' : 		BitDef(0x00,0,doc='Phase shift control clock -- Not used'),
		'PS_EN':		BitDef(0x00,1,doc='Enable Phase shift increment/decrement when transitionning from 0 to 1'),
		'PS_INCDEC':	BitDef(0x00,2,doc='1=Increment phase by 1/56th of cycle, 0= decrement phase by same amount'),

		'PS_DONE' : 	BitDef(0x080+ 0x00,0,doc='Phase shift completed'),
		'LOCKED' : 		BitDef(0x080+ 0x00,1,doc='MCMM is locked'),
	}


	def __init__(self,fpga):
		super(self.__class__,self).__init__(fpga,fpga.SYSTEM_PORT, fpga.SYSTEM_REFCLK_MODULE)

	def init(self):
		pass

	def inc_phase(self,inc_amount):
		if inc_amount>0:
			self.PS_INCDEC=1
		else:
			self.PS_INCDEC=0
		for i in range(abs(inc_amount)):
			self.pulse_bit('PS_EN')
			#while not self.PS_DONE: pass




	def status(self):
		print '---------------------FMC REF CLK  ------------------------------------'
		print 'MCMM Locked: %i' % (self.LOCKED)
		print '----------------------------------------------------------------------'


