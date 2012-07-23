# -*- coding: utf-8 -*-
import numpy as np
import time

def set_inject_mode(fpga_ctrl, fpga_recv):
    """ Sets all channels into injection mode"""
    fpga_recv.send_every_frame(1)
    fpga_ctrl.set_data_source('inject')
    fpga_ctrl.start_data_capture(burst_period_in_frames=1, number_of_bursts=0)
    fpga_recv.flush()
    # The first injected frame is dropped, so I send a dummy frame
    for k in range(1):
        for ch in range(8): 
            fpga_ctrl.ANT[ch].FR_DIST.reset_fifo()
            fpga_ctrl.ANT[ch].FR_DIST.inject_frame()

def inject(fc, fr, channels=range(8), data=None):
    """
    Injects data into the specified channels.
    
    If 'data' is a dicionnary, the data is sent to all channels represented by the corresponding keys.
    If data is None, a ramp will be sent to all channels specified by 'channels'. 
    By default, 'channels' covers all channels unless specified otherwise. 
    """
    print data
    returned_data = []
    if isinstance(data, dict):
        for ch in data.iterkeys():
            fc.ANT[ch].FR_DIST.inject_frame(data[ch])
            #time.sleep(0.01)
            returned_data.append(fr.read_frames()[ch])
    else:
        if isinstance(channels,int):
            channels = [channels]
        for ch in channels:
            fc.ANT[ch].FR_DIST.inject_frame(data)
            #time.sleep(0.01)
            got_data =fr.read_frames()
            #print "data returned"
            #print got_data
            returned_data.append(got_data[ch])
    #returned_data = fr.read_frames()
    return returned_data

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

def inject_dc(fc,fr, dc_level=1, channels=[0,1,2,3,4,5,6,7]):
    data = np.ones(2048)*dc_level
    return inject(fc,fr, channels, data)
    
def inject_sine(fc,fr, sine_amp=1, sine_freq=1.0, channels=[0,1,2,3,4,5,6,7]):
    '''
    Injects a sine wave with amplitude sine_level and frequency in frequency bin, assumes 2048 point fft.
    '''
    t = np.arange(2048)
    freq = sin_freq/2048.0
    data = sine_amp*np.sine(2.0*np.pi*freq*t)
    return inject(fc,fr, channels, data)
    
def check_fft_dc(fc,fr):
    dc_levels = range(-128,128)
    dcs = []
    for dc_level in dc_levels:
        dc_fft_out = inject_dc(fc,fr,dc_level)
        print "DC level with " + str(dc_level) + " input is " + str(dc_fft_out[0])
        dcs.append(dc_fft_out[0])
    #put some overflow checks here
    return dcs
    
def check_fft_sine(fc,fr):
    sine_amps = [5,120] #range(1,128)
    sine_freqs = np.arange(1,1024)
    spectra = []
    for sine_amp in sine_amps:
        for sine_freq in sine_freqs:
            sine_fft_out = inject_sine(fc,fr,sine_level=sine_amp, sine_freq=sine_freq)
            print "Amplitude of FFT of bin" + str(sine_freq) + " with amplitude " + str(sine_amp) + " is " + str(abs(sine_fft_out[sine_freq]))
            spectra.append(sine_fft_out)
    return spectra


if __name__ == '__main__':
    print "testing frame injection"
    import chFPGA_controller
    import chFPGA_receiver
    #import numpy as np
    ADC_TEST_MODE = 0     #  0= normal, 1= ramp, 2=pulse (1 high, 10 low)
    ADC_DELAYS_REV2_SN0001 = (
                              [20,26,25,25,25,25,25,24], #CH0
                              [23]*8, #CH1 
                              [24,22,20,20,20,20,20,17], #CH2 
                              [19]*8+[0], #CH3
                              [17]*8, #CH4
                              [17]*8, #CH5 
                              [19,19,19,18,17,16,20,20], #CH6 
                              [16]*8, #CH7
                              )
    FREF = 10 # FMC Reference clock frequency
    # Create the new chFPGA object.
    c = chFPGA_controller.chFPGA_controller(adc_delay_table=ADC_DELAYS_REV2_SN0001)
    c.sync()
    #c.set_data_source('inject')
    c.start_data_capture(burst_period_in_frames=1, number_of_bursts=0)
    channels=[4,5]
    cr = chFPGA_receiver.chFPGA_receiver()
    set_inject_mode(c,cr)
    dcs = check_fft_dc(c,cr)
    spectra = check_fft_sine(c,cr)

