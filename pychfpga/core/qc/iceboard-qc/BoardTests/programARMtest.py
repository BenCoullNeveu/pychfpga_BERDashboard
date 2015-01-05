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
from testFail import mtestFail, armFail
import git

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
    file.write('Tester: ' + username + '\n')
    repo = git.Repo()
    file.write("On branch '" + repo.active_branch + "' with commit " + str(repo.commit('HEAD')) + " of iceboard-qc.\n\n")
    file.flush()

    print "For this test, you'll need an Ethernet cable, D-link router and an SD card."
    print "Please obtain a properly programmed SD card. These should be available in the CHIME lab."
    print "Insert the SD card in the slot on the top right corner of board. The card should slide"
    print "comfortably in with the golden plates facing down."

    print "\nPlease set up the D-link router."
    print "Be sure an Ethernet cable links the lab network to one of the slots in the router."
    print "Be sure an Ethernet cable links this computer to the router."

    print "\nLook on the righthand side of the board. You should see a set of"
    print "switches labelled BTMode Switches. We'll need to configure them."
    print "Please leave the GP switches ALONE for this part."

    notimportant = raw_input("Press Enter to continue: 	")

    print "For SW1, turn switches 2,3,5 on (up). For SW2, turn switches 2,4 on (up)."
    print "The switch configuration should look like below:"
    print "DUUDUDDD DUDUDDDD"
    print "You will also need to flip the switches for the FPGA Config Mode. The set of 4 switches are located above the heat sink."
    print "Flip the configuration to be UDDD."
    print "Please note the orientation of the switch is upsidedown, so technically, switches 1,2,3 are actually up and 4 is down."
    print "When you have done so, you may proceed." #  You may consult https:// for details."

    print "\nLook at the bottom right corner of the board. There should be two Ethernet ports."
    print "Connect an Ethernet cable going from the LEFT-MOST INNER port to the router."
    print "Power on the board."

    print "\nWait a few minutes, you should be able to see some LEDs flashing on the right side of the board."
    print "Have any lights flashed after waiting a few minutes since the board turned on?"
    lights = raw_input("Enter 'Y' or 'N': 	")
    if lights == 'Y' or lights == 'y':
        file.write('LED lights flashed after initiating board. Hints at proper connection and properly programmed SD card.\n\n')
    print "\nOpen up an Internet browser window. Log on to 10.10.10.1 by typing in 'https://10.10.10.1' in the adress bar."
    print "Ask Kevin for the username and password associated with the website."
    print "Click on the large computer icon on centre-left part of the website. (There will be text saying 'Clients:' below it"
    notimportant = raw_input("Press Enter to continue: 	")

    print "\nThe icon should now be highlighted in blue. There will now be a list on the right hand side of the page."
    print "On the list, find which of the MAC addresses (left column) correponds to that of the board. A quick and "
    print "dirty way of doing this is simply writing down all the IP addresses (right column) you see in the list, unplug the"
    print "Ethernet cable from the board, hit refresh, and see which of the IP address disappeared from the list."
    print "Do this a few times to confirm that the MAC address is right."

    print "Please enter the MAC address of the board below: "
    MACright = raw_input("Enter MAC address: ")
    file.write('\nMAC address of left Ethernet connector: ' + MACright)

    print "\nNow we must change the IP address from this Ethernet port to match the serial number of board."
    print "On left hand side of the page, under Advanced Settings, click on LAN. On top of page, you should"
    print "see some tabs. Click on the DHCP Server tab."

    print "What we want to do now is manually assign the IP address for this board. Scroll down to the Manually Assigned IP section."
    print "From the drop-down box in the MAC address column, pick the one which corresponds to the board. Its corresponding IP address"
    print "should appear in the column beside it. Change the IP address to 10.10.10.NUM where NUM is the serial number of the board."
    print "(i.e. if the board has serial number 0009, its IP address should be 10.10.10.9  "

    print "Now, click on the + icon in the last column to add this IP address. DOUBLE CHECK to make sure it's the right IP address!"
    print "Write down the IP address of the board."
    IPright = raw_input("Enter IP address: 	")
    file.write('\nIP address of left Ethernet connector:  ' + IPright)

    print "\nAfter programming the IP address, let's check to see if this works! Open up a Terminal window, such as git bash."
    print "On the command line, type in 'ping IP' where IP is the IP address you've just assigned to it."
    print "You should be able to send and receive packets without any issues. The terminal window should say more or less something like so:\n"
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

    print "\nAre you able to ping the board and have a result like above?"
    ping = raw_input("Enter 'Y' or 'N': 	")
    if ping == 'Y' or ping == 'y':
        file.write('\nPinging the board: Pass')
    else:
        file.write('\nPinging the board: Fail')
        file.write('\nARM Programming Test Overall Status: Fail')
        file.close()
        armFail(username,board_sn,board_vn,board_md,testStatus)
    print "Let's try to log in via ssh onto the board! In your terminal window, type in 'ssh root@IP' where IP is the IP address of board."
    print "The password is blank. At the command line, you should see you logged in as root@iceboard."
    print "Were you successful in logging in via ssh "
    ssh = raw_input("Enter 'Y' or 'N': 	")
    if ssh == 'Y' or ssh == 'y':
        file.write('\nLogging into the board via ssh: Pass')
    else:
        file.write('\nLogging into the board via ssh: Fail')
        file.write('\nARM Programming Test Overall Status: Fail')
        file.close()
        armFail(username,board_sn,board_vn,board_md,testStatus)
    
    # Memory test
    #print("\nThe next step is to perform a memory test")
    #print("You will need a different SD card, labeled 'MTEST'. It should be in the drawer under the monitor.")
    #print("You will also need to read the RS232 from the board. For this, take the FTDI cable and three pin adapter (also in the drawer).")
    #print("Load the SD card into the board, flip it upside down, and find the RS232 connector (three small holes just to the left of the ARM).")
    #print("Attach the adapter and connect the yellow cable to the pin closest to the ARM, the black cable in the centre, and the orange one furthest from the ARM.")
    #print("Open up 'Termite' on the computer and boot up the board. You should see the RS232 output scroll across the screen.")
    #print("You must now reboot the board and interrupt the bootloader by entering any key in Termite IMMEDIATELY.")
    #print("Once you are in the shell, enter 'mtest' to begin the memory test.")
    #print("You should see it go through an iteration (printing one line) every few seconds. If you see a bunch of reading/writing scrolling across the screen,\nyou interrupted the boot too late. Try again and make sure you interrupt the first boot stage, immediately after it starts.")
    #print("Let mtest run through a few iterations (5-10) to confirm it doesn't produce any errors.")
    #errors = raw_input("\nDid mtest produce any errors? (y/n)\t")
    #if errors == 'Y' or errors == 'y':
    #    file.write("\nMemory Test produces errors: FAIL\n")
    #    file.write('\nARM Programming Test Overall Status: Fail\n')
    #    mtestFail(username, board_sn, board_vn, board_md, testStatus)
    #else:
    #    file.write("\nMemory Test produces no errors: Pass\n")
    
    print "If there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments: 	")
    file.write('\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'): 	")
    if check == 'Y' or check == 'y':
        file.write('\n\nARM Programming Test Overall Status: Pass')
        file.close()
        testStatus[7] = True
    else:
        file.write('\n\nARM Programming Test Overall Status: Fail')
        file.close()
        testStatus[7] = False
        armFail(username,board_sn,board_vn,board_md,testStatus)
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")







