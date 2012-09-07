#!/usr/bin/env python

'''
Class with testing function for testing the adc for algs running on the board
'''

from pychime.core import Inject as inj
from pychime.common.algs.alg_BaseClass import alg_BaseClass
import numpy as np

class alg_test_adc(alg_BaseClass):
    '''
     Base class for all  alg operations on chFPGA
    '''

    def inject_dc(self,fc,fr, dc_level=1, channels=[0,1,2,3,4,5,6,7]):
        data = np.ones(2048)*dc_level
        return inj.inject(fc,fr, channels, data)
        
    def inject_sine(self,fc,fr, sine_amp=1, sine_freq=1.0, channels=[0,1,2,3,4,5,6,7]):
        '''
        Injects a sine wave with amplitude sine_level and frequency in frequency bin, assumes 2048 point fft.
        '''
        t = np.arange(2048)
        freq = sine_freq/2048.0
        data = sine_amp*np.sin(2.0*np.pi*freq*t)
        return inj.inject(fc,fr, channels, data)
        
    def check_fft_dc(self,fc,fr):
        dc_levels = range(-128,128)
        dcs = []
        for dc_level in dc_levels:
            dc_fft_out = self.inject_dc(fc,fr,dc_level)
            #print dc_fft_out
            print "DC level with " + str(dc_level) + " input is " + str(dc_fft_out[0])
            dcs.append(dc_fft_out[0])
        #put some overflow checks here
        return dcs
        
    def check_fft_sine(self,fc,fr):
        sine_amps = [5,120] #range(1,128)
        sine_freqs = np.arange(1,1024)
        spectra = []
        for sine_amp in sine_amps:
            for sine_freq in sine_freqs:
                sine_fft_out = inject_sine(fc,fr,sine_level=sine_amp, sine_freq=sine_freq)
                print "Amplitude of FFT of bin" + str(sine_freq) + " with amplitude " + str(sine_amp) + " is " + str(abs(sine_fft_out[sine_freq]))
                spectra.append(sine_fft_out)
        return spectra
        
    def execute(self): 
        ''' set mode to inject and get dc packets out'''
        inj.set_inject_mode(self.fpga_ctrl, self.fpga_recv)
        #dcs = self.check_fft_dc(self.fpga_ctrl,self.fpga_recv)
        self.fpga_ctrl.ANT[0].FFT.BYPASS=0
        self.fpga_ctrl.ANT[0].SCALER.BYPASS=0
        self.fpga_ctrl.ANT[0].SCALER.SHIFT_LEFT=3
        print "initialized"
        data = []
        for i in range(20):
            data.append(self.inject_sine(self.fpga_ctrl, self.fpga_recv, sine_amp=16.0, sine_freq=510.0, channels=[0]))
        print data
        return data