#!/usr/bin/python
"""
run_corr.py script 
 Script to run the 4-channel correlator.
#
History:
    2012-09-28 KMB: First attempt
    2012-04-28 JFC: Cleanup. Added file_info. CHange date in filename to ISO format. 
"""

from pychime.core import chFPGA_controller
#from pychime.core import chFPGA_receiver_raw
import numpy as np
import time, pylab, file_utils, os
import pickle
import getpass #used to get username
import sys
import argparse
from subprocess import Popen
import signal
#import socket

class setup_corr():
    '''
    class for running chFPGA correlator
     out.  
    '''
    def __init__(self,fpga_ctrl, integration_period=1, args = None):
        '''
            The baseclass has one data member, called data. 
            It is meant to hold the results of executing the algorithm once.
            you must call alg_BaseClass.__init__(self) from your derived __init__
            method.
        '''
        self.fpga_ctrl = fpga_ctrl
        self.integration_period = integration_period
        self.args = args
        self.channels = range(8)
        #set bypass FFT and initial settings'''
        print "Setting up data acquisition and signal processing chain"
        self.fpga_ctrl.set_data_source('adc') # This should come first, as it reinitializes the whole signal processing chain.
        self.fpga_ctrl.set_FFT_bypass(False, channels=self.channels)
        self.fpga_ctrl.set_FFT_shift(fft_shift=2**5-1, channels=self.channels)
        self.fpga_ctrl.set_gain(log2_gain=1, channels=self.channels)
        self.fpga_ctrl.start_corr_capture(integration_period=self.integration_period)
        #print self.integration_period
        print " Correlator started with an integration time of %0.4s s" % self.integration_period
        print 'Initialization Complete'


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


    def execute(self):

        nowtime=time.time()
        self.basename = '/data/out_%s' %  time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) # Use GMT time in ISO 8601 format as base filename

        nfiles = 0

        #Add spectrum file as well
        datainfofile, timefile, temperaturefile = self.init_housekeeping()

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
            proc = Popen(["./chr", "net", "41001", (self.basename+'/out_'+str(nowtime)+".h5"), str(nowtime)], cwd='/home/chime/pychime')
            # Debug by JFC
            #for corr in self.fpga_ctrl.CORR:
            #    corr.ACC.status()
            while nfiles < (3000):
                for i in xrange(3600):
                    time.sleep(1)
                    nowtime=time.time()
                    try:
                        temperature = self.fpga_ctrl.ADC_BOARD.AmbTemp.temperature
                    except:
                         temperature = 'null'
                    temperaturefile.write(str(temperature) + '\n' )
                    timefile.write(str(nowtime) + '\n')
                    sys.stdout.write('. ')
                    sys.stdout.flush()
                nfiles += 1
            timefile.close()
            temperaturefile.close()
        except (KeyboardInterrupt, SystemExit):
            proc.send_signal(signal.SIGINT)
            self.fpga_ctrl.close()
            datainfofile.close()
            timefile.close()
            temperaturefile.close()
            print "tried to close nicely"
        except:
            proc.send_signal(signal.SIGINT)
            self.fpga_ctrl.close()
            datainfofile.close()
            timefile.close()
            temperaturefile.close()
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
    parser.add_argument('-m', '--message', help='Additional message to write to data header, in quotes "MESSAGE HERE"')
    parser.add_argument('-f', '--sampling_frequency', action = 'store', type=float, default=850, help='Sampling frequency of the ADC in MHz')
    args = parser.parse_args()
    print 'Using Sampling frequency of %0.3f MHz' % args.sampling_frequency
    c = chFPGA_controller.chFPGA_controller(ip_address='10.10.10.11', port_number=41000, adc_delay_table=ADC_DELAY_TABLE, init=1, sampling_frequency=args.sampling_frequency*1e6, reference_frequency=10e6) # pylint: disable=C0103
    chFPGA_config = c.get_config()
    #c.sync() sync means crash!!!
    corr = setup_corr(c, integration_period=1.0, args=args)
    corr.execute()
    c.close()


