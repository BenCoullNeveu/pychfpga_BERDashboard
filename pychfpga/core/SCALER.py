#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
SCALER.py module 
 Implements interface to the SCALER

 History:
        2012-07-13 JFC: Created
"""
#import time
import struct
import numpy as np
from Module import Module_base, BitField

class SCALER_base(Module_base):
    """ Implements interface to the SCALER module within a procecessor pipeline"""
    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # Define Control registers
    RESET             = BitField(CONTROL, 0x00, 7, doc="Reset the SCALER.")
    BYPASS            = BitField(CONTROL, 0x00, 6, doc="Bypass the SCALER")
    FOUR_BITS         = BitField(CONTROL, 0x00, 5, doc="Enables 4-bit operation")
    SHIFT_LEFT        = BitField(CONTROL, 0x00, 0, width=5, doc="Number of bits to shift left the incoming data")
    USE_OFFSET_BINARY = BitField(CONTROL, 0x01, 6, doc="When '1', offset binary encoding is used.")
    USE_GAIN_TABLE    = BitField(CONTROL, 0x01, 5, doc="When '1', the gain tables are used to apply a bin-by-bin complex gain. Otherwise, the fixed complex gain is used for all bins.")
    READ_COEFF_BANK   = BitField(CONTROL, 0x01, 4, doc="Indicates which bank of gain coefficients is to be used by the scaler")
    WRITE_COEFF_BANK  = BitField(CONTROL, 0x01, 0, width=4, doc="Indicates which bank of gain coefficients is being written to")
    FIXED_GAIN_REAL   = BitField(CONTROL, 0x03, 0, width=16, doc="Real part of the fixed gain. Used when USE_GAIN_TABLE= '0'.")
    FIXED_GAIN_IMAG   = BitField(CONTROL, 0x05, 0, width=16, doc="Imaginary part of the fixed gain. Used when USE_GAIN_TABLE= '0'.")

    # Define Status registers

    def __init__(self, fpga_instance, base_address, instance_number):
         super(self.__class__, self).__init__(fpga_instance, base_address, instance_number)
        
    def reset(self):
        """ Resets the SCALER module """
        self.pulse_bit('RESET')

    def init(self):
        """ Initialize the SCALER module"""
        # Bypass the scaler by default if the FFT is not present
        if self.instance_number in self.fpga.LIST_OF_ANTENNAS_WITH_FFT:
          self.BYPASS = 0
        else:
          self.BYPASS = 1
        #self.BYPASS = 1
        #self.SHIFT_LEFT = 10
        self.SHIFT_LEFT = 31
        self.USE_GAIN_TABLE = 0
        self.USE_OFFSET_BINARY = 1
        self.set_fixed_gain(1)


    def set_fixed_gain(self, complex_gain):
        """
        Sets the scaler's fixed gain complex value.
        """

        if complex_gain.real<-32768 or complex_gain.real > 32767 or complex_gain.imag<-32768 or complex_gain.imag>32767:
            self.fpga.chFPGAException("Invalid fixed gain")

        self.FIXED_GAIN_REAL = np.int16(complex_gain.real)
        self.FIXED_GAIN_IMAG = np.int16(complex_gain.imag)

        # if use_gain_table is not None:
        #     self.USE_GAIN_TABLE = use_gain_table

    def get_fixed_gain(self):
        """
        Returns the scaler's fixed gain complex value.
        """
        return np.int16(self.FIXED_GAIN_REAL) + 1j*np.int16(self.FIXED_GAIN_IMAG)

    def set_gain_table(self, gain_list, bank = 0):
        """
        Sets the scaler's complex gain table for the specified bank.
        """
        if isinstance(gain_list, (int, float, complex)):
            gain_list = [complex(gain_list)]*self.fpga.NUMBER_OF_FREQUENCY_BINS

        gain_table = np.zeros(4*self.fpga.NUMBER_OF_FREQUENCY_BINS, np.int8)
        for bin, gain in enumerate(gain_list):
            gain_table[4*bin:4*bin+4] = np.fromstring(struct.pack('<HH', gain.imag, gain.real), np.int8)

        self.write_ram(bank*4*self.fpga.NUMBER_OF_FREQUENCY_BINS, gain_table)


    def status(self):
        """ Displays the status of the scaler module"""
        print '-------------- ANT[%i].SCALER STATUS --------------' % self.instance_number 
        print ' SCALER Bypass: %s' % (bool(self.BYPASS))
        print ' Shift left: %i' % self.SHIFT_LEFT


