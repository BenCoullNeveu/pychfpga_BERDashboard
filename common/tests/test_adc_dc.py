#!/usr/bin/env python

'''
Class with testing function for testing the adc.
'''

from pychime.core import Inject as inj
from pychime.common.tests.test_BaseClass import test_BaseClass
import numpy as np
import pychime.pffb as pfb
import pylab

class test_adc_dc(test_BaseClass):
    '''
     Test class for testing chFPGA behavior.  Tests DC level returned is the dc level
      injected for the full range of the ADC.  more?
    '''
        
    def check_timestream_dc(self):
        '''
        Checks that dc level injected is what is returned.
        '''
        original_bypass = np.zeros((8,), dtype=np.int)
        for i in range(8):
            original_bypass[i] = self.fpga_ctrl.ANT[i].FFT.BYPASS
            self.fpga_ctrl.ANT[i].FFT.BYPASS=1
        dc_levels = range(-128,128)
        dcs = []
        for dc_level in dc_levels:
            dc_fft_out = self.inject_dc(dc_level)
            #print dc_fft_out
            print "DC level with " + str(dc_level) + " input is " + str(dc_fft_out[0])
            dcs.append(dc_fft_out[0])
        #put some overflow checks here
        for i in range(8):
            self.fpga_ctrl.ANT[i].FFT.BYPASS=original_bypass[i]
        return dcs

    def execute(self): 
        ''' set mode to inject and get dc packets out'''
        inj.set_inject_mode(self.fpga_ctrl, self.fpga_recv)
        print self.inject_dc(0)
        print "initialized"
        self.fpga_ctrl.ANT[0].FFT.BYPASS=1
        dcs = self.check_timestream_dc()        
        print "Test passed??  "
        return dcs