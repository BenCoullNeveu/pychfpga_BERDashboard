
"""Performs tests on the full crate setup."""
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

class MGK7BP16CrateTests(unittest.TestCase):
   
    def setUp(self):
        """ Prepare the test for execution.

        Here, we load the yaml configuration file.
        """
        xr.header('Setting-up')
        self.cfg = util.load_config(TEST_CONFIG_FILE)
        cfg = self.cfg.crate_tests.setup  # config options pertaining to setup


    def bitErrorRate_test(self):
        
        # Useful shortcuts
        cfg = self.cfg.crate_tests.bitErrorRate_test

        ca = FPGAArray(icecrates = 11, prog = 1, open = 1)

        xr.header('Beginn Testing')
        try:
            result = ca.get_ber(period = cfg.period, print_ = False)
            bp_rate = True
            qsfp_rate = True
            #gpu_rate = True
            bad_lanes = []

            for key in result.keys():
                if key[0] == 'BP':
                    if result[key] >= cfg.bp_limit:
                        bp_rate = False
                        bad_lanes.append((key, result[key]))
                elif key[0] == 'BP_QSFP':
                    if result[key] >= cfg.qsfp_limit:
                        qsfp_rate = False
                        bad_lanes.append((key, result[key]))
                elif key[0] == 'GPU':
                    #if result[key] >= cfg.gpu_limit:
                    #    gpu_rate = False
                    #    bad_lanes.append((key, result[key]))
                    del result[key]
            
            xr.header('Test-Results')
            keys = result.keys()
            keys.sort()
            for key in keys:
                print key, result[key]

            assert bp_rate, 'Bit Error Rate for Backplane lanes too high!'
            assert qsfp_rate, 'Bit Error Rate for QSFP lanes too high!'
            #assert gpu_rate, 'Bit Error Rate for GPU lanes too high!'

        finally:
            xr.save_data(result)


    def reset_test(self):
        cfg = self.cfg.crate_tests.reset_test
        
        ca = FPGAArray(icecrates = 11, prog = 1, open = 1)

        result = NameSpace()
        result.res = {}
        result.onoff = {}
        result.res.off = [False]*16
        result.res.on = [False]*16
        result.onoff.off = [False]*16
        result.onoff.on = [False]*16

        xr.header('Beginn Reset Test')
        try:
            for i in range(0, 16, 2):
                print "Resetting arm on board %d." % (i+2)
                ca.ib[i].reset_arm_on_slot(i+2)
                result.res.off[i+1] = not ca.ib[i+1].ping()
            
            print "Waiting ..." 
            time.sleep(cfg.sleep_time/2)
            
            for i in range(0, 16, 2):
                result.res.on[i+1] = ca.ib[i+1].ping()
            
            for i in range(1, 16, 2):
                print "Resetting arm on board %d." % i
                ca.ib[i].reset_arm_on_slot(i)
                result.res.off[i-1] = not ca.ib[i-1].ping()
            
            print "Waiting ..."
            time.sleep(cfg.sleep_time/2)
            
            for i in range(1, 16, 2):
                result.res.on[i-1] = ca.ib[i-1].ping()

            xr.header('Test-Results')
            for i in range(0, len(result.res.off)):
                print result.res.off[i] , result.res.on[i]
            
            for i in range(0, len(result.res.off)):
                assert result.res.off[i], "Iceboard(s) did not turn off properly!"
                assert result.res.on[i], "Iceboard(s) did not turn on properly!"

        finally:
            xr.save_data(result.res)

        xr.header('Beginn ON/OFF Test')
        try:
            for i in range(0, 16, 2):
                print "Turning board %d off." % (i+2)
                ca.ib[i].set_power_on_slot(i+2, False)
                result.onoff.off[i+1] = not ca.ib[i+1].ping()
                print "Turning board %d on." % (i+2)
                ca.ib[i].set_power_on_slot(i+2, True)
            
            print "Waiting ..." 
            time.sleep(cfg.sleep_time)
            
            for i in range(0, 16, 2):
                result.onoff.on[i+1] = ca.ib[i+1].ping()
            
            for i in range(1, 16, 2):
                print "Turning board %d off." % i
                ca.ib[i].set_power_on_slot(i, False)
                result.onoff.off[i-1] = not ca.ib[i-1].ping()
                print "Turning board %d on." % i
                ca.ib[i].set_power_on_slot(i, True)
            
            print "Waiting ..."
            time.sleep(cfg.sleep_time)
            
            for i in range(1, 16, 2):
                result.onoff.on[i-1] = ca.ib[i-1].ping()

            xr.header('Test-Results')
            for i in range(0, len(result.onoff.off)):
                print result.onoff.off[i] , result.onoff.on[i]
            
            for i in range(0, len(result.onoff.off)):
                assert result.onoff.off[i], "Iceboard(s) did not turn off properly!"
                assert result.onoff.on[i], "Iceboard(s) did not turn on properly!"

        finally:
            xr.save_data(result.onoff)


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

            if qsfpslots[i-1]:
                print "QSFP module manufactured by: "+ base64.b64decode(ca.ib[0]._bp_qsfp_eeprom_read_base64(i, 148, 16)).strip() + ". Serial number: " + base64.b64decode(ca.ib[0]._bp_qsfp_eeprom_read_base64(i, 196, 16)).strip() + "."

        for i in range(0, 16):
            assert qsfpslots[i], "Not all connectors were detected!"

        assert input_yes_no('Were the manufactor and serial number correctly read? Answer Y/N\n'), "User detected error in QSFP readout!"


    def sensor_test(self):
        cfg = self.cfg.crate_tests.sensor_test

        ca = FPGAArray(icecrates = 11, prog = 1, open = 1)
        ca.set_sync_method('local_soft_trigger')
        ca.set_operational_mode('shuffle256', frames_per_packet=2)

        xr.header('Test-Results')

        voltage = ca.ib[0].get_backplane_voltage()
        current = ca.ib[0].get_backplane_current()
        bpTemp1 = ca.ib[0].get_backplane_temperature(ca.ib[0].TEMPERATURE_SENSOR.BP_SLOT1)
        bpTemp16 = ca.ib[0].get_backplane_temperature(ca.ib[0].TEMPERATURE_SENSOR.BP_SLOT16)
        #extTemp1 = ca.ib[0].get_backplane_temperature(ca.ib[0].TEMPERATURE_SENSOR.BP_SLOT1_EXTERN)
        #extTemp16 = ca.ib[0].get_backplane_temperature(ca.ib[0].TEMPERATURE_SENSOR.BP_SLOT16_EXTERN)
        serial = ca.ib[0]._get_backplane_serial()

        print 'backplane voltage = ' + repr(voltage)
        print 'backplane current = ' + repr(current)
        print 'backplane slot1 temp = ' + repr(bpTemp1)
        print 'backplane slot16 temp = ' + repr(bpTemp16)
        #print 'backplane slot1 extern temp = ' + repr(extTemp1)
        #print 'backplane slot16 extern temp = ' + repr(extTemp16)
        print 'backplane serial number = ' + repr(serial)
        ca.print_iceboard_temperatures()

        assert input_yes_no('\nIs the above data sensical? Answer Y/N\n'), "User detected error in sensory data!"
        assert (voltage >= cfg.voltage_limits[0] and voltage <= cfg.voltage_limits[1]), "Voltage out of bounds!"
        assert (current >= cfg.current_limits[0] and current <= cfg.current_limits[1]), "Current out of bounds!"
        for i in range(0, 16):
            assert ca.ib[i].SYSMON.temperature() <= cfg.temp_limit, "FPGA temperature too high!"


if __name__ == '__main__':
    """ Run the test in this file."""
    import mgk7bp16_crate_tests
    reload(mgk7bp16_crate_tests)
    v = util.run_tests(TEST_CONFIG_FILE)
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging