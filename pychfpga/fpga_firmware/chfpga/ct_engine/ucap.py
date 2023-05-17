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
    CH2              = BitField(CONTROL, 1, 0, width=3, doc='Channel #2 in 4-channel mode')
    CH3              = BitField(CONTROL, 1, 3, width=3, doc='Channel #3 in 4-channel mode')
    CAPTURE_PERIOD   = BitField(CONTROL, 4, 0, width=24, doc='Number of frames between captures')

    FIFO_OVERFLOW    = BitField(STATUS, 0, 0, doc='1 when dat FIFO has overflowed. Sticky flag.')
    OVERRUN          = BitField(STATUS, 0, 1, doc='1 when data transmission request was performed before the previous transmission was completed. Sticky flag.')

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

        s = getattr(__main__,"ucap_sock", None)
        if s:
            self.sock = s
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); 
            self.sock.bind(("0.0.0.0",41000))
            __main__.ucap_sock = self.sock
        # Flush the UDP  buffers by reading and discarding data until we timeout
        self.sock.settimeout(flush_timeout)
        b = np.zeros((128, 4096+5), '>i2')
        print('Flushing UDB buffers')
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
