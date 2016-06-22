
""" Performs tests on the full crate setup.
"""
import unittest
import time
import numpy as np
import matplotlib.pyplot as plt
import base64
import util
import datetime
from util import NameSpace
import textwrap

util.add_paths('../..')  # needed to find icecore
from icecore import XReport as xr
from icecore.tests.xreport import test_report
from icecore.hw import ipmi_fru

util.add_paths('../../..')  # needed to find fpga_array
util.add_paths('../../../..') # needed to find pychfpga
from fpga_array import FPGAArray

TEST_CONFIG_FILE = './mgk7bp16_test_config.yaml'

def wrap(obj, width=80):
    return textwrap.fill(str(obj), width)

def input(message):
    key = xr.input(message).lower()
    assert not key.startswith('q'), 'Test was interrupted by user'
    return key

def input_yes_no(message, additional_answers=[]):
    while True:
        key = input(message)
        if key.startswith('y'):
            return True
        elif key.startswith('n'):
            return False
        elif key in additional_answers:
            return key
        print 'Wrong answer. Try again'

class MGK7BP16CrateTests(unittest.TestCase):  #
    """
    Perform dummy test on a full crate.
    """
    def setUp(self):
        """ Prepare the test for execution.

        Here, we grab the command line arguments and parse them.
        """
        xr.header('Setting-up')
        self.cfg = util.load_config(TEST_CONFIG_FILE)
        cfg = self.cfg.crate_tests.setup  # config options pertaining to setup


    def bitErrorRate_test(self):
        
        # Useful shortcuts
        cfg = self.cfg.crate_tests.bitErrorRate_test

        print '--------------------------------'
        print '--Starting Bit Error Rate Test--'
        print '--------------------------------'

        try:
            ca = FPGAArray(icecrates = 11, prog = 1, open = 1)
            result = ca.get_ber(print_ = False)

            for key in result.keys():
                if key[0] == 'BP':
                    print result[key]

        finally:
            xr.save_data(result)



if __name__ == '__main__':
    """ Run the test in this file."""
    import mgk7bp16_crate_tests
    reload(mgk7bp16_crate_tests)
    v = util.run_tests(TEST_CONFIG_FILE)
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging