import iceboardtest
from statusReport import EMPTY_TEST_STATUS
'''
Add functions here to deal with failures in specific tests.
'''

def genericFail(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
    '''
    Generic fail process to be called at the end of specific fail functions.
    '''
    print("\nThe failure of this test has been recorded.")
    print("\nIMPORTANT: If you have any reason whatsoever to suspect it is unsafe to proceed with further testing,\nplease check with someone and fix the problem appropriately before continuing with the tests.")
    raw_input("Press Enter once you've read the warning:\t")
    print("\nIf you are confident it is safe to do so, would you like to carry on testing?")
    confirm = raw_input("Enter (y/n):\t")
    if confirm == 'Y' or confirm == 'y':
        iceboardtest.choosetest(username, board_sn, board_vn, board_md, testStatus)
    else:
        updateStatus.update(testStatus)
        sys.exit("Thank you for this testing process! The data has been saved. The testing program will now exit.")

def DCFail(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
    print("\nOne of the values you entered is not within the accpetable range.")
    print("Please POWER OFF the board NOW to prevent any damage.")
    print("\nIf one of the buck regulators is supplying the wrong voltage, suspect a faulty IC or solder joint.")
    raw_input("Press Enter to continue:\t")
    
    genericFail(username, board_sn, board_vn, board_md, testStatus)
    
def mtestFail(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
    print("\nFailed memory test.")
    print("Things to investigate: correct RAM IC mounted on board, soldering issues, possibility of PCB issues.")
    print("Tests that require the use of the ARM (FPGA tests) may fail if the memory is problematic.")