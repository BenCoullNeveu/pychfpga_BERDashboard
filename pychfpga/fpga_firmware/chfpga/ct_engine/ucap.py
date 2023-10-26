#!/usr/bin/python

"""
ucap.py module
Interface to the FPGA UltraRAM-based frame capture module.
"""

import logging
import asyncio
import socket

from ..mmi import MMI, BitField
import numpy as np
import __main__



class UCAP(MMI):
    """ Object that allows access to an UltraRAM-based frame capture module"""

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS
    MODE             = BitField(CONTROL, 0, 6, width=2, doc='Capture mode: 0: 8 channel, 1: 4 channel, 2: 2 channel, 3: 1 channel')
    CH0              = BitField(CONTROL, 0, 0, width=3, doc='Channel #0 in 1, 2, or 4-channel mode')
    CH1              = BitField(CONTROL, 0, 3, width=3, doc='Channel #1 in 2 or 4-channel mode')
    USER_RESET       = BitField(CONTROL, 1, 7, doc='User reset')
    OUTPUT_SOURCE_SEL = BitField(CONTROL, 1, 6, doc='Selects what data is streamed out: 0: UCAP, 1: CORR44')
    CH2              = BitField(CONTROL, 1, 0, width=3, doc='Channel #2 in 4-channel mode')
    CH3              = BitField(CONTROL, 1, 3, width=3, doc='Channel #3 in 4-channel mode')
    CAPTURE_PERIOD   = BitField(CONTROL, 4, 0, width=24, doc='Number of frames between captures for source 0')
    CAPTURE_PERIOD2  = BitField(CONTROL, 7, 0, width=24, doc='Number of frames between captures for source 1')
    SUB_PERIOD       = BitField(CONTROL, 8, 0, width=5, doc='Dynamic capture rate, 2**(N+1) frames')
    SOURCE_SEL       = BitField(CONTROL, 9, 0, width=8, doc='Bit map selecting the source (0 or 1) for each channel (bit 0 = channel 0)')

    FIFO_OVERFLOW    = BitField(STATUS, 0, 0, doc='1 when dat FIFO has overflowed. Sticky flag.')
    OVERRUN          = BitField(STATUS, 0, 1, doc='1 when data transmission request was performed before the previous transmission was completed. Sticky flag.')
    RST_MON = BitField(STATUS, 0, 2, doc='debug')
    USER_RST_MON = BitField(STATUS, 0, 3, doc='debug')
    PERIOD_CTR          = BitField(STATUS, 1, 0, width=8, doc='debug')
    CAPTURE_CTR          = BitField(STATUS, 2, 0, width=8, doc='debug')

    def __init__(self, fpga_instance, base_address, address_increment, verbose=0):
        self.fpga = fpga_instance
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        super().__init__(fpga_instance, base_address)
        self.sock = None

    def init(self):
        """ Initializes UCAP module"""
        pass


    def get_data(self, flush_timeout=0.01):

        self.sock = self.fpga.get_data_socket()
        # s = getattr(__main__,"ucap_sock", None)
        # if s:
        #     self.sock = s
        # if self.sock is None:
        #     self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); 
        #     self.sock.bind(("0.0.0.0",41000))
        #     __main__.ucap_sock = self.sock
        # Flush the UDP  buffers by reading and discarding data until we timeout
        self.sock.settimeout(flush_timeout)
        b = np.zeros((128, 8192+5), '>i2')
        print('Flushing UDP buffers')
        while True:
            try:
                self.sock.recv_into(b[0])
            except socket.timeout:
                break
        self.sock.settimeout(2)
        print('Capturing data')
        for bb in b: 
            self.sock.recv_into(bb)
        print(f'got stream_IDs: {b[:, 1] >> 8}')
        for bb in b:
            print(bb[:5].tobytes().hex(':'))
        # sid = 
        # sid_ok = all(b[:,1]>>8 == np.arange(b.shape[0], dtype=np.uint8) & 63)
        # if not sid_ok:
        #     raise RuntimeError('Missing packets')
        return b[:63, 5:]

    def get_data_receiver(self):
        return RawFrameReceiver(self.fpga.get_data_socket())

