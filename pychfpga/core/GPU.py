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


    QPLL_LOCK          = BitField(STATUS, 1, 5, doc='')
    QPLL_RESET         = BitField(STATUS, 1, 4, doc='')

# Add DRP registers here...


    def __init__(self, fpga_instance, base_address, instance_number):
        # self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        super(self.__class__, self).__init__(fpga_instance, base_address, instance_number)

    def init(self):
        """ Initializes the antenna modules"""
        self.logger.info('Initializing GPU GTX_COMMON  #%i' % self.instance_number)

    def status(self):
        """ Displays the status of the antenna modules"""
        self.logger.info('--- GPU GTX COMMON %i ' % self.instance_number)


class GTX_CHANNEL_base(Module_base):
    """ Implements interface to a GTX_CHANNEL block """


    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # PCS_LOCK           = BitField(STATUS, 0, 0, doc='PCS Lock from core_status vector')
    # FEC_OK             = BitField(STATUS, 0, 1, doc='FEC OK from core_status vector')
    # TRAINING_DONE      = BitField(STATUS, 0, 2, doc='TRAINING_DONE from core_status vector')
    # AUTONEG_DONE       = BitField(STATUS, 0, 3, doc='AUTONEG_DONE from core_status vector')
    # AUTONEG_ENABLE     = BitField(STATUS, 0, 4, doc='AUTONEG_ENABLE from core_status vector')
    # AUTONEG_LINK_UP    = BitField(STATUS, 0, 5, doc='AUTONEG_LINK_UP from core_status vector. ')
    # CORE_VECT_RESERVED = BitField(STATUS, 0, 6, width=2, doc='Reserved core_status vector bits')

    # TX_RESET_DONE      = BitField(STATUS, 1, 7, doc='')
    # RX_RESET_DONE      = BitField(STATUS, 1, 6, doc='')

# Add DRP registers here...

    def __init__(self, fpga_instance, base_address, instance_number):
        # self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        super(self.__class__, self).__init__(fpga_instance, base_address, instance_number)




    def init(self):
        """ Initializes the GTX CHANNEL block"""
        self.logger.info('Initializing GTX_CHANNEL  #%i' % self.instance_number)


    def status(self):
        """ Displays the status of the GTX_CHANNEL"""
        self.logger.info('--- GPU GTX CHANNEL %i ' % self.instance_number)


class GPU_base(Module_base):
    """ Instantiates a container for all the GPU link ressources """

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # XGLINK common control and status registers
    CORE_RESET         = BitField(CONTROL, 0, 7, doc='The GTX cores are reset when this signal goes from 1 to 0')
    TX_DATA_LSB        = BitField(CONTROL, 3, 0, width=16, doc='24 most significant bits of the data word that can be sent manually. This is common to all lanes.')

    NUMBER_OF_QUADS    = BitField(STATUS, 0, 5, width=3, doc='Number of QUADS (QPLLs)')
    NUMBER_OF_LINKS    = BitField(STATUS, 0, 0, width=5, doc='Number of links')
    RESET_PULSE        = BitField(STATUS, 1, 5, doc='debug')
    RESET_DONE         = BitField(STATUS, 1, 4, doc='debug')
    QPLL_RESET_MON     = BitField(STATUS, 1, 4, doc='debug')

    # 10GE Link control and status registers
    RESET               = BitField(CONTROL, 4+0, 0, doc='Resets the MAC and the GTX core.')
    TEST_ENABLE         = BitField(CONTROL, 4+0, 1, doc='When 1, enables trsnamission of test packets over the link.')
    TEST_PACKET_LENGTH  = BitField(CONTROL, 4+2, 0, width=16, doc='')
    TEST_PACKET_PERIOD  = BitField(CONTROL, 4+4, 0, width=16, doc='')
    WORD_CTR            = BitField(STATUS, 2+0, 0, width=8, doc='Last 8 bits of the counter used to produce the test test pattern.')
    FRAME_CTR           = BitField(STATUS, 2+1, 0, width=8, doc='Counts the number of frames coming in on lane 0.')
    DATA_FIFO_OVERFLOW  = BitField(STATUS, 2+2, 0, width=8, doc='Indicates if the data FIFO has overflows on the last 8 GPU links. Bit 0 is for lane 0.')
    FRAME_FIFO_OVERFLOW = BitField(STATUS, 2+3, 0, width=8, doc='Indicates if the frame header FIFO has overflows on the last 8 GPU links. Bit 0 is for lane 0.')

    def __init__(self, fpga_instance, base_address, address_increment, verbose = 1):
        # self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose
        super(self.__class__, self).__init__(fpga_instance, base_address)

        i = 1

        # Instantiate QUAD objects
        self.QUAD = []
        for j in range(self.NUMBER_OF_QUADS):
            self.QUAD.append(GTX_COMMON_base(fpga_instance, base_address + i * address_increment, j))
            i += 1

        self.CHANNEL = []
        for j in range(self.NUMBER_OF_LINKS):
            self.CHANNEL.append(GTX_CHANNEL_base(fpga_instance, base_address + i * address_increment, j))
            i += 1

    def init(self):
        """ Initializes the GPU links"""
        for (i, quad) in enumerate(self.QUAD):
            self.logger.debug('Initializing GPU GTX QUAD #%i' % i)
            quad.init()

        for (i, ch) in enumerate(self.CHANNEL):
            self.logger.debug('Initializing GPU GTX CHANNEL #%i' % i)
            ch.init()

    def set_enable(self, state):
#        self.LINK_ENABLE = state
        pass

    def status(self):
        """ Displays the status of the GPU GTX hardware"""
        # for gtx in self.GTX_COMMON:
        #     gtx.status()
