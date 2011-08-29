#!/usr/bin/python

"""
MGT.py module 
 Implements interface to the MGT
#
# History:
# 2011-08-03 : JFC : Created 
"""

import time
import numpy as np
import matplotlib.pyplot as plt

from Module import Module_base, BitDef
import util

class MGT_port_base(Module_base):
	""" Implements interface to the MGT """

	# Register definition
	BITS={
		'USER_CHARISK' : 	BitDef(0x04,0,4,doc=''),
		'USER_DATA_EN' : 	BitDef(0x04,7,doc=''),

		'GTX_RX_RESET':		BitDef(0x05,7,doc=''),
		'RX_RESET' :		BitDef(0x05,6,doc=''),
		'GTX_TX_RESET':		BitDef(0x05,5,doc=''),
		'TX_RESET' :		BitDef(0x05,4,doc=''),
		'LOGIC_RESET' :		BitDef(0x05,3,doc=''),
		'LOOPBACK_MODE' : 	BitDef(0x05,0,3,doc=''),

		'TX_DIFFCTRL' :		BitDef(0x06,4,4,doc=''),
		'TX_PREEMPHASIS' :	BitDef(0x06,0,4,doc=''),

		'TX_POSTEMPHASIS' :	BitDef(0x07,3,5,doc=''),
		'RX_EQMIX' :		BitDef(0x07,0,3,doc=''),

		'RX_CDR_RESET' :	BitDef(0x08,7,doc=''),
		'TX_ELEC_IDLE' :	BitDef(0x08,6,doc=''),
		'DRP_BANK' : 		BitDef(0x08,0,2,doc=''), # not used anymore

		'TX_PRBS_FORCE_ERROR' : BitDef(0x09,7,doc=''),
		'TX_PRBS_MODE' : 		BitDef(0x09,4,3,doc=''),
		'RX_PRBS_RESET_COUNTER':BitDef(0x09,3,doc=''),
		'RX_PRBS_MODE' : 		BitDef(0x09,0,3,doc=''),

		'RX_DFE_OVERRIDE': 		BitDef(10,7,doc=''),
		'TAP1' : 		BitDef(10,0,5,doc=''),
		'TAP2' : 		BitDef(11,0,5,doc=''),

		'TAP3' : 		BitDef(12,4,4,doc=''),
		'TAP4' : 		BitDef(12,0,4,doc=''),


		# STATUS bitfields
		'RX_CHARISK' : 		BitDef(0x84,4,4,doc=''),
		'RX_CHARISCOMMA' : 	BitDef(0x84,0,4,doc=''),

		'RX_LOSSOFSYNC': 	BitDef(0x85,6,2,doc=''),
		'RX_PRBS_ERROR': 	BitDef(0x85,5,doc=''),
		'EYE_HEIGHT' : 		BitDef(0x85,0,5,doc=''),

		'RX_STATE_NUMBER' : BitDef(0x86,5,3,doc=''),
		'TAP1_MON' : 		BitDef(0x86,0,5,doc=''),

		'RX_COUNT' : 		BitDef(0x87,5,3,doc=''),
		'TAP2_MON' : 		BitDef(0x87,0,5,doc=''),

		'TAP4_MON' : 		BitDef(0x88,4,4,doc=''),
		'TAP3_MON' : 		BitDef(0x88,0,4,doc=''),


		'RX_RESETDONE' : 	BitDef(0x89,7,doc=''),
		'RX_PLL_LOCKED' : 	BitDef(0x89,6,doc=''),
		'CLK_DLY_MON' : 	BitDef(0x89,0,6,doc=''),

		'RX_BUF_STATUS' : 	BitDef(0x8A,5,3,doc=''),
		'TX_COUNT' : 		BitDef(0x8A,0,5,doc=''),

		'TX_STATE' :		BitDef(0x080 + 20,4,4,doc=''),
	
		'RX_VALID' :		BitDef(0x080 + 21,7,doc=''),
		'RX_ELEC_IDLE' :	BitDef(0x080 + 21,6,doc=''),

		}

	DRP_FIELDS={
		'RX_CLK25_DIVIDER' : 	BitDef(0x17,5,5,doc=''),
		'RX_EYE_SCANMODE' : 	BitDef(0x2E,9,2,doc=''),
		'RX_EYE_OFFSET' : 		BitDef(0x2D,8,8,doc=''),
		'AC_CAP_DIS' : 			BitDef(0x17,4,doc=''),
		'RX_PRBS_ERR_COUNT' : 	BitDef(0x82,0,16,doc=''),
		'RX_PLL_DIVSEL_FB' : 	BitDef(0x1B,1,5,doc=''),
		'RX_PLL_DIVSEL_FB45' : 	BitDef(0x1B,6,doc=''),
		'TXOUTCLK_CTRL' : 	BitDef(0x43,0,3,doc=''),
		}

	def __init__(self,fpga,MGT_number):
		self.MGT_number=MGT_number
		super(self.__class__,self).__init__(fpga,fpga.MGT_PORT, MGT_number)

		for field_name in self.DRP_FIELDS.keys():
			print '  Defining property "%s"' % (field_name)

			# Use function closures to create the callback function with arguments that won't be rebinded
			fget=lambda s,_bit_name=field_name:s.read_sys_field(_bit_name) # Pass bit_name as a default argument to 'close' that variable (i.e. bind it now). Otherwise the function will use the value at call time (which is the last value assigned to that variable) 
			fset=lambda s,value,_bit_name=field_name:s.write_sys_field(_bit_name,value)
			setattr(self.__class__, field_name, property(fget, fset,doc=self.DRP_FIELDS[field_name].doc))
		self._lock()

	def read_DRP(self,addr):
		""" 
		Reads a 16-bit register of the MGT at specified word address 
		"""
		return self.read(0x200+2*(addr),type=np.dtype('<u2')); # Sysmon data is read LSB first

	def write_DRP(self,addr,data):
		""" 
		Writes a 16-bit register of the MGT at specified word address 
		"""
		self.write(0x200+2*(addr),[data &0xFF, (data>>8)&0xFF]); # Sysmon data is LSB first

	def read_sys_field(self,bit_name):
		""" Reads the field identified by the name 'bit_name' which is looked up in the BITS table to find the bit definition (port, bit position etc). Returns a boolean."""  
		bit_def=self.DRP_FIELDS[bit_name]
		data= self.read_DRP(bit_def.addr)
		return data>>bit_def.bit & ((1<<bit_def.width)-1)

	def write_sys_field(self,bit_name,data):
		""" Writes the field identified by the name 'bit_name' which is looked up in the BITS table to find the bit definition (port, bit position etc). Returns a boolean."""  
		bit_def=self.DRP_FIELDS[bit_name]
		if (data>=2**bit_def.width) or data<0:
			raise Exception('Bad value %i for parameter %s' % (data, bit_name))
		old_data= self.read_DRP(bit_def.addr)
		mask=(2**bit_def.width-1)<<bit_def.bit
		new_data = old_data & ~mask
		new_data |= ((data << bit_def.bit) & mask) 
		self.write_DRP(bit_def.addr, new_data)

	def rx_reset(self):
		self.RX_DFE_OVERRIDE=1
		#self.TAP1=8
		self.RX_CDR_RESET=1;
		self.RX_CDR_RESET=0;
		self.RX_EYE_SCANMODE=1
		self.RX_EYE_SCANMODE=0

		while not self.RX_RESETDONE:
			pass

	def init(self):
		# Receiver set-up

		self.RX_DFE_OVERRIDE=1
		self.TAP1=8
		self.TAP2=0
		self.TAP3=0
		self.TAP4=0
		self.RX_EQMIX=0 # RX Equalizer
		self.RX_EYE_SCANMODE=0

		# Transmitter set-up
		self.TX_DIFFCTRL=10 # Transmit power
		self.TX_PREEMPHASIS=0
		self.TX_POSTEMPHASIS=0


	def reset(self):
		self.GTX_RX_RESET=1;
		self.GTX_RX_RESET=0;
		self.GTX_TX_RESET=1;
		self.GTX_TX_RESET=0;
		self.LOGIC_RESET=1;
		self.LOGIC_RESET=0;
		while not self.RX_RESETDONE:
			pass

	def status(self):
		print self
		print '-------------- MGT[%i] STATUS --------------' % (self.MGT_number)
		print 'RX RESET DONE: %i' % self.RX_RESETDONE
		print 'RX PLL LOCKED: %i' % self.RX_PLL_LOCKED
		print 'RX LOSS OF SYNC: %i' % self.RX_LOSSOFSYNC
		print 'TX parameters: Diff swing: %i, Pre-emph: %i, Post-emph: %i ' % (self.TX_DIFFCTRL,self.TX_PREEMPHASIS,self.TX_POSTEMPHASIS)
		print 'RX parameters: Equalization: %i' % (self.RX_EQMIX)
		print 'RX DFE status : Tap1=%i, Tap2=%i, Tap3=%i, Tap4=%i ' % (self.TAP1_MON,self.TAP2_MON,self.TAP3_MON,self.TAP4_MON)
		print 'RX voltage swing : %0.1f mV (%i lsb)' % (self.EYE_HEIGHT/31.0*200,self.EYE_HEIGHT)
		print 'TX PRBS MODE: %i' % (self.TX_PRBS_MODE)
		print 'RX PRBS MODE: %i' % (self.RX_PRBS_MODE)
		print 'RX PRBS ERROR: %i' % (self.RX_PRBS_ERROR)
		print 'RX PRBS ERROR COUNT: %i' % (self.RX_PRBS_ERR_COUNT)



		

	def print_status(self):
		try:
			while 1: 
				print util.hex(self.read(0,length=5)), self.RX_LOSSOFSYNC, self.CLK_DLY_MON, self.EYE_HEIGHT, ' DFE Taps=[ %2i, %2i, %2i, %2i] ' % (self.TAP1_MON,self.TAP2_MON,self.TAP3_MON,self.TAP4_MON)
		except KeyboardInterrupt:
			pass

