import time
import numpy as np
import matplotlib.pyplot as plt

BP_RX_TO_TX_MAP = {
    # (rx_slot, rx_lane) <= (tx_slot_tx_lane)
    # Slots are numbered from 1 to 16
    # Lanes are numbered from 0 to 15. Lane 0 is internal to the FPGA.

    (1,0):(1,0), # direct internal link in FPGA
    (1,1):(12,1), (1,2):(10,11),  (1,3): (9,15),  (1,4): (6,8),  (1,5): (5,2),  (1,6): (3,8), (1,7): (8,6), (1,8):(2,10),
    (1,9):(15,3), (1,10):(16,11), (1,11):(11,13), (1,12):(14,5), (1,13):(13,1), (1,14):(4,7), (1,15):(7,13),

    (2,0):(2,0), # direct internal link in FPGA
    (2,1):(11,11), (2,2) :(16,7),  (2,3) :(12,13),  (2,4) :(6,14),  (2,5) :(5,4),  (2,6) :(15,5), (2,7) :(8,2), (2,8):(3,10),
    (2,9):(14,7),  (2,10):(13,2),  (2,11):(10,13),  (2,12):(9,13),  (2,13):(1,6),  (2,14):(4,8),  (2,15):(7,15),

    (3,0):(3,0), # direct internal link in FPGA
    (3,1):(9,12), (3,2):(12,14), (3,3):(14,11), (3,4):(11,12), (3,5):(5,8), (3,6):(2,6), (3,7):(8,4), (3,8):(4,10), (3,9):(6,4),
    (3,10):(1,4), (3,11):(15,11), (3,12):(16,12), (3,13):(10,15), (3,14):(13,4), (3,15):(7,14), (4,1):(15,2),


    (4,0):(4,0), # direct internal link in FPGA
    (4,2):(16,2), (4,3):(11,1), (4,4):(6,2), (4,5):(12,2), (4,6):(3,6), (4,7):(8,12), (4,8):(5,10), (4,9):(2,2),
    (4,10):(1,2), (4,11):(13,11), (4,12):(9,14), (4,13):(10,14), (4,14):(14,2), (4,15):(7,4),


    (5,0):(5,0), # direct internal link in FPGA
    (5,1):(9,2),  (5,2):(16,15), (5,3):(13,15),  (5,4):(15,15),  (5,5):(14,15), (5,6):(3,4),    (5,7):(8,8),  (5,8):(6,10),
    (5,9):(2,11), (5,10):(1,1),  (5,11):(10,12), (5,12):(11,14), (5,13):(4,6),  (5,14):(12,15), (5,15):(7,8),

    (6,0):(6,0), # direct internal link in FPGA
    (6,1):(16,5), (6,2):(15,13), (6,3):(9,4), (6,4):(14,14), (6,5):(13,5), (6,6):(3,2), (6,7):(8,9), (6,8):(7,10),
    (6,9):(2,12), (6,10):(1,11), (6,11):(10,2), (6,12):(12,4), (6,13):(5,6), (6,14):(4,4), (6,15):(11,4),


    (7,0):(7,0), # direct internal link in FPGA
    (7,1):(16,9), (7,2):(15,9), (7,3):(13,7), (7,4):(14,9), (7,5):(5,11), (7,6):(3,1), (7,7):(6,6), (7,8):(8,10),
    (7,9):(2,13), (7,10):(1,12), (7,11):(9,8), (7,12):(12,10), (7,13):(10,4), (7,14):(4,2), (7,15):(11,15),


    (8,0):(8,0), # direct internal link in FPGA
    (8,1):(6,11), (8,2):(16,8), (8,3):(14,8), (8,4):(15,8), (8,5):(5,12), (8,6):(3,11), (8,7):(7,6), (8,8):(9,10),
    (8,9):(2,14), (8,10):(1,13), (8,11):(10,8), (8,12):(13,8), (8,13):(12,8), (8,14):(4,1), (8,15):(11,8),

    (9,0):(9,0), # direct internal link in FPGA
    (9,1):(6,12), (9,2):(14,6), (9,3):(15,6), (9,4):(16,6), (9,5):(5,13), (9,6):(3,12), (9,7):(8,13), (9,8):(10,10),
    (9,9):(2,15), (9,10):(1,14), (9,11):(12,6), (9,12):(13,6), (9,13):(11,6), (9,14):(4,11), (9,15):(7,12),


    (10,0):(10,0), # direct internal link in FPGA
    (10,1):(6,13), (10,2):(4,12), (10,3):(7,2), (10,4):(8,14), (10,5):(5,15), (10,6):(3,13), (10,7):(9,6),
    (10,8):(11,10), (10,9):(2,1), (10,10):(1,15), (10,11):(16,14), (10,12):(15,14), (10,13):(14,13), (10,14):(13,14), (10,15):(12,11),

    (11,0):(11,0), # direct internal link in FPGA
    (11,1):(5,1), (11,2):(7,11), (11,3):(8,11), (11,4):(9,11), (11,5):(6,15), (11,6):(3,14), (11,7):(10,6),
    (11,8):(12,7), (11,9):(2,5), (11,10):(1,3), (11,11):(4,13), (11,12):(16,4), (11,13):(15,4), (11,14):(14,4), (11,15):(13,13),

    (12,0):(12,0), # direct internal link in FPGA
    (12,1):(7,1), (12,2):(8,1), (12,3):(9,1), (12,4):(10,1), (12,5):(5,14), (12,6):(3,15), (12,7):(11,2),
    (12,8):(13,10), (12,9):(2,7), (12,10):(1,5), (12,11):(15,1), (12,12):(16,1), (12,13):(14,1), (12,14):(4,14), (12,15):(6,1),

    (13,0):(13,0), # direct internal link in FPGA
    (13,1):(7,7), (13,2):(8,7), (13,3):(9,7), (13,4):(10,7), (13,5):(11,7), (13,6):(3,5), (13,7):(12,12),
    (13,8):(14,10), (13,9):(2,9), (13,10):(1,7), (13,11):(16,3), (13,12):(5,7), (13,13):(15,7), (13,14):(4,15), (13,15):(6,7),

    (14,0):(14,0), # direct internal link in FPGA
    (14,1):(7,5), (14,2):(8,5), (14,3):(9,5), (14,4):(10,5), (14,5):(11,5), (14,6):(12,5), (14,7):(13,12),
    (14,8):(15,10), (14,9):(2,8), (14,10):(1,9), (14,11):(5,5), (14,12):(6,5), (14,13):(4,5), (14,14):(3,7), (14,15):(16,13),


    (15,0):(15,0), # direct internal link in FPGA
    (15,1):(8,15), (15,2):(9,9), (15,3):(10,9), (15,4):(11,9), (15,5):(12,9), (15,6):(13,9), (15,7):(14,12),
    (15,8):(16,10), (15,9):(2,4), (15,10):(1,10), (15,11):(6,9), (15,12):(7,9), (15,13):(5,9), (15,14):(4,9), (15,15):(3,9),


    (16,0):(16,0), # direct internal link in FPGA
    (16,1):(8,3), (16,2):(9,3), (16,3):(10,3), (16,4):(11,3), (16,5):(12,3), (16,6):(13,3), (16,7):(15,12),
    (16,8):(14,3), (16,9):(7,3), (16,10):(1,8), (16,11):(5,3), (16,12):(6,3), (16,13):(4,3), (16,14):(3,3), (16,15):(2,3)
}