class RawFrameReceiver(object):
    """
    Pure Python socket receiver to capture the raw ADC or FFT data from the FPGA.

    Note that the packets are larger than 1500 bytes, which requires the
    networking equipment and the computer interface to be configured to
    receive Jumbo frames.

    The receiver is fast enough to capture data exceeding 500
    Mbits/s, provided the system provides a sufficiently big UDP buffer to hold
    the data until the receiver method is called to process it (see below).

    Parameters:

        socket (socket.socket): An opened and bound UDP socket to which the
            FPGA correlator data will be sent. The socket will not be closed
            when the call is completed.

    System Requirements:

    The transmit rate must be fast enough to accommodate the desired bandwidth
    by setting ib.GPIO.HOST_FRAME_READ_RATE = rate. rate=16 limits to about
    260 Mbps but is slow enough to allow python to process the data with a
    small standard UDP buffer. ``rate``=15 is good for about 500 Mbps, and
    ``rate``=16 is good for the full Gigabit bandwidth. The latetr two require
    bigger UDP buffers. See below::

        ib.GPIO.HOST_FRAME_READ_RATE = 14

    The Ethernet interface must be set to receive Jumbo frames::

        sudo ifconfig eno1 mtu 9000

    The UDP buffers shall be increased to reduce packet loss to a minimum::
        sudo sysctl -w net.core.rmem_max=26214400
        sudo sysctl -w net.core.rmem_default=26214400
        sudo sysctl -w net.ipv4.udp_mem='26214400 26214400 26214400'
        sudo sysctl -w net.ipv4.udp_rmem_min=26214400

    Check udp buffers::
        sysctl -a | grep mem

    Monitor UDP buffer::

        watch -cd -n .5 "grep :A6  /proc/net/udp"
    """

    def __init__(self, socket, buffer_length=256):

        self.socket = socket
        self.NPACKETS = buffer_length
        self.FRAME_SIZE = 16384*2 # bytes
        self.DATA_SIZE = self.FRAME_SIZE // 4
        # self.ignore_packet_size = ignore_packet_size
        # Define numpy data types that will be used to efficiently parse the data

        self.header_dtype = np.dtype(dict(
            names=['cookie', 'stream_id', 'source_crate', 'slot_chan', 'subframe', 'ts'],
            offsets=[0, 1, 1, 2, 3, 2],
            formats=['u1', '>u2', 'u1', 'u1', 'u1', '>u8']))

        self.packet_dtype = np.dtype([
            ('header', self.header_dtype, (1, )),
            ('data', np.int8, (self.DATA_SIZE, ))])

        self.PACKET_SIZE = self.packet_dtype.itemsize

        # Pre-allocate buffers
        # Buffer in which recv_into() will put the data directly
        self.buf = np.zeros((self.NPACKETS, self.PACKET_SIZE), dtype=np.int8)  # can use empty(), but the uninitialized data can be confusing for debugging
        self.n = 0  # buffer write index
        self.last_ts = None  # timestamp of the last packet written in the buffer

        # Various views of the buffer to allow quick and easy access to the packet contents

        self.buf_struct = self.buf.view(self.packet_dtype)[:,0]

        self.buf_cookie = self.buf_struct['header']['cookie'][:, 0]
        self.buf_stream_id = self.buf_struct['header']['stream_id'][:, 0]
        # self.buf_source_crate = self.buf_struct['header']['source_crate'][:, 0]
        self.buf_slot_chan = self.buf_struct['header']['slot_chan'][:, 0]
        self.buf_subframe = self.buf_struct['header']['subframe'][:, 0]
        self.buf_ts = self.buf_struct['header']['ts'][:, 0]
        self.buf_ts_dirty = self.buf_struct['header']['ts'][:, 0]
        self.buf_data = self.buf_struct['data']
        self.ts_mask = np.uint64(0xFFFFFFFFFFFF)  # just keep the last 48 bits

    def flush(self, timeout, verbose=0):
            # Read packets until timeout
            self.socket.settimeout(timeout)
            while True:
                try:
                    s = self.socket.recv_into(self.buf[0])
                    if verbose:
                        print(f'flushing packet len={s} cookie=0x{self.buf_cookie[0]:02x} ts={self.buf_ts[0] & self.ts_mask}')

                except socket.timeout:
                    break
            # We assume the buffer might have overflowed and contains partial
            # timestamp. We flush until we gen a new timestamp.
    def wait_for_new_timestamp(self, cookie, timeout, verbose=0):
            self.socket.settimeout(timeout)
            while True:
                try:
                    s = self.socket.recv_into(self.buf[0])
                    if self.buf_cookie[0] & 0xfe != cookie:
                        continue
                    ts = self.buf_ts[0] & self.ts_mask
                    if self.last_ts is None:
                        self.last_ts = ts
                        continue
                    if self.last_ts == ts:
                        if verbose:
                            print(f'skipping packet len={s} cookie=0x{self.buf_cookie[0]:02x} ts={ts}')
                        continue
                    self.last_ts = ts
                    self.n = 1
                    break
                except socket.timeout:
                    continue
    def receive_packets(self, cookie, verbose=0):
        """ Receive some packets into the buffer until there is a timeout or the buffer is full
        """
        while True:
            if self.n == self.NPACKETS:
                return
            try:
                s = self.socket.recv_into(self.buf[self.n])
                # check if the packet has the right cookie
                if verbose:
                    print(f'got packet len={s} cookie=0x{self.buf_cookie[self.n]:02x} ts={self.buf_ts[self.n] & self.ts_mask}')
                if self.buf_cookie[self.n] & 0xfe != cookie:
                    continue

                # Ignore packets that don't have the right length
                if s != self.PACKET_SIZE:
                    continue
                ts = self.buf_ts[self.n] & self.ts_mask
                self.n += 1
                if verbose:
                    print(f'ts={ts}, last_ts={self.last_ts}, sid={self.buf_stream_id[self.n]:04x}')
                if self.last_ts is None:
                    self.last_ts = ts
                    continue
                if ts != self.last_ts:
                    break
            except socket.timeout:  # we have a timeout, so we probably have time to process data
                if self.n:  # continue if we don't have any data to process
                    print('timeout')
                    break
        # we get here if there is a timeout, a timestamp change, or if the buffer is full
        print(f'got {self.n} packets')

    def read_raw_frames(
            self,
            stream_ids=range(8),
            flush=True,
            data_timeout=0.01,
            flush_timeout=0.001,
            verbose=0):
        """ Reads the specified number of raw data frames.

        Parameters:

            channels (list of int): List of channels to capture

            number_of_frames (int): number of frames to capture for each channel.

        Returns:
        {timestamp:{channel:data}}


        use flush=true is we expect the UDP buffer to contain old data tht needs to be discarded.
        """
        sid_map = {sid:ix for ix, sid in enumerate(stream_ids)}
        self.cookie = cookie = 0xa0

        if flush:
            self.flush(flush_timeout, verbose=verbose)
            self.wait_for_new_timestamp(cookie, data_timeout, verbose=verbose)
        print(f'finished flushing')
        self.last_ts = None
        self.socket.settimeout(data_timeout)
        self.receive_packets(cookie=cookie)

        # Determine the capture mode
        print(f'sf={self.buf_subframe[:self.n]}')
        mode = list(set((self.buf_subframe[:self.n] >> 2) & 0x3))
        if len(mode) != 1:
            raise(RuntimeError(f'Unknown capture mode. Got packets with modes {mode}'))
        mode = mode[0]
        frames_per_channel = 2 * 2**(mode)
        print(f"mode={mode}")
        # FRAMES_PER_CHANNEL = 2
        self.data = np.zeros((len(sid_map), self.FRAME_SIZE*frames_per_channel), dtype=np.int8)
        self.data_count = np.zeros((len(sid_map),), dtype=np.int8)


        for i in range(self.n):
            bix = sid_map.get(self.buf_stream_id[i] & 0x7, None)
            subframe = self.buf_subframe[i] & 0x3
            frame = (self.buf_stream_id[i] >> 12) & 0x0F
            print(f'Ch={bix}, frame={frame}, subframe={subframe}')
            if bix is not None:
                x = frame * self.FRAME_SIZE + subframe*self.DATA_SIZE
                self.data[bix][x:x+self.DATA_SIZE] = self.buf_data[i]
                self.data_count[bix] += 1

        ts = self.buf_ts[0]
        return ts, self.data, self.data_count

