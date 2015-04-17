import numpy as np
import struct
import time
#import core.icecore.icebox

def init_crossbars(ib, frames_per_packet=3, cb1_lanes=16, cb1_bins=64, cb2_lanes=8, cb2_bins=1, cb2_bypass=False, bp_bypass=1):
    ib.set_ant_reset(1)
    ib.set_corr_reset(1)
    cb1=ib.CROSSBAR
    cb2=ib.CROSSBAR2
    gpu_links=ib.GPU

    if frames_per_packet<1 or frames_per_packet>4:
        raise Exception('Number of frames per packet must be between 1 and 4')
    if cb1_lanes % 4:
        raise Exception('Crossbar 1 number of input lanes must be a multiple of 4')
    if cb2_lanes % 2:
        raise Exception('Crossbar 2 number of input lanes must be a multiple of 2')

    words_per_bin = cb1_lanes / 4
    cb1_minimum_bin_spacing = 16
    cb2_minimum_bin_spacing = 8

    for gtx in gpu_links.CHANNEL:
        gtx.LOOPBACK = bp_bypass

    for (i, bs) in enumerate(cb1):
        bs.GROUP_FRAMES = frames_per_packet
        bs.NUMBER_OF_LANES = cb1_lanes
        tx = (ib.slot, i)
        destination_slot = ib.bp.get_matching_rx(tx)[0]
        bs.select_bins(np.arange(cb1_bins) * cb1_minimum_bin_spacing + (destination_slot-1))
        # bs.select_bins(np.arange(800))
    #cb1.configure(cb1_bins)

    for (i, bs) in enumerate(cb2):
        bs.LANE0_BYPASS = bool(cb2_bypass)
        bs.NUMBER_OF_FRAMES_PER_PACKET = frames_per_packet
        bs.NUMBER_OF_LANES = cb2_lanes
        bs.NUMBER_OF_BINS_PER_FRAME = cb1_bins
        bs.NUMBER_OF_WORDS_PER_BIN = cb1_lanes/4
        bs.select_bins(np.arange(cb2_bins) * cb2_minimum_bin_spacing + i)
    #cb2.configure(cb2_bins)

    header_size = 16
    packet_flags_size = 4
    eth_overhead = 42
    bp_overhead = 8
    eth_data_rate = 156.25e6 * 66 * 32/33
    bp_data_rate = 156.25e6* 50 * 32/33
    packet_rate = 800e6/2048/frames_per_packet
    cb1_payload_size = header_size + packet_flags_size + frames_per_packet * (words_per_bin * cb1_bins + cb1_bins + 1) * 4
    cb1_eth_packet_size = (cb1_payload_size+eth_overhead+7)//8*8
    cb1_eth_data_rate = cb1_eth_packet_size * packet_rate * 8

    cb1_bp_packet_size = (cb1_payload_size+bp_overhead+7)//8*8
    cb1_bp_data_rate = cb1_bp_packet_size * packet_rate * 8

    print 'CROSSBAR1 output: payload = %i bytes' % (cb1_payload_size)
    print 'Backplane links: Packet size = %i bytes, data rate = %0.2f Gbps / %0.2f Gbps (%0.2f%%)' % (cb1_bp_packet_size, cb1_bp_data_rate/1e9, bp_data_rate / 1e9, cb1_bp_data_rate/bp_data_rate*100)

    cb2_payload_size = header_size + packet_flags_size + frames_per_packet * (words_per_bin * cb2_bins* cb2_lanes + 1*cb2_bins*cb2_lanes/2 + cb2_lanes) * 4
    cb2_eth_packet_size = (cb2_payload_size + eth_overhead + 7)// 8 * 8
    cb2_eth_data_rate = cb2_eth_packet_size * packet_rate * 8
    cb2_fifo_load = cb2_bins * words_per_bin * frames_per_packet - ( cb2_bins * words_per_bin* cb2_minimum_bin_spacing* frames_per_packet / 16)
    print 'CROSSBAR2 output: payload = %i bytes' % (cb2_payload_size)
    print 'CROSSBAR2 peak FIFO load per frame: %i (Max. 16), Words per frame: %i (max %i)' % (cb2_fifo_load,cb2_payload_size/frames_per_packet, 512*bp_data_rate/32/200e6)

    if cb2_bypass:
        print 'GPU link (CROSSBAR1 data): UDP Payload = %i bytes, Ethernet packets = %i bytes, data rate = %0.2f Gbps (%0.2f%%)' % (cb1_payload_size, cb1_eth_packet_size, cb1_eth_data_rate/1e9, cb1_eth_data_rate/eth_data_rate*100)
    else:
        print 'GPU Link (CROSSBAR2 data): UDP Payload = %i bytes, Ethernet packets = %i bytes, data rate = %0.2f Gbps (%0.2f%%)' % (cb2_payload_size, cb2_eth_packet_size, cb2_eth_data_rate/1e9, cb2_eth_data_rate/eth_data_rate*100)

    #words_per_bin = cb1_lanes / 4
    #
    #
    #bs0=cb2[0]
    #bs0.write(0,0x41)
    #cb1[0].GROUP_FRAMES=1
    #cb1[0].NUMBER_OF_LANES=4
    #cb1.configure(1)
    ib.set_corr_reset(0)
    ib.set_ant_reset(0)

