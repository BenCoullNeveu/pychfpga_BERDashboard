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
        the config file in ``motherboard_tests.global_settings`` will be
        used.
        """
        # open power supply instrument if it is in the list of instruments and if we don't force manual operation
        if 'ps' in self.cfg.instruments and not self.cfg.get('manual_ps', False):
            self.ps = self.open_instruments(name)
        else:
            self.ps = None

        # initialize power supply if we have one
        if self.ps:
            voltage = voltage if voltage is not None else self.cfg.motherboard_tests.global_settings.ps_voltage
            current = current if current is not None else self.cfg.motherboard_tests.global_settings.ps_current
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
        #     ip_addr = instr_params.pop('ip_addr')
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

            return ca

        except Exception as e:
            print('Error initializing crate. Error message is:')
            print(e)


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
    4) Force ADC delay calculations
        - intialize crate
        - will need to think about how best to test this since the output is more visual...
          maybe just print each output and force user to answer an input asking if it passed?
    5) ...? will fill in later, moving on to start writing functions
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
            input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
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

        xr.header('Crate Initialization Test')
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

        xr.header('Crate Initialization Test')
        cfg = self.cfg.f_engine_tests.sync_test # not needed
        test_results = NameSpace()

        passed = False
        N = 100 # make this part of test_config.yaml

        # Initialize the crate
        try:
            xr.input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
            self.ca = self.crate_init()
            counter = 0
            for n in range(N):
                print(f'Sync #{n+1}')
                self.ca.sync()
                counter += 1
            if counter == N:
                passed = True
        finally:
            test_results.passed = passed
            xr.save_data(test_results)


    def test_adc_clock(self, xr):
        """
        QC004: ADC clock test: ensure all ADCs get the correct clocks on every channel.

        Procedure:

          - Start the ADC clock test on the computer
          - Power up crate
          - Iterate through each motherboard, and visually inspect the ADC delays.

        """

        # xr.header('Crate Initialization Test')
        # cfg = self.cfg.f_engine_tests.delay_test # not used
        # test_results = NameSpace()

        # # Initialize the crate:
        # passed = False
        # try:
        #     input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
        #     self.ca = self.crate_init()

    def test_adc_delays(self, xr):
        """
        QC005: ADC delays test: ensure ADC delays have no errors or issues

        Procedure:

          - Start the ADC delays test on the computer
          - Power up crate
          - Iterate through each motherboard, and visually inspect the ADC delays.

        """

        # xr.header('Crate Initialization Test')
        # cfg = self.cfg.f_engine_tests.delay_test # not used
        # test_results = NameSpace()

        # # Initialize the crate:
        # passed = False
        # try:
        #     input('Turn on the power supply. Press ENTER to continue. (Q:Exit) ')
        #     self.ca = self.crate_init()



if __name__ == '__main__':
    """ Run the test in this file."""
    v = TestMenu(TEST_CONFIG_FILE).run()
    locals().update(v) # bring local variables from the test runner into the current namespace for easier debugging