def scan_eye(self, horiz_offset=range(-32,32,4), vert_offset=range(-127,127,16), max_scaler = 12, ut_sign=0, prescale_step=6, plot=1):
        """
        Return a (M x N) matrix of BER values for M horizontal and N vertical offsets.
        Horiz_offset : -32 to 32
        Vert offset: : -127 to 127
        """
        prescale_step=4
        self.PMA_RSV2_5 = 1
        self.ES_EYE_SCAN_EN = 1
        self.ES_ERRDET_EN = 1
        self.ES_SDATA_MASK0=0x00ff
        self.ES_SDATA_MASK1=0x0000
        self.ES_SDATA_MASK2=0xFF00
        self.ES_SDATA_MASK3=0xFFFF
        self.ES_SDATA_MASK4=0xFFFF

        self.ES_QUAL_MASK0=0xFFFF
        self.ES_QUAL_MASK1=0xFFFF
        self.ES_QUAL_MASK2=0xFFFF
        self.ES_QUAL_MASK3=0xFFFF
        self.ES_QUAL_MASK4=0xFFFF

        if np.isscalar(horiz_offset):
            horiz_offset = [horiz_offset]

        if np.isscalar(vert_offset):
            vert_offset = [vert_offset]

        ber = np.zeros((len(horiz_offset), len(vert_offset)))
        prescale = 0