class GpuData(object):
    def __repr__(self):
        return '\n'.join(['%10s = %r' % (name, value) for (name, value) in vars(self).items() if not name.startswith('_') and not name=='data'])

def get_gpu_data(node_number, dna_number):
    from subprocess import Popen, PIPE
    p = Popen(['sudo','chi-exec','%i' % node_number, '/root/inspect_pkt_dna_select', 'dna%i' % dna_number], stdout=PIPE)
    (data, stderr) = p.communicate()
    split_data = data.split('\n')
    d=[]
    for line in split_data[2:]:
        if line.startswith('Packet'):
            break
        split_line = line.lstrip().split(' ')
        # print split_line
        d += [int(c,16) for c in split_line[2:2+min(len(split_line)-2, 16)] if c]
    result=GpuData()
    result.ethernet_packet_size = len(d)
    result.mac_dst = ':'.join(['%02X' % c for c in d[0:6]])
    result.mac_src = ':'.join(['%02X' % c for c in d[6:12]])
    result.ethertype = '%04X' % (d[12]*256 + d[13])
    result.ip_length = d[16]*256 + d[17]
    result.ip_protocol = d[23]
    result.ip_src = d[26:30]
    result.ip_dst = d[30:34]
    result.udp_src_port = d[34]*256 + d[35]
    result.udp_dst_port = d[36]*256 + d[37]
    result.udp_length = d[38]*256 + d[39] # includes 8 bytes of the UDP header
    result.udp_payload_length = result.udp_length-8

    d = d[42:42+result.udp_payload_length]

    header = ''.join(chr(x) for x in d[0:16])
    (result.cookie, __, result.stream_id, __, __, result.timestamp) = struct.unpack('<BBHLLL',header)
    result.source_lane_number = result.stream_id & 0x00F

    result.data = d[16:]

    print 'UDP Payload = %i bytes, Ethernet packet=%i bytes' % (result.udp_payload_length, result.ethernet_packet_size)

    return result


