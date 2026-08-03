

	def inject_frame(self,ant=0,frames=1,verbose=1,length=32,random_period=0,frame_group=1,tx_port=None,loopback_mode=None,reset_MGT=1):
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
