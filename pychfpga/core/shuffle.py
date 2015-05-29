#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
shuffle.py module
    Implements interface to the backplane or intercrate shuffle module

History:
    2013-10-29 : JFC : Created
"""
import numpy as np
import logging

from Module import Module_base, BitField

# Types of memory-mapped registers
CONTROL = BitField.CONTROL
STATUS = BitField.STATUS
DRP = BitField.DRP


class QPLL(Module_base):
    """ Implements interface to one of the COMMON """

    QPLL_LOCK          = BitField(STATUS, 0, 0, doc='Indicates if the QPLL is locked')

    QPLL_INIT_CFG            = BitField(DRP, 0x0030, 0, width=16, doc="0-65535")
    QPLL_LPF                 = BitField(DRP, 0x0031, 11, width=4, doc="0-15")
    QPLL_INIT_CFG            = BitField(DRP, 0x0031, 0, width=8,   doc="0-255")
    QPLL_CFG                 = BitField(DRP, 0x0032, 0, width=16, doc="0-65535")
    QPLL_REFCLK_DIV          = BitField(DRP, 0x0033, 11, width=5, doc="1: 16, 2: 0, 3: 1, 4: 2, 5: 3, 6: 5, 8: 6, 10: 7, 12: 13, 16: 14, 20: 15")
    QPLL_CFG                 = BitField(DRP, 0x0033, 0, width=11, doc="0-2047")
    QPLL_LOCK_CFG            = BitField(DRP, 0x0034, 0, width=16, doc="0-65535")
    QPLL_COARSE_FREQ_OVRD    = BitField(DRP, 0x0035, 10, width=6, doc="0-63")
    QPLL_CP                  = BitField(DRP, 0x0035, 0, width=10,  doc="0-1023")
    QPLL_DMONITOR_SEL        = BitField(DRP, 0x0036, 15,             doc="0-1")
    QPLL_FBDIV_MONITOR_EN    = BitField(DRP, 0x0036, 14,             doc="0-1")
    QPLL_CP_MONITOR_EN       = BitField(DRP, 0x0036, 13,             doc="0-1")
    QPLL_COARSE_FREQ_OVRD_EN = BitField(DRP, 0x0036, 11,             doc="0-1")
    QPLL_FBDIV               = BitField(DRP, 0x0036, 0, width=10,  doc="0-1023")
    QPLL_FBDIV_RATIO         = BitField(DRP, 0x0037, 6,              doc="0-1")
    QPLL_CLKOUT_CFG          = BitField(DRP, 0x0037, 2, width=4,   doc="0-15")
    BIAS_CFG0                = BitField(DRP, 0x003E, 0, width=16, doc="BIAS_CFG[15:0 ] 0-65535")
    BIAS_CFG1                = BitField(DRP, 0x003F, 0, width=16, doc="BIAS_CFG[31:16] 0-65535")
    BIAS_CFG2                = BitField(DRP, 0x0040, 0, width=16, doc="BIAS_CFG[47:32] 0-65535")
    BIAS_CFG3                = BitField(DRP, 0x0041, 0, width=16, doc="BIAS_CFG[63:48] 0-65535")
    COMMON_CFG0              = BitField(DRP, 0x0043, 0, width=16, doc="COMMON_CFG[15:0 ] 0-65535")
    COMMON_CFG1              = BitField(DRP, 0x0044, 0, width=16, doc="COMMON_CFG[31:16] 0-65535")


# Add DRP registers here...


    def __init__(self, fpga_instance, base_address, instance_number):
        # self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        super(self.__class__, self).__init__(fpga_instance, base_address, instance_number)

    def init(self):
        """ Initializes the antenna modules"""
        self.logger.info('Initializing BP Shuffle QPLL #%i' % self.instance_number)


    def status(self):
        """ Displays the status of the antenna modules"""
        return self.read_all_fields()

class GTX(Module_base):
    """ Implements interface to a GTX_CHANNEL block """


    USER_RESET     = BitField(CONTROL, 0, 7, doc='')
    USER_GTTXRESET = BitField(CONTROL, 0, 6, doc='')
    TXINHIBIT      = BitField(CONTROL, 0, 5, doc='Debug')
    TXPOSTCURSOR   = BitField(CONTROL, 0, 0, width=5, doc='Debug')

    TXDIFFCTRL     = BitField(CONTROL, 1, 4, width=4, doc='Debug')
    LOOPBACK       = BitField(CONTROL, 1, 0, width=3, doc='Debug') #-- '000' = normal operation

    SOURCE_SEL     = BitField(CONTROL, 2, 7, doc='')
    TXPRECURSOR    = BitField(CONTROL, 2, 2, width=5, doc='Debug')
    TXHEADER       = BitField(CONTROL, 2, 0, width=2, doc='Debug')

    TX_DATA_LSB    = BitField(CONTROL, 3, 0, width=8, doc='Debug')

    RXDFELPMRESET    = BitField(CONTROL, 4, 7, doc='') #gt_control_bytes(i)(10)(5);
    USER_GTRXRESET   = BitField(CONTROL, 4, 6, doc='')
    RXLPMEN          = BitField(CONTROL, 4, 5, doc='') #gt_control_bytes(i)(10)(6);
    RXMONITORSEL     = BitField(CONTROL, 4, 3, width=2, doc='') #gt_control_bytes(i)(10)(4 downto 3);
    CAPTURE_ENABLE   = BitField(CONTROL, 4, 2, doc='')
    BLOCK_LOCK_RESET = BitField(CONTROL, 4, 1, doc='')

    # SCRAMBLER_RESET    = BitField(CONTROL, 0, 5, doc='')
    # DESCRAMBLER_RESET  = BitField(CONTROL, 0, 4, doc='')
    # SCRAMBLER_ENABLE   = BitField(CONTROL, 0, 3, doc='')
    # DESCRAMBLER_ENABLE = BitField(CONTROL, 0, 2, doc='')

    RXPRBSCNTRESET = BitField(CONTROL, 5, 7, doc='Debug')
    TXPRBSFORCEERR = BitField(CONTROL, 5, 6, doc='Debug')
    TXPRBSSEL      = BitField(CONTROL, 5, 3, width=3, doc='Debug')
    RXPRBSSEL      = BitField(CONTROL, 5, 0, width=3, doc='Debug')


    # RXCDRHOLD      = BitField(CONTROL, 0, 3, doc='Debug')
    # TXPOLARITY     = BitField(CONTROL, 1, 1, doc='Debug')
    # RXPOLARITY     = BitField(CONTROL, 1, 0, doc='Debug')

    # BLOCK_LOCK_RESET  = BitField(CONTROL, 8, 5, doc='')
    # SCRAMBLER_RESET   = BitField(CONTROL, 8, 6, doc='')
    # UNSCRAMBLER_RESET = BitField(CONTROL, 8, 7, doc='')

    # SCRAMBLE_EN    = BitField(CONTROL, 9, 0, doc='')
    # DESCRAMBLE_EN  = BitField(CONTROL, 9, 1, doc='')
    # CAPTURE_EN     = BitField(CONTROL, 9, 2, doc='')
    # STOP_BITSLIP   = BitField(CONTROL, 9, 3, doc='')
    # DRP_BANK       = BitField(CONTROL, 9, 7, doc='')

    # RXLPMHOLD     = BitField(CONTROL, 10, 1, width=2, doc='') #gt_control_bytes(i)(10)(2 downto 1);
    # RXDFEHOLD     = BitField(CONTROL, 11, 0, width=9, doc='') # Bit 0: AGC, 1: LF, 2-5: TAP2-5, 6: UT, 7: VP, 8: OS
    # RXLPMOVRD     = BitField(CONTROL, 12, 1, width=2, doc='') #gt_control_bytes(i)(10)(2 downto 1);
    # RXDFEOVRD     = BitField(CONTROL, 13, 0, width=9, doc='') # Bit 0: AGC, 1: LF, 2-5: TAP2-5, 6: UT, 7: VP, 8: OS

    TX_RESETDONE  = BitField(STATUS, 0, 7, doc='Debug')
    RX_RESETDONE  = BitField(STATUS, 0, 6, doc='Debug')
    TXBUFSTATUS   = BitField(STATUS, 0, 4, width=2)
    TXRESETDONE   = BitField(STATUS, 0, 3, doc='Debug')
    RXRESETDONE   = BitField(STATUS, 0, 2, doc='Debug')
    BLOCK_LOCK    = BitField(STATUS, 0, 1, doc='Debug')

    RXHEADER      = BitField(STATUS, 1, 6, width=2, doc='Debug')
    RXBUFSTATUS   = BitField(STATUS, 1, 0, width=3)

    RXMONITOR     = BitField(STATUS, 2, 0, width=7, doc='Debug')

    RXDATA        = BitField(STATUS, 6, 0, width=32)

    ERR_CTR       = BitField(STATUS, 10, 0, width=32)

    DMONITOROUT   = BitField(STATUS, 11, 0, width=8, doc='Debug')

    # RXPRBSERR     = BitField(STATUS, 5, 0, doc='Debug')
    # TXUSERRDY     = BitField(STATUS, 6, 0, doc='Debug')
    # RX_CDRLOCKED  = BitField(STATUS, 6, 3, doc='Debug')
    # GTTXRESET     = BitField(STATUS, 6, 4, doc='Debug')
    # RXUSERRDY     = BitField(STATUS, 6, 5, doc='Debug')

    # RXGEARBOXSLIP = BitField(STATUS, 7, 4, doc='Debug')
    # RXHEADERVALID = BitField(STATUS, 7, 5, doc='Debug')
    # GTRXRESET     = BitField(STATUS, 7, 6, doc='Debug')


    RX_PRBS_ERR_CNT   = BitField(DRP, 0x015C, 0, width=16, doc="Pattern checker error counter since last RXPRBSCNTRESET")
    GEARBOX_MODE      = BitField(DRP, 0x01C, 0, width=3, doc="")
    RXGEARBOX_EN      = BitField(DRP, 0x04b, 15, doc="")
    TXGEARBOX_EN      = BitField(DRP, 0x01c, 5, doc="")
    TXBUF_EN          = BitField(DRP, 0x01c, 14, doc="")
    RXBUF_EN          = BitField(DRP, 0x09d, 1, doc="")

    RX_DEBUG_CFG      = BitField(DRP, 0x0A5, 0, width=12, doc='')
    DMONITOR_CFG0     = BitField(DRP, 0x086, 0, width=16, doc='Bits 15:0 of the DMONITOR_CFG register. Bit 15 should always be 1. Bit 0 enables DMONITOR output when 1.')
    DMONITOR_CFG1     = BitField(DRP, 0x087, 0, width=8, doc='Bits 23:16 of the DMONITOR_CFG register. Should always be 0x00')
    DMONITOR_SELECT   = BitField(DRP, 0x086, 0, doc='Bits 0 of the DMONITOR_CFG register. Enables DMONITOR output when 1.')
    PCS_RSVD_ATTR_BIT6= BitField(DRP, 0x06F, 6, doc='Bit 6 of the PCS_RSVD_ATTR. Must be 1 to use DMONITOR.')
    RX_DFE_GAIN_CFG0  = BitField(DRP, 0x01D, 0, width=16, doc='Bits 15:0 of RX_DFE_GAIN_CFG')
    RX_DFE_GAIN_CFG0  = BitField(DRP, 0x01E, 0, width=7, doc='Bits 22:16 of RX_DFE_GAIN_CFG')
    ES_PMA_CFG        = BitField(DRP, 0x0A6, 0, width=9, doc='')
    ES_ERRDET_EN      = BitField(DRP, 0x03D, 9, doc='') #    0 FALSE 0 TRUE 1
    ES_EYE_SCAN_EN    = BitField(DRP, 0x03D, 8, doc='') #    0 FALSE 0 TRUE 1
    ES_CONTROL        = BitField(DRP, 0x03D, 0, width=6, doc='') #  5:0 0-63 0-63
    PMA_RSV2_5        = BitField(DRP, 0x082, 5, doc="Must be '1' to enable the Eye Scan feature")

    ES_QUALIFIER0     = BitField(DRP, 0x02C, 0, width=16, doc='')# 15:0  15:0 0-65535 0-65535
    ES_QUALIFIER1     = BitField(DRP, 0x02D, 0, width=16, doc='')# 15:0  31:16 0-65535 0-65535
    ES_QUALIFIER2     = BitField(DRP, 0x02E, 0, width=16, doc='')# 15:0  47:32 0-65535 0-65535
    ES_QUALIFIER3     = BitField(DRP, 0x02F, 0, width=16, doc='')# 15:0  63:48 0-65535 0-65535
    ES_QUALIFIER4     = BitField(DRP, 0x030, 0, width=16, doc='')# 15:0  79:64 0-65535 0-65535
    ES_QUAL_MASK0     = BitField(DRP, 0x031, 0, width=16, doc='')# 15:0  15:0 0-65535 0-65535
    ES_QUAL_MASK1     = BitField(DRP, 0x032, 0, width=16, doc='')# 15:0  31:16 0-65535 0-65535
    ES_QUAL_MASK2     = BitField(DRP, 0x033, 0, width=16, doc='')# 15:0  47:32 0-65535 0-65535
    ES_QUAL_MASK3     = BitField(DRP, 0x034, 0, width=16, doc='')# 15:0  63:48 0-65535 0-65535
    ES_QUAL_MASK4     = BitField(DRP, 0x035, 0, width=16, doc='')# 15:0  79:64 0-65535 0-65535
    ES_SDATA_MASK0    = BitField(DRP, 0x036, 0, width=16, doc='')# 15:0  15:0 0-65535 0-65535
    ES_SDATA_MASK1    = BitField(DRP, 0x037, 0, width=16, doc='')# 15:0  31:16 0-65535 0-65535
    ES_SDATA_MASK2    = BitField(DRP, 0x038, 0, width=16, doc='')# 15:0  47:32 0-65535 0-65535
    ES_SDATA_MASK3    = BitField(DRP, 0x039, 0, width=16, doc='')# 15:0  63:48 0-65535 0-65535
    ES_SDATA_MASK4    = BitField(DRP, 0x03A, 0, width=16, doc='')# 15:0  79:64 0-65535 0-65535
    ES_PRESCALE       = BitField(DRP, 0x03B, 11, width=5, doc='')# 15:11 4:0 0-31 0-31
    ES_VERT_OFFSET    = BitField(DRP, 0x03B, 0, width=9, doc='')# 8:0   8:0 0-511 0-511
    ES_HORZ_OFFSET    = BitField(DRP, 0x03C, 0, width=12, doc='')# 11:0  11:0 0-4095 0-4095

    ES_ERROR_COUNT    = BitField(DRP, 0x14F, 0, width=15, doc='')
    ES_SAMPLE_COUNT   = BitField(DRP, 0x150, 0, width=15, doc='')
    ES_CONTROL_STATUS = BitField(DRP, 0x151, 0, width=4, doc='')

# Add DRP registers here...

    def __init__(self, fpga_instance, base_address, instance_number):
        # self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        super(self.__class__, self).__init__(fpga_instance, base_address, instance_number)
        self._lock()

    def init(self):
        """ Initializes the GTX CHANNEL block"""
        self.logger.info('Initializing GTX_CHANNEL  #%i' % self.instance_number)
        self.configure()
        self.reset_rx_equalizer()

    def status(self):
        """ Displays the status of the GTX_CHANNEL"""
        self.logger.info('--- GPU GTX CHANNEL %i ' % self.instance_number)

    def get_rxdata(self):
        self.CAPTURE_ENABLE=1
        self.CAPTURE_ENABLE=0
        return self.RXDATA

    def configure(self):
        """ Execute only when there is a clock """
        self.SOURCE_SEL=0 # 0:Send user packets, 1: send TXDATA word
        self.LOOPBACK = 0
        # self.TXPOLARITY=0
        # self.RXPOLARITY=0
        self.TXPRBSSEL=0
        self.RXPRBSSEL=0
        self.TXDIFFCTRL = 8
        self.TXPRECURSOR = 0b00000 #DFE cannot compensate pre-cursor
        self.TXPOSTCURSOR = 0b00000
        self.RXMONITORSEL = 1 # 1=AGC, 2=UL, 3=VP loop
        self.RX_DEBUG_CFG = 0b1011<<2
        self.DMONITOR_SELECT = 1
        self.PCS_RSVD_ATTR_BIT6 = 1

    def reset_rx_equalizer(self):
        """ Execute only when there is a clock """
        self.RXDFELPMRESET=1
        self.RXDFELPMRESET=0

    def capture_rx_words(self, number_of_words = 1000):
        """ Return a unique set of words seen on the rx link.
        'number_of_words' words are sampled randomly, so not all words in a packet may appear in the set.
        The values are resturned as a 8-digit hex value string.
        """
        return set(['%08x' % self.get_rxdata() for x in xrange(number_of_words)])

class Shuffle(Module_base):
    """ Instantiates a container for all the shuffle ressources """

    # # LINK_ENABLE           = BitField(CONTROL, 0, 0, doc='When 1, enables trsnamission of data over the link.')
    # # TEST_ENABLE           = BitField(CONTROL, 0, 1, doc='When 1, enables trsnamission of test data over the link. Requires LINK_ENABLE=1.')
    # RESET                 = BitField(CONTROL, 0, 2, doc='The cores are reset when this signal goes from 1 to 0')

    # XGLINK common control and status registers
    CORE_RESET      = BitField(CONTROL, 0, 7, doc='The GTX cores are reset when this signal goes from 1 to 0')
    TX_DATA_MSB     = BitField(CONTROL, 3, 0, width=16, doc='24 most significant bits of the data word that can be sent manually. This is common to all lanes.')

    NUMBER_OF_QUADS = BitField(STATUS, 0, 5, width=3, doc='Number of QUADS (QPLLs)')
    NUMBER_OF_LINKS = BitField(STATUS, 0, 0, width=5, doc='Number of links')
    RESET_PULSE     = BitField(STATUS, 1, 5, doc='debug')
    RESET_DONE      = BitField(STATUS, 1, 4, doc='debug')
    QPLL_RESET_MON  = BitField(STATUS, 1, 3, doc='debug')

    # backplane link-specific registers
    BYPASS          = BitField(CONTROL, 4+0, 0, doc='Completely bypasses the backplane shuffle and connects CROSSBAR1 output directly to CROSSBAR2 input.')
    TX_TEST_ENABLE  = BitField(CONTROL, 4+0, 1, doc='')
    RESET_STATS     = BitField(CONTROL, 4+0, 3, doc='')
    LANE_SEL        = BitField(CONTROL, 4+0, 4, width=4, doc='')

    FIFO_OVERFLOW   = BitField(STATUS, 2+0, 0, doc='Sticky fifo overflow bit for the selected lane. Is cleared when RESET_STATS=1.')
    RESET_MON       = BitField(STATUS, 2+0, 1, doc='State of the reset line')
    TEST_CTR        = BitField(STATUS, 2+0, 2, width=6, doc='State of the test pattern counter')
    RX_ERROR_CTR    = BitField(STATUS, 2+2, 0, width=16, doc='Current value of the error counter for the selected lane. Saturates at 255. Is cleared when RESET_STATS=1.')

    def __init__(self, fpga_instance, base_address, address_increment, verbose=1):
        # self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        self.verbose = verbose
        super(self.__class__, self).__init__(fpga_instance, base_address)

        i = 1

        # Instantiate QUAD objects
        self.qpll = []
        for j in range(self.NUMBER_OF_QUADS):
            self.qpll.append(QPLL(fpga_instance, base_address + i * address_increment, j))
            i += 1

        self.gtx = []
        for j in range(self.NUMBER_OF_LINKS):
            self.gtx.append(GTX(fpga_instance, base_address + i * address_increment, j))
            i += 1

        self._lock()

    def init(self):
        """ Initializes the GPU links"""

        for (i, qpll) in enumerate(self.qpll):
            self.logger.debug('Initializing Backplane link QUAD #%i' % i)
            qpll.init()

        for (i, gtx) in enumerate(self.gtx):
            self.logger.debug('Initializing backplane link GTX #%i' % i)
            gtx.init()

    def reset_rx_equalizers(self):
        for g in self.gtx:
            g.reset_rx_equalizer()

    def status(self):
        """ Displays the status of the GPU GTX hardware"""

        print 'Common Bitfields'
        for (name, value) in self.read_all_fields():
            print '    %s = %i, 0x%X, %s' % (name, value, value, bin(value))

        for (i, qpll) in enumerate(self.qpll):
            print 'QPLL[%i] Bitfields' % i
            for (name, value) in qpll.read_all_fields():
                print '    %s = %i, 0x%X, %s' % (name, value, value, bin(value))

        for (i, gtx) in enumerate(self.gtx):
            print 'GTX[%i] Bitfields' % i
            for (name, value) in gtx.read_all_fields():
                print '    %s = %i, 0x%X, %s' % (name, value, value, bin(value))