def shuffle_init(c, sync_board, remap=False, frames_per_packet=1, cb1_lanes=4, cb1_bins=16, cb2_lanes=2, cb2_bins=1, cb2_bypass=0):

    tx_list=[]

    # set-up transmitters
    for i,bb in enumerate(c):

        print '**** Initializing transmitters for Slot %02i (IceBoard SN%s) ****' % (bb.slot, bb.serial)
        bb.set_corr_reset(0)
        # bb.set_data_source('funcgen')
        # bb.set_funcgen_function('a', a=0)
        bb.set_data_source('adc')
        # set all analog inputs to send the (slot_number, analog input) complex number on every bin
        for j in range(len(bb.ANT)):
            bb.set_funcgen_function('ab', a=(bb.slot-1)<<4, b=j<<4, channels=[j])
            # bb.set_funcgen_function('4bit_split_ramp')
            pass
        # set the stream ID of every transmitter to (slot_number, analog input) complex number on every bin
        for j,cb in enumerate(bb.CROSSBAR):
            cb.STREAM_ID = bb.slot-1

        for j,cb in enumerate(bb.CROSSBAR2):
            cb.STREAM_ID = bb.slot-1
        # Make the board respond to SYNC triggers from the backplane
        bb.REFCLK.SLAVE=1

        for j,gtx in enumerate(bb.BP_SHUFFLE.gtx):
            tx_list.append((bb.slot, j+1))

        if remap:
            bb.CROSSBAR2.set_lane_map(compute_lane_map(bb))

        # Initialize the crossbars to select and send data in a specific format
        init_crossbars(bb, frames_per_packet=frames_per_packet, cb1_lanes=cb1_lanes, cb1_bins=cb1_bins, cb2_lanes=cb2_lanes, cb2_bins=cb2_bins, cb2_bypass=cb2_bypass)

    # set-up receivers
    for i,bb in enumerate(c):
        # Disable all receivers for which there are no transmitters
        for i,gtx in enumerate(bb.BP_SHUFFLE.gtx):
            rx = (bb.slot, i+1)
            tx = bb.bp.get_matching_tx(rx)
            if tx in tx_list:
                print '%s is receiving from %s' % (rx, tx)
                gtx.USER_GTRXRESET = 0
            else:
                print '%s has no corresponding transmitter' % (rx,)
                gtx.USER_GTRXRESET = 1
                # gtx.USER_RESET = 1

        bb.CROSSBAR2.SOF_WINDOW_STOP = 100
        bb.BP_SHUFFLE.reset_rx_equalizers()
        bb.REFCLK.sync() # needed

    soft_sync(c, sync_board)

# r.CROSSBAR2[0].print_frame_info()
def compute_lane_map(c):
    lane_map = np.zeros(16, dtype=np.int8)
    for i in range(16):
        rx = (c.slot, i)
        tx = c.bp.get_matching_tx(rx)
        print '%s is receiving from %s' % (rx, tx)
        lane_map[tx[0]-1] = i
    return lane_map

def test_sync(c, sync_board):
    sync_ctr = np.zeros(len(c), dtype=int)
    for i,bb in enumerate(c):
        bb.REFCLK.SLAVE=1
        sync_ctr[i] = bb.REFCLK.SYNC_CTR

    fail=0
    for test_number in range(10):
        print 'Trial # %i: Sending SYNC pulse from Slot %02i (Iceboard SN%s)' % (test_number+1, sync_board.slot, sync_board.serial)
        sync_board.REFCLK.sync()
        for i,bb in enumerate(c):
            new_sync_ctr = bb.REFCLK.SYNC_CTR
            diff = (new_sync_ctr - sync_ctr[i]) & 0xF
            sync_ctr[i] = bb.REFCLK.SYNC_CTR
            fail += bool(diff!=1)
            print '    Slot %02i (Iceboard SN%s): Sync counter = %2i, diff = %2i => %s' % (bb.slot, bb.serial, new_sync_ctr, diff, ('FAILED!', 'PASS')[bool(diff==1)])
        time.sleep(0.2)
    if fail:
        print 'SYNC Test has FAILED!'
    else:
        print 'SYNC Test has PASSED!'

def check_gpu_data(nodes):
    if isinstance(nodes,int):
        nodes=[nodes]
    for node in nodes:
        for port in range(8):
            errors=np.sum( np.array(get_gpu_data(node,port).data[:256])!=np.arange(256))
            print 'GPU Node %2i port %2i has %i error(s)' % (node, port, errors)
