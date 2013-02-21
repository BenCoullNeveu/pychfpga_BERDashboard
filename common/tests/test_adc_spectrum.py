#!/usr/bin/env python

'''
Class to test the adc by sweeping an input tone and checking the correlator output.
'''

import numpy as np
import time, pylab
from pychime.common.tests.test_BaseClass import test_BaseClass
from pychime.common.tests import fl6062a

class test_adc_spectrum(test_BaseClass):
    '''
     Test class for testing chFPGA behavior.  Runs through all frequency bins and checks the Power level 
     out.  
    '''
    def configure_board(self):
        self.fpga_ctrl.set_FFT_bypass(False, channels=[0,1,2,3,4,5,6,7])
        self.fpga_ctrl.set_data_source('adc', channels=[0,1,2,3,4,5,6,7])
        self.fpga_ctrl.set_ADC_mode(mode='data')
        time.sleep(1)
        self.fpga_ctrl.start_corr_capture(integration_period=0.5)
        #self.fpga_ctrl.sync()
        time.sleep(2)
        return

    def measure_adc_response(self,signal_generator):
        freqs_nyquest2 = np.linspace(800e6,400.390625e6,1024)
        freqs_nyquest1 = np.linspace(0,399.609375e6,1024)
        freqs_nyquest3 = np.linspace(800e6, 1199.609375e6,1024)
        freqs1 = np.concatenate([freqs_nyquest1,freqs_nyquest2])
        freqs = np.concatenate([freqs1, freqs_nyquest3]) 
        indicies1 = np.arange(freqs_nyquest1.size)
        indicies2 = np.arange(freqs_nyquest2.size)
        indicies3 = np.concatenate([indicies1,indicies2])
        indicies = np.concatenate([indicies3,indicies1])
        datas = np.empty(freqs.size, dtype=np.complex)
        for i,freq in enumerate(freqs):
            fl6062a.set_freq(freq, signal_generator)
            time.sleep(0.5)
            #self.fpga_recv.flush()
            data = self.fpga_recv.read_corr_frames(verbose=0,flush=True)
            print freq/1e6, data[0,indicies[i]]
            datas[i] = data[0,indicies[i]]
        return freqs, datas
        
    def execute(self):
        print "Make sure signal generator is connected to channel 1, " 
        test = raw_input("Press Enter to continue...")
        self.configure_board()
        self.fpga_recv.flush()
        signal_generator = fl6062a.GPIB(address=2, to=5, ip='192.168.0.37')
        fl6062a.set_freq(410e6,signal_generator)
        data_return = self.measure_adc_response(signal_generator)
        np.save('freq_sweep.npy', data_return[0])
        np.save('analog_data.npy', data_return[1])
        return data_return
