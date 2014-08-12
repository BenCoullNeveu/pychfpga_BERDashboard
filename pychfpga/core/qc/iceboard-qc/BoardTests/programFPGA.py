from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import sys
import updateStatus
from date_format import date_format
from statusReport import EMPTY_TEST_STATUS
from testFail import fpgaProgFail
import fpgaFun

def programFPGA(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
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
    file = open(fname, 'a')
    file.write('\n\nProgramming the FPGA Test\n')
    file.write('------\n')
    date_str = iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')

    print "Please have everything set up as that from the Programming ARM Test."
    print "Make sure you can ping the motherboard, in the same method as that of Programming ARM Test. You may need to turn the board on/off"
    print "a few times to make sure it works."
    
    # Get correct ch_acq path
    ch_acq_path = '../../ch_acq/'
    print '\nThis test requires modules from ch_acq.\nUsing path ' + ch_acq_path + '.'
    confirm = raw_input('Check that this is correct. Would you like to modify it? (y/n)\t')
    if confirm == 'y' or confirm == 'Y':
        ch_acq_path = raw_input("Enter path (ending with a '/'):\t")
    print "If it is not already the case, set ch_acq to the 'master' git branch."
    
    # We assume there is a proper bitfile to program the FPGA in
    # ../../chFPGA/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit
    
    print "\nWe will now program the FPGA."
    ip = raw_input("Enter IP address of board (i.e. 10.10.10.NUM):\t")
    raw_input("Press Enter to proceed with programming (this may take some time):\t")
    fpgaFun.programFpga(ch_acq_path, ip) # Can include 3rd argument for custom bitfile path.

    #print 'Type in python pychfpga\\arm.py --ip 10.10.10.NUM -f "..\\chFPGA\\xilinx_projects\\CHFPGA_MGK7MB_REV2\\CHFPGA_MGK7MB_REV2.runs\\impl_Rev2\\chFPGA_MGK7MB_Rev2.bit" under this new directory'
    #print 'where NUM is the number of the board (such that 10.10.10.NUM is the IP address programmed onto the board).'
    #notimportant = raw_input("Press Enter to continue:  ")

    print "\nCheck the last line of the block of text. Does it say 'Programming successful'?"
    program = raw_input("Enter 'Y' or 'N':  ")
    if program == 'Y' or program == 'y':
        file.write('Output stating programming successful: Pass')
    else:
        file.write('Output stating programming successful: Fail')
        file.write('\nFPGA Programming Test Overall Status: Fail')
        file.close()
        fpgaProgFail(username,board_sn,board_vn,board_md,testStatus)

    print "\nCheck to see there are blinking red lights at the bottom edge of the FPGA. Are they there?"
    lights = raw_input("Enter 'Y' or 'N':   ")
    if lights == 'Y' or lights == 'y':
        file.write('\nBlinking red lights seen on board: Pass')
    else:
        file.write('\nBlinking red lights seen on board: Fail')
        file.write('\nFPGA Programming Test Overall Status: Fail')
        file.close()
        fpgaProgFail(username,board_sn,board_vn,board_md,testStatus)
        
    print "\nYou should also be able to see the current draw has gone up. This is normal!"
    print "\nIf there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments:  ")
    file.write('\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'):  ")
    if check == 'Y' or check == 'y':
        file.write('\n\nFPGA Programming Test Overall Status: Pass')
        testStatus[8] = True
        file.close()
    else:
        file.write('\n\nFPGA Programming Test Overall Status: Fail')
        print "Please describe why below."
        failure = raw_input("Enter your comments:       ")
        file.write('\nComments:         ' + failure)
        file.close()
        fpgaProgFail(username,board_sn,board_vn,board_md,testStatus)
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")