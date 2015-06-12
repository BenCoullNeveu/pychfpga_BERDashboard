from numpy import *
import time as tm
import os
import iceboardtest
from other_stuff import date_format, read_config, get_repo
from statusReport import EMPTY_TEST_STATUS
from testFail import gtxFail

def GTXtest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
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
    file.write('\n\nGTX Test\n')
    file.write('----------\n')
    date_str=date_format(tm.localtime())
    file.write('| Date : ' + date_str + '\n')
    file.write('| Tester: ' + username + '\n')
    repo = get_repo()
    file.write("| On branch '" + str(repo.active_branch) + "' with commit " + str(repo.commit('HEAD')) + \
           " of " + os.path.split(os.path.dirname(repo.git_dir))[-1] + ".\n\n")
    file.flush()

    print "For this test, we NEED to have the same SET UP as that of the already programmed FPGA. You also need the JTAG and QSFP cables."
    # print "Please consult https:// for details regarding the materials. Or ask Kevin."
    #print "Let's get started. Is the board turned on and the set up same as that described from above?"
    #program = raw_input("Enter 'Y' or 'N': 	")
    #if program != 'Y' and program != 'y':
    #    FPGAtest.FPGAtest(username,board_sn,board_vn,board_md,testStatus)
    
    print "\nThis test can only be run on a computer equipped with the Xilinx Chipscope Pro software."
    print "\nIf this software is not available to you (e.g. you are using the Linux netbook), please skip this test for now."
    print "You may want to inquire about either obtaining the software or to find out if an alternative test is available."
    confirm = raw_input("Do you have the necessary software to proceed to this test? (y/n)\t")
    if not (confirm == 'Y' or confirm == 'y'):
        file.write('\n\nTester not able to perform GTX test at this time as proper software is not available.\nTest status: N/A')
        testStatus[10] = None
        return testStatus
    print "\nLet's set everything up! Grab the JTAG cable and connect all the wires to the JTAG pins. The pins are located on the left side of the fan."
    print "Connect the cables accordingly by pin. Leave the n/c pin unconnected and connect VREF wire to 3V3 pin. All other labels should match."
    print "Connect the JTAG USB to the computer."

    print "\nNow grab a QSFP cable. We need to connect the two scary-looking spiky connector along the bottom edge of the board together."
    # print "Please consult http://kingspeak.physics.mcgill.ca/twiki/bin/edit/Chime/IceBoardQCManual for details regarding the board."
    raw_input("Press Enter to continue:      ")
    print "\nNow let's open up ChipScope Pro's Analyzer program~ Go into the Start Menu."
    print "Go to All Programs -> Xilink Design Tools -> ISE Design Suite 14.4 -> ChipScope Pro -> ChipScoe 64-bit -> Analyzer."
    print "In the new ChipScope window, on the left pane, right above the New Project pane, there should be two small icons."
    print "You are currently selected on a grey P icon, click on the icon to its left, the black four squares icon thing."
    print "This will detect the JTAG cable."
    print "A pop-up window may appear, which states it detects the JTAG cable. Click on OK if this is the case."
    print "Sometimes it takes the program is very picky and will not work right away. If it happens try restarting the program."
    raw_input("Press Enter to continue:         ")
    print "\nYou should be able to see the grey P circle turn into a green P circle."
    print "Now click on File, select the File that has '...\\icebertcore144\\chipscope_proj.cpj' in its name."
    print "Click on No when it asks if you want to save or set the changes."
    raw_input("Press Enter to continue:         ")
    #print "When asked if you want to set up the IBERT core settings... click on No."
    print "\nOn the menu bar, select Device, then DEV:0... then Configure."
    print "In the new pop-up window, click on Select New File button."
    print "In Kevin's iceboard-qc git repository, go into the icebertcore144 directory."
    print "Click on the example_chipscope_ibert.bit file and click Open. Then click on OK of the original pop-up window."
    print "Programming the with the new firmware will take a bit of time..."
    print "You can see your status on the bottom right corner of the Analyzer window."

    print "\nWhen finished, check the upper-left pane. Under DEV select UNIT. Double click on the option 'IBERT Console'. "
    print "When asked if you want to set up the IBERT settings with ..., click on no."
    print "Once completed, check to see ALL the GTX columns (from 0 to 27) are GREEN, with the EXCEPTION of GTX 19 (which is the SFP connection link)."
    print "The scrollbar is small at the bottom of the pane. Are the columns all green (except perhaps GTX 19)?"
    GTXcolumns = raw_input("Enter 'Y' or 'N':       ")
    if GTXcolumns == 'Y' or GTXcolumns == 'y':
        file.write('\nDetection of all Channels (except maybe GTX 19) on the board after programming with Chipscope: Pass')
    else:
        file.write('\nDetection of all Channels (except maybe GTX 19) on the board after programming with Chipscope: Fail')
        file.write('\n\n**GTX Test Overall Status: Fail**')
        file.close()
        return gtxFail(username,board_sn,board_vn,board_md,testStatus)
    print "\nYou may also set the JTAG scan rate to about 1s (Kevin's favourite rate) just below the menu bar on top of the window."
    print "Under the BERT settings, you now will want to do BERT reset. Click on Reset for the BERT reset for each of the 8 columns."
    print "You now will want to wait a while, typically the RX Bit Error Ratio will be very low. (10E-10 ish)"
    print "Are any of the bit error rates for green columns significantly larger than this?"
    biterrorlarge = raw_input("Enter 'Y' or 'N':        ")
    if biterrorlarge == 'Y' or biterrorlarge == 'y':
        file.write('\nBit error rate is larger than expected: ')
        col = raw_input("Enter the column numbers which have significantly larger error ratios:       ")
        file.write('\nColumns which have significantly larger error ratios: ' + col)
        errorratei = raw_input("Enter the bit error rates of the columns you entered above in the same order:  ")
        file.write('\nBit Error Rate of problematic Channels respectively: ' + errorratei)
        file.write('\n\n**GTX Test Overall Status: Fail**')
        file.close()
        return gtxFail(username,board_sn,board_vn,board_md,testStatus)
    print "\nAre the RX Bit Error Count all 0's for the 8 green columns??"
    errorcount = raw_input("Enter 'Y' or 'N':       ")
    if errorcount == 'Y' or errorcount == 'y':
        file.write('\nBit Error Count is all 0 for all 8 channels.')
    else:
        file.write('\nBit Error Count is non-zero for some channels after reset.')
        col = raw_input("Enter the column numbers which have non-zero error counts:       ")
        file.write('\nColumns which have non-zero error counts: ' + col)
        errorratei = raw_input("Enter the RX bit error count of columns you entered above in the same order: ")
        file.write('\nBit Error Count of problematic Channels respectively: ' + errorratei)
        file.write('\n\n**GTX Test Overall Status: Fail**')
        file.close()
        return gtxFail(username,board_sn,board_vn,board_md,testStatus)
    print "Wait until the bit count ratio go down to the order of 1E-14."
    raw_input("Press Enter to continue:      ")
    print "Do you succeed in achieving count ratios on the order of 1E-14?"
    ratio = raw_input("Enter 'Y' or 'N':        ")
    if ratio != 'Y' and ratio != 'y':
        file.write('\n\nBit error count ratio fails to decrease over time.')
        col = raw_input("Enter the column numbers of which error rates do not fall on order of 10E-13:       ")
        file.write('\nColumns whose error rates do not fall on order of 1E-14: ' + col)
        errorratei = raw_input("Enter the bit error rate of columns you entered above in the same order: ")
        file.write('\nBit Error Rate of problematic Channels respectively: ' + errorratei)
        file.write('\n\n**GTX Test Overall Status: Fail**')
        file.close()
        return gtxFail(username,board_sn,board_vn,board_md,testStatus)
    else:
        file.write('\n\nBit error count falls to order 1E-14 over time.')
    
    print "\nIf there are any special concerns regarding the board for this test, please describe them below. If none, enter 'None'. "
    comments = raw_input("Enter your comments:  ")
    file.write('\n\nComments: ' + comments)

    print "Has everything in this test gone smoothly?"
    check = raw_input("Enter ('Y' or 'N'):  ")
    if check == 'Y' or check == 'y':
        file.write('\n\n**GTX Test Overall Status: Pass**')
        file.close()
        testStatus[10] = True
    else:
        file.write('\n\n**GTX Test Overall Status: Fail**')
        print "Please describe why below."
        failure = raw_input("Enter your comments:       ")
        file.write('\nComments:         ' + failure)
        file.close()
        testStatus[10] = False
        return gtxFail(username,board_sn,board_vn,board_md,testStatus)

    return testStatus