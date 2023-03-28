#!/usr/bin/python

"""
untract.py module
Interface for the FPGA UltraRAM-based crossbar/packet generator.
"""

import logging
import asyncio
import socket

from wtl.metrics import Metrics
from ..mmi import MMI, BitField
import numpy as np

from . import chan_bin_sel


class UltraCT(MMI):
    """ Object that allows access to an UltraRAM-based corner-turn module"""

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    RAM_SEL             = BitField(CONTROL, 0, 5, doc='When 0, RAM writes are made to the UltraRAM data memory. When 1, RAM writes are made to the playlist memory.')
    RAM_BANK            = BitField(CONTROL, 0, 4, doc='Determines in which bank of the data buffer is written by RAM writes')
    RAM_FRAME            = BitField(CONTROL, 0, 0, width=4, doc='Determines for which frame of the data buffer is written by RAM writes')

    RX_WRITE_EN       = BitField(CONTROL, 1, 7, doc='1: Allows channelizer data to be written in the data buffer')
    TX_TRIG_SEL         = BitField(CONTROL, 1, 6, doc='   0: Data transmission starts when an incoming frame set is completed; 1: data transmission starts every `TX_PERIOD` clocks. ')
    TX_ENABLE           = BitField(CONTROL, 1, 5, doc="'1' to enable data transmission. '0' data transmission is muted.  ")
    TX_RESET           = BitField(CONTROL, 1, 4, doc="'1' resets the data transmitter  ")
    TX_TOGGLE_BANK           = BitField(CONTROL, 1, 3, doc="When 0, only bank 0 is sent. When 1, the bank not being currently written into is sent.")
    TX_INSERT_TIMESTAMP           = BitField(CONTROL, 1, 2, doc="When 1, a timestamp is inserted in the header words .")
    RX_MASK_LOW_BINS  = BitField(CONTROL, 1, 1, doc="When 1, a incoming data for bins 0 to 127 is not written into the buffer so these bins can be used for packet headers.")
    TX_OVERRIDE_DATA  = BitField(CONTROL, 1, 0, doc="When 1, the output data is oferriden by a fixed pattern.")

    TX_PERIOD           = BitField(CONTROL, 5, 0, width=32, doc="Number of clocks between playlist transmission")
    TX_LENGTH           = BitField(CONTROL, 6, 0, width=8, doc="maximum number of words to transmit in a period")

    TIMESTAMP_INCR           = BitField(CONTROL, 7, 0, width=5,  doc="Timestamp increments between transmission sets")

    OVERRUN           = BitField(STATUS, 0, 0, doc='1 when data transmission request was performed before the previous transmission was completed. Sticky flag.')
    IN_FRAME_CTR           = BitField(STATUS, 1, 0, width=8, doc='Counts the number of frames coming in.')
    OUT_FRAME_CTR           = BitField(STATUS, 2, 0, width=8, doc='Counts the number of frames coming out.')

    def __init__(self, fpga_instance, base_address, address_increment, verbose=0):
        self.fpga = fpga_instance
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.crossbar_level = 1
        self.NUMBER_OF_CROSSBAR_OUTPUTS = 1 # 1 physicala link, although we have up to 128 logical links
        super().__init__(fpga_instance, base_address)

        self.source_mac_addr = "00:5D:03:01:02:03"
        self.source_ip_addr = "10.70.0.1"
        self.source_ip_port = 41000
        self.targets = {
            0: dict(target_mac_addr="FF:FF:FF:FF:FF:FF", target_ip_addr="255.255.255.255", target_ip_port=41001)
        }

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



        self.RX_WRITE_EN = 0
        self.RX_MASK_LOW_BINS = 1

        self.TX_TRIG_SEL = 1  # enable period-based transmission trigger
        self.TX_ENABLE = 1
        self.TX_TOGGLE_BANK = 0
        self.TX_INSERT_TIMESTAMP = 1
        self.TX_OVERRIDE_DATA = 0
        self.TX_RESET = 1
        self.set_playlist()
        # hdr = (0xFFFFFFFFFFFF_010203040506_0800_4500_0000_1234_0000_7F11_0000_0A0A0A82_0A0A0A0A_A027_A028_0000_0000_BEEFFACEABBA_00000000_deadbea7_0011223344556677).to_bytes(64,'big')
        # self.set_bin_data(0, hdr)
        for i in range(16):
            self.set_bin_data(1, frame=i, data=np.arange(8, dtype=np.uint8)+16*i)

        self.TX_RESET = 0

    def set_bin_data(self, bin, data, frame=0):
        """ Set the bin data for one or more consecutive frames
        """
        for i in range(0,len(data),8):
            self.write_data_buffer(bin=bin, frame=frame, data=data[i:i+8])
            frame += 1

    def set_ethernet_header(self, target, length, stream_id):
        """ Stores an Ethernet/IP/UDP/payload header in the bin corresponding to specified target. 
        """
        def h(s):
            print(s)
            return bytes.fromhex(s.translate({ord(c):None for c in "_ :"}))
        src_mac_addr = h(self.source_mac_addr)
        src_ip_addr = socket.inet_aton(self.source_ip_addr)
        src_port = self.source_ip_port.to_bytes(2, 'big')

        tgt = self.targets[target]
        dest_mac_addr = h(tgt['target_mac_addr'])
        dest_ip_addr = socket.inet_aton(tgt['target_ip_addr'])
        dest_port = tgt['target_ip_port'].to_bytes(2, 'big')

        udp_len = 8 + 22 + length
        ip_len = 20 + udp_len

        # ethernet header
        ethertype = h('0800') # IP protocol
        # eth_header = f"{dest_mac_addr} {src_mac_addr} 0800"  # -- dest MAC addr, src MAC addr, ethertype (0x0800=IPv4)
        eth_bytes = dest_mac_addr + src_mac_addr + ethertype  # -- dest MAC addr, src MAC addr, ethertype (0x0800=IPv4)

        # IP header
        # ip_header = ; #-- Version/HdrLen/DSCP/ECP flags, IP Len, ID, Flags/Frag offset, TTL, Protocol, IP header checksum, src IP addr, Dest IP Addr
        ip_bytes = bytearray(h('4500') + ip_len.to_bytes(2,'big') + h('1234 0000 7F 11_0000') + src_ip_addr + dest_ip_addr)
        ip_checksum = (sum(ip_bytes[::2]) << 8) + sum(ip_bytes[1::2])
        ip_checksum = (~ (ip_checksum + (ip_checksum >> 16))) & 0xFFFF
        ip_bytes[10:12] = ip_checksum.to_bytes(2,'big')

        # UDP Header
        udp_bytes = src_port + dest_port + udp_len.to_bytes(2, 'big') + h("0000"); #-- Src port, dest port, UDP len,  UDP checksum (0=disable)
        # udp_header = f"{src_port:04X} {dest_port:04X} {udp_len:04X} 0000"; #-- Src port, dest port, UDP len,  UDP checksum (0=disable)

        # user header
        user_bytes = h("CF14") + stream_id.to_bytes(2, 'little') + h('0000 0000 0000000000000000 000000000000')

        # total header
        header = eth_bytes + ip_bytes + udp_bytes + user_bytes
        print(f"Eth Header is {eth_bytes.hex()} ({len(eth_bytes)} bytes)")
        print(f"IP Header is {ip_bytes.hex()} ({len(ip_bytes)} bytes)")
        print(f"UDP Header is {udp_bytes.hex()} ({len(udp_bytes)} bytes)")
        print(f"User Header is {user_bytes.hex()} ({len(user_bytes)} bytes)")

        # print(f"Header is {header.hex()} ({len(header)} bytes)")
        self.set_bin_data(target, header)


    def set_playlist(self,bins={0:[1]}):
        """
        bins (dict): {target_id:bin_list} dict describing the bin numbers to send to each target. 8-frame (8*8 = 64 bytes) of the first bin is send, and 16 frames (128 bytes) is sent for the others.  
        Word:

            15: End of transmisison
            14: End of packet
            13: Number of frames: 0: 2 frames, 1: 4 frames
            12-0: Bin number
        """
        addr = 0
        for i, (target, b) in enumerate(bins.items()): 
            length = 8 * 16 * len(b)
            self.set_ethernet_header(target, length, stream_id=0x1234)
            b = np.array([target] + b, dtype='>u2')
            b[-1] |= 1<<14 # end of packet on last bin
            b[1:] |= 1<<13 # Send 4 frames except for 1st bin
            if i == len(bins)-1:
                b[-1] |= (1<<15) # end of transmission on last bin of last packet
            print(f'Writing PL RAM[{addr}]={b.tobytes().hex()}')
            self.write_playlist_buffer(addr, b.tobytes())
            addr += 2 * len(b)

        # self.RAM_SEL = 0  # select playlist buffer
        # b = np.array([i + (1<<13) for i in range(10*10)], dtype=np.uint8)

    def write_data_buffer(self, data, bin=0, frame=0, bank=0):
        self.RAM_SEL = 0  # select data buffer
        if not isinstance(bank, (list, tuple)):
            bank = (bank,)
        if not isinstance(frame, (list, tuple)):
            frame = (frame,)
        if isinstance(data, np.ndarray):
            data = data.tobytes()
        for b in bank:
            self.RAM_BANK = b
            for f in frame:
                self.RAM_FRAME = f
                self.write_ram(8*bin, data)

    def write_playlist_buffer(self, addr, data):
        self.RAM_SEL = 1  # select data buffer
        self.write_ram(addr, data)


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
