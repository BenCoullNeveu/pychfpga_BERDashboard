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

    RXPRBSCNTRESET = BitField(CONTROL, 0, 7, doc='Debug')
    RXPRBSSEL      = BitField(CONTROL, 0, 4, width=3, doc='Debug')
    RXCDRHOLD      = BitField(CONTROL, 0, 3, doc='Debug')
    LOOPBACK       = BitField(CONTROL, 0, 0, width=3, doc='Debug') #-- '000' = normal operation
    TXDIFFCTRL     = BitField(CONTROL, 1, 4, width=4, doc='Debug')
    TXINHIBIT      = BitField(CONTROL, 1, 3, doc='Debug')
    TXPRBSFORCEERR = BitField(CONTROL, 1, 2, doc='Debug')
    TXPOLARITY     = BitField(CONTROL, 1, 1, doc='Debug')
    RXPOLARITY     = BitField(CONTROL, 1, 0, doc='Debug')
    TXPOSTCURSOR   = BitField(CONTROL, 2, 0, width=5, doc='Debug')
    TXPRECURSOR    = BitField(CONTROL, 3, 0, width=5, doc='Debug')
    TXDATA         = BitField(CONTROL, 7, 0, width=32, doc='Debug')

    TXPRBSSEL         = BitField(CONTROL, 8, 2, width=3, doc='Debug')
    TXHEADER          = BitField(CONTROL, 8, 0, width=2, doc='Debug')
    BLOCK_LOCK_RESET  = BitField(CONTROL, 8, 5, doc='')
    SCRAMBLER_RESET   = BitField(CONTROL, 8, 6, doc='')
    UNSCRAMBLER_RESET = BitField(CONTROL, 8, 7, doc='')

    SCRAMBLE_EN    = BitField(CONTROL, 9, 0, doc='')
    DESCRAMBLE_EN  = BitField(CONTROL, 9, 1, doc='')
    CAPTURE_EN     = BitField(CONTROL, 9, 2, doc='')
    STOP_BITSLIP   = BitField(CONTROL, 9, 3, doc='')
    USER_GTTXRESET = BitField(CONTROL, 9, 4, doc='')
    USER_GTRXRESET = BitField(CONTROL, 9, 5, doc='')
    SOURCE_SEL    = BitField(CONTROL, 9, 6, doc='')
    DRP_BANK       = BitField(CONTROL, 9, 7, doc='')

    RXLPMEN       = BitField(CONTROL, 10, 6, doc='') #gt_control_bytes(i)(10)(6);
    RXDFELPMRESET = BitField(CONTROL, 10, 5, doc='') #gt_control_bytes(i)(10)(5);
    RXMONITORSEL  = BitField(CONTROL, 10, 3, width=2, doc='') #gt_control_bytes(i)(10)(4 downto 3);
    RXLPMHOLD     = BitField(CONTROL, 10, 1, width=2, doc='') #gt_control_bytes(i)(10)(2 downto 1);
    RXDFEHOLD     = BitField(CONTROL, 11, 0, width=9, doc='') # Bit 0: AGC, 1: LF, 2-5: TAP2-5, 6: UT, 7: VP, 8: OS
    RXLPMOVRD     = BitField(CONTROL, 12, 1, width=2, doc='') #gt_control_bytes(i)(10)(2 downto 1);
    RXDFEOVRD     = BitField(CONTROL, 13, 0, width=9, doc='') # Bit 0: AGC, 1: LF, 2-5: TAP2-5, 6: UT, 7: VP, 8: OS

    DMONITOROUT   = BitField(STATUS, 0, 0, width=8, doc='Debug')
    RXDATA        = BitField(STATUS, 4, 0, width=32)
    TXRESETDONE   = BitField(STATUS, 5, 7, doc='Debug')
    RXRESETDONE   = BitField(STATUS, 5, 6, doc='Debug')
    TXBUFSTATUS   = BitField(STATUS, 5, 4, width=2)
    RXBUFSTATUS   = BitField(STATUS, 5, 1, width=3)
    RXPRBSERR     = BitField(STATUS, 5, 0, doc='Debug')
    TXUSERRDY     = BitField(STATUS, 6, 0, doc='Debug')
    TX_RESETDONE  = BitField(STATUS, 6, 1, doc='Debug')
    RX_RESETDONE  = BitField(STATUS, 6, 2, doc='Debug')
    RX_CDRLOCKED  = BitField(STATUS, 6, 3, doc='Debug')
    GTTXRESET     = BitField(STATUS, 6, 4, doc='Debug')
    RXUSERRDY     = BitField(STATUS, 6, 5, doc='Debug')

    RXHEADER      = BitField(STATUS, 7, 0, width=2, doc='Debug')
    BLOCK_LOCK    = BitField(STATUS, 7, 3, doc='Debug')
    RXGEARBOXSLIP = BitField(STATUS, 7, 4, doc='Debug')
    RXHEADERVALID = BitField(STATUS, 7, 5, doc='Debug')
    GTRXRESET     = BitField(STATUS, 7, 6, doc='Debug')

    ERR_CTR       = BitField(STATUS, 11, 0, width=32)
    RXMONITOR     = BitField(STATUS, 12, 0, width=7, doc='Debug')

    RX_PRBS_ERR_CNT   = BitField(DRP, 0x015C, 0, width=16, doc="Pattern checker errour counter since last RXPRBSCNTRESET")
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



    # def read_drp(self, addr):
    #     """
    #     Reads a DRP (Dynamic Reconfigurable Port) from one of the FPGA internal devices (PLL, SYSMON, MGT etc). 'addr' is the 16-bit DRP register address.
    #     """
    #     addr = (2*addr) & 0x1FF
    #     bank = (2*addr) >> 9
    #     self.DRP_BANK = bank
    #     value= self.read(0x200+addr, type=np.dtype('<u2'))
    #     self.DRP_BANK = 0
    #     return value

    # read_DRP = read_drp

    # def write_drp(self, addr, data):
    #     """
    #     Writes a DRP (Dynamic Reconfigurable Port) of the FPGA internal devices (PLL, SYSMON, MGT etc).
    #     'addr' is the 16-bit DRP register address.
    #     """
    #     addr = (2*addr) & 0x1FF
    #     bank = (2*addr) >> 9
    #     self.DRP_BANK = bank
    #     self.write(0x200+addr, [data &0xFF, (data>>8)& 0xFF])
    #     self.DRP_BANK = 0

    # write_DRP = write_drp

    def init(self):
        """ Initializes the GTX CHANNEL block"""
        self.logger.info('Initializing GTX_CHANNEL  #%i' % self.instance_number)


    def status(self):
        """ Displays the status of the GTX_CHANNEL"""
        self.logger.info('--- GPU GTX CHANNEL %i ' % self.instance_number)

    def get_rxdata(self):
        self.CAPTURE_EN=1
        self.CAPTURE_EN=0
        return self.RXDATA

    # def scan_eye(self, horiz_offset=0, vert_offset=0, max_scaler = 15, ut_sign=0):
    #     """
    #     Return a (M x N) matrix of BER values for M horizontal and N vertical offsets.
    #     Horiz_offset : -32 to 32
    #     Vert offset: : -127 to 127
    #     """
    #     self.PMA_RSV2_5 = 1
    #     self.ES_EYE_SCAN_EN = 1
    #     self.ES_ERRDET_EN = 1
    #     self.ES_SDATA_MASK0=0x00ff
    #     self.ES_SDATA_MASK1=0x0000
    #     self.ES_SDATA_MASK2=0xFF00
    #     self.ES_SDATA_MASK3=0xFFFF
    #     self.ES_SDATA_MASK4=0xFFFF

    #     self.ES_QUAL_MASK0=0xFFFF
    #     self.ES_QUAL_MASK1=0xFFFF
    #     self.ES_QUAL_MASK2=0xFFFF
    #     self.ES_QUAL_MASK3=0xFFFF
    #     self.ES_QUAL_MASK4=0xFFFF

    #     if not np.isscalar(horiz_offset):
    #         horiz_offset = [horiz_offset]

    #     if not np.isscalar(vert_offset):
    #         vert_offset = [vert_offset]

    #     ber = zeros((len(horiz_offset), len(vert_offset)))
    #     prescale = 0

    #     sample_list = [(ih,iv, h,v, h**2+v**2) for iv,v in enumerate(vert_offset), for ih,h in enumerate(horiz_offset)]

    #     sample_list.sort(key=lambda x: x(4))
    #     sample_list.reverse()

    #     for (ih, iv, h_offset, v_offset) in sample_list:

    #         self.ES_VERT_OFFSET = (abs(v_offset)&0x7F) | (0x80 * (v_offset<0)) | (0x100 * bool(ut_sign))
    #         self.ES_HORZ_OFFSET = h_offset & 0xFFF

    #         print 'Horiz offset = %i, Vert offset = %i' % (h_offset, v_offset),

    #         while True:
    #             print '    Trying prescale=%i'%prescale
    #             self.ES_PRESCALE = prescale
    #             self.ES_CONTROL=0
    #             self.ES_CONTROL=1
    #             while self.ES_CONTROL_STATUS != 5:
    #                 print '.',
    #                 time.sleep(.2)
    #             error_count = self.ES_ERROR_COUNT
    #             sample_count = self.ES_SAMPLE_COUNT

    #             if sample_count == 32767:
    #                 if prescale == max_scale:
    #                     break
    #                 else:
    #                     prescale = min(max_scale, prescale + 2)
    #             elif sample_count < 1024:
    #                 if prescale==0:
    #                     break
    #                 else:
    #                     prescale = max(0, prescale-2)
    #             else:
    #                 break
    #         sample_count *= 2**(1+prescale)
    #         ber(ih,iv) = float(error_count)/float(sample_count)

    #     print '    -> %i samples, %i errors, BER = %1.3e' % (sample_count, error_count,  ber)
    #     return ber

