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
import SYSMON
import SYSMOD
import FreqCtr
import MGT

# SPI device handlers
import ADC
import IOExpander
import ADC_PLL
import AmbTemp
import BiasADC
import MGT_PLL
# Antenna processor handlers
import ANT


# -- Module reloader -- 
# Reload modules if we are debugging in case the source code has changed

reload_modules=(util,SocketIO,Module,SPI,SYSMOD,SYSMON,AmbTemp,FreqCtr,ADC,IOExpander,ADC_PLL,BiasADC,MGT_PLL,ANT,MGT)
	

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


	def __init__(self,adc_test_mode=0, adc_delay_table=None, fref=10):

		# Create socket handled and open socket communications to chFPGA
		self.sock=SocketIO.SocketIO_base()
		self.sock.open();

		try: # catch initialization errors so we can free the socket for future instantiation
		# Create handware handling objects
			self.SYSMON=SYSMON.SYSMON_base(self)
			self.SPI=SPI.SPI_base(self)
			self.FreqCtr=FreqCtr.FreqCtr_base(self)
			self.SYSMOD=SYSMOD.SYSMOD_base(self)

			self.MGT=MGT.MGT_base(self)

			self.ADC=ADC.ADC_base(self)
			self.IOExpander=IOExpander.IOExpander_base(self)
			self.ADC_PLL=ADC_PLL.ADC_PLL_base(self)
			self.AmbTemp=AmbTemp.AmbTemp_base(self)
			self.MGT_PLL=MGT_PLL.MGT_PLL_base(self)
			self.BiasADC=BiasADC.BiasADC_base(self)

			self.ANT=ANT.ANT_base(self)

			# Initialize subsystems. This has to be done only once all subsystems are created because some subsystems depend on each other.

			self.SYSMOD.init()
			self.SYSMOD.status()
			self.SYSMON.init()
			self.SYSMON.status()
			self.SPI.init()
			self.IOExpander.init()
			self.ADC_PLL.init(fref=fref)
		#	pdb.set_trace()
			self.ADC.init(test_mode=adc_test_mode);
			self.AmbTemp.status()
			self.ANT.init()
			self.MGT_PLL.init(fref=fref)
			self.MGT.init() # MGT_PLL must be initialized first

			if adc_delay_table:
				self.ANT.set_delays(adc_delay_table)

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

		# Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))
		for i in range(length*itemsize): 
			s=chr(0x00+ant)+chr((module<<2)+(addr>>8))+chr(addr&0xff)
			self.sock.write_control(s)
			data=self.sock.read_control()
			if data[0:2]!=s[0:2]:
				print "Read: ERROR: Returned ANT/SUB/ADDR (",data[0:2]," does not match request values (",s[0:2],")"
			dout[i]=ord(data[3]) # store received byte
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
		s=chr(0x80+ant+(0x40 if incr else 0))+chr((module<<2)+(addr>>8))+chr(addr&0xFF) 

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
			a=array([data],np.dtype('>u2')); # store as big endian (most significant byte first)
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

	def read_frame(self):
		return self.sock.read_data();



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
					except socket.timeout:
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


	def ADC_plot_eye_diagram(self, channel=0):

		m=np.zeros((32,1024),np.uint8)
		old_delays=self.ADC_read_delay(channel)
		plt.figure(2)
		plt.clf()
		plt.plot(old_delays,arange(8),'ro')
		plt.hold(1)
		plt.draw()
		for dly in range(32):
			self.ADC_set_delay(channel,[dly]*8,reset=0)
			a=self.ADC_Read_Frame(channel,length=1024);
			#m[dly,:]=[ 1 if a[i]&(1<<bit) else 0 for i in xrange(len(a))]
			m[dly,:]=a
			#print ' Delay %2i : %s' % (dly, ''.join([ '|' if a[i]&(1<<bit) else '.' for i in xrange(160)])) 
		self.ADC_set_delay(channel,old_delays); # restore original delays
		for b in range(8):
			#mm=m & (1<<b) # select desired bit
			#ix=where(diff(mm)) # find indexes of all transitions
			#ixx=column_stack((ix-2,ix-1,ix,ix+1))

			plot(np.arange(0,32),(m[:,:(2**b)*4] & (1<<b)!=0 )*0.4-0.2 +b,'b.-')
			plt.draw()
		xlabel('Tap delay #');
		ylabel('Bit #');
		
		#plt.figure(1)
		#plt.clf()
		#plt.imshow((m & (1<<bit))!=0,aspect='auto', interpolation='nearest', cmap=plt.gray(), filternorm=1)
		#plt.draw()

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

	def read_ADC_frame(self,channels=0,frames=1,verbose=0,length=1024,simulate=0, reset=1, fft=0, dummy=0):
		"""
		Acquires frames from the specified ADC channel.
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

		if verbose:
			print ' Receiving %i ADC frames of %i bytes from Antenna %i' % ( frames, length, channels)
			print 'Resetting FIFO'
		if isinstance(channels,int): # make sure that channel is a list of channels
			channels=[channels]

		for ch in channels:
			ant=self.ANT[ch]
			if reset:
				if simulate==0: # Source is ADC data
					ant.ADCDAQ.ENABLE_RAMP=0
					ant.FR_DIST.DSP_DATA_SRC_ADC=1 # Source is ADC DAQ
				elif simulate==1: # Source is ADC-DAQ ramp generator
					ant.ADCDAQ.ENABLE_RAMP=1
					ant.FR_DIST.DSP_DATA_SRC_ADC=1 # Source is ADC DAQ
				elif simulate==2: # Source is Frame_DIST-based ramp generator
					ant.ADCDAQ.ENABLE_RAMP=0
					ant.FR_DIST.ENABLE_RAMP=1 # Enable ranp generator
					ant.FR_DIST.DSP_DATA_SRC_ADC=0 # Source is ADC DAQ
				else:
					raise Exception('Invalid simulation parameter')
				
			if reset:
				if fft:
					self.FFTinit(ch)
				else:
					ant.DSP.BYPASS=0
					ant.DSP.reset_sync()

#				ant.FR_DIST.TRIG_FRAME_COUNT=frames # Set number of frames to send when triggered
				ant.FR_DIST.reset_fifo()
				ant.CH_DIST.select_words(length//4); # Enable transmission of all bytes 
#		if len(channel)==1:
		ant.FR_DIST.trig_frame(frames); # Trigger frame acquisition and transmission  
#		else:
#			print 'Sending trig'
#			self.pulse_bit(self.SYSTEM_PORT,self.FMC_SPI_MODULE,5,7); # Trigger transmission for all frames

		data=np.zeros((len(channels),output_length));
		ch=0
		for j in range(len(channels)*frames):
			if verbose>1 or (verbose==1 and (i % 100 ==99 or i==frames-1)):
				print 'Frame %i (%.0f%%)' % ((i+1),(100*(i+1)/frames))

			in_frame=self.read_frame()
			if(len(in_frame)!=length+5):
				print 'Frame %i: !!!Frame length MISMATCH: Received %i, Expected : %i!!!' % ((j+1), len(in_frame), (5+length))

			# Process the packet header
			rx_packet_header=ord(in_frame[0])
			channel=rx_packet_header & 0x3F

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

			print 'Packet received from port %i. Frame header information: Antenna %i, Valid frame #=%i, Frame #=%i, Frame length=%i' % (channel, ant_number, frame_valid_ctr, frame_ctr, frame_length)
			print data
			if fft:
				data[ch,:]=np.array([raw_data[i]+1j*raw_data[i+1] for i in range(0,1024,2)])
			else:
				data[ch,:]=raw_data;
			ch+=1
		return data		

	def plot_ADC_frame(self, channels=0, hold=0, frames=1, continuous=0,xmax=1023,fft=0, sync_period=None, out_shift=0, fft_shift=None, filename=None,simulate=0,correlate=0):
		if filename:
			file=open(filename,'w')
		else:
			file=None

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

		if type(channels) is int: # make sure that 'channels' is a list
			channels=[channels];

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
			while (frames==0) or (frames!=0 and number_of_frames<frames):
				try:
					a=self.read_ADC_frame(channels,length=1024,reset=(number_of_frames==0),fft=fft,simulate=simulate) #(number_of_frames==0)
					if fft: 
						if correlate:
							corr=a[ch1]*conj(a[ch2])
						else:
							corr=a[ch1]
						corr_sum+=corr
					number_of_frames+=1
					
					aamax=max(max(abs(a)))
					ymax=max(ymax*.99,aamax)
					if fft:
						plt.subplot(2,1,1);
						if correlate:
							plt.plot(f,abs(a[ch1,:]) ,'b.-',f,abs(a[ch2]),'k.-')
						else:
							#raise
							plt.plot(abs(a[ch1,:]) ,'b.-')

						plt.axis([0,xmax,-ymax,ymax])
						plt.subplot(2,1,2);
						plt.plot(f,abs(corr) ,'b.-',f,corr_sum.real/number_of_frames,'r.-')
					else:
						plt.plot(a[ch1],'b.-')
						if mult_chan:
							plt.plot(a[ch2],'r.-')
						plt.axis([0,xmax,-ymax,ymax])
						#plt.axis([0,xmax,-70,70])
					plt.draw()
					if file:
						file.write(np.int8(a[ch1,:]))
						if mult_chan:
							file.write(np.int8(a[ch2,:]))
				except:
					raise
		except KeyboardInterrupt:
			pass
		if file:
			file.close()
		print 'Plotted %i frames' % number_of_frames
		
		
	def plot_ADC_frame_fft(self, channels=0, hold=0, frames=1, continuous=0,xmax=1023, sync_period=None, fft=1, out_shift=0, fft_shift=None, filename=None,simulate=0,correlate=0):
		'''
		20110906KMB:  added fft plotting
		20110909KMB: changed save to be npy files. other gave anomolous results.
		'''
		#if filename:
		data_list = []
		#	#file=open(filename,'w')
		#else:
		#	#file=None

		plt.figure(5)
		#if not hold:
		plt.clf()
		plt.hold(hold)
		plt.show()

		if fft:
			#f=np.arange(1024)*1024.0/800.0
			f=np.fft.fftfreq(1024,1/800.0)
			plt.title('Signal')
			plt.subplot(2,1,1)
			plt.xlabel('Frequency (MHz)')
			plt.ylabel('Amplitude');
			plt.subplot(2,1,2)
			plt.title('Timestream')
			plt.xlabel('sample')
			plt.ylabel('Amplitude');

		if type(channels) is int: # make sure that 'channels' is a list
			channels=[channels];

		correlate=(len(channels)>1) & correlate
		mult_chan = len(channels)>1
		if mult_chan: # select channels to correlate
			ch1=channels[0]
			ch2=channels[1]
		else:
			ch1=channels[0]
		#corr_sum=np.zeros(512,dtype=complex)
		number_of_frames=0

		
		ymax=1
#		if fft:
#			self.FFTinit(ant=channel,sync_period=sync_period, out_shift=out_shift, fft_shift=fft_shift);
		try:
			while (frames==0) or (frames!=0 and number_of_frames<frames):
				try:
					a=self.read_ADC_frame(channels,length=1024,reset=(number_of_frames==0),fft=0,simulate=simulate) #(number_of_frames==0)
					if fft:
						fa = np.fft.fft(a[ch1])#[:512]
						if correlate:
							corr=fa[ch1]*conj(fa[ch2])
						else:
							corr=a[ch1]
						#corr_sum+=corr
					number_of_frames+=1
					
					aamax=max(max(abs(a)))
					ymax=max(ymax*.99,aamax)
					fmax = f.max()
					ftmax = 10*np.log10(np.abs(fa)**2).max()
					print fa.size
					if fft:
						plt.subplot(2,1,1);
						if correlate:
							plt.plot(f,abs(a[ch1,:]) ,'b.-',f,abs(a[ch2]),'k.-')
						else:
							#raise
							plt.plot(f,10*np.log10(np.abs(fa)**2) ,'b.-')

						#plt.axis([0,fmax,0,ftmax])
						plt.ylim(0,100)
						plt.subplot(2,1,2);
						plt.plot(a[ch1] ,'b.-')
						plt.axis([0,xmax,-ymax,ymax])
					else:
						plt.plot(a[ch1],'b.-')
						if mult_chan:
							plt.plot(a[ch2],'r.-')
						plt.axis([0,xmax,-ymax,ymax])
						#plt.axis([0,xmax,-70,70])
					plt.draw()
					if filename:
						data_list.append(a[ch1])
						#file.write(np.int8(a[ch1,:]))
						if mult_chan:
							data_list.append(a[ch2])
							#file.write(np.int8(a[ch2,:]))
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






