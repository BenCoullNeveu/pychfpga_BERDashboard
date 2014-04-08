#!/usr/bin/python

"""
timestream_rms.py script 
 Script to run the 5-channel system and just print to screen the rms of the adc timestream input.
#
History:
    2012-12-04 KMB: First attempt 
"""

from pychfpga.core import chFPGA_controller
from pychfpga.core import chFPGA_receiver
import numpy as np
import time, sys, os

ADC_DELAYS_REV2_SN0001 = (
    [20,26,25,25,25,25,25,24], #CH0
    [22]*8, #CH1 
    [22,22,20,20,20,20,20,19], #CH2 
    [18]*8+[0], #CH3
    [17]*8, #CH4
    [17]*8, #CH5 
    [19,19,19,18,17,16,20,20], #CH6 
    [16]*8, #CH7
    )

ADC_DELAYS_REV2_SN0001_KC705_FMC700 = (
    [13,10,9,10,9,10,9,9], #CH0
    [7]*8, #CH1 
    [11,11,8,9,7,8,8,7], #CH2 
    [6]*8, #CH3
    [14]*8, #CH4
    [14]*8, #CH5 
    [13]*8, #CH6 
    [0]*8, #CH7
    )

ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 = (
    ([16]*8,     [3]*8), #CH0
    ([7]*8,                       [3]*8), #CH1 
    ([22]*8,    [3]*8), #CH2 
    ([19]*8,                       [3]*8), #CH3
    ([15]*8,                        [3]*8), #CH4
    ([14, 13, 14, 14, 13, 14, 15, 14],    [3]*8), #CH5 
    ([18]*8,     [3]*8), #CH6 
    ([17]*8,                       [4]*8), #CH7

    ([15, 17, 15, 18, 17, 14, 17, 15],   [3]*8), #CH8
    ([16]*8,                       [4]*8), #CH9
    ([20]*8,                       [3]*8), #CH10
    ([18]*8,                     [3]*8), #CH11
    ([15]*8,                       [3]*8), #CH12
    ([18]*8,                       [3]*8), #CH13
    ([18]*8,                       [3]*8), #CH14
    ([16]*8,                       [3]*8)  #CH15
    )

def print_RMS(r):
    channels = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
    cont = True
    while cont:
        try:
            a = r.read_frames()
            for chan in channels:
                sys.stdout.write("ch%d %f\n" % (chan, np.log2(a[chan].std())))
            for i in xrange(2):
                sys.stdout.write("\n")
            time.sleep(1.5)
            sys.stdout.flush()
            os.system("cls" if os.name=='nt' else 'clear')
        except KeyboardInterrupt:
            print "Stopped by User"
            cont = False
        except KeyError:
            print "key error, missing data..."
            pass    

if __name__ == '__main__':
    ADC_DELAY_TABLE = ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 # ADC_DELAYS_REV2_SN0001 # select the table corresponding to the FMC serial number
    c = chFPGA_controller.chFPGA_controller(ip_address='10.10.10.11', port_number=41000, adc_delay_table=ADC_DELAY_TABLE, init=1, sampling_frequency=800e6, reference_frequency=10e6, data_width=8, group_frames=2, enable_gpu_link = 1, host_ip = '10.10.10.200') # pylint: disable=C0103
    chFPGA_config = c.get_config()
    r = chFPGA_receiver.chFPGA_receiver(chFPGA_config, ip_address='10.10.10.11', port=41001, host_ip = '10.10.10.200')
    c.set_data_source('adc')
    c.set_adc_mode('data')
    c.set_FFT_bypass(True)
    c.set_scaler_bypass(False)
    c.set_gain((1,27))
    c.start_data_capture(burst_period_in_seconds=1.5, number_of_bursts=0)
    time.sleep(2)
    print_RMS(r)
    c.close()
    r.close()
    
