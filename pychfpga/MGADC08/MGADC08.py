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
import time
import struct
# import zlib
# import ast

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref

from pychfpga.core.icecore import FMCMezzanine
from pychfpga.core.icecore import FMCMezzanineHandler

# Import mezzanine-specific modules
import ADC
import IOExpander
import ADC_PLL
import AmbTemp
import MGT_PLL

class MGADC08_base(FMCMezzanine):
    handler_name = 'MGADC08_Handler'
    __ipmi_part_number__ = 'MGADC08'  # Must match part number in IPMI data. Used for auto-discovery.

    __tablename__ = 'mgadc08'
    __mapper_args__ = {'polymorphic_identity': 'MGADC08'}
    _pk = Column(Integer, ForeignKey('fmc_mezzanines._pk'), primary_key=True)

    """ Implements object that exposes the MGADC08 FMC ADC board hardware ressources"""

class MGADC08_Handler(FMCMezzanineHandler):

    __handler_for__ = MGADC08_base

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

    def __init__(self, **kwargs):
        super(MGADC08_Handler, self).__init__(**kwargs)
        # self.type = 'mgadc08'
        self._board_is_present = None
        self.sampling_frequency = None
        self.reference_frequency = None
        # self._board_info = {}

        #self.check_FMC_presence()
        self.verbose = False
        self._board_is_present = True

        self.motherboard = self.iceboard
        self.fmc_number = self.mezzanine-1

        if self.is_present():
            # self._board_info = self.load_board_info()
            self.logger.debug('  - ADC')
            self.ADC = ADC.ADC_base(adc_board=self)
            self.logger.debug('  - IOExpander')
            self.IOExpander = IOExpander.IOExpander_base(adc_board=self)
            self.logger.debug('  - ADC_PLL')
            self.ADC_PLL = ADC_PLL.ADC_PLL_base(adc_board=self)
            self.logger.debug('  - AmbTemp')
            self.AmbTemp = AmbTemp.AmbTemp_base(adc_board=self)
            # self.logger.debug('  - MGT_PLL')
            # self.MGT_PLL = MGT_PLL.MGT_PLL_base(self.motherboard)

    ############################################
    # Methods available to the board hardware
    #############################################

    def spi_read_write(self, device, data,  type=np.uint8, verbose=None):
        """
        Provides read/write function to access the SPI devices on this board.
        """
        if verbose is None:
            verbose = self.verbose
        return self.iceboard.SPI.read_write(device=device, data=data, type=type, port=self.mezzanine-1, verbose=verbose)

    def adc_reset(self):
        self.iceboard.GPIO.pulse_bit(('ADC0_RESET', 'ADC1_RESET')[self.mezzanine-1])

    def adc_sync(self):
        self.iceboard.REFCLK.local_sync()

    def set_power(self, state):
        self.iceboard.set_mezzanine_power(bool(state), self.mezzanine)

    def check_FMC_presence(self, verbose=0):
        """ Checks if the FMC is present"""
        # self.logger.debug("Attempting to read FMC eeprom to determine board presence")
        # data = self.eeprom.read(0, length=1, noerror=True, verbose=verbose)
        # self.logger.debug("FMC eeprom returned the value: %i", data[0])
        self._board_is_present = self.iceboard._get_mezzanine_type(self.mezzanine) == self.polymorphic_identity
        #self.logger.info("is the ADC board present: %i" % self._board_is_present)

    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self._board_is_present

    def init(self, sampling_frequency=800e6, reference_frequency=10e6, verbose=0):
        """ Initializes the FMC board modules"""

        if self.is_present():
            self.sampling_frequency = sampling_frequency
            self.reference_frequency = reference_frequency
            self.logger.info('Initializing MGADC08 on Mezzanine %i' % self.mezzanine)
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
        self.logger.info('Status of MGADC08 ADC board on Mezzanine %i' % self.mezzanine)
        self.logger.info('  ADC board is %s' % (('not present', 'present')[bool(self.is_present())]))
        if self.is_present():
            self.AmbTemp.status()
            self.IOExpander.status()
            self.ADC_PLL.status()
            self.ADC.status()