#        sample_list = [(ih,iv, h,v, h**2+v**2) for iv,v in enumerate(vert_offset) for ih,h in enumerate(horiz_offset)]
#
#        sample_list.sort(key=lambda x: x[4])
#        sample_list.reverse()

        for (iv,v_offset) in enumerate(vert_offset):
            ih=0
            dir = 1
            while True:
                #print ih, len(horiz_offset)
                h_offset=horiz_offset[ih]
                self.ES_VERT_OFFSET = (abs(v_offset)&0x7F) | (0x80 * (v_offset<0)) | (0x100 * bool(ut_sign))
                self.ES_HORZ_OFFSET = h_offset & 0xFFF

                print 'Horiz offset %i/%i= %i, Vert offset %i/%i= %i' % (ih, len(horiz_offset)-1, h_offset, iv, len(vert_offset)-1, v_offset)

                while True:
                    self.ES_PRESCALE = prescale
                    self.ES_CONTROL=0
                    self.ES_CONTROL=1
                    while self.ES_CONTROL_STATUS != 5:
                        #print '.',
                        time.sleep(.2)
                    error_count = self.ES_ERROR_COUNT
                    sample_count = self.ES_SAMPLE_COUNT

                    print '      Prescale=%i => %i err / %i samples '% (prescale, error_count, sample_count)
                    if sample_count < 100:
                        if prescale==0:
                            break
                        else:
                            prescale = max(0, prescale-prescale_step)
                    elif error_count < 100 :
                        if prescale == max_scaler:
                            break
                        else:
                            prescale = min(max_scaler, prescale + prescale_step)
                    else:
                        break
                if sample_count == 0:
                    sample_count =1

                sample_count *= 2**(1+prescale)
                e=float(error_count)/float(sample_count)
                print '    -> %i samples, %i errors, BER=%1.1e' % (sample_count, error_count, e)
                ber[ih,iv] = e

                if dir==-1 and (ih==old_ih or ih==0):
                    break
                elif dir==1 and ih==len(horiz_offset)-1:
                    break

                if error_count == 0:
                    if dir==1:
                        print 'swapping direction!'
                        old_ih = ih
                        dir = -1
                        ih=len(horiz_offset)-1
                    else:
                        break
                else:
                    ih=ih+dir
        #plt.imshow(np.log10(ber+1e-12), origin='lower', extent=(min(horiz_offset),max(horiz_offset),min(vert_offset),max(vert_offset)), aspect=0.1, vmin=-12, vmax=1)
        return ber