# crx=b[0]
# cb1=crx.CROSSBAR
# cb2=crx.CROSSBAR2
# bp=crx.BP_SHUFFLE
# rx1=bp.gtx[0]
# rx2=bp.gtx[1]
# rx3=bp.gtx[2]
# gpu=crx.GPU
# bs2=cb2[0]
def print_frame_info(self):
        bs = self
        ts=[]
        sid=[]

        # get 8 bits of stream ID
        self.HEADER_CAPTURE_DATA_SEL=0
        self.HEADER_CAPTURE_EN=1
        self.HEADER_CAPTURE_EN=0
        for i in range(16):
            self.HEADER_CAPTURE_LANE_SEL=i
            sid.append(self.HEADER_CAPTURE_DATA)

        # get lsb of timestamp
        self.HEADER_CAPTURE_DATA_SEL=1
        self.HEADER_CAPTURE_EN=1
        self.HEADER_CAPTURE_EN=0
        for i in range(16):
            self.HEADER_CAPTURE_LANE_SEL=i
            ts.append(self.HEADER_CAPTURE_DATA)

        for i in range(len(ts)):
            print 'Lane %02i: Stream ID=0x%02x, Frame = 0x%02x (delta = %i)' % (i, sid[i], ts[i], ts[i]-ts[0])

def reopen(boards, bitstream):
    for ib in boards:
        if ib.is_open():
            print 'IceBoard SN%i (Slot #%s) is already opened' % (ib.serial, ib.slot)
        else:
            while not ib.is_open():
                print 'Reprogramming FPGA on IceBoard SN%s ' % (ib.serial)
                try:
                    ib.set_fpga_firmware(bitstream, force=1)
                    ib.open()
                    print 'IceBoard SN%s (Slot #%i) is now opened' % (ib.serial, ib.slot)
                    break
                except:
                    print 'Failed to open IceBoard SN%s. Retrying' % (ib.serial)

def init_gains(c):
    import pickle
    for cc in c:
        try:
            g_array = pickle.load(open('/home/chime/ch_acq/gains_'+str(cc.fpga_serial_number)+'.pkl', 'rb'))
        except:
            g_array = pickle.load(open('/home/chime/ch_acq/gains.pkl', 'rb'))
            print 'Could not find gain settings for %r. Using default gain settings.' %cc
        print 'Setting gains on IceBoard SN%s' % cc.serial
        cc.set_gain(g_array)

def soft_sync(boards, sync_board):

    boards = list(boards)
    print 'Masking ADC data before sync'
    for ib in boards:
        for ant in ib.ANT:
            ant.ADCDAQ.BYTE_MASK = 0

    print 'Initiating global sync'
    sync_board.REFCLK.sync()

    print 'Unmasking ADC data'
    for ib in boards:
        for ant in ib.ANT:
            ant.ADCDAQ.BYTE_MASK = 255

def print_temperatures(boards):
    t=[(b.slot, b.serial, b.SYSMON.temperature()) for b in boards]
    t.sort()
    for (slot, serial_number, fpga_temp) in t:
        print 'Slot %2i (SN%s): FPGA %2.1f C' % (slot, serial_number, fpga_temp)

def set_adc_mask(boards, value):

    boards = list(boards)
    for ib in boards:
        for ant in ib.ANT:
            ant.ADCDAQ.BYTE_MASK = value

def print_fmc_power(boards):
    sensor_list = ['FMCA_12V0', 'FMCA_3V3','FMCA_VADJ','FMCB_12V0','FMCB_3V3','FMCB_VADJ']
    for b in boards:
        for sensor in sensor_list:
            t=b.hw.get_power(sensor)[sensor]
            if t[0] is not None:
                print '%0.1fV@%0.2fA=%0.1fW ' % (t[0], t[2], t[3]),
            else:
                print 'None                 ',
        print
