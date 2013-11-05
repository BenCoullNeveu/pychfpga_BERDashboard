#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
GPU.py module 
    Implements interface to the GPU links

History:
    2013-10-29 : JFC : Created 
"""
import logging
from Module import Module_base, BitField




class GTX_COMMON_base(Module_base):
    """ Implements interface to one of the COMMON """


    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    LINK_ENABLE           = BitField(CONTROL, 0, 0, doc='When 1, enables trsnamission of data over the link.')
    TEST_ENABLE           = BitField(CONTROL, 0, 1, doc='When 1, enables trsnamission of test data over the link. Requires LINK_ENABLE=1.')
    RESET           = BitField(CONTROL, 0, 2, doc='The cores are reset when this signal goes from 1 to 0')

    PCS_LOCK           = BitField(STATUS, 0, 0, doc='PCS Lock from core_status vector')
    FEC_OK             = BitField(STATUS, 0, 1, doc='FEC OK from core_status vector')
    TRAINING_DONE      = BitField(STATUS, 0, 2, doc='TRAINING_DONE from core_status vector')
    AUTONEG_DONE       = BitField(STATUS, 0, 3, doc='AUTONEG_DONE from core_status vector')
    AUTONEG_ENABLE     = BitField(STATUS, 0, 4, doc='AUTONEG_ENABLE from core_status vector')
    AUTONEG_LINK_UP    = BitField(STATUS, 0, 5, doc='AUTONEG_LINK_UP from core_status vector. ')
    CORE_VECT_RESERVED = BitField(STATUS, 0, 6, width=2, doc='Reserved core_status vector bits')

    TX_RESET_DONE      = BitField(STATUS, 1, 7, doc='')
    RX_RESET_DONE      = BitField(STATUS, 1, 6, doc='')
    QPLL_LOCK          = BitField(STATUS, 1, 5, doc='')
    QPLL_RESET         = BitField(STATUS, 1, 4, doc='')

    FRAME_CTR         = BitField(STATUS, 2, 0, width=8, doc='')


    def __init__(self, fpga, instance_number):
        self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        super(self.__class__, self).__init__(fpga, fpga.GPU_PORT[0], instance_number)




    def init(self):
        """ Initializes the antenna modules""" 
        self.logger.info('Initializing GPU GTX_COMMON  #%i' % self.instance_number)


    def status(self):
        """ Displays the status of the antenna modules""" 
        self.logger.info('--- GPU GTX COMMON %i ' % self.instance_number)


class GPU_base(object):
    """ Instantiates a container for all the GPU link ressources """

    def __init__(self, fpga, verbose=0):
        self.fpga = fpga
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

        self.GTX_COMMON = []
        for i in range(fpga.NUMBER_OF_GPU_LINKS):
            self.GTX_COMMON.append(GTX_COMMON_base(fpga, i))

    def __getitem__(self, key):
        """If the user indexes this object (ANT[n] instead of ANT) then return the antenna processor instance"""
        return self.GTX_COMMON[key]

    def __len__(self):
        """Returns the number of antennas"""
        return len(self.GTX_COMMON)


    def init(self):
        """ Initializes the GPU links""" 
        for (i, gtx) in enumerate(self.GTX_COMMON):
            self.logger.debug('Initializing GPU GTX COMMON #%i' % i)
            gtx.init()

    def status(self):
        """ Displays the status of the GPU GTX""" 
        for gtx in self.GTX_COMMON:
            gtx.status()
