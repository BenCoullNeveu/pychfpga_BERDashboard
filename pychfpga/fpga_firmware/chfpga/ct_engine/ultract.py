#!/usr/bin/python

"""
untract.py module
Interface for the FPGA UltraRAM-based crossbar/packet generator.
"""

import logging
import asyncio


from wtl.metrics import Metrics
from ..mmi import MMI, BitField

from . import chan_bin_sel


class UltraCT(MMI):
    """ Object that allows access to an UltraRAM-based corner-turn module"""

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    CHAN_WRITE_EN       = BitField(CONTROL, 0, 7, doc='Allows channelizer data to be written in the buffer')
    AUTO_TRIG           = BitField(CONTROL, 0, 6, doc='Buffer transmission does not wait for channelizer data to have filled the buffer; a new transmission starts as soon as a previous transmission stops.   ')
    RAM_SEL             = BitField(CONTROL, 0, 5, doc='When 0, RAM writes are made to the UltraRAM data memory. When 1, RAM writes are made to the playlist memory.')
    RAM_BANK            = BitField(CONTROL, 0, 4, doc='Determines in which bank of the data buffer is written by RAM writes')
    RAM_FRAME            = BitField(CONTROL, 0, 0, width=4, doc='Determines for which frame of the data buffer is written by RAM writes')


    OVERRUN           = BitField(STATUS, 0, 0, doc='1 when data transmission request was performed before the previous transmission was completed. Sticky flag.')
    IN_FRAME_CTR           = BitField(STATUS, 1, 0, width=8, doc='Counts the number of frames coming in.')
    OUT_FRAME_CTR           = BitField(STATUS, 2, 0, width=8, doc='Counts the number of frames coming out.')

    def __init__(self, fpga_instance, base_address, address_increment, verbose=0):
        self.fpga = fpga_instance
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.crossbar_level = 1
        super().__init__(fpga_instance, base_address)

    def __getitem__(self, key):
        """    Returns the bin selector instance specified by the key"""
        return self.BIN_SEL[key]

    def init(self):
        """ Initializes all correlators"""
        # for bs in self.BIN_SEL:
        #     bs.init()

        # Default bin selector configuration. To be overriden by system-level configuration method.
        # By default we send 64 bins for each of the 16 output lanes. Bins are interleaved.
        # number_of_bins_per_crossbar_output = 64
        # Do not initialize the bin selection map now to same time. This will be done anyway when we initialize the shuffling system.
        # for (i, bs) in enumerate(self.BIN_SEL):
        #     bin_list = np.arange(number_of_bins_per_crossbar_output) * 16 + i
        #     bs.select_bins(bin_list)

    def set_data_width(self, width):
    #     """
    #     Sets the number of bits expected at the input of the crossbar.
    #     All crossbars are set to the new setting.
    #         width=4: data is 4 bits Real + 4 bits Imaginary
    #         width=8: data is 8 bits Real + 8 bits Imaginary
    #     """
        self.logger.warn('{self!r}: Cannot set data width on UltraCT. Command is ignored. ')

    def get_data_width(self):
        """
        Returns number of bits used by the crossbar.
        If all the crossbar sub-units  are not set in the same mode, an error is raised.
        """
        return 4

    def set_frames_per_packet(self, group_size):
        """
        Set the number of frame per packets.
        """
        self.logger.warn('{self!r}: set_frames_per_packet is not implemented on UltraCT. Packet size is set through the playlist. Command is ignored. ')


    # def get_frames_per_packet(self):
    #     """
    #     Return the number of frames per packets.
    #     """
    #     return self.BIN_SEL[0].GROUP_FRAMES

    # def status(self):
    #     """ Displays the status of all bin selectors"""
    #     for bs in self.BIN_SEL:
    #         bs.status()

    # CB1_LANE_MONITOR_TABLE = {
    #     'RESET': 0,
    #     'MISSING_FRAME': 4,
    #     'ALIGN_FIFO_OVERFLOW': 6,
    #     }

    # def get_lane_monitor(self, name):
    #     """
    #     Return a list describing the status of the specified flag for each
    #     lane.
    #     """
    #     table = self.CB1_LANE_MONITOR_TABLE

    #     if name not in table:
    #         raise ValueError('Invalid lane monitor name. valid names are %s' % ','.join(table.keys()))
    #     ix = table[name]
    #     self.LANE_MONITOR_SEL = ix
    #     value = self.LANE_MONITOR
    #     return [bool(value & (1 << bit)) for bit in range(16)]

    # def reset_stats(self):
    #     self.LANE_MONITOR_RESET = 1
    #     self.LANE_MONITOR_RESET = 0

    # def print_lane_monitor(self, reset=True):

    #     if reset:
    #         self.reset_stats()

    #     lane_range = list(range(self.NUMBER_OF_CROSSBAR_INPUTS))

    #     print('%20s: %s' % ('Monitor point', ' '.join('  L%2i ' % v for v in lane_range)))
    #     print('%20s: %s' % ('--------------------', ' '+' '.join('------' for v in lane_range)))
    #     input_frame_ctr = []
    #     align_frame_ctr = []
    #     reset_mon = []
    #     align_fifo_overflow = []
    #     for lane in lane_range:
    #         self.LANE_MONITOR_SEL = lane
    #         reset_mon.append(self.RESET_MON)
    #         align_fifo_overflow.append(self.ALIGN_FIFO_OVERFLOW)
    #         input_frame_ctr.append(self.INPUT_FRAME_CTR)
    #         align_frame_ctr.append(self.ALIGN_FRAME_CTR)

    #     print('%20s: %s' % ('RESET', ' '.join('%6s' % ('-', 'ERR!')[bool(v)] for v in reset_mon)))
    #     print('%20s: %s' % ('ALIGN_FIFO_OVERFLOW',
    #                         ' '.join('%6s' % ('-', 'ERR!')[bool(v)] for v in align_fifo_overflow)))
    #     print('%20s: %s' % ('INPUT FRAME CTR', ' '.join('%6i' % v for v in input_frame_ctr)))
    #     print('%20s: %s' % ('ALIGN FRAME CTR', ' '.join('%6i' % v for v in align_frame_ctr)))
    #     # print '%20s: %s' % ('ALIGN GLOBAL FRAME CTR', '(common to all lanes) %6i' % self.ALIGN_GLOBAL_FRAME_CTR)

    # def print_align_monitor(self, reset=True, N=100):
    #     """ Debug method to monitor the CHAN_ALIGN module monitoring bits. We print the number of times each bit was read as '1'
    #     """
    #     if reset:
    #         self.reset_stats()

    #     for source in range(16):
    #         self.LANE_MONITOR_SOURCE=source;
    #         print(f'Source {source:2}: ', end='')
    #         for i in range(16):
    #             self.LANE_MONITOR_SEL=i;
    #             self.reset_stats()  # reset the bit counter now that we have selected the bit
    #             s = sum(self.LANE_MONITOR_BIT for _ in range(N))
    #             c = self.LANE_MONITOR_CTR
    #             print(f"{s:3}({c:2})", end=" ", flush=True)
    #         print()

    # async def get_metrics(self, reset=True):
    #     """ Return the monitoring metrics for the 1st crossbar.
    #     """
    #     metrics = Metrics(
    #         type='GAUGE',
    #         crate_id=self.fpga.crate.get_string_id() if self.fpga.crate else None,
    #         crate_number=self.fpga.crate.crate_number if self.fpga.crate else None,
    #         slot=(self.fpga.slot or 0) - 1,
    #         id=self.fpga.get_string_id())

    #     for lane in range(self.NUMBER_OF_CROSSBAR_INPUTS):
    #         await asyncio.sleep(0)
    #         self.LANE_MONITOR_SEL = lane
    #         await asyncio.sleep(0)
    #         metrics.add('fpga_crossbar1_reset_state', value=self.RESET_MON, lane=lane)
    #         await asyncio.sleep(0)
    #         metrics.add('fpga_crossbar1_align_fifo_overflow_flag', value=self.ALIGN_FIFO_OVERFLOW, lane=lane)
    #         await asyncio.sleep(0)
    #         metrics.add('fpga_crossbar1_input_frame_counter', value=self.INPUT_FRAME_CTR, lane=lane)
    #         await asyncio.sleep(0)
    #         metrics.add('fpga_crossbar1_align_output_frame_counter', value=self.ALIGN_FRAME_CTR, lane=lane)

    #     if reset:
    #         self.reset_stats()

    #     return metrics

    # def map(self, input_data):
    #     """
    #     Reorders the input data based on the configuration of the bin selectors.
    #     input data: {channel_number: [data, ...]}
    #     output_data: {lane_number: [data, ...]}
    #     """
    #     cb_out = {output_lane: bs.map(input_data) for output_lane, bs in enumerate(self.BIN_SEL)}
    #     return cb_out
    #     # fmap = {output_lane:bs.get_map() for output_lane, bs in enumerate(self.BIN_SEL)}
    #     # return fmap

    # def get_sim_output(self, chan_outputs):
    #     """ Compute the channelizer crossbar output packets.
    #     """
    #     return [bs.get_sim_output(chan_outputs) for bs in self.BIN_SEL]
