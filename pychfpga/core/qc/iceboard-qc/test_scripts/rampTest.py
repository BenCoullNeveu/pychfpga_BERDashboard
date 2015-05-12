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
import fpgaFun
import git

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
    file.write('\n\nRamp test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n')
    adc_a = raw_input("Enter the 4-digit serial number of the ADC mezzanine plugged in slot A of the ICEBOARD: " )
    adc_b = raw_input("Enter the 4-digit serial number of the ADC mezzanine plugged in slot B of the ICEBOARD: " )
    file.write('Using ADC #' + adc_a + ' on FMC slot A and ADC #' + adc_b + ' on FMC slot B.\n')
    ice_qc_repo = git.Repo()
    file.write("On branch '" + str(ice_qc_repo.active_branch) + "' with commit " + str(ice_qc_repo.commit('HEAD')) + " of iceboard-qc.\n")
    ch_acq_repo = git.Repo("../../ch_acq/")
    file.write("On branch '" + str(ch_acq_repo.active_branch) + "' with commit " + str(ch_acq_repo.commit('HEAD')) + " of ch_acq.\n\n")
    file.flush()
    
    # Import parameters from config
    import yaml
    config = yaml.load(open('config.yaml'))
    if username == None:
        username = config['user']
    host_ip = config['host_ip']
    ch_acq_path = config['ch_acq_path']
    
    # Intro
    print "\nFor this test, you will need to have both CHIME ADC mezzanines mounted on the board."
    print "As for the FPGA test, you need an ethernet cable going from the ARM port to the network"
    print "and another from the SFP-Ethernet apdapter to the network."
    print "Make sure the computer you are using is connected to the network via a gigabit port with Jumbo Frames enabled."
    
    print "\nYou should connect a fan to the FPGA heatsink, and ensure there is airflow over the mezzanine ADCs."

    # Make directory
    directory = 'ramp_tests/QC/sn' + board_sn
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # Begin Ramp test
    raw_input("\nPress Enter to begin ramp test:\t")
    [ delay_table, stuck_bits ] = fpgaFun.rampTest(board_sn, directory + '/ramp_testing_trial_sn' + board_sn, ch_acq_path=ch_acq_path, host_ip=host_ip)
    
    # Record results to file
    test_pass = False
    confirm = raw_input("\nHas the ramp test successfully completed? (y/n)\t")
    if confirm == 'Y' or confirm == 'y':
        file.write("Ramp test was run successfully. (See BoardTests/ramp_tests/ for details.\n")
        print("\nPlease take a look at the output of the test: error ratios and histograms (found printed to console and in BoardTests/ramp_tests respectively)")
        confirm = raw_input("Are there any non-zero error ratios, or non-flat histograms? (y/n)\t")
        if confirm == 'Y' or confirm == 'y':
            bit_errors = raw_input("\nIf there are any non-zero bit error ratios, enter the affected channels and bits (e.g. ch 10 bit 4, ch 1 bit 7, ...):\n")
            file.write("Bit errors found on: " + bit_errors + "\n")
            hist_errors = raw_input("If any of the histograms are not perfectly flat, enter the affected channels:\n")
            file.write("Channels with non-flat histogram: " + hist_errors + "\n")
            hist_errors = raw_input("If any of the histograms show very large distorsion, beyond relatively small peaks away from flat, enter the affected channels:\n")
            file.write("Channels with severely distorted histogram: " + hist_errors + "\n")
            print("\nSmall peaks around a flat histogram or small (< 0.1) error ratios may be attributed to timing issues with the ADC mezzanines, but a very distorted histogram may point to more serious issues.\n If this is found to be the case, the connector to the affected mezzanine or the traces, vias, and solder joints connecting it to the FPGA are possible culprits.")
        else:
            file.write("Ramp found no errors." + "\n")
            test_pass = True
    else:
        error = raw_input("Can you describe the error?\t")
        file.write("Ramp test failed to run: " + error + "\n")
    file.write('\n\nComputed ADC delay table:\n')
    file.write('\n::\n')
    for line in delay_table:
        file.write('\n   ' +  repr(line) + ',\\')
    file.write('\n\nStuck bit flags (1 means no stuck bit):\n')
    file.write('\n::\n')
    for line in stuck_bits:
        file.write('\n   ' +  repr(line) + ',\\')
    
    # End test
    print "\nIf there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments:  ")
    file.write('\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'):  ")
    if check == 'Y' or check == 'y':
        file.write('\n\nRamp Test Overall Status: Pass')
        file.close()
        testStatus[11] = test_pass
    else:
        file.write('\n\nRamp Test Overall Status: Fail')
        print "Please describe why below."
        failure = raw_input("Enter your comments:       ")
        file.write('\nComments:         ' + failure)
        file.close()
        testStatus[11] = False
        # Must modify this behaviour
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update( testStatus )
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.") 


