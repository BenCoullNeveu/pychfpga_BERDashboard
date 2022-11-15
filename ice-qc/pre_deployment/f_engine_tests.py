#!/usr/bin/env python

"""
Tests to be run in preparation for deployment of a full F-Engine, including
a fully-populated crate, switch, power supply, GPS, etc.
"""

import asyncio

# Pypi packages
import pytest
import numpy as np

# External private packages
from wtl.namespace import NameSpace
from wtl.pytest_xreport import xr
import pychfpga
from pychfpga import fpga_array
import labpy

TEST_CONFIG_FILE = './pre_deployment/test_config.yaml'

class TestUtils:
    """ Some utility methods common to all tests.
    """

    def open_instrument(self, name):
        instr_params = self.cfg.instruments[name].copy()
        class_name = instr_params.pop('labpy_object')
        return labpy.open_instrument(class_name, **instr_params)

    def open_ps(self, name='ps', voltage=None, current=None):
        """ Opens a power supply and configures it

        The `voltage` and `current` to be programmed can be specified. If `None`, the global values from
        the config file in ``f_engine_tests.global_settings`` will be used.
        """
        # open power supply instrument if it is in the list of instruments and if we don't force manual operation
        if 'ps' in self.cfg.instruments and not self.cfg.get('manual_ps', False):
            self.ps = self.open_instrument(name)
        else:
            self.ps = None

        # initialize power supply if we have one
        if self.ps:
            voltage = voltage if voltage is not None else self.cfg.f_engine_tests.global_settings.ps_voltage
            current = current if current is not None else self.cfg.f_engine_tests.global_settings.ps_current
            self.ps.set_output(state=False) #Ensuring power on N5764A is off
            self.ps.clear() #Clearing any previous protection
            self.ps.set_voltage(voltage=voltage) #Setting voltage, power still off
            self.ps.set_current_limit(current=current, ocp=True) #Setting current limit and turning on ocp feature
        return self.ps

    def crate_init(self, reset_power = True):
        """
        Run fpga_array, initializing the crate. Recover ca object. Power is reset by default.
        """
        # if reset_power:
        #     # Check if power supply on:
        #     if self.ps:
        #         self.ps.set_output(state=False) #Ensuring power on N5764A is off

        #     # Turn power supply back on:
        #     instr_params = self.cfg.instruments['ps'].copy()
        #     ip_addr = instr_params.pop('adapter')[5:]
        #     print(f'Turning on power supply at {ip_addr}...')
        #     self.ps = self.open_ps()

        try:
            fpga_array_params = self.cfg.f_engine_tests.global_settings.fpga_array_params
            ca = fpga_array.FPGAArray(hwm = fpga_array_params.hwm,
                stderr_log_level = fpga_array_params.stderr_log_level,
                prog = fpga_array_params.prog,
                mode = fpga_array_params.mode,
                sync_method = fpga_array_params.sync_method,
                mdns_timeout = fpga_array_params.mdns_timeout)

            assert len(ca) == 16 # need a better assertion

        finally:
            return ca