class MGT_base(Module_base):
	""" Instantiates a container for all MGTs """
	NUMBER_OF_MGT=4

	# Register definition
	BITS={
		'RESET' : 	BitDef(0x00,7,doc=''),
		'TX_SEL' : 	BitDef(0x00,0,2,doc=''),

		'MMCM_RESET' : 	BitDef(0x80,7,doc=''),
		'MMCM_LOCKED' : BitDef(0x80,6,doc=''),
		'RX_PLL_LOCKED' : BitDef(0x80,5,doc=''),
		}

	def __init__(self,fpga,verbose=0):
		self.fpga=fpga
		self.verbose=verbose
		super(self.__class__,self).__init__(fpga,fpga.MGT_PORT, self.NUMBER_OF_MGT)
		# Create an instance of ADC_chip for each chip of the FMC board
		self.MGT=[]
		for i in range(self.NUMBER_OF_MGT):
			self.MGT.append(MGT_port_base(self.fpga,i))
		self._lock() # Prevents further attribute assignments

	def __getitem__(self,key):
		"""	If the user indexes this object (MGT[n] instead of MGT) then return the MGT instance"""
		return self.MGT[key]

	# Low-level access functions

	def init(self):
		"""
		Initializes all MGTs.
		"""
		for mgt in self.MGT:
			mgt.init()

	def status(self):
		print '-------------- MGT Container STATUS --------------'
		print 'MGT Transmitter #: %i' % self.TX_SEL
		print 'MMCM_RESET: %i' % self.MMCM_RESET
		print 'MMCM_LOCKED: %i' % self.MMCM_LOCKED
		print 'RX PLL LOCKED: %i' % self.RX_PLL_LOCKED

		for mgt in self.MGT:
			mgt.status()

	def rx_reset(self):
		for mgt in self.MGT:
			mgt.rx_reset()

	def reset(self):
		self.RESET=1;
		self.RESET=0;

		#for mgt in self.MGT:
		#	mgt.reset()

	def test_link(self,tx,rx,duration=1,prbs_mode=1,ac_coupling=True):
		rx_mgt=self.MGT[rx]
		tx_mgt=self.MGT[tx]

		tx_mgt.TX_PRBS_MODE=prbs_mode
		tx_mgt.GTX_TX_RESET=1
		tx_mgt.GTX_TX_RESET=0

		rx_mgt.RX_PRBS_MODE=prbs_mode
		rx_mgt.AC_CAP_DIS=not ac_coupling
		rx_mgt.GTX_RX_RESET=1
		rx_mgt.GTX_RX_RESET=0
		rx_mgt.RX_PRBS_RESET_COUNTER=1
		rx_mgt.RX_PRBS_RESET_COUNTER=0
		t1=time.time();

		try:
			while 1:
				t2=time.time();
				dt=max(t2-t1,1e-3); # Limits minimum time interval to 1 ms
				errors=rx_mgt.RX_PRBS_ERR_COUNT
				if errors==65535 or dt>=duration: break
		except KeyboardInterrupt:
			pass
		nbits=5e9*dt
		ber_max=(errors+1)/nbits
		#print '# of errors: %i (BER<%3.1e)' % (errors, ber_max)

		#print 'DIsabling PRBS test mode for ', tx_mgt , 'and', rx_mgt
		tx_mgt.TX_PRBS_MODE=0
		rx_mgt.RX_PRBS_MODE=0
		rx_mgt.AC_CAP_DIS=False
		return errors

	def test_all_links(self,duration=0.1,prbs_mode=1,ac_coupling=True):
		N=len(self.MGT)
		for tx in range(N):
			for rx in range(N):
				print '%i->%i:' % (tx,rx),
				errors=self.test_link(tx,rx,duration,prbs_mode,ac_coupling)
				print '%s' % (errors if errors else 'OK')

	def plot_eye(self, Navg=1, step=1, tx_port=0, rx_port=1, sweep_port=0, sweep_param=None, sweep_range=None):
		rx=self.MGT[rx_port]
		tx=self.MGT[tx_port]
		sx=self.MGT[sweep_port]
		rx.RX_EYE_SCANMODE=1
		tx.TX_PRBS_MODE=1
		rx.RX_PRBS_MODE=1
		eye_max=[]

		if hasattr(sx,sweep_param):
			old_param_value=getattr(sx,sweep_param)
			param_fn=lambda val,_mgt=sx,_param=sweep_param: setattr(_mgt,_param,val)
			if sweep_range is None:
				if sweep_param in sx.BITS: sweep_range=range(2**sx.BITS[sweep_param].width)
				elif sweep_param in sx.DRP_FIELDS: sweep_range=range(2**sx.DRP_FIELDS[sweep_param].width)
				else:
					print 'You must specify the sweep range'
					raise Exception('sweep_range not specified')
		elif sweep_param=='MGT_line_freq':
			old_param_value=5000
			param_fn=lambda val: self.fpga.MGT_PLL.init(fout=val/16.0)
		else:
			print 'Parameter "%s" does not exist in MGT[%i]' %(sweep_param,sweep_port)
			raise Exception
		plt.figure(2)
		plt.clf()
		plt.hold(1)
		plt.grid(1)
		plt.figure(3)
		plt.clf()
		plt.hold(1)
		plt.grid(1)
		try:
			for param_value in sweep_range:
				rx.RX_RESET=1;
				rx.RX_RESET=0;
			
				param_fn(param_value) # set the sweep parameter

				offset=range(0,128,step);
				plt.figure(1)
				plt.clf()
				plt.hold(1)
				plt.axis([0,max(offset),-200,200])
				plt.ylabel('RX Differential amplitude (mV)') 
				eye_avg=np.zeros(len(offset));
				for j in range(Navg):
					eye=np.zeros(len(offset));
					for i in range(len(offset)):
						rx.RX_EYE_OFFSET=offset[i]
						eye[i]=rx.EYE_HEIGHT;
						#print '*'*eye[i]
					eye*=200./31
					eye_avg+=eye
					plt.plot(offset,eye,'r.')
					plt.plot(offset,-eye,'r.')
					plt.draw()
				eye_avg/=Navg
				plt.figure(2)
				plt.plot(offset,eye_avg,'k-')
				plt.plot(offset,-eye_avg,'k-')
				plt.draw()
				print '%s=%i, Eye max=%.1f mV' % (sweep_param, param_value, max(eye_avg))
				eye_max.append(max(eye_avg))
				plt.figure(3)
				plt.clf()
				plt.plot(sweep_range[:len(eye_max)],eye_max,'b.-')
				plt.draw()
				plt.xlabel(sweep_param)
				plt.ylabel('Eye opening (mV)')
		except KeyboardInterrupt:
			pass
		rx.RX_EYE_SCANMODE=0
		tx.TX_PRBS_MODE=0
		rx.RX_PRBS_MODE=0
		param_fn(old_param_value)