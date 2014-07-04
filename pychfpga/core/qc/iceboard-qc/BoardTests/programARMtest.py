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

def programARMtest(username=None,board_sn=None,board_vn=None,board_md=None,testStatus = EMPTY_TEST_STATUS()):
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
    file.write('\n\nProgramming the ARM Test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')

    print "For this test, you'll need an Ethernet cable, D-link router and an microSD card."
    print "Please obtain a properly programmed SD card. If you cannot do so,"
    print "follow the instructions on http://"
    print "or seek help from someone (i.e. Kevin)."
    print "Insert the SD card in the slot on the top right corner of board. The card should slide"
    print "comfortably in with the golden plates facing down."

    notimportant = raw_input("Press Enter to continue: 	")
    print "Please set up the D-link router."
    print "Be sure an Ethernet cable links the lab network to one of the slots in the router."
    print "Be sure an Ethernet cable links this computer to the router."
    notimportant = raw_input("Press Enter to continue:")

    print "Look on the righthand side of the board. You should see a set of"
    print "switches labelled BTMode Switches. We'll need to configure them."
    print "Please leave the GP switches ALONE for this part."

    notimportant = raw_input("Press Enter to continue: 	")

    print "For SW1, turn switches 2,3,5 on (up). For SW2, turn switches 2,4 on (up)."
    print "The switch configuration should look like below:"
    print "DUUDUDDD DUDUDDDD"
    print "You will also need to flip the switches for the FPGA Config Mode. The set of 4 switches are located above the heat sink."
    print "Flip the configuration to be UDDD."
    print "Please note the orientation of the switch is upsidedown, so technically, switches 1,2,3 are actually up and 4 is down."
    print "When you have done so, you may proceed. You may consult https:// for details."
    notimportant = raw_input("Press Enter to continue: 	")
    print "Look at the bottom right corner of the board. There should be two Ethernet ports."
    print "Connect an Ethernet cable going from this computer to the RIGHT-MOST OUTER port to the router."
    print "Power on the board."
    notimportant = raw_input("Press Enter to continue: 	")

    print "Wait a few minutes, you should be able to see some LEDs flashing on right side of the board."
    notimportant = raw_input("Press Enter to continue: 	")
    print "Have any lights flashed after waiting a few minutes since board turned on?"
    lights = raw_input("Enter 'Y' or 'N': 	")
    if lights == 'Y' or lights == 'y':
        file.write('LED lights flashed after initiating board. Hints at proper connection and properly programmed SD card.\n\n')
    print "Open up an Internet browser window. Log on to 10.10.10.1 by typing in 'https://10.10.10.1' in the adress bar."
    print "Ask Kevin for the username and password associated with the website."
    print "Click on the large computer icon on centre-left part of the website. (There will be text saying 'Clients:' below it"
    notimportant = raw_input("Press Enter to continue: 	")

    print "The icon should now be highlighted in blue. There will now be a list on the right hand side of the page."
    print "On the list, find which of the MAC addresses (left column) correponds to that of the board. A quick and "
    print "dirty way of doing this is simply writing down all the IP addresses (right column) you see in the list, unplug the"
    print "Ethernet cable from the board, hit refresh, and see which of the IP address disappeared from the list."
    print "Do this a few times to confirm that the MAC address is right."
    tm.sleep(2)

    print "Please enter the MAC address of the board below: "
    MACright = raw_input("Enter MAC address: ")
    file.write('\nMAC address of right Ethernet connector: ' + MACright)

    print "Now we must change the IP address from this Ethernet port to match the serial number of board."
    print "On left hand side of the page, under Advanced Settings, click on LAN. On top of page, you should"
    print "see some tabs. Click on the DHCP Server tab."
    notimportant = raw_input("Press Enter to continue: 	")

    print "What we want to do now is manually assign the IP address for this board. Scroll down to the Manually Assigned IP section."
    print "From the drop-down box in the MAC address column, pick the one which corresponds to the board. Its corresponding IP address"
    print "should appear in the column beside it. Change the IP address to 10.10.10.NUM where NUM is the serial number of the board."
    print "(i.e. if the board has serial number 0009, its IP address should be 10.10.10.9  "
    notimportant = raw_input('Press Enter to continue: 	')

    print "Now, click on the + icon in the last column to add this IP address. DOUBLE CHECK to make sure it's the right IP address!"
    notimportant = raw_input('Press Enter to continue: 	')
    print "Are you sure you have the right IP address? Double check!"
    notimportant = raw_input('Press Enter to continue: 	')
    print "Once you're SURE it's the right IP address, click on Apply at the bottom of the table."
    print "Write down the IP address of the board."
    IPright = raw_input("Enter IP address: 	")
    file.write('\nIP address of right Ethernet connector:  ' + IPright)

    print "After programming the IP address, let's check to see if this works! Open up a Terminal window, such as git bash."
    print "On the command line, type in 'ping IP' where IP is the IP address you've just assigned to it."
    tm.sleep(2)
    notimportant = raw_input("Press Enter to continue.")
    print "You should be able to send and receive packets without any issues. The terminal window should say more or less something like so:"
    print "$ping 10.10.10.9"
    print "Pinging 10.10.10.9 with 32 bytes of data:"
    print "Reply from 10.10.10.9: bytes=32 time<1ms TTL=64"
    print "Reply from 10.10.10.9: bytes=32 time<1ms TTL=64"
    print "Reply from 10.10.10.9: bytes=32 time<1ms TTL=64"
    print "Reply from 10.10.10.9: bytes=32 time<1ms TTL=64"

    print "Ping statistics for 10.10.10.9:"
    print "Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),"
    print "Approximate round trip times in milli-seconds:"
    print "Minimum = 0ms, Maximum = 0ms, Average = 0ms"

    print "Are you able to ping the board and have a result like above?"
    ping = raw_input("Enter 'Y' or 'N': 	")
    if ping == 'Y' or ping == 'y':
        file.write('\nPinging the board: Pass')
    else:
        file.write('\nPinging the board: Fail')
        file.write('\nARM Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Let's try to log in via ssh onto the board! In your terminal window, type in 'ssh root@IP' where IP is the IP address of board."
    print "Obtain the password from Kevin. At the command line, you should see you logged in as root@iceboard."
    print "Were you successful in logging in via ssh "
    ssh = raw_input("Enter 'Y' or 'N': 	")
    if ssh == 'Y' or ssh == 'y':
        file.write('\nLogging into the board via ssh: Pass')
    else:
        file.write('\nLogging into the board via ssh: Fail')
        file.write('\nARM Programming Test Overall Status: Fail')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "If there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments: 	")
    file.write('\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'): 	")
    if check == 'Y' or check == 'y':
        file.write('\n\nARM Programming Test Overall Status: Pass')
        file.close()
        testStatus = True
    else:
        file.write('\n\nARM Programming Test Overall Status: Fail')
        file.close()
        testStatus = False
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")







