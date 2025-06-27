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
from random import randint

NUM_CHANNELS = 16
FIG_WIDTH = 8
FIG_HEIGHT = 6


def compare_plot_data(test_unit=None, *, approximate=False):
    def _decorate(test_unit):
        @wraps(test_unit)
        def wrapper(*args, **kwargs):
            res = test_unit(*args, **kwargs)
            data = res[0][0]
            ref_data = res[0][1]
            title = test_unit.__name__[5:] if len(res) < 2 else res[1]
            folder = test_unit.__name__[5:] if len(res) >= 2 else None 
            plot_kwargs = {} if len(res) < 3 else res[2]
            if len(data.shape) > 1:
                for i in range(data.shape[0]):
                    if not np.equal(data[0], data[i]).all():
                        plot(datasets=[data[0], data[i]], labels=["First channel", f"{i}th channel"], title=f"Different channeliser outputs for {title}")
                    np.testing.assert_equal(data[0], data[i])
                actual_data = data[0]
            else:
                actual_data = data
            if TEST_CONFIG['always_plot'] or (TEST_CONFIG['plot_on_failure'] and not np.equal(data, ref_data).all()):
                plot(datasets=[actual_data, *res[0][1:]], labels=['Returned', 'Reference'], title=title, folder=folder, **plot_kwargs)
            if approximate:
                np.testing.assert_allclose(actual_data, ref_data, atol=0.1)
            else:
                np.testing.assert_equal(actual_data, ref_data)
        return wrapper
    if test_unit:
        return _decorate(test_unit)
    return _decorate

'''def get_func(name):
    if name not in TEST_CONFIG: return {'func': 'const', 'a': 0}
    elif 'func' not in TEST_CONFIG[name]: return {'func': 'const', 'a': 0}
    args = TEST_CONFIG[name]['func'].copy()
    func = args.pop('name', 'const')
    return {'func': func, **args}
'''

def sat_percent(postscaler: int, min: int):
    '''
    Returns the percentage of inputs that are expected to saturate the scaler when the log gain is set to postscaler, assuming a uniform distribution over all possible 8 bit inputs.
    '''
    count = 0
    for v in range(-128, 127):
        out = v * 2.0**(postscaler + 10 - 31)
        count += (out >= 7) or (out <= min)
    return count / 256
class TestFW:
    """
    Collection of tests for an ICE/CRS board firmware. Most tests utilize the board_conn fixture, that reads
    connection parameters specified in config.yaml and connects to the boards. Some tests also use the setup_funcgen
    or the setup_scaler fixture which allows controlling the function generator or the scaler, respectively, within tests. 
    The @compare_plot_data decorator is used to compare the data read from the board and reference data. For this to work, 
    test units must return data and ref_data numpy arrays.
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
        return [data, ref_data], f'funcgen_real_ramp', {'split_complex': True}

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
    
    def _set_capture_scaler(self, func, read=True, **func_kwargs):
        '''
        Sets the function generator to output a ecific set of values and then captures data from the scaler.
        '''
        source = gen_data(func, **func_kwargs)
        self.board.set_data_source(source='arb', data=source)
        self.board.start_data_capture(period=1, source='scaler')
        if not read:
            return source, source
        receiver = self.board.get_data_receiver()
        _, data, _ = receiver.read_raw_frames()
        return source, data//16
    
    @compare_plot_data
    @pytest.mark.scaler
    def test_scaler_all_zeroes(self, board_conn, setup_scaler):
        '''
        Set all gains to 0 and tests if output is uniformly 0.
        
        The input ranges from ramp_min to ramp_max.
        '''
        self.board.set_gains(0)
        min = TEST_CONFIG['all_zeroes'].get('ramp_min', -128)
        max = TEST_CONFIG['all_zeroes'].get('ramp_max', 127)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = source * 0
        return [data, ref_data],
    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("postscaler", range(TEST_CONFIG['all_ones'].get('postscaler_min', 0), TEST_CONFIG['all_ones'].get('postscaler_max', 31)))
    def test_scaler_all_ones(self, postscaler, board_conn, setup_scaler):
        '''
        Sets all gains to 1 and tests if the output is merely a shifted and truncated copy of the input.

        
        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        '''
        self.board.set_gains(1, postscaler=postscaler)
        min = TEST_CONFIG['all_ones'].get('ramp_min', -128)
        max = TEST_CONFIG['all_ones'].get('ramp_max', 127)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(source * 2**10 * 2**postscaler // 2**31, -8, 7)
        return [data, ref_data], f"all_ones[glog={postscaler}]"

    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("period", range(TEST_CONFIG['alternating_gain'].get('min_period', 2), TEST_CONFIG['alternating_gain'].get('max_period', 3), TEST_CONFIG['alternating_gain'].get('step', 1)))
    def test_alternating_gain(self, period, board_conn, setup_scaler):
        '''
        Tests that the gains are being applied to the correct bin by setting the gains uniformly to 0, save for each periodth gain, which is set to 1. 
        
        The period ranges from period_min to period_max in bounds of step.
        The input ranges from ramp_min to ramp_max. Notice that this differs from previous ramps in that instead of covering the entire range once per frame, it does so as many times as possible per frame.
        '''
        #checks that per-bin gains work and also the alignment of frequency bins in input to output
        gains = np.tile([*np.repeat(0, period - 1), 1], self.FG_NS//(2 * period))
        gains = np.append(gains, (np.repeat(0, self.FG_NS//2 - gains.size)))
        self.board.set_gains(gains, 21)
        min = TEST_CONFIG['alternating_gain'].get('ramp_min', -8)
        max = TEST_CONFIG['alternating_gain'].get('ramp_max', 7)
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
        Sets linear gains to a consant values and tests if output corresponds to scaled, shifted and truncated copy of the input.
        
        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        '''
        self.board.set_gains(gain, postscaler=postscaler)
        min = TEST_CONFIG['constant_gain'].get('ramp_min', -128)
        max = TEST_CONFIG['constant_gain'].get('ramp_max', 127)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(gain * source * 2**10 * 2**postscaler // 2**31, -8, 7)
        return [data, ref_data], f"constant_gain[glin={gain}, glog={postscaler}]"


    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("val, sig_bit, rounding_mode", product(TEST_CONFIG['rounding'].get('test_values', [1]), range(1, 8), (1, 2)))
    def test_rounding(self, val, sig_bit, rounding_mode, board_conn, setup_scaler):
        '''
        Tests the 2 non-truncation rounding modes of the scaler by ensuring the input number is rounded up or down correctly according to the value of its fractional bits.

        test_values: list of values to be tested
        sig_bit: number of fractional bits
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
        
        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        '''
        self.board.set_symmetric_saturation(True)
        self.board.set_gains(1, postscaler)
        min = TEST_CONFIG['constant_gain'].get('ramp_min', -128)
        max = TEST_CONFIG['constant_gain'].get('ramp_max', 127)
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
        Tests the zero on saturation functionality by ensuring that both the real and imaginary components are zeroed when either exceeds the bounds.
        
        
        The input ranges from ramp_min to ramp_max. Note that unlike in earlier tests, this is a complex ramp, so the complex component must cover the full range before the real part is incremented by one)
        '''
        min = TEST_CONFIG['zero_on_sat'].get('ramp_min', -9)
        max = TEST_CONFIG['zero_on_sat'].get('ramp_max', 9)
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
    #@pytest.mark.parametrize("postscaler, symmetric_saturation, frame_cnt", product(range(TEST_CONFIG['overflow_stats'].get('postscaler_min', 0), TEST_CONFIG['overflow_stats'].get('postscaler_max', 31)), (False, True), TEST_CONFIG['overflow_stats'].get('frame_cnt', 1)))
    async def test_overflow_stats(self, board_conn, setup_scaler, postscaler=21, symmetric_saturation=False, frame_cnt=1000):
        '''
        Tests the collection of scaler overflow statistics by ensuring that the number of detected overflows is correct.


        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        frame_cnt: number of frames to integrate the statistics over
        '''
        min = TEST_CONFIG['overflow_stats'].get('ramp_min', -16)
        max = TEST_CONFIG['overflow_stats'].get('ramp_max', 16)
        self.board.set_gains(1, postscaler)
        self.board.set_symmetric_saturation(symmetric_saturation)
        source, _ = self._set_capture_scaler(read=False, func='ramp', min=min, max=max)
        #ref_data = source * 2**10 * 2**postscaler // 2**31
        overflow_stats = (await self.board.get_channel_metrics_async(ch=0, frame_cnt=frame_cnt))[0]
        max_val = 7
        min_val = -7 if symmetric_saturation else -8
        #overflow_cnt = np.sum((ref_data < min_val) | (ref_data > max_val))
        assert(overflow_stats == 0)#overflow_cnt * frame_cnt)

    @compare_plot_data(approximate=True)
    @pytest.mark.scaler
    @pytest.mark.statistical
    @pytest.mark.parametrize("rounding_mode, symmetric_saturation, num_frames", product(range(3), (False, True), (10,)))
    def test_averages(self, rounding_mode, symmetric_saturation, num_frames, board_conn, setup_scaler):
        logger = self.get_logger()
        for ch in range(len(self.board.chan)):
            self.board.chan[ch].FUNCGEN.BYTE_A = randint(0, 255)
            self.board.chan[ch].FUNCGEN.BYTE_B = randint(0, 255)
            
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
            for i in range(num_frames):
                _, data, _ = receiver.read_raw_frames()
                data //= 16
                avgs[postscaler-POSTSCALER_MIN] += np.sum(data)
        avgs /= n
        logger.debug(f"Average: {[s for s in avgs]}")
        if rounding_mode == 0 and not symmetric_saturation:
            ref_data = -0.5 * np.ones(POSTSCALER_MAX - POSTSCALER_MIN)
        elif rounding_mode == 0 and symmetric_saturation:
            ref_data = -0.5 * (1 - np.vectorize(sat_percent)(np.arange(POSTSCALER_MIN, POSTSCALER_MAX), min=-7))
        elif rounding_mode > 0 and not symmetric_saturation:
            ref_data = -0.5 * np.vectorize(sat_percent)(np.arange(POSTSCALER_MIN, POSTSCALER_MAX), min=-8)
        elif rounding_mode > 0 and symmetric_saturation:
            ref_data = np.zeros(POSTSCALER_MAX - POSTSCALER_MIN)
        return [avgs, ref_data], f'average[rounding_mode={rounding_mode}, symmetric_saturation={symmetric_saturation}]', {'y_range': (-0.6, 0.1)}

    @pytest.mark.scaler
    @pytest.mark.statistical
    @pytest.mark.parametrize("symmetric_saturation", (False, True))
    def parity(self, symmetric_saturation, board_conn, setup_scaler):
        NUM_FRAMES = 100
        logger = self.get_logger()
        self.board.set_data_source('noise')
        self.board.start_data_capture(source='scaler', period=1)
        receiver = self.board.get_data_receiver()
        self.board.set_symmetric_saturation(symmetric_saturation)
        ratios = [[], []]
        POSTSCALER_MIN  = 12
        POSTSCALER_MAX  = 25
        for rm in (1, 2):
            self.board.set_scaler_rounding_mode(rm)
            for postscaler in range(POSTSCALER_MIN, POSTSCALER_MAX):
                self.board.set_gains(1, postscaler)
                even = 0
                odd = 0
                for i in range(NUM_FRAMES):
                    _, data, _ = receiver.read_raw_frames()
                    data //= 16
                    even += np.sum(data % 2 == 0)
                    odd += np.sum(data % 2 == 1)
                ratios[rm - 1].append(odd/even)
                logger.debug(f'Even: {even}, odd: {odd}')
        plt.clf()
        xs = np.arange(POSTSCALER_MIN, POSTSCALER_MAX)
        plt.plot(xs, ratios[0], 'o-r', label='normal')
        plt.plot(xs, ratios[1], 'o-b', label='convergent')
        plt.legend()
        plt.title("Odd:even ratio for different rounding modes and postscalers")
        plt.savefig(PLOT_DIR / f'parity[symmetric_saturation={symmetric_saturation}]')
            
    @compare_plot_data
    @pytest.mark.scaler
    def test_gain_bank_switching(self, board_conn, setup_scaler, interval=int(10e5)): #10 000 frames
        '''
        Test that the scaler can switch between two independant gain banks in semi-real time by ensuring that the data frames on either side of the switch reflect the change
        '''
        logger = self.get_logger()
        bank1 = np.ones(1024)
        self.board.set_gains(bank1 * 2, 21, bank=1)
        self.board.set_gains(bank1, 21, bank=0, when='now')
        source = gen_data(func='ramp', min=-8, max=8)
        self.board.set_data_source(source='arb', data=source)
        self.board.switch_gains(bank=1, when=5*interval)
        self.board.start_data_capture(burst_period_in_frames=interval, source='scaler')
        receiver = self.board.get_data_receiver()
        #how to capture multiple frames?
        frames = []
        for i in range(10):
            ts, data, _ = receiver.read_raw_frames()
            #logger.debug(str(ts) + ' ' + str(data[0][700]))
            frames.append(data//16)
        #find the frame  where switch occurs
        switch = 0
        for i in range(1, len(frames)):
            if (frames[i] != frames[i-1]).any():
                switch = i
                logger.debug(f"Bank switch occured between frames {i*interval} and {(i+1)*interval}")
                break
        assert(switch == 4)
        return [frames[switch], np.clip(source * 2, -8, 7)],


    
    
    
    
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
    



'''
TODO:
    1. Add automatic platform detection and propagate this to the various tests to adjust test
    2. Add new tests for new features - floating point gains, new output modes
    3. Redo pre-existing tests for various features to make use of new introspection capabilities offered by capture output
'''