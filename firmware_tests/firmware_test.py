import logging
import numpy as np
from test_setup import delete_plots, board_conn, setup_funcgen, setup_scaler, TEST_CONFIG
from utils import plot, gen_data
import pytest
import socket
import psutil
from net_tools import ping_sources_async
from functools import wraps
from itertools import product
import matplotlib.pyplot as plt
from utils import PLOT_DIR

NUM_CHANNELS = 16
FIG_WIDTH = 8
FIG_HEIGHT = 6

def compare_plot_data(test_unit):

    @wraps(test_unit)
    def wrapper(*args, **kwargs):
        res = test_unit(*args, **kwargs)
        data = res[0][0]
        ref_data = res[0][1]
        title = test_unit.__name__[5:] if len(res) < 2 else res[1]
        folder = test_unit.__name__[5:] if len(res) >= 2 else None 
        plot_kwargs = {} if len(res) < 3 else res[2]
        for i in range(data.shape[0]):
            if not np.equal(data[0], data[i]).all():
                plot(datasets=[data[0], data[i]], labels=["First channel", f"{i}th channel"], title=f"Different channeliser outputs for {title}")
            np.testing.assert_equal(data[0], data[i])
        if TEST_CONFIG['always_plot'] or (TEST_CONFIG['plot_on_failure'] and not np.equal(data, ref_data).all()):
            plot(datasets=[data[0], *res[0][1:]], labels=['Returned', 'Reference'], title=title, folder=folder, **plot_kwargs)
        np.testing.assert_equal(data[0], ref_data)
    return wrapper

