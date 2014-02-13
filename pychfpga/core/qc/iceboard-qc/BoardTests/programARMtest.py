from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import sys

def programARMtest(username=None,board_sn=None,board_vn=None,board_md=None):
    if (username == None) or (board_sn == None) or (board_vn == None) or (board_md == None):
        iceboardtest()
    fname = 'board' + board_sn + '.txt'
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
    print "On the list, find which of the MAC addres (left column) correponds to that of the board. A quick and "
    print "dirty way of doing this is simply writing down all the IP addresses (right column) you see in the list, unplug the"
    print "Ethernet cable from the board, hit refresh, and see which of the IP address disappeared from the list."
    tm.sleep(2)

    print "Please enter the MAC address of the board below: "
    MACright = raw_input("Enter MAC address: ")
    file.write('MAC address of right Ethernet connector: ' + MACright)

    print "Now we must change the IP address from this Ethernet port to match the serial number of board."
    print "On left hand side of the page, under Advanced Settings, click on LAN."






