#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
MGADC08.py module
 Wrapper object for MGADC08 FMC ADC board

 History:
 2011-07-25 : JFC : Created
"""
# MGADC08 FMC ADC board device handlers
import logging
import numpy as np

import ADC
import IOExpander
import ADC_PLL
import AmbTemp
import BiasADC
import MGT_PLL
import FMC_EEPROM
from common import util

MODULE_LIST = (
    AmbTemp,
    ADC,
    IOExpander,
    ADC_PLL,
    BiasADC,
    MGT_PLL,
    FMC_EEPROM,
)

util.reload_modules(MODULE_LIST)

class MGADC08_base(object):
    """ Implements object that exposes the MGADC08 FMC ADC board hardware ressources"""

    # SPI port numbers specific to this board
    SPI_ADC0_ADDR      = 0    # ADC. R/W device. 8 bit address+RW, 16 bit data.
    SPI_ADC1_ADDR      = 1 # ADC. R/W device. 8 bit address+RW, 16 bit data.
    SPI_ADC0_TEMP_ADDR = 2 # ADC temperature sensor chip. Read only
    SPI_ADC1_TEMP_ADDR = 3 # ADC temperature sensor chip. Read only
    SPI_AMB_TEMP_ADDR  = 4 # Board temperature sensor chip. Read/Write device
    SPI_PLL1_ADDR      = (5, 1) # ADC PLL. The second element of the tuple indicates that we use the alternate timing 
    #SPI_ADC_BIAS_ADDR =5 # Bias measurement ADC.  Read/Write device # Not present on Rev2 board
    SPI_IO_EXP_ADDR    = 6 # IO Expander. Read/Write device
    SPI_PLL2_ADDR      = 7 # MGT PLL. Write only.

    _board_is_present = False # Will be checked later

    def __init__(self, system, fmc_number, fmc_name, verbose=0):
        self.fpga = system
        self.verbose = verbose
        self.fmc_number = fmc_number
        self.fmc_name = fmc_name
        self._board_is_present = None
        self.sampling_frequency = None
        self.reference_frequency = None
        self._board_info = {}

        self.logger = logging.getLogger(__name__)

        # provide access to the resources needed to access the ADC board hardware
        self.i2c = self.fpga.motherboard.i2c # I2C bus
        # self.spi = self.fpga.SPI # SPI bus

        self.logger.debug('  - FMC EEPROM')
        self.eeprom = FMC_EEPROM.FMC_EEPROM_base(self.i2c, self.fmc_name, verbose = verbose)
        self.eeprom.init()

        self.check_FMC_presence()

        if self.is_present():
            self.load_board_info()
            self.logger.debug('  - ADC')
            self.ADC = ADC.ADC_base(adc_board = self)
            self.logger.debug('  - IOExpander')
            self.IOExpander = IOExpander.IOExpander_base(adc_board = self)
            self.logger.debug('  - ADC_PLL')
            self.ADC_PLL = ADC_PLL.ADC_PLL_base(adc_board = self)
            self.logger.debug('  - AmbTemp')
            self.AmbTemp = AmbTemp.AmbTemp_base(adc_board = self)
            # self.logger.debug('  - MGT_PLL')
            # self.MGT_PLL = MGT_PLL.MGT_PLL_base(self.fpga)
            # self.logger.debug('  - BiasADC')
            # self.BiasADC = BiasADC.BiasADC_base(self.fpga)

    ############################################
    # Methods available to the board hardware
    #############################################

    def spi_read_write(self, device, data,  type=np.uint8, verbose=None):
        """
        Provides read/write function to access the SPI devices on this board. 
        """
        if verbose is None:
            verbose = self.verbose
        return self.fpga.SPI.read_write(device = device, data = data, type = type, port = self.fmc_number, verbose = verbose)

    def adc_reset(self):
        self.fpga.GPIO.pulse_bit(('ADC0_RESET', 'ADC1_RESET')[self.fmc_number])

    def adc_sync(self):
        self.fpga.REFCLK.local_sync()

    def set_power(self, state):
        self.fpga.motherboard.set_fmc_power(self.fmc_number, state)

    def check_FMC_presence(self, verbose=0):
        """ Checks if the FMC is present"""
        self.logger.debug("Attempting to read FMC eeprom to determine board presence")
        data = self.eeprom.read(0, length=1, noerror=True, verbose=verbose)
        self.logger.debug("FMC eeprom returned the value: %i", data[0])
        self._board_is_present = (data[0] == 13)
        #self.logger.info("is the ADC board present: %i" % self._board_is_present)

    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self._board_is_present

    def load_board_info(self):
        """ loads the info data block from the ADC board EEPROM into memory for future access. """
        self._board_info = {
            'Model': 'MGADC08',
            'Revision': 'Unknown',
            'SYNC delay': 0,
            'ADC delays': []
        }

    def init(self, sampling_frequency=800e6, reference_frequency=10e6, verbose=0):
        """ Initializes the FMC board modules"""

        if self.is_present():
            self.sampling_frequency = sampling_frequency
            self.reference_frequency = reference_frequency
            self.logger.info('Initializing MGADC08 on FMC%i' % self.fmc_number)
            self.logger.debug('  - AmbTemp')
            self.AmbTemp.init()

            self.logger.debug('  - IOExpander')
            self.IOExpander.init()

            self.logger.debug('  - ADC_PLL')
            self.ADC_PLL.init(fout=2*self.sampling_frequency/1e6, fref=self.reference_frequency/1e6, verbose=verbose)

            self.logger.debug('  - ADC')
            self.ADC.init()

    def status(self):
        """ Displays the status of the ADC board"""
        self.logger.info('Status of MGADC08 ADC board on FMC%i' % self.fmc_number)
        self.logger.info('  ADC board is %s' % (('not present', 'present')[bool(self.is_present())]))
        if self.is_present():
            self.eeprom.status()
            self.AmbTemp.status()
            self.IOExpander.status()
            self.ADC_PLL.status()
            self.ADC.status()