'''def get_func(name):
    if name not in TEST_CONFIG: return {'func': 'const', 'a': 0}
    elif 'func' not in TEST_CONFIG[name]: return {'func': 'const', 'a': 0}
    args = TEST_CONFIG[name]['func'].copy()
    func = args.pop('name', 'const')
    return {'func': func, **args}
'''

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
    FG_LSHIFT = None

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

    def _set_capture_funcgen(self, source: str, period: float = 1, **func_kwargs):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(period=period, source='adc')
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source, **func_kwargs)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        timestamp, data, count = receiver.read_raw_frames()
        return data

    @staticmethod
    def _compare_data(data: np.ndarray, ref_data: np.ndarray):
        pass

    @compare_plot_data
    def test_funcgen_ramp(self, board_conn, setup_funcgen):
        ref_data = np.arange(self.FG_NS, dtype=self.FG_DTYPE).view('i1')
        data = self._set_capture_funcgen('ramp')
        return [data, ref_data],

    @compare_plot_data
    def test_funcgen_sin(self, board_conn, setup_funcgen):
        sin_freq = 1
        # np.sin(np.arange(self.NS) * 2 * np.pi / self.NS * freq) * (ampl if ampl is not None else (1 << (self.Nbits - 1) - 1))))
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * sin_freq) * 127).astype("i1")
        data = self._set_capture_funcgen('sin', freq=sin_freq, ampl=127)
        return [data, ref_data],

    @compare_plot_data
    def test_funcgen_arb(self, board_conn, setup_funcgen):
        freq_sin = 1
        freq_cos = 2
        t = np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS
        ref_data = (np.sin(t * freq_sin) * 127 / 2 + np.cos(t * freq_cos) * 127 / 2).astype("i1")
        data = self._set_capture_funcgen('arb', data=ref_data)
        return [data, ref_data],

    @compare_plot_data
    def test_funcgen_const(self, board_conn, setup_funcgen):
        a = 13 << self.FG_LSHIFT
        ref_data = np.full(self.FG_NS, a, self.FG_DTYPE).view('u1')
        data = self._set_capture_funcgen('a', a=a)
        return [data, ref_data],

    @compare_plot_data
    def test_funcgen_ab(self, board_conn, setup_funcgen):
        a = 13 << self.FG_LSHIFT
        b = 42 << self.FG_LSHIFT
        ref_data = np.tile(np.array((a, b), self.FG_DTYPE), self.FG_NS // 2).view('u1')
        data = self._set_capture_funcgen('ab', period=0.01, a=a, b=b)
        return [data, ref_data],

    @compare_plot_data
    def test_funcgen_real_ramp(self, board_conn, setup_funcgen):
        ref_data = (np.arange(self.FG_NS // 2) << 8).astype('>u2').view("i1")
        data = self._set_capture_funcgen('real_ramp')
        return [data, ref_data],

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
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * sin_freq) * 127).astype("i1")
        return [data, ref_data],
    
    def _set_capture_scaler(self, func, **func_kwargs):
        source = gen_data(func, **func_kwargs)
        self.board.set_data_source(source='arb', data=source)
        self.board.start_data_capture(period=1, source='scaler')
        receiver = self.board.get_data_receiver()
        _, data, _ = receiver.read_raw_frames()
        return source, data//16
    
    @compare_plot_data
    @pytest.mark.scaler
    def test_scaler_all_zeroes(self, board_conn, setup_scaler):
        '''
        Set all gains to 0 and tests if output is 0 for all inputs between ramp_min and ramp_max
        '''
        self.board.set_gains(0)
        min = TEST_CONFIG['all_zeroes'].get('min', -128)
        max = TEST_CONFIG['all_zeroes'].get('max', 127)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = source * 0
        return [data, ref_data],
    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("postscaler", range(TEST_CONFIG['all_ones'].get('postscaler_min', 0), TEST_CONFIG['all_ones'].get('postscaler_max', 31)))
    def test_scaler_all_ones(self, postscaler, board_conn, setup_scaler):
        '''
        Sets all gains to 1 and tests if the output is merely a shifted and truncated copy of the input.

        Tests all values of the postscaler between postscaler_min and postscaler_max, and the input ranges between ramp_min and ramp_max
        '''
        self.board.set_gains(1, postscaler=postscaler)
        min = TEST_CONFIG['all_ones'].get('min', -128)
        max = TEST_CONFIG['all_ones'].get('max', 127)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(source * 2**10 * 2**postscaler // 2**31, -8, 7)
        return [data, ref_data], f"all_ones[glog={postscaler}]"

    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("period", range(TEST_CONFIG['alternating_gain'].get('min_period', 2), TEST_CONFIG['alternating_gain'].get('max_period', 3), TEST_CONFIG['alternating_gain'].get('step', 1)))
    def test_alternating_gain(self, period, board_conn, setup_scaler):
        '''
        Tests that the gains are being applied to the correct bin. 
        
        It does so by setting the gains uniformly to 0, save for each periodth gain, which is set to 1. The period ranges from min_period to max_period in bounds of step.

        The input data is a periodic ramp which ranges from ramp_min to ramp_max. This differs from the earlier ramps in that they cover the range once in the frame, whereas this periodic ramp covers the range as many times as possible in each frame.
        '''
        #checks that per-bin gains work and also the alignment of frequency bins in input to output
        gains = np.tile([*np.repeat(0, period - 1), 1], self.FG_NS//(2 * period))
        gains = np.append(gains, (np.repeat(0, self.FG_NS//2 - gains.size)))
        self.board.set_gains(gains, 21)
        min = TEST_CONFIG['alternating_gain'].get('min', -8)
        max = TEST_CONFIG['alternating_gain'].get('max', 7)
        source, data = self._set_capture_scaler('periodic_ramp', min=min, max=max)
        ref_data = np.clip(source * np.repeat(gains, 2), -8, 7)
        return [data, ref_data], f"alternating_gain[period={period}]"

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize(
        "postscaler,gain", product(
            range(TEST_CONFIG['constant_gain'].get('postscaler_min', 0), TEST_CONFIG['constant_gain'].get('postscaler_max', 31)), 
            TEST_CONFIG['constant_gain'].get('gains', []),
        )
    )
    def test_constant_gain(self, postscaler, gain, board_conn, setup_scaler):
        '''
        Tests the linear gains.

        Sets all gains to each gain specified in gains and allows the postscaler to range between postscaler_min and postscaler_max. Tests if output corresponds to scaled, shifted and truncated copy of the input.

        Input data is a ramp ranging from ramp_min to ramp_max
        '''
        self.board.set_gains(gain, postscaler=postscaler)
        min = TEST_CONFIG['constant_gain'].get('min', -128)
        max = TEST_CONFIG['constant_gain'].get('max', 127)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(gain * source * 2**10 * 2**postscaler // 2**31, -8, 7)
        return [data, ref_data], f"constant_gain[glin={gain}, glog={postscaler}]"


    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("val, sig_bit, rounding_mode", product(TEST_CONFIG['rounding'].get('test_values', [1]), range(1, 8), (1, 2)))
    def test_rounding(self, val, sig_bit, rounding_mode, board_conn, setup_scaler):
        '''
        Tests the 2 non-truncation rounding modes of the scaler.

        Sets the gain and the input so that the rounding stage of the scaler sees val.x, where x is sig_bit bits long and ranges over all possible values. The test ensures that the number is rounded up or down correctly according to the value of x.
        '''
        max_val = 2**(8 - sig_bit - 1) - 1
        min_val = -max_val - 1
        val = np.clip(val, min_val, max_val)
        self.board.set_gains((1, 21-sig_bit))
        self.board.set_scaler_rounding_mode(rounding_mode)
        source, data = self._set_capture_scaler('ramp', min=(val * 2**sig_bit), max=((val + 1) * 2**sig_bit))
        bottom = abs(source & (2**sig_bit - 1))
        if rounding_mode == 1:
            round_up = bottom >= 2**(sig_bit - 1)
        elif rounding_mode == 2:
            round_up = (bottom > 2**(sig_bit - 1)) | ((bottom == 2**(sig_bit - 1)) & (val % 2 == 1))
        ref_data = np.clip(val + round_up, -8, 7)
        return [data, ref_data], f"convergent_rounding[val={val}, sig_bit={sig_bit}, rounding={'normal' if rounding_mode == 1 else 'convergent'}]"
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("postscaler", range(TEST_CONFIG['symmetric_saturation'].get('postscaler_min', 0), TEST_CONFIG['symmetric_saturation'].get('postscaler_max', 31)))
    def test_symmetric_saturation(self, postscaler, board_conn, setup_scaler):
        '''
        Similar to the all_ones test above, except with symmetric saturation enabled.
        '''
        self.board.set_symmetric_saturation(True)
        self.board.set_gains(1, postscaler)
        min = TEST_CONFIG['constant_gain'].get('min', -128)
        max = TEST_CONFIG['constant_gain'].get('max', 127)
        source, data  = self._set_capture_scaler(func='ramp', min=min, max=max)
        self.board.set_symmetric_saturation(False)
        ref_data = np.clip(source * 2**10 * 2**postscaler // 2**31, -7, 7)
        return [data, ref_data], "symmetric_saturation[glog={postscaler}]"
    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('rounding_mode', range(1, 3))
    def test_rounding_symmetric_saturation(self, rounding_mode, board_conn, setup_scaler):
        '''
        Similar to the rounding test above, except that val=-8 and sig_bit=4 and symmetric saturation is enabled. Tests that the output is uniformly -7.
        '''
        self.board.set_symmetric_saturation(True)
        self.board.set_scaler_rounding_mode(rounding_mode)
        self.board.set_gains(1, 21-4)
        _, data = self._set_capture_scaler('ramp', min=-8 * 16, max=-7*16)
        ref_data = np.ones(self.FG_NS) * -7
        return [data, ref_data], f"symmetric_saturation[rounding={'normal' if rounding_mode == 1 else 'convergent'}]"

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("symmetric_saturation", (False, True))
    def test_zero_on_sat(self, symmetric_saturation, board_conn, setup_scaler):
        '''
        Tests the zero on saturation functionality. Inputs a complex ramp ranging from 1 below the minimum value to 1 above the maximum value. (i.e. -9-9j, -9-8j, ..., -9+8j, -8-9j, ..., 8+8j) and tests that both the real and imaginary components are zeroed when either exceeds the bounds.
        '''
        min = TEST_CONFIG['zero_on_sat'].get('min', -9)
        max = TEST_CONFIG['zero_on_sat'].get('max', 9)
        self.board.set_gains(1, 21)
        self.board.set_zero_on_sat(True)
        self.board.set_symmetric_saturation(symmetric_saturation)
        source, data = self._set_capture_scaler(func='complex_ramp', min=min, max=max) 
        self.board.set_zero_on_sat(False)
        self.board.set_symmetric_saturation(False)
        max_val = 7
        min_val = -7 if symmetric_saturation else -8
        mask = (source < min_val) | (source > max_val)
        mask = np.repeat(mask[::2] | mask[1::2], 2) #spill from Re or Im into pair
        ref_data = source
        ref_data[mask] = 0
        return [data, ref_data], f"zero_on_sat[symmetric_saturation={bool(symmetric_saturation)}]", {'split_complex':True}

    @pytest.mark.scaler
    @pytest.mark.asyncio
    @pytest.mark.parametrize("postscaler, symmetric_saturation, frame_cnt", product(range(TEST_CONFIG['overflow_stats'].get('postscaler_min', 0), TEST_CONFIG['overflow_stats'].get('postscaler_max', 31)), (False, True), TEST_CONFIG['overflow_stats'].get('frame_cnt', 1)))
    async def test_overflow_stats(self, postscaler, symmetric_saturation, frame_cnt, board_conn, setup_scaler):
        min = TEST_CONFIG['overflow_stats'].get('min', -16)
        max = TEST_CONFIG['overflow_stats'].get('max', 15)
        self.board.set_gains(1, postscaler)
        source, _ = self._set_capture_scaler(func='ramp', min=min, max=max)
        ref_data = source * 2**10 * 2**postscaler // 2**31
        stats = await self.board.get_scaler_metrics_async(frame_cnt=frame_cnt)
        overflow_stats = sum([ch[0] for ch in stats])
        max_val = 7
        min_val = -7 if symmetric_saturation else -8
        overflow_cnt = np.sum((ref_data < min_val) | (ref_data > max_val))
        assert(overflow_stats == overflow_cnt * frame_cnt)

    @pytest.mark.scaler
    @pytest.mark.parametrize("rounding_mode, symmetric_saturation, num_frames", product(range(3), (False, True), (1, 10, 100)))
    def test_statistical_properties(self, rounding_mode, symmetric_saturation, num_frames, board_conn, setup_scaler):
        logger = self.get_logger() 
        self.board.set_data_source('noise')
        self.board.start_data_capture(source='scaler', period=1)
        self.board.set_scaler_rounding_mode(rounding_mode)
        self.board.set_symmetric_saturation(symmetric_saturation)
        receiver = self.board.get_data_receiver()
        POSTSCALER_MIN  = 12
        POSTSCALER_MAX  = 25
        avgs = np.zeros(POSTSCALER_MAX  - POSTSCALER_MIN)
        std_dev = np.zeros(POSTSCALER_MAX - POSTSCALER_MIN)
        n = 2048 * 16 * num_frames
        for postscaler in range(POSTSCALER_MIN, POSTSCALER_MAX): #for all possible postscalers
            self.board.set_gains(1, postscaler)
            K = 0
            sum = 0
            sum_sq = 0
            for i in range(num_frames):
                _, data, _ = receiver.read_raw_frames()
                data //= 16
                if i == 0:
                    K = data[0][0]
                avgs[postscaler-POSTSCALER_MIN] += np.sum(data)
                sum += np.sum(data - K)
                sum_sq += np.sum((data - K) ** 2)
            std_dev[postscaler - POSTSCALER_MIN] = (sum_sq - (sum**2 / n)) / (n - 1)
        avgs /= n
        #logger.debug(f"Standard deviations: {[s for s in std_dev]}")
        plt.clf()
        plt.plot(np.arange(POSTSCALER_MIN, POSTSCALER_MAX), avgs, label='x̄', marker='o')
        #plt.plot(std_dev, label='s')
        #plt.legend()
        plt.xlabel('Postscaler')
        plt.ylabel('Average')
        plt.ylim(-1, 1)
        plt.tight_layout()
        plt.savefig(PLOT_DIR / 'stats' / f'average[rounding_mode={rounding_mode}, symmetric_saturation={symmetric_saturation}, frames={num_frames}]')
    '''def plot_all_values(self, board_conn, setup_scaler):
        #create a colourmap of data from scaler with all values from scaler and all values from -128 to 127 as input
        for i in range(16):
            self.board.set_gains(1, postscaler=i, channels=[i])
        _, data0 = self._set_capture_scaler(func='ramp', min=-128, max=128)
        for i in range(16):
            self.board.set_gains(1, postscaler=16+i, channels=[i])
        _, data1 = self._set_capture_scaler(func='ramp',  min=-128, max=128)
        #merge data0 and data1 into 1 2d array
        data = np.concatenate((data0, data1), axis=0)
        fig, ax = plt.subplots()
        ax.set_ylabel("Postscaler")
        ax.set_xlabel("Input value")
        plt.imshow(data, cmap='coolwarm', aspect='auto')
        
        plt.colorbar()
        plt.savefig("cmap.png")'''