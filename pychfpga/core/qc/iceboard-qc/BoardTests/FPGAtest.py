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

    print "For this test, we NEED to have already programmed the FPGA. You also need an Ethernet cable and an adapter for the board connector."
    print "Please consult http://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual for details regarding the connector. Or ask Kevin."
    print "Let's get started. Is the board turned on and the FPGA has been programmed?"
    program = raw_input("Enter 'Y' or 'N': 	")
    if program != 'Y' and program != 'y':
        print "\nWe must first program the FPGA.\n"
        programFPGA.programFPGA(username,board_sn,board_vn,board_md,testStatus)
    
    print "We'll need to disconnect this computer from the lab network and connect the board directly to the network card of the PC."
    print "First, disconnect the Ethernet cable going from the computer to the router."
    notimportant = raw_input("Press Enter to continue: 	")

    print "You should see three big silver long rectangular (QSFP) connectors on the bottom edge of the board. You should connect the adapter"
    print "for the connector to the connector to the right of these (the one besides the two scary-looking spiky connectors)."
    notimportant = raw_input("Press Enter to continue: 	")

    print "In the Network and Sharing Centre part of the PC, click on 'Change adapter settings' on the left pane."
    print "In Local Area Connection 2 connection, you should NOT see an 'x' on the icon for the connection."
    notimportant = raw_input("Press Enter to continue: 	")
    print "Right click on this icon and select Properties. In the pop-up window, highlight Internet Protocol Version 4"
    print "and click on the Properties button below. You should see the option set to 'use the following IP address'"
    print "Write down the IP address that appears below that line."
    host_ip = raw_input("Enter IP address: 		")
    
    # Get correct ch_acq path
    ch_acq_path = '../../ch_acq/'
    print '\nThis test requires modules from ch_acq.\nUsing path ' + ch_acq_path + '.'
    confirm = raw_input('Check that this is correct. Would you like to modify it? (y/n)\t')
    if confirm == 'y' or confirm == 'Y':
        ch_acq_path = raw_input("Enter path (ending with a '/'):\t")
    print "If it is not already the case, set ch_acq to the 'master' git branch."
    
    # Run top_test
    print "\nWe will now attempt to run top_test."
    # ip = raw_input("Enter IP address of board (i.e. 10.10.10.NUM):\t")
    raw_input("Press Enter to proceed with top_test (this may take some time):\t")
    success = False
    [c,r] = [None,None]
    while not success:
        try:
            [c,r] = fpgaFun.top_test(ch_acq_path, host_ip)
            success = True
        except Exception as e:
            traceback.print_exc(e)
            confirm = raw_input("Top_test did not run successfully. Do you want to try again")
            if confirm != 'Y' and confirm != 'y':
                file.write('\nRunning top_test on board: Fail')
                file.write("\n" + repr(e))
                file.write('\nFPGA Test Overall Status: Fail')
                file.close()
                fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        
    print "\nTop test should have been able to load without any problems or errors. You should also see the current draw to be above 2A at this point."
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
    class Capturing(list):
        '''
        Captures standard output. Taken from http://stackoverflow.com/a/16571630 .
        '''
        def __enter__(self):
            self._stdout = sys.stdout
            sys.stdout = self._stringio = StringIO()
            return self
        def __exit__(self, *args):
            self.extend(self._stringio.getvalue().splitlines())
            sys.stdout = self._stdout
    
    print "Let's try probing some temperatures on the board."
    with Capturing() as output:
        try:
            c.SYSMON.status()
        except Exception as e:
            file.write('\nRunning top_test on board: Fail')
            file.write("\n" + repr(e))
            file.write('\nFPGA Test Overall Status: Fail')
            file.close()
            fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        print "SYSMON.status()"
        for line in output:
            print line
    print "\nYou should be able to read the core temperature of the FPGA. Now, move the fan away for the board and probe again. (And move the fan back.) "
    probe = raw_input("Probe temperature? (y/n)\t")
    while probe == 'y' or probe == 'Y':
        with Capturing() as output:
            try:
                c.SYSMON.status()
            except Exception as e:
                file.write('\nRunning top_test on board: Fail')
                file.write("\n" + repr(e))
                file.write('\nFPGA Test Overall Status: Fail')
                file.close()
                fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
            print "SYSMON.status()"
            for line in output:
                print line
        probe = raw_input("Probe temperature? (y/n)\t")
    
    print "\nDo you see a temperature difference that indicates the temperating is being probed correctly?"
    tempprobe = raw_input("Enter 'Y' or 'N': 		")
    if tempprobe == 'Y' or tempprobe == 'y':
        file.write('\nProbing FPGA temperature on board: Pass')
    else:
        file.write('\nProbing FPGA temperature on board: Fail')
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        
    print "\nNow let's write all these status!"
    print "!!!!!!!!!!!!!!!! WARNING !!!!!!!!!!!!!!!!!!!!!!!"
    print "------------------------------------------------"
    tm.sleep(1)
    print "For the part below to work, please consult the website https://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual before continuing."
    
    print "We will now call a few of the FPGA functions and record them."
    
    print "\nc.ANT.status():"
    file.write('\n\nANT status output: ')
    with Capturing() as output:
        try:
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
    with Capturing() as output:
        try:
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
    with Capturing() as output:
        try:
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
    with Capturing() as output:
        try:
            c.GPIO.status()
        except Exception as e:
            file.write('\nRunning top_test on board: Fail')
            file.write("\n" + repr(e))
            file.write('\nFPGA Test Overall Status: Fail')
            file.close()
            fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        for line in output:
            file.write('\n' + line)
            print line
    
    print "\nc.GPU.status():"
    file.write('\n\nGPU status output: ')
    with Capturing() as output:
        try:
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
    with Capturing() as output:
        try:
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
    with Capturing() as output:
        try:
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
    with Capturing() as output:
        try:
            c.SYSMON.status()
        except Exception as e:
            file.write('\nRunning top_test on board: Fail')
            file.write("\n" + repr(e))
            file.write('\nFPGA Test Overall Status: Fail')
            file.close()
            fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        for line in output:
            file.write('\n' + line)
            print line
    
    print "\nc.fpga.GPIO.FPGA_SERIAL_NUMBER:"
    file.write('\n\nFPGA serial number: ')
    with Capturing() as output:
        try:
            c.fpga.GPIO.FPGA_SERIAL_NUMBER
        except Exception as e:
            file.write('\nRunning top_test on board: Fail')
            file.write("\n" + repr(e))
            file.write('\nFPGA Test Overall Status: Fail')
            file.close()
            fpgaTestFail(username,board_sn,board_vn,board_md,testStatus)
        file.write(output)
        # Save FPGA serial to separate file
        if not os.path.isfile('fpga_serials.txt'):
            serials_file = open('fpga_serials.txt', 'w')
        else:
            serials_file = open('fpga_serials.txt', 'a')
        serials_file.write('\nBoard ' + board_sn + ': ' + hex(int(output)))
        serials_file.close()
    
    print "If there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
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
