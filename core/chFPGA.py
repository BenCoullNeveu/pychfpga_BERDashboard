#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
chFPGA.py module 
 Implements interface to the CHIME chFPGA Proof of Concept board
 
 Provided methods:


#
# History:
# 2011-01-10 : JFC : First version
# 2011-04-30 JFC : Modified UDP.py into chFPGA.py to implement higher level communication system
# 2011-04 - 2011-08 JFC : Major modifications & cleanup
# 2011-08-29 JFC: Moved hex to util to solve circular import reference.
# 2012-03-27 JFC: Modified the read and write commands to support the new format following AXI4-Streaming implementation of the command bus
# 2012-05-29 JFC: Cleanup init. Support FMC board detection. Extracted test functions.
"""

import time
#import datetime
#import random
#import sys
#import select
import struct
import Queue
import threading
#import multiprocessing

import numpy as np
import matplotlib.pyplot as plt
#import pdb

import util
 
import Module

import SocketIO
# hardware subsystems handlers
import SPI
import I2C
import SYSMON
import SYSMOD
import FreqCtr
import REFCLK
import MGT

# SPI device handlers
import ADC
import IOExpander
import ADC_PLL
import AmbTemp
import BiasADC
import MGT_PLL

# I2C device handlers
import FMC_EEPROM
import ML605_PMBus


# Antenna processor handlers
import ANT
import ADCDAQ # Included only so it can be reloaded
import FRAMER # Included only so it can be reloaded
import FFT # Included only so it can be reloaded
import SCALER # Included only so it can be reloaded
import PROBER # Included only so it can be reloaded


# Correlator handlers
import CORR_BLOCK
import CH_DIST	# Included only so it can be reloaded


# -- Module reloader -- 
# Reload modules if we are debugging in case the source code has changed

reload_modules=(util,SocketIO,Module,SPI,I2C,SYSMOD,SYSMON,REFCLK,AmbTemp,FreqCtr,ADC,IOExpander,ADC_PLL,BiasADC,MGT_PLL,FMC_EEPROM,ML605_PMBus,ANT,ADCDAQ, FRAMER, FFT, SCALER, PROBER, CORR_BLOCK, CH_DIST, MGT)
	

for m in reload_modules: 
	print 'Reloading module %s' % (m.__name__)
	reload(m)



class Frame:
	def __init__(self, data):
		data=map(ord,data) # convert string to integer array
		self.probe_id = data[0]
		self.stream_id = (data[1]<<8) | data[2]
		self.flags = data[3]>>4
		self.word_length = ((data[3]&0x0F)<<8) | data[4]
		self.timestamp = (data[5]<<24) | (data[6]<<16) | (data[7]<<8) | data[8]
		self.data = data[9:]
		self.length = len(data)

# -- chFPGA -- 

class FrameReceiver(threading.Thread):		
	BUF_SIZE=32768
	data = bytearray(BUF_SIZE)
	data_buf=buffer(data)
	data_block = np.zeros((8,2048+9), dtype=np.uint8)
#		frame_block = {'timestamp' :0, 'data':frame_data}		
	queue_overflow = 0
	n_frames = 0
	
	def __init__(self, sock, queue, verbose = 1):
		self.sock = sock
		self.queue = frame_queue
		self._stop = threading.Event()
		self.verbose = verbose
		self.print_delay = 1
		super(type(self), self).__init__()
	
	def stop(self):
		self._stop.set()


	def is_stopped(self):
		return self._stop.is_set()

	def run(self):
	#	timeout=1
	#	frame_array=[]
		last_timestamp = 0
	#	last_delta = 0
		n = 0
		#t0 = time.time()
		#last_display_time = t0
#			expected_delta=self.ANT[0].PROBER.get_burst_period()
#			missing_frames = 0
#			bad_delta = 0
	#	data2 = bytearray(buf_size)		
		self.sock.settimeout(0.1)
		print 'Frame acquisition thread is running'
		while not self._stop.is_set():
			#data = self.sock.read_data(timeout_delay=timeout)
			# Read data from the UDP listening port
			try:
				nbytes = self.sock.recv_into(self.data)
			except SocketIO.timeout:
				nbytes = 0

			if nbytes:
				self.n_frames += 1
				(probe_id, stream_id, word_length, timestamp) = struct.unpack_from('>BHHL', self.data_buf)


				if timestamp != last_timestamp:
					if n:
						try:
							self.queue.put_nowait((timestamp, self.data_block[0:n,:].copy()))
						except Queue.Full:
							self.queue_overflow += 1
					last_timestamp = timestamp
					n = 0
				# Copy the new vector into the block memory buffer
				self.data_block[n,:] = self.data[:2048+9]					
				n += 1
		print 'Frame acquisition thread is stopped'

	def status(self, print_delay=1):
		last_display_time = 0
		try:
			while True:
				t = time.time()						
				dt = t-last_display_time
				if dt > print_delay:
					print 'Received %i frames at %f frames/s (%f Mb/s), buffer size = %i, overflows= %i' % (self.n_frames, self.n_frames/dt, self.n_frames/dt*(2048+9)*8/1e6,  self.queue.qsize(), self.queue_overflow)
					last_display_time = t
					self.n_frames = 0
		except KeyboardInterrupt:
			pass

frame_queue = Queue.Queue(maxsize=1000)
	

class chFPGA:

	# Basic system parameters
	NUMBER_OF_CORRELATORS = 1
	NUMBER_OF_ANTENNAS = 8
	LOG2_FRAME_LENGTH = 11
	FRAME_LENGTH = 2**LOG2_FRAME_LENGTH # 2**11 = 2048 time samples per frame
	ADC_CLK_SELECT = 1 # Antenna number from which the antenna processing will be clocked. This is hardwired in the firmware (need to use an ADCDAQ with a PLL)	
	SAMPLING_FREQUENCY = 800e6 # in Hz
	REFERENCE_FREQUENCY = 10e6 # in Hz
	SYSTEM_CLOCK_FREQUENCY = 200e6 # in Hz
	FRAME_HEADER_LENGTH = 9
	FRAME_PERIOD = float(FRAME_LENGTH)/SAMPLING_FREQUENCY
	
	# Port numbers
	ANT_PORT=range(NUMBER_OF_ANTENNAS) # Antennas are ports 0-7
	SYSTEM_PORT = NUMBER_OF_ANTENNAS
	CORR_PORT = NUMBER_OF_ANTENNAS+1
	#MGT_PORT = NUMBER_OF_ANTENNAS+2 -- for future use, if needed


	# SYSTEM Modules
	SYSTEM_SPI_MODULE=0
	SYSTEM_SYSMON_MODULE=1
	SYSTEM_FREQ_CTR_MODULE=2
	SYSTEM_SYSMOD_MODULE=3
	SYSTEM_REFCLK_MODULE=4
	SYSTEM_I2C_MODULE=5


	FMC_present=False # indicates if the FMC board is present. If not, the modules will act accordingly.

#	class FrameReceiver(threading.Thread):		

	def __init__(self, adc_test_mode=0, adc_delay_table=None, fref=10, verbose=2):

		print '*** Opening sockets ***'
		# Create socket handled and open socket communications to the chFPGA board
		self.sock=SocketIO.SocketIO_base()
		self.sock.open()

		try: # catch initialization errors so we can free the socket for future instantiation
			print '*** Instantiating modules ***'
			# Create handware handling objects 
			#  NOTE: Does not initialize them yet because some modules are interdependent - we need to wait until all of them are instantiated.
			#  NOTE: The instantiation does not initiate communicattion with the hardware yet. this is done in the INIT phase.
	
	
			if verbose>=2: print '  - SYSMOD'
			self.SYSMOD=SYSMOD.SYSMOD_base(self)
			if verbose>=2: print '  - I2C'
			self.I2C=I2C.I2C_base(self)
			if verbose>=2: print '  - SYSMON'
			self.SYSMON=SYSMON.SYSMON_base(self)
			if verbose>=2: print '  - SPI'
			self.SPI=SPI.SPI_base(self)
			if verbose>=2: print '  - FreqCtr'
			self.FreqCtr=FreqCtr.FreqCtr_base(self)
			if verbose>=2: print '  - REFCLK'
			self.REFCLK=REFCLK.REFCLK_base(self)
	
			#if verbose>=2: print '  - MGT'
			#self.MGT=MGT.MGT_base(self)
	
			if verbose>=2: print '  - ADC'
			self.ADC=ADC.ADC_base(self)
			if verbose>=2: print '  - IOExpander'
			self.IOExpander=IOExpander.IOExpander_base(self)
			if verbose>=2: print '  - ADC_PLL'
			self.ADC_PLL=ADC_PLL.ADC_PLL_base(self)
			if verbose>=2: print '  - AmbTemp'
			self.AmbTemp=AmbTemp.AmbTemp_base(self)
			if verbose>=2: print '  - MGT_PLL'
			self.MGT_PLL=MGT_PLL.MGT_PLL_base(self)
			if verbose>=2: print '  - BiasADC'
			self.BiasADC=BiasADC.BiasADC_base(self)
			if verbose>=2: print '  - FMC EEPROM'
			self.FMC_EEPROM=FMC_EEPROM.FMC_EEPROM_base(self)
			if verbose>=2: print '  - ML605 PMBus'
			self.ML605_PMBus=ML605_PMBus.ML605_PMBus_base(self)
	
			if verbose>=2: print '  - ANT'
			self.ANT=ANT.ANT_base(self)
	
			if verbose>=2: print '  - CORR'
			self.CORR=CORR_BLOCK.CORR_base(self)
	
			# Initialize subsystems. This has to be done only once all subsystems are created because some subsystems depend on each other.
			print '*** Initializing modules ***'
	
			if verbose>=2: print '  - SYSMOD'
			self.SYSMOD.init() # This stops the antenna procesors from sending data. Neeeded if the FPGA is flooding the buffers which prevent subsequent reads to come through
			self.sock.flush_data_socket() # Now the the data stops coming, flush the buffers
			self.sock.flush_control_socket()
			self.SYSMOD.status()
	
			if verbose>=2: print '  - I2C'
			self.I2C.init()
	
	
			if verbose>=2: print '  - ML605 PMBus'
			self.ML605_PMBus.init()
			self.ML605_PMBus.status()
	
	
			if verbose>=2: print '  - EEPROM'
			self.FMC_EEPROM.init()
			self.FMC_EEPROM.status()
	
			self.FMC_present=self.FMC_EEPROM.FMC_present(verbose=True)
	
			 # Module depend on the FMC_present flag after this point
	
			if verbose>=2: print '  - REFCLK'
			self.REFCLK.init()
			self.REFCLK.status()
	
			if verbose>=2: print '  - SYSMON'
			self.SYSMON.init()
			self.SYSMON.status()
	
			if verbose>=2: print '  - SPI'
			self.SPI.init()
			self.SPI.status()
	
			if verbose>=2: print '  - AmbTemp'
			self.AmbTemp.init()
			self.AmbTemp.status()
	
	
			if verbose>=2: print '  - IOExpander'
			self.IOExpander.init()
			self.IOExpander.status()
	
			if verbose>=2: print '  - ADC_PLL'
			self.ADC_PLL.init(fout=2*self.SAMPLING_FREQUENCY/1e6, fref=self.REFERENCE_FREQUENCY/1e6, verbose=1)
			self.ADC_PLL.status()
	
			if verbose>=2: print '  - ADC'
			self.ADC.init(test_mode=adc_test_mode)
			self.ADC.status()
	
			if verbose>=2: print '  - ANT'
			self.ANT.init(delay_table=adc_delay_table)
			self.ANT.status()
	
			if verbose>=2: print '  - CORR'
			self.CORR.init()
			self.CORR.status()
	
			# MGT is disabled	
			#print '  - MGT_PLL'
			#self.MGT_PLL.init(fref=fref)
			#print '  - MGT'
			#self.MGT.init() # MGT_PLL must be initialized first
			if verbose>=2: print '  - Done with initializations'
	
			#print '*** Setting ADCDAQ delays ***'
	
			#if adc_delay_table:
			#	self.ANT.set_delays(adc_delay_table)
	
			print '*** Set ADC mode ***'
	
			self.set_ADC_mode('data')
			print '*** End of chFPGA initialization ***'
	
			# Create a frame a queue and a thread that will fill it
			#self.frame_queue = multiprocessing.Queue(maxsize=1000)
			self.frame_receiver = FrameReceiver(self.sock.sock_data, frame_queue, verbose=0)
			self.frame_receiver.start()
		except:
			self.close()
			raise
	def __del__(self):

		self.close()
		print '__del__: Closed FPGA at IP address %s' % self.SocketIO.OUT_IP

	def close(self):
		""" 
		Close chFPGA object, which releases the socket bindings
		"""
		self.frame_receiver.stop()
		self.frame_receiver.join()
		self.sock.close()

	def read(self,ant,module,addr,type=np.dtype('>u1'),length=1, incr=1):
		""" Reads memory-mapped byte(s) from the FPGA through the Ethernet interface.
		Returns a numpy array where the bytes are intrepreted as a series of 'length' elements of type 'type'.
		"""

		itemsize=np.dtype(type).itemsize # number of bytes contained in the destinaion vector type
		dout=np.zeros(length*itemsize,np.int8) # initialize result vector as a byte array
		NBYTES=0
		# Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))
		for i in range(length*itemsize): 
			s=chr(0x00+(NBYTES<<3)+(ant>>2))+chr(((ant&0x03)<<6)+(module<<2)+(addr>>8))+chr(addr&0xff)
			self.sock.write_control(s)
			data=self.sock.read_control()
			#if data[0]!=s[0]:
			#	print "Read: ERROR: Returned ANT/SUB/ADDR (",data[0:2]," does not match request values (",s[0:2],")"
			if len(data)!=2:
				print "Read: ERROR: %i bytes were returned" % len(data)
			dout[i]=ord(data[1]) # store received byte
			if incr: addr+=1
		dout.dtype=np.dtype(type) # change interpretation of the byte array into a 'type' array

		#if we requested a single value (length=1), returns the object, otherwise return a numpy array of objects
		if len(dout)==1:
			return dout[0]
		else:
			return dout
		
	
	def write(self,ant,module,addr,data,incr=1,mask=0xff):
		""" 
		Writes byte(s) to memory-mapped registers in the FPGA through the Ethernet interface.
		'data' can be:
			- String
			- list of integers between 0 and 255
			- numpy array of integers between 0 and 255
			- 4 bytes in a numpy uint32. MSB is transmitted first
			- 2 bytes in a numpy uint16. MSB is transmitted first
			- 1 byte in a numpy uint8. 
		"""
		# build command packet
		#s=chr(0x80+ant+(0x40 if incr else 0))+chr((module<<2)+(addr>>8))+chr(addr&0xFF) 
		NBYTES=0
		s=chr(0x80+(0x40 if incr else 0)+(NBYTES<<3)+(ant>>2))+chr(((ant&0x03)<<6)+(module<<2)+(addr>>8))+chr(addr&0xff)

		# Add the data to the string. The method depends on the data type
		if type(data)==str:
			s+=data
			length=len(data)
		elif type(data)==list or type(data)==np.ndarray:
			s+=''.join([chr(data[i]) for i in range(len(data))])
			length=len(data)
		elif type(data)==np.uint32:
			length=4;
			a=np.array([data],np.dtype('>u4')) # store as big endian (most significant byte first)
			a.dtype=np.uint8
			s+=''.join([chr(a[i]) for i in range(4)])
		elif type(data)==np.uint16:
			length=2;
			a=np.array([data],np.dtype('>u2')) # store as big endian (most significant byte first)
			a.dtype=np.uint8
			s+=''.join([chr(a[i]) for i in range(2)])
		elif type([data])==np.uint8:
			length=1;
			a=np.array([data]); # store as big endian (most significant byte first)
			a.dtype=np.uint8
			s+=chr(a[i])
		else:
			s=s+chr(data);
			length=1
		self.sock.write_control(s)
		return length
		

	# Define Read and Write for legacy compatibility
	Read=read
	Write=write

	def read_bit(self,port,module,addr,bit):
		return (self.read(port,module,addr) & (1<<bit))!=0

	def write_bit(self,port,module,addr,bit,data):
		old_data=self.read(port,module,addr)
		mask=1<<bit
		self.write(port,module, addr, (old_data & (~mask)) | (mask if data else 0))

	def write_mask(self,port,module,addr,mask,data):
		old_data=self.read(port,module,addr)
		self.write(port,module, addr, (old_data & (~mask)) | (mask & data))

	def pulse_bit(self,port,module,addr,bit):
		old_data=self.read(port,module,addr)
		mask=1<<bit
		self.write(port,module, addr, (old_data | mask))
		self.write(port,module, addr, (old_data & (~mask)))

	def read_frame(self,*args,**kwargs):
		return self.sock.read_data(*args,**kwargs);


	def plot_ADC_eye_diagram(self, channel=0):

		ant=self.ANT[channel]
		m=np.zeros((32,1024),np.uint8)
		old_delays=ant.ADCDAQ.read_delay()
		plt.figure(2)
		plt.clf()
		plt.plot(old_delays,np.arange(8),'ro')
		plt.hold(1)
		plt.draw()
		for dly in range(32):
			ant.ADCDAQ.set_delay([dly]*8,reset=0)
			a=self.read_ADC_frame(channels=[channel],length=1024);
			#m[dly,:]=[ 1 if a[i]&(1<<bit) else 0 for i in xrange(len(a))]
			m[dly,:]=a[channel]
			#print ' Delay %2i : %s' % (dly, ''.join([ '|' if a[i]&(1<<bit) else '.' for i in xrange(160)])) 
		ant.ADCDAQ.set_delay(old_delays); # restore original delays
		for b in range(8):
			mm=np.array(m & (1<<b),dtype=bool) # select desired bit
			ix=np.where(np.diff(mm,axis=0)) # find indexes of all transitions (dly ix,sample ix)
			
			xx=np.row_stack((ix[0],ix[0]+1))
			yy=np.row_stack((mm[ix],mm[ix[0]+1,ix[1]]))*0.4-0.2 +b
			plt.plot(np.arange(0,32),(m[:,:(2**b)*4] & (1<<b)!=0 )*0.4-0.2 +b,'r.-')
			#plt.plot(xx,yy,'b.-')
			print('Bit %i, %i points' % (b,len(ix[0])))
			#plt.plot(np.arange(0,32),(m[:,:(2**b)*4] & (1<<b)!=0 )*0.4-0.2 +b,'r.-')
			plt.draw()
		plt.xlabel('Tap delay #');
		plt.ylabel('Bit #');
		
		#plt.figure(1)
		#plt.clf()
		#plt.imshow((m & (1<<bit))!=0,aspect='auto', interpolation='nearest', cmap=plt.gray(), filternorm=1)
		#plt.draw()

	def read_eye_diagram(self,channels=[0], offset=5):
		self.set_ADC_mode('pulse') # generate pulse pattern

		data={}
		for ch in channels:
			d=np.zeros((32,3),dtype=np.uint8)
			print 'Reading channel %i' % (ch)
			adcdaq=self.ANT[ch].ADCDAQ

			#adcdaq.CAPTURE_ALIGN=1 # first capture will be done while aligning bits
			for dly in range(32):
				#print '  Acquiring pattern for delay %i' % (dly)
				#dly=0
				adcdaq.set_delay(dly)
				#adcdaq.pulse_bit('CAPTURE_TRIG')
				#adcdaq.wait_for_bit('CAPTURE_DONE')
				#d[dly,:]=adcdaq.read(0x8B, type=np.uint8, length=3)
				d[dly,:]=self.ANT[ch].ADCDAQ.get_pattern(period=11)[offset:offset+3];
				#adcdaq.CAPTURE_ALIGN=0 # we no longer want to align the following captures so we can track the bits moving with the delays
			data[ch]=d
			#if np.sum(d[:,1])==0: raise
		return data

	def scan_delay(self,channels=[0],bit=0,phase=[0],delay=range(32),sync=1):
		self.set_ADC_mode('pulse',sync=0) # generate pulse pattern, and sets CAPTURE period
		for ch in channels:
			print 'Reading channel %i' % (ch)
			adcdaq=self.ANT[ch].ADCDAQ

			for p in phase:
				self.ANT[1].ADCDAQ.set_divclk_phase(p)
				self.sync() # make sure the capture now restarts properly with the right period and we recover fromm the PLL reset caused by phase change
				for d in delay:
					adcdaq.set_delay(d)
					if sync: self.sync()
					time.sleep(0.1)
					data=adcdaq.get_pattern(period=11)
					print 'CH%i DIVCLK phase: %2i, delay=%2i Bit %i: %s' % (ch,p,d,bit, ''.join(('0','1')[bool(d&(1<<bit))] for d in data))

	def scan_divclk_phase(self,channel=0, bit=None):
		self.ADC.set_test_mode(2) # generate pulse pattern
		ch=channel
		for phase in range(32):
			self.sync()
			time.sleep(0.1)
			data= self.ANT[ch].ADCDAQ.get_pattern(period=11);
			if bit is None:
				print 'DIVCLK Phase=%2i CH%i:' % (phase,ch), data
			else:
				print 'DIVCLK Phase=%2i CH%i Bit %i: %s' % (phase,ch,bit, ''.join(('0','1')[bool(d&(1<<bit))] for d in data))

	def compute_delays(self,channels=[0], offset=5):
		data=self.read_eye_diagram(channels, offset=offset)
		n=np.zeros((8,3),dtype=np.uint8)
		delays={}

		for ch in channels:
			for bit in range(8):
				mask=1<<bit
				n[bit,:]=np.sum((data[ch] & mask)/mask,axis=0)
			#print 'n is ', n

			n_min=np.min(n,axis=0) # minimum number of delay values that allowed the pulse in each slot
			N=np.argmax(n_min) # slot with the maximum number of possible delays for all bits
			N=1
			print 'Aligning bits on sample #%i' % N

			print 'CHANNEL %i' % ch
			m=np.zeros(8,dtype=np.uint8)
			for bit in range(8):
				mask=1<<bit
				d=(data[ch][:,0] & mask)/mask
				m[bit]=np.sum(d*range(32))/np.sum(d)
				print 'Bit %i:' % bit, ''.join('.#!O'[d[i] +2*bool(m[bit]==i)] for i in range(len(d))), 'Delay = %2i' % m[bit]

			delays[ch]=m

		return delays

	def print_phase(self,channels=range(8), bit=None):
		for phase in range(64):
			self.ANT[1].ADCDAQ.set_divclk_phase(phase)
			a= self.read_ADC_frame(channels=channels,reset=1,simulate=0,raw=1,verbose=0);
			for (ch,data) in a.iteritems():
				if bit is None:
					print 'DIVCLK Phase=%2i CH%i:' % (phase,ch), data[:10]
				else:
					print 'DIVCLK Phase=%2i CH%i Bit %i: %s' % (phase,ch,bit, ''.join(('0','1')[bool(d&(1<<bit))] for d in data[:32]))

	def scan_phase(self):
		for phase in range(0,200,5):
			#for i in range(10):
				self.sync(phase=phase,verbose=0)
				s=self.REFCLK.scan_refclk_delay()
				print ' Phase %i, %s' % (phase, self.REFCLK.bit_vector_to_string(s))
				time.sleep(0.01)
			#raw_input('Press [ENTER]')


	def ADC_plot_map(self, channel=0,bit=0):

		old_delays=self.ADC_read_delay(channel)
		m=np.zeros((32,1024),np.uint8)
		for dly in range(32):
			self.ADC_set_delay(channel,[dly]*8)
			m[dly,:]=self.ADC_Read_Frame(channel,length=1024);

		self.ADC_set_delay(channel,old_delays); # restore original delays
		plt.figure(1)
		plt.clf()
		plt.imshow((m & (1<<bit))!=0,aspect='auto', interpolation='nearest', cmap=plt.gray(), filternorm=1)
		plt.draw()
		
	def ADC_plot_frame_bits(self, channel=0, delay=None, simulate=0):

		old_delays=self.ADC_read_delay(channel)
		if delay:
			self.ADC_set_delay(channel,delay)

		plt.figure(4)
		plt.clf()
		plt.hold(1)
#		self.ADC_set_delay(adc,dly)
		a=self.ADC_Read_Frame(channel,length=1024,simulate=simulate);
		if delay:
			self.ADC_set_delay(channel,old_delays); # restore original delays
		for bit in range(8):
			plt.plot(((a & (1<<bit))!=0) +2*bit,'b.-')
#			hold(1)
		plt.draw()

	def ADC_check_frames(self, channel=0, frames=16, delay=None, verbose=0):
		if np.iterable(channel): #110906 JFC
			channel_list=channel
		else:
			channel_list=[channel]
		for ch in channel_list:
			print '*** Processing channel %i ****' % ch, 
			old_delays=self.ADC_read_delay(ch)
			if delay is not None:
				self.ADC_set_delay(ch,delay)

			a=self.ADC_Read_Frame(ch,length=1024);
			a0=(np.arange(1024)+a[0]) % 256;
			passed=0
			failed=0;
			try:
				for i in xrange(frames):
					a=self.ADC_Read_Frame(ch,length=1024);
					if (a==a0).all():
						passed+=1
						if (i % 100)==0:
							if verbose:
								print 'Frame %i match'  % (i)
							else:
								print '.',
					else:
						if verbose:
							print '** Frame %i DO NOT match'  % (i)
						else:
							print '!',
						failed+=1
			except KeyboardInterrupt:
					pass
			self.ADC_set_delay(ch,old_delays); # restore original delays
			print ' Channel %i: Pass: %i (%.2f%%), fail: %i (%.2f%%)' % (ch, passed, passed*100.0/(passed+failed), failed, failed*100.0/(passed+failed))

	def sync(self, continuous=0, sleep=0,phase=None,delay=None,plot=0,verbose=0,local=1):
		if phase is not None:
			self.ADC_PLL.init(phase=phase,verbose=verbose)
		if plot:
			plt.figure(1)
			plt.clf()
			plt.hold(1)
			plt.axis([0,32,-1,2])
			
		try:
			while 1:
				if verbose:
					print 'Sync...'
				if local:
					self.REFCLK.local_sync(delay=delay)
				else:
					self.REFCLK.sync(delay=delay)

				s=self.REFCLK.scan_refclk_delay()
				if verbose:
					self.REFCLK.print_bit_vector(s)
				if plot:
					plt.plot(s)
					plt.draw()
				if not continuous: break
				time.sleep(sleep)
		except KeyboardInterrupt:
			pass

	DATA_SOURCE_NAMES = {
		# name, source_sel, adcdaq_ramp, adc
		'func_zero' : (0, None), # All bytes are zero
		'func_one' : (1, None), # All bytes are one
		'func_ramp': (2, None), # Successive bytes generate a repeating ramp from 0 to 255
		'func_real_ramp' : (3, None), # Generates a complex ramp from 0+0i to 255+0i on each successive (8+8) bits complex values (the imaginary part is always zero). 
		'inject' : (6, None), # Takes the data from the data injection FIFO
		'adcdaq_data' : (7, False),  # takes the data from the ADC. Use set_adc_mode() to choose whether the ADC sends data, a ramp or pulses.
		'adcdaq_ramp' : (7, True), # takes a ramp generated by the ADCDAQ
		}	


	def set_data_source(self, source="adcdaq_data", channels=range(8)):
		
		if source in self.DATA_SOURCE_NAMES:
			source_info = self.DATA_SOURCE_NAMES[source.lower()]
			source_sel = source_info[0]			
			adcdaq_ramp = source_info[1]
			
		else:
			raise Exception('Invalid data source')
			
		for ch in channels:
			ant = self.ANT[ch]
			ant.FR_DIST.DATA_SOURCE = source_sel
			ant.FR_DIST.reset_fifo() # if this automatically reset by SYNC now?
			if adcdaq_ramp is not None:
				ant.ADCDAQ.ENABLE_RAMP = adcdaq_ramp

	ADC_MODE_NAMES = {
		# name, mode number, period
		'data' : (0, 64), # All bytes are zero
		'ramp' : (1, 64), # All bytes are one
		'pulse': (2, 11), # Successive bytes generate a repeating ramp from 0 to 255
		}	

	def set_ADC_mode(self, channels=range(8), mode='data', sync=1):
		"""
		Sets the test mode of both ADCs, sets the proper CAPTURE period, and sends a SYNC.
			test_mode:
				'data': Normal mode (ADC output contains analog samples)
				'ramp': Ramp mode (ADC output contains repeating 0-255 pattern. Note that ADCDAQ inverts bit 7 during acquisition to convert offset binary to 2's complement binary)
				'pulse': Strobe mode (ADC output contains one 0xFF followed by ten 0x00. It repeats with a pariod of 11. Same comment as above)
		111212 JFC: Added this high-level function with string mode.
		"""

		mode_info = self.ADC_MODE_NAMES[mode.lower()]
		mode_value = mode_info[0]
		capture_period = mode_info[1]

		self.ADC.set_test_mode(test_mode=mode_value)
		self.current_ADC_mode = mode_value

		for ant in self.ANT:
			ant.ADCDAQ.CAPTURE2_PERIOD = capture_period # set the period so we are ready to capture data correctly after the SYNC resets the CAPTURE logic

		self.sync() # make sure the ADC mode is set and that capture  restarts properly with the right period


	def set_data_capture(self, source=None, channels=range(NUMBER_OF_ANTENNAS), frames_per_burst=1, burst_period=1.0/FRAME_PERIOD, number_of_bursts=0, sync=1, verbose=1):
		"""
		Triggers the capture of the specified number of frames in the FPGA for transmission over the Ethernet port. 
		This function does not receive the frames from the ethernet port. This has to be done separately.
		"""
		if verbose:
			print 'Configuring antennas %s to transmit %i-frame burst every %i frames (i.e .every %.3f ms) %s' %  (
				channels.__repr__(),
				frames_per_burst, 
				burst_period, 
				burst_period*self.FRAME_PERIOD*1000, 
				('continuously when TRIG=1' if not number_of_bursts else 'for a total of %i bursts' % number_of_bursts ) ) 
			frames_per_second = len(channels)*frames_per_burst*1.0/self.FRAME_PERIOD
			bits_per_second = frames_per_second * 8 * self.FRAME_LENGTH
			print 'Data rates are: %f Frames/s, %f Mbits/s' % (frames_per_second, bits_per_second/1e6)

		self.SYSMOD.GLOBAL_TRIG=0 # disable data transmission if continuous mode is currentlly selected
		self.SYSMOD.ANT_RESET=1 # resets all 
		self.sock.flush_data_socket()
		if source is not None:
			pass
		
		for ant in self.ANT:
			ant.PROBER.RESET=1
			ant.PROBER.PROBE_ID = 0xA0+ant.ant_number
			ant.PROBER.config_capture(frames_per_burst=frames_per_burst, burst_period=int(burst_period), number_of_bursts=number_of_bursts)
			if ant.ant_number in channels:
				print 'Enabling Capture for Antenna %i' % ant.ant_number
				ant.PROBER.RESET = 0

		self.SYSMOD.GLOBAL_TRIG = 1 # enables data transmission if continuous mode is selected
		self.SYSMOD.ANT_RESET = 0 # disable reset all 
				
			
	def read_frames(self, frames=1, verbose=1, raw=0, flush=0):
		"""
		Get frames that were captured by the capture thread.

		Parameters:
			frames: Number of frames to acquire per channel. Limited by the buffer lengths in the FPGA
			raw: when true, returns the unsigned raw data from the ADC (bit 7 is not inverted)
		History:
			110916 JFC: Added comments. 
				Changed output format to dictionnary of arrays instead of bidimentional array.
				Now use global trigger to support multi-channel
			120713 JFC: Changed name to from read_ADC_frames to get_frames. Rewritten for new frame acquisition architecture 
		"""

		# Acquire the data
		data={}
		if flush:
			with frame_queue.mutex:
				frame_queue.queue.clear()
			
		for j in range(frames):
		#j=0
		#while 1:
			#j+=1
			if verbose>1 or (verbose==1 and (j % 100 ==99 or j==frames-1)):
				print 'Acquiring Frame %i (%.0f%%)' % ((j+1),(100*(j+1)/frames))
			#try:
			data_block = frame_queue.get(timeout=10)
			#except Queue.`:
			#	return None
				
			block_timestamp = data_block[0]
			in_frames =  data_block[1]
			
			data['timestamp'] = block_timestamp
			
			for in_frame in in_frames[:]:
				

				if(len(in_frame) < self.FRAME_HEADER_LENGTH):
					print 'Bad header'
					break
				else:	
					(probe_id, stream_id, word_length, timestamp) = struct.unpack_from('>BHHL', in_frame)
					channel = probe_id & 0x0F
				
				if(len(in_frame) != self.FRAME_LENGTH+self.FRAME_HEADER_LENGTH):
					print 'Frame too short'
					break
		
				# Process the frame data
	
				raw_data=in_frame[self.FRAME_HEADER_LENGTH:]
				raw_data.dtype=np.int8 # ADC output are signed values
	
				if raw:
					raw_data.dtype=np.uint8
					raw_data^=0x80
	
				if verbose:
					#print 'Packet received from port %i. Frame header information:  Valid frame #=%i, Frame #=%i, Frame length=%i words, trigger count=%i' % (channel_number, ant_number, frame_valid_ctr, frame_ctr, frame_length,self.ANT[ch].FR_DIST.TRIG_COUNT)
					#print data
					pass
				# Make sure there is an empty vector on the first storage so we can concatenate to it the new data
				
				if channel not in data:
					data[channel]=raw_data
				else:
					data[channel]=np.hstack((data[channel],raw_data));
		return data		

	def plot_ADC_frame(self, channel=0, hold=0, frames=1, continuous=0, raw=0, flush=0):
		""" Plots incoming frames """
		#if isinstance(channels,int): # make sure that channel is a list of channels
		#	channels=[channels]

		continuous |= (frames == 0) # plots continuously if frames=0
		
		
		plt.figure(5)
		plt.clf()
		plt.hold(hold)
		plt.show()

		number_of_frames = 0
		ymax = 1
		try:
			while (continuous == 1) or (number_of_frames < frames):
				try:
					print 'Reading data...'
					#sync_again=(number_of_frames==0) or bool(reset)
					a = self.read_frames(raw=raw, flush=flush) #(number_of_frames==0)
					flush = 0
					ch1_data = a[channel]
					number_of_frames += 1
					
					aamax = max(abs(ch1_data))
					ymax = max(ymax*.99, aamax)
					plt.plot(ch1_data, 'b.-')
					plt.draw()
				except:
					raise
		except KeyboardInterrupt:
			pass
		print 'Plotted %i frames' % number_of_frames


	def save_frames(self, filename, channels=0, frames=1, raw=0):
		""" Save incoming frames to disk """
		if filename:
			file=open(filename,'w')
		else:
			file=None

		if isinstance(channels,int): # make sure that channel is a list of channels
			channels=[channels]

		number_of_frames=0
		try:
			while (continuous==1) or (number_of_frames<frames):
				try:
					print 'Reading data...'
					#sync_again=(number_of_frames==0) or bool(reset)
					a=self.read_frames(raw=raw) #(number_of_frames==0)
					ch1_data=a[ch1][:length]
					number_of_frames+=1
					file.write(np.int8(ch1_data))
				except:
					raise
		except KeyboardInterrupt:
			pass
		if file:
			file.close()
		print 'Saved %i frames' % number_of_frames
		
		
	def plot_ADC_frame_fft(self, channels=0, hold=0, frames=1, continuous=0,xmax=1023, sync_period=None, fft=1, out_shift=0, fft_shift=None, filename=None,simulate=0, contiguousFrames=1, length=1024):
		'''
		20120220KMB: added contiguous frames support
		20110906KMB:  added fft plotting
		20110909KMB: changed save to be npy files. other gave anomolous results.
		20110919KMB:  got rid of correlation, added support for any number of channels
		'''
		#if filename:
		data_list = []
		#	#file=open(filename,'w')
		#else:
		#	#file=None
		if type(channels) is int: # make sure that 'channels' is a list
			channels=[channels];
		nchan = len(channels)
		plt.figure(5, figsize=(6*nchan,6))
		plt.ion()
		#if not hold:
		plt.clf()
		plt.hold(hold)
		plt.show()

		
		chanIndex = range(nchan)
		plotFFTObject = range(nchan)
		plotObject = range(nchan)
		
		if fft:
			#f=np.arange(1024)*1024.0/800.0
			f=np.fft.fftfreq(length*contiguousFrames,1/800.0)
			zeros=np.zeros(len(f))
			for chanNum in chanIndex:
				plt.subplot(2,nchan,chanNum+1)
				plt.title('Spectrum')
				plt.xlabel('Frequency (MHz)')
				plt.ylabel('Amplitude')
				plotFFTObject[chanNum], = plt.plot(f,zeros ,'b.-')
				plt.subplot(2,nchan,nchan+chanNum+1)
				plt.title('Timestream')
				plt.xlabel('sample')
				plt.ylabel('Amplitude')
				plotObject[chanNum], = plt.plot(zeros ,'b.-')

		
		mult_chan = nchan>1

		#corr_sum=np.zeros(512,dtype=complex)
		number_of_frames=0

		
		ymax=1
#		if fft:
#			self.FFTinit(ant=channel,sync_period=sync_period, out_shift=out_shift, fft_shift=fft_shift);
		try:
			while (frames==0) or (frames!=0 and number_of_frames<frames):
				try:
					a=self.read_ADC_frame(channels, length=length,sync=(number_of_frames==0),fft=0,simulate=simulate, frames=contiguousFrames) #(number_of_frames==0)
					print a
					#print f, f.shape
					fa = np.zeros((nchan,len(a[channels[0]])))
					if fft:
						for chanNum in chanIndex:
							fa[chanNum] = np.fft.fft(a[channels[chanNum]])#[:512]

					number_of_frames+=1
					
					aamax=max(abs(a[channels[0]]))
					ymax=max(ymax*.99,aamax)
					fmax = f.max()
					ftmax = 10*np.log10(np.abs(fa)**2).max()
					
					if fft:
						for chanNum in chanIndex:
							plt.subplot(2,nchan,chanNum+1);
							plotFFTObject[chanNum].set_ydata(10*np.log10(np.abs(fa[chanNum])**2))
							###plt.plot(f,10*np.log10(np.abs(fa[chanNum])**2) ,'b.-')
							#plt.axis([0,fmax,0,ftmax])
							plt.ylim(0,100)
							plt.subplot(2,nchan,nchan+chanNum+1);
							###plt.plot(a[channels[chanNum]] ,'b.-')
							plotObject[chanNum].set_ydata(a[channels[chanNum]])
							#plt.axis([0,xmax,-ymax,ymax])
							plt.axis([0,xmax,-128,127])
							#plt.draw()
					else:
						for chanNum in chanIndex:
							plt.subplot(2,nchan,chanNum)
							plt.plot(a[channels[chanNum]],'b.-')
							plt.axis([0,xmax,-ymax,ymax])
							#plt.axis([0,xmax,-70,70])
					plt.draw()
					if filename:
						for chanNum in chanIndex:
							data_list.append(a[channels[chanNum]])
							#file.write(np.int8(a[ch1,:]))
				except:
					raise
		except KeyboardInterrupt:
			pass
		if filename:
			np.array(data_list)
			np.save(filename,data_list)
			#file.close()
		print 'Plotted %i frames' % number_of_frames
	
	def save_ADC_frames(self, channels=0, verbose=0, frames=1, continuous=0,xmax=1023, sync_period=None, out_shift=0, fft_shift=None, filename=None,simulate=0, contiguousFrames=1, length=1024):	
		'''
		20120521KMB: created to just save stream data without plotting 
		'''
		#if filename:
		data_list = []
		#	#file=open(filename,'w')
		#else:
		#	#file=None
		if type(channels) is int: # make sure that 'channels' is a list
			channels=[channels];
		nchan = len(channels)
		chanIndex = range(nchan)

		
		mult_chan = nchan>1

		#corr_sum=np.zeros(512,dtype=complex)
		number_of_frames=0

		
		ymax=1
#		if fft:
#			self.FFTinit(ant=channel,sync_period=sync_period, out_shift=out_shift, fft_shift=fft_shift);
		try:
			self.setup_ADC(channels, length=length, frames=contiguousFrames)
			while (frames==0) or (frames!=0 and number_of_frames<frames):
				try:
					a=self.read_ADC_frame_simple(channels,length=length, frames=contiguousFrames) #(number_of_frames==0)
					#print a
					number_of_frames+=1					
					if filename:
						for chanNum in chanIndex:
							data_list.append(a[channels[chanNum]])
							#file.write(np.int8(a[ch1,:]))
				except:
					raise
		except KeyboardInterrupt:
			pass
		if filename:
			np.array(data_list)
			np.save(filename,data_list)
			#file.close()
		print 'Saved %i frames' % number_of_frames
	
	def setup_ADC(self, channels=0, length=1024, frames=1):
		self.sock.flush_data_socket()
		self.sync()
		length=((length+3)//4)*4;
		if isinstance(channels,int): # make sure that channel is a list of channels
			channels=[channels]
		# Disable frame transmission for all antennas. Those thar are selected will be set-up later.
		for ant in self.ANT:
			ant.FR_DIST.TRIG_FRAME_COUNT=0 # Disable response to global trigger for all channnels by default. The requested ones will be re-enabled later. 

		for ch in channels:
			ant=self.ANT[ch]
			ant.ADCDAQ.ENABLE_RAMP=0
			ant.FR_DIST.DSP_DATA_SRC_ADC=1 # Source is ADC DAQ

			ant.CH_DIST.pulse_bit('RESET') # Make sure the CH_DIST buffers are empty
			ant.FR_DIST.reset_fifo() # if this automatically reset by SYNC now?
				
			ant.DSP.BYPASS=0
			ant.DSP.reset_sync() # recompute pipeline delays of selected DSP processing block

			ant.FR_DIST.TRIG_FRAME_COUNT=frames # Set number of frames to send when triggered. 110916 JFC: re-enabled line
			ant.CH_DIST.select_words(length//4); # Enable transmission of desired number of words 
			
	def read_ADC_frame_simple(self,channels=0,frames=1,length=1024):
		"""
		Triggers frame acquisition  from the specified ADC channel and capture the data.

		Parameters:
			channels: List of channels to configure and trigger. Will expect len(channels) frames. Frames from unexpected channels will cause an error
			frames: Number of frames to acquire per channel. Limited by the buffer lengths in the FPGA
			length: number of bytes to capture per channel. Must be a multiple of 4.
			sync: when true, send a local sync and resets the antenna processor before acquiring the frames
			raw: when true, returns the unsigned raw data from the ADC (bit 7 is not inverted)
		History:
			110916 JFC: Added comments. 
				Changed output format to dictionnary of arrays instead of bidimentional array.
				Now use global trigger to support multi-channel
		"""

		length=((length+3)//4)*4;

		
		if isinstance(channels,int): # make sure that channel is a list of channels
			channels=[channels]


		# Send a global trigger to start frame transmission
		self.SYSMOD.GLOBAL_TRIG=0 #trigger data acquisition  on all antennas
		self.SYSMOD.GLOBAL_TRIG=1 #trigger data acquisition  on all antennas

		# Now we acquire the data
		data={}
		for j in range(len(channels)*frames):
		#j=0
		#while 1:
			#j+=1
			try:
				in_frame=self.read_frame(timeout_delay=0.2)
			except SocketIO.timeout:
				print 'Timeout!'
				break

			if(len(in_frame)!=length+5):
				print 'Frame %i: !!!Frame length MISMATCH: Received %i, Expected : %i!!!' % ((j+1), len(in_frame), (5+length))

			# Process the packet header
			rx_packet_header=ord(in_frame[0])
			port=rx_packet_header & 0x3F

			# Process the frame header

			rx_frame_header=np.array(map(ord,in_frame[1:5]),np.uint8) # extract 4 header bytes as an uint8 array

			ant_number=rx_frame_header[0]
			frame_valid_ctr=rx_frame_header[1]>>2
			frame_ctr=((rx_frame_header[1]&0x03)<<6)+(rx_frame_header[2]>>2);
			frame_length=((rx_frame_header[2]&0x03)<<8)+rx_frame_header[3]

			# Process the frame data

			rx_subframe=in_frame[5:]
			raw_data=np.array(map(ord,rx_subframe),dtype=np.uint8)
			raw_data.dtype=np.int8


			ch=port
			# Make sure there is an empty vector on the first storage so we can concatenate to it the new data

			vector=raw_data;

			if ch not in data:
				data[ch]=vector
			else:
				data[ch]=np.hstack((data[ch],vector));
		return data	




from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

# Here's a UDP version of the simplest possible protocol
class receiveUDP(DatagramProtocol):
	n_frames = 0
	t0 = time.time()
	def datagramReceived(self, datagram, address):
		verbose = 1
		frame_array=[]
		last_timestamp = 0
		last_delta = 0
		n = 0
		#expected_delta=self.ANT[0].PROBER.get_burst_period()
		#data = self.sock.read_data(timeout_delay=timeout)
		frame=Frame(datagram)
		self.n_frames += 1
		if verbose >= 1 and (not self.n_frames % 500):
			dt = (time.time()-self.t0)
			print 'Received %i frames at %f frames/s (%f Mb/s), ' % (self.n_frames, self.n_frames/dt, self.n_frames/dt*2048*8/1e6)
			self.t0 = time.time()
			self.n_frames = 0
#		if frame.timestamp != last_timestamp:
#			delta = frame.timestamp - last_timestamp
#			last_timestamp = frame.timestamp
#				
#			if verbose >= 2:
#				print 'Received %i frames with timestamp=%i (%f s), ' % (n+1, frame.timestamp, frame.timestamp*self.FRAME_PERIOD)
##					if delta != last_delta:
##						print 'Timestamp increased by %i frames instead of %i frames' % (delta, last_delta)
#			if delta != expected_delta:
#				print 'Timestamp increased by %i frames instead of %i frames' % (delta, expected_delta)
#			if n != 8-1:
#				print 'Received only %i frames on the same timestamp' % (n+1)
#			n = 0
#			last_delta = delta
#		else:
#			n += 1

def main():
    reactor.listenUDP(41001, receiveUDP())
    reactor.run()
		
		
		
		#---------------------------------------------------------------------------------------------------