def scan_links(array, tx_power=7):
    array = [ib for ib in array if ib.is_open()]
    slot = [ib.slot_number for ib in array]
    if len(set(slot)) != len(slot):
        raise SystemError('Slot numbers are not unique!')

    #for ib in array:
    #    ib.fpga.BP_SHUFFLE.RESET=1
    #    time.sleep(0.1)
    #    ib.fpga.BP_SHUFFLE.RESET=0
    #    time.sleep(0.1)

    print 'Setting Transmitted ID'
    for ib in array:
    	ib.fpga.BP_SHUFFLE.TX_DATA_MSB = 0xFF00 + ib.slot_number
        for lane,g in enumerate(ib.fpga.BP_SHUFFLE.gtx):
            g.SOURCE_SEL=1 # 0:Send TXDATA , 1: SEND 10G Ethernet test packet
            g.LOOPBACK = 0
            #g.TXPOLARITY=0
            #g.RXPOLARITY=0
            g.TXPRBSSEL=0
            g.RXPRBSSEL=0
            #g.SCRAMBLE_EN=1
            #g.DESCRAMBLE_EN=1
            g.TXDIFFCTRL = tx_power
            g.TX_DATA_LSB = lane
            g.TXHEADER=1
            g.CAPTURE_ENABLE = 1
            g.TXPRECURSOR = 0b00000 #DFE cannot compensate pre-cursor
            g.TXPOSTCURSOR = 0b00000
            g.RXLPMEN = 0 #Go to DFE mode instead of LPM
            g.RXMONITORSEL = 1 # 1=AGC, 2=UL, 3=VP loop
            g.RX_DEBUG_CFG = 0b1011<<2
            #g.DMONITOR_CFG1 = 0
            #g.DMONITOR_CFG0 = (0b1<<15) | (0x0080 <<1) | 1
            # Configure DMONITOR to read the AGC gain
            g.DMONITOR_SELECT = 1
            g.PCS_RSVD_ATTR_BIT6 = 1
            #old=g.read_drp(0x6f)
            #g.write_drp(0x6f,old | 1<<6)
            #g.RXDFEOVRD=1
            #g.write_drp(0x1d, 0x00ea)

    print 'Resetting the GTXes'
    for ib in array:
        #ib.fpga.BP_SHUFFLE.RESET=1
        #time.sleep(0.1)
        #ib.fpga.BP_SHUFFLE.RESET=0
        #time.sleep(0.1)
        for g in ib.fpga.BP_SHUFFLE.gtx:
            g.RXDFELPMRESET=1
            g.RXDFELPMRESET=0
            #g.RXDFEOVRD=1
            #g.write_drp(0x1d, 0x1Fea)
        time.sleep(0.1)

    #time.sleep(0.5)

    print 'Checking received data'

    link_list=[]
    link_matrix = [[None]*16 for x in range(16)]
    serial_number = ['N/A'] * 16
    for ib in array:
        #print 'Slot %i' % (ib.slot_number+1)
        dest_slot = ib.slot_number
        serial_number[dest_slot] = ib.serial_number
        for lane,g in enumerate(ib.fpga.BP_SHUFFLE.gtx):
            for trial in range(3):
                rxdata = g.get_rxdata()
                #print '   Slot %i Lane %i received %08X' % (    ib.slot_number+1, lane+1,  rxdata)
                source_slot = int((rxdata >>8) & 0xFF)
                source_lane = int((rxdata) & 0xFF)
                source_valid = (rxdata >>16) == 0xFFFF
                maybe = (rxdata != 0x55555555) and (rxdata != 0xAAAAAAAA)
                if source_valid:
                    break
            if source_valid:
                print 'Slot %2i Lane %2i is receiving data from Slot %2i Lane %2i (received word = 0x%08X, RXMONITOROUT= %x, DMONITOROUT=%x)' % (ib.slot_number+1, lane+1, source_slot+1, source_lane+1, rxdata, g.RXMONITOR, g.DMONITOROUT)
                link_matrix[dest_slot][lane]='S%02iL%02i' % (source_slot+1, source_lane+1)
                if (dest_slot+1, lane+1) in BP_RX_TO_TX_MAP and BP_RX_TO_TX_MAP[(dest_slot+1, lane+1)] != (source_slot+1, source_lane+1):
                    link_matrix[dest_slot][lane] += '(S%iL%i!)' % BP_RX_TO_TX_MAP[(dest_slot+1, lane+1)]
                link_list.append(((source_slot+1, source_lane+1), (ib.slot_number+1, lane+1)))

            elif maybe:
                print 'Slot %2i Lane %2i is receiving some data but cannot determine source (received word = 0x%08X, RXMONITOROUT= %x, DMONITOROUT=%x)' % (ib.slot_number+1, lane+1, rxdata, g.RXMONITOR, g.DMONITOROUT)
                #link_matrix[dest_slot][lane]='?'
                if (dest_slot+1, lane+1) in BP_RX_TO_TX_MAP:
                    link_matrix[dest_slot][lane] = '(S%iL%i?)' % BP_RX_TO_TX_MAP[(dest_slot+1, lane+1)]
                    link_list.append((BP_RX_TO_TX_MAP[(dest_slot+1, lane+1)], (ib.slot_number+1, lane+1)))
                else:
                    link_matrix[dest_slot][lane]='?'
            #else:
            #    if (dest_slot+1, lane+1) in BP_RX_TO_TX_MAP:
            #        link_matrix[dest_slot][lane] = 'NC (S%iL%i)' % BP_RX_TO_TX_MAP[(dest_slot+1, lane+1)]

            #if source_valid or maybe:
            #    link_list.append(((source_slot+1, source_lane+1), (ib.slot_number+1, lane+1)))

    print 'Slot-> ' + ' '.join(['%-10i' % (slot+1) for slot in range(16)])
    print 'S/N -> ' + ' '.join(['%-10s' % (sn) for sn in serial_number])
    print 'Lane   ' + ' '.join(['%-10s' % '----------' for x in range(16)])

    for lane in range(15):
        print '%6i ' % (lane+1),
        for slot in range(16):
            print '%-10s' % link_matrix[slot][lane],
        print

    return link_list

