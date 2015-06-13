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

from Module import Module_base, BitField
import CH_DIST
import SHUFFLE_BIN_SEL

class CROSSBAR_base(Module_base):
    """ Instantiates a container for all correlators blocks"""

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    FRAME_CLK_SEL      = BitField(CONTROL, 0, 7, doc='')
    ALIGN_RESET        = BitField(CONTROL, 0, 6, doc='')
    REMAP_RESET        = BitField(CONTROL, 0, 5, doc='')
    LANE_MONITOR_RESET = BitField(CONTROL, 0, 4, doc='')
    LANE_MONITOR_SEL   = BitField(CONTROL, 0, 0, width=3, doc='')

    SOF_WINDOW_START   = BitField(CONTROL, 1, 0, width=8, doc='')
    SOF_WINDOW_STOP    = BitField(CONTROL, 2, 0, width=8, doc='')
    LANE_MAP_BYTE0     = BitField(CONTROL, 3, 0, width=8, doc='Lane map')
    LANE_MAP_BYTE7     = BitField(CONTROL, 10, 0, width=8, doc='Lane map')


    CB1_LANE_MONITOR   = BitField(STATUS, 1, 0, width=16, doc='')
    CB2_LANE_MONITOR   = BitField(STATUS, 1, 0, width=16, doc='')
    CB1_BIN_CTR        = BitField(STATUS, 2, 0, width=8, doc='')
    INPUT_FRAME_CTR    = BitField(STATUS, 2, 0, width=8, doc='')
    ALIGN_FRAME_CTR    = BitField(STATUS, 3, 0, width=8, doc='')
    OUTPUT_FRAME_CTR   = BitField(STATUS, 4, 0, width=8, doc='')
    CLK_CTR            = BitField(STATUS, 5, 0, width=8, doc='')
    FRAME_CLK_CTR      = BitField(STATUS, 6, 0, width=8, doc='')

    def __init__(self, fpga_instance, base_address, address_increment, crossbar_level=1, verbose=0):
        self.fpga = fpga_instance
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.crossbar_level = crossbar_level
        super(self.__class__, self).__init__(fpga_instance, base_address)
        self.BIN_SEL = []
        if crossbar_level==1:
            self.NUMBER_OF_CROSSBAR_INPUTS = self.fpga.NUMBER_OF_CROSSBAR_INPUTS
            self.NUMBER_OF_CROSSBAR_OUTPUTS = self.fpga.NUMBER_OF_CROSSBAR_OUTPUTS
            for i in range(self.fpga.NUMBER_OF_CROSSBAR_OUTPUTS):
                self.BIN_SEL.append(CH_DIST.CH_DIST_base(fpga_instance, base_address+ (i+1) * address_increment, i))
        else:
            self.NUMBER_OF_CROSSBAR_INPUTS = self.fpga.NUMBER_OF_CROSSBAR_OUTPUTS
            self.NUMBER_OF_CROSSBAR_OUTPUTS = self.fpga.NUMBER_OF_GPU_LINKS
            for i in range(self.NUMBER_OF_CROSSBAR_OUTPUTS):
                self.BIN_SEL.append(SHUFFLE_BIN_SEL.SHUFFLE_BIN_SEL_base(fpga_instance, base_address+ (i+1) * address_increment, i))

    def __getitem__(self, key):
        """    Returns the correlator instance specified by the index"""
        return self.BIN_SEL[key]

    def init(self):
        """ Initializes all correlators"""
        for bs in self.BIN_SEL:
            bs.init()

        self.configure() # apply default configuration for now.
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
            raise ValueError('Number of bits %i is invalid for the channelizers. Only 4 or 8 is allowed' % width)

        # Set the channelizer data width
        for bs in self.BIN_SEL:
            bs.FOUR_BITS = is_four_bits

    def get_data_width(self):
        """
        Returns number of bits used by the crossbar.
        If all the crossbar sub-units  are not set in the same mode, an error is raised.
        """
        if not self.BIN_SEL:
            return None

        four_bits = {bs.FOUR_BITS for bs in self.BIN_SEL}  # use a set to uniquely record all the possible encountered states

        if four_bits == {0}:
            return 8
        elif four_bits == {1}:
            return 4
        else:
            raise ValueError("The crossbars are not all set to the same data width.")

    def set_frames_per_packet(self, group_size):
        """
        Set the number of frame per packets.
        """
        for bs in self.BIN_SEL:
            bs.GROUP_FRAMES = group_size

    def get_frames_per_packet(self):
        """
        Return the number of frames per packets.
        """
        return self.BIN_SEL[0].GROUP_FRAMES

    def set_lane_map(self, lane_map):
    	"""
    	NOTE: Lanes are numbered from 0 to 15.
    	"""
        if len(lane_map)!=self.NUMBER_OF_CROSSBAR_INPUTS:
            raise TypeError('Lane map must be a list of %i values' % self.NUMBER_OF_CROSSBAR_INPUTS)

        lane_map_bytes = np.zeros(self.NUMBER_OF_CROSSBAR_INPUTS/2, dtype=np.uint8)
        for i,lane in enumerate(lane_map):
            byte = i//2
            bit = (i%2)*4
            lane_map_bytes[byte] |= (lane & 0x0F) << bit

        self.write(self.get_addr('LANE_MAP_BYTE0'), lane_map_bytes)

    def configure(self, number_of_bins_per_crossbar_output= 8):
        """
        Configure the channel selection.
        This should be done once the data width has been selected.
        """
        # data_width = self.get_data_width()
        # # Compute the minimum word spacing to allow the channel_selector time to forwared the data.
        # # In 8-bit mode, 2*N bins come every clock from the channelizers, and it takes N clocks to send them away (2 per output word). So the bin spacing is N.
        # # In 4-bit mode, 2*N bins come every clock from the channelizers, and it takes N/2 clocks to send them away ( 4 per output word). So bin spacing is N/2.
        # bin_step = self.fpga.NUMBER_OF_CROSSBAR_INPUTS * data_width / 8
        # number_of_bins_per_frame = self.fpga.FRAME_LENGTH / 2 # The FFT generates 2048 bins, but half of them are discarded
        # #number_of_bins_per_frame = 2 # The FFT generates 2048 bins, but half of them are discarded
        # if number_of_bins_per_crossbar_output is None:
        #     number_of_bins_per_crossbar_output =  int (number_of_bins_per_frame / bin_step) # Number of channels that one channel selector can handle

        # if bin_step > self.fpga.NUMBER_OF_CROSSBAR_OUTPUTS:
        #     self.logger.warning('   Only a fraction of the frequency bins can be mapped to the crossbar outputs because the total number of bits entering the crossbar exceeds the number of bits at its outputs.')

        # # Check if the set-up is acceptable for the FPGA correlator (if present in the FPGA), and make corrections if needed
        # if self.fpga.NUMBER_OF_CORRELATORS:
        #     if data_width == 4:
        #         self.logger.warning('The FPGA correlator will not operate properly in 4-bit mode ')

        #     max_correlator_frame_length_in_words = 511 # maximum number of words that the correlator can handle in a frame. This is limited by the ACCumulator buffer depth
        #     max_number_of_words_per_correlator = int( max_correlator_frame_length_in_words / self.fpga.NUMBER_OF_ANTENNAS_TO_CORRELATE ) # maximum number of words that can be selected
        #     if number_of_bins_per_crossbar_output > 2*max_number_of_words_per_correlator:
        #         self.logger.warning('   The number of frequency bins in each crossbar output was reduced from %i to %i due to the correlator accumulator memory limitation' % (number_of_bins_per_crossbar_output, max_number_of_words_per_correlator))
        #         number_of_bins_per_crossbar_output = 2*max_number_of_words_per_correlator

        # # Apply GPU Link limitations
        # if self.fpga.NUMBER_OF_GPU_LINKS:
        #     max_number_of_words_per_input_frame = 4095 // self.get_frame_grouping() * 8 / data_width / self.fpga.NUMBER_OF_CROSSBAR_INPUTS
        #     if number_of_bins_per_crossbar_output > 2*max_number_of_words_per_input_frame:
        #         self.logger.warning('   The number of frequency bins in each crossbar output was reduced from %i to %i due to the GPU link buffer size limitations' % (number_of_bins_per_crossbar_output, max_number_of_words_per_input_frame))
        #         number_of_bins_per_crossbar_output = 2*max_number_of_words_per_input_frame

