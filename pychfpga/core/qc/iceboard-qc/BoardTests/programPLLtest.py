from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import sys
import updateStatus
from statusReport import EMPTY_TEST_STATUS

def programPLLtest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
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
    file.write('\n\nProgramming the PLL Test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')

    print "For this test, you'll need an FTDI cable and a jumper."
    print "Please see http://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual for details"
    print "or seek help from someone (i.e. Kevin). Make sure the board's connected to a power supply but turn it off for now."
    print "Please attach a jumper for the 'Crystal' Jumper in the Clock Select Jumpers selection. "
    print "They are located on the left of the SD card slot. "
    notimportant = raw_input("Press Enter to continue: 	")
    print "Locate the PLL Programming pins on the boards. They are just to the left of the shields."
    print "Please connect the FTDI cable mini wires to the pins as follows:"
    print "GREEN to (tdo or miso), YELLOW to (tdi or mosi), ORANGE to (tck or sck), BROWN to either csn2 (pll2) or csn1(pll1) and BLACK to ground."
    print "When programming PLL1, you'll want the brown wire connected to whichever PLL you wish to program. The csn1 pin corresponds to PLL1"
    print "and csn2 pin corresponds to PLL2. For the purpose of this test, we'll program PLL1 first, so please attach the brown wire to csn1 pin."
    print "(But really, it doesn't matter which one you program first....)"
    notimportant = raw_input("Press Enter to continue:")

    print "Unfortunately, we cannot use Windows to program the boards. We must program the board through a virtual Linux machine."
    print "Click on the Windows start icon at the lower left corner of the screen. Select All Programs. Then click on Oracle VM VirtualBox directory."
    print "Click on Oracle VM VirtualBox program."
    notimportant = raw_input("Press Enter to continue: ")
    print "In the Manager window, click on Start icon at the top."
    print "In the pop-up window, select 'Host Drive D:' and then click on Start."
    print "Wait for the Virtual Machien to bootup."
    notimportant = raw_input("Press Enter to continue:  ")
    print "After a while, you should on a Ubuntu desktop. "
    print "Turn on the power supply of the board."
    notimportant = raw_input("Press Enter to continue:  ")
    print "On the bottom of the Virtual Machine window, there are several small icons. RIGHT click on the USB icon (third from the left)."
    print "There should be an option that says FTDI ... If it is not selected, please click on it to have a checkmark beside it."
    print "If you don't see the FTDI option, you'll need to power cycle the board and attempt again."
    notimportant = raw_input("Press ENter to continue:   ")
    print "Open up a terminal window. (You can do so by click on the large swirly circular icon on the left"
    print "side of the desktop (which is the first one). In the searchbox, type in 'Terminal' and click on the icon (the box with >_ inside)."
    print "Go to the git rdirectory, then cd to the iceboard-qc repository then go to the pll directory."
    notimportant = raw_input("Press enter to continue:   ")
    print "Since we have the brown wire connected to csn1, we'll need to run the pllprog1 executable."
    print "To do so, type in 'sudo ./pllprog1' in the terminal window."
    print "The password is the location of CHIME (all lowercase, no special letters)."
    print "You should be able to see an output like this: 0: 0x01260320 1:0xeb060301 2:0x011e0302 3: 0xeb040303 4: 0xeb860314 ... until 9:0x0000001f."
    print "Do you see an output like above?"
    PLL1output = raw_input("Enter 'Y' or 'N': 	")
    if PLL1output == 'n' or PLL1output == 'N':
        file.write('\n\nPLL Programming Test: Fail to program PLL1')
        file.write('\n\nPLL Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "OK, let's check to make sure the PLL test actually worked, power cycle the board as it is."
    print "Check the LED lights at the top left corner of the board. You should see one of the LEDs light up. This means the PLL is programmed!"
    print "Is this the case?"
    PLL1 = raw_input("Enter 'Y' or 'N':     ")
    if PLL1 == 'Y' or PLL1 == 'y':
        file.write('\nThe LED lighted up after programming PLL1.')
    else:
        file.write('\nThe LED failed to light up after programming PLL1. ')
        file.write('\nPLL Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Let's program the other PLL. Turn off the board (for safety reasons) and switch the brown wire from csn1 pin to csn2 pin."
    print "Power on the board."
    notimportant = raw_input("Press Enter to continue:  ")
    print "In the Virtual Machine, type in 'sudo ./pllprog2' in the terminal window. Enter the password."
    print "Do you see an output as that described from PLL1?"
    PLL2output = raw_input("Enter 'Y' or 'N':   ")
    if PLL1output == 'n' or PLL1output == 'N':
        file.write('\n\nPLL Programming Test: Fail to program PLL2')
        file.write('\n\nPLL Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Check the LED lights at the top left corner of the board. You should see another one of the LEDs light up. This means the PLL is programmed!"
    print "Is this the case?"
    PLL1 = raw_input("Enter 'Y' or 'N':     ")
    if PLL1 == 'Y' or PLL1 == 'y':
        file.write('\nThe LED lighted up after programming PLL1.')
    else:
        file.write('\nThe LED failed to light up after programming PLL1. ')
        file.write('\nPLL Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    
    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'): 	")
    if check == 'Y' or check == 'y':
        file.write('\n\nPLL Programming Test Overall Status: Pass')
        file.close()
        testStatus[6] = True
    else:
        file.write('\n\nPLL Programming Test Overall Status: Fail')
        file.close()
        testStatus[6] = False
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")







