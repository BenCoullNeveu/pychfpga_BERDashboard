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
import time
import logging
import numpy as np


from Module import Module_base, BitField

#############################################
# Basic Geometry of the firmware correlator
#############################################

# Driving parameters
NCHAN = 16  # Number of channels on which to generate N-squared products
NBINS_TOTAL = 1024  # Number of frequency bins to process
NPROD_PER_CMAC = 512  # Number of products per CMAC, limited by BRAM size (512 x (18+18) bits for the accumulator & capture RAM)
NCLOCKS_PER_BIN = 4  # Number of clocks that in which all products of one bin must be computed. This matches how many clocks is needed to receive all the channels of one bin

# Derived parameters
NPROD_TOTAL = NCHAN * (NCHAN + 1) / 2  # Total number of products per correlator frame
NI_CLOCKS_PER_BIN = NCHAN / 2  # Clocks per bin of a straight Non-interleaved correlator architecture using the minimal amount of CMACs
CMAC_INTERLEAVE_FACTOR = NI_CLOCKS_PER_BIN / NCLOCKS_PER_BIN
NI_CMAC_PER_CORR = (NCHAN + 1)  # number of CMACs per correlator if computations are done in NI_CLOCKS_PER_BIN clocks
NCMAC_PER_CORR = CMAC_INTERLEAVE_FACTOR * NI_CMAC_PER_CORR # Number of interleaved CMACs per core needed to make the computations in the target number of clocks
NBINS_PER_CMAC = NPROD_PER_CMAC / NCLOCKS_PER_BIN
NBINS_PER_CORR = NBINS_PER_CMAC # = 128
NCORR = NBINS_TOTAL / NBINS_PER_CORR  # = 8

class CORR_core(Module_base):
    """ Implements interface to one of the correlator"""

    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # Control registers
    SOFT_RESET         = BitField(CONTROL, 0x00, 7, doc="Resets this correlator core.")
    AUTOCORR_ONLY         = BitField(CONTROL, 0x00, 6, doc="Force the correlator input to be 0x10101010")
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
        # self.SOFT_RESET = self.instance_number!=0
        self.INTEGRATION_PERIOD = 16384-1

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
        self.NUMBER_OF_CORRELATED_CHANNELS = 16
        self.NUMBER_OF_CMACS_PER_CORRELATOR = 2*(self.NUMBER_OF_CORRELATED_CHANNELS + 1) # per correlator
        self.PRODUCTS_PER_BIN = self.NUMBER_OF_CORRELATED_CHANNELS / 4  # per CMAC

        for corr in self.corr:
            corr.init()


    def status(self):
        """ Displays the status of all correlators"""
        for corr in self.corr:
            corr.status()

    def start_correlator(self, integration_period=16384, autocorr_only=False, correlators=None, bandwidth_limit=0.5e9, verbose=1):
        """ Start the correlator with specified parameters.

        """

        if correlators is None:
            correlators = range(self.fpga.NUMBER_OF_CORRELATORS)

        Ncorr = len(set(correlators)) # Number of active correlators
        Ncmac = 4 if autocorr_only else self.NUMBER_OF_CMACS_PER_CORRELATOR
        Nprod = self.PRODUCTS_PER_BIN * self.fpga.FRAME_LENGTH / 2 / self.fpga.NUMBER_OF_CORRELATORS  # assumes the CROSSBAR is setup this way...
        frame_rate = self.fpga.FRAME_RATE
        integ_rate = frame_rate / integration_period
        cmac_frame_size = (42 + 12 + 5*Nprod) # for all specified correlators, in bytes
        all_corr_frame_size = Ncorr * Ncmac * cmac_frame_size # for all specified correlators, in bytes

        bit_rate = integ_rate * all_corr_frame_size * 8
        min_integ_period = frame_rate / (bandwidth_limit/8/all_corr_frame_size)
        autocorr_only_bit_rate = integ_rate * Ncorr * 4 * cmac_frame_size
        if verbose:
            print 'Integration rate: %.1f integ/s (%.3fs/integ)' % (integ_rate, 1/integ_rate)
            print 'Bit rate =%.3f Gbps' % ( bit_rate/ 1e9)
        if bit_rate > bandwidth_limit:
            raise ValueError('The correlator setting would make it produce %.3f Gbps of data, which exceeds the specified bandwith '
                             'limit of %.3f Gbps. Try using a longer integration period (%i frames min).'
                             'Note that sending only the autocorrlation products with autocorr_only=True will produce %.3f Gbps)' %
                             (bit_rate/1e9, bandwidth_limit/1e9, min_integ_period, autocorr_only_bit_rate/1e9))

        self.fpga.set_corr_reset(1)
        for i, corr in enumerate(self.corr):
            corr.SOFT_RESET = 1 # make sure we stop sending readouts in progres
            corr.INTEGRATION_PERIOD = integration_period - 1
            corr.AUTOCORR_ONLY = autocorr_only
            corr.SOFT_RESET = i not in correlators
        self.fpga.set_corr_reset(0)

    def stop_correlator(self):
        """ Stop all correlator cored from sending data.
        """
        for corr in self.corr:
            corr.SOFT_RESET = 1

