#!/usr/bin/python

"""
run_corr.py script 
 Script to run the 4-channel correlator.
#
History:
    2012-09-28 KMB: First attempt 
"""

from pychime.core import chFPGA_controller
from pychime.core import chFPGA_receiver
import numpy as np
import time, pylab, file_utils, os

class run_corr():
    '''
    class for running chFPGA correlator
     out.  
    '''
    def __init__(self,fpga_ctrl, fpga_recv):
        '''
            The baseclass has one data member, called data. 
            It is meant to hold the results of executing the algorithm once.
            you must call alg_BaseClass.__init__(self) from your derived __init__
            method.
        '''
        self.fpga_ctrl = fpga_ctrl
        self.fpga_recv = fpga_recv
        #set bypass FFT and initial settings'''
        self.fpga_ctrl.set_FFT_bypass(True, channels=[0,1,2,3,4,5,6,7])
        self.fpga_ctrl.set_data_source('func_zero')
        self.fpga_ctrl.set_data_source('func_real_ramp', channels=[0,1,2,3])
        self.fpga_ctrl.set_corr_reset(False)
        self.fpga_ctrl.start_data_capture(burst_period_in_seconds=1.0, number_of_bursts=0)
        time.sleep(2)

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

    def clean_spec(self,output):
        out_list=[]
        for item in output.items():
            if type(item[0]) == int:
                out_list.append(item[1])
        out_list = np.array(out_list)
        out_list = out_list.reshape(out_list.shape[0],out_list.shape[-1])
        spec = np.empty((out_list.shape[0],out_list.shape[1]/2),dtype=complex)
        spec.real = out_list[:,::2]
        spec.imag = out_list[:,1::2]
        return spec
        
        
    def get_data(self): 

        spectrum = self.fpga_recv.read_frames()
        spectrum = self.clean_spec(spectrum)
        output = self.fpga_recv.read_corr_frames()
        dout = np.array([output[0],output[1],output[2],output[3],output[4]])
        data = self.unscramble(dout)
        return spectrum, data

    def init_file(self, fcount):
        filename = 'out'
        if fcount == 0:
            nowtime=time.time()
            #nowtime = 1338143259.2
            basename = '\\Users\\kbandura\\chime\\data\\'+filename + '_'+ str(nowtime)+'\\'
            #print basename
            os.mkdir(basename)
            os.chdir(basename)
        fname=filename+str(time.time())+'.'
        print fname
        fout = open(fname+'%04i'%fcount, 'w+b')
        #timeFileName = basename+'time_file.txt'
        #timefile = open(timeFileName, 'w+')
        #temperatureFileName = basename+'temperature_file.txt'
        #temperaturefile = open(temperatureFileName, 'w+')
        est_clk = 65
        acc_len = 65536 #fake for now
        file_utils.write_header(fout, est_clk, acc_len)
        return fout

    def convert_format(self, accumulator):
        #want 1024 int32 real, int32 imag
        interleave_a = np.zeros([10,2048],dtype=np.int32)
        gain = 1
        acc_real = (gain*accumulator).real.astype(np.int32)
        acc_imag = (gain*accumulator).imag.astype(np.int32)
        #interleave_a[:,::2] = acc_real
        #interleave_a[:,1::2] = acc_imag
        ## Find a better way?
        #Should be 1024 eventually
        for i in range(256):
            interleave_a[:,i * 2]     = acc_real[:,i]
            interleave_a[:,i * 2 + 1] = acc_imag[:,i]
        #print interleave_a
        return interleave_a

    def execute(self):
        nfiles = 0
        #Add spectrum file as well
        try: 
            while nfiles < 4:
                fileHandle = self.init_file(nfiles)
                for i in xrange(NSEC):
                    spectrum, data = self.get_data()
                    interleave_a = self.convert_format(data)
                    for ia in interleave_a:
                        fileHandle.write(ia)
                    print '. ',
                fileHandle.close()
                nfiles += 1
        except KeyboardInterrupt:
            self.fpga_ctrl.close()
            self.fpga_recv.close()
            raise

# Default data and clock line delays for the two FMC boards/ML605 combination.
# First 8 values are the delays for bits 0 to 7, 8th value is the delay for the clock line.
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


ADC_DELAY_TABLE = ADC_DELAYS_REV2_SN0001 # select the table corresponding to the FMC serial number

NSEC=60*60

if __name__ == "__main__":
    c = chFPGA_controller.chFPGA_controller(adc_delay_table=ADC_DELAY_TABLE) # pylint: disable=C0103
    r = chFPGA_receiver.chFPGA_receiver()
    c.sync()

    #channels=[0,1,2,3]
    corr = run_corr(c,r)
    corr.execute()
    c.close()
    r.close()



