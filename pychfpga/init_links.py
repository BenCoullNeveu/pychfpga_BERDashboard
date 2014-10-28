import numpy as np
import struct
import icecore.icebox

def init_crossbars(ib, frames_per_packet=3, cb1_lanes=16, cb1_bins=64, cb2_lanes=8, cb2_bins=1, cb2_bypass=False, bp_bypass=1):
    ib.fpga.set_ant_reset(1)
    ib.fpga.set_corr_reset(1)
    cb1=ib.fpga.CROSSBAR
    cb2=ib.fpga.CROSSBAR2
    gpu_links=ib.fpga.GPU

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
        bs.select_bins(np.arange(cb1_bins) * cb1_minimum_bin_spacing + i)
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
    ib.fpga.set_corr_reset(0)
    ib.fpga.set_ant_reset(0)

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
        print split_line
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


def shuffle_init(c, sync_board):

    tx_list=[]

    # set-up transmitters
    for i,bb in enumerate(c):

        print '**** Initializing transmitters for Slot %02i (IceBoard SN%i) ****' % (bb.slot_number+1, bb.serial_number)
        bb.fpga.set_corr_reset(0)
        bb.fpga.set_data_source('funcgen')
        # set all analog inputs to send the (slot_number, analog input) complex number on every bin
        for j in range(len(bb.fpga.ANT)):
            bb.fpga.set_funcgen_function('ab', a=(bb.slot_number+1)<<4, b=j<<4, channels=[j])

        # set the stream ID of every transmitter to (slot_number, analog input) complex number on every bin
        for j,cb in enumerate(bb.fpga.CROSSBAR):
            tx_list.append((bb.slot_number+1, j))
            cb.STREAM_ID = ((bb.slot_number+1)<<4) + j
        # Make the board respond to SYNC triggers from the backplane
        bb.fpga.REFCLK.SLAVE=1
        # Initialize the crossbars to select and send data in a specific format
        init_crossbars(bb, frames_per_packet=1, cb1_lanes=16, cb1_bins=1, cb2_lanes=4, cb2_bins=1, cb2_bypass=0)

    # set-up receivers
    for i,bb in enumerate(c):
        # Disable all receivers for which there are no transmitters
        for i,gtx in enumerate(bb.fpga.BP_SHUFFLE.gtx):
            rx = (bb.slot_number+1, i+1)
            tx = icecore.icebox.IceBox.get_matching_tx(rx)
            if tx in tx_list:
                print '%s is receiving from %s' % (rx, tx)
                gtx.USER_GTRXRESET = 0
            else:
                print '%s has no corresponding transmitter' % (rx,)
                gtx.USER_GTRXRESET = 1
                gtx.USER_RESET = 1

        bb.fpga.CROSSBAR2.SOF_WINDOW_STOP = 100
        bb.fpga.BP_SHUFFLE.reset_rx_equalizers()
        bb.fpga.REFCLK.sync() # needed

    sync_board.fpga.REFCLK.sync()

# r.fpga.CROSSBAR2[0].print_frame_info()



# crx=b[0]
# cb1=crx.fpga.CROSSBAR
# cb2=crx.fpga.CROSSBAR2
# bp=crx.fpga.BP_SHUFFLE
# rx1=bp.gtx[0]
# rx2=bp.gtx[1]
# rx3=bp.gtx[2]
# gpu=crx.fpga.GPU
# bs2=cb2[0]