class TestPreDeploymentCrate(TestUtils):
    """
    List of tests:

    0?) Visual inspection?

    1) Check board initialization:
        - all 16 boards found in hwm
        - all FPGAs programmed
        - crate must sync
    2) Check backplane errors (requires above to pass to be able to run)
        - initialize crate
        - iterate through output of await ca.print_shuffle_status(verbose = 1)
        - maybe save the verbose = 2 one as well?
    3) Force IRIG-B syncs
        - initialize crate
        - config-defined number of sync tries
    4) Check ADC clocks
        - initialize crate
        - iterate through all motherboards and mezzanines, check that
          clocks are 200 MHz +/- tolerance (set by integration time)
    5) Force ADC sync delay calculations
        - intialize crate
        - visual inspection
    6) Check ADC eye diagrams
        - initialize crate
        - visual inspection
    """

    @pytest.fixture(autouse=True)
    def setup(self, xr):
        """ Prepare the test for execution. This fixture is executed automatically before each test.
        """
        xr.header('Setting-up')
        self.cfg = xr.config  # get the test config NameSpace
        # pre-define instrument variable. We'll load them only as needed by the tests.
        self.ps = None

        yield  # pass control to the test and return

        # turn off power supply
        if self.ps:
            self.ps.set_output(state=False) #Ensuring power on N5764A is off

    def test_init(self, xr):
        """
        QC001: Crate initialization test: ensure crate properly intializes

        Procedure:

          - Start the crate init test on the computer
          - Power up crate
          - If init ok, test passed:
            - all 16 boards found in hwm
            - all FPGAs programmed
            - crate must sync

        """

        xr.header('Crate Initialization Test')
        cfg = self.cfg.f_engine_tests.crate_init # not used
        test_results = NameSpace()

        # Initialize the crate:
        passed = False
        try:
            # input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
            self.ca = self.crate_init()
            # If we made it to this point, FPGAs programmed, all boards present in hwm
            # and crate has synced (see test_config.yaml - parameters passed to FPGAArray
            # force all these to be present to return self.ca
            passed = True
        except Exception as e:
            print(f'Crate did not properly initialize. Error message is:')
            print(e)
        finally:
            test_results.passed = passed
            xr.save_data(test_results)


    def test_bperr(self, xr):
        """
        QC002: Backplane error test: check if there are errors in print_shuffle_status()

        Procedure:

            - Start the bperr test on the computer
            - Power up crate
            - After initializing crate, check backplane errors using
                await ca.print_shuffle_status()

        """

        xr.header('Backplane Error Test')
        cfg = self.cfg.f_engine_tests.backplane_err # not needed
        test_results = NameSpace()

        passed = False
        bp_errs = []

        try:
            test_results.bp_errs = NameSpace() # How do I make sure the bp_errs list gets saved?
            # Initialize the crate
            xr.input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
            self.ca = self.crate_init()

            while True:
                xr.input('Press ENTER to print shuffle status results. (Q:Exit) ')
                asyncio.run(self.ca.print_shuffle_status())
                errs_present = xr.input('Are there any backplane errors?. Note that QSFP errors are expected if not connected to X-Engine. Answer Y/N. (Q:Exit) ')

                if errs_present == 'y':
                    while True:
                        finished = xr.input('Press ENTER to write the error. If finished, answer F. (Q:Exit) ')
                        if finished == 'f':
                            break
                        lane = xr.input('Enter the location of the error, e.g. BP PCB Rx L11. (Q:Exit) ') # i.e. left-most column of print_shuffle_status
                        slot_serial = xr.input('Enter the slot and serial number of the error, e.g. Slot 6, SN0332. (Q:Exit) ') # slot + serial
                        bp_errs.append((lane, slot_serial))

                print_again = xr.input('Would you like to reprint the shuffle status results? Answer Y/N. (Q:Exit) ')

                if print_again == 'n':
                    break

            assert not bp_errs, f'Backplane errors present on: {bp_errs}'
            passed = True

        finally:
            test_results.passed = passed
            xr.save_data(test_results)


    def test_sync(self, xr):
        """
        QC003: Sync/IRIG-B test: stress test of crate sync using IRIG-B

        Procedure:

            - Start the sync test on the computer
            - Power up crate
            - After initializing crate, run self.ca.sync() in a loop, and
              only pass if it's able to successfully sync N times (e.g. N = 100)

        """

        xr.header('Crate Sync Test')
        cfg = self.cfg.f_engine_tests.sync_test # not needed
        test_results = NameSpace()

        passed = False
        n_syncs = cfg.n_syncs

        # Initialize the crate
        try:
            # xr.input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
            self.ca = self.crate_init()
            counter = 0
            for n in range(n_syncs):
                print(f'Sync #{n+1}')
                self.ca.sync()
                counter += 1
            assert not counter == n_syncs
            passed = True
        finally:
            test_results.passed = passed
            xr.save_data(test_results)


    def test_adc_clocks(self, xr):
        """
        QC004: ADC clock test: ensure all ADCs get the correct clocks on every channel.

        Procedure:

          - Start the ADC clock test on the computer
          - Power up crate
          - Iterate through all clocks on all mezzanines on all motherboards, check that they
            are 200 MHz +/- some tolerance set in the config.

        """

        xr.header('ADC Clocks Test')
        cfg = self.cfg.f_engine_tests.clock_test
        test_results = NameSpace()

        integration_period = cfg.integration_period
        n_clock_checks = cfg.n_clock_checks

        # The FreqCtr reports values as e.g. 200.000 MHz. If count_time = 0.001 for example, 200e6/0.001 = 200,000
        expected_diffs = {-2/integration_period, 0.0, 2/integration_period} # fix this
        failed_clocks = []

        passed = False
        try:
            # Initialize the crate:
            self.ca = self.crate_init()

            # Iterate through each motherboard. Form a set of unique values of the
            # difference between the measured clock and the expected 200 MHz. To pass,
            # there should only be two values in the set: 0 and 200 MHz/count_time (which
            # is the maximum error, resulting from a missed rising edge) --> is this correct?

            for i in self.ca.ib:
                for clock in range(15):
                    print(f'{i}, ADC_CLK{clock}')
                    diffs = set(i.FreqCtr.read_frequency(f'ADC_CLK{clock}', integration_period) - 200e6 for _ in range(n_clock_checks))
                    # If diffs is not a subset of expected_diffs, i.e. it contains an unexpected value, then append to failed_clocks
                    if not diffs.issubset(expected_diffs):
                        failed_clocks.append([f'{i}', f'ADC_CLK{clock}', diffs])

            assert not failed_clocks, f'ADC clock errors present on: {failed_clocks}'
            passed = True

        finally:
            test_results.passed = passed
            xr.save_data(test_results)

    def test_sync_delays(self, xr):
        """
        QC005: Sync delays test: ensure ADC sync delays have no errors or issues

        Procedure:

          - Start the sync delays test on the computer
          - Power up crate
          - Iterate through each motherboard, and visually inspect the sync delays.

        """

        xr.header('Sync Delays Test')
        cfg = self.cfg.f_engine_tests.sync_delay_test
        test_results = NameSpace()

        sync_delay_errors = []

        # Initialize the crate:
        passed = False
        try:
            # input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
            self.ca = self.crate_init()

            for i in self.ca.ib:
                while True:
                    xr.input(f'Press ENTER to compute sync delays for {i}. (Q:Exit) ')
                    i.compute_sync_delays()
                    errs_present = xr.input('Are there any sync delay errors? Answer Y/N. (Q:Exit) ')

                    if errs_present == 'y':
                        sync_delay_errors.append(i)

                    print_again = xr.input('Would you like to see the sync delays again? Answer Y/N. (Q:Exit) ')

                    if print_again == 'n':
                        break

            assert not sync_delay_errors, f'Sync delay errors present on: {sync_delay_errors}'
            passed = True

        finally:
            test_results.passed = passed
            xr.save_data(test_results)

    def test_adc_eye(self, xr):
        """
        QC006: ADC eye test: check ADC eye diagrams to ensure stability.

        Procedure:

          - Start the adc eye test on the computer
          - Power up crate
          - Inspect the adc eye diagrams.

        """

        xr.header('ADC Eye Test')
        cfg = self.cfg.f_engine_tests.adc_eye_test
        n_checks = cfg.n_checks
        n_refs = cfg.n_refs
        n_fails_accept = cfg.n_fails_accept # number of allowable fails. if exceeded, board/channel pair fails.
        test_results = NameSpace()

        unstable_channels = []

        # Initialize the crate:
        passed = False
        try:
            # input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
            self.ca = self.crate_init()

            for i in self.ca.ib:
                for channel in range(16):
                    print('==========================================================')
                    print(f'Checking ADC eye diagrams for {i}, ADC channel {channel}')

                    ref_nz_idx = [] # 'reference non-zero indices', checks where non-zero values are in eye diagram

                    # Gather non-zero indices for a few reference eye diagrams. n_refs should be large enough
                    # to capture any small jitters. If there really are weird, large jitters, they should move
                    # around enough that they're not capture by the reference diagrams. If it's just small jitters,
                    # they should be captured by the reference diagrams.

                    for n in range(n_refs):
                        ref_d = i.capture_adc_eye_diagram(channels=[channel])[0] # sample reference diagram
                        nz_idx = np.where(ref_d != 0) # non-zero indices
                        for j in range(len(nz_idx[0])):
                            pair = [nz_idx[0][j], nz_idx[1][j]] # generates index pairs
                            if pair not in ref_nz_idx:
                                ref_nz_idx.append(pair) # if pair not already in ref_nz_idx, add it

                    ref_nz_idx = set(tuple(x) for x in ref_nz_idx) # change ref_nz_idx to a set so we can use issubset

                    # Now iterate through n_checks more diagrams to check stability
                    fails_counter = 0
                    for n in range(n_checks):
                        d = i.capture_adc_eye_diagram(channels=[channel])[0] # grab a diagram
                        nz_idx = np.where(d != 0)
                        pairs = []
                        for j in range(len(nz_idx[0])):
                            pairs.append([nz_idx[0][j], nz_idx[1][j]]) # add every pair to pairs
                        pairs = set(tuple(x) for x in pairs) # change pairs to set

                        # If pairs is not a subset of ref_nz_idx, i.e. the channel is unstable,
                        # add the motherboard index and channel number to unstable_channels if not already present
                        if not pairs.issubset(ref_nz_idx):
                            print(f'Fail on diagram {n+1}')
                            fails_counter += 1
                            if fails_counter > n_fails_accept and if not [f'{i}', f'Channel {channel}'] in unstable_channels:
                                # If accetpable fails is exceeded, and board/channel pair not already in unstable checks, append it.
                                unstable_channels.append([f'{i}', f'Channel {channel}'])

            assert not unstable_channels, f'Unstable channels: {unstable_channels}'
            passed = True

        finally:
            test_results.passed = passed
            xr.save_data(test_results)



if __name__ == '__main__':
    """ Run the test in this file."""
    v = TestMenu(TEST_CONFIG_FILE).run()
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging