#!/usr/bin/python

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
"""

import time
import datetime
import random
import sys
import select
import numpy as np
#import matplotlib as mpl
import matplotlib.pyplot as plt
import pdb
import socket #110906 JFCs

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


# -- Module reloader -- 
# Reload modules if we are debugging in case the source code has changed

reload_modules=(util,SocketIO,Module,SPI,I2C,SYSMOD,SYSMON,REFCLK,AmbTemp,FreqCtr,ADC,IOExpander,ADC_PLL,BiasADC,MGT_PLL,FMC_EEPROM,ML605_PMBus,ANT,MGT)
	

for m in reload_modules: 
	print 'Reloading module %s' % (m.__name__)
	reload(m)


# -- hex() -- 
#hex=util.hex # override default hex function

# -- chFPGA -- 

class chFPGA:
	# Port numbers
	ANT_PORT=range(8) # Antennas are ports 0-7
	SYSTEM_PORT = 8
	MGT_PORT = 9


	# SYSTEM Modules
	SYSTEM_SPI_MODULE=0
	SYSTEM_SYSMON_MODULE=1
	SYSTEM_FREQ_CTR_MODULE=2
	SYSTEM_SYSMOD_MODULE=3
	SYSTEM_REFCLK_MODULE=4
	SYSTEM_I2C_MODULE=5


	def __init__(self,adc_test_mode=0, adc_delay_table=None, fref=10):

		print '*** Opening sockets ***'
		# Create socket handled and open socket communications to chFPGA
		self.sock=SocketIO.SocketIO_base()
		self.sock.open();

		try: # catch initialization errors so we can free the socket for future instantiation
			print '*** Instantiating modules ***'
		# Create handware handling objects
			print '  - SYSMON'
			self.SYSMON=SYSMON.SYSMON_base(self)
			print '  - SPI'
			self.SPI=SPI.SPI_base(self)
			print '  - I2C'
			self.I2C=I2C.I2C_base(self)
			print '  - FreqCtr'
			self.FreqCtr=FreqCtr.FreqCtr_base(self)
			print '  - SYSMOD'
			self.SYSMOD=SYSMOD.SYSMOD_base(self)
			print '  - REFCLK'
			self.REFCLK=REFCLK.REFCLK_base(self)

			print '  - MGT'
			self.MGT=MGT.MGT_base(self)

			print '  - ADC'
			self.ADC=ADC.ADC_base(self)
			print '  - IOExpander'
			self.IOExpander=IOExpander.IOExpander_base(self)
			print '  - ADC_PLL'
			self.ADC_PLL=ADC_PLL.ADC_PLL_base(self)
			print '  - AmbTemp'
			self.AmbTemp=AmbTemp.AmbTemp_base(self)
			print '  - MGT_PLL'
			self.MGT_PLL=MGT_PLL.MGT_PLL_base(self)
			print '  - BiasADC'
			self.BiasADC=BiasADC.BiasADC_base(self)
			print '  - FMC EEPROM'
			self.FMC_EEPROM=FMC_EEPROM.FMC_EEPROM_base(self)
			print '  - ML605 PMBus'
			self.ML605_PMBus=ML605_PMBus.ML605_PMBus_base(self)

			print '  - ANT'
			self.ANT=ANT.ANT_base(self)
	
			# Initialize subsystems. This has to be done only once all subsystems are created because some subsystems depend on each other.
			print '*** Initializing modules ***'

			print '  - SYSMOD'
			self.SYSMOD.init()
			self.SYSMOD.status()
			print '  - REFCLK'
			self.REFCLK.status()
			print '  - SYSMON'
			self.SYSMON.init()
			self.SYSMON.status()
			print '  - SPI'
			self.SPI.init()
			print '  - I2C'
			self.I2C.init()
			print '  - EEPROM'
			self.FMC_EEPROM.init()
			self.FMC_EEPROM.status()

			print '  - ML605 PMBus'
			self.ML605_PMBus.init()
			self.ML605_PMBus.status()

			print '  - IOExpander'
			self.IOExpander.init()
			print '  - ADC_PLL'
			self.ADC_PLL.init(fref=fref)
		#	pdb.set_trace()
			print '  - ADC'

			self.ADC.init(test_mode=adc_test_mode);
			print '  - AmbTemp'

			self.AmbTemp.status()
			print '  - ANT'
			self.ANT.init()
			print '  - MGT_PLL'
			self.MGT_PLL.init(fref=fref)
			print '  - MGT'
			self.MGT.init() # MGT_PLL must be initialized first
			print '  - Done with initializations'

			print '*** Setting ADCDAQ delays ***'

			if adc_delay_table:
				self.ANT.set_delays(adc_delay_table)

			print '*** Set ADC mode ***'

			self.set_ADC_mode('Normal')
			print '*** End of chFPGA initialization ***'

		except:
			print 'Error during chFPGA initialization. Closing socket communications'
			self.close()
			raise

	def __del__(self):

		self.close();
		print '__del__: Closed FPGA at IP address %s' % self.self.OUT_IP

	def close(self):
		""" 
		Close chFPGA object, which releases the socket bindings
		"""
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
			return dout[0];
		else:
			return dout;
		
	
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
			s+=data;
			length=len(data)
		elif type(data)==list or type(data)==np.ndarray:
			s+=''.join([chr(data[i]) for i in range(len(data))])
			length=len(data)
		elif type(data)==np.uint32:
			length=4;
			a=np.array([data],np.dtype('>u4')) # store as big endian (most significant byte first)
			a.dtype=np.uint8;
			s+=''.join([chr(a[i]) for i in range(4)])
		elif type(data)==np.uint16:
			length=2;
			a=np.array([data],np.dtype('>u2')); # store as big endian (most significant byte first)
			a.dtype=np.uint8;
			s+=''.join([chr(a[i]) for i in range(2)])
		elif type([data])==np.uint8:
			length=1;
			a=array([data]); # store as big endian (most significant byte first)
			a.dtype=np.uint8;
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



	def test1(self):
		self.OpenSocket();

		# Empty buffer
		self.flush_control_socket();
		
		# Create big data string
		#print 'Generating data...'
		#s="";
		#for i in range(9014-42):
		#	s+="A";

		frame_transmission_time=(9014+42+4+12)*8/1e9; # frame transmission time @ 1 Gb/s- used to compute timout	
		print "Frame transmission duration is ", frame_transmission_time;
		self.sock.settimeout(max(frame_transmission_time*4,0.1));

		# Send test patterns
		print 'Sending test patterns'
		fail=0;
		success=0;
		total_size=0;
		total_rx_size=0;
		
		s0=''.join([chr(random.randint(0,255)) for i in range(7000)])
#		s="XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXx";
		t1=time.time();
		i=1;
		j=1;
		send_retry=0;
		rx_retry=0;
		N=1000;
		while j<=N:
		#	print '------------------------'

		#	res= 'Iteration ',i,


			#s="";
			#for i in range(9014-42):
			#	s+=chr(random.randint(0,255));
			s="Message #" + str(i)+s0;
			s=s0;
		#	print '     Sending data:', s
		#	print '     Sending data...',
			#print 'Iteration ',i
			data="";
			rx,tx,ex=select.select((self.sock,),(self.sock,),[],0);
			if i<=N:
				try:
					self.sock.settimeout(0);
			#		print "TX Message #", i
					n=self.sock.sendto ( s, self.OUT_ADDR );
			#		data,client=self.sock.recvfrom ( 16384 );
			#		print '    Received data length:', len(data),
					total_size+=len(s)+8+42+4+12; # also include preamble, Ethernet/IP/UDP headers, CRC and interframe delay to get a better idea of the real throughput
					i+=1;
			#	except KeyboardInterrupt:
			#		raise
				except socket.error as (errno,errname):
					if errno==11:
						#print 'Error 11 on packet #',i
						#ss=''.join([chr(random.randint(0,255)) for i in range(90-42)])
						send_retry+=1;
					#	time.sleep(0.00001);
						pass


			if(len(rx)>0):
				self.sock.settimeout(1);
				data,client=self.sock.recvfrom ( 16384);
				print '   RX Message #', j
				total_rx_size+=len(data)+8+42+4+12; # also include preamble, Ethernet/IP/UDP headers, CRC and interframe delay to get a better idea of the real throughput
				s2="Message #" + str(j)+s0;
				s2=s0;
				j+=1;
				if data[0:100]==s2[0:100]: 
					success+=1;
				#	print '   Data match'
				#	print s2
				#	print data
				else:

					print '   !!!Data MISMATCH!!!'
				#	print s2
				#	print data
					fail+=1;
			#except socket.error as (errno,errname):
			#	if errno==11:

			#		print 'Receive Error 11 on packet #',j
			#		print data
			#		#ss=''.join([chr(random.randint(0,255)) for i in range(90-42)])
			#		rx_retry+=1;
			#	#	time.sleep(0.00001);
			#		pass
			#	else:
			#		print '   !!! Socket error: ',errno,errname
			#		fail+=1;
		t2=time.time();
		dt=t2-t1;
		if dt==0:
			dt=0.000001;
		print '------------------------'
		print ' Success: ', success, '/', success+fail, '(', success/(success+fail)*100, '%) over ', total_size/1024/1024, 'MBytes in', dt, 'seconds, average speed=',total_size*8/1e6/dt,"Mb/s", 'retries=',send_retry
				
		self.CloseSocket();		
			
		
	

	def Test_Frame(self,ant=0,frames=1,verbose=1,length=32,random_period=0,frame_group=1,tx_port=None,loopback_mode=None,reset_MGT=1):
		"""
		Injects random frames in the FR_DIST FIFO and check the returned frames for errors.
		"""

		# Compute the number of 32-bit words that are to be received
		number_of_words=int((length+3)/4);
		# Adjust the length so it matches the number of words
		length=number_of_words*4;

		ant=self.ANT[ant]
		print ' Sending %i groups of %i frames of %i bytes' % (frame_group, frames, length)

		if random_period==0:
			random_period=frames
		print 'Resetting FIFO'

		# flush socket buffers
		self.sock.flush_control_socket();
		self.sock.flush_data_socket();

		# FR_DIST set-up
		ant.FR_DIST.reset_fifo(); # Reset FR_DIST data injection FIFO by pulsing the FIFO reset bit . Set in internal clock and internal data source mode.
		ant.TRIG_FRAME_COUNT=1;

		# DSP set-up
		ant.DSP.BYPASS=1
		ant.DSP.reset_sync();

		# CH_DIST set-up
		ant.CH_DIST.reset()
		ant.CH_DIST.select_words(number_of_words); # Enable transmission of selected samples 

		# MGT set-up
		if tx_port is not None:
			self.MGT.TX_SEL=tx_port
		else:
			tx_port=self.MGT.TX_SEL
		if loopback_mode is not None: self.MGT[tx_port].LOOPBACK_MODE=loopback_mode

		if reset_MGT:
			self.MGT.rx_reset() # reset all MGTs
			#self.MGT[0].reset();

		t1=time.time();
		passed=0
		failed=0;
		antennas=set();
		try:
			for i in range(frames):
				if verbose>1 or (verbose==1 and (i % 100 ==99 or i==frames-1)):
					print 'Frame %i (%.0f%%)' % ((i+1)*frame_group,(100*(i+1)/frames)), 
					if antennas:
						mgt=self.MGT[list(antennas)[0]]
						print 'Eye = %3.1f mV, DFE Taps=[%2i,%2i,%2i,%2i]' % (mgt.EYE_HEIGHT/31.0*200, mgt.TAP1_MON,mgt.TAP2_MON,mgt.TAP3_MON,mgt.TAP4_MON)
					else:
						print
				if i % random_period == 0 :
					out_frame=''.join([chr(random.randint(64,95)) for j in range(1024)]);
					#our_frame=''.join([chr(0) for j in range(1024)]);
					print 'Frame %i : Randomizing test vector' % (i+1)
				ant.FR_DIST.inject_frame(data=out_frame*frame_group); # Send the frame 'frame_group' times
				for k in range(frame_group):
					try:
						in_frame=self.read_frame()
						if(len(in_frame)!=length+1+4):
							print 'Frame %i: !!!Frame length MISMATCH: Received %i, Expected : %i!!!' % ((i+1), len(in_frame), frame_group*(length+1+4))
						rx_subframe_header=in_frame[:5]
						antenna_number=ord(rx_subframe_header[0]) & 0x3F
						in_frame=in_frame[5:]
						antennas.add(antenna_number)
						#print "Data from antenna %i" % (antenna_number)	
						if in_frame!=out_frame[:length]: 
							print 'Frame %i: !!!Data MISMATCH!!!' % (i+1)
							print '   Sent    : %s...%s (length %i)'%  (out_frame[:64],out_frame[-64:], len(out_frame))
							print '   Received: %s...%s (length %i)'% (in_frame[:64],in_frame[-64:], len(in_frame))
							failed+=1
						else:
							passed+=1;
					except SocketIO.timeout:
						print 'Frame %i: !!! Timeout !!!' % (i+1)
						failed+=1
		except KeyboardInterrupt:
			pass
		t2=time.time();
		dt=max(t2-t1,1e-3); # Limits minimum time interval to 1 ms
		print ' Transmitted  %i frames of %i bytes each (total %.1f MB) in %s s (%.1f fps, %.1f MB/s)' % (passed+failed, 1024, (passed+failed)/1024, dt, frames*frame_group/dt, frames*frame_group*1024/dt/1e6)
		print ' Pass: %i (%.2f%%), fail: %i (%.2f%%)' % (passed, passed*100.0/(passed+failed), failed, failed*100.0/(passed+failed))
		print ' Source antenna(s)', ','.join(str(a) for a in antennas)

	def Test_FFT(self,ant=0,frames=1,verbose=1,random_period=0,frame_group=1,value=0):
		length=1024;
		number_of_words=length/32;
		print ' Sending %i frames of %i bytes' % (frames, length)
		print 'Resetting FIFO'
		self.Write(ant,0,0,[0x08, 0x00],incr=0); # Reset FR_DIST data injection FIFO by pulsing the FIFO reset bit . Set in internal clock and internal data source mode.
		self.Write(ant,1,128,[0xff if j<number_of_words else 0x00 for j in range(1024/8)]); # Enable transmission of all bytes 
		self.Write(ant,2,0,[3,1],incr=0); # Route data through FFT and Reset SYNC module  
		t1=time.time();
		for i in range(frames):
			if verbose>1 or (verbose==1 and (i % 100 ==99 or i==frames-1)):
				print 'Frame %i (%.0f%%)' % (i+1,(100*(i+1)/frames))

			out_frame=''.join([chr(value) for j in range(1024)]);
			self.Write_Frame(ant=ant, data=out_frame*frame_group); # Send the frame 'frame_group' times

			for k in range(frame_group):
				in_frame=self.Read_Frame(ant=ant)
				if(len(in_frame)!=length+1):
					print 'Frame %i: !!!Frame length MISMATCH: Received %i, Expected : %i!!!' % ((i+1), len(in_frame), frame_group*(1+length))
				rx_subframe_header=in_frame[0]
				rx_subframe=in_frame[1:]
					
				#print 'Frame %i: !!!Data MISMATCH!!!' % (i+1)
				print '   Sent    : %s... (length %i)'%  (`[ord(out_frame[k]) for k in range(10)]`, len(out_frame))
				print '   Received: %s... (length %i)'%  (`[ord(rx_subframe[k]) for k in range(10)]`, len(rx_subframe))
		t2=time.time();
		dt=max(t2-t1,1e-3); # Limits minimum time interval to 1 ms
		print ' Transmitted %i group(s) of %i frames of %i bytes each in %s s (%.1f fps, %.1f MB/s)' % (frames, frame_group, 1024, dt, frames*frame_group/dt, frames*frame_group*1024/dt/1e6)

	def FFTinit(self,ant=0,sync_period=None, out_shift=None, fft_shift=None):
		self.Write(ant,1,128,[0xff]*32); # Enable transmission of all bytes 
		if sync_period:
			self.Write(ant,0,2,uint16(sync_period)); #    
		if out_shift is not None:
			self.write_mask(ant,2,1,0xF0,out_shift<<4); # 
		if fft_shift is not None:
			self.write_mask(ant,2,1,0x03,(fft_shift>>8)); #    
			self.Write(ant,2,2,fft_shift & 0xFF); #    
		self.write_bit(ant,2,0,0,1); # Route data through DSP engine   
		self.pulse_bit(ant,2,0,1); #  Reset SYNC module  


	
	def FFT(self,tx_data, ant=0, dual_frame=0):

		#out_frame=''.join([chr(value) for j in range(1024)]);
		self.write_bit(self.ANT_PORT+ant,self.ANT_FR_DIST_MODULE,0,5,dual_frame); # 

		for i in range(dual_frame+1):
			self.Write_Frame(ant=ant, data=tx_data, length=1024); # Send the frame (force the length to 1024 - elements will be repeated if needed) 

		for i in range(dual_frame+1):
			in_frame=self.Read_Frame(ant=ant)
			if(len(in_frame)!=1025):
				print '!!!Frame length MISMATCH: Received %i, Expected : %i!!!' % (len(in_frame), 1025)
		rx_data_header=in_frame[0]
		rx_data=np.array([np.int8(ord(in_frame[i]))+1j*np.int8(ord(in_frame[i+1])) for i in range(1,1025,2)]);
		return rx_data
		

	def FFTCompare(self,tx_data, ant=0, hold=0, sync_period=None, out_shift=0, fft_shift=None, dual_frame=1):
		self.FFTinit(ant=ant,sync_period=sync_period, out_shift=out_shift, fft_shift=fft_shift);
		if type(tx_data)==int:
			tx_data=[tx_data]*1024*(dual_frame+1); # repeat int 1024 times
		
		x=self.FFT(tx_data,ant=ant, dual_frame=dual_frame)
		y=np.fft.fft(np.int8(tx_data))/1024.
		y=y[:512]
		f=range(512)
		
		plt.figure(1)
		plt.subplot(2,1,1);
		plt.hold(hold)
		plt.plot(f,x.real,'r.-',f,y.real,'b-')
		plt.legend(('chFPGA FFT','numpy FFT'))
		plt.grid(True)
		
		plt.subplot(2,1,2);
		plt.hold(hold)
		plt.plot(f,x.imag,'r.-',f,y.imag,'b-')
		plt.grid(True)


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
		hold(1)
#		self.ADC_set_delay(adc,dly)
		a=self.ADC_Read_Frame(channel,length=1024,simulate=simulate);
		if delay:
			self.ADC_set_delay(channel,old_delays); # restore original delays
		for bit in range(8):
			plot(((a & (1<<bit))!=0) +2*bit,'b.-')
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
			a0=(arange(1024)+a[0]) % 256;
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

	def set_ADC_mode(self,test_mode=0, sync=1):
		"""
		Sets the test mode of both ADCs, sets the proper CAPTURE period, and sends a SYNC.
			test_mode:
				0 or 'normal': Normal mode (ADC output contains analog samples)
				1 or 'ramp': Ramp mode (ADC output contains repeating 0-255 pattern. Note that ADCDAQ inverts bit 7 during acquisition to convert offset binary to 2's complement binary)
				2 or 'pulse' or 'strobe' : Strobe mode (ADC output contains one 0xFF followed by ten 0x00. It repeats with a pariod of 11. Same comment as above)
		111212 JFC: Added this high-level function with string mode.
		"""

		mode_strings={'n':0, 'r':1, 's':2, 'p':2} # define the test mode based on the first character of the test_mode string
		mode_periods=(64,64,11) # repetition period (in words) for each mode
		if isinstance(test_mode,str):
			test_mode=mode_strings[test_mode[0].lower()]

		self.ADC.set_test_mode(test_mode=test_mode)
		self.current_ADC_mode=test_mode

		for ant in self.ANT:
			ant.ADCDAQ.CAPTURE2_PERIOD=mode_periods[test_mode] # set the period so we are ready to capture data correctly after the SYNC resets the CAPTURE logic

		if sync:
			self.sync() # make sure the ADC mode is set and that capture  restarts properly with the right period

	def scan_phase(self):
		for phase in range(0,200,5):
			#for i in range(10):
				self.sync(phase=phase,verbose=0)
				s=self.REFCLK.scan_refclk_delay()
				print ' Phase %i, %s' % (phase, self.REFCLK.bit_vector_to_string(s))
				time.sleep(0.01)
			#raw_input('Press [ENTER]')

	def read_ADC_frame(self,channels=0,frames=1,verbose=1,length=1024,simulate=0, sync=1, fft=0, dummy=0,raw=0):
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
		if dummy:
			if fft:
				return np.array(rand(1024)*256-128,np.int8)
			else:
				return np.array(rand(512)*256-128,np.int8)

		length=((length+3)//4)*4;

		if fft:
			output_length=512
		else:
			output_length=1024

		if verbose>=2:
			print ' Receiving %i ADC frames of %i bytes from Antenna %i' % ( frames, length, channels)
			print 'Resetting FIFO'
		if isinstance(channels,int): # make sure that channel is a list of channels
			channels=[channels]

		# Disable frame transmission for all antennas. Those thar are selected will be set-up later.
		for ant in self.ANT:
			ant.FR_DIST.TRIG_FRAME_COUNT=0 # Disable response to global trigger for all channnels by default. The requested ones will be re-enabled later. 

		if sync:
			if verbose:
				print 'Resetting and SYNCing the devices'
			self.sock.flush_data_socket()
			self.sync()
	
		for ch in channels:
			ant=self.ANT[ch]
			if sync:
				if simulate==0: # Source is ADC data
					ant.ADCDAQ.ENABLE_RAMP=0
					ant.FR_DIST.DSP_DATA_SRC_ADC=1 # Source is ADC DAQ
				elif simulate==1: # Source is ADC-DAQ ramp generator
					ant.ADCDAQ.ENABLE_RAMP=1
					ant.FR_DIST.DSP_DATA_SRC_ADC=1 # Source is ADC DAQ
				elif simulate==2: # Source is Frame_DIST-based ramp generator
					ant.ADCDAQ.ENABLE_RAMP=0
					ant.FR_DIST.ENABLE_RAMP=1 # Enable ramp generator
					ant.FR_DIST.DSP_DATA_SRC_ADC=0 # Source is ADC DAQ
				else:
					raise Exception('Invalid simulation parameter')

				ant.CH_DIST.pulse_bit('RESET') # Make sure the CH_DIST buffers are empty
				ant.FR_DIST.reset_fifo() # if this automatically reset by SYNC now?
				
				if fft:
					self.FFTinit(ch)
				else:
					ant.DSP.BYPASS=0
					ant.DSP.reset_sync() # recompute pipeline delays of selected DSP processing block

			ant.FR_DIST.TRIG_FRAME_COUNT=frames # Set number of frames to send when triggered. 110916 JFC: re-enabled line
			ant.CH_DIST.select_words(length//4); # Enable transmission of desired number of words 


		# Send a global trigger to start frame transmission
		self.SYSMOD.GLOBAL_TRIG=0 #trigger data acquisition  on all antennas
		self.SYSMOD.GLOBAL_TRIG=1 #trigger data acquisition  on all antennas

		# Now we acquire the data
		data={}
		for j in range(len(channels)*frames):
		#j=0
		#while 1:
			#j+=1
			if verbose>1 or (verbose==1 and (j % 100 ==99 or j==frames-1)):
				print 'Acquiring Frame %i (%.0f%%)' % ((j+1),(100*(j+1)/frames))
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

			if raw:
				raw_data.dtype=np.uint8
				raw_data^=0x80

			ch=port
			if verbose:
				print 'Packet received from port %i. Frame header information: Antenna %i, Valid frame #=%i, Frame #=%i, Frame length=%i words, trigger count=%i' % (port, ant_number, frame_valid_ctr, frame_ctr, frame_length,self.ANT[ch].FR_DIST.TRIG_COUNT)
				#print data

			# Make sure there is an empty vector on the first storage so we can concatenate to it the new data
			
			if fft:
				vector=np.array([raw_data[i]+1j*raw_data[i+1] for i in range(0,1024,2)])
			else:
				vector=raw_data;

			if ch not in data:
				data[ch]=vector
			else:
				data[ch]=np.hstack((data[ch],vector));
		return data		

	def plot_ADC_frame(self, channels=0, hold=0, frames=1, continuous=0,xmax=1023,fft=0, sync_period=None, out_shift=0, fft_shift=None, filename=None,simulate=0,correlate=0,reset=0,length=1024):
		if filename:
			file=open(filename,'w')
		else:
			file=None

		if isinstance(channels,int): # make sure that channel is a list of channels
			channels=[channels]

		plt.figure(5)
		#if not hold:
		plt.clf()
		plt.hold(hold)
		plt.show()

		if fft:
			f=arange(512)*1024.0/800.0
			plt.title('Signal')
			plt.subplot(2,1,1)
			plt.xlabel('Frequency (MHz)')
			plt.ylabel('Amplitude');
			plt.subplot(2,1,2)
			plt.title('Correlation')
			plt.xlabel('Frequency (MHz)')
			plt.ylabel('Amplitude');

		correlate=(len(channels)>1) & correlate
		mult_chan = len(channels)>1
		if mult_chan: # select channels to correlate
			ch1=channels[0]
			ch2=channels[1]
		else:
			ch1=channels[0]
		corr_sum=np.zeros(512,dtype=complex)
		number_of_frames=0

		
		ymax=1
#		if fft:
#			self.FFTinit(ant=channel,sync_period=sync_period, out_shift=out_shift, fft_shift=fft_shift);
		try:
			while (continuous==1) or (number_of_frames<frames):
				try:
					print 'Reading data...'
					a=self.read_ADC_frame(channels,length=1024,sync=(number_of_frames==0) or bool(reset),fft=fft,simulate=simulate) #(number_of_frames==0)
					ch1_data=a[ch1][:length]
					if mult_chan: # select channels to correlate
						ch2_data=a[ch2]
						print 'CHa[0]=',hex(ch1_data[0]),'CHb[0]=',hex(ch2_data[0]), ' Difference=', ch1_data[0]-ch2_data[0]
					if fft: 
						if correlate:
							corr=ch1_data*conj(ch2_data)
						else:
							corr=ch1_data
						corr_sum+=corr
					number_of_frames+=1
					
					aamax=max(abs(ch1_data))
					ymax=max(ymax*.99,aamax)
					if fft:
						plt.subplot(2,1,1);
						if correlate:
							plt.plot(f,abs(ch1_data) ,'b.-',f,abs(ch2_data),'k.-')
						else:
							#raise
							plt.plot(abs(ch1_data) ,'b.-')

						plt.axis([0,xmax,-ymax,ymax])
						plt.subplot(2,1,2);
						plt.plot(f,abs(corr) ,'b.-',f,corr_sum.real/number_of_frames,'r.-')
					else:
						if not mult_chan:
							plt.plot(ch1_data,'b.-')
						else:
							plt.plot(ch1_data,'b-', ch2_data,'r-')
						plt.axis([0,xmax,-ymax,ymax])
						#plt.axis([0,xmax,-70,70])
					#plt.legend(('Ch%i' % ch1, 'Ch%i' % ch2))
					plt.draw()

					if file:
						file.write(np.int8(ch1_data))
						if mult_chan:
							file.write(np.int8(ch2_data))
				except:
					raise
		except KeyboardInterrupt:
			pass
		if file:
			file.close()
		print 'Plotted %i frames' % number_of_frames
		
		
	def plot_ADC_frame_fft(self, channels=0, hold=0, frames=1, continuous=0,xmax=1023, sync_period=None, fft=1, out_shift=0, fft_shift=None, filename=None,simulate=0, contiguousFrames=8, length=1024):
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
		
		if fft:
			#f=np.arange(1024)*1024.0/800.0
			f=np.fft.fftfreq(length*contiguousFrames,1/800.0)
			for chanNum in chanIndex:
				plt.subplot(2,nchan,chanNum+1)
				plt.title('Spectrum')
				plt.xlabel('Frequency (MHz)')
				plt.ylabel('Amplitude');
				plt.subplot(2,nchan,nchan+chanNum+1)
				plt.title('Timestream')
				plt.xlabel('sample')
				plt.ylabel('Amplitude');

		
		mult_chan = nchan>1

		#corr_sum=np.zeros(512,dtype=complex)
		number_of_frames=0

		
		ymax=1
#		if fft:
#			self.FFTinit(ant=channel,sync_period=sync_period, out_shift=out_shift, fft_shift=fft_shift);
		try:
			while (frames==0) or (frames!=0 and number_of_frames<frames):
				try:
					a=self.read_ADC_frame(channels,length=length,sync=(number_of_frames==0),fft=0,simulate=simulate, frames=contiguousFrames) #(number_of_frames==0)
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
							plt.plot(f,10*np.log10(np.abs(fa[chanNum])**2) ,'b.-')
							#plt.axis([0,fmax,0,ftmax])
							plt.ylim(0,100)
							plt.subplot(2,nchan,nchan+chanNum+1);
							plt.plot(a[channels[chanNum]] ,'b.-')
							#plt.axis([0,xmax,-ymax,ymax])
							plt.axis([0,xmax,-128,127])
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
	
		
		
		
		
		
		
		
		#---------------------------------------------------------------------------------------------------






