import logging
import numpy as np
from test_setup import board_conn, setup_funcgen, TEST_CONFIG, CONN_CONFIG
from utils import plot_comp_data
import pytest
import socket
import psutil
from net_tools import ping_sources_async
from functools import wraps 
import sts
import matplotlib.pyplot as plt
import math
from test_setup import PLOT_DIR
from time import sleep


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
    seeds = [-7680, 7744, -14296, -65, -32175, -29190, 30160, 5679, -2070, 24601, 29784, -18765, -25554, -10744, -27608, 3207, 5129, 5031, 22606, 11371, 2446, -28089, 29554, -24103, -26437, 18246, -6527, 10486, -25707, -5372, -16068, 25810, 14648, 23623, 4812, 4715, -2645, -28820, -15584, 13563, 32522, 31152, 17351, -22105, -2246, 25818, 17051, -2280, -25287, -20404, -15797, -12642, -15709, -31140, 7986, 22594, -6864, -32133, 11524, -4534, -11304, 16974, -14582, -19158, -30167, 18625, 24000, -12775, -2598, 10724, -17769, -6480, -21887, -20074, -20059, 14521, -5225, 4359, 6366, 30513, -25340, 4396, -224, -4468, 28533, -14307, 13536, -24931, 20594, -30438, -10245, -4246, 25084, -3154, 26509, -16821, -1224, 10499, -16869, -1795]

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

    def _set_capture_funcgen(self, source: str, period: float = 1, frames_per_burst: int = 2, number_of_bursts: int = 1, **func_kwargs):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(period=period, source='adc', frames_per_burst = frames_per_burst, number_of_bursts = number_of_bursts)
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source, **func_kwargs)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        if self.PLATFORM == "CRS":
            _, data, _ = receiver.read_raw_frames(format='16',split = True, ncap=number_of_bursts)
        else:
            _, data, _ = receiver.read_raw_frames()
        data = data[0] >> self.FG_LSHIFT
        return data
    
    @staticmethod
    def _compare_data(data: np.ndarray, ref_data: np.ndarray):
        pass

    # @compare_plot_data
    def test_funcgen_ramp(self, board_conn, setup_funcgen):
        ref_data = (np.arange(self.FG_NS, dtype="u2")<<self.FG_LSHIFT).view("i1")>>self.FG_LSHIFT
        data = self._set_capture_funcgen('ramp')
        # plt.plot(data[0],label="data")
        plt.plot(ref_data, data="expected")
        plt.legend()
        plt.title(ref_data.shape)
        plt.savefig(PLOT_DIR/f"ramp")
        # return data, ref_data

    @compare_plot_data
    def test_funcgen_sin(self, board_conn, setup_funcgen):
        sin_freq = 1
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * sin_freq) * 127).astype('i2')
        data = self._set_capture_funcgen('sin', freq=sin_freq, ampl=127)
        plt.plot(data[0],label="data")
        plt.plot(ref_data, data="expected")
        plt.legend()
        plt.savefig(PLOT_DIR/f"sin")
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

    @pytest.mark.parametrize("seed", seeds[:10])
    def test_funcgen_deterministic(self, board_conn, setup_funcgen, seed):
        data_1 = self._set_capture_funcgen('noise', fft_bypass=True, scaler_bypass=True, seed = seed)
        data_2 = self._set_capture_funcgen('noise', fft_bypass=True, scaler_bypass=True, seed = seed)
        plot_comp_data("deterministic", data_1, data_2)
        assert np.array_equal(data_1, data_2)

    @pytest.mark.parametrize("seed", seeds[:10])
    def test_funcgen_deterministic_after_rst_lfsr(self, board_conn, setup_funcgen, seed):
        # Testing that noise is the same before and afer resetting the lfsr
        self.board.start_data_capture(period=1, source='adc', frames_per_burst = 1, number_of_bursts = 0)
        self.board.set_channelizer(data_source='noise', fft_bypass=True, scaler_bypass=True, seed = seed)
        receiver = self.board.get_data_receiver()
        if self.PLATFORM == "CRS":
            _, data_1, _ = receiver.read_raw_frames(format='16',split = True)
            self.board.chan[0].FUNCGEN.reset_noise()
            _, data_2, _ = receiver.read_raw_frames(format='16',split = True)
        else:
            _, data_1, _ = receiver.read_raw_frames()
            self.board.chan[0].FUNCGEN.reset_noise()
            _, data_2, _ = receiver.read_raw_frames()
        data_1 = data_1 >> self.FG_LSHIFT
        data_2 = data_2 >> self.FG_LSHIFT

        plt.figure()
        plt.plot(data_1)
        plt.plot(data_2)
        plt.savefig(PLOT_DIR/f"lfspr_rst with {seed=}")
        assert np.array_equal(data_1, data_2)

    @pytest.mark.parametrize("seed", seeds[:10])
    def test_funcgen_deterministic_after_rst_lfsr(self, board_conn, setup_funcgen, seed):
    # have two channelizers generating noise. reset one of the channelizers to a different seed. correlate to check how different they are. 
        self.board.start_data_capture(period=1, source='adc', frames_per_burst = 2, number_of_bursts = 0)
        self.board.set_channelizer(data_source='noise', fft_bypass=True, scaler_bypass=True, seed = seed, chans = [0, 1])
        receiver = self.board.get_data_receiver()
        self.board.chan[1].FUNCGEN.reset_noise()
        _, data, _ = receiver.read_raw_frames(format='16',split = True)
        assert not np.array_equal(data[0], data[1])

    def test_lfsr_output(self, board_conn, setup_funcgen):
        """Test randomness of noise generator using chi-square test"""
        logger = self.get_logger()
        a = np.zeros(10)
        a = a + 1
        data = self._set_capture_funcgen('noise',fft_bypass=True, scaler_bypass=True, seed = self.seeds[0]).view("u2")
        processed_data = self.noise_data_process(data, self.board.ADC_BITS_PER_SAMPLE)
        processed_data = np.unpackbits(processed_data)
        np.savetxt(PLOT_DIR/f'random.txt', processed_data, fmt='%.1d', delimiter=' ', newline='')

    def test_nist_random_tests(self, board_conn, setup_funcgen):
        logger = self.get_logger()
        for i in range(len(self.seeds[:10])):
            data = self._set_capture_funcgen('noise',fft_bypass=True, scaler_bypass=True, seed = self.seeds[i]).view("u2")
            processed_data = self.noise_data_process(data, self.board.ADC_BITS_PER_SAMPLE).view('u1')
            processed_data = processed_data.tolist()
            # p_val = sts.frequency(processed_data)
            sts.discrete_fourier_transform(processed_data)
    
    def test_funcgen_random_pval(self, board_conn, setup_funcgen):
        """Monobit test on funcgen noise generator. P-val > 0.01 indicates randomness"""
        p_val_threshold = 0.01
        p_val_l= np.zeros(len(self.seeds))
        for i in range(len(self.seeds)):
            sum = 0
            data = self._set_capture_funcgen('noise',fft_bypass=True, scaler_bypass=True, seed = self.seeds[i]).view("u2")
            data = np.unpackbits(self.noise_data_process(data, self.board.ADC_BITS_PER_SAMPLE))
            for bit in data:
                if bit == 0:
                    bit = -1
                sum += bit
            sn = abs(sum) / math.sqrt(len(data))
            p_val = math.erfc(sn/np.sqrt(2))
            p_val_l[i] = p_val
        plt.plot(self.seeds, p_val_l, marker='o', linestyle='None')
        plt.ylabel("p-val")
        plt.xlabel("seed")
        plt.title("p-val")
        # plt.legend()
        plt.savefig(PLOT_DIR/"monobit test on noise")
        p = 1 - p_val_threshold
        success_proportion = np.sum(p_val_l >= p_val_threshold) / len(self.seeds)
        print(f"Number of successful pvals (less than 0.01): {np.sum(p_val_l >= p_val_threshold)}")
        print(f"Percentage of successful runs: {success_proportion * 100}%")
        assert success_proportion >= (p - 3 * math.sqrt(p * (1 - p) / len(self.seeds))) and success_proportion <= (p + 3 * math.sqrt(p * (1 - p) / len(self.seeds)))


    def noise_data_process(self, data_arr, bits_per_sample):
        """
        Transforms data of numpy type 'u2' into 'u1',
        where only the 14 LSBs of each u2 sample are processed
        and packed into bytes.
        """
        assert bits_per_sample <= 16, "Invalid bits_per_sample"
        processed_data_arr = np.zeros(len(data_arr))
        for i in range(len(data_arr)):
            data = data_arr[i]
            total_bits = bits_per_sample * len(data)
            total_bytes = math.ceil(total_bits / 8)
            processed_data = np.zeros(total_bytes, dtype='u1')

            bit_buffer = 0
            bit_count = 0
            byte_idx = 0

            for sample in data:
                sample &= (1 << bits_per_sample) - 1  # keep only lowest `bits_per_sample` bits
                bit_buffer = (bit_buffer << bits_per_sample) | sample
                bit_count += bits_per_sample

                while bit_count >= 8:
                    bit_count -= 8
                    byte = (bit_buffer >> bit_count) & 0xFF
                    processed_data[byte_idx] = byte
                    byte_idx += 1

            # If any bits remain (pad the last byte)
            if bit_count > 0:
                processed_data[byte_idx] = (bit_buffer << (8 - bit_count)) & 0xFF
            processed_data_arr.append(processed_data)

        return processed_data_arr
    
    
    def test_call_process_data(self, board_conn, setup_funcgen):
        data = self._set_capture_funcgen('noise', fft_bypass=True, scaler_bypass=True, seed = self.seeds[0]).view("u1")
        print(f"data: {data}")
        data_2 = self.noise_data_process(data, self.board.ADC_BITS_PER_SAMPLE)
        print(f"processed data into bytes: {data_2=}")
        
    def test_funcgen_noise_graphs(self, board_conn, setup_funcgen):
        """Histogram of noise"""
        frames_per_burst = 2
        number_of_bursts = 10
        burst_period_in_frames = 1000
        total_samples = frames_per_burst * number_of_bursts * self.board.ADC_SAMPLES_PER_FRAME
        num_seeds = 100
        psd_a = np.empty((num_seeds, total_samples))
        for i in range(num_seeds):
            seed=self.seeds[i]
            data = self._set_capture_funcgen('noise', number_of_bursts = number_of_bursts, fft_bypass=True, scaler_bypass=True, seed = seed).view("i2") #check first channelizer
            data = data.flatten()
            print(data.shape)
            #Plot the histogram
            std_deviation = np.std(data)
            avg = np.average(data)
            upper_deviation = avg + std_deviation
            lower_deviation = avg - std_deviation
            plt.figure(f"histogram of noise with {seed=}")
            # plt.plot()
            bins = 1000
            plt.hist(data, bins, label=f"{seed=}")
            # plt.plot(np.full(bins, upper_deviation), label = "upper",linestyle='--')
            # plt.plot(np.full(bins, lower_deviation), label = "lower",linestyle='--')
            plt.xlabel("noise value")
            plt.ylabel("count")
            plt.title(f"histogram of noise with {seed=}")
            plt.legend()
            plt.savefig(PLOT_DIR/f"noise histogram with {seed=}")
            plt.close()

            #Only relevant for gaussian noise:
            #Test that noise value are within one standard deviance of the mean of the noise values
            # values_within_std = sum((data >= lower_deviation)&(data <= upper_deviation))
            # assert values_within_std/num_seeds(data) >= 0.68

            #Plot histogram with counts for each specific value
            unique, counts = np.unique(data, return_counts=True)
            plt.figure(f"More specific histogram with {seed=}")
            plt.scatter(unique, counts, s=1)
            plt.title(f"Values tht appear the most often and the least often with {seed=}")
            # plt.plot(np.full(len(data), upper_deviation), label = "upper",linestyle='--')
            # plt.plot(np.full(len(data), lower_deviation), label = "lower",linestyle='--')
            plt.xlabel("noise value")
            plt.ylabel("count")
            plt.savefig(PLOT_DIR/f"More specific histogram with {seed=}")
            plt.close()

            #Plot the values that appear the most often and the least often
            unique, counts = np.unique(data, return_counts=True)
            min_count = np.min(counts)
            max_count = np.max(counts)

            min_values = [unique[idx] for idx, value in enumerate(counts) if counts[idx] == min_count]
            max_values = [unique[idx] for idx, value in enumerate(counts) if counts[idx]== max_count]
            plt.scatter(min_values, np.full(len(min_values), min_count), label = "values with min count", s=1)
            plt.scatter(max_values, np.full(len(max_values), max_count), label = "values with max count", s=1)
            plt.xlabel("noise value")
            plt.ylabel("count")
            # plt.legend()
            plt.savefig(PLOT_DIR/f"noise value with min and max counts with {seed=}")
            plt.close()

            # #Plot the Power Spectrum Density of noise
            # plt.figure(f"Power Spectrum Density of noise with {seed=}")
            # plt.psd(data)
            # plt.title(f"Power Spectrum Density of noise with {seed=}")
            # plt.savefig(PLOT_DIR/f"Power Spectrum Density with {seed=}")
            # plt.close()
            
            #Plot the Fourier Transform of noise
            psd_a[i] = (np.abs(np.fft.fft(data)))**2
        psd_avg = psd_a[0]
        for psd in psd_a[1:]:
            psd_avg += psd
        psd_avg = np.divide(psd_avg, num_seeds)
        np.savetxt(PLOT_DIR/f'random_fft_avg.txt', psd_avg, fmt='%d', delimiter=',', newline='')

        plt.figure(f"Average of Fourier Transforms of noise values")
        plt.plot(psd_avg)
        plt.ylim(0, max(psd_avg))
        plt.xlabel("frequency")
        plt.ylabel("magnitude")
        plt.title(f"Fourier Transform of noise")
        plt.savefig(PLOT_DIR/f"Fourier Transform of noise values")
        plt.close()

    def test_expected_python_random_noise_fft(self,board_conn, setup_funcgen):
        num_runs = 100
        frames_per_burst = 2
        number_of_bursts = 10
        num_samples = frames_per_burst * number_of_bursts * self.FG_NS
        psd_avg = np.zeros(num_samples)
        for j in range(num_runs):
            #number of noise values per run
            rand_arr = np.zeros(num_samples)
            for i in range(len(rand_arr)):
                rand_arr[i] = np.random.randint(- 2**(self.board.ADC_BITS_PER_SAMPLE - 1), 2**(self.board.ADC_BITS_PER_SAMPLE - 1) -1)
            psd = (np.abs(np.fft.fft(rand_arr)))**2
            psd_avg += psd
        psd_avg = np.divide(psd_avg, num_runs)
        plt.figure(f"Average of Fourier Transforms of noise values")
        plt.plot(psd_avg)
        plt.ylim(0, max(psd_avg))
        plt.xlabel("frequency")
        plt.ylabel("magnitude")
        plt.title(f"Fourier Transform of python simulation")
        plt.savefig(PLOT_DIR/f"Python simulation noise fft")
        plt.close()

    def test_expected_python_random_noise_histogram(self,board_conn, setup_funcgen):
        frames_per_burst = 2
        number_of_bursts = 10
        num_samples = frames_per_burst * number_of_bursts * self.FG_NS
        data = np.zeros(num_samples)
        for i in range(len(data)):
            data[i] = np.random.randint(- 2**(self.board.ADC_BITS_PER_SAMPLE - 1), 2**(self.board.ADC_BITS_PER_SAMPLE - 1) -1)

        #Plot histogram with counts for each specific value
        unique, counts = np.unique(data, return_counts=True)
        plt.figure(f"More specific histogram with python simulation")
        plt.scatter(unique, counts, s=1)
        plt.title(f"Values tht appear the most often and the least often with python simulation")
        # plt.plot(np.full(len(data), upper_deviation), label = "upper",linestyle='--')
        # plt.plot(np.full(len(data), lower_deviation), label = "lower",linestyle='--')
        plt.xlabel("noise value")
        plt.ylabel("count")
        plt.savefig(PLOT_DIR/f"More specific histogram with python simulation")
        plt.close()

    def test_expected_python_random_noise_min_max(self,board_conn, setup_funcgen):
        frames_per_burst = 2
        number_of_bursts = 10
        num_samples = frames_per_burst * number_of_bursts * self.FG_NS
        data = np.zeros(num_samples)
        for i in range(len(data)):
            data[i] = np.random.randint(- 2**(self.board.ADC_BITS_PER_SAMPLE - 1), 2**(self.board.ADC_BITS_PER_SAMPLE - 1) -1)

        unique, counts = np.unique(data, return_counts=True)
        min_count = np.min(counts)
        max_count = np.max(counts)

        min_values = [unique[idx] for idx, value in enumerate(counts) if counts[idx] == min_count]
        max_values = [unique[idx] for idx, value in enumerate(counts) if counts[idx]== max_count]
        plt.scatter(min_values, np.full(len(min_values), min_count), label = "values with min count", s=1)
        plt.scatter(max_values, np.full(len(max_values), max_count), label = "values with max count", s=1)
        plt.xlabel("noise value")
        plt.ylabel("count")
        # plt.legend()
        plt.savefig(PLOT_DIR/f"noise value with min and max counts with python sim")
        plt.close()



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


    def _set_capture_funcgen_frames(self, source: str, **func_kwargs):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(source='adc', verbose = 1, **func_kwargs)
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        if self.PLATFORM == "CRS":
            ncap = func_kwargs.get('number_of_bursts', 1)
            timestamp, data, count = receiver.read_raw_frames(format='16', split = True, ncap = ncap)
        else:
            timestamp, data, count = receiver.read_raw_frames()
        data = (data.astype(self.FG_DTYPE) >> self.FG_LSHIFT)
        return timestamp, data[0].flatten(), count
    
    def _set_capture_funcgen_frames_noise(self, source: str, frames_per_burst, number_of_bursts, burst_period_in_frames):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(source='adc', verbose = 1, frames_per_burst = frames_per_burst, number_of_bursts = number_of_bursts, burst_period_in_frames=burst_period_in_frames)
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        if self.PLATFORM == "CRS":
            ncap = number_of_bursts
            logger.debug(f"{ncap=}")
            timestamp, data, count = receiver.read_raw_frames(format='16', split = True, ncap = ncap)
        else:
            timestamp, data, count = receiver.read_raw_frames()
        data = (data.astype(self.FG_DTYPE) >> self.FG_LSHIFT)
        return data[0].flatten()
    
    @pytest.mark.parametrize("frames_per_burst, number_of_bursts, burst_period_in_frames", [(2, 1, 5000), (2, 4, 5000), (2, 2, 10000), (2, 5, 10000)])
    def test_word_ctr_buffer_flags(self, board_conn, setup_funcgen, frames_per_burst, number_of_bursts, burst_period_in_frames):
        """Test for mode: "word_ctr_buffer_flags". Test that frame counter and word counter have the correct count according to the number of bursts and frames per burst.
        For CRS, we are calling read_raw_frames with format='16' and split = True, so each specified frame is actually two frames (with different frame count since word count overflows at 2048)"""
        logger = self.get_logger()
        timestamp, data, count = self._set_capture_funcgen_frames(
            "word_ctr_buffer_flags", 
            frames_per_burst=frames_per_burst, 
            number_of_bursts=number_of_bursts, 
            burst_period_in_frames=burst_period_in_frames
        )
        words_per_frame = self.FG_NS // self.board.SAMPLES_PER_WORD
        words_per_burst = words_per_frame * frames_per_burst
        words_per_cap = words_per_burst * number_of_bursts
        K = (32 + self.board.ADC_BITS_PER_SAMPLE + 1) // self.board.ADC_BITS_PER_SAMPLE #ceiling
        #modes
        logger.debug(f"{timestamp=}")
        if self.PLATFORM == "CRS":
            #1. Capture the last three out of eight samples of each word
            #2. Concatenate first two samples and first three bits of last sample -> Frame counter
            #3. Last sample bits[0:11] -> word counter
            word_counter_mask = 0x7FF #11 LSBs
            word_bits = 11
            self.board.ADC_BITS_PER_SAMPLE = 14
            packed_samples = np.zeros(len(data) // self.board.SAMPLES_PER_WORD, dtype = np.uint32)
            for i in range(len(packed_samples)):
                packed_samples[i] = sum(int(data[self.board.SAMPLES_PER_WORD * (i + 1) - 1 - w]) << (self.board.ADC_BITS_PER_SAMPLE * w) for w in range(K))
            #Process bits for word counter
            frame_num = packed_samples >> word_bits 
            #Process bits for frame counter
            word_count = np.bitwise_and(packed_samples, word_counter_mask)
        
        unique_frame_count = np.unique(frame_num)
        

        logger.debug(f"{unique_frame_count=}")

        #Assertions for frame counter
        logger.debug(f"{frames_per_burst=}, {number_of_bursts=}, {burst_period_in_frames=}, {words_per_burst=}, {words_per_frame=}")

        logger.debug(f"Initial frame count: {unique_frame_count[0]}. Final frame count: {unique_frame_count[-1]}")
        # expected_final_frame = frame_count_l[0] + number_of_bursts * frames_per_burst + (number_of_bursts - 1) * burst_period_in_frames
        

        cn = (np.arange(words_per_cap) // (frames_per_burst * words_per_frame)) * burst_period_in_frames #//4096
        ef = (np.arange(words_per_cap) // words_per_frame) % frames_per_burst + frame_num[0] + cn #//2048

        logger.debug(f"{ef=}")

        unique_ef = np.unique(ef)
        logger.debug(f"{unique_ef=}")

        ew = np.tile(np.arange(words_per_frame), frames_per_burst * number_of_bursts)
        
        logger.debug(f"Word count is correct")

        plt.figure(f"{number_of_bursts}")
        plt.plot(ef, marker='.', label="expected frame count")
        plt.plot(frame_num, label="measured frame count")
        plt.plot(ew, marker=".",label="rexpected frame count")
        plt.plot(word_count, label="word count")
        plt.legend()
        plt.xlabel("Word number")
        plt.ylabel("Count")
        plt.title(f"Frame/Word Count with: \n{frames_per_burst} frames per burst, {number_of_bursts} bursts and {burst_period_in_frames} frames between bursts")
        plt.savefig(PLOT_DIR/f"Frame and word counter with {frames_per_burst=}, {number_of_bursts=}")
        
        assert all(frame_num == ef)
        logger.debug(f"Frame count matches expected frame count")
        assert all(word_count== ew)
        logger.debug(f"Word count matches expected word count")

         
    @pytest.mark.parametrize("frames_per_burst, number_of_bursts, burst_period_in_frames, mode", [(2,2,4000, "frame8"), (2,5,2**11, "frame8")])
    def test_frame_counter(self, board_conn, setup_funcgen, frames_per_burst, number_of_bursts, burst_period_in_frames, mode):
        """Test for mode: "frame8" or "frame4. Test that frame counter has the correct count according to the number of bursts and frames per burst."""
        samples_per_burst = self.FG_NS * frames_per_burst
        total_samples = samples_per_burst * number_of_bursts * self.board.ADC_SAMPLES_PER_FRAME
        logger = self.get_logger()
        timestamp,data,count = self._set_capture_funcgen_frames(
            mode,
            frames_per_burst = frames_per_burst, 
            number_of_bursts = number_of_bursts, 
            burst_period_in_frames = burst_period_in_frames,
        )
        if mode == "frame4":
            #4 LSBs of frame counter is in the 4 MSBs of each sample for both CRS and ICE
            shift = self.board.ADC_BITS_PER_SAMPLE - 4 #For CRS, shift right by 10 bits. For ICE, by 4 bits.
            frame_overflow_bit = 4
        else:
            #For CRS, the 12 LSBs of the frame count is in the 12 MSBs of each sample.
            #For ICE, the 6 LSBs of the frame count is in the 6 MSBs of each sample.
            shift = 2
            frame_overflow_bit = 12 if self.PLATFORM == "CRS" else 6
        
        data = data >> shift
        ref_incr_per_frame = (np.arange(total_samples) // self.FG_NS)  % frames_per_burst
        ref = (data[0] + (np.arange(total_samples) // samples_per_burst) * burst_period_in_frames +ref_incr_per_frame) % (2**frame_overflow_bit)

        plt.figure(f"{number_of_bursts}")
        plt.plot(ref, marker=".", label="reference")
        plt.plot(data, label = "measurement")
        plt.xlabel("Number of Samples")
        plt.ylabel("Frame Count")
        plt.legend()
        plt.title(f"Frame Count with mode: {mode} \n{frames_per_burst} frames per burst, {number_of_bursts} bursts and {burst_period_in_frames} frames between bursts")
        plt.savefig(PLOT_DIR/f"{mode} counter with {frames_per_burst=}, {number_of_bursts=}")

        assert all(ref == data)
        
    @pytest.mark.parametrize("frames_per_burst, number_of_bursts, burst_period_in_frames", [(2,1,4001)])
    def test_frame_counter_nibble(self, board_conn, setup_funcgen, frames_per_burst, number_of_bursts, burst_period_in_frames):
        """Test for mode: "nibble4". Test that bits 3:0 of RAM samples are sent on even frames and bits 7:4 on odd frames."""
        #we want even frames to be 0b1111 and odd frames to be 0b1000. Send 0b11111000 aka 0xF0 on each frame
        logger = self.get_logger()
        injected_data = np.full(self.FG_NS, 0x10, dtype=self.FG_DTYPE)
        self.board.set_channelizer(data_source='buffer', buffer=injected_data, channels=[0])
        self.board.chan[0].FUNCGEN.set_buffer(injected_data)
        _,data,_ = self._set_capture_funcgen_frames(
            'nibble4',
            frames_per_burst = frames_per_burst, 
            number_of_bursts = number_of_bursts, 
            burst_period_in_frames = burst_period_in_frames,
        )
        data = data >> self.board.ADC_BITS_PER_SAMPLE - 4 # bits are aligned at 4MSBS of each sample
        logger.debug(f"{data=}")
        second_frame = 0x0 if data[0] % 2 == 1 else 0x1
        expected_data = np.repeat(np.array([data[0],second_frame]), self.FG_NS).astype(self.FG_DTYPE)
        plt.figure(f"{number_of_bursts}")
        plt.plot(expected_data, marker=".", linestyle='', label='expected')
        plt.plot(data, label='measured')
        plt.xlabel("Number of Samples")
        plt.ylabel("Buffer output")
        plt.title(f"Frame Count with mode: nibble4 \n{frames_per_burst} frames per burst, {number_of_bursts} bursts and {burst_period_in_frames} frames between bursts")
        plt.legend()
        plt.savefig(PLOT_DIR/f"nibble4_{burst_period_in_frames=}")

    @pytest.mark.parametrize("expected_overflows", [0, 254, 255, 256])
    def test_overflow_ctr(self, board_conn, setup_funcgen, expected_overflows):
        """Test that the overflow counter displays the right amount of overflows
            at the last word of each frame"""
        injected_data = np.full(self.FG_NS, 2**self.board.ADC_BITS_PER_SAMPLE)
        logger = self.get_logger()
        # for i in range(expected_overflows):
        #     injected_data[i] == 2**self.board.ADC_BITS_PER_SAMPLE
        for chan in self.board.chan.values():
            measured_overflows = chan.FUNCGEN.CLIP_WIDTH = 3
        self.board.set_channelizer(data_source='buffer', data=injected_data)
        data = self._set_capture_funcgen('buffer', data=injected_data)
        logger.debug(data)
        plt.plot(data)
        plt.show()
        for chan in self.board.chan.values():
            measured_overflows = chan.FUNCGEN.ADC_OVERFLOW_CTR
            assert measured_overflows == expected_overflows

    def test_stats_reset(self, board_conn, setup_funcgen):
        """Test that overflow counter resets with stats_reset"""
        injected_overflows = 256
        logger = self.get_logger()
        injected_data = np.zeros(self.FG_NS)
        for i in range(injected_overflows):
            injected_data[i] == 2**self.board.ADC_BITS_PER_SAMPLE
        self.board.set_channelizer(data_source='buffer', buffer=injected_data)
        logger.debug(f"Started data capture")
        self._set_capture_funcgen('buffer', data=injected_data)
        self.board.stop_data_capture()
        logger.debug(f"Stopped data capture")
        for chan in self.board.chan.values():
            chan.FUNCGEN.reset_stats()
            measured_overflows = chan.FUNCGEN.ADC_OVERFLOW_CTR
            assert measured_overflows == 0

    def test_reset(self, board_conn, setup_funcgen):
        logger = self.get_logger()
        injected_data = np.zeros(self.FG_NS)
        self.board.set_channelizer(data_source='buffer', buffer=injected_data)
        logger.debug(f"Started data capture")
        self._set_capture_funcgen('buffer', data=injected_data)
        self.board.stop_data_capture()
        logger.debug(f"Stopped data capture")
        for chan in self.board.chan.values():
            chan.FUNCGEN.RESET = 1
            logger.debug(f"Channelizer {chan} reset")

        for chan in self.board.chan.values():
            assert chan.FUNCGEN.RAMP_CTR == 0
            assert chan.FUNCGEN.FRAME_CTR == 0
            assert chan.FUNCGEN.SEND_FRAME == 0
            assert chan.FUNCGEN.ADC_OVERFLOW_CTR == 0
    
    def test_word_frame_ctr_reg(self, board_conn, setup_funcgen):
        """Test that the word and frame counter registers are outputting the correct number (set by NUMBER_OF_FRAMES)"""
        num_frames_to_send = 10
        logger = self.get_logger()
        for chan in self.board.chan.values():
            chan.FUNCGEN.ENABLE = 0
            chan.FUNCGEN.RESET = 1
            assert chan.FUNCGEN.FRAME_CTR == 0
            assert chan.FUNCGEN.RAMP_CTR == 0
            chan.FUNCGEN.NUMBER_OF_FRAMES = 10
            chan.FUNCGEN.ENABLE = 1
            chan.FUNCGEN.RESET = 0

        for chan in self.board.chan.values():
            assert chan.FUNCGEN.FRAME_CTR == num_frames_to_send
            assert chan.FUNCGEN.RAMP_CTR != 0
            logger.debug(chan.FUNCGEN.RAMP_CTR)

    def test_delay_capture(self, board_conn, setup_funcgen):
        """Test delay capture. Same as with scalar."""
        for ch in self.board.chan:
            ch.FUNCGEN.RESET = 1
        sleep(0.1)
        for ch in self.board.chan:
            ch.FUNCGEN.RESET = 0
        self._set_capture_funcgen('ramp')
        delay_ctrs = [ch.FUNCGEN.DELAY_CTR for ch in self.board.chan.values()]
        logger = self.get_logger()
        logger.debug(delay_ctrs)
        assert(len(set(delay_ctrs)) == 1) #ensure all delay counters are the same
        

    # test delay_capture_ctr
    @pytest.mark.parametrize("shift", range(5))
    def test_right_shift(self, board_conn, setup_funcgen, shift):
        """Test that the ouput is right shifted by specified bits then saturated at clip width"""
        logger = self.get_logger()
        injected_values = [1,-1, 8, -8]
        self.board.chan[0].FUNCGEN.CLIP_WIDTH = 15
        self.board.chan[0].FUNCGEN.SHIFT = shift
        for injected_value in injected_values:  
            injected_data = np.full(self.FG_NS, injected_value, dtype=self.FG_DTYPE_SIGNED)
            expected_data = injected_data >> shift
            self.board.set_channelizer(data_source='buffer', buffer=injected_data, channels=[0, 1])
            data = self._set_capture_funcgen('buffer', data=injected_data)
            plt.figure(f"{shift} with {injected_value}")
            plt.plot(expected_data, marker=".", linestyle='', label='expected')
            plt.plot(data, label='measured')
            plt.title(f"Right shift by {shift} and injected data {injected_value}")
            plt.legend()
            plt.savefig(PLOT_DIR/f"Right shift by {shift} and injected data {injected_value}")
            assert np.array_equal(data, expected_data)

    @pytest.mark.parametrize("shift, clip_width", [(0,3), (1,6), (3,5)])
    def test_shift_clip_width(self, board_conn, setup_funcgen, shift, clip_width):
        """Test that the ouput is right shifted by specified bits then saturated at clip width"""
        logger = self.get_logger()
        max = 2 ** (self.board.ADC_BITS_PER_SAMPLE - 1) - 1
        min = - 2 **(self.board.ADC_BITS_PER_SAMPLE - 1)
        max_clipped = 2 ** clip_width - 1
        min_clipped = -2 ** clip_width
        injected_values = [max, min, 1, -1, max_clipped - 1, max_clipped + 1, min_clipped - 1, min_clipped - 2, min_clipped + 1]
        expected_values = []
        for value in injected_values:
            value = value >> shift
            if value >= max_clipped:
                expected_values.append(max_clipped)
            elif value <= min_clipped:
                expected_values.append(min_clipped)
            else:
                expected_values.append(value)
        self.board.chan[0].FUNCGEN.SHIFT = shift
        self.board.chan[0].FUNCGEN.CLIP_WIDTH = clip_width
        for injected_value, expected_value in zip(injected_values, expected_values):  
            injected_data = np.full(self.FG_NS, injected_value, dtype=self.FG_DTYPE_SIGNED)
            expected_data = np.full(self.FG_NS, expected_value, dtype=self.FG_DTYPE_SIGNED)
            self.board.set_channelizer(data_source='buffer', buffer=injected_data)
            data = self._set_capture_funcgen('buffer', data=injected_data)
            plt.figure(f"{clip_width} with {injected_value}")
            plt.plot(expected_data, marker=".", linestyle='', label='expected')
            plt.plot(data, label='measured')
            plt.title(f"Clip width saturation at bit {clip_width} and injected data {injected_value}")
            plt.legend()
            plt.savefig(PLOT_DIR/f"Clip width saturatation at bit {clip_width} with {injected_value=}")
            logger.debug(f"{injected_data=}")
            print(f"{data=}")
            logger.debug(f"{expected_value=}")
            assert np.array_equal(data, expected_data)


            