#         for (i, xbar) in enumerate(self.CROSSBAR):
#             bin_list = np.arange(number_of_bins_per_crossbar_output)* bin_step + i
#             # xbar.CH_DIST.select_words(word_list) # enable tranmission 8 words, 16 freq channels by default
# #            bin_list = [0,8]
#             xbar.CH_DIST.select_bins(bin_list) # enable tranmission 8 words, 16 freq channels by default
        for (i, bs) in enumerate(self.BIN_SEL):
            if self.crossbar_level==1:
                bin_list = np.arange(number_of_bins_per_crossbar_output)* 2 + i
            else:
                bin_list = np.arange(number_of_bins_per_crossbar_output) * 8 + i
            # xbar.CH_DIST.select_words(word_list) # enable tranmission 8 words, 16 freq channels by default
#            bin_list = [0,8]
            bs.select_bins(bin_list) # enable tranmission 8 words, 16 freq channels by default

    def status(self):
        """ Displays the status of all correlators"""
        for bs in self.BIN_SEL:
            bs.status()

    def print_lane_monitor(self):
        if self.crossbar_level == 1:
            lane_monitor_info = {
                0: 'reset',
                5: 'align fifo overflow (real time)',
                6: 'align fifo overflow (sticky)',
                }
        else:
            lane_monitor_info = {
                0: 'input frame detect',
                1: 'fifo frame detect',
                2: 'align frame detect',
                3: 'output frame detect',
                4: 'remap frame detect',
                5: 'align fifo overflow (real time)',
                6: 'align fifo overflow (sticky)',
                7: 'align fifo tvalid (real time)'
                }

        self.LANE_MONITOR_RESET=1
        self.LANE_MONITOR_RESET=0
        for (ix,name) in lane_monitor_info.items():
            self.LANE_MONITOR_SEL = ix
            if self.crossbar_level == 1:
                value = self.CB1_LANE_MONITOR
                print '%32s = %s' % (name, '{:08b}'.format(value))
            else:
                value = self.CB2_LANE_MONITOR
                print '%32s = %s' % (name, '{:016b}'.format(value))
