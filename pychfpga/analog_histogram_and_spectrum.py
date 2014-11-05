#!/usr/bin/env python

'''
for testing analog data.
'''

import numpy as np
import matplotlib
matplotlib.use('Agg')
import time, pylab, csv
from validate import Validator
from configobj import *

class test_adc_analog_histogram:
    '''
     Test class for testing Analog data.   
    '''
    def __init__(self,fpga_ctrl, fpga_recv):
        '''
            Need fpga controller and receiver objects to get started.
        '''
        self.fpga_ctrl = fpga_ctrl
        self.fpga_recv = fpga_recv

    def configure_board(self):
        self.fpga_ctrl.set_fft_bypass(True, channels=range(16))
        self.fpga_ctrl.set_scaler_bypass(False, channels=range(16))
        self.fpga_ctrl.set_data_source('adc', channels=range(16))
        self.fpga_ctrl.set_ADC_mode(mode='data')
        self.fpga_ctrl.set_gain((1,27))
        time.sleep(1)
        self.fpga_ctrl.start_data_capture(burst_period_in_seconds=0.1, channels=range(16))
        self.fpga_ctrl.sync()
        time.sleep(2)
        return

        
    def plot_histogram(self, filename):
        datas = np.load(filename + '.npy')
        pylab.clf()
        
        for i in xrange(16):
            pylab.hist(datas[:,i,:].flatten(), bins=256, range = (-128,127))
            rms = datas[:,i,:].flatten().std()
            pylab.title(filename + ' Histogram Channel '+str(i+1) + ' RMS ' + str(rms))
            pylab.xlim(-128,127)
            pylab.savefig(filename + 'histogram_chan' +str(i+1)+'.pdf')
            pylab.clf()


    def spectrum(self, fname):
        datas = np.load(fname + '.npy')
        spectra = np.fft.fft(datas, axis=2)[:,:,:1024]
        spectrum = (np.abs(spectra)**2).mean(axis=0)
        pylab.clf()
        for i in range(16):
            pylab.plot(10.0*np.log10(np.abs(spectrum[i,:])))
            pylab.title(fname + ' Spectrum for Channel '+str(i+1))
            pylab.ylim(20,80)
            pylab.savefig(fname + '_spectrum_chan' +str(i+1)+'.pdf')
            pylab.clf()


    def execute(self, fname ):
        try:
            self.configure_board()
            self.fpga_recv.flush()
            filename = fname + '.npy'
            save_raw_frames.save_timestream_frames(self.fpga_recv, channels = range(16), frames=256, filename = filename)
            self.fpga_ctrl.stop_data_capture()
            self.plot_histogram(fname)
            self.spectrum(fname)
            #self.compute_bit_errors(fname)
            #confirm = raw_input('Start print_ramp_errors? This will print error counts until a KeyboardInterrupt. (y/n)\n')
            #if confirm == 'y' or confirm == 'Y':
            #    self.fpga_ctrl.ANT.print_ramp_errors()
        except:
            self.fpga_recv.close()
            raise

