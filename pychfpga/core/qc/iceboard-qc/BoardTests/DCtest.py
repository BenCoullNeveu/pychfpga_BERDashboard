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
from testFail import DCFail

def DCtest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
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
    file.write('\n\nDC Test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')
    print 'For this test, please do power up the board. '# Please configure the set up to that as shown on http://kingspeak.physics.mcgill.ca/twiki/bin/view/Chime/IceBoardQCManual'
    print 'For this board, you will need a multimeter, a power supply, and a twisted pair cable with two banana plugs on one side to measure voltage.'
    notimportant = raw_input("Press Enter to continue:      ")
    print "Lay the board on a grounding mat in front of you"
    print "To properly orient the board, rotate the board until the McGill Cosmology logo is facing the right way as you look at the board"
    print "The buck regulators to be tested will go in a ANTICLOCKWISE order, starting off with the upper left-most regulator"
    # print "If you're unsure about which regulator is which, please refer to 'https://' for an image guide"
    print "All these regulators should be probed with respects to the board's GROUND. A good ground to pick is the ground to the power supply, i.e. centre screw on the connector on the left-hand side of the board"
    print "You should be probing the LONGER pin on the regulators."
    print "When probing, it's a good habit to press the probe testing the place of interest with the pin tightly pressed against your fingertips."
    print "Again, refer to the website for help."
    notimportant = raw_input("Press Enter to continue:  ")
    print "I M P O R T A N T"
    print "-----------------"
    print "For this test, it is REALLY EASY to kill the board"
    notimportant = raw_input("Press Enter to continue:  ")
    print "You MUST take utmost care not to accidently fry the board!"
    notimportant = raw_input("Press Enter to continue:  ")
    print "Whatever you do, do NOT short the smaller pin on the buck regulator to anything else"
    notimportant = raw_input("Press Enter to continue:  ")
    print "Be SURE you are measuring the longer pin on the regulators"
    notimportant = raw_input("Press Enter to continue:  ")
    print "Make sure you are pressing the probe tightly against your fingers to prevent it from shorting anything else!"
    notimportant = raw_input("Press Enter to continue:  ")

    file.write('================  ======== ======== ========\n')
    file.write('\n')
    file.write('Voltage Supply    Measured Expected Status\n')
    file.write('\n')
    file.write('================  ======== ======== ========\n')
    
    print "Please read the voltage measurement on power supply. Enter the voltage below (up to 3 sig. figs. , i.e. '1.00')."
    volt = float(input("Enter:     "))
    file.write('Voltage           ' + str(volt) + '     ' + '16.0     ')
    if abs((volt-16.00))/16. < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        print "\nThe board needs a 16V power supply.\n"
        DCFail((username, board_sn, board_vn, board_md, testStatus))

    print "Please read the current measurement on power supply. Enter the voltage below (up to 3 sig. figs. , i.e. '1.00')."
    cur = float(input("Enter:     "))
    file.write('Current           ' + str(cur) + '     ' + '1.00     ')
    if abs((cur-0.90))/0.9 < 0.15:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        print "\nCurrent not within acceptable range.\n"
        DCFail(username, board_sn, board_vn, board_md, testStatus)
    file.write('================  ======== ======== ========\n\n')

    file.write('================  ======== ======== ========\n')
    file.write('\n')
    file.write('Regulator         Measured Expected Status\n')
    file.write('\n')
    file.write('================  ======== ======== ========\n')

    print "Please probe the 12V regulator pin. Enter the voltage below (up to 3 sig. figs. , i.e. '1.00')."
    V12 = float(input("Enter:     "))
    file.write('12V               ' + str(V12) + '     ' + '12.0     ')
    if abs((V12-12.00))/12. < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)
    
    print "Please probe the Vadj regulator pin. Enter the voltage below (up to 3 sig. figs, i.e. '1.00')."
    Vadj = float(input("Enter:     "))
    file.write('Vadj              ' + str(Vadj) + '     ' + '2.50     ')
    if abs((Vadj-2.50))/2.5 < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)

    print "Please probe the 3V3 regulator pin. Enter the voltage below (up to 3 sig. figs. , i.e. '1.00')."
    V3 = float(input("Enter:     "))
    file.write('3V3               ' + str(V3) + '     ' + '3.30     ')
    if abs((V3-3.30))/3.3 < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)

        print "Please probe the 3V3 regulator pin. Enter the voltage below (up to 3 sig. figs. , i.e. '1.00')."

    print "Please probe the 5V regulator pin. Enter the voltage below (up to 3 sig. figs., i.e. '1.00')."
    V5 = float(input("Enter:     "))
    file.write('5V                ' + str(V5) + '     ' + '5.50     ')
    if abs(V5-5.50)/5.5 < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)
    
    print "Please skip the buck regulator next to the power connector."
    notimportant = raw_input("Press Enter to continue:  ")
    
    print "Please probe the 1VGTX regulator pin. Enter the voltage below (up to 3 sig. figs., i.e. '1.00')."
    VGTX1 = float(input("Enter:     "))
    file.write('1VGTX             ' + str(VGTX1) + '     ' + '1.00     ')
    if abs(VGTX1-1.05)/1.05 < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)

    print "Please probe the 1.2VGTX regulator pin. Enter the voltage below (up to 3 sig. figs., i.e. '1.00')."
    VGTX12 = float(input("Enter:     "))
    file.write('1.2VGTX           ' + str(VGTX12) + '     ' + '1.20     ')
    if abs(VGTX12-1.20)/1.2 < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)

    print "Please probe the 1VCORE regulator pin. Enter the voltage below (up to 3 sig. figs., i.e. '1.00')."
    VCORE1 = float(input("Enter:     "))
    file.write('1VCORE            ' + str(VCORE1) + '     ' + '1.00     ')
    if abs(VCORE1-1.00)/100. < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)

    print "Please probe the 1.5V regulator pin. Enter the voltage below (up to 3 sig. figs., i.e. '1.00')."
    V15 = float(input("Enter:     "))
    file.write('1.5V              ' + str(V15) + '     ' + '1.50     ')
    if abs(V15-1.50)/100. < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)

    print "Please probe the 1.8V regulator pin. Enter the voltage below (up to 3 sig. figs., i.e. '1.00')."
    V18 = float(input("Enter:     "))
    file.write('1.8V              ' + str(V18) + '     ' + '1.80     ')
    if abs(V18-1.80)/100. < 0.02:
        file.write('Pass\n')
    else:
        file.write('Fail\n')
        file.write('================  ======== ======== ========\n')
        file.close()
        DCFail(username, board_sn, board_vn, board_md, testStatus)


    file.write('================  ======== ======== ========\n\n')

    file.write('DC Test Overall Status: Pass')
    file.close()
    testStatus[5] = True
    
    print "\nIf this hasn't been done, you should attach a heat sink on the FPGA at this point."
    # print "Please consult http://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual as this is not part of the testing process"
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")
    