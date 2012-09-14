#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
CH_DIST.py module 
 Implements interface to the channel filter
#
# History:
# 2011-07-12 JFC : Created from test code in chFPGA.py
# 2012-05-29 JFC: Extracted frm ANT.py
# 2012-07-23 JFC: Adapted to new firmware version now part of the correlator block 
"""
#import time
import numpy as np
from Module import Module_base, BitField
    

class CH_DIST_base(Module_base):
    """ Implements interface to the FR_DIST within a procecessor pipeline"""
    # Create local variables for page numbers to make the bitfield table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # Control bitfields
    RESET = BitField(CONTROL, 0x00, 7, doc="Reset the CH_DIST. Clears FIFO.")
    STREAM_ID = BitField(CONTROL, 0x02, 0, width=16, doc="Stream ID to be used for tagging the output frames")

    # Status bitfields
    FIFO_EMPTY = BitField(STATUS, 0x00, 7, doc="Active high when the data FIFO is empty")
    FIFO_OVERFLOW = BitField(STATUS, 0x00, 6, doc="Active high if the data FIFO is overflowing")
    FRAME_CTR = BitField(STATUS, 0x01, 0, width=8, doc="Number of frames written into the FIFOs. Rolls over.")

    def __init__(self, parent, fpga_instance, port_number, module_number):
        self.parent = parent
        self.fpga = fpga_instance
        super(self.__class__, self).__init__(fpga_instance, port_number, module_number)
        self._lock()
    def reset(self):
        """Performs the soft reset of the CH_DIST module."""
        self.RESET = 1
        self.RESET = 0

    def select_words(self, words_to_enable):
        """
        Selects which words* are going to be transmitted at the output of the antenna processing pipeline.
        If 'pattern' is an integer, words 0 to (pattern-1) are transmitted.
        If pattern is an array, the word numbers indicated in the arrays are transmitted.
        * NOTE: a word is 4 bytes. If the FFT is bypassed, each word contains 4 8-bit ADC samples. 
            If the FFT is enabled, each word contains 2 complex values, one for the even and odd frequency bin. Each complex value is two 8-bit values (real and imaginary)
        """
        # Initialize filter mask (8 flags per word)
        mask = np.zeros(self.fpga.FRAME_LENGTH/4/8, np.uint8)

        if isinstance(words_to_enable, int):
            words_to_enable = range(words_to_enable)

        # Set the bits in mask
        for j in words_to_enable:
            #print 'setting bit %i of byte %i' % ((j % 8), j//8)
            mask[j//8] |= (1<<(j % 8))

        self.write_ram(0x00, mask) # Enable transmission of selected bytes 

    def init(self):
        """ Initializes CH_DIST."""
        #self.select_words(self.fpga.FRAME_LENGTH//4) # enable tranmission of all words by default
        #array doesn't seem to work here....
        self.select_words(8) # enable tranmission 8 words, 16 freq channels by default

    def status(self):
        """Displays the status of CH_DIST."""
        print '-------------- CORR[%i].CH_DIST STATUS --------------' % (self.parent.instance_number)
        print '   RESET: %i' % self.RESET
        print '   FIFO EMPTY: %i' % self.FIFO_EMPTY
        print '   FIFO OVERFLOW: %i' % self.FIFO_OVERFLOW


