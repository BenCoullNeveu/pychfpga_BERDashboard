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
import sys


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

    # @pytest.mark.parametrize("extremum", ["min", "max"])
    # def test_funcgen_random_extremes(self, board_conn, setup_funcgen, extremum):
    #     """Returns the number of counts of min/max values generated by random noise"""
    #     for seed in self.seeds:
    #         data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2")[0] #check first channelizer
    #         freq, count = np.unique(data, return_counts = True)
    #         num_extremes = 15 # return the num_extremes values from the noise generator that have the lowest count
    #         if extremum == "min":
    #             indices = np.argpartition(count, num_extremes)[:num_extremes]
    #         else:
    #             indices = np.argpartition(count, -num_extremes)[-num_extremes:]
    #         extreme_count = []
    #         extreme_values = []
    #         for i in indices:
    #             extreme_values.append(freq[i])
    #             extreme_count.append(count[i])
    #             plt.plot(extreme_values, extreme_count, marker='o',linestyle='None', ms=1, label=f"{seed=}")
    #     plt.savefig(PLOT_DIR/f"{extremum} {num_extremes} values generated randomly")
    @pytest.mark.parametrize("extremum", ["min", "max"])
    def test_funcgen_random_extremes(self, board_conn, setup_funcgen, extremum):
        """Returns the number of counts of min/max values generated by random noise"""
        for seed in self.seeds:
            data = self._set_capture_funcgen('noise', 1, 5, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2")[0] #check first channelizer
            values, count = np.unique(data, return_counts = True)
            if extremum == "min":
                ext_count = np.min(count)
            else:
                ext_count = np.max(count)
            ext_idx = np.where(count == ext_count)
            ext_values = []
            for i in ext_idx:
                ext_values.append(values[i])
            plt.plot(ext_values, marker='o',linestyle='None', ms=1, label=f"{seed=}")
            plt.savefig(PLOT_DIR/f"{extremum} values generated randomly with seed {seed=}")


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
    #     'nibble4':               FN_BUFFER_NIBBLE4,  # Sends the lower/upper nibble of the bytes in the buffer as a real value based on whether the frame number is even/odd.
    #     }

    def _set_capture_funcgen_frames(self, source: str, **func_kwargs):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        split = True if self.PLATFORM == "CRS" else False
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(source='adc', verbose = 1, **func_kwargs)
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source, channels=[0])
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        if self.PLATFORM == "CRS":
            ncap = func_kwargs.get('number_of_bursts', 1)
            logger.debug(f"Number of captures: {ncap}")
            timestamp, data, count = receiver.read_raw_frames(format='16', split = True, ncap = ncap)
        else:
            timestamp, data, count = receiver.read_raw_frames()
        print("Verifying that shift is logical...")

        data = (data.astype(self.FG_DTYPE) >> self.FG_LSHIFT)
        return timestamp, data[0].flatten(), count
    
    @pytest.mark.parametrize("frames_per_burst, number_of_bursts, burst_period_in_frames", [(1,1,5000), (2, 4, 5000), (10,2,10000), (5,5,10000)])
    def test_word_ctr_buffer_flags(self, board_conn, setup_funcgen, frames_per_burst, number_of_bursts, burst_period_in_frames):
        """Test for mode: "word_ctr_buffer_flags". Test that frame counter and word counter have the correct count according to the number of bursts and frames per burst.
        For CRS, we are calling read_raw_frames with format='16' and split = True, so each specified frame is actually two frames (with different frame count since word count overflows at 2048)"""
        logger = self.get_logger()
        timestamp,data,count = self._set_capture_funcgen_frames(
            "word_ctr_buffer_flags", 
            frames_per_burst = frames_per_burst, 
            number_of_bursts = number_of_bursts, 
            burst_period_in_frames = burst_period_in_frames
        )
        
        logger.debug(f"{timestamp=}")
        if self.PLATFORM == "CRS":
            #1. Capture the last three out of eight samples of each word
            #2. Concatenate first two samples and first three bits of last sample -> Frame counter
            #3. Last sample bits[0:11] -> word counter
            word_counter_mask = 0x7FF #11 LSBs
            word_bits = 11
            bits_per_sample = 14
            last_three_samples = np.array([], dtype = self.FG_DTYPE)
            for i in range(1, len(data)):
                if (i % 8 == 0):
                    last_three_samples = np.append(last_three_samples, data[i-3:i])
            #Process bits for word counter
            word_count_l = np.bitwise_and(last_three_samples[2::3], word_counter_mask) #word counter represented by the 11 LSBs of the last sample
            frame_count_l = np.array([], dtype = self.FG_DTYPE)
            #Process bits for frame counter
            for i in range(last_three_samples[0], len(last_three_samples), 3):
                frame_num = ((last_three_samples[i] & 0xf) << (2*bits_per_sample - word_bits)) + (last_three_samples[i+1] << (bits_per_sample - word_bits)) + (last_three_samples[i+2] >> word_bits) 
                frame_count_l = np.append(frame_count_l,frame_num)

        elif self.PLATFORM == "ICE":
            return
        
        plt.figure(f"{number_of_bursts}")
        plt.plot(frame_count_l, label = "frame count")
        plt.plot(word_count_l, label = "word count")
        plt.xlabel("Word number")
        plt.ylabel("Count")
        plt.title(f"Frame/Word Count with: \n{frames_per_burst} frames per burst, {number_of_bursts} bursts and {burst_period_in_frames} frames between bursts")
        plt.savefig(PLOT_DIR/f"Frame and word counter with {frames_per_burst=}, {number_of_bursts=}")
        
        unique_frame_count = np.unique(frame_count_l)
        

        logger.debug(f"{unique_frame_count=}")

        #Assertions for frame counter
        logger.debug(f"{frames_per_burst=}, {number_of_bursts=}, {burst_period_in_frames=}")
        # assert len(timestamp) == len(unique_frame_count)
        # logger.debug(f"Timestamp values are identical to frame counts captured in tdata")

        logger.debug(f"Initial frame count: {unique_frame_count[0]}. Final frame count: {unique_frame_count[-1]}")
        # expected_final_frame = frame_count_l[0] + number_of_bursts * frames_per_burst + (number_of_bursts - 1) * burst_period_in_frames
        expected_final_frame = frame_count_l[0] + (number_of_bursts - 1) * burst_period_in_frames + 1 #Frames within the same burst are the same count
        assert frame_count_l[-1] == expected_final_frame
        logger.debug(f"Expected final frame number is correct")

        #Assertions for word counter
        overflows = 0
        for i in range(len(word_count_l) - 1):
            if word_count_l[i] == 2 ** word_bits - 1 and word_count_l[i+1] == 0:
                overflows += 1
            elif word_count_l[i+1] - word_count_l[i] != 1:
                assert False
        assert len(unique_frame_count) - 1 == overflows
        logger.debug(f"Word count is correct")

        with open(PLOT_DIR/f"Frame and word counter with {frames_per_burst=}, {number_of_bursts=}", "w") as f:
            f.write(f"{frames_per_burst=}, {number_of_bursts=}, {burst_period_in_frames=} \nframes: \n")
            for frame in unique_frame_count:
                f.write(f"{frame}\n")

         
    @pytest.mark.parametrize("frames_per_burst, number_of_bursts, burst_period_in_frames, mode", [(10,3,4000, "frame4"), (10,2,4000, "frame4"), (10,10,4000, "frame4")])
    def test_frame_counter(self, board_conn, setup_funcgen, frames_per_burst, number_of_bursts, burst_period_in_frames, mode):
        """Test for mode: "frame8" or "frame4. Test that frame counter has the correct count according to the number of bursts and frames per burst."""
        bits_per_sample = 14 if self.PLATFORM == "CRS" else 8
        logger = self.get_logger()
        timestamp,data,count = self._set_capture_funcgen_frames(
            mode,
            frames_per_burst = frames_per_burst, 
            number_of_bursts = number_of_bursts, 
            burst_period_in_frames = burst_period_in_frames,
        )
        if mode == "frame4":
            #4 LSBs of frame counter is in the 4 MSBs of each sample for both CRS and ICE
            shift = bits_per_sample - 4 #For CRS, shift right by 10 bits. For ICE, by 4 bits.
            frame_overflow_bit = 4
        else:
            #For CRS, the 12 LSBs of the frame count is in the 12 MSBs of each sample.
            #For ICE, the 6 LSBs of the frame count is in the 6 MSBs of each sample.
            shift = 2
            frame_overflow_bit = 12 if self.PLATFORM == "CRS" else 6
        data = data >> shift
        unique_frame_count = np.array([], dtype=self.FG_DTYPE)
        prev_data = data[0]
        for el in data:
            if el != prev_data:
                unique_frame_count = np.append(unique_frame_count, el)
                prev_data = el

        print(unique_frame_count)

        #problem: frame counter is not capped at 2**12 (4096) 

        with open(PLOT_DIR/f"Frame counter with {frames_per_burst=}, {number_of_bursts=}.txt", "w") as f:
            f.write(f"{frames_per_burst=}, {number_of_bursts=}, {burst_period_in_frames=} \nframes: \n")
            #check if number of frames between each burst is correct
            #Frame counter overflows at 2**12 (CRS) and 2**6 (ICE)
            prev_frame = unique_frame_count[0]
            for frame in unique_frame_count[2::2]:
                logger.debug(f"{prev_frame=}")
                f.write(f"{prev_frame=}\n")
                logger.debug(f"{frame=}\n")
                f.write(f"{frame=}\n")
                if frame < prev_frame: 
                    diff = frame + 2**frame_overflow_bit - prev_frame
                else:
                    diff = frame - prev_frame
                logger.debug(f"{diff}")
                f.write(f"{diff=}\n")
                assert diff == burst_period_in_frames
                prev_frame = frame
            logger.debug(f"Frame counter is correct")
        

        plt.figure(f"{number_of_bursts}")
        plt.plot(data, label = "frame count")
        plt.xlabel("Number of samples")
        plt.ylabel("Count")
        plt.title(f"Frame Count with {frames_per_burst} frames per burst, {number_of_bursts} bursts and {burst_period_in_frames} frames between bursts")
        plt.savefig(PLOT_DIR/f"{mode} counter with {frames_per_burst=}, {number_of_bursts=}")

        

        

        