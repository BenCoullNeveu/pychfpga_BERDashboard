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
from testFail import inspectionFail
import git

def inspectiontest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
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
    fname = 'board' + board_sn + '.txt'
    file = open(fname, 'a')
    file.write('\nInspection Test\n')
    file.write('------\n')
    date_str=date_format(tm.localtime())
    file.write('Date : ' + date_str + '\n')
    file.write('Tester: ' + username + '\n')
    repo = git.Repo()
    file.write("On branch '" + repo.active_branch + "' with commit " + str(repo.commit('HEAD')) + " of iceboard-qc.\n\n")
    file.flush()

    print 'For this test, please do NOT power up the board. Everything should be done with nothing connected to the power supply!'
    print "It is highly suggested for you to view the board under the microscope to see everything properly."
    print "When travelling with the board, please be VERY GENTLE."
    notimportant = raw_input("Press Enter to continue when you have done the above.... ")
    
    print '\nAre there any unsoldered components?'
    file.write('Soldering status: ')
    unsol = raw_input("Enter ('Y' or 'N'):     ")
    if unsol == 'Y' or unsol == 'y':
        file.write('Bad. Unsoldered parts on board. \n')
        file.write('Unsoldered parts: ')
        print 'Please describe the unsoldered parts. Please be specific (describe the component names)'
        solcomment = raw_input("Enter:     ")
        file.write(solcomment + '\n')
        soldering = True
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
        file.write(shocomments + '\n')
        shorting = True
    else:
        file.write('No unwanted shorted components occur. \n')
        shorting = False
        
    print "Please inspect the GTX backplane connector pins on the back of the board (you will need the microscope). Are any of them bent or otherwise unusual?"
    confirm = raw_input("Enter 'Y' or 'N':    ")
    if confirm == 'Y' or confirm == 'y':
        print "Describe the problematic pins and give their location (e.g. '4th pin of 1st column is bent')"
        comment = raw_input("Enter:    ")
        file.write('Problem with GTX backplane connector pins: ' + comment  + '\n')
        GTX = True
    else:
        file.write('GTX backplane connector pins seem fine.\n')
        GTX = False
        
    print "If there are any additional comments you wish to make (e.g. scratches), please describe below. (If none, enter 'None')"
    comments = raw_input("Enter additional comments:    ")
    file.write('Additional comments: ' + comments + '\n')
    print "Are there any worrying issues regarding the board?"
    lastminutecheck = raw_input("Enter 'Y' or 'N':     ")
    if lastminutecheck == 'Y' or lastminutecheck == 'y':
        print "Please describe any of these last concerns:"
        otherissues = raw_input("Enter:     ")
        file.write('Major issues: ' + otherissues)
        issues = True
    else:
        file.write('Major issues: None \n')
        issues = False
        
    if soldering == False and shorting == False and issues == False and GTX == False:
        file.write('Inspection test: PASS \n')
        file.close()
        testStatus[3] = True
    else:
        file.write('Inspection test: FAIL \n')
        file.close()
        inspectionFail(username,board_sn,board_vn,board_md,testStatus)
    print "Do you wish to proceed to another test?"
    proceed = raw_input("Enter 'Y' or 'N':  ")
    if proceed == 'Y' or proceed == 'y':
        iceboardtest.choosetest(username,board_sn,board_vn,board_md,testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")