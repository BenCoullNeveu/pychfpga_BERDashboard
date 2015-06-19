from numpy import *
import time as tm
import os
import iceboardtest
from other_stuff import date_format, read_config, get_repo
from statusReport import EMPTY_TEST_STATUS
from testFail import mtestFail, armFail
from fpgaFun import read_list, edit_list

def programARMtest(username=None,board_sn=None,board_vn=None,board_md=None,testStatus = EMPTY_TEST_STATUS()):
    testStatus[0] = username
    testStatus[1] = board_sn
    testStatus[2] = board_vn
    # Get config
    config = read_config()

    # Check file exists for this board
    fname = os.path.join(config['results_directory'], 'board' + board_sn + '.txt')
    if not os.path.isfile(fname):
        print "There is no existing file for this board."
        print "Redirecting to 'iceboardtest.py' to create a new board file.\n"
        iceboardtest.starttest()
        return testStatus

    file = open(fname, 'a')
    file.write('\n\nProgramming the ARM Test\n')
    file.write('-------------------------\n')
    date_str=date_format(tm.localtime())
    file.write('| Date : ' + date_str + '\n')
    file.write('| Tester: ' + username + '\n')
    repo = get_repo()
    file.write("| On branch '" + str(repo.active_branch) + "' with commit " + str(repo.commit('HEAD')) +
               " of " + os.path.split(os.path.dirname(repo.git_dir))[-1] + ".\n\n")
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

    raw_input("Press Enter to continue: 	")

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
    else:
        file.write('N.B. LED lights *DID NOT flash* after initiating board.\n\n')
    print "\nLogin to the router's control panel at 10.10.10.1 using a browser."
    print "Open the 'Clients' page (large computer icon on the main page)."
    raw_input("Press Enter to continue: 	")

    print "Look at the list of clients and find which one of the MAC addresses (left column) correponds to this board. A quick "
    print "way of doing this is to simply unplug the Ethernet cable from the board and note which MAC/IP in the list vanishes."
    print "Do this a few times to confirm that the MAC address is right."

    print "Please enter the MAC address of the board below: "
    MACright = raw_input("Enter MAC address: ")
    file.write('MAC address of left Ethernet connector: ' + MACright)

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
    file.write('\n\nIP address of left Ethernet connector:  ' + IPright)

    # Add MAC and IP to iceboard_list.txt file
    content = read_list()
    current_ip = None
    current_mac = None
    for line in content[1:len(content)]:
        if int(line[0]) == int(board_sn):
            current_ip = line[1]
            current_mac = line[2]
            break
        else:
            pass
    if current_ip is None or len(current_ip) < 20:
        print "\nNo previous valid assigned IP. Adding " + IPright + " to list."
        new_ip = "'http://" + IPright + ":80/tuber'"
    else:
        print "\nFound IP already in list. " + current_ip + " It will not be modified."
        new_ip = None
    if current_mac is None or len(current_mac) < 18:
        print "No previous valid assigned MAC. Adding " + MACright + " to list."
        new_mac = "'" + MACright + "'"
    else:
        print "Found MAC already in list. " + current_mac + " It will not be modified."
        new_mac = None
    edit_list(board_sn, arm_ip = new_ip, arm_mac = new_mac)
    
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
        file.write('\n\nPinging the board: Pass')
    else:
        file.write('\n\nPinging the board: Fail')
        file.write('\n\n**ARM Programming Test Overall Status: Fail**\n')
        file.close()
        return armFail(username,board_sn,board_vn,board_md,testStatus)
    print "Let's try to log in via ssh onto the board! In your terminal window, type in 'ssh root@IP' where IP is the IP address of board."
    print "The password is blank. At the command line, you should see you logged in as root@iceboard."
    print "Were you successful in logging in via ssh "
    ssh = raw_input("Enter 'Y' or 'N': 	")
    if ssh == 'Y' or ssh == 'y':
        file.write('\n\nLogging into the board via ssh: Pass')
    else:
        file.write('\n\nLogging into the board via ssh: Fail')
        file.write('\n\n**ARM Programming Test Overall Status: Fail**\n')
        file.close()
        return armFail(username,board_sn,board_vn,board_md,testStatus)
    
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
    file.write('\n\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'): 	")
    if check == 'Y' or check == 'y':
        file.write('\n\n**ARM Programming Test Overall Status: Pass**\n')
        file.close()
        testStatus[7] = True
    else:
        file.write('\n\n**ARM Programming Test Overall Status: Fail**\n')
        file.close()
        testStatus[7] = False
        return armFail(username,board_sn,board_vn,board_md,testStatus)

    return testStatus







