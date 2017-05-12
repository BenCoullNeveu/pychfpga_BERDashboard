#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
CORR.py module
 Implements interface to the correlator blocks

 History:
 2017-05-04 : JFC : Created
"""
# import ACC
import logging
from Module import Module_base, BitField


class CORR_core(Module_base):
    """ Implements interface to one of the correlator"""

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # Control registers
    SOFT_RESET         = BitField(CONTROL, 0x00, 7, doc="Resets this correlator core.")
    FORCE_TDATA         = BitField(CONTROL, 0x00, 6, doc="Force the correlator input to be 0x10101010")
    NO_ACCUM         = BitField(CONTROL, 0x00, 5, doc="Disables accumulation - only the last result is saved")
    USER_ID            = BitField(CONTROL, 0x00, 0, width=4, doc="USER ID used in the correlator packet header")
    INTEGRATION_PERIOD = BitField(CONTROL, 0x04, 0, width=32, doc="Duration of te integration period -1")
    BINS_PER_FRAME     = BitField(CONTROL, 0x05, 0, width=8, doc="Number of frequency bins per frame")

    # Status registers
    STATUS_BYTE = BitField(STATUS, 0x00, 0, width=8, doc="Status byte")
    IN_FRAME_CTR          = BitField(STATUS, 0x01, 0, width=8, doc="Input frame counter")
    OUT_FRAME_CTR          = BitField(STATUS, 0x02, 0, width=8, doc="Output frame counter")

    def __init__(self, fpga_instance, base_address, instance_number, verbose=0):
        super(CORR_core, self).__init__(fpga_instance, base_address, instance_number)
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

    def init(self):
        """ Inisializes all modules of a correlator block."""
        # self.CH_DIST.init()
        # self.ACC.init()
        self.SOFT_RESET = self.instance_number!=0
        self.INTEGRATION_PERIOD = 64-1

    def status(self):
        """Displays the status of al the correlator blocks"""
        print '======= CORR.core[%i] =============' % self.instance_number
        # self.CH_DIST.status()



class CORR(object):
    """ Instantiates a container for all correlators blocks"""

    def __init__(self, fpga_instance, base_address, address_increment, verbose=0):
        self.fpga = fpga_instance
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.corr = []
        for i in range(self.fpga.NUMBER_OF_CORRELATORS):
            self.corr.append(CORR_core(self.fpga, base_address + i * address_increment, i))

    def __getitem__(self, key):
        """    Returns the correlator instance specified by the index"""
        return self.corr[key]



    def init(self):
        """ Initializes all correlators"""
        for corr in self.corr:
            corr.init()


    def status(self):
        """ Displays the status of all correlators"""
        for corr in self.corr:
            corr.status()