###################################################
# Functions to support correlator data processing
###################################################

def get_raw_corr_map():
    """
    Creates a map that maps a correlator sample indexed by (correlator_number,
    cmac_number, product_number) into a index (bin_number, channel_x,
    channel_y).

    This map can be used to remap the raw correlator packets contents into a more usefully indexed array.

    Returns:
        A numpy array such as::

            map(corr, cmac, prod) = (bin, i, j)


    The basic correlator structure is made of a fixed array (Y) of N samples
    and a rotating array (X) of also N samples. On each clock, we rotate X,
    but Y is fixed.

    We treat the diagonal products (autocorrelations) separately from the
    upper triangle, with their own multipliers. This way, we can produce only
    autocorrelations if needed.

    The upper triangle consist of N*(N-1)/2 products. We can compute the
    products in N/2 clocks using N-1 multipliers. On the first clock, the N-1
    multipliers compute the N-1 products that have a lag of 1 (e.g ((1,0),
    (2,1) ...). On the second clock, we compute the N-2 products with a lag of
    2, and 1 product with a lag of N-1, so we keep all N-1 multipliers busy.
    On clock N/2, we compute the N/2 products with lag N/2 and N/2-1 product
    with lag N/2+1.

    We need two multipliers to also compute the N autocorrelations in N/2
    clocks. One multiplier proguce the products for (0,0), (1,1), ... (N/2-1,
    N/2-1), while the second multiplier produce the products of (N/2, N/2) ...
    (N-1, N-1).

    In total, we use N-1 multipliers for the upper triangle, and 2 multipliers
    for the diagonal, with a total of N+1 multipliers per correlator.

    CMAC 0 is for the lower channel autocorrelations, CMAC1 for the upper
    channel autocorrelations, and CMAC 2 ... N are for the upper triangle
    computations.

    In practice, the data arrives 4 samples at a time (four (4+4) bit complex
    numbers in a 32-bit word). This means that a new data set arrives every
    N/4 clock. The example given above takes N/2 clocks to compute all
    products, which is 2x too slow.  To solve the problem we double the number
    of multipliers to 2*(N+1), and products are computed two at a time. The
    extra set of multipliers is interleaved with th eoriginal ones, meaning
    that the data will come out as if we were computing corr0:clk0,
    corr0:clk1, corr1:clk0, corr1:clk1  etc.

    For the computation below, we assume a non-interleaves correlator that
    compute the products with N+1 multipliers in N/2 clocks, and then apply
    the interleving operation to get the results of a 2*(N+1) multipliers
    computing in N/4 clocks.

    Each multiplier therefore shall store N/4 products per frequency bin (one product per clock). The
    accumulator can store a total of 512 products, or 512/(N/4) frequency bins
    (128 bins for N=16). If the channelizer produce 1024 frequency bins, we
    need 1024/512*N/4=N/2 correlators to process all the products (8 correlators for N=16).

    The corner-turn engine will be typically set-up to distribute 1/8th of the
    bins to each correlator in a round robin fashion, i.e. correlator 0 has
    bins 0, 8, 16, 24 ..., while correlator 1 has bins 1, 9, ...

    The CMAC products are read out in the reverse order than they were written.

    Data formats:

        raw: [CORR, CMAC, PROD]
        matrix: [BIN, ch_i, ch_j]
        vector: [bin, product]

    The `raw` format is as close to the correlator output format, and is
    processed just enough to allow the data to be usable (i.e, complex numbers
    are extracted, and specific bin/product can be indexed directly)


    """
    N = NCHAN
    Ncmac = NI_CMAC_PER_CORR # Number of CMACs (before interleaving)
    Ncorr = NCORR
    Nbins_per_corr = NBINS_PER_CORR # Number of bins processed by each correlator
    Nprods = NPROD_PER_CMAC # NI_CLOCKS_PER_BIN * Nbins_per_corr # total number of products in a CMAC (before interleaving)
    raw_map = np.zeros((Ncorr, Ncmac, Nprods, 3), int) - 1  # each element if raw_map[corr,cmac,prod] is a (bin, ch_x, ch_y) array
    interleaved_raw_map = np.empty((Ncorr, Ncmac*2, Nprods/2, 3), int)

    # Create the arrays that will be used to index the raw data into the target array
    # The first dimension is for the 3 indexes of the war a=data (CORR, CMAC, PROD]
    # We use int16 values to store indices to fit NBINS_TOTAL (0..1023)
    raw_to_matrix_map = np.empty((3, NBINS_TOTAL, N, N), np.int16)
    raw_to_vector_map = np.empty((3, NBINS_TOTAL, NPROD_TOTAL), np.int16)
    # Compute the corelator output map as if we computed all the products for each bin in N/2 clocks.
    cmac = np.arange(Ncmac)
    x = np.zeros(Ncmac)
    y = np.zeros(Ncmac)
    bin_number = np.zeros(NCMAC_PER_CORR, dtype=int)

    ni_i = np.zeros((NI_CMAC_PER_CORR,NI_CLOCKS_PER_BIN), dtype=int)
    ni_j = np.zeros((NI_CMAC_PER_CORR,NI_CLOCKS_PER_BIN), dtype=int)
    i_i = np.zeros((NCMAC_PER_CORR,NCLOCKS_PER_BIN), dtype=int)
    i_j = np.zeros((NCMAC_PER_CORR,NCLOCKS_PER_BIN), dtype=int)

    X = (np.arange(N)[None].T - np.arange(NI_CLOCKS_PER_BIN)) % N
    Y = np.tile(np.arange(N)[None].T, (1, NI_CLOCKS_PER_BIN))
    ni_i[0] = ni_j[0] = X[N / 2 - 1]
    ni_i[1] = ni_j[1] = X[N - 1]
    ni_i[2:] = X[:N-1]
    ni_j[2:] = Y[1:]
    # Handle rotated-in i indices: they use different indices and are compelx conjugate
    for clock in range(NI_CLOCKS_PER_BIN):
        ni_j[2:2 + clock, clock] = Y[:clock, clock]

        # These products use the opposite complex conjugate in the fpga, so
        # swap the axis. This keeps the pairs in the upper triangle.

        tmp = ni_i[2:2 + clock, clock].copy()  # make sure we make a copy, not just a view
        ni_i[2:2 + clock, clock] = ni_j[2:2 + clock, clock]
        ni_j[2:2 + clock, clock] = tmp

    # interleave (double CMACs, cut clocks in 2)
    for i in range(2):
        i_i[i::2] = ni_i[:,i::2]
        i_j[i::2] = ni_j[:,i::2]


    cmac_bin_index = np.arange(NBINS_PER_CMAC, dtype=int).repeat(NCLOCKS_PER_BIN)
    ii_i = np.tile(i_i,(1, NBINS_PER_CMAC))
    ii_j = np.tile(i_j,(1, NBINS_PER_CMAC))

    # Reverse readout order
    cmac_bin_index = cmac_bin_index[::-1]
    ii_i = np.fliplr(ii_i)
    ii_j = np.fliplr(ii_j)

    # Procuct number, in the order they are received
    cmac_prod_index = np.arange(NPROD_PER_CMAC, dtype=int)

    # For each correlator, we
    for corr in range(Ncorr):  # Correlator number
        # for corr_bin_index in range(Nbins_per_corr): # relative bin index for this correlator
        #     bin_number[:] = corr + corr_bin_index * Ncorr  # bin
            # for clock in range(NI_CLOCKS_PER_BIN): # clock cycle in which the computation is done (8 clocks, will be interleaved in 4)
            #     cmac_prod = NI_CLOCKS_PER_BIN * corr_bin_index + clock


            #     x[0] = y[0] = NI_CLOCKS_PER_BIN - 1 - clock # 1st autocorrellation products (products 0 .. N/2-1, read in reverse order)
            #     x[1] = y[1] = N - 1 - clock  # 2nd autocorrelation products (products N/2 .. N-1, read in reverse order)

            #     x[2:] = (cmac[0:N-1] + N - clock) % N
            #     x[2:clock+2] = np.arange(clock)
            #     y[2:] = cmac[0:N-1] + 1
            #     y[2:2+clock] = N-clock+np.arange(clock)

