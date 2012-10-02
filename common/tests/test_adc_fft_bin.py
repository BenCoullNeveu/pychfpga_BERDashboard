#!/usr/bin/env python

'''
Class with testing function for testing the adc.
'''

from pychime.core import Inject_tools as inj
from pychime.common.tests.test_BaseClass import test_BaseClass
import numpy as np
import pychime.pffb as pfb
import pylab

class test_adc_fft_bin(test_BaseClass):
    '''
     Test class for testing chFPGA poly-phase filter-bank FFT bin shape.  
     Looks closely at bin number 31 (), Might want to change to be configurable.
    '''
        
    
    def check_fft_bin_shape(self):
        sine_amp = 32
        sine_freq_center = 31
        sine_freqs = np.arange(sine_freq_center-2,sine_freq_center+2,0.0025)
        spectra = []
        tone = []
        for sine_freq in sine_freqs:
            sine_fft_out = self.inject_sine(sine_amp=sine_amp, sine_freq=sine_freq, channels=[0], loops=20)
            spec = self.clean_output(sine_fft_out)
            print "Output with {0} Amp in bin {1} is {2}".format(sine_amp,sine_freq,spec[0][sine_freq_center])
            spectra.append(spec)
            tone.append(spec[0][sine_freq_center])
        tone = np.array(tone)
        xs = sine_freq_center-2 + np.arange(tone.size)*0.0025
        return xs, spectra, tone
            
        
    def execute(self): 
        ''' set mode to inject and get dc packets out'''
        inj.set_inject_mode(self.fpga_ctrl, self.fpga_recv)
        print self.inject_dc(0)
        print "initialized"

        self.fpga_ctrl.ANT[0].FFT.BYPASS=0
        self.fpga_ctrl.ANT[0].SCALER.BYPASS=0
        self.fpga_ctrl.ANT[0].SCALER.SHIFT_LEFT=0
        self.fpga_ctrl.ANT[0].FFT.FFT_SHIFT= 2**7 - 1

        x, spectra, tone = self.check_fft_bin_shape()
        xs, sim_spec = pfb.sim_pfb(taps=4, L=2048, window_function=pfb.boxcar, bin_number=31, resolution=2**20)        
        pylab.plot(x,20*np.log10(abs(tone)/abs(tone).max()))
        pylab.plot(xs,20*np.log10(abs(sim_spec)/abs(sim_spec).max()))
        pylab.xlim(x.min(),x.max())
        pylab.ylim(-60,0)
        pylab.savefig('Measured_vs_sim_binshape.pdf')
        return x, spectra, tone, xs, sim_spec
