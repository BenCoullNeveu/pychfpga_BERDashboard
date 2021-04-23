
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

util.add_paths('../pychfpga/core')  # needed to find icecore
from icecore import XReport as xr
from icecore.tests.xreport import test_report
from icecore.hw import ipmi_fru

util.add_paths('../pychfpga')  # needed to find fpga_array
util.add_paths('../') # needed to find pychfpga
from fpga_array import FPGAArray

TEST_CONFIG_FILE = './MGK7BP16/mgk7bp16_test_config.yaml'

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

        ca = FPGAArray(icecrates = xr.params.serial, prog = self.cfg.debug.force_fpga_prog, open = 1)

        while True:
            irigb_source = raw_input('Indicate the source for the IRIG-B signal, 1 for bp_time, 2 for bp_trig, or 3 for both. ')
            if irigb_source != '1' and irigb_source != '2' and time_source != '3':
                print 'Wrong input, try again!'
            else:
                break

        xr.header('Test-Results')
        try:
            result = NameSpace()

            # Create a set of unique slot numbers
            slots = set(ca.ib.slot)

            # Print the list of boards
            print 'Populated Slots:'
            for (slot, ib) in ca.ic[0].slot.items():
                print 'Slot %02i: IceBoard SN%s' % (slot, ib.serial)

            print '\nReference clock Frequencies:'
            clock = []
            for ib in ca.ib:
                raw_clk_freq = ib.FreqCtr.read_frequency('RAW_CLK')
                print 'Slot %02i: %.6f MHz' % (ib.slot, raw_clk_freq)
                clock.append(raw_clk_freq)

            if irigb_source == '1' or irigb_source == '3':
                print '\nTime Readout:'
                result.time = []
                ca.ib.set_irigb_source('bp_time')
                print ca.ib.get_irigb_time()
                for ib in ca.ib:
                    result.time.append(ib.get_irigb_time(format = 'nano'))

            if irigb_source == '2' or irigb_source == '3':
                print '\nTrig Readout:'
                result.trig = []
                ca.ib.set_irigb_source('bp_trig')
                time.sleep(3)
                print ca.ib.get_irigb_time()
                for ib in ca.ib:
                    result.trig.append(ib.get_irigb_time(format = 'nano'))

            assert len(slots) == 16, 'Problem with slot detection.'
            assert min(clock) > cfg.limits[0] and max(clock) < cfg.limits[1], 'Clock out of bounds!'
            if irigb_source == '1' or irigb_source == '3':
                assert max(np.diff(result.time).tolist()) < cfg.max_time_diff, 'Difference in time signal too great between boards!'
            if irigb_source == '2' or irigb_source == '3':
                assert max(np.diff(result.trig).tolist()) < cfg.max_time_diff, 'Difference in trig signal too great between boards!'

        finally:
            xr.save_data(result)
            xr.params.test_locals = locals()


    def sensor_test(self):
        cfg = self.cfg.crate_tests.sensor_test

        ca = FPGAArray(icecrates = xr.params.serial, prog = self.cfg.debug.force_fpga_prog, open = 1)

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

        ca = FPGAArray(icecrates = xr.params.serial, prog = self.cfg.debug.force_fpga_prog, open = 1)

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

        ca = FPGAArray(icecrates = xr.params.serial, prog = self.cfg.debug.force_fpga_prog, open = 1)

        result = NameSpace()
        result.res = {}
        result.onoff = {}
        result.res.off = [False]*16
        result.res.on = [False]*16
        result.onoff.off = [False]*16
        result.onoff.on = [False]*16

        xr.header('Begin Reset Test')
        try:
            for i in range(0, 16, 2):
                print "Resetting arm on board %d." % (i+2)
                ca.ib[i].reset_arm_on_slot(i+2)
                result.res.off[i+1] = not ca.ib[i+1].ping()

            print "Waiting ..."
            time.sleep(cfg.arm_sleep_time)

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

        xr.header('Begin ON/OFF Test')

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

        while True:
            numberOfCrates = raw_input('Do you want to test on 1 or 2 crates (QSFP links require 2 crates, unless connected in a loop)?\nEnter "1" or "2" for respective choices. ')
            if numberOfCrates == '1':
                serials = xr.params.serial
                break

            elif numberOfCrates == '2':
                crate2 = raw_input('What is the serial number of the second crate you want to use for this test? ')
                serials = [xr.params.serial, crate2]
                break

            else:
                print 'Wrong input!'

        ca = FPGAArray(icecrates = serials, prog = self.cfg.debug.force_fpga_prog, open = 1)

        xr.header('Begin Testing')
        bad_lanes = []
        result = []
        try:
            # for ib in ca.ib:
            #     ib.set_irigb_source('bp_time')

            # if numberOfCrates == '1':
            #     ca.init_corner_turn(mode = 'shuffle256')
            # else:
            #     ca.init_corner_turn(mode = 'shuffle512')
            
            link_map = {}
            link_map.update(ca.get_backplane_pcb_link_map())
            link_map.update(ca.get_backplane_qsfp_link_map())
            link_map = {link: gtxes for link, gtxes in link_map.items() if (('int' not in gtxes) and (None not in gtxes))}

            result = ca.get_ber(link_list = link_map, period = cfg.period, print_ = True, tx_init_power=2, tx_power=6, tx_qsfp_power=14, minerrors_toprint=0)
            bp_rate = True
            qsfp_rate = True
            #gpu_rate = True
            bad_lanes = []

            for key in result.keys():
                if key[0] == 'pcb':
                    if result[key] >= cfg.bp_limit:
                        bp_rate = False
                        bad_lanes.append((key, result[key]))
                elif key[0] == 'qsfp':
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
                print key, round(result[key], 3)

            bad_lanes.sort()

            assert bp_rate, 'Bit Error Rate for Backplane lanes too high!'
            assert qsfp_rate, 'Bit Error Rate for QSFP lanes too high!'
            #assert gpu_rate, 'Bit Error Rate for GPU lanes too high!'

        finally:
            print 'Bad Links:'
            for item in bad_lanes:
                print item
            xr.save_data(result)
            xr.params.test_locals = locals()

    def mezzRamp_test(self):
        cfg = self.cfg.crate_tests.mezzRamp_test

        ca = FPGAArray(icecrates = xr.params.serial, prog = self.cfg.debug.force_fpga_prog, open = 1)

        result = NameSpace()  # test result container
        board = 0

        xr.header('Test-Results')
        try:
            for ib in ca.ib:
                result[board] = NameSpace()
                result[board].data = []
                result[board].ramp_ok = []

                for mezz in ib.mezzanine.values():
                    print 'initializing mezzanine...'
                    mezz.init()

                print 'Computing ADC delays for board serial number: ' + ib.serial
                ib.set_adc_delays(source='default', compute_delays=1, save_delays=False, check_sync_delays=True, check_adc_delays=20, verbose=0, retry=5)

                for mezz in ib.mezzanine.values():
                    
                    delay_table= ib.get_adc_delays()
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
                    ib.stop_data_capture()

                    result[board].data.append(data)
                    plt.figure(1)

                    ideal_ramp = (np.arange(2048) - 128).astype(np.int8)

                    ramp_ok = []
                    for ch in range(8):
                        plt.clf()
                        plt.plot(data[ch])
                        xr.insert_plot('Ramp capture for %s SN%s CHANNEL %02i' % (xr.params.model, xr.params.serial, ch))
                        ok = np.all(data[ch] == ideal_ramp)
                        ramp_ok.append(ok)
                        if ok:
                            print 'Channel %02i: OK' % (ch+1)
                        else:
                            print 'Channel %02i: ERROR!' % (ch+1)

                    result[board].ramp_ok.append(ramp_ok)

                board += 1

            for board in range(16):
                assert all(result[board].ramp_ok), 'One or more channels have ramp errors'

        finally:
            xr.params.test_locals = locals()  # store local variables for interactive debugging
            #receiver.close()
            xr.save_data(result)



# Iceboard missing tests:
# QC017.1 Full load FPGA temperature  Check FPGA operation temp on full load (detects power supplies and heatsink issues)
# QC017.2 Heat sink visual check  *** Add: Visual check: heat sink installed, proper model, orientation, with posts. No obvious contact with surrounding components. Record compliance.
# QC017.3 Stiffener and board flatness visual check   *** Add: Visual check: Stiffner installed, board is reasonably flat.
# QC017.4 ARM Shield check    *** Add
# QC010.2.1   Power LEDs  *** Add: Check that all power LEDs are turned ON
# QC011.2     *** Add: Check that Bot PLL lock (LEDs) when using crystal source
# QC011.3     *** Add: Check that Both PLL lock (check LED) when using SMA.
# QC016.2.1       *** Add: check that SYNC stops clock and that RESET restores ADC registers and IO Expanders registers
# QC016.2.2       *** Add: Test SPI communication with ADC to confirm SPI bus connectivity to Mezz
# QC016.2.3       *** Add: Check PLL_LOCK line to see if PLL is locked (requires firmware change)
# QC016.1.1       *** Add: Backplane I2C Comms through FPGA & ARM to test I2C matrix circuitry and connectivity to backplane EEPROM
# QC016.1.2       *** Add: Access Motherboard I2C devices via FPGA on SMPS bus (Temperature or power), GPIO bus (Write & readback reg)
# QC016.1.3       *** Add: Confirm Mezz can be powered on and off (IO Extender & power switch test), test Power Good and PRSNT Line
# QC016.1.4       *** Add: Validate that SFP Present and FAULT line can be read (tests SFP & IO_Extender connectivity)
# QC016.1.5       *** Add: Check M2C reference clock frequencies (both).
# QC016.1.6       *** Add: I2C communications to mezzanines EEPROM


if __name__ == '__main__':
    """ Run the test in this file."""
    import mgk7bp16_crate_tests
    reload(mgk7bp16_crate_tests)
    v = util.run_tests(TEST_CONFIG_FILE)
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging
