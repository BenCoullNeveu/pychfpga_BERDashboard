#!/usr/bin/python

"""
cge.py module
    Implements interface to the 100G Ethernet FPGA module
"""
import logging
from ..mmi import MMI, BitField


class CGE(MMI):
    """ Instantiates a container for all the GPU link ressources

    This class provides access to the memory-mapped registers and
    the high-level methods needed to operate the XGE_ARRAY.VHD module,
    which implements a array on transmit-only 10G Ethernet links.

    It implements a XGLinkCore (ensemble of QPLLs and GTXes and
    date encoding/synchonization) and adds 10G Ethernet packet framing
    (SOF, EOF) and checksum (CRC32). It provides an additional set of
    registers to the XGLinkCore.

    XGLinkArray is used to implement Tx-only communication links from the
    IceBoard's QSFP connector to the GPU farm.

    """

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # 100GE Link control and status registers
    RESET_TX_DATAPATH               = BitField(CONTROL, 0, 0, doc='When 1, the TX datapath is reset')
    RESET_RX_DATAPATH         = BitField(CONTROL, 0, 1, doc='When 1, the RX datapath is reset.')
    CMAC_SYS_RESET      = BitField(CONTROL, 0, 2, doc='When 1, The CMAC is reset.')
    CORE_TX_RESET      = BitField(CONTROL, 0, 3, doc='When 1, The 100G Cor elogic is reset.')
    TEST_PACKET_ENABLE  = BitField(CONTROL, 0, 7, doc='When 1, the test packet generator is enabled')
    TEST_PACKET_WORDS  = BitField(CONTROL, 1, 0, width=8, doc='Number of 32-byte words in the UDP packets in addition to the 22 bytes payload header')
    TEST_PACKET_PERIOD  = BitField(CONTROL, 3, 0, width=16, doc='Time between packets in  322MHz clocks periods')
    STATUS0            = BitField(STATUS, 0, 0, width=8, doc='various status bits')
    IN_FRAME_CTR           = BitField(STATUS, 1, 0, width=8, doc='Counts the number of frames coming in (test frames are counted when enabled).')
    OUT_FRAME_CTR           = BitField(STATUS, 2, 0, width=8, doc='Counts the number of framesgoing out to the CMAC.')
    # DATA_FIFO_OVERFLOW  = BitField(STATUS, 2+2, 0, width=8, doc='Indicates if the data FIFO has overflows on the last 8 GPU links. Bit 0 is for lane 0.')
    # FRAME_FIFO_OVERFLOW = BitField(STATUS, 2+3, 0, width=8, doc='Indicates if the frame header FIFO has overflows on the last 8 GPU links. Bit 0 is for lane 0.')

    def __init__(self, fpga_instance, base_address, address_increment, verbose=1):
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose
        super().__init__(fpga_instance, base_address, address_increment)

    def set_enable(self, enable):
        """
        Enable link.
        """
        self.logger.warn('{self!r}: set_enable()  is not implemented on UltraCT. Command is ignored. ')

    # def reset(self):
    #     """ Resets the UDP/MAC stack, the SGMII interface and the GTX """
    #     self.RESET = 1
    #     self.RESET = 0

    def get_lane_numbers(self):
        """ Returns a list of logical lane numbers for the GPU links.

        There is no distinction between the two QSFP connectors.

        Returns:

            List of integers.
        """
        return list(range(1))

    def get_lane_ids(self):
        """ Return a list of all lane IDs in the form of [(crate_number, slot_number, lane_number), ...].

        Returns:
            List of all lane IDs in the form of [(crate_number, slot_number, lane_number), ...]
        """

        return [self.fpga.get_id(lane) for lane in self.get_lane_numbers()]

    # def status(self):
    #     """ Displays the status of the GPU GTX hardware"""
    #     # for gtx in self.GTX_COMMON:
    #     #     gtx.status()
