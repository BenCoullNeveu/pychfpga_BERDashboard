from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import sys
import programFPGA
import updateStatus
def FPGAtest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = [ '', '', '', None, None, None, None, None, None, None, None, '', '' ]):
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
    file.write('\n\nFPGA Test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')

    print "For this test, we NEED to have already programmed the FPGA. You also need the cable and an adapter for the board connector."
    print "Please consult http://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual for details regarding the connector. Or ask Kevin."
    print "Let's get started. Is the board turned on and the FPGA has been programmed?"
    program = raw_input("Enter 'Y' or 'N': 	")
    if program != 'Y' and program != 'y':
        programFPGA.programFPGA(username,board_sn,board_vn,board_md)
    
    print "We'll need to disconnect this computer from the lab network and connect the board directly to the network card of the PC."
    print "First, disconnect the Ethernet cable going from the computer to the router."
    notimportant = raw_input("Press Enter to continue: 	")

    print "You should see three big silver long rectangular connectors on the bottom edge of the board. You should connect the adapter"
    print "for the connector to the right-most connector (the one besides the two scary-looking spiky connectors)."
    notimportant = raw_input("Press Enter to continue: 	")

    print "In the Network and Sharing Centre part of the PC, click on 'Change adapter settings' on the left pane."
    print "In Local Area Connection 2 connection, you should NOT see an 'x' on the icon for the connection."
    notimportant = raw_input("Press Enter to continue: 	")
    print "Right click on this icon and select Properties. In the pop-up window, highlight Internet Protocol Version 4"
    print "and click on the Properties button below. You should see the option set to 'use the following IP address'"
    print "Write down the IP address that appears below that line."
    hostIP = raw_input("Enter IP address: 		")
    print "Open up a separate cmd window and go into the ch_acq git directory. Open up ipython via 'ipython --pylab' command."
    notimportant = raw_input("Press Enter to continue: 	")
    print "In the ipython command line, type in 'run -i pychfpga/top_test --init 1 -f 800 -l debug -w 4 -g 2 --enable_gpu_link 1  --host_ip " + hostIP + "'"
    print "where NUM is the last number of the IP assigned to the intel card by the computer."
    tm.sleep(3)
    print "Top test should have been able to load without any problems or errors. You should also see the current draw to be above 2A at this point."
    print "Was top_test able to run successfully?"
    top_test = raw_input("Enter 'Y' or 'N': 	")
    if top_test == 'Y' or top_test == 'y':
        file.write('\nRunning top_test on board: Pass')
    else:
        file.write('\nRunning top_test on board: Fail')
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Try probing some temperatures on the board. In the ipython command prompt, type in 'c.SYSMON.status()' You should be able to read the "
    print "core temperature of the FPGA. Now, move the fan away for the board and type the same command. (And move the fan back.) "
    print "Do you see a temperature difference that indicates the temperating is being probed correctly?"
    tempprobe = raw_input("Enter 'Y' or 'N': 		")
    if tempprobe == 'Y' or tempprobe == 'y':
        file.write('\nProbing FPGA temperature on board: Pass')
    else:
        file.write('\nProbing FPGA temperature on board: Fail')
        file.write('\nFPGA Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Now let's write all these status!"
    print "!!!!!!!!!!!!!!!! WARNING !!!!!!!!!!!!!!!!!!!!!!!"
    tm.sleep(1)
    print "------------------------------------------------"
    tm.sleep(1)
    print "For the part below to work, please consult the website https://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual before continuing."
    notimportant = raw_input("Press Enter to continue.")
    print "Type in c.ANT.status() on the ipython command prompt. Enter the outputted results below."
    ANT = raw_input("Enter ANT status comments: 		")
    file.write('\n\nANT status output: ')
    file.write('\n' + ANT)
    print "Type in c.CORR.status() on the ipython command prompt. Enter the outputted results below."
    CORR = raw_input("Enter CORR status comments: 		")
    file.write('\n\nCORR status output: ')
    file.write('\n' + CORR)
    print "Type in c.FreqCtr.status() on the ipython command prompt. Enter the outputted results below."
    FreqCtr = raw_input("Enter FreqCtr status comments: 		")
    file.write('\n\nFreqCtr status output: ')
    file.write('\n' + FreqCtr)
    print "Type in c.GPIO.status() on the ipython command prompt. Enter the outputted results below."
    GPIO = raw_input("Enter GPIO status comments: 		")
    file.write('\n\nGPIO status output: ')
    file.write('\n' + GPIO)
    print "Type in c.GPU.status() on the ipython command prompt. Enter the outputted results below."
    GPU = raw_input("Enter GPU status comments: 		")
    file.write('\n\nGPU status output: ')
    file.write('\n' + GPU)
    print "Type in c.REFCLK.status() on the ipython command prompt. Enter the outputted results below."
    REFCLK = raw_input("Enter REFCLK status comments: 		")
    file.write('\n\nREFCLK status output: ')
    file.write('\n' + REFCLK)
    print "Type in c.SPI.status() on the ipython command prompt. Enter the outputted results below."
    SPI = raw_input("Enter SPI status comments: 		")
    file.write('\n\nSPI status output: ')
    file.write('\n' + SPI)
    print "Type in c.SYSMON.status() on the ipython command prompt. Enter the outputted results below."
    SYSMON = raw_input("Enter SYSMON status comments: 		")
    file.write('\n\nSYSMON status output: ')
    file.write('\n' + SYSMON)
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
        testStatus[9] = False
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update( testStatus )
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")