class Shuffle(Module_base):
    """ Instantiates a container for all the shuffle ressources """

    # LINK_ENABLE           = BitField(CONTROL, 0, 0, doc='When 1, enables trsnamission of data over the link.')
    # TEST_ENABLE           = BitField(CONTROL, 0, 1, doc='When 1, enables trsnamission of test data over the link. Requires LINK_ENABLE=1.')
    RESET                 = BitField(CONTROL, 0, 2, doc='The cores are reset when this signal goes from 1 to 0')

    NUMBER_OF_QUADS       = BitField(STATUS, 0, 0, width=8, doc='Number of GTX quads (QPLLs)')
    NUMBER_OF_LINKS       = BitField(STATUS, 1, 0, width=8, doc='Number of lanes (GTX)')

    RESET_PULSE           = BitField(STATUS, 2, 5, doc='Debug')
    RESET_DONE            = BitField(STATUS, 2, 4, doc='Debug')
    QPLL_RESET            = BitField(STATUS, 2, 3, doc='Debug')
    # RESET_COUNTER_DONE    = BitField(STATUS, 2, 0, doc='Debug')

    FRAME_CTR             = BitField(STATUS, 3, 0, width=8, doc='Counts incoming frames on lane 0. Wraps around.')
    WORD_CTR              = BitField(STATUS, 4, 0, width=8, doc='Word counter userd to generate the test patterns.')

    def __init__(self, fpga_instance, base_address, address_increment, verbose = 1):
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

    def init(self):
        """ Initializes the GPU links"""
        for (i, qpll) in enumerate(self.qpll):
            self.logger.debug('Initializing GPU GTX QUAD #%i' % i)
            qpll.init()

        for (i, gtx) in enumerate(self.gtx):
            self.logger.debug('Initializing GPU GTX CHANNEL #%i' % i)
            gtx.init()

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
