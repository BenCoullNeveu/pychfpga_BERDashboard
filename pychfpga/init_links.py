import numpy as np

def init_links(ib, frames_per_packet=3, cb1_lanes=16, cb1_bins=64, cb2_lanes=8, cb2_bins=1, cb2_bypass=False, bp_bypass=1):
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

    for bs in cb1:
        bs.GROUP_FRAMES = frames_per_packet
        bs.NUMBER_OF_LANES = cb1_lanes
        bs.select_bins(np.arange(cb1_bins) * cb1_minimum_bin_spacing)
    #cb1.configure(cb1_bins)

    for bs in cb2:
        if cb2_bypass:
            bs.write(0, 0x41)
        else:
            bs.write(0, 0x01)
        bs.NUMBER_OF_FRAMES_PER_PACKET = frames_per_packet
        bs.NUMBER_OF_LANES = cb2_lanes
        bs.NUMBER_OF_BINS_PER_FRAME = cb1_bins
        bs.NUMBER_OF_WORDS_PER_BIN = cb1_lanes/4
        bs.select_bins(np.arange(cb2_bins) * cb2_minimum_bin_spacing)
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
