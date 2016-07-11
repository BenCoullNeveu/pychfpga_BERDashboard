
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


    def clock_test(self):
        cfg = self.cfg.crate_tests.clock_test

        ca = FPGAArray(icecrates = xr.params.serial, prog = 1, open = 1)

        xr.header('Test-Results')
        
        try:
            print 'Slot Numbers:'
            slots = set([])
            for slot in ca.ib.slot:
                print slot
                slots.add(slot)

            print '\nClock Frequencies:'
            clock = []
            for ib in ca.ib:
                print ib.FreqCtr.read_frequency('RAW_CLK')
                clock.append(ib.FreqCtr.read_frequency('RAW_CLK'))

            print '\nTime Readout:'
            time = []
            for ib in ca.ib:
                ib.set_irigb_source('bp_time')
                ib.get_irigb_source()
                print ib.get_irigb_time()
            for ib in ca.ib:
                time.append(ib.get_irigb_time(format = 'nano'))
            '''
            print '\nTrig Readout:'
            trig = []
            for ib in ca.ib:
                ib.set_irigb_source('bp_trig')
                ib.get_irigb_source()
                print ib.get_irigb_time()
            for ib in ca.ib:
                trig.append(ib.get_irigb_time(format = 'nano'))
            '''

            assert len(slots) == 16, 'Problem with slot association.'
            assert min(clock) > cfg.limits[0] and max(clock) < cfg.limits[1], 'Clock out of bounds!' 
            assert max(np.diff(time).tolist()) < cfg.max_time_diff, 'Difference in time signal too great between boards!'
            #assert max(np.diff(trig).tolist()) < cfg.max_time_diff, 'Difference in trig signal too great between boards!'
       
        finally:
            xr.params.test_locals = locals()


    def sensor_test(self):
        cfg = self.cfg.crate_tests.sensor_test

        ca = FPGAArray(icecrates = xr.params.serial, prog = 1, open = 1)
        ca.set_sync_method('local_soft_trigger')
        ca.set_operational_mode('shuffle256', frames_per_packet=2)

        xr.header('Test-Results')

        try:
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
            assert input_yes_no("Can you see all heartbeat led's blinking correctly? Answer Y?N\n"), "Heartbeat led's not functioning properly!"

        finally:
            xr.params.test_locals = locals()


    def qsfp_test(self):
        cfg = self.cfg.crate_tests.qsfp_test
        
        ca = FPGAArray(icecrates = xr.params.serial, prog = 1, open = 1)
        
        xr.header('Test-Results')

        try:
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

        finally:
            xr.params.test_locals = locals()


    def reset_test(self):
        cfg = self.cfg.crate_tests.reset_test
        
        ca = FPGAArray(icecrates = xr.params.serial, prog = 1, open = 1)

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
            time.sleep(cfg.arm_sleep_time/2)
            
            for i in range(0, 16, 2):
                result.res.on[i+1] = ca.ib[i+1].ping()
            
            for i in range(1, 16, 2):
                print "Resetting arm on board %d." % i
                ca.ib[i].reset_arm_on_slot(i)
                result.res.off[i-1] = not ca.ib[i-1].ping()
            
            print "Waiting ..."
            time.sleep(cfg.arm_sleep_time)
            
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
            xr.params.test_locals = locals()
        
        xr.header('Beginn ON/OFF Test')
        try:
            for i in range(0, 16, 2):
                print "Turning board %d off." % (i+2)
                ca.ib[i].set_power_on_slot(i+2, False)
                result.onoff.off[i+1] = not ca.ib[i+1].ping()
                print "Turning board %d on." % (i+2)
                ca.ib[i].set_power_on_slot(i+2, True)
            
            print "Waiting ..." 
            time.sleep(cfg.pow_sleep_time)
            
            for i in range(0, 16, 2):
                result.onoff.on[i+1] = ca.ib[i+1].ping()
            
            for i in range(1, 16, 2):
                print "Turning board %d off." % i
                ca.ib[i].set_power_on_slot(i, False)
                result.onoff.off[i-1] = not ca.ib[i-1].ping()
                print "Turning board %d on." % i
                ca.ib[i].set_power_on_slot(i, True)
            
            print "Waiting ..."
            time.sleep(cfg.pow_sleep_time)
            
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
            xr.params.test_locals = locals()


    def bitErrorRate_test(self):
        
        # Useful shortcuts
        cfg = self.cfg.crate_tests.bitErrorRate_test

        ca = FPGAArray(icecrates = xr.params.serial, prog = 1, open = 1)

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
            xr.params.test_locals = locals()


    def shuffle_test(self):
        cfg = self.cfg.crate_tests.shuffle_test

        while True:
            shuffleType = raw_input('Do you want to perform the 256 shuffle test (1 crate), or the 512 shuffle test (2 crates)?\nEnter "1" or "2" for respective choices. ')
            if shuffleType == '1':
                serials = xr.params.serial
                shuffle = 'shuffle256'
                break
        
            elif shuffleType == '2':
                crate2 = raw_input('What is the serial number of the second crate you want to use for this test? ')
                serials = [xr.params.serial, crate2]
                shuffle = 'shuffle512'
                break

            else:
                print 'Wrong input!'

        ca = FPGAArray(icecrates = serials, prog = 1, open = 1)
        
        xr.header('Start-Testing')
        ca.set_sync_method(method = 'distributed_time', source = cfg.time_source)
        time.sleep(2)
        for i,c in enumerate(ca.ic): c.handler.crate_number = i
        ca.set_operational_mode(shuffle, frames_per_packet=2)

        def searchErrDict(dic):
            if dic == {}:
                yield 0
            for key in dic.keys():
                if type(dic[key]) == type({}):
                    for value in searchErrDict(dic[key]):
                        yield value
                elif type(dic[key]) == type([]):
                    for item in dic[key]:
                        for value in searchErrDict(item):
                            yield value
                else:
                    yield 1
        
        xr.header('Test-Results')
        try:
            for i in range(cfg.repeat_test):
                ca.print_shuffle_status(verbose = 1)
                status = ca.get_shuffle_status()
                errors = sum(searchErrDict(status))   
                assert not errors, 'Found %d errors in data shuffle!' % errors

        finally:
            xr.save_data(status)
            xr.params.test_locals = locals()


    def set_adc_delays(self, ib):
        # Timing for ADCs. Calculate proper offsets for this board.
        trial = 0
        while True:
            delay_table, stuck_bits, bitposgood = ib.compute_adc_delay_offsets(channels=range(8))
            print "Computed delay table:"
            for ch, dt in delay_table.items():
                print '   Channel %02i: %s' % (ch, dt)

            print "Stuck bit flags"
            for ch, dt in stuck_bits.items():
                print '   Channel %02i: Stuck bits %s' % (ch, dt)

            print 'Bit positions validity'
            for ch, dt in bitposgood.items():
                print '   Channel %02i: Bit position good %s' % (ch, dt)

            stuck_ok = not any(stuck_bits.values())
            bitpos_ok = all(all(v) for v in bitposgood.values())
            if stuck_ok and bitpos_ok:
                break
            trial += 1
            assert trial < 6, 'Could not compute ADC delays'
            print 'Could not compute ADC delays. Retrying...'
        # Set ADC delays
        ib.set_adc_delays(delay_table)
        return delay_table


    def mezzRamp_test(self):
        cfg = self.cfg.crate_tests.mezzRamp_test

        ca = FPGAArray(icecrates = xr.params.serial, prog = 1, open = 1)

        results = NameSpace()  # test results container
        board = 0
        try:
            for ib in ca.ib:
                results[board] = NameSpace()
                results[board].data = []
                results[board].ramp_ok = []

                for mezz in ib.mezzanine.values():                
                    print 'initializing mezzanine...'
                    mezz.init()
                
                    print 'Computing ADC delays...'
                    delay_table = self.set_adc_delays(ib)
                
                    print 'Opening data receiver socket'
                    receiver = ib.get_data_receiver()

                    print 'Setting up ramp transmission...'
                    ib.set_adcdaq_mode('data')
                    ib.set_data_source('adc')
                    ib.set_adc_mode('ramp')
                    ib.start_data_capture(period=1, source='adc')
                
                    print 'Syncing...'
                    ib.sync()
                
                    print 'Getting data frames...'
                    receiver.read_frames(flush=1, frames=3)  # flush
                    data = receiver.read_frames(1)

                    results[board].data.append(data)
                    plt.figure(1)

                    ideal_ramp = (np.arange(2048) - 128).astype(np.int8)

                    ramp_ok = []
                    for ch in range(8):
                        plt.clf()
                        plt.plot(data[ch])
                        xr.insert_plot('Ramp capture for %s SN%s CHANNEL %02i' % (self.model, self.serial, ch))
                        ok = np.all(data[ch] == ideal_ramp)
                        ramp_ok.append(ok)
                        if ok:
                            print 'Channel %02i: OK' % (ch+1)
                        else:
                            print 'Channel %02i: ERROR!' % (ch+1)

                    results[board].ramp_ok.append(ramp_ok)
                
                board += 1

            for board in range(16):
                assert all(results[board].ramp_ok), 'One or more channels have ramp errors'

        finally:
            xr.params.test_locals = locals()  # store local variables for interactive debugging
            #receiver.close()
            #xr.save_data(results)


if __name__ == '__main__':
    """ Run the test in this file."""
    import mgk7bp16_crate_tests
    reload(mgk7bp16_crate_tests)
    v = util.run_tests(TEST_CONFIG_FILE)
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging