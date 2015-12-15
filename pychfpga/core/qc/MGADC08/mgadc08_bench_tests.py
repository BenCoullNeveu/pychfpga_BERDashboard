
""" Performs bench tests of the MGADC08 CHIME ADC Mezzanine board.
"""
import unittest
import time
import numpy as np
import base64
import util
from util import NameSpace

util.add_paths('../..')  # needed to find icecore
from icecore import XReport as xr
util.add_paths('../../..')  # needed to find fpga_array
from fpga_array import FPGAArray


TEST_CONFIG_FILE = './mgadc08_test_config.yaml'


class MGADC08BenchTests(unittest.TestCase): #
    """
    Perform impedance & power tests on the MGADC08 Mezzanine.
    """
    def setUp(self):
        """ Prepare the test for execution.

        Here, we grab the command line arguments and parse them.
        """
        xr.header('Setting-up')
        self.cfg = util.load_config(TEST_CONFIG_FILE)
        cfg = self.cfg.bench_tests.setup  # config options pertaining to setup
        self.instr = util.open_instruments(self.cfg.instruments, cfg.instruments)  # open only instruments listed in cfg.instruments

        self.instr.dmm.set_beeper(True)
        self.instr.dmm.display('Ready for','MGADC08 tests')

        # Disable power supply outputs
        self.instr.ps12v.output_enable(0)
        self.instr.ps3v3_2v5.output_enable(0)

        # Set-up power supply voltages and current limits
        self.rails = NameSpace()
        for rail_name, rail in cfg.rails.items():
            ps = self.instr[rail.ps]
            print 'Configuring rail %s to %.3fV@%.3fA' % (rail_name, rail.voltage, rail.current_limit)
            ps.set_voltage(rail.output, rail.voltage)
            ps.set_current(rail.output, rail.current_limit)
            self.rails[rail_name] = NameSpace(ps=ps, output=rail.output)

    def input(self, message):
        key = xr.input(message).lower()
        assert not key.startswith('q'), 'Test was interrupted by user'
        return key

    def input_yes_no(self, message):
        while True:
            key = self.input(message)
            if key.startswith('y'):
                return True
            elif key.startswith('n'):
                return False
            print 'Wrong answer. Try again'


    def impedance_test(self):
        """
        QC001: Power supply Impedance: checks for power supply shorts

        Procedure:
          - Start the impedance test on the computer
          - Type in serial number of tested board.
          - Clip ground probe of multimeter on specified grounding point
          - Touch each test points indicated by the software and press ENTER
          - Test points:
               - J7-2 (12V)
               - J7-3 (2.5V)
               - J7-4 (3.3V)
               - 1V8 test point
               - 3V3 test point
          - Total time: 20 s

        We pass/fail the test only after all measurements are done so we can gather more debugging info.
        """
        # Useful shortcuts
        cfg = self.cfg.bench_tests.impedance
        dmm = self.instr.dmm  # Multimeter
        pss = [self.instr.ps12v, self.instr.ps3v3_2v5]  # Both power supplies
        test_results = NameSpace()



        for ps in pss:  # Turn off both power supplies, just to be sure
            ps.output_enable(0)

        xr.header('Test results')

        failed_test_points = []
        passed = False
        try:
            test_results.test_points = NameSpace()
            for tp_name, limits in NameSpace(cfg.test_points).items():
                dmm.display('','Measure %s' % tp_name)
                dmm.select_resistance_measurement()
                while True:
                    dmm.local()
                    self.input("Apply probe to test point '%s' and press ENTER to measure (Q=Exit):" % tp_name)
                    if limits.delay:
                        dmm.get_resistance()  # make a dummy measurement
                        time.sleep(limits.delay)
                    result = dmm.get_resistance()
                    if result <= cfg.max_impedance: break
                    print 'Impedance is too high. Is the probe really connected?'
                dmm.beep()
                passed = result > limits.zmin
                test_results.test_points[tp_name] = NameSpace(Z=result, passed=passed)
                if not passed:
                    failed_test_points.append(tp_name)
                    dmm.beep()
                    dmm.beep()
                print '   %s : %.0f ohms (must be more than %.0f ohms) ==> %s' % (tp_name, result, limits.zmin, xr.pass_fail(passed))
            assert not len(failed_test_points), 'Low impedance on %s' % ','.join(failed_test_points)
            passed = True
        finally:
            test_results.passed = passed
            dmm.display(xr.pass_fail(passed),'Impedance tests')
            dmm.local()
            xr.save_data(test_results)


    def smoke_test(self):
        """
        QC002: Smoke test: tests currents and voltages

            - Connect power cable to mezzanine
            - Start current tests on the computer.
            - The computer will set-up the power-supply, enable the outputs, and measure currents. The power will turn off immediately if there is any problem.
            - The computer will ask if the 3.3V LED (DS7) is ON. Answer.
            - Touch multimeter probe on the test points indicated by the software and press ENTER
            - Test points:
                - 1V8 test point
                - 3V3 test point
            - Total time: 15 s
        """
        # Useful shortcuts
        cfg = self.cfg.bench_tests.smoke_test
        dmm = self.instr.dmm  # Multimeter
        pss = [self.instr.ps12v, self.instr.ps3v3_2v5]  # Both power supplies


        test_results = NameSpace()  # container for the test results to be saved in the test report
        xr.header('Test results')

        for ps in pss:  # Turn off both power supplies, just to be sure
            ps.output_enable(0)

        passed = False
        try:
            key = xr.input("Connect power cable to MGADC08 and press ENTER to measure current (Q=Exit):")
            assert not key.lower().startswith('q'), 'Test was interrupted by user'

            for ps in pss: # Turn on both power supplies
                ps.output_enable(1)

            # Measure currents on the power supplies
            test_results.rails = NameSpace()  # Namespace to store all rail results
            for rail_name, limits in cfg.rails.items():
                rail = self.rails[rail_name]
                V = rail.ps.get_voltage(rail.output)
                I = rail.ps.get_current(rail.output)
                print 'Rail %s: %.3fV@%.3fA,  limits = %s' % (rail_name, V, I, limits)
                test_results.rails[rail_name] = NameSpace(V=V, I=I)  # Namespace to store this rail results
                print test_results.rails[rail_name]
                print test_results
                if V < limits.vmin or V > limits.vmax or I < limits.imin or I > limits.imax:
                    # stop immediately as soon as we fail one of these tests. We can't go further anyway. This will powewr off the supplies
                    assert False, 'Inadequate current or voltage on rail %s' % rail_name

            dmm.display('','Check power LED')
            power_led_state = self.input_yes_no('Is the power LED turned ON?')
            test_results.power_led_state = power_led_state
            assert power_led_state, 'Power LED is not tuned ON. Something is wrong. Aborting.'

            # Measure voltages on test points
            failed_rails = []
            test_results.test_points = NameSpace()  # Namespace to store all rail results
            for tp_name, limits in NameSpace(cfg.test_points).items(): # Convert list to (ordered) namespace. limits will also be a NameSpace.
                dmm.display('','Measure %s' % tp_name)
                dmm.select_voltage_measurement()
                while True:
                    dmm.local() # Allow the multimeter to update its display in real time
                    self.input("Apply probe to test point '%s' and press ENTER to measure (Q=Exit):" % tp_name)
                    result = dmm.get_dc_voltage()
                    if result >= cfg.min_test_voltage: break
                    print 'Voltage too low. Is the probe well connected? Try again.'
                dmm.beep()
                passed = not (result < limits.vmin or result > limits.vmax)
                test_results.test_points[tp_name] = NameSpace(V=result, passed=passed)
                if not passed:
                    failed_rails.append(tp_name)
                    print '   %s : %.3g volts (must be between %.3f - %.3f) ==> %s' % (tp_name, result, limits.vmin, limits.vmax, xr.pass_fail(passed))
                    dmm.beep()
                    dmm.beep()

            assert not len(failed_rails), 'Inadequate voltage or current on %s' % ','.join(failed_rails)
            passed = True
        finally: # Always execute this, whatever happens
            for ps in pss:  # Turn off both power supplies
                ps.output_enable(0)
            test_results.passed = passed
            dmm.display(xr.pass_fail(passed), 'Power-up tests')
            dmm.local()
            xr.save_data(test_results)

class MGADC08CarrierTests(): #

    def setUp(self):
        # xr.summary.pass
        xr.header('Setting-up')
        self.cfg = util.load_config(xr.params.config_file)
        self.model = xr.params.model
        self.serial = xr.params.serial
        cfg = self.cfg.carrier_tests.setup  # config options pertaining to setup
        self.slot = cfg.fmc_slot
        self.instr = util.open_instruments(self.cfg.instruments, cfg.instruments)  # open only instruments listed in cfg.instruments
        self.instr.dmm.display('carrier tests', '%s SN%s' % (self.model, self.serial))

    def eeprom_test(self):
        """
        Start EEPROM test on the computer.

        - The software connects to the IceBoard
        - The test will automatically check:
            - Detects the mezzanine presence (PRSNT Line)
            - Detect the Mezzanine EEPROM, and configures it with the serial number.
        No user intervention is needed
        Total time: 3 s
        """
        xr.header('Testing...')

        tr = NameSpace()
        cfg = self.cfg.carrier_tests
        passed = False
        try:

            a = FPGAArray(**cfg.setup.fpga_array)
            ib = a.ib[0]
            print 'Testing with %r' % ib
            # Check if PRSNT line is help low
            tr.is_mezzanine_present = ib.is_mezzanine_present(self.slot)
            print 'Mezzanine is present: %s' % bool(tr.is_mezzanine_present)
            assert tr.is_mezzanine_present, 'Mezzanine was not detected on FMC slot %i' % self.slot

            # Attempt to access the EEPROM
            eeprom = [ib.hw._fmca_eeprom, ib.hw._fmcb_eeprom][self.slot-1]
            tr.is_eeprom_i2c_responding = eeprom.is_present()
            print 'EEPROM is responding: %s' % bool(tr.is_eeprom_i2c_responding)
            assert tr.is_eeprom_i2c_responding, 'The Mezzanine EEPROM did not respond to I2C addressing.'

            # Attempt to read 32 characters of the EEPROM contents
            try:
                tr.eeprom_contents_from_fpga = ib.hw.read_mezzanine_eeprom(self.slot, 0, 32).decode('utf-8', 'ignore')
                print 'EEPROM content read by FPGA is: %s' % tr.eeprom_contents_from_fpga
            except:
                assert False, 'Error while attempting to read the EEPROM contents using the FPGA'

            try:
                tr.eeprom_contents_from_arm = base64.decodestring(ib._mezzanine_eeprom_read_base64(self.slot)).decode('utf-8', 'ignore')
                print 'EEPROM content read by ARM is: %s' % tr.eeprom_contents_from_arm
            except:
                assert False, 'Error while attempting to read the EEPROM contents using the ARM'

            print 'Discovering Mezzanine'
            ib.discover_mezzanines()
            mezz = ib.mezzanine[self.slot]
            print 'Mezzanine is %r:' % mezz
            assert mezz, 'Mezzanine was not discovered'

            passed = True
        finally:
            tr.passed = passed
            xr.save_data(tr)
            self.instr.dmm.display(xr.pass_fail(passed), 'EEPROM tests')
            self.instr.dmm.local()


if __name__ == '__main__':
    """ Run the test in this file."""
    import mgadc08_bench_tests
    reload(mgadc08_bench_tests)
    v = util.run_tests(TEST_CONFIG_FILE)
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging