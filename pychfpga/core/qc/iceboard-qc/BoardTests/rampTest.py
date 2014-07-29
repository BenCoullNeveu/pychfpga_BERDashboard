#!/usr/bin/env python

'''
ramp test script for ICEboard QC (uses test class from ch_acq/pychfpga/common/tests/ramp_test)
'''

from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import updateStatus
from statusReport import EMPTY_TEST_STATUS
import csv
import argparse
import sys

def rampTest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
    testStatus[0] = username
    testStatus[1] = board_sn
    testStatus[2] = board_vn
    fname = 'board' + board_sn + '.txt'
    if os.path.isfile('board' + board_sn + '.txt') == False:
        file = open(fname, 'w')
        file.write('=========================\n')
        file.write('ICE board ' + board_sn + 'QC testing\n') 
        file.write('=========================\n')
        file.write('Quality control testing results for ICE board serial number ' + board_sn + '\n')
        file.write('Revision number: ' + board_vn + '\n')
        file.write('Board model: ' + board_md + '\n')
        date_str=date_format(tm.localtime())
        file.write('File created on : ' + date_str + '\n')
        file.write('\n')
        file.close()
        print "File 'board" + board_sn + ".txt' is created in directory."
    fname = 'board' + board_sn + '.txt'
    file = open(fname, 'a')
    file.write('\nRamp test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')
    
    # Get correct ch_acq path
    ch_acq_path = '../../chime/ch_acq/'
    confirm = raw_input('This test requires modules from ch_acq (make sure you are using iceboard_dev branch).\nUsing path ' + ch_acq_path + '. Would you like to modify it? (y/n)\t')
    if confirm == 'y' or confirm == 'Y':
        ch_acq_path = raw_input('Enter path:\t')
    # Import necessary pychpga modules
    sys.path.append(ch_acq_path)
    from pychfpga.common.tests.ramp_test import test_adc_ramp_histogram
    from pychfpga import save_raw_frames
    # from pychfpga.icecore import hardware_map
    # from pychfpga.icecore import tuber
    from pychfpga.icecore.icearray import IceArray, close_all_sockets
    # from pychfpga.icecore.fpga_bitstream import FpgaBitstream
    from pychfpga.icecore.iceboard import IceBoard
    from pychfpga.core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware
    from pychfpga.core import chFPGA_receiver
    
    # Get bitfile path
    bitfile_path = '../../chime/chFPGA/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit'
    confirm = raw_input('\nThis test requires a bitfile to program the FPGA.\nUsing path ' + bitfile_path + '. Would you like to modify it? (y/n)\t')
    if confirm == 'y' or confirm == 'Y':
        bitfile_path = raw_input('Enter path:\t')
    
    # Get IP address
    if_ip = '10.10.10.33'
    confirm = raw_input('\nThis test requires the IP adress of this computer to communicate with the FPGA.\nUsing ' + if_ip + '. Is this correct? (y/n)\t')
    if confirm == 'n' or confirm == 'N':
        if_ip == raw_input('Enter your IP:\t')
        
    # Force argument for programming FPGA
    force = 1
    
    # Timing for ADCs
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
    
    # Begin Ramp test
    close_all_sockets()
    IceArray.close_all_sessions() # close all previously opened sessions
    
    ca = IceArray(uri='sqlite:///test.db', interface_ip_addr=if_ip) # Create IceArray
    # Need to add way for user to add iceboard to list
    ca.load_iceboards(ch_acq_path + 'pychfpga/iceboard_list.txt')
    ca.discover() # automatically update the hardware map database with discovered resources
    
    fpga_bitstream = ca.get_fpga_bitstream(bitfile_path, ChimeFpgaFirmware) # Get a new bitstream from the database (or create a new database entry if it does not exist yet)
    c = ca.get_iceboards(serial_number=board_sn) # get IceBoard
    c.set_fpga_firmware(fpga_bitstream, force=force)
    c.open( \
        adc_delay_table=ADC_DELAY_TABLE, \
        init=1, \
        sampling_frequency=800 * 1e6, \
        reference_frequency=10e6, data_width=8, \
        group_frames=1, \
        enable_gpu_link = 0)
    print c.fpga.get_temperatures()
    #rs = [chFPGA_receiver.chFPGA_receiver(c_element.fpga.get_config(), ip_address=c_element.fpga_ip_addr, port=c_element.fpga_port_number+1, host_ip = '10.10.10.83') for c_element in c]
    for i, c_element in enumerate(c):
        r = chFPGA_receiver.chFPGA_receiver(c_element.fpga.get_config(), ip_address=c_element.fpga_ip_addr, port=c_element.fpga_port_number+1, host_ip = if_ip)
        test = test_adc_ramp_histogram(c_element.fpga, r)
        directory = 'ramp_tests/QC/sn' + board_sn
        if not os.path.exists(directory):
            os.makedirs(directory)
        test.execute(directory + '/ramp_testing_trial_sn' + board_sn + '_' + str(i))
        r.close()
    #[r.close() for r in rs]
    
    # Record results to file
    confirm = raw_input("\nHas the ramp test successfully completed? (y/n)\t")
    if confirm == 'Y' or confirm == 'y':
        file.write("Ramp test was run successfully.")
    else:
        error = raw_input("Can you describe the error?")
        file.write("Ramp test failed to run: " + error)
    print("\nPlease take a look at the output of the test: error ratios and histograms (found in console and BoardTests/ramp_tests respectively)")
    confirm = raw_input("Are there any non-zero error ratios, or non-flat histograms? (y/n)\t")
    if confirm == 'Y' or confirm == 'y':
        test_pass = False
        bit_errors = raw_input("\nIf there are any non-zero bit error ratios, enter the affected channels and bits (e.g. ch 10 bit 4, ch 1 bit 7, ...):\n")
        file.write("Bit errors found on: " + bit_errors)
        hist_errors = raw_input("If any of the histograms are not perfectly flat, enter the affected channels:\n")
        file.write("Channels with non-flat histogram: " + hist_errors)
        hist_errors = raw_input("If any of the histograms show very large distorsion, beyond relatively small peaks away from flat, enter the affected channels:\n")
        file.write("Channels with severely distorted histogram: " + hist_errors)
        print("\nSmall peaks around a flat histogram or small (< 0.1) error ratios may be attributed to timing issues with the ADC mezzanines, but a very distorted histogram may point to more serious issues.\n If this is found to be the case, the connector to the affected mezzanine or the traces, vias, and solder joints connecting it to the FPGA are possible culprits.")
    else:
        file.write("Ramp found no errors.")
        test_pass = True
    
    # End test
    print "If there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments:  ")
    file.write('\n\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'):  ")
    if check == 'Y' or check == 'y':
        file.write('\n\nRamp Test Overall Status: Pass')
        file.close()
        testStatus[10] = (True and test_pass)
    else:
        file.write('\n\nFPGA Test Overall Status: Fail')
        print "Please describe why below."
        failure = raw_input("Enter your comments:       ")
        file.write('\nComments:         ' + failure)
        file.close()
        testStatus[10] = False
        # Must modify this behaviour
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update( testStatus )
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.") 


