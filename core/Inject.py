# -*- coding: utf-8 -*-
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 
"""
Inject.py module 
 Provides functions to inject data into the chFPGA antenna processing pipelines and read out the resulting data

History:
    2012-09-28 JFC: Modified to allow synchronized multi-channel injection.
    2012-09-18 JFC: Switched the order of the inject() parameters

"""

import numpy as np
import time

###set bypass fft or not.

def set_inject_mode(fpga_ctrl, fpga_recv, bypass_FFT=False, channels=range(8)):
    """ Sets all channels into injection mode"""
    fpga_recv.send_every_frame(1)
    fpga_ctrl.set_default_channels(channels) # sets which channels are used by default in subsequent commands
    fpga_ctrl.set_FFT_bypass(bypass_FFT)
    fpga_ctrl.set_data_source('inject')
    fpga_ctrl.pulse_ant_reset() # resets the antenna processing chain to eliminate any frames in transit in the processing pipeline
    fpga_ctrl.start_data_capture(burst_period_in_frames=1, number_of_bursts=0)
    fpga_recv.flush()
    for ch in channels: 
        fpga_ctrl.ANT[ch].FR_DIST.reset_fifo()
    ### changed to inject until see something coming out.  Record number of frames
    ### if get to 100, break out of the loop. 
    filling_buffer = True
    pipeline = 0
    while (filling_buffer):
        for ch in channels: 
            fpga_ctrl.ANT[ch].FR_DIST.inject_frame()
        try:
            #fpga_recv.read_frames()
            print "Got data"
            if ( pipeline > 20):
                filling_buffer=False
            else:
                pipeline +=1
        except:
            print "pipeline not full"
            pipeline += 1
        if (pipeline >100):
            break
                            
    time.sleep(0.5)
    print fpga_recv.length()
    fpga_recv.flush()

    #if fpga_recv.length():
    #    fpga_recv.read_frames()        
    #fpga_recv.flush()

def inject(fc, fr, channels=None, data=None):
    """
    Injects data into the specified channels.
    
    If 'data' is a dictionnary, the data is sent to all channels represented by the corresponding keys.
    If data is None, a ramp will be sent to all channels specified by 'channels'. 
    By default, 'channels' covers all channels unless specified otherwise. 

    2012-09-18 JFC: Switched the order of the parameters
    2012-09-19 KMB: Switched back parameters to keep compatiblity
    """
    #print data
    if channels is None:
            channels = fc.get_default_channels()
            
    returned_data = {}

    fc.set_global_trigger(False) # Stop injection buffers from being read out
    # Inject data
    fc.inject_frame(data, channels)

    # Read the results. The frames can come in any order.
    fc.set_global_trigger(True) # Start reading of all injection buffers simulataneously
    timestamp = None
    for i in range(len(channels)): # Read as many times as we injected channels.
        data = fr.read_frames()
        if timestamp is None:
            timestamp = data['timestamp'] # set the timestamp
        elif timestamp != data['timestamp']:
            print 'Warning: incoming frames have different timestamps.'
        returned_data.update(data) # Add the frame to the dictionary
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

