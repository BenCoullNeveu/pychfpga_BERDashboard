import time as tm
import os
from other_stuff import date_format, read_config, get_repo
from statusReport import EMPTY_TEST_STATUS
from testFail import gtxFail
from fpgaFun import gtx_ber

# Tolerance for bit error rate pass
BER_TOL = 1e-10

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
        print "Please run the 'starttest()' function from 'iceboardtest.py' to create one."
        print "Aborting test.\n"
        return testStatus

    file = open(fname, 'a')
    file.write('\n\n\n\nGTX Test\n')
    file.write('----------\n')
    date_str=date_format(tm.localtime())
    file.write('| Date : ' + date_str + '\n')
    file.write('| Tester: ' + username + '\n')
    repo = get_repo()
    file.write("| On branch '" + str(repo.active_branch) + "' with commit " + str(repo.commit('HEAD')) + \
           " of " + os.path.split(os.path.dirname(repo.git_dir))[-1] + ".\n\n")
    file.flush()

    # Import parameters from config
    if username is None:
        username = config['user']
    ch_acq_path = config['ch_acq_root']

    print "For this test, we will need a one-slot backplane and a QSFP cable."

    print "\nSet up the board in the one-slot backplane and connect the two Ethernet cables, one to the inside port " +\
          "near the ARM, and the other to the FPGA SFP adapter."
    print "Now connect the two QSFP ports on the board (next to the FPGA SFP adapter port) to one-another using the " +\
          "QSFP cable."
    print "There should also be a fan over the FPGA heatsink."

    raw_input("\nPress any key to begin the GTX test, once the board has booted:    ")

    # Run bit error test with these parameters
    links = None  # For all links. Could also be 'gpu' or 'bp'
    power = 10  # This is the default value in chime_array.py
    period = 1  # In seconds
    ber = gtx_ber(board_sn, ch_acq_path=ch_acq_path, links=links, period=period, power=power)

    # Write results to file
    test_results = {}
    file.write("| Used one-slot backplane:  {}\n".format(ber.keys()[0][1][0]))
    file.write("| Bit error rate test period (s):  {:.2f}\n\n".format(period))
    file.write("=" * 24 + " " + "=" * 18 + " " + "=" * 6 + "\n")
    file.write("{0: <24} {1: <18} {2: <6}\n".format("  Link", "  Error rate", " "))
    file.write("=" * 24 + " " + "=" * 18 + " " + "=" * 6 + "\n")
    for link in sorted(ber.keys()):
        link_name = "{0} {1} {2}".format(link[0], link[1][1:], link[2][1:])
        result = ber[link] < BER_TOL
        test_results.update({link: result})
        file.write("{0: <24} {1: >18.2e} {2: >6}\n".format(link_name, ber[link],"PASS" if result else "FAIL"))
    file.write("=" * 24 + " " + "=" * 18 + " " + "=" * 6 + "\n\n")
    file.flush()

    # Check for failure
    gtx_pass = True
    for key in test_results:
        if not test_results[key]:
            gtx_pass = False
            print "\nFailure (error rate > {0:.2e}) on link {1}".format(BER_TOL, key)
            print "    With error rate: {:.2e}".format(ber[key])

    # Write final verdict and close
    print "\nIf there are any special concerns regarding the board for this test, please describe them below. " +\
          "If none, enter 'None'. "
    comments = raw_input("Enter your comments:  ")
    file.write('\n\nComments: ' + comments)

    if gtx_pass:
        print "Has everything in this test gone smoothly?"
        check = raw_input("Enter ('Y' or 'N'):  ").strip().lower()
        if check == 'y':
            file.write('\n\n**GTX Test Overall Status: Pass**\n\n')
            file.close()
            testStatus[10] = True
            return testStatus
        else:
            print "Please describe why below."
            failure = raw_input("Enter your comments:       ")
            file.write('\nComments:         ' + failure)
    file.write('\n\n**GTX Test Overall Status: Fail**\n\n')
    file.close()
    testStatus[10] = False
    return gtxFail(username,board_sn,board_vn,board_md,testStatus)
