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
    # USE_GAIN_TABLE    = BitField(CONTROL, 0x01, 5, doc="When '1', the gain tables are used to apply a bin-by-bin complex gain. Otherwise, the fixed complex gain is used for all bins.")
    READ_COEFF_BANK   = BitField(CONTROL, 0x01, 4, doc="Target gain coefficients bank to be used by the scaler")
    WRITE_COEFF_BANK  = BitField(CONTROL, 0x01, 0, width=4, doc="Indicates in which data page the gain coefficients are being written to. Page 0-7 are coefficients fri bank0, Page 8-15 are for Bank 1 coefficients.")

    STATS_CAPTURE                 = BitField(CONTROL, 0x02, 7, doc="When '1', New saturation/overflow stats are captured")
    SATURATE_ON_MINUS_7           = BitField(CONTROL, 0x02, 6, doc="When '1', Values will saturate at -7 instead of -8.")
    ZERO_ON_SATURATION            = BitField(CONTROL, 0x02, 5, doc="When '1', Both real and Imaginary parts are zeroed when either of them overflow.")
    SYNCHRONIZE_GAIN_BANK         = BitField(CONTROL, 0x02, 4, doc="When '1', The target bank number will be enabled at the target frame number.")
    ROUNDING_MODE                 = BitField(CONTROL, 0x02, 0, width=2, doc="Set rounding mode.  0: Truncate, 1: Round, 2: Convergent Rounding")

    STATS_FRAME_COUNT             = BitField(CONTROL, 0x05, 0, width=24, doc="Number of frames to inclue in stats results.")
    GAIN_BANK_SWITCH_FRAME_NUMBER = BitField(CONTROL, 0x09, 0, width=32, doc="Frame number at which the target gain bak is to be activated.")

    STATS_READY             = BitField(STATUS, 0x00, 7, doc="Indicates that new stats results are ready")
    CURRENT_GAIN_BANK       = BitField(STATUS, 0x00, 6, doc="Currently active gain bank.")
    EIGHT_BIT_SUPPORT       = BitField(STATUS, 0x00, 5, doc="'1' when the SCALER supports 8-bit output")

    STATS_SCALER_OVERFLOWS = BitField(STATUS, 0x02, 0, width=16, doc="Stats result: number of scaler overflows")
    STATS_ADC_OVERFLOWS    = BitField(STATUS, 0x04, 0, width=16, doc="Stats result: number of ADC overflows")
    FRAME_CTR              = BitField(STATUS, 0x05, 0, width=8, doc="Free running frame counter (last 8 bits)")


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
        # self.USE_GAIN_TABLE = 1
        self.USE_OFFSET_BINARY = 1
        # self.set_fixed_gain(1)
        self.set_gain_table(1)
        self.SATURATE_ON_MINUS_7 = 1


    # def set_fixed_gain(self, complex_gain):
    #     """
    #     Sets the scaler's fixed gain complex value.
    #     """

    #     if complex_gain.real<-32768 or complex_gain.real > 32767 or complex_gain.imag<-32768 or complex_gain.imag>32767:
    #         raise ValueError("Invalid fixed gain")

    #     self.FIXED_GAIN_REAL = np.int16(complex_gain.real)
    #     self.FIXED_GAIN_IMAG = np.int16(complex_gain.imag)

    #     # if use_gain_table is not None:
    #     #     self.USE_GAIN_TABLE = use_gain_table

    # def get_fixed_gain(self):
    #     """
    #     Returns the scaler's fixed gain complex value.
    #     """
    #     return np.int16(self.FIXED_GAIN_REAL) + 1j*np.int16(self.FIXED_GAIN_IMAG)

    def set_gain_table(self, gain_list, bank=0):
        """
        Sets the scaler's complex gain table for the specified bank.
        """
        total_bins = self.fpga.NUMBER_OF_FREQUENCY_BINS
        if isinstance(gain_list, (int, float, complex)):
            gains = np.array([complex(gain_list)]*total_bins)
        else:
            gains = np.array(gain_list)

        if any(gains.real < -32768) or any(gains.real > 32767) or any(gains.real != gains.real.astype('<i2')) or \
           any(gains.imag < -32768) or any(gains.imag > 32767) or any(gains.imag != gains.imag.astype('<i2')):
            raise ValueError('All real or imaginary parts of the gains must be integers between -32768 and 32767')

        if len(gains) != total_bins:
            raise ValueError('Either a scalar gain or a 1024 element gain vector must be provided')

        gain_string = np.reshape(np.vstack((gains.imag, gains.real)).T, 2 * total_bins).astype('<i2').tostring()

        # page_table = np.zeros(512, np.int8)
        for page in range(8): # there are 8 pages of coefficients per bank
            self.WRITE_COEFF_BANK = 8 * bank + page
            self.write_ram(0, gain_string[512 * page: 512 * (page + 1)])
            # for ix in range(128): # there are 128 coefficients per page ( 4 byte per coefficient = 512 bytes total per page)
            #     bin = page*128 + ix
            #     gain = gain_list[bin]
            #     page_table[4*ix:4*ix+4] = np.fromstring(struct.pack('<hh', gain.imag, gain.real), np.int8)

            #print page_table
            # self.write_ram(0, np.uint8(page_table))



    def get_gain_table(self, bank=0):
        """
        Gets the scaler's complex gain table for the specified bank.  Converts to numpy complex array.
        """
        page_table = np.zeros(512, np.int8)
        gain_table = []#np.zeros(self.fpga.NUMBER_OF_FREQUENCY_BINS, np.complex)
        for page in range(8): # there are 8 pages of coefficients per bank
            self.WRITE_COEFF_BANK = 8*bank + page # Sets which page/bank being read? Not sure if will work...
            page_table = self.read_ram(0, length=512)
            for ix in range(128): # there are 128 coefficients per page ( 4 byte per coefficient = 512 bytes total per page)
                bin = page*128 + ix
                g_imag, g_real = struct.unpack('<hh',page_table[4*ix:4*ix+4])
                gain_table.append(g_real +1j*g_imag) #[bin] = g_real +1j*g_imag
        return gain_table

    def status(self):
        """ Displays the status of the scaler module"""
        print '-------------- ANT[%i].SCALER STATUS --------------' % self.instance_number
        print ' SCALER Bypass: %s' % (bool(self.BYPASS))
        print ' Shift left: %i' % self.SHIFT_LEFT