def get_ber(array, link_list, period=0.1, tx_power = None):

    link_list.sort(key=lambda ((ss,sl),(ds,dl)): ss*16+ds)
    ib_map = {ib.slot_number+1:ib for ib in array}
    ber_table={}
    for ((ss,sl),(ds,dl)) in link_list:
        if ss not in ib_map or ds not in ib_map:
            continue
        source_ib = ib_map[ss]
        dest_ib = ib_map[ds]
        if not source_ib.is_open() or not dest_ib.is_open():
            continue
        source_gtx = source_ib.fpga.BP_SHUFFLE.gtx[sl-1]
        dest_gtx = dest_ib.fpga.BP_SHUFFLE.gtx[dl-1]

        if tx_power is not None:
            source_gtx.TXDIFFCTRL=tx_power

        source_gtx.TXPRBSSEL=4

        print 'Measuring BER for Slots %2i->%2i (SN%03i, GTX[%2i])=> (SN%03i, GTX[%2i])' % (ss, ds, source_ib.serial_number, sl-1,  dest_ib.serial_number, dl-1),

        # First, make sure we can get errors by setting the wrong RX PRBS Sequence
        dest_gtx.RXPRBSCNTRESET=1
        dest_gtx.RXPRBSSEL=3
        dest_gtx.RXPRBSCNTRESET=0
        t0=time.time()
        while True:
            if dest_gtx.ERR_CTR:
                break
            if time.time()-t0 < 1:
                raise SystemError('Cannot detect errors even with the wrong sequence!')

        #dest_gtx.RXPRBSCNTRESET=1
        #dest_gtx.RXPRBSCNTRESET=0
        #dest_gtx.RXPRBSCNTRESET=1
        #dest_gtx.RXPRBSCNTRESET=0
        #t0=time.time()
        #while time.time()-t0 < 13:
        #    print  dest_gtx.ERR_CTR, 'from', dest_gtx
        #    #dest_gtx.RXPRBSCNTRESET=1
        #    #dest_gtx.RXPRBSCNTRESET=0
        #    time.sleep(0.5)
        #    #if not dest_gtx.ERR_CTR:
        #    #    print 'locked',
        #    #    break
        #dest_gtx.RXPRBSCNTRESET=1
        dest_gtx.RXDFELPMRESET=1
        time.sleep(0.001)
        dest_gtx.RXDFELPMRESET=0
        time.sleep(0.001)
        dest_gtx.RXPRBSCNTRESET=1
        dest_gtx.RXPRBSSEL=4
        dest_gtx.RXDFELPMRESET=1
        time.sleep(0.001)
        dest_gtx.RXDFELPMRESET=0
        time.sleep(0.001)
        dest_gtx.RXPRBSCNTRESET=0
        time.sleep(period)
        cnt=dest_gtx.ERR_CTR
        err=(float(cnt)*16)/(period*10e9)
        err_max=(float(cnt)*16+1)/(period*10e9)

        print 'BER = %1.1e (%i errors, BER<%1.1e)' % (err, cnt, err_max)
        ber_table[(ss,ds)]=err
    return ber_table

def get_eye_matrix(array, h_step=10, v_step=40):
    link_map = scan_links(array)
    link_ber = {}

    for link in link_map:
        ((from_slot, from_lane), (to_slot, to_lane)) = link
        print  "###### running from slot %i lane %i to slot %i lane %i #######" % ( from_slot, from_lane, to_slot, to_lane)
        gtx = [ib.fpga.BP_SHUFFLE.gtx[to_lane-1] for ib in array if ib.slot_number==to_slot-1][0]
        e=scan_eye(gtx, range(-32,32,h_step), range(-127,128,v_step), plot=1)
        link_ber[link] = e
    return link_ber

def plot_eye_matrix(eye_matrix):

    plt.figure(1)
    plt.clf()

    source_slots= [ss for ((ss,sl),(ds,dl)) in eye_matrix.keys()]
    dest_slots= [ds for ((ss,sl),(ds,dl)) in eye_matrix.keys()]
    slots = sorted(set(source_slots + dest_slots))
    max_slot = max(slots)

    slot_map = {slot:ix for (ix,slot) in enumerate(slots)}
    slot_map = {x+1:x for x in range(16)}

    (fig, ax) = plt.subplots(len(slot_map), len(slot_map), sharex=True, sharey=True, subplot_kw={'axis_bgcolor':'black'})
    fig.subplots_adjust(wspace=0,hspace=0)
    fig.suptitle('MGK7BP16 10Gbps mesh eye diagrams\n TX slot #: left, Rx slot #: bottom')

    for (slot,ix) in slot_map.items():
        # Bottom images
        a=ax[ix,0]
        a.tick_params(labelsize=6)
        a.set_ylabel("TX S%02i" % (slot), fontsize=10)
        # Left images
        a=ax[len(slot_map)-1,ix]
        a.tick_params(labelsize=6)
        a.set_xlabel("RX S%02i" % (slot))
        plt.setp(a.xaxis.get_majorticklabels(), rotation=70)
        # Diagonal images
        a=ax[ix,ix]
        a.patch.set_color('black')

    for (((ss,sl),(ds,dl)), eye) in eye_matrix.items():
        a=ax[slot_map[ss],slot_map[ds]]
        a.imshow(np.log10(eye+1e-12), origin='lower', extent=(-32,32,-128,128), aspect='auto', vmin=-12, vmax=1)

    plt.draw()

