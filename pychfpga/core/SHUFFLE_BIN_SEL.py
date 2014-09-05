#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
SHUFFLE_BIN_SEL.py module
 Implements interface to the shuffle bin selector (used in the shuffle crossbars, not to be confused with the channel bin selector used in the channel crossbar)
#
# History:
# 2014-09-01 JFC : Created from CH_DIST.py
"""
#import time
import numpy as np
from Module import Module_base, BitField
import logging


class SHUFFLE_BIN_SEL_base(Module_base):
    """ Implements interface to the FR_DIST within a procecessor pipeline"""
    # Create local variables for page numbers to make the bitfield table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # Control bitfields
    RESET                       = BitField(CONTROL, 0x00, 7, doc="Reset the CH_DIST. Clears FIFO.")
    # FOUR_BITS                = BitField(CONTROL, 0x00, 6, doc="When '1', input data is assumed to be four bits only and the output words are repacked accordingly (4 complex numbers per word).")
    # USE_OFFSET_BINARY        = BitField(CONTROL, 0x00, 5, doc="When '1', indicates that the data uses offset binary encoding instead of 2's complement. Does not affect any processing here, but the flag is passed in the frame header.")
    # SEND_FLAGS               = BitField(CONTROL, 0x00, 4, doc="When '1', the scaler and ADC/FFT flags are appended to the end of the data packet")
    # DUAL_BINS                = BitField(CONTROL, 0x00, 3, doc="When '1', both bins coming out of the FFT are always selected simultaneously, allowing all the data from a channelizer to be packed into a single GPU lane. '0' is the default. ")
    HEADER_CAPTURE_SEL         = BitField(CONTROL, 0x00, 1, width=4, doc=" Select from which lane the captured STREAM_ID and TIMESTAMP is accessed.")
    HEADER_CAPTURE_EN          = BitField(CONTROL, 0x00, 0, doc="Enables capture of header info on all lanes simultaneously.")

    STREAM_ID                   = BitField(CONTROL, 0x02, 4, width=12, doc="Stream ID to be used for tagging the output frames")
    NUMBER_OF_BINS_PER_FRAME    = BitField(CONTROL, 0x03, 0, width=11, doc="Number of bins extected in each incoming frame")
    NUMBER_OF_WORDS_PER_BIN     = BitField(CONTROL, 0x04, 0, width=7, doc="Number of words expected in each bin. In 4-bit mode, 1 Word = 4 analog inputs")
    NUMBER_OF_FRAMES_PER_PACKET = BitField(CONTROL, 0x05, 5, width=3, doc="Number of expected frames per packet. ")
    NUMBER_OF_LANES             = BitField(CONTROL, 0x05, 0, width=5, doc="Number of lanes (from lane 0 to lane N-1) to include in the output")

    # Status bitfields
    FIFO_EMPTY               = BitField(STATUS, 0x00, 7, doc="Active high when the data FIFO is empty")
    # FIFO_OVERFLOW            = BitField(STATUS, 0x00, 6, doc="Active high if the data FIFO is overflowing")
    IS_RESET                 = BitField(STATUS, 0x00, 5, doc="High when the module reset line is active")
    COMBINE_DATA_FLAGS       = BitField(STATUS, 0x00, 4, doc="Active high if this crossbar is configured to pack the data flags two by two. This is used for the 2nd crossbar, where the incoming data flags occupy only 16 bits of the words.")
    STREAM_ID_CAPTURE        = BitField(STATUS, 0x02, 0, width=16, doc="")
    TIMESTAMP_CAPTURE        = BitField(STATUS, 0x04, 0, width=16, doc="")

    # IN_FRAME_CTR             = BitField(STATUS, 0x02, 0, width=8, doc="Number of frames received on lane 0 before the alignment FIFOs. Rolls over.")

    LANE_CTR                = BitField(STATUS, 0x04, 0, width=4, doc="Debug")

    def __init__(self, fpga_instance, base_address, instance_number):
        # self.parent = parent
        # self.fpga = fpga_instance
        super(self.__class__, self).__init__(fpga_instance, base_address, instance_number)
        self.logger = logging.getLogger(__name__)
        self._lock()

    def reset(self):
        """Performs the soft reset of the CH_DIST module."""
        self.RESET = 1
        self.RESET = 0


    def select_bins(self, bins_to_enable):
        """
        Selects which frequency bins are going to be passed to the output.

        If 'bins_to_enable' is an integer, words 0 to (bins_to_enable-1) are transmitted. (i.e channels 0 to 2*bins_to_enable-1 are selected )
            select_words(4) selects words 0,1,2 and 3. and freq channels [0,1,2,3,4,5,6,7]
        If 'bins_to_enable' is an array, the word numbers indicated in the arrays are selected.
            select_words([0,1,2,3]) selects words 0,1,2 and 3. and freq channels [0,1,2,3,4,5,6,7]

        If the FFT is bypassed, each word contains 4 8-bit ADC samples instead of a pair of frequency channels.
        """
        # Initialize bin selection mask
        mask = np.zeros(128, np.uint8) # 128*8 = up to 1024 bins / frame

        if isinstance(bins_to_enable, int):
            bins_to_enable = range(bins_to_enable)

        # Set the bits in mask
        for j in bins_to_enable:
            #print 'setting bit %i of byte %i' % ((j % 8), j//8)
            mask[j//8] |= (1<<(j % 8))
        # verbose = False
        # if verbose: print (bins_to_enable)
        self.logger.debug('Configuring lane %i of the crossbar to capture %i frequency bins: %s' % ( self.instance_number, len(bins_to_enable), repr(bins_to_enable)))
        self.logger.debug('Mask pattern is: %s' % ( ' '.join('%02X'% byte for byte in mask)))

        self.write_ram(0x00, mask) # Write the bin selection mask array

    def init(self):
        """ Initializes SHUFFLE_BIN_SEL"""
        #self.select_words(self.fpga.FRAME_LENGTH//4) # enable tranmission of all words by default
        #array doesn't seem to work here....
#        frequency_bins_per_correlator = 124 # 202-5chan correlator # must be even, max 1010 / number of correlated antennas 124-8 channel.  Should get this from config
        #self.select_words(range(words_per_correlator)) # enable tranmission 8 words, 16 freq channels by default
        self.NUMBER_OF_FRAMES_PER_PACKET = 4
        self.NUMBER_OF_WORDS_PER_BIN=4
        self.NUMBER_OF_BINS_PER_FRAME = 8



    def status(self):
        """Displays the status of SHUFFLE_BIN_SEL."""
        self.logger.debug('--- SHUFFLE_BIN_SEL[%i] STATUS' % (self.instance_number))
        self.logger.debug('   RESET: %i' % self.RESET)
        self.logger.debug('   FIFO EMPTY: %i' % self.FIFO_EMPTY)
        # self.logger.debug('   FIFO OVERFLOW: %i' % self.FIFO_OVERFLOW)



    def print_frame_info(self):
        bs = self
        self.HEADER_CAPTURE_EN=1
        self.HEADER_CAPTURE_EN=0
        ts=[]
        sid=[]
        for i in range(16):
            self.HEADER_CAPTURE_SEL=i
            sid.append(self.STREAM_ID_CAPTURE)
            ts.append(self.TIMESTAMP_CAPTURE)
        for i in range(len(ts)):
            print 'Lane %02i: Stream ID=%04x, Frame = %04x (delta = %i)' % (i, sid[i], ts[i], ts[i]-ts[0])
