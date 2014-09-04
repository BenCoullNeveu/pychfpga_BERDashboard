#!/usr/bin/env python

'''
for testing analog data.
'''

import numpy as np
import matplotlib
matplotlib.use('Agg')
import time, pylab, csv


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
    parser.add_argument('--ip', action = 'store', type=str, default='10.10.10.11', help='IP address of the board')
    parser.add_argument('--host_ip', action = 'store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. If not specified, the controller will attempt to identify the proper host based on the FPGA IP address.')
    parser.add_argument('-l', '--log_level', action = 'store', type =  str, default = 'info', help = 'Log level: accpets either "debug" or "info" (default).')
    parser.add_argument('-n', '--output_name', action = 'store', type = str, default = 'adc_data_test', help = 'Naming of output files without extension')
    args = parser.parse_args()
    
    log_level = {'info': logging.INFO, 'debug': logging.DEBUG}[args.log_level]
    logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.WARN)

    logger = logging.getLogger(__name__)
    logger.info('------------------------')
    logger.info('analog_input_test.py: chFGPA test script')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))

    c = ChimeFpgaFirmware(ip_address=args.ip, \
        port_number=41000, adc_delay_table=ADC_DELAY_TABLE, init=1, \
        sampling_frequency=800 * 1e6, \
        reference_frequency=10e6, data_width=8, \
        group_frames=2, \
        enable_gpu_link = 0, \
        host_ip = args.host_ip) # pylint: disable=C0103
   

    print 'ADC 00', c.adc_board[0].ADC[0].get_temperature()
    print 'ADC 01', c.adc_board[0].ADC[1].get_temperature()
    print 'ADC 10', c.adc_board[1].ADC[0].get_temperature()
    print 'ADC 11', c.adc_board[1].ADC[1].get_temperature()
    #rs = [chFPGA_receiver.chFPGA_receiver(c_element.fpga.get_config(), ip_address=c_element.fpga_ip_addr, port=c_element.fpga_port_number+1, host_ip = '10.10.10.83') for c_element in c]

    r = chFPGA_receiver.chFPGA_receiver(c.get_config(), ip_address=args.ip, port=41001, host_ip = args.host_ip)
    test = test_adc_analog_histogram(c, r)
    test.execute(args.output_name)
    r.close()
    #[r.close() for r in rs]
