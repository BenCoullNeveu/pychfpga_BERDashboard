#!/usr/bin/env python

'''
Class with testing function for testing the adc.
'''

from pychime.core import Inject as inj
from pychime.common.tests.test_BaseClass import test_BaseClass
import numpy as np
import time, pylab

class test_corr(test_BaseClass):
    '''
     Test class for testing chFPGA behavior.  Runs through all frequency bins and checks the Power level 
     out.  
    '''

    def unscramble(self, data):
        '''
        Assumes data is (5,512) in shape array
        writes to (10,256) shape, where the 10 
        are correlation pairs:  AA, AB,AC,AD,BB,BC,BD,CC,CD,DD
        and the 256 are frequency channels.  Will need to further combine output from 4
        Correlators to get all frequencies. Hopefully will see a pattern to put in for loop.  Also should change to 
        better support the actual data coming out
        '''
        corr_output = np.zeros((10,256), dtype=np.complex)
        corr_output[0,::2] = data[4,::4] #AA
        corr_output[0,1::2] = data[0,3::4] #AA
        corr_output[1,::2] = data[3,::4] #AB
        corr_output[1,1::2] = data[1,3::4] #AB
        corr_output[2,::2] = data[3,1::4] #AC
        corr_output[2,1::2] = data[1,2::4] #AC
        corr_output[3,::2] = data[3,2::4] #AD
        corr_output[3,1::2] = data[1,1::4] #AD
        corr_output[4,::2] = data[4,1::4] #BB
        corr_output[4,1::2] = data[0,2::4] #BB
        corr_output[5,::2] = data[2,::4] #BC
        corr_output[5,1::2] = data[2,3::4] #BC
        corr_output[6,::2] = data[2,1::4] #BD
        corr_output[6,1::2] = data[2,2::4] #BD
        corr_output[7,::2] = data[4,2::4] #CC
        corr_output[7,1::2] = data[0,1::4] #CC
        corr_output[8,::2] = data[1,::4] #CD
        corr_output[8,1::2] = data[3,3::4] #CD
        corr_output[9,::2] = data[4,3::4] #DD
        corr_output[9,1::2] = data[0,::4] #DD
        return corr_output
        
        
    def execute(self): 
        ''' set bypass FFT and '''
        self.fpga_ctr.set_FFT_bypass(True, channels=[0,1,2,3,4,5,6,7])
        self.fpga_ctr.set_data_source('func_zero')
        self.fpga_ctr.set_data_source('func_real_ramp', channels=[0,1,2,3])
        self.fpga_ctr.start_data_capture(burst_period_in_seconds=1.0, number_of_bursts=0)
        time.sleep(2)
        test = self.fpga_recv.read_frames()
        test = self.fpga_recv.read_frames()
        output = self.fpga_recv.read_corr_frames()
        output = self.fpga_recv.read_corr_frames()
        dout = np.array([output[0],output[1],output[2],output[3],output[4]])
        data = self.unscramble(dout)
        expected = np.load('expected_real_ramp_corr_1sec.npy')
        pylab.plot(abs(data[0,:256]))
        pylab.plot(abs(expected[0,:256]))
        pylab.xlabel('Freq Channel')
        pylab.ylabel('abs correlation')
        pylab.savefig('Correlation_check.pdf')
        pylab.show()
        return data