def get_ber_vs_power(array, max_power, period=0.1):


    links = scan_links(array, tx_power = max_power)
    power = range(0,max_power+1)
    data = {}
    for tx_power in power:
        e = get_ber(array, links, period=period, tx_power = tx_power)
        for (link, ber) in e.items():
            if link in data:
                data[link][0].append(tx_power)
                data[link][1].append(ber)
            else:
                data[link] = [[tx_power], [ber]]
    return data

def plot_ber_vs_power(data):
    for (ss,ds),(tx_power, ber) in data.items(): print '%10s'% ((ss,ds),), ','.join(['%6.1g' % b for b in ber])
    plt.figure(1)
    plt.clf()

    for (ss,ds),(tx_power, ber) in data.items():
        plt.plot(tx_power, np.log10(np.array(ber)+1e-12), label='Slot %i=>%i' % (ss,ds))
    plt.legend()

def is_locked(rx, count=1000):
    return all([rx.BLOCK_LOCK for x in range(count)])

def reverse_bits(x):
    x = ((x & 0x5555555555555555) << 1) | ((x & 0xAAAAAAAAAAAAAAAA) >> 1)
    x = ((x & 0x3333333333333333) << 2) | ((x & 0xCCCCCCCCCCCCCCCC) >> 2)
    x = ((x & 0x0F0F0F0F0F0F0F0F) << 4) | ((x & 0xF0F0F0F0F0F0F0F0) >> 4)
    return x

def reverse_bytes(x):
    x = ((x & 0x00FF00FF00FF00FF) << 8) | ((x & 0xFF00FF00FF00FF00) >> 8)
    x = ((x & 0x0000FFFF0000FFFF) << 16) | ((x & 0xFFFF0000FFFF0000) >> 16)
    #x = ((x & 0x00000000FFFFFFFF) << 32) | ((x & 0xFFFFFFFF00000000) >> 32)
    return x

VALID_WORDS = [
"78555555", "555555D5",
"90E2BA2F", "F88090E2",
"BA2FF880", "08004500",
"0034013F", "00000111",
"D37B0202", "0201E000",
"00FCC313", "14EB0020",
"70AC73D4", "00000001",
"00000000", "00000669",
"73617461", "70000001",
"E10001B8", "5E5E0000",
"1E000000", "00000000"
]

def scramble(data):
    scrambler = 0b0101010101010101010101010101010101010101010101010101010101
    result=[]
    for d in data:
        poly = scrambler
        dout=0
        for i in range(32):
            xorBit = bool (d & (1<<i)) ^ bool(poly & (1<<38)) ^ bool(poly & (1<<57))
            poly = ((poly <<1) | xorBit) & ((1<<58)-1)
            dout |= xorBit << i
        scrambler = poly
        result.append(dout)
    return result

def serialize(data):
    stream=[]
    for d in data:
        for i in range(32):
            stream.append(bool(d&(1<<i)))
    return stream

def plot_power_vs_lane_separation(data):

    power=[]
    slot_sep=[]
    for (ss,ds),(tx_power, ber) in data.items():
        p = np.where(np.array(ber)!=0)[0]

        if len(p):
            pp=max(p)+1
        else:
            pp=0
        #print

        print '%10s' % ((ss,ds),), pp, ber
        power.append(pp)
        slot_sep.append(abs(ds-ss))
    plt.clf()
    plt.plot(slot_sep, power, '.')

def packet_length(frames_per_packet=4, number_of_lanes=4, number_of_selected_bins=8):
    data_per_frame = number_of_lanes * number_of_selected_bins
    data_flags_per_frame = number_of_selected_bins
