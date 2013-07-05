#!/usr/bin/python
"""
run_corr.py script 
 Script to run the 4-channel correlator.
#
History:
    2012-09-28 KMB: First attempt
    2012-04-28 JFC: Cleanup. Added file_info. CHange date in filename to ISO format. 
"""

from pychfpga.core import chFPGA_controller
from pychfpga.core import chFPGA_receiver_raw
import numpy as np
import time, pylab, file_utils, os
import pickle
import getpass #used to get username
import sys
import argparse
import socket

class run_corr():
    '''
    class for running chFPGA correlator
     out.  
    '''
    def __init__(self,fpga_ctrl, fpga_recv, integration_period=1, args = None):
        '''
            The baseclass has one data member, called data. 
            It is meant to hold the results of executing the algorithm once.
            you must call alg_BaseClass.__init__(self) from your derived __init__
            method.
        '''
        self.fpga_ctrl = fpga_ctrl
        self.fpga_recv = fpga_recv
        self.integration_period = integration_period
        self.args = args
        self.channels = range(8)
        #set bypass FFT and initial settings'''
        print "Setting up data acquisition and signal processing chain"
        self.fpga_ctrl.set_data_source('adc') # This should come first, as it reinitializes the whole signal processing chain.
        self.fpga_ctrl.set_FFT_bypass(False, channels=self.channels)
        self.fpga_ctrl.set_FFT_shift(fft_shift=2**5-1, channels=self.channels)
        self.fpga_ctrl.set_gain(log2_gain=1, channels=self.channels)
        #self.fpga_ctrl.set_ADC_mode(mode='data')
        #print "set adc mode"
        #time.sleep(1)
        #self.fpga_ctrl.set_corr_reset(False)
        #self.fpga_ctrl.start_data_capture(burst_period_in_seconds=0.9, number_of_bursts=0)
        #Currently 0.25s is the fastest will go with regular reciever.
        #self.fpga_ctrl.start_corr_capture(integration_period=1)
        #print "set to 1s"
        # time.sleep(3)
        # self.fpga_ctrl.start_corr_capture(integration_period=0.1)
        # print "set to 0.1s"
        # time.sleep(2)
        # self.fpga_ctrl.start_corr_capture(integration_period=0.05)
        # print "set to 0.05s"
        # time.sleep(2)
        #self.HOUR = 3600/self.integration_period
        #self.fpga_ctrl.start_corr_capture(integration_period=0.27373734585)
        self.fpga_ctrl.start_corr_capture(integration_period=self.integration_period)
        print " Correlator started with an integration time of %0.1s s" % self.integration_period
 
        print " Discarding first correlator frame(s) to ensure the PFB frame buffers are full"
        frames_to_discard = 1
        for i in range(frames_to_discard):
            print 'Discarding correlator frame %i/%i' % (i+1,frames_to_discard)
            self.get_data()

        #time.sleep(1)
        #self.fpga_ctrl.sync()  #sync means crash!
        #self.fpga_recv.flush()
        print 'Initialization Complete'



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
        data = self.fpga_recv.read_corr_frames()
        return data

    def init_file(self, fcount):
        fname= "{0}/out_{1}.{2:04g}".format(self.basename, time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()),fcount) #'%s.%04i' % (self.basename, fcount)
        print fname
        fout = open(fname, 'w+b')
        #est_clk = 65
        #acc_len = 65536 #fake for now
        #file_utils.write_header(fout, est_clk, acc_len)
        return fout

    def init_housekeeping(self):
        #print basename
        os.mkdir(self.basename)
        os.chdir(self.basename)
        timeFileName = 'time_file.txt'
        timefile = open(timeFileName, 'w', 1)
        temperatureFileName = 'temperature_file.txt'
        temperaturefile = open(temperatureFileName, 'w', 1)
        datainfoFileName = 'data_info.txt'
        datainfofile = open(datainfoFileName, 'w')
        print "Housekeeping established"
        return datainfofile, timefile, temperaturefile

    def convert_format(self, accumulator):
        #want 1024 int32 real, int32 imag
        ncorr, nfreq = accumulator.shape
        interleave_a = np.zeros([ncorr,2*nfreq],dtype=np.int32)
        gain = 1
        acc_real = (gain*accumulator).real.astype(np.int32)
        acc_imag = (gain*accumulator).imag.astype(np.int32)
        #interleave_a[:,::2] = acc_real
        #interleave_a[:,1::2] = acc_imag
        ## Find a better way?
        #Should be 1024 eventually
        for i in range(nfreq):
            interleave_a[:,i * 2]     = acc_real[:,i]
            interleave_a[:,i * 2 + 1] = acc_imag[:,i]
        #print interleave_a
        return interleave_a

    def check_corr_frame(self):
        data = self.get_data()
        nchan = (-1+np.sqrt(1+8*data.shape[0]))/2
        pylab.clf()
        for i in range(int(nchan)):
            #get autocorrelation
            k = i*nchan - i*(i+1)/2 + i
            pylab.plot(abs(data[k].real), label = 'Ch%i' % i)
        pylab.yscale('log')
        pylab.xlabel('Frequency bin #')
        pylab.ylabel('Correlator counts')
        pylab.title('First autocorrelations of %s' % self.basename)
        pylab.rcParams['legend.loc']='best' # Tell pylab to use the best location for the legend
        pylab.grid(True, which='both')
        pylab.legend()
        if self.args.show_graph:
            pylab.show()
        if not self.args.no_data:
            pylab.savefig('autocorr_plots.pdf')
        #pylab.clf()
        print 'Made autocorrelation plot'

    def execute(self):

        nowtime=time.time()
        self.basename = '/data/out_%s' %  time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) # Use GMT time in ISO 8601 format as base filename

        nfiles = 0

        #Add spectrum file as well
        if not self.args.no_data:
            datainfofile, timefile, temperaturefile = self.init_housekeeping()

        ##self.check_corr_frame() needs to be updated for unscrambling

        if self.args.no_data:
            return

        try:
 
             # Prepare and save the data information
            config = self.fpga_ctrl.get_config()
            # Add useful info that is not already in the config structure
            config.job_start_time = time.time()
            config.job_basename = self.basename
            config.job_username = getpass.getuser()
            config.job_command = sys.argv
            config.message = args.message
            # Add other info as needed
            datainfofile.write(
                '# Data information\n'
                '# This data can be parsed back into a python dictionary using \n'
                '#    mydict=dict(); execfile(''filename'', mydict)\n'
                '# or it can be converted in attributes of the object ''myobject'' with\n'
                '#    execfile(''filename'', myobject.__dict__)\n'
                )
            datainfofile.write(str(config))
            datainfofile.write('\n\n')
            datainfofile.write('# The Pickled version of the same information follows\n\n')
            datainfofile.write('_pickled_data="""\n')
            pickle.dump(config, datainfofile)
            datainfofile.write('\n"""\n')
            datainfofile.close()

            # Debug by JFC
            #for corr in self.fpga_ctrl.CORR:
            #    corr.ACC.status()
            while nfiles < (3000):
                fileHandle = self.init_file(nfiles)
                for i in xrange(3600):
                    data = self.get_data()
                    fileHandle.write(data)
                    # interleave_a = self.convert_format(data)
                    # ##interleave_a = data
                    # for ia in interleave_a:
                    #     fileHandle.write(ia)
                    if (i % (1//self.integration_period)) == 0:
                        nowtime=time.time()
                        try:
                            temperature = self.fpga_ctrl.ADC_BOARD.AmbTemp.temperature
                        except:
                             temperature = 'null'
                        temperaturefile.write(str(temperature) + '\n' )
                        timefile.write(str(nowtime) + '\n')
                        sys.stdout.write('. ')
                        sys.stdout.flush()
                fileHandle.close()
                nfiles += 1
            timefile.close()
            temperaturefile.close()
        except (KeyboardInterrupt, SystemExit):
            self.fpga_ctrl.close()
            self.fpga_recv.close()
            datainfofile.close()
            timefile.close()
            temperaturefile.close()
            fileHandle.close()
            print "tried to close nicely"
        except:
            self.fpga_ctrl.close()
            self.fpga_recv.close()
            datainfofile.close()
            timefile.close()
            temperaturefile.close()
            fileHandle.close()
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


ADC_DELAY_TABLE = ADC_DELAYS_REV2_SN0001_KC705_FMC700 #ADC_DELAYS_REV2_SN0001 # select the table corresponding to the FMC serial number

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('--show_graph', action = 'store_true', help='Shows the first autocorelation graph before proceeding')
    parser.add_argument('-n', '--no_data', action = 'store_true', help='Does not store any data.')
    parser.add_argument('-m', '--message', help='Additional message to write to data header, in quotes "MESSAGE HERE"')
    parser.add_argument('-f', '--sampling_frequency', action = 'store', type=float, default=850, help='Sampling frequency of the ADC in MHz')
    args = parser.parse_args()
    print 'Using Sampling frequency of %0.3f MHz' % args.sampling_frequency
    c = chFPGA_controller.chFPGA_controller(ip_address='10.10.10.11', port_number=41000, adc_delay_table=ADC_DELAY_TABLE, init=1, sampling_frequency=args.sampling_frequency*1e6, reference_frequency=10e6) # pylint: disable=C0103
    chFPGA_config = c.get_config()
    #r = receiver_corr_fast.chFPGA_receiver(chFPGA_config, ip_address='10.10.10.11', port=41001)
    r = chFPGA_receiver_raw.chFPGA_receiver(chFPGA_config, ip_address='10.10.10.11', port=41001)
    #c.sync() sync means crash!!!
    corr = run_corr(c, r, integration_period=1.0, args=args)
    corr.execute()
    c.close()
    r.close()


