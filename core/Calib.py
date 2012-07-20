#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
x module 
 Implements the functions needed to calibrate the data acquisition and SYNC delays in the electronics

 History:
	2012-07-19 JFC: Created
"""


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
		ch = channel
		for phase in range(32):
			self.sync()
			time.sleep(0.1)
			data = self.ANT[ch].ADCDAQ.get_pattern(period=11);
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

