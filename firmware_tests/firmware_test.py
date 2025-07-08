import logging
import numpy as np
from test_setup import board_conn, setup_funcgen, TEST_CONFIG, CONN_CONFIG
from utils import plot_comp_data, some_plot
import pytest
import socket
import psutil
from net_tools import ping_sources_async
from functools import wraps
import sts
import matplotlib.pyplot as plt
import math
from test_setup import PLOT_DIR
from pychfpga.fpga_firmware.chfpga.f_engine.funcgen import FUNCGEN
from pychfpga.fpga_firmware.chfpga.mmi import MMI


def compare_plot_data(test_unit):
    """
    A wrapper for unit tests that plots data (if requested) and compares all read rows to reference data using
    np.isclose(). Unit tests must return data and ref_data which are np.ndarray type.
    """
    @wraps(test_unit)
    def wrapper(*args, **kwargs):
        data, ref_data = test_unit(*args, **kwargs)

        logger = TestFW.get_logger()

        if TEST_CONFIG['comp_plots']:
            logger.debug("Generating plots")
            plot_comp_data(test_unit.__name__, ref_data, data, title=test_unit.__name__)

        for i, data_row in enumerate(data):            
            np.testing.assert_allclose(
                data_row,
                ref_data,
                err_msg=f"Data row with index {i} does not match the reference data",
            )
    return wrapper


