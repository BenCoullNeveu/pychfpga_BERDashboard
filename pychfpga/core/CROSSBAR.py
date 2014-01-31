#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
CROSSBAR.py module 
 Implements interface to the crossbar. 
 The crossbar gets data from all channelizers and provide a number of output streams, each of which contain selected frequency channels from those antennas

 History:
 2013-12-03 : JFC : Created 
"""

import logging
import numpy as np

import CH_DIST

class CROSSBAR_channel(object):
    """ Implements interface to one of the correlator"""

    # Antenna processor module addresses
    # CORR_MODULE_ADDR_INCREMENT = 0x00400
    # CH_DIST_ADDR_OFFSET = 0 * CORR_MODULE_ADDR_INCREMENT

    def __init__(self, fpga_instance, base_address, instance_number):
        #super(ADC_chip,self).__init__(fpga)
        # self.parent = parent # store current ADC number for this instance
        self.instance_number = instance_number # store current correlator number for this instance
        # self.fpga = self.parent.fpga
        self.logger = logging.getLogger(__name__)
        self.CH_DIST = CH_DIST.CH_DIST_base(fpga_instance, base_address, instance_number)
        

    def init(self):
        """ Inisializes all modules of a crossbar block.""" 
        self.logger.debug('=== Initializing CROSBAR[%i]' % self.instance_number)
        self.CH_DIST.init()


    def status(self):
        """Displays the status of a crossbar block"""
        self.logger.debug('=== Instantiating CROSBAR[%i]' % self.instance_number)
        self.CH_DIST.status()



class CROSSBAR_base(object):
    """ Instantiates a container for all correlators blocks"""


    def __init__(self, fpga_instance, base_address, address_increment, verbose=0):
        self.fpga = fpga_instance
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        # Create an instance of ADC_chip for each chip of the FMC board
        self.CROSSBAR = []
        for i in range(self.fpga.NUMBER_OF_CROSSBAR_OUTPUTS):
            self.CROSSBAR.append(CROSSBAR_channel(self.fpga, base_address + i * address_increment, i))

    def __getitem__(self, key):
        """    Returns the correlator instance specified by the index"""
        return self.CROSSBAR[key]



    def init(self):
        """ Initializes all correlators"""
        for CROSSBAR in self.CROSSBAR:
            CROSSBAR.init()

    # def select_words(self, words):
    #     """ Initializes all correlators"""
    #     for CROSSBAR in self.CROSSBAR:
    #         CROSSBAR.CH_DIST.select_words(words)

    def set_data_width(self, width):
        """
        Sets the number of bits expected at the input of the crossbar.
        All crossbars are set to the new setting.
            width=4: data is 4 bits Real + 4 bits Imaginary
            width=8: data is 8 bits Real + 8 bits Imaginary
        """

        if width==4:
            is_four_bits = 1
        elif width == 8:
            is_four_bits = 0
        else:
            raise self.fpga.chFPGAException('Number of bits %i is invalid for the channelizers. Only 4 or 8 is allowed' % width)

        # Set the channelizer data width
        for xbar in self.CROSSBAR:
            xbar.CH_DIST.FOUR_BITS = is_four_bits

    def get_data_width(self):
        """
        Returns number of bits used by the crossbar.
        If all the crossbar sub-units  are not set in the same mode, an error is raised.
        """

        four_bits = set() # use a set to uniquely record all the possible encountered states

        for xbar in self.CROSSBAR:
            four_bits.add(xbar.CH_DIST.FOUR_BITS)

        if four_bits == set([0]):
            return 8
        elif four_bits == set([1]):
            return 4
        else:
            raise self.fpga.chFPGAException("The crossbars are not set to the same data width.")

    def set_frame_grouping(self, group_size):
        """
        Sets the numbr of channelizer frames to group in a single frame at the output of the crossbar.
        """
        for xbar in self.CROSSBAR:
            xbar.CH_DIST.GROUP_FRAMES = group_size

    def get_frame_grouping(self):
        """
        returns the numbr of channelizer frames to group in a single frame at the output of the crossbar.
        """
        return self.CROSSBAR[0].CH_DIST.GROUP_FRAMES

    def configure(self, number_of_bins_per_crossbar_output= None):
        """
        Configure the channel selection.
        This should be done once the data width has been selected.
        """
        data_width = self.get_data_width()
        # Compute the minimum word spacing to allow the channel_selector time to forwared the data. 
        # In 8-bit mode, 2*N bins come every clock from the channelizers, and it takes N clocks to send them away (2 per output word). So the bin spacing is N.
        # In 4-bit mode, 2*N bins come every clock from the channelizers, and it takes N/2 clocks to send them away ( 4 per output word). So bin spacing is N/2.
        bin_step = self.fpga.NUMBER_OF_CROSSBAR_INPUTS * data_width / 8 
        number_of_bins_per_frame = self.fpga.FRAME_LENGTH / 2 # The FFT generates 2048 bins, but half of them are discarded 
        #number_of_bins_per_frame = 2 # The FFT generates 2048 bins, but half of them are discarded 
        if number_of_bins_per_crossbar_output is None:
            number_of_bins_per_crossbar_output =  int (number_of_bins_per_frame / bin_step) # Number of channels that one channel selector can handle

        if bin_step > self.fpga.NUMBER_OF_CROSSBAR_OUTPUTS:
            self.logger.warning('   Only a fraction of the frequency bins can be mapped to the crossbar outputs because the total number of bits entering the crossbar exceeds the number of bits at its outputs.')

        # Check if the set-up is acceptable for the FPGA correlator (if present in the FPGA), and make corrections if needed
        if self.fpga.NUMBER_OF_CORRELATORS:
            if data_width == 4:
                self.logger.warning('The FPGA correlator will not operate properly in 4-bit mode ')

            max_correlator_frame_length_in_words = 511 # maximum number of words that the correlator can handle in a frame. This is limited by the ACCumulator buffer depth
            max_number_of_words_per_correlator = int( max_correlator_frame_length_in_words / self.fpga.NUMBER_OF_ANTENNAS_TO_CORRELATE ) # maximum number of words that can be selected
            if number_of_bins_per_crossbar_output > 2*max_number_of_words_per_correlator:
                self.logger.warning('   The number of frequency bins in each crossbar output was reduced from %i to %i due to the correlator accumulator memory limitation' % (number_of_bins_per_crossbar_output, max_number_of_words_per_correlator))
                number_of_bins_per_crossbar_output = 2*max_number_of_words_per_correlator

        # Apply GPU Link limitations
        if self.fpga.NUMBER_OF_GPU_LINKS:
            max_number_of_words_per_input_frame = 4095 // self.get_frame_grouping() * 8 / data_width / self.fpga.NUMBER_OF_CROSSBAR_INPUTS
            if number_of_bins_per_crossbar_output > 2*max_number_of_words_per_input_frame:
                self.logger.warning('   The number of frequency bins in each crossbar output was reduced from %i to %i due to the GPU link buffer size limitations' % (number_of_bins_per_crossbar_output, max_number_of_words_per_input_frame))
                number_of_bins_per_crossbar_output = 2*max_number_of_words_per_input_frame
        
        for (i, xbar) in enumerate(self.CROSSBAR):
            bin_list = np.arange(number_of_bins_per_crossbar_output)* bin_step + i
            # xbar.CH_DIST.select_words(word_list) # enable tranmission 8 words, 16 freq channels by default
#            bin_list = [0,8]
            xbar.CH_DIST.select_bins(bin_list) # enable tranmission 8 words, 16 freq channels by default

    def status(self):
        """ Displays the status of all correlators"""
        for CROSSBAR in self.CROSSBAR:
            CROSSBAR.status()
