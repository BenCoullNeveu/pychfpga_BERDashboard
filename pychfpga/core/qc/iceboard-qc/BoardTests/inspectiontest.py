from numpy import *
from math import *
import pylab as plt
import time as tm
import os
import shutil
import iceboardtest
import sys
import updateStatus

def inspectiontest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = [ '', '', '', None, None, None, None, None, None, None, None, '' ]):
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
    file.write('\nInspection Test\n')
    file.write('------\n')
    date_str=iceboardtest.date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n\n')
    print 'For this test, please do NOT power up the board. Everything should be done with nothing connected to the power supply!'
    print "It is highly suggested for you to view the board under the microscope to see everything properly."
    print "When travelling with the board, please be VERY GENTLE."
    print "Please write down any comments you wish to make (shorting, scratches, unsoldered parts, etc.) before continuing"
    notimportant = raw_input("Press Enter to continue when you have done the above.... ")
    
    print 'Are there any unsoldered components?'
    file.write('Soldering status: ')
    unsol = raw_input("Enter ('Y' or 'N'):     ")
    if unsol == 'Y' or unsol == 'y':
        file.write('Bad. Unsoldered parts on board. \n')
        file.write('Unsoldered parts: ')
        print 'Please describe the unsoldered parts. Please be specific (describe the component names)'
        solcomment = raw_input("Enter:     ")
        file.write(solcomment + '\n')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    else:
        file.write('All soldering seems fine. \n')
        soldering = False
    print 'Are there any shorted components?'
    file.write('Shorting status: ')
    shorts = raw_input("Enter ('Y' or 'N') :   ")
    if shorts == 'Y' or shorts == 'y':
        file.write('Bad. Shorted components on board. \n')
        file.write('Shorted parts: ')
        print 'Please describe the shorted parts. Please be specific (describe the component names)'
        shocomments = raw_input("Enter:     ")
        file.write(shocomment + '\n')
        file.close()
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    else:
        file.write('No unwanted shorted components occur. \n')
        shorting = False
        
    print "If there are any additional comments you wish to make (e.g. scratches), please describe below. (If none, enter 'None')"
    comments = raw_input("Enter additional comments:    ")
    file.write('Additional comments: ' + comments + '\n')
    print "Are there any worrying issues regarding the board?"
    lastminutecheck = raw_input("Enter 'Y' or 'N':     ")
    if lastminutecheck == 'Y' or lastminutecheck == 'y':
        print "Please describe any of these last concerns:"
        otherissues = raw_input("Enter:     ")
        file.write('Major issues: ' + otherissues)
        sys.exit("It is unsafe to proceed any further testing. Please check with someone and fix the problem appropriately before proceeding")
    else:
        file.write('Major issues: None \n')
        issues = False
        
    if soldering == False and shorting == False and issues == False:
        file.write('Inspection test: PASS \n')
        file.close()
        testStatus[3] = True
    else:
        file.write('Inspection test: FAIL \n')
        file.close()
        testStatus[3] = False
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")