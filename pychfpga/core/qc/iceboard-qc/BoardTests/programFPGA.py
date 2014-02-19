from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import sys

def programFPGA(username=None,board_sn=None,board_vn=None,board_md=None):
    if (username == None) or (board_sn == None) or (board_vn == None) or (board_md == None):
        iceboardtest.starttest()
    fname = 'board' + board_sn + '.txt'
    file = open(fname, 'a')
    file.write('\n\nProgramming the FPGA Test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')

    print "Please have everything set up as that from the Programming ARM Test."
    print "Make sure you can ping the motherboard, in the same method as that of Programming ARM Test. You may need to turn the board on/off"
    print "a few times to make sure it works."
    notimportant = raw_input("Press Enter to continue:  ")
    print "Open up a different cmd window. From there, go into the ch_acq git repository."
    notimportant = raw_input("Press Enter to continue:  ")

    print 'Type in python pychfpga\\arm.py --ip 10.10.10.NUM -f "..\\chFPGA\\xilinx_projects\\CHFPGA_MGK7MB_REV2\\CHFPGA_MGK7MB_REV2.runs\\impl_Rev2\\chFPGA_MGK7MB_Rev2.bit" under this new directory'
    print 'where NUM is the number of the board (such that 10.10.10.NUM is the IP address programmed onto the board).'
    notimportant = raw_input("Press Enter to continue:  ")

    print 'It will take a bit of time to run this program. '
    print "When you're back on the command prompt, you should be able to see some texts have been outputted when programming the FPGA."
    print "Check the last line of the block of text. Does it say 'Programming successful'?"
    program = raw_input("Enter 'Y' or 'N':  ")
    if program == 'Y' or program == 'y':
        file.write('\nOutput stating programming successful: Pass')
    else:
        file.write('\nOutput stating programming successful: Fail')
        file.write('\nFPGA Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")

    print "Check to see there are blinking red lights at the bottom edge of the FPGA. Are they there?"
    lights = raw_input("Enter 'Y' or 'N':   ")
    if lights == 'Y' or lights == 'y':
        file.write('\nBlinking red lights seen on board: Pass')
    else:
        file.write('\nBlinking red lights seen on board: Fail')
        file.write('\nFPGA Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "You should also be able to see the current draw has gone up to about 1.4-1.5A. This is normal!"
    print "If there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments:  ")
    file.write('\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'):  ")
    if check == 'Y' or check == 'y':
        file.write('\n\nFPGA Programming Test Overall Status: Pass')
        file.close()
    else:
        file.write('\n\nFPGA Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md)
    else:
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")