class TestFW:
    """
    Collection of tests for an ICE/CRS board firmware. Most tests utilize the board_conn fixture, that reads
    connection parameters specified in config.yaml and connects to the boards. Some tests also use setup_funcgen
    fixture which allows controlling function generator within tests. The @compare_plot_data decorator is used
    to compare the data read from the board and reference data. For this to work, test units must return data and
    ref_data numpy arrays.
    """
    # All parameters are set by fixtures
    board = None
    FG_NS = None
    FG_DTYPE = None
    FG_DTYPE_SIGNED = None
    FG_LSHIFT = None
    NUMBER_OF_CHANNELIZERS = None

    PLATFORM = "CRS" if "crs" in CONN_CONFIG['hwm'] else "ICE"

    #list of 10 seeds to test noise from funcgen (seeds are 16 bits signed int)
    seeds = [22099, 2690, 9868, -7423, -13225, -7684, 13287, 5207, 18207, -1201]
    random_test_functions = ["frequency", "runs", "longest_run_of_ones", "rank", "discrete_fourier_transform", ]
    P_VALUE_THRESHOLD = 0.01

    @classmethod
    def get_logger(cls):
        logger = logging.getLogger(cls.__class__.__name__)
        logger.setLevel(TEST_CONFIG['logleveltest'])
        return logger

    def test_udp_buffers_size(self):
        logger = self.get_logger()
        buff_config = list()
        logger.debug("Reading system files in /proc/sys/net")
        with open("/proc/sys/net/core/rmem_max") as file:
            buff_config.append(int(file.readline()))
        with open("/proc/sys/net/core/rmem_default") as file:
            buff_config.append(int(file.readline()))
        with open("/proc/sys/net/ipv4/udp_mem") as file:
            for val in file.readline().split():
                buff_config.append(int(val))
        with open("/proc/sys/net/ipv4/udp_rmem_min") as file:
            buff_config.append(int(file.readline()))

        if any(val < 26214400 for val in buff_config):
            raise RuntimeError(
                "The UDP buffers' memory parameters (net.core.rmem_max, net.core.rmem_default, "
                "net.ipv4.udp_mem, net.ipv4.udp_rmem_min) are too low. Increase them to at least 26214400 "
                "bytes. \nYou can do it by running:\n"
                ">>> sudo sysctl -w net.core.rmem_max=26214400 net.core.rmem_default=26214400 "
                "net.ipv4.udp_mem='26214400 26214400 26214400' net.ipv4.udp_rmem_min=26214400"
            )

    @pytest.mark.asyncio
    async def test_mtu_size(self, board_conn):
        logger = self.get_logger()
        logger.debug("Getting the board's address")
        port_map = dict(
            port=self.board.get_data_socket().getsockname()[1],
            sources=[(self.board.hostname, 80)]
        )
        logger.debug(f"The board located at {port_map['sources'][0][0]}")
        logger.debug("Pinging the board to determine interface used")
        src_if_addrs = await ping_sources_async([port_map])
        if_ip = list(src_if_addrs.values())[0]
        logger.debug(f"Interface address: {if_ip[0]}:{if_ip[1]}")
        if_addrs = psutil.net_if_addrs()
        if_name = None
        for key in if_addrs.keys():
            for snic_addr in if_addrs[key]:
                if snic_addr[0] == socket.AF_INET:
                    if snic_addr[1] == if_ip[0]:
                        if_name = key
        logger.debug(f"Interface name: {if_name}")
        if_stats = psutil.net_if_stats()
        mtu = if_stats[if_name].mtu
        logger.debug(f"Interface MTU size: {mtu}")

        if mtu < 9000:
            raise RuntimeError(f"Default network interface has MTU={mtu} (<9000). Please set MTU to 9000 to "
                               f"prevent loss of packages.")

    def test_packets_number(self, board_conn):
        """
        Ensures that all packages sent by the motherboard are received.
        """
        logger = self.get_logger()
        logger.debug("Starting data capture for one period")
        self.board.start_data_capture(period=1)
        receiver = self.board.get_data_receiver()
        logger.debug("Reading raw frames")
        _, _, count = receiver.read_raw_frames()
        logger.info(f"Expected {len(count)} packages, received {len([p for p in count if p])}.")
        assert all(count), "Missing packages from ICE board. Check connection and system configuration."

    def _set_capture_funcgen(self, source: str, period: float = 1, frames_per_burst: int = 1, number_of_bursts: int = 0, **func_kwargs):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        split = True if self.PLATFORM == "CRS" else False
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(period=period, source='adc', frames_per_burst = frames_per_burst, number_of_bursts = number_of_bursts)
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source, **func_kwargs)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        if self.PLATFORM == "CRS":
            timestamp, data, count = receiver.read_raw_frames(format='16',split = True)
        else:
            timestamp, data, count = receiver.read_raw_frames()
        data = data >> self.FG_LSHIFT
        return data
    
    
    # def read_data_bypass_fft_scaler(data_array):
    #     scale_factor = 2 ** (16 - FPGAArray.ADC_BITS_PER_SAMPLE) # Output read is aligned on the MSB. For the CRS, 14 bits are aligned with 16 bits. For ICE, 16 bits are aligned with 16 bits (no change)
    #     return np.divide(data_array, scale_factor)


    @staticmethod
    def _compare_data(data: np.ndarray, ref_data: np.ndarray):
        pass

    @compare_plot_data
    def test_funcgen_ramp(self, board_conn, setup_funcgen):
        ref_data = (np.arange(self.FG_NS, dtype="u2")<<self.FG_LSHIFT).view("i1")>>self.FG_LSHIFT
        # ref_data = (((np.arange(self.FG_NS, dtype="u2"))<<self.FG_LSHIFT).view(self.FG_DTYPE_SIGNED))>>self.FG_LSHIFT
        data = self._set_capture_funcgen('ramp')
        
        # data = data >> self.FG_LSHIFT #IMplemented in _set_capture_funcgen
        # ref_data = ((ref_data << self.lshift)).view("i2")
        return data, ref_data

    @compare_plot_data
    def test_funcgen_sin(self, board_conn, setup_funcgen):
        sin_freq = 1
        # np.sin(np.arange(self.NS) * 2 * np.pi / self.NS * freq) * (ampl if ampl is not None else (1 << (self.Nbits - 1) - 1))))
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * sin_freq) * 127).astype('i2')
        data = self._set_capture_funcgen('sin', freq=sin_freq, ampl=127)
        # data = np.divide(data, 2**self.FG_LSHIFT) # For CRS, output of FUNCGEN is 14 bit read into 16 bits aligned at the MSB.
        #^Implemented in _set_capture_funcgen
        return data, ref_data

    @compare_plot_data
    def test_funcgen_arb(self, board_conn, setup_funcgen):
        freq_sin = 1
        freq_cos = 2
        t = np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS
        ref_data = (np.sin(t * freq_sin) * 127 / 2 + np.cos(t * freq_cos) * 127 / 2).astype('i2')
        print(ref_data)
        data = self._set_capture_funcgen('arb', data=ref_data)
        return data, ref_data

    @compare_plot_data
    def test_funcgen_const(self, board_conn, setup_funcgen):
        a = 13 << self.FG_LSHIFT
        ref_data = np.full(self.FG_NS, a, self.FG_DTYPE).view('u1')
        data = self._set_capture_funcgen('a', a=a)
        return data, ref_data

    @compare_plot_data
    def test_funcgen_ab(self, board_conn, setup_funcgen):
        a = 13 << self.FG_LSHIFT
        b = 42 << self.FG_LSHIFT
        ref_data = np.tile(np.array((a, b), self.FG_DTYPE), self.FG_NS // 2).view('u1')
        data = self._set_capture_funcgen('ab', period=0.01, a=a, b=b)
        return data, ref_data

    @compare_plot_data
    def test_funcgen_real_ramp(self, board_conn, setup_funcgen):
        #Check it works with ICE too, works with CRS
        ref_data = np.ravel([(i,0) for i in range(self.FG_NS//2)])
        #ref_data = (np.arange(self.FG_NS // 2)<<8).astype('>u2').view('i1')
        data = self._set_capture_funcgen('real_ramp')
        return data, ref_data

    @compare_plot_data
    def test_bypass_fft_and_scaler(self, board_conn, setup_funcgen):
        sin_freq = 100
        chan_params = dict(
            data_source='sin',
            freq=sin_freq,
            ampl=127,
            fft_bypass=1,
            scaler_bypass=1,
            scaler_eight_bit=1,
            prober_user_flags=0,
        )
        self.board.set_channelizer(**chan_params)
        self.board.start_data_capture(period=1, source='scaler')
        receiver = self.board.get_data_receiver()
        timestamp, data, count = receiver.read_raw_frames()

        sin_freq = 100
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * sin_freq) * 127).astype(self.FG_DTYPE_SIGNED)
        return data, ref_data
    


#How to write to control register to change SHIFT
    # def shift_adc_input(self, bits_to_shift: int, address: int = FUNCGEN.SHIFT):
    #     self.board.fpga_i2c_write_read(address, bits_to_shift)

    @pytest.mark.parametrize("bits_to_shift", [1,10]) #to change
    def test_funcgen_shift_and_saturation(self,board_conn, setup_funcgen, bits_to_shift):
        """"""
        data_1 = self._set_capture_funcgen('adc', fft_bypass=True, scaler_bypass=True)
        # self.shift_adc_input(bits_to_shift)
        # self.board.fpga_i2c_write_read(FUNCGEN.SHIFT, bits_to_shift)
        #####No I2C for crs???#####
        data_2 = self._set_capture_funcgen('adc', fft_bypass=True, scaler_bypass=True)
        plt.plot(data_1)
        plt.plot(data_2)
        plt.savefig(PLOT_DIR/"bits to shift")


    # #shift adc value and check if the correct number of saturations is outputted
    # def test_funcgen_saturated_adc(self,board_conn, setup_funcgen):
    #     """ Test saturation of adc source"""
    #     # data_1 = self._set_capture_funcgen('adc').view("i2")[0]
        
    #     # #shift adc value and compare expected saturations vs actual saturations
    #     # plt.plot(data_1)
    #     # plt.savefig(PLOT_DIR/f"adc source values")
    #     # control_byte = int(MMI.read_control(FUNCGEN.SHIFT, int, 1)) & int("0x0F", 16)
    #     control_byte = MMI.read_drp(FUNCGEN.SHIFT)
    #     print(control_byte)

    # #65536 possible diff seeds so we can test with 10 random seeds
    # #need to change so it works with all boards
    @pytest.mark.parametrize("seed", seeds)
    def test_funcgen_deterministic(self, board_conn, setup_funcgen, seed):
        data_1 = self._set_capture_funcgen('noise', fft_bypass=True, scaler_bypass=True, seed = seed)
        data_2 = self._set_capture_funcgen('noise', fft_bypass=True, scaler_bypass=True, seed = seed)
        plot_comp_data("deterministic", data_1[0], data_2[0]) #only plotting data for first channelizer is enough
        assert np.array_equal(data_1, data_2)
    

    # Randomness tests from NIST
    # @pytest.mark.parametrize("seed, function", [(seeds[:2], random_test_functions)])
    # @pytest.mark.parametrize("seed", seeds[:2])
    # def test_funcgen_random(self, board_conn, setup_funcgen):
    #     p_val_l = []
    #     for seed in self.seeds:
    #         data = self._set_capture_funcgen('noise', fft_bypass=True, scaler_bypass=True, seed = seed).view("u1").tolist()
    #         print(len(data))
    #         # for i in range(self.NUMBER_OF_CHANNELIZERS):
    #         p_val = sts.frequency(data[0])
    #         print(p_val)
    #         p_val_l.append(p_val)
    #         # assert p_val >= self.P_VALUE_THRESHOLD
    #     some_plot(self.seeds, p_val_l, "p_val")


    def test_funcgen_random(self, board_conn, setup_funcgen):
        """Monobit test on funcgen noise generator. P-val > 0.01 indicates randomness"""
        p_val_l= []
        for seed in self.seeds:
            sum = 0
            data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("u1")[0] #check first channelizer
            data = np.unpackbits(data)
            # avg = np.sum(data) / len(data)
            # avg_l.append(avg)
            for bit in data:
                if bit == 0:
                    bit = -1
                sum += bit
            sn = abs(sum) / math.sqrt(len(data))
            p_val = math.erfc(sn)
            p_val_l.append(p_val)
        some_plot(self.seeds, p_val_l, "frequency", "seed", "p-val")

    def test_funcgen_random_count(self, board_conn, setup_funcgen):
        """Histogram of frequency counts"""
        #increase frame number!
        for seed in self.seeds:
            data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2")[0] #check first channelizer
            # frequency, count = np.unique(data, return_counts = True)
            plt.hist(data, 100, label=f"{seed=}")
            # freq, count = np.unique(data, return_counts = True)
        plt.savefig(PLOT_DIR/f"histogram of noise values")
            


    # def test_funcgen_random_extremes(self, board_conn, setup_funcgen):
    #     """Histogram of frequency counts"""
    #     #increase frame number!
    #     for seed in self.seeds:
    #         fig, axs = plt.subplots(2)
    #         min_values_plot = axs[0]
    #         max_values_plot = axs[1]
    #         data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2")[0] #check first channelizer
    #         freq, count = np.unique(data, return_counts = True)
    #         num_extremes = 25 # return the num_extremes values from the noise generator that have the lowest count
    #         min_indices = np.argpartition(count, num_extremes)[:num_extremes]
    #         max_indices = np.argpartition(count, -num_extremes)[-num_extremes:]
    #         min_count = []
    #         min_values = []
    #         max_count = []
    #         max_values = []
    #         for i in min_indices:
    #             min_values.append(freq[i])
    #             min_count.append(count[i])
    #         for i in max_indices:
    #             max_values.append(freq[i])
    #             max_count.append(count[i])

    #         min_values_plot.plot(min_values, min_count, marker='o',linestyle='None', ms=1)
    #         max_values_plot.plot(max_values, max_count, marker='o',linestyle='None',ms=1)
    #         min_values_plot.set_title(f"min with {seed=}")
    #         max_values_plot.set_title(f"min with {seed=}")
    #     plt.savefig(PLOT_DIR/f"random min count with seed {seed}")

    @pytest.mark.parametrize("extremum", ["min", "max"])
    def test_funcgen_random_extremes(self, board_conn, setup_funcgen, extremum):
        """Returns the number of counts of min/max values generated by random noise"""
        for seed in self.seeds:
            data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2")[0] #check first channelizer
            freq, count = np.unique(data, return_counts = True)
            num_extremes = 15 # return the num_extremes values from the noise generator that have the lowest count
            if extremum == "min":
                indices = np.argpartition(count, num_extremes)[:num_extremes]
            else:
                indices = np.argpartition(count, -num_extremes)[-num_extremes:]
            extreme_count = []
            extreme_values = []
            for i in indices:
                extreme_values.append(freq[i])
                extreme_count.append(count[i])
                plt.plot(extreme_values, extreme_count, marker='o',linestyle='None', ms=1, label=f"{seed=}")
        plt.savefig(PLOT_DIR/f"{extremum} {num_extremes} values generated randomly")


    # def test_funcgen_random_max(self, board_conn, setup_funcgen):
    #     """Histogram of frequency counts"""
    #     #increase frame number!
    #     for seed in self.seeds:
    #         data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2")[0] #check first channelizer
    #         freq, count = np.unique(data, return_counts = True)
    #         num_extremes = 15 # return the num_extremes values from the noise generator that have the lowest count
    #         max_indices = np.argpartition(count, -num_extremes)[-num_extremes:]
    #         min_count = []
    #         min_values = []
    #         max_count = []
    #         max_values = []
    #         for i in max_indices:
    #             max_values.append(freq[i])
    #             max_count.append(count[i])
    #         plt.plot(max_values, max_count, marker='o',linestyle='None', ms=1)
    #     plt.savefig(PLOT_DIR/f"random count  {seed}")

    # def test_funcgen_random_min(self, board_conn, setup_funcgen):
    #     """Histogram of frequency counts"""
    #     #increase frame number!
    #     for seed in self.seeds:
    #         data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2")[0] #check first channelizer
    #         freq, count = np.unique(data, return_counts = True)
    #         num_extremes = 15 # return the num_extremes values from the noise generator that have the lowest count
    #         min_indices = np.argpartition(count, num_extremes)[:num_extremes]
    #         min_count = []
    #         min_values = []
    #         max_count = []
    #         max_values = []
    #         for i in min_indices:
    #             min_values.append(freq[i])
    #             min_count.append(count[i])
    #         plt.plot(min_values, min_count, marker='o',linestyle='None')
    #     plt.savefig(PLOT_DIR/f"random max count with seed {seed}")



###TODO:###

    #     # The following define the source of the data
    # DATA_SOURCE_NAMES = {
    #     'adc':                   FN_ADC,  # Sends the ADC data


    #     'word_ctr_buffer_flags': FN_WORD_CTR,  # 32-bit Frame/word counter, with ADC overflow from bit 0 of buffer bytes
    #     'buffer':                FN_BUFFER,  # Sends the data stored in the buffer

    #     'frame8':                FN_FRAME8,  # Sends the frame number in every 8-bit sample
    #     'frame4':                FN_FRAME4,  # Sends the frame number if the upper 4 bits of each samples. The lower bits are zero.
    #     'nibble4':               FN_BUFFER_NIBBLE4,  # Sends the lower/upper nibble of the bytes in the buffer as a real value based on whether the frame number is even/odd.
    #     }

    def _set_capture_funcgen_frames(self, source: str, **func_kwargs):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        split = True if self.PLATFORM == "CRS" else False
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(source='adc', **func_kwargs)
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        if self.PLATFORM == "CRS":
            timestamp, data, count = receiver.read_raw_frames(format='16',split = True)
        else:
            timestamp, data, count = receiver.read_raw_frames()
        data = (data >> self.FG_LSHIFT).astype(self.FG_DTYPE)
        return data
    

    @pytest.mark.parametrize("num_frames", [2])
    def test_frame_counter(self, board_conn, setup_funcgen, num_frames):
        """"""
        words_per_frame = 2048
        chan_params = dict(
            frames_per_burst = num_frames,
            number_of_bursts = 3,
            burst_period_in_frames = 2,
        )
        num_bits_counter = 8
        logger = self.get_logger()
        data_1 = self._set_capture_funcgen_frames("word_ctr_buffer_flags", period = 1, frames_per_burst=1,number_of_bursts=0)[0]
        receiver = self.board.get_data_receiver(verbose=2)
        _,data_2,__ = receiver.read_raw_frames(format='16',split = True)
        data_2 = (data_2 >> self.FG_LSHIFT).astype(self.FG_DTYPE)[0]
        _,data_3,__ = receiver.read_raw_frames(format='16',split = True)
        data_3 = (data_3 >> self.FG_LSHIFT).astype(self.FG_DTYPE)[0]
        if self.PLATFORM == "CRS":
            #1. Capture the last three samples of each word (of 8 samples) into a list 
            #2. Concatenate first two samples and first two bits of last sample -> Frame counter
            #3. Last sample [0:11] -> word counter
            word_counter_bits = 12 # word counter bits occupy the last 11 bits of a word's last sample
            last_three_samples = np.array([], dtype = self.FG_DTYPE)
            data = np.concatenate((data_1, data_2, data_3))
            for i in range(1, len(data)):
                if (i % 8 == 0):
                    last_three_samples = np.append(last_three_samples, data[i-3:i])
            word_count_l = np.bitwise_and(last_three_samples[2::3], 0xff) #woird counter represented by the 11 LSBs of the last sample, word counter only has the 8LSBs of counted words
            frame_count_l = np.array([], dtype = self.FG_DTYPE)
            # frame_count_l_last_bits = last_three_samples[2::3] >> word_counter_bits
            for i in range(0, len(last_three_samples), 3):
                # frame_num = (last_three_samples[i] << 16) + (last_three_samples[i+1] << 2) + (last_three_samples[i+2] >> word_counter_bits) #last_three_samples[i] << 16 is always 0
                frame_num = ((last_three_samples[i+1] & 0xff) << 2) + (last_three_samples[i+2] >> word_counter_bits) #last_three_samples[i] << 16 is always 0
                frame_count_l = np.append(frame_count_l,frame_num)   
        logger.debug(f"{data.shape=}")
        logger.debug(f"{word_count_l=}")
        logger.debug(f"{frame_count_l=}")
        plt.plot(frame_count_l)
        plt.plot(word_count_l)
        plt.savefig(PLOT_DIR/"frame and word counter")
        expected_final_frame = frame_count_l[0] + chan_params["number_of_bursts"] * chan_params["frames_per_burst"] + chan_params["burst_period_in_frames"]
        for i in range(len(word_count_l) - 1):
            assert word_count_l[i+1] - word_count_l[i] == 1 or (word_count_l[i] == 255 and word_count_l[i+1] == 0) #word count increases by one or overflows at the 8th bit
        assert word_count_l[-1] == (word_count_l[0] + (chan_params["number_of_bursts"] * chan_params["frames_per_burst"] + chan_params["burst_period_in_frames"])* words_per_frame)% (2**num_bits_counter)
        assert frame_count_l[-1] == expected_final_frame

    # def test_frame_counter(self, board_conn, setup_funcgen, num_frames):
    #     """Test that RAM[3:0] are send on even frames and RAM[7:4] are sent on odd frames"""
        



#Test 'nibble4' even and odd frames!!!