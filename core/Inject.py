# -*- coding: utf-8 -*-

def set_inject_mode(fpga_ctrl, fpga_recv):
    fpga_ctrl.set_data_source('inject')
    fpga_ctrl.start_data_capture(burst_period_in_frames=1, number_of_bursts=0)
    fpga_recv.flush()

def inject(fc, fr, channel=0, data=None):
    print data
    fc.ANT[channel].FR_DIST.inject_frame(data)
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

if __name__ == '__main__':
    print "testing frame injection"
    import chFPGA_controller
    import chFPGA_receiver
    import numpy as np
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
    c.set_data_source('inject')
    c.start_data_capture(burst_period_in_frames=1, number_of_bursts=0)
    channels=[4,5]
    cr = chFPGA_receiver.chFPGA_receiver()
    data1 = np.load('../testing_rfof_2.npy')
    out = []
    for channel in channels:
        out.append(inject(c, cr, channel, data1[0]))