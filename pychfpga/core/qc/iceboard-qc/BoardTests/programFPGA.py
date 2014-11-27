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

    # Import parameters from config
    import yaml
    config = yaml.load(open('config.yaml'))
    if username == None:
        username = config['user']
    host_ip = config['host_ip']
    ch_acq_path = config['ch_acq_path']

    print "Please have everything set up as that from the Programming ARM Test."
    print "You need to have already installed a heatsink on the FPGA, and running a fan over it is recommended."
    print "Make sure you can ping the motherboard, in the same method as that of Programming ARM Test. You may need to turn the board on/off"
    print "a few times to make sure it works."
    
    # Get correct ch_acq path
    if ch_acq_path is None:
        ch_acq_path = '../../ch_acq/'
        print '\nThis test requires modules from ch_acq.\nUsing path ' + ch_acq_path + '.'
        confirm = raw_input('Check that this is correct. Would you like to modify it? (y/n)\t')
        if confirm == 'y' or confirm == 'Y':
            ch_acq_path = raw_input("Enter path (ending with a '/'):\t")
    print "\nIf it is not already the case, set ch_acq to the 'master' git branch."

    # Get host_ip
    if host_ip is None:
        host_ip = raw_input("\nEnter the IP of the network adpater you will use to communicate with FPGA (must be gigabit)\n")
    
    print "\nWe will now program the FPGA of board " + board_sn + "."
    print "You need to have successfully run the 'Program ARM' in its entirety, or be sure that the ARM addresses were entered in database."
    raw_input("Press Enter to proceed with programming (this may take some time):\t")
    fpgaFun.programFpga(board_sn,ch_acq_path=ch_acq_path,host_ip=host_ip,force=True)

    # Command to program FPGA using arm.py in old ch_acq, for reference
    #print 'Type in python pychfpga\\arm.py --ip 10.10.10.NUM -f "..\\chFPGA\\xilinx_projects\\CHFPGA_MGK7MB_REV2\\CHFPGA_MGK7MB_REV2.runs\\impl_Rev2\\chFPGA_MGK7MB_Rev2.bit" under this new directory'
    #print 'where NUM is the number of the board (such that 10.10.10.NUM is the IP address programmed onto the board).'
    #notimportant = raw_input("Press Enter to continue:  ")

    print "\nCheck the last line of the block of text. Does it say 'Done configuring FPGA'?"
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

    # Get FPGA serial and append to iceboard_list.txt
    iceboard_list = fpgaFun.read_list()
    if len(iceboard_list) == 0:
        print "\nCould not find 'iceboard_list.txt' or file empty."
        file.write("\nCould not find 'iceboard_list.txt' or file empty.")
        file.write('\n\nFPGA Programming Test Overall Status: Fail')
        file.close()
        fpgaProgFail(username,board_sn,board_vn,board_md,testStatus)

    serial = fpgaFun.discover_fpgas(host_ip)
    if len(serial) == 0:
        print "No FPGAs found on network. Check that you are properly connected via a Gigabit adapter and that your board is programmed."
        file.write("\nNo FPGAs found on network. Could not fetch FPGA serial.")
        file.write('\n\nFPGA Programming Test Overall Status: Fail')
        file.close()
        fpgaProgFail(username,board_sn,board_vn,board_md,testStatus)
    # Identify which serial is new
    elif len(serial) == 1:
        fpga_sn = str(hex(int(serial[0])))
    else:
        doesnt_exist = range(0,len(serial))
        already_in_list = False
        iceboard_list = fpgaFun.read_list()
        for line in iceboard_list[1:len(iceboard_list)]:
            for i in doesnt_exist:
                if int(line[4]) == int(serial[i]): # WHY DOES PYTHON THINK line[4] IS A HEX??
                    if int(line[0]) == int(board_sn):
                        already_in_list = True
                        break
                    doesnt_exist.remove(i)
            if already_in_list:
                break
        if already_in_list:
            fpga_sn = None # This will just leave the previous value in the list
        elif len(doesnt_exist) == 0:
            print "No new FPGAs (not in list) found on network. Check that you are properly connected via a Gigabit adapter and that your board is programmed."
            file.write("\nNo new FPGAs (not in list found on network. Could not fetch FPGA serial.")
            file.write('\n\nFPGA Programming Test Overall Status: Fail')
            file.close()
            fpgaProgFail(username,board_sn,board_vn,board_md,testStatus)
        elif len(doesnt_exist) > 1:
            print "More than one FPGA not currently in list found on network. Make sure you have your iceboard_list is up to date."
            file.write("\nCould not identify new FPGA on network. Could not fetch FPGA serial.")
            file.write('\n\nFPGA Programming Test Overall Status: Fail')
            file.close()
            fpgaProgFail(username,board_sn,board_vn,board_md,testStatus)
        else:
            fpga_sn = str(hex(serial[doesnt_exist[0]]))

    # Assign IP to FPGA
    current_ip = None
    # First, check if already assigned
    for line in iceboard_list[1:len(iceboard_list)]:
        if int(line[0]) == int(board_sn):
            current_ip = line[3]
            break
    if current_ip is None or len(current_ip.strip("'")) < 7:
        fpga_ip = "'10.10.3." + str(board_sn) + "'"
    else:
        fpga_ip = current_ip
    print "\nAssigning IP address " + fpga_ip + " to FPGA."
    print "Adding serial number " + fpga_sn + " to database."
    fpgaFun.edit_list(board_sn,fpga_sn=fpga_sn,fpga_ip=fpga_ip,locked='0')

    # Reload modified list
    fpgaFun.reload_list(host_ip=host_ip)

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