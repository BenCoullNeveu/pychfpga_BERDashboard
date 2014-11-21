from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import sys
import traceback
import programFPGA
import updateStatus
from date_format import date_format
from statusReport import EMPTY_TEST_STATUS
from testFail import fpgaTestFail
import fpgaFun

def FPGAtest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
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
    file.write('\n\nFPGA Test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')

    print "\nFor this test, you need an Ethernet cable and an adapter for the board connector."
    print "You must have already installed a heatsink on the FPGA, and you should run a fan over it for this test."
    # print "Please consult http://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual for details regarding the connector. Or ask Kevin."
    print "Let's get started. Have you ran the 'Program FPGA' test, or are the FPGA addresses already in database?"
    program = raw_input("Enter 'Y' or 'N': 	")
    if program != 'Y' and program != 'y':
        print "\nWe must first run 'Program the FPGA'.\n"
        programFPGA.programFPGA(username,board_sn,board_vn,board_md,testStatus)
    
    print "\nFirst, connect the board's ethernet port to the network and also connect the FPGA to the network using the SFTP to ethernet adapter."
    
    # Get correct ch_acq path
    ch_acq_path = '../../ch_acq/'
    print '\nThis test requires modules from ch_acq.\nUsing path ' + ch_acq_path + '.'
    confirm = raw_input('Check that this is correct. Would you like to modify it? (y/n)\t')
    if confirm == 'y' or confirm == 'Y':
        ch_acq_path = raw_input("Enter path (ending with a '/'):\t")
    print "If it is not already the case, set ch_acq to the 'master' git branch."

    # Program FPGA
    print "\nProgramming FPGA:"
    raw_input("Press Enter to proceed (this may take some time):\t")
    fpgaFun.programFpga(board_sn,ch_acq_path=ch_acq_path)

    # Run top_test
    print "\nWe will now attempt to run top_test."
    raw_input("Press Enter to proceed with top_test (this may take some time):\t")
    success = False
    [c,r] = [None,None]
    try:
        [c,r] = fpgaFun.top_test(ch_acq_path, host_ip)
        success = True
    except Exception as e:
        traceback.print_exc(e)
        print "\nTop_test did not run successfully."
        
    print "\nTop test should have been able to load without any problems or errors."
    print "You should also see the current draw to be above 2A at this point."
    if success:
        file.write('\nRunning top_test on board: Pass')
    else:
        file.write('\nRunning top_test on board: Fail')
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        
    # Capture standard output
    from cStringIO import StringIO
    import sys
    import logging
    class Capturing(list):
        '''
        Captures standard output and error. Taken from http://stackoverflow.com/a/16571630 .
        '''
        def __enter__(self):
            self._stdout = sys.stdout
            self._stderr = sys.stderr
            sys.stdout = sys.stderr = self._stringio = StringIO()
            self._handler = logging.StreamHandler(self._stringio)
            logging.getLogger().addHandler(self._handler)
            return self
        def __exit__(self, *args):
            self.extend(self._stringio.getvalue().splitlines())
            sys.stdout = self._stdout
            sys.stderr = self._stderr
            logging.getLogger().removeHandler(self._handler)
    
    print "Let's try probing some temperatures on the board."
    try:
        c.SYSMON.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)

    print "\nYou should be able to read the core temperature of the FPGA. Now, move the fan away for the board and probe again. (And move the fan back.) "
    probe = raw_input("Probe temperature? (y/n)\t")
    while probe == 'y' or probe == 'Y':
        try:
            with Capturing() as output:
                c.SYSMON.status()
        except Exception as e:
            file.write('\nRunning top_test on board: Fail')
            file.write("\n" + repr(e))
            file.write('\nFPGA Test Overall Status: Fail')
            file.close()
            fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        probe = raw_input("Probe temperature? (y/n)\t")
    
    print "\nDo you see a temperature difference that indicates the temperature is being probed correctly?"
    tempprobe = raw_input("Enter 'Y' or 'N': 		")
    if tempprobe == 'Y' or tempprobe == 'y':
        file.write('\nProbing FPGA temperature on board: Pass')
    else:
        file.write('\nProbing FPGA temperature on board: Fail')
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        
    # print "For the part below to work, please consult the website https://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual before continuing."
    
    print "\nWe will now call a few of the FPGA functions and record them."
    
    print "\nc.ANT.status():"
    file.write('\n\nANT status output: ')
    try:
        with Capturing() as output:
            c.ANT.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
        print line
    
    print "\nc.CORR.status():"
    file.write('\n\nCORR status output: ')
    try:
        with Capturing() as output:
            c.CORR.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
        print line
        
    print "\nc.FreqCtr.status():"
    file.write('\n\nFreqCtr status output: ')
    try:
        with Capturing() as output:
           c.FreqCtr.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
        print line
    
    print "\nc.GPIO.status():"
    file.write('\n\nGPIO status output: ')
    try:
        with Capturing() as output:
            c.GPIO.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
    
    print "\nc.GPU.status():"
    file.write('\n\nGPU status output: ')
    try:
        with Capturing() as output:
            c.GPU.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
        print line

    print "\nc.REFCLK.status():"
    file.write('\n\nREFCLK status output: ')
    try:
        with Capturing() as output:
            c.REFCLK.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
        print line
    
    print "\nc.SPI.status():"
    file.write('\n\nSPI status output: ')
    try:
        with Capturing() as output:
            c.SPI.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
        print line
    
    print "\nc.SYSMON.status():"
    file.write('\n\nSYSMON status output: ')
    try:
        with Capturing() as output:
            c.SYSMON.status()
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    for line in output:
        file.write('\n' + line)
    
    print "\nc.GPIO.FPGA_SERIAL_NUMBER:"
    file.write('\n\nFPGA serial number: ')
    try:
        fpga_serial = c.GPIO.FPGA_SERIAL_NUMBER
    except Exception as e:
        file.write('\nRunning top_test on board: Fail')
        file.write("\n" + repr(e))
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    file.write('\n' + str(fpga_serial))
    print fpga_serial
    # Save FPGA serial to separate file
    if not os.path.isfile('fpga_serials.txt'):
        serials_file = open('fpga_serials.txt', 'w')
    else:
        serials_file = open('fpga_serials.txt', 'a')
    serials_file.write('\nBoard ' + board_sn + ': ' + hex(int(fpga_serial)))
    serials_file.close()
    
    print "\nIf there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments:  ")
    file.write('\n\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'):  ")
    if check == 'Y' or check == 'y':
        file.write('\n\nFPGA Test Overall Status: Pass')
        file.close()
        testStatus[9] = True
    else:
        file.write('\n\nFPGA Test Overall Status: Fail')
        print "Please describe why below."
        failure = raw_input("Enter your comments:       ")
        file.write('\nComments:         ' + failure)
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update( testStatus )
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")