#                raw_map[corr, :, cmac_prod] = np.array([list(bin_number), x, y]).T  #(b, x , y)


                #  new method
        freq_bin = np.tile(corr + 8*cmac_bin_index, (NCMAC_PER_CORR, 1))
        r = raw_to_matrix_map[:, freq_bin, ii_i, ii_j]
        return r,r
        r[0] = corr # int scalar, broadcasted to all elements
        r[1] = np.arange(NCMAC_PER_CORR, dtype=int)[None].T # 1xNCMAC column, broadcasted to evert product
        r[2] = np.array(cmac_prod_index) # NPROD x NCMAC array indicating the product number
        # return  r

    # Since we need to compute the products in N/4 clocks (there are 4 clocks per bin), we use two CMAC in parallel.
    # The CMACs are interleaved. We update the map to repreent this.
    # interleaved_raw_map[:, 0::2] = raw_map[:, :, 0::2]
    # interleaved_raw_map[:, 1::2] = raw_map[:, :, 1::2]
    return raw_to_matrix_map, raw_to_vector_map

def imap(self, shape):
    """ Return an array of shape `shape` where each element is a 3-element tuple containing the index on that element.
    """
    N1, N2, N3 = shape
    im = np.zeros((N1,N2,N3, 3), int) + 65535
    [b,i,j] = np.meshgrid(range(N1), range(N2), range(N3), indexing='ij')
    im[...,0], im[..., 1], im[..., 2] = b, i, j
    return im

