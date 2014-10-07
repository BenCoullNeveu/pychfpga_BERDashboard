#!/usr/bin/python

"""
timestream_rms.py script 
 Script to run the 5-channel system and just print to screen the rms of the adc timestream input.
#
History:
    2012-12-04 KMB: First attempt 
"""


from pychfpga.core import chFPGA_receiver
import numpy as np
import time, sys, os, logging
import argparse

from pychfpga.icecore import hardware_map
from pychfpga.icecore import tuber
from pychfpga.icecore.icearray import IceArray, close_all_sockets
from pychfpga.icecore.fpga_bitstream import FpgaBitstream
from pychfpga.icecore.iceboard import IceBoard

from pychfpga.core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware

ADC_DELAYS_REV2_SN0001 = (
    [20,26,25,25,25,25,25,24], #CH0
    [22]*8, #CH1 
    [22,22,20,20,20,20,20,19], #CH2 
    [18]*8+[0], #CH3
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

ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 = (
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

def print_RMS(r):
    channels = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
    cont = True
    while cont:
        try:
            a = r.read_frames()
            for chan in channels:
                sys.stdout.write("ch%d %f\n" % (chan, np.log2(a[chan].std())))
            for i in xrange(2):
                sys.stdout.write("\n")
            time.sleep(1.5)
            sys.stdout.flush()
            os.system("cls" if os.name=='nt' else 'clear')
        except KeyboardInterrupt:
            print "Stopped by User"
            cont = False
        except KeyError:
            print "key error, missing data..."
            pass    

if __name__ == '__main__':


    close_all_sockets()

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('--force', action = 'store', type=int, default=0, help='Forces reprogramming of the FPGAs even if they are already programmed')
    parser.add_argument('-i', '--if_ip', action = 'store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. If not specified, the controller will attempt to identify the proper host based on the FPGA IP address.')
    parser.add_argument('--bitfile', action = 'store', type=str, default= '../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit',  help='Filename of the bitfile used to to program the FPGAs')
    parser.add_argument('--subarray', action = 'store', type=int, default=2, help='Which subarray to use')
    args = parser.parse_args()
    log_level = {'info': logging.INFO, 'debug': logging.DEBUG}[args.log_level]

    # logging.basicConfig(level=log_level, format='%(asctime)s  %(context)s %(name)-32s %(levelname)-10s : %(message)s')


    logger = logging.getLogger('')
    logger.setLevel(log_level)
    handler = logging.FileHandler('rms_tesing.log')
    #handler = logging.handlers.SysLogHandler()
    # handler = logging.StreamHandler()
    # handler.addFilter(CompletionFilter)
    logger.addHandler(handler)
    ADC_DELAY_TABLE = ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 # ADC_DELAYS_REV2_SN0001 # select the table corresponding to the FMC serial number
    IceArray.close_all_sessions() # close all previously opened sessions
    ca = IceArray(interface_ip_addr=args.if_ip)
    ca.load_iceboards('iceboard_list.txt')
    ca.discover() # automatically update the hardware map database with discovered resources
    bitfile_filename = args.bitfile
    fpga_bitstream = ca.get_fpga_bitstream(args.bitfile, ChimeFpgaFirmware) # Get a new bitstream from the database (or create a new database entry if it does not exist yet)
    c = ca.get_iceboards(subarray=args.subarray).index_by(IceBoard.serial_number) # get one or more IceBoards from specified subarray
    c.set_fpga_firmware(fpga_bitstream, force=args.force)
    c.open( \
        adc_delay_table=ADC_DELAY_TABLE, \
        init=1, \
        sampling_frequency=800* 1e6, \
        data_width=4, \
        group_frames=4, \
        enable_gpu_link = 1)
    c.fpga.set_corr_reset(1)
    time.sleep(0.1)
    c.fpga.set_corr_reset(0)
    for i, c_element in enumerate(c):
        chFPGA_config = c_element.fpga.get_config()
        r = chFPGA_receiver.chFPGA_receiver(chFPGA_config, \
                      ip_address=c_element.fpga_ip_addr, \
                      port=c_element.fpga_port_number+1, \
                      host_ip = args.if_ip)
        c_element.set_data_source('adc_element')
        c_element.set_adc_mode('data')
        c_element.set_FFT_bypass(True)
        c_element.set_scaler_bypass(False)
        c_element.set_gain((1,27))
        c_element.start_data_capture(burst_period_in_seconds=1.5, number_of_bursts=0)
        time.sleep(2)
        print_RMS(r)
        r.close()




    