if __name__ == '__main__':

    import argparse
    import logging
    from pychfpga import save_raw_frames
    from pychfpga.icecore.icearray import IceArray, close_all_sockets
    from pychfpga.icecore.iceboard import IceBoard
    from pychfpga.core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware
    from pychfpga.core import chFPGA_receiver
    ADC_DELAY_TABLE= (
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
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    # parser.add_argument('-g', '--group_frames', action = 'store', type=int, default=4, help='Number of frames to group before sending to the GPU or FPGA correlator. The total size of the frame, including the header and ethernet obverhead, cannot exceed 8 kibytes.')
    # parser.add_argument('--enable_gpu_link', action = 'store', type=int, default=0, help='Enables the GPU link transmission')
    parser.add_argument('--force', action = 'store', type=int, default=0, help='Forces reprogramming of the FPGAs even if they are already programmed')
    parser.add_argument('--bitfile', action = 'store', type=str, default= '../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit',  help='Filename of the bitfile used to to program the FPGAs')
    #parser.add_argument('-s', '--subarray', action = 'store', nargs='+', type=int, help='Space-separated list of subarrays to include')
    parser.add_argument('-l', '--log_level', action = 'store', type =  str, default = 'debug', help = 'Log level: accpets either "debug" or "info" (default).')
    parser.add_argument('-n', '--output_name', action = 'store', type = str, default = 'adc_data_test', help = 'Naming of output files without extension')
    parser.add_argument("-c", "--conf_file", action = "store", \
                      default = "ch_master.conf", \
                      help = "Configuration file.")
    parser.add_argument("-s", "--spec_file", action = "store", \
                      default = "ch_master.spec", \
                      help = "Configuration file specifications.")
    args = parser.parse_args()
    
    log_level = {'info': logging.INFO, 'debug': logging.DEBUG}[args.log_level]
    logger = logging.getLogger('')
    logger.setLevel(log_level)
    handler = logging.FileHandler('histogram_and_analog_testing.log')
    logger.addHandler(handler)

    logger.info('------------------------')
    logger.info('analog_input_test.py: chFGPA test script')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))

    val_conf = Validator()
    conf = ConfigObj(args.conf_file, configspec = args.spec_file)
    ret = conf.validate(val_conf, preserve_errors = True)
    # Build up the adc_delay_table.
    n = int(conf["n_antenna"])
    adc_delay = []
    for i in range(n):
      name = "ch%02d" % i
      tmp_delay = []
      if not name in conf["fpga"]["adc_delay"]:
        log.critical("Could not find fpga.adc_delay.%s entry in configuration " \
                   "file." % (name))
        exit()
      else:
        this_chan = conf["fpga"]["adc_delay"][name]
      for j in range(len(this_chan)):
        k = int(this_chan[j])
        tmp_delay.append(k)
      if len(tmp_delay) != 16:
        log.critical("Entry fpga.adc_delay.%s needs 16 integer entries." % \
                   (name))
        exit()
      adc_delay.append((tmp_delay[:8],tmp_delay[8:]))
    ca = IceArray(uri=conf["fpga"]["db_file"], interface_ip_addr=conf["fpga"]["host_ip"])
    # Might want to move the list somewhere else/into conf file?
    ca.load_iceboards('/home/chime/ch_acq/pychfpga/iceboard_list.txt')
    ca.discover()
    bitfile_filename = conf["fpga"]["bitfile_name"]
    fpga_bitstream = ca.get_fpga_bitstream(bitfile_filename, ChimeFpgaFirmware)
    c = ca.get_iceboards(subarray=[conf["fpga"]["subarray"]]).index_by(IceBoard.serial_number)
    c.set_fpga_firmware(fpga_bitstream, force=args.force)
    c.open( \
        adc_delay_table=adc_delay, \
        init=1, \
        sampling_frequency=conf["fpga"]["samp_freq"] * 1e6, \
        reference_frequency=conf["fpga"]["ref_freq"], \
        data_width=8, \
        group_frames=conf["fpga"]["group_frames"], \
        enable_gpu_link = 0)
    for cc in c:
      cc.fpga.GPU.LINK_ENABLE=1
    c.fpga.set_corr_reset(1)
    time.sleep(0.1)
    c.fpga.set_corr_reset(0)
   
    for cc in c:
      print 'ADC 00', cc.fpga._adc_board[0].ADC[0].get_temperature()
      print 'ADC 01', cc.fpga._adc_board[0].ADC[1].get_temperature()
      print 'ADC 10', cc.fpga._adc_board[1].ADC[0].get_temperature()
      print 'ADC 11', cc.fpga._adc_board[1].ADC[1].get_temperature()
      #rs = [chFPGA_receiver.chFPGA_receiver(c_element.fpga.get_config(), ip_address=c_element.fpga_ip_addr, port=c_element.fpga_port_number+1, host_ip = '10.10.10.83') for c_element in c]
      r = chFPGA_receiver.chFPGA_receiver(cc.fpga.get_config(), ip_address=cc.fpga_ip_addr, port=cc.fpga_port_number+1, host_ip = conf["fpga"]["host_ip"])
      test = test_adc_analog_histogram(cc.fpga, r)
      test.execute(args.output_name)
      r.close()
      #[r.close() for r in rs]
      cc.fpga.close()
    close_all_sessions()