def reverse_map(self, m):
    (N1, N2, N3) = m.reshape(-1, 3).max(axis=0) + 1  # Find the maximum indices if each dimension
    rm = np.empty((N1, N2, N3, 3), int)
    im = self.imap(m.shape[:-1])
    rm[m[..., 0], m[..., 1], m[..., 2]] = im
    rm[m[..., 0], m[..., 2], m[..., 1]] = im  # also populate j,i with same values
    return rm



def read_corr_frames(socket, integration_period, integ_time=1, timeout=0.100, packets_per_chunk=1*34*8):
    """

    Requirements:

    The transmit rate must be fast enough to accomodate the desired bandwidth
    by setting ib.GPIO.HOST_FRAME_READ_RATE = rate. rate=16 limits to about
    260 Mbps but is slow enough to allow python to process the data with a
    small standard UDP buffer. ``rate``=15 is good for about 500 Mbps, and
    ``rate``=16 is good for the full Gigabit bandwidth. The latetr two require
    bigger UDP buffers. See below::

        ib.GPIO.HOST_FRAME_READ_RATE = 14

    The Ethernet interface must be set to receive Jumbo frames::

        sudo ifconfig eno1 mtu 9000

    The UDP buffers shall be increased to reduce packet loss to a minimum::
        sudo sysctl -w net.core.rmem_max=26214400
        sudo sysctl -w net.core.rmem_default=26214400
        sudo sysctl -w net.ipv4.udp_mem='26214400 26214400 26214400'
        sudo sysctl -w net.ipv4.udp_rmem_min=26214400

    Check udp buffers::
        sysctl -a | grep mem

    Monitor UDP buffer::

        watch -cd -n .5 "grep :A6  /proc/net/udp"

    The receiver can do software integration for unlimited time at a firmware integration period of 5000 frames (12.8 ms).


    """



    # integration_period = self.CORR[0].INTEGRATION_PERIOD + 1
    integration_time = 2.56e-6 * integration_period
    dt = np.dtype(dict(
        names=['sat', 'h', 'l'],
        offsets=[4, 1, 0],
        formats=['u1', '<i4', '<i4']))
    t = np.dtype([
        ('cookie', np.uint8, 1),
        ('proto', np.uint8, 1),
        ('corr', np.uint8, 1),
        ('cmac', np.uint8, 1),
        ('geometry', '<u4', 1),
        ('ts', '<u4', 1),
        ('data', dt, 512)])
    NCORR = 8
    NCMAC = 34
    NPROD = 512
    PACKET_SIZE = 12 + NPROD * 5

    average_data_rate = (NCORR * NCMAC * (42 + PACKET_SIZE) * 8) / integration_time
    min_transmit_time = (NCORR * NCMAC * (42 + PACKET_SIZE) * 8) / 1e9
    integ_time = max(integ_time, integration_time)
    expected_chunks = int(integ_time * NCORR * NCMAC / integration_time / packets_per_chunk)
    expected_packets = expected_chunks * packets_per_chunk
    expected_corr_frames = expected_packets / (NCORR * NCMAC)

    print 'Correlator is sending data at %.3f Gb/s, correlator frame period= %i channelizer frames = %.3f ms, minimum transmit time = %.3f' % (average_data_rate/1e9, integration_period, integration_time*1000, min_transmit_time*1000)
    print 'We expect around %.1f packets and %.1f correlator frames in the requested integration period of %.3fs' % (expected_packets, expected_corr_frames, integ_time)

    # packets_per_chunk = corr_frames_per_chunk * NCORR * NCMAC

    a = np.empty((packets_per_chunk, PACKET_SIZE), dtype=np.uint8)
    h = np.empty((packets_per_chunk, NPROD), dtype=np.int32)
    ah = np.zeros((NCORR, NCMAC, NPROD), dtype=np.int64)
    al = np.zeros((NCORR, NCMAC, NPROD), dtype=np.int64)
    sat = np.empty((NCORR, NCMAC, NPROD), dtype=np.uint8)
    count = np.zeros((NCORR, NCMAC), dtype=np.uint64)
    # sock = self.get_data_socket()
    socket.settimeout(timeout)
    chunks = 0
    packets = 0
    timeouts = 0
    data_timeouts = 0
    size = 0
    dt = 0
    packets_per_chunk = 0

    # Flush the UDP buffer
    for _ in range(8*34):
        s = socket.recv_into(a[0])

    t0 = time.time()
    N = len(a)
    # while time.time() - t0 < integ_time:
    for chunk in range(expected_chunks):
        n = 0
        while n < N:
            # try:
            s = socket.recv_into(a[n])
            if s != PACKET_SIZE:
                continue
            # size += s
            n += 1
            # packets += 1
            # except socket.timeout:
            #     timeouts += 1
            #     if n:
            #         data_timeouts += 1
            #         break

        packets += n
        chunks += 1
        packets_per_chunk += n
        # z=zeros(h.shape,dtype=int64)

        # l=empty((1*8*34,512), dtype=np.int32)
        # h=a.view(t)[:,0]['data']['h'].copy();np.left_shift(h,4,h);np.right_shift(h,14,h);np.add(z,h,out=z)
        t1 = time.time()
        v = a.view(t)[:n, 0]
        corr = v['corr']
        cmac = v['cmac']
        # print 'corr=', corr
        # print 'cmac=', cmac

        ts = v['ts']
        hh = h[:n]
        np.copyto(hh, v['data']['h'])
        np.left_shift(hh, 4, hh)
        np.right_shift(hh, 14, hh)
        ah[corr, cmac] += hh

        np.copyto(hh, v['data']['l'])
        np.left_shift(hh, 14, hh)
        np.right_shift(hh, 14, hh)
        al[corr, cmac] += hh
        count[corr, cmac] += 1
        # print 'count=', count[0,0]
        dt += time.time() - t1
        sat[corr, cmac] |= v['data']['sat']
    print 'Got %i packets in %i chunks with %i timeouts total and %i data timeouts. Processing took on average %i packets/chunk at %.3f ms/chunk, %.1f bytes/packet' % (packets, chunks, timeouts, data_timeouts, float(packets_per_chunk)/chunks, (float(dt) / chunks) * 1000, float(size)/packets)
    print 'Got %.1f%% of the packets, and between %.1f%% and %.1f%% of the correlator frames' % (float(packets)/expected_packets*100, np.min(count)/float(expected_corr_frames)*100, np.max(count)/float(expected_corr_frames)*100)
    c = ah + 1j * al
    return (c, count, sat & 0x30)

