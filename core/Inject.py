# -*- coding: utf-8 -*-

def set_inject_mode(fpga_ctrl, fpga_data):
	pass
	#

def inject(fc, fr, channel=0, data=[]):
	fc.ANT[channel].inject(data)
	returned_data = fr.read_frames()
	return returned_data[channel]

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
