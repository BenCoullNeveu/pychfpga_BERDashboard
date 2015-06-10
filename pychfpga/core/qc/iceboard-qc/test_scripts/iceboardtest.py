'''
Script for launching ICEboard quality control testing suite.
To use just run as 'python iceboardtest.py' or 'run iceboardtest.py' in ipython.
'''
from numpy import *
import os
import inspectiontest
import resistancetest
import DCtest
import programPLLtest
import programARMtest
import programFPGA
import FPGAtest
import GTXtest
import rampTest
import testFail
import traceback
from statusReport import EMPTY_TEST_STATUS
from edit_boardfile import new_file_header

def starttest():
    '''Starts a testing session: Prompts for information about the board to be tested, creates a file to store results in
    if doesn't already exist, then proceeds to testing.
    '''

    print "***********************************************"
    print "| I C E B O A R D  T E S T I N G  S C R I P T |"
    print "***********************************************"

    # Import parameters from config
    import yaml
    if os.path.isfile('config.yaml'):
        config = yaml.load(open('config.yaml'))
        username = config['user']
        board_md = config['board_md']
        res_dir = config['results_directory']
    else:
        print "Did not find config.yaml file. Will use default values from config_example.yaml.\n"
        config = yaml.load(open('config_example.yaml'))
        username = config['user']
        board_md = config['board_md']
        res_dir = config['results_directory']

    #Pass/Fail status of tests. This list will be passed from method to method.
    testStatus = EMPTY_TEST_STATUS()

    print "Welcome fellow CHIME member to the Iceboard testing script!"
    print "We'll need some information from you... Please enter everything as prompted below:"
    print "What is your name? (if left blank, will use config.yaml entry)"
    uname_input = raw_input("Enter:	")
    if not uname_input.strip() == '':
        username = uname_input
    print "What is the serial number of the board? (e.g. 0009) Please be CONSISTENT in your file naming!!"
    board_sn = raw_input("Enter:	")
    print "What is the revision of this board? (e.g. Rev1)"
    board_vn = raw_input("Enter:	")
    fname = os.path.join(res_dir, 'board' + board_sn + '.txt')
    if not os.path.isfile(fname): # Only necessary if file doesn't already exist
        #print "What is the model of this board?" Moved this to 'config.yaml'
        #board_md = raw_input("Enter:	")
        print "What is the PCB serial number of this board? It is printed on the top-left edge of the board, above " \
              "the 'FMC B' label and components. (e.g. 04-14-017)"
        # TODO: Is this still the case on the new boards (PCB serial location)?
        pcb_sn = raw_input("Enter:\t")
    else:
        print "\nA file already exists for this board. Will record following results there."
        pcb_sn = None # This is only needed if a new file is being created
    
    if not os.path.isfile(fname):
        new_file_header(fname, board_sn, board_md, board_vn, pcb_sn) # Create new file with header

    raw_input("Press enter when ready to begin testing...    ")
    choosetest(username,board_sn,board_vn,board_md,testStatus)

    
def choosetest(username=None,board_sn=None,board_vn=None,board_md=None,testStatus = EMPTY_TEST_STATUS()):
    print "Select the test you wish to proceed to.\n"
    print "1. Inspection test"
    print "2. Resistance test."
    print "3. DC test."
    print "4. Programming PLL."
    print "5. Programming the ARM."
    print "6. Programming the FPGA."
    print "7. FPGA test."
    print "8. GTX test."
    print "9. Ramp test.\n"
    choiceMade = False
    while not choiceMade:
        try:
            choice = int(raw_input(""))
            if choice <= 9 and choice >=1:
                choiceMade = True
            else:
                print "Input not within range. Please try again."
        except Exception, e:
            print "What you entered was not expected."
            print e
            print "Please try again"

    try:
        if choice == 1:
            inspectiontest.inspectiontest(username,board_sn,board_vn,board_md,testStatus)
        elif choice == 2:
            resistancetest.resistancetest(username,board_sn,board_vn,board_md,testStatus)
        elif choice == 3:
            DCtest.DCtest(username,board_sn,board_vn,board_md,testStatus)
        elif choice == 4:
            programPLLtest.programPLLtest(username,board_sn,board_vn,board_md,testStatus)
        elif choice == 5:
            programARMtest.programARMtest(username,board_sn,board_vn,board_md,testStatus)
        elif choice == 6:
            programFPGA.programFPGA(username,board_sn,board_vn,board_md,testStatus)
        elif choice == 7:
            FPGAtest.FPGAtest(username,board_sn,board_vn,board_md, testStatus)
        elif choice == 8:
            GTXtest.GTXtest(username,board_sn,board_vn,board_md,testStatus)
        elif choice == 9:
            rampTest.rampTest(username, board_sn, board_vn, board_md, testStatus)
    except:
            print("\nAn exception occurred. Trace below:\n")
            traceback.print_exc()
            testFail.genericFail(username,board_sn,board_vn,board_md,testStatus)

if __name__ == "__main__":
    starttest()