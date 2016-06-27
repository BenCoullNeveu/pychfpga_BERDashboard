
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
        print '\n TEST TEST TEST \n'
        self.cfg = util.load_config(TEST_CONFIG_FILE)
        cfg = self.cfg.crate_tests.setup  # config options pertaining to setup


    def bitErrorRate_test(self):
        
        # Useful shortcuts
        cfg = self.cfg.crate_tests.bitErrorRate_test

        ca = FPGAArray(icecrates = 11, prog = 1, open = 1)

        xr.header('Test-Results')
        print '--------------------------------'
        print '--Starting Bit Error Rate Test--'
        print '--------------------------------'

        try:
            result = ca.get_ber(print_ = False)
            bp_rate = True
            gpu_rate = True
            bad_lanes = []

            for key in result.keys():
                if key[0] == 'BP':
                    if result[key] >= cfg.bp_limit:
                        bp_rate = False
                        bad_lanes.append((key, result[key]))
                else:
                    if result[key] >= cfg.gpu_limit:
                        gpu_rate = False
                        bad_lanes.append((key, result[key]))

            assert bp_rate, 'Bit Error Rate for Backplane lanes too high!'
            assert gpu_rate, 'Bit Error Rate for GPU lanes too high!'

        finally:
            bad_lanes.sort()
            print '\n'
            for item in bad_lanes:
                print item
            xr.save_data(result)

    def reset_test(self):
        cfg = self.cfg.crate_tests.reset_test
        
        ca = FPGAArray(icecrates = 11, prog = 1, open = 1)
        
        xr.header('Beginn Testing')

        result = NameSpace()
        result.on = [False]
        result.off = [False]

        try:
            for i in range(2, 17):
                print "Turning board %d off." % i
                ca.ib[0].set_power_on_slot(i, False)
                result.off.append(not ca.ib[i-1].ping())
                print "Turning board %d on." % i
                ca.ib[0].set_power_on_slot(i, True)
            
            print "Waiting ..." 
            time.sleep(cfg.sleep_time)
            
            for i in range(2, 17):
                result.on.append(ca.ib[i-1].ping())
            
            i = result.on.index(True)
            print "Turning board 1 off."
            ca.ib[i].set_power_on_slot(1, False)
            result.off[0] = not ca.ib[0].ping()
            print "Turning board 1 on."
            ca.ib[i].set_power_on_slot(1, True)
            print "Waiting ..."
            time.sleep(cfg.sleep_time)
            result.on[0] = ca.ib[0].ping()

            xr.header('Test-Results')
            for i in range(0, len(result.off)):
                print result.off[i] , result.on[i]
            
            for i in range(0, len(result.off)):
                assert result.off[i], "Iceboard(s) did not turn off properly!"
                assert result.on[i], "Iceboard(s) did not turn on properly!"

        finally:
            xr.save_data(result)

    def qsfp_test(self):
        cfg = self.cfg.crate_tests.qsfp_test
        
        ca = FPGAArray(icecrates = 11, prog = 1, open = 1)
        
        xr.header('Test-Results')

        qsfpslots = [0]*16
        for i in range(1, 17):
            if ca.ib[0].is_bp_qsfp_present(i): 
                print "Backplane QSFP module present on slot " + repr(i)
                qsfpslots[i-1] = 1
            else:
                print "Backplane QSFP module NOT present on slot " + repr(i)

        for i in range(0, 16):
            assert qsfpslots[i], "Not all connectors were detected!"

    def sensor_test(self):
        cfg = self.cfg.crate_tests.sensor_test

        ca = FPGAArray(icecrates = 11, prog = 1, open = 1)
        ca.set_sync_method('local_soft_trigger')
        ca.set_operational_mode('shuffle256', frames_per_packet=2)

        xr.header('Test-Results')

        voltage = ca.ib[0].get_backplane_voltage()
        current = ca.ib[0].get_backplane_current()
        print 'backplane voltage = ' + repr(voltage)
        print 'backplane current = ' + repr(current)

        assert (voltage >= cfg.voltage_limits[0] and voltage <= cfg.voltage_limits[1]), "Voltage out of bounds!"
        assert (current >= cfg.current_limits[0] and current <= cfg.current_limits[1]), "Current out of bounds!"

        ca.print_iceboard_temperatures()

        for i in range(0, 16):
            assert ca.ib[i].SYSMON.temperature() <= cfg.temp_limit, "FPGA temperature too high!"



if __name__ == '__main__':
    """ Run the test in this file."""
    import mgk7bp16_crate_tests
    reload(mgk7bp16_crate_tests)
    v = util.run_tests(TEST_CONFIG_FILE)
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging