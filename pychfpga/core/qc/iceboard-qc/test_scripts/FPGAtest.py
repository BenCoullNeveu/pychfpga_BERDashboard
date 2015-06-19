from numpy import *
import time as tm
import os
import iceboardtest
import traceback
import programFPGA
from other_stuff import date_format, read_config, get_repo
from statusReport import EMPTY_TEST_STATUS
from testFail import fpgaTestFail
import fpgaFun
# Use JF's Xreport
import sys
sys.path.append('../../../../../../icecore/python/tests/xreport')
from xreport import XReport as xr
import unittest
import argparse

def launch_unittest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
    ''' DOESNT WORK RIGHT NOW
        Launch the xreport test as if it was a traditional test, with the usual arguments
    :param username:
    :param board_sn:
    :param board_vn:
    :param board_md:
    :param testStatus:
    :return:
    '''
    args = ['xreport.py', '--xargs', '--username', username, '--board_sn', board_sn, '--board_vn', board_vn,
            '--board_md', board_md]
    xr.run_from_module(args)
    '''import logging.handlers
    log_handler = logging.handlers.SysLogHandler()
    logger = logging.getLogger('')
    logger.handlers = []  # Clear all existing handlers
    logger.setLevel(logging.DEBUG)
    logger.addHandler(log_handler)

    xr.XReport.instance_exists = False  # (debug) Bypass check to allow creation of a new instance of the plugin
    x = xr.XReport()  # Plugin is enabled by default. No need to use the option --with-xreport
    args = ['/Users/tristan/Documents/Cosmology_Lab/QC/icecore/python/tests/xreport/xreport.py', '/Users/tristan/Documents/Cosmology_Lab/QC/ch_acq/pychfpga/core/qc/iceboard-qc/test_scripts/FPGAtest.py', '--xargs', '--username', username, '--board_sn', board_sn, '--board_vn', board_vn,
            '--board_md', board_md]
    nose.run(addplugins=[x], argv=args)
    filename = 'fpgaTest_test'
    x.write_xml(filename + '.xml')
    x.write_rst(filename)
    return x'''

def FPGAtest(username=str,board_sn=str,board_vn=str,board_md=str,testStatus = EMPTY_TEST_STATUS()):
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

    # f = open(fname, 'a')
    f = fake_file()
    f.write('\n\nFPGA Test\n' +
          '------------\n')
    date_str=date_format(tm.localtime())
    repo = get_repo()
    f.write('| Date : ' + date_str + '\n' +
            '| Tester: ' + username + '\n' +
            "| On branch '" + str(repo.active_branch) + "' with commit " + str(repo.commit('HEAD')) +
            " of " + os.path.split(os.path.dirname(repo.git_dir))[-1] + ".\n\n")
    f.flush()

    # Import parameters from config
    if username == None:
        username = config['user']
    host_ip = config['host_ip']

    # Print and write some results to test out xreport
    print "Here is a statement describing where we are in the test, intended as stdout for the user."
    f.write('Running top_test on board: Pass\n\n')
    f.write('Probing FPGA temperature on board: Pass\n\n')

    f.write('ANT status output:\n\n' +
            '::\n\n' +
            'FreqCtr status output:\n\n' +
            '::\n\n' +

            '   System Frequencies:' +
            '\n      System clock frequency:      200.000 MHz' +
            '\n      CTRL_CLK frequency:        125.000 MHz' +
            '\n      Channelizer clock frequency: 200.000 MHz (Source= 1 (SYSTEM CLOCK))' +
            '\n      Correlator frequency:      250.000 MHz' +
            '\n      FMC0 Reference frequency:    10.000 MHz (ADC board not present)' +
            '\n      FMC1 Reference frequency:   (data not available)' +
            '\n      GPU link Ref clock frequency:     0.000 MHz' +
            '\n      GPU link data clock frequency:    0.000 MHz' +
            '\n      GPU link TX clock frequency:      0.000 MHz' +
            '\n      ADC0 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC1 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC2 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC3 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC4 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC5 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC6 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC7 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC8 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC9 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC10 clock frequency:        0.002 MHz (ADC board not present)' +
            '\n      ADC11 clock frequency:        4.682 MHz (ADC board not present)' +
            '\n      ADC12 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC13 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC14 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      ADC15 clock frequency:        0.000 MHz (ADC board not present)' +
            '\n      Resolution          :      0.000040 MHz' +
            '\n      Gate time           :    0.050 s' +
            '\n      Fan speed:                     0 RPM (resolution 300 RPM)\n')


    return testStatus

class fake_file():
    ''' This class is meant to allow the FPGAtest to be run in the traditional way, or as
        an xreport test, by replacing the file object used to write record results.
    '''
    def __init__(self):
        self.xr = xr
    def write(self, lines):
        # Write to xreport test
        self.xr.rst(lines)
    def flush(self):
        pass
    def close(self):
        pass

class TestFpga(unittest.TestCase):
    ''' FPGA test
    '''

    def setUp(self):
        parser = argparse.ArgumentParser(description=self.__doc__.split('\n')[0])  # description is the first line of the docstring
        parser.add_argument('--username', action='store', type=str, help="User performing QC.")
        parser.add_argument('--board_sn', action='store', type=str, help="Board serial number.")
        parser.add_argument('--board_md', action='store', type=str, help="Board model.")
        parser.add_argument('--board_vn', action='store', type=str, help="Board version number.")
        self.args = parser.parse_args(xr.xargs)
        # Write usual test header
        date_str = date_format(tm.localtime())
        repo = get_repo()
        xr.rst('| Date : ' + date_str + '\n' + \
               '| Tester: ' + self.args.username + '\n' + \
               "| On branch '" + str(repo.active_branch) + "' with commit " + str(repo.commit('HEAD')) + \
               " of " + os.path.split(os.path.dirname(repo.git_dir))[-1] + ".\n")

    def test_fpga(self):
        FPGAtest(self.args.username, self.args.board_sn, self.args.board_vn, self.args.board_md)