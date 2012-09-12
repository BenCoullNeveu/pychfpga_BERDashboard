#!/usr/bin/env python

'''
Class with testing function for testing the adc for algs running on the board
'''

from pychime.core import Inject as inj
from pychime.common.algs.alg_BaseClass import alg_BaseClass
import numpy as np
import pychime.pffb as pfb
import pylab

class alg_test_adc(alg_BaseClass):
    '''
     Test class for testing chFPGA behavior
    '''

    def inject_dc(self, dc_level=1, channels=[0,1,2,3,4,5,6,7]):
        '''
        Injects a DC level given by dc_level.  
        '''
        data = np.ones(2048)*dc_level
        return inj.inject(self.fpga_ctrl,self.fpga_recv, channels, data)
        
    def inject_sine(self, sine_amp=1, sine_freq=1.0, channels=[0,1,2,3,4,5,6,7]):
        '''
        Injects a sine wave with amplitude sine_level and frequency in frequency bin, assumes 2048 point fft.
        '''
        t = np.arange(2048)
        freq = sine_freq/2048.0
        data = sine_amp*np.sin(2.0*np.pi*freq*t)
        return inj.inject(self.fpga_ctrl,self.fpga_recv, channels, data)
        
    def clean_output(self,output):
        output = np.array(output)
        output = output.reshape(output.shape[0],output.shape[-1])
        spec = np.empty((output.shape[0],output.shape[1]/2),dtype=complex)
        spec.real = output[:,::2]
        spec.imag = output[:,1::2]
        return spec
        
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
        
    def check_fft_sine(self):
        sine_amps = [16,120] #range(1,128)
        sine_freqs = np.arange(1,1024)
        spectra = []
        tone=[]
        for sine_amp in sine_amps:
            for sine_freq in sine_freqs:
                for i in range(20):
                    sine_fft_out = self.inject_sine(sine_amp=sine_amp, sine_freq=sine_freq, channels=[0])
                spec = self.clean_output(sine_fft_out)
                print "Amplitude of FFT of bin " + str(sine_freq) + " with amplitude " + str(sine_amp) + " is " + str(abs(spec[0][sine_freq]))
                spectra.append(spec)
                tone.append(spec[0][sine_freq])
        return spectra, tone
    
    def check_fft_bin_shape(self):
        sine_amp = 32
        sine_freq_center = 31
        sine_freqs = np.arange(sine_freq_center-2,sine_freq_center+2,0.0025)
        spectra = []
        tone = []
        for sine_freq in sine_freqs:
            for i in range(20):
                sine_fft_out = self.inject_sine(sine_amp=sine_amp, sine_freq=sine_freq, channels=[0])
            spec = self.clean_output(sine_fft_out)
            print "Output with {0} Amp in bin {1} is {2}".format(sine_amp,sine_freq,spec[0][sine_freq_center])
            spectra.append(spec)
            tone.append(spec[0][sine_freq_center])
        tone = np.array(tone)
        xs = sine_freq_center-2 + arange(tone.size)*0.0025
        return xs, spectra, tone
        
    def check_fft_shifts(self):
        shifts = np.arange(11)
        specs = []
        for shift in shifts:
            self.fpga_ctrl.ANT[0].FFT.FFT_SHIFT= 2**shift - 1
            data = []
            for i in range(20):
                data.append(self.inject_sine( sine_amp=16.0, sine_freq=510.0, channels=[0]))
            #print data
            data = np.array(data)
            data = data.reshape(data.shape[0],data.shape[-1])
            spec = np.empty((data.shape[0],data.shape[1]/2),dtype=complex)
            spec.real = data[:,::2]
            spec.imag = data[:,1::2]
            specs.append(spec[-1])
        return np.array(specs)       
        
    def execute(self): 
        ''' set mode to inject and get dc packets out'''
        inj.set_inject_mode(self.fpga_ctrl, self.fpga_recv)
        print self.inject_dc(0)
        print "initialized"
        #self.fpga_ctrl.ANT[0].FFT.BYPASS=1
        #dcs = self.check_timestream_dc()        
        self.fpga_ctrl.ANT[0].FFT.BYPASS=0
        self.fpga_ctrl.ANT[0].SCALER.BYPASS=0
        self.fpga_ctrl.ANT[0].SCALER.SHIFT_LEFT=0
        self.fpga_ctrl.ANT[0].FFT.FFT_SHIFT= 2**7 - 1
        #spectra = self.check_fft_sine()
        x, spectra, tone = self.check_fft_bin_shape()
        xs, sim_spec = pfb.sim_pfb(taps=4, L=2048, window_function=pfb.boxcar, bin_number=31, resolution=2**20)        
        pylab.plot(x,abs(tone))
        pylab.plot(xs,abs(sim_spec))
        pylab.xlim(x.min(),x.max())
        pylab.savefig('Measured_vs_sim_binshape.pdf')
        return x, spectra, tone, xs, sim_spec

