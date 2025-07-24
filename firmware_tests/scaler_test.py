import logging
import numpy as np
from test_setup import delete_plots, board_conn, setup_scaler, check_fifo_overflow, TEST_CONFIG
from utils import compare_plot_data, gen_data, unsplit_imag, split_imag
import pytest
from random import randint
from time import sleep
#from wtl.pytest_xreport import xr, TestMenu
#from wtl.pytest_xreport.xreport import XReport

#v = TestMenu(TEST_CONFIG).run()
#locals().update(v)

def get_test_param(test_name, param_name, default):
    '''
    Get a parameter for a certain test, permitting both the test and the parameter to be omitted
    '''
    params = TEST_CONFIG.get(test_name, {})
    return params.get(param_name, default)

platforms = {
    'ICE-4bit-c':
        {'INPUT_WIDTH': 8, 'CAPTURE_WIDTH': 4, 'FFT_WIDTH': 18, 'SCALER_WIDTH': 35, 'READOUT_SHIFT': 4},
    'ICE-4bit-r':
        {'INPUT_WIDTH': 8, 'CAPTURE_WIDTH': 4, 'FFT_WIDTH': 18, 'SCALER_WIDTH': 34, 'READOUT_SHIFT': 4},
    'ICE-8bit-c':
        {'INPUT_WIDTH': 8, 'CAPTURE_WIDTH': 8, 'FFT_WIDTH': 18, 'SCALER_WIDTH': 35, 'READOUT_SHIFT': 0},
    'ICE-8bit-r':
        {'INPUT_WIDTH': 8, 'CAPTURE_WIDTH': 8, 'FFT_WIDTH': 18, 'SCALER_WIDTH': 34, 'READOUT_SHIFT': 0},
    'CRS':
        {'INPUT_WIDTH': 14, 'CAPTURE_WIDTH': 16, 'FFT_WIDTH': 18, 'SCALER_WIDTH': 35, 'READOUT_SHIFT': 0},
    'CHORD':
        {'INPUT_WIDTH': 14, 'CAPTURE_WIDTH': 16, 'FFT_WIDTH': 32, 'SCALER_WIDTH': 48, 'READOUT_SHIFT': 0}
}
class TestScaler:

    board = None
    #various bit widths
    INPUT_WIDTH = None
    MIN_INPUT, MAX_INPUT = None, None
    CAPTURE_WIDTH = None
    MIN_OUTPUT, MAX_OUTPUT = None, None
    FFT_WIDTH = None
    IMPLICIT_SHIFT = None
    READOUT_SHIFT = None
    SCALER_SHIFT = None
    IDENTITY_POSTSCALER = None
    MAPPING_POSTSCALER = None
    POSTSCALER_MIN, POSTSCALER_MAX = None, None
    
    ROUNDING_MODES = ['truncation', 'normal', 'convergent']

    @classmethod
    def get_logger(cls):
        logger = logging.getLogger(cls.__class__.__name__)
        logger.setLevel(TEST_CONFIG['logleveltest'])
        return logger
    
    @classmethod
    def get_widths(cls):
        platform = TEST_CONFIG['platform']
        if platform not in platforms.keys():
            logger = cls.get_logger()
            logger.error(f'{platform} not recognised as a possible platform')
        platform = TEST_CONFIG['platform']
        widths = platforms[platform]
        cls.INPUT_WIDTH = widths['INPUT_WIDTH']
        cls.MIN_INPUT, cls.MAX_INPUT = -2**(cls.INPUT_WIDTH-1), 2**(cls.INPUT_WIDTH-1)-1
        cls.CAPTURE_WIDTH = widths['CAPTURE_WIDTH']
        cls.FFT_WIDTH = widths['FFT_WIDTH']
        cls.MIN_OUTPUT, cls.MAX_OUTPUT = -2**(cls.CAPTURE_WIDTH-1), 2**(cls.CAPTURE_WIDTH-1)-1
        cls.IMPLICIT_SHIFT = cls.FFT_WIDTH - cls.INPUT_WIDTH
        cls.READOUT_SHIFT = widths['READOUT_SHIFT']
        cls.SCALER_SHIFT = widths['SCALER_WIDTH'] - cls.CAPTURE_WIDTH 
        cls.IDENTITY_POSTSCALER = cls.SCALER_SHIFT - cls.IMPLICIT_SHIFT
        cls.MAPPING_POSTSCALER = cls.IDENTITY_POSTSCALER - (cls.INPUT_WIDTH - widths['CAPTURE_WIDTH']) # postscaler to map all possible inputs into range of output
        cls.POSTSCALER_MIN = cls.SCALER_SHIFT - cls.INPUT_WIDTH - cls.IMPLICIT_SHIFT + 1
        cls.POSTSCALER_MAX = widths['SCALER_WIDTH'] - cls.IMPLICIT_SHIFT

    def pytest_generate_tests(self, metafunc):
        self.get_widths()
        default_min = TEST_CONFIG.get('global_postscaler_min', self.POSTSCALER_MIN)
        default_max = TEST_CONFIG.get('global_postscaler_max', self.POSTSCALER_MAX)
        if 'postscaler' in metafunc.fixturenames:
            name = metafunc.function.__name__[5:]
            metafunc.parametrize('postscaler', range(get_test_param(name, 'postscaler_min', default_min), get_test_param(name, 'postscaler_max', default_max)))
        
    def _set_capture_scaler(self, func, read=True, get_flags=False, **func_kwargs):
        '''
        Sets the function generator to output a specific set of values and then captures data from the scaler.
        '''
        source = gen_data(func, **func_kwargs)
        for ch in range(len(self.board.chan)):
            self.board.chan[ch].PROBER.PROBER_USER_FLAGS = True
        self.board.set_data_source(source='arb', data=source)
        self.board.start_data_capture(period=1, source='scaler')
        if not read:
            return source, source
        receiver = self.board.get_data_receiver()
        _, data, _ = receiver.read_raw_frames()
        if get_flags:
            return source, data & (2**self.READOUT_SHIFT-1)
        return source, data//(2 ** self.READOUT_SHIFT)
    
    @compare_plot_data
    @pytest.mark.scaler
    def test_all_zeroes(self, board_conn, setup_scaler):
        '''
        Set all gains to 0 and tests if output is uniformly 0.
        The input ranges from ramp_min to ramp_max.
        '''
        self.board.set_gains(0)
        min = get_test_param('all_zeroes', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('all_zeroes', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = source * 0
        return [data, ref_data],
    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('symmetric_saturation', (False, True))
    def test_all_ones(self, postscaler, symmetric_saturation, board_conn, setup_scaler):
        '''
        Sets all gains to 1 and tests if the output is merely a shifted and truncated copy of the input.

        
        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        '''
        self.board.set_scaler_rounding_mode(0)
        self.board.set_gains(1, postscaler=postscaler)
        self.board.set_symmetric_saturation(symmetric_saturation)
        min = get_test_param('all_ones', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('all_ones', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT, self.MIN_OUTPUT + symmetric_saturation, self.MAX_OUTPUT)
        return [data, ref_data], f'All ones (postscaler={postscaler}, symmetric_saturation={symmetric_saturation})'

    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('period', range(TEST_CONFIG['alternating_gain'].get('min_period', 2), TEST_CONFIG['alternating_gain'].get('max_period', 3), TEST_CONFIG['alternating_gain'].get('step', 1)))
    def test_alternating_gain(self, period, board_conn, setup_scaler):
        '''
        Tests that the gains are being applied to the correct bin by setting the gains uniformly to 0, save for each periodth gain, which is set to 1. 
        
        The period ranges from period_min to period_max in bounds of step.
        The input ranges from ramp_min to ramp_max. Notice that this differs from previous ramps in that instead of covering the entire range once per frame, it does so as many times as possible per frame.
        '''
        #checks that per-bin gains work and also the alignment of frequency bins in input to output
        gains = np.tile([*np.repeat(0, period - 1), 1], self.FG_NS//(2 * period))
        gains = np.append(gains, (np.repeat(0, self.FG_NS//2 - gains.size)))
        self.board.set_gains(gains, self.MAPPING_POSTSCALER)
        min = get_test_param('alternating_gain', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('alternating_gain', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('periodic_ramp', min=min, max=max)
        ref_data = np.clip(source * np.repeat(gains, 2) * 2**self.IMPLICIT_SHIFT * 2**self.MAPPING_POSTSCALER // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data], f'Alternating gain (period={period})'

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('gain', TEST_CONFIG['constant_gain'].get('gains', []))
    @pytest.mark.parametrize('symmetric_saturation', (False, True)) 
    @pytest.mark.parametrize('force_float_gains', (False, True))
    def test_constant_gain(self, postscaler, gain, symmetric_saturation, force_float_gains, board_conn, setup_scaler):
        '''
        Sets linear gains to a consant values and tests if output corresponds to scaled, shifted and truncated copy of the input.
        
        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        '''
        if force_float_gains:
            if any(chan.SCALER.USE_COMPLEX_GAINS for chan in self.board.chan):
                pytest.skip("Platform does not support floating point gains")
            self.board.set_gains(gain * 2**postscaler)
            assert(all(ch.SCALER.USE_FLOAT_GAINS == True for ch in self.board.chan))
        else:
            self.board.set_gains(gain, postscaler=postscaler)
            assert(all(ch.SCALER.USE_FLOAT_GAINS == False for ch in self.board.chan))
        self.board.set_symmetric_saturation(symmetric_saturation)
        min = get_test_param('constant_gain', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('constant_gain', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(gain * source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT, self.MIN_OUTPUT + symmetric_saturation, self.MAX_OUTPUT)
        return [data, ref_data], f'Constant gain (postscaler={postscaler}, gain={gain}, symmetric saturation={symmetric_saturation}, force_float_gains={force_float_gains})'

    @compare_plot_data
    @pytest.mark.scaler
    def test_ramp_gains(self, board_conn, setup_scaler):
        gains = gen_data('periodic_ramp', min=0, max=8, samples=512)
        gains = np.concatenate((gains, gains[::-1]))
        self.board.set_gains(gains, self.MAPPING_POSTSCALER)
        min = get_test_param('ramp_gains', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('ramp_gains', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data  = np.clip(np.repeat(gains, 2) * source * 2**self.IMPLICIT_SHIFT * 2**self.MAPPING_POSTSCALER // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data],

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.complex
    def test_alternating_complex_gains(self, board_conn, setup_scaler):
        if any(not chan.SCALER.USE_COMPLEX_GAINS for chan in self.board.chan):
            pytest.skip("Platform does not support complex gains")
        #alternate between 1+0j and 0+1j
        gains = np.tile((1+0j, 0+1j), 1024//2)
        self.board.set_gains(gains, self.MAPPING_POSTSCALER)
        min = get_test_param('alternating_complex_gains', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('atlernating_complex_gains', 'ramp_max', self.MAX_INPUT)
        split_source, data = self._set_capture_scaler('ramp', min=min, max=max)
        source = unsplit_imag(split_source)
        ref_data = np.clip(split_imag(gains * source) * 2**self.IMPLICIT_SHIFT * 2**self.MAPPING_POSTSCALER // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data], 'alternating_complex_gains', {'split_complex': True}#, 'data_range':(600, 700)}
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.complex
    def test_periodic_complex_gains(self, board_conn, setup_scaler):
        if any(not chan.SCALER.USE_COMPLEX_GAINS for chan in self.board.chan):
            pytest.skip("Platform does not support complex gains")
        split_gains = gen_data('complex_ramp', min=0, max=32, samples=2048)
        #collapse 2048 real numbers into 1024 complex ones
        gains = unsplit_imag(split_gains)
        self.board.set_gains(gains, self.MAPPING_POSTSCALER)
        min = get_test_param('periodic_complex_gains', 'ramp_min', self.MIN_OUTPUT)
        max = get_test_param('periodic_complex_gains', 'ramp_max', self.MAX_OUTPUT)
        split_source, data = self._set_capture_scaler('ramp', min=min, max=max)
        source = unsplit_imag(split_source)
        ref_data = np.clip(split_imag(gains * source) * 2**self.IMPLICIT_SHIFT * 2**self.MAPPING_POSTSCALER // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        logger = self.get_logger()
        logger.debug(gains)
        return [data, ref_data], 'periodic_complex_gains', {'split_complex': True}

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.floating
    def test_uniform_common_log_gain(self, board_conn, setup_scaler):
        if any(chan.SCALER.USE_COMPLEX_GAINS for chan in self.board.chan):
            pytest.skip("Platform does not support floating point gains")
        self.board.set_gains(np.ones(1024) * 2**self.IDENTITY_POSTSCALER) #since postscaler=None, should automatically detect common factor
        logger = self.get_logger()
        for ch in range(len(self.board.chan)):
            if not self.board.chan[ch].SCALER.USE_FLOAT_GAINS:
                logger.error(f'Floating point gains not enabled in channel {ch}')
                assert(False)
            if not self.board.chan[ch].SCALER.SHIFT_LEFT == self.IDENTITY_POSTSCALER - 10:
                logger.error(f'Common log gain incorrectly set to {self.board.chan[ch].SCALER.SHIFT_LEFT} in channel {ch}')
                assert(False)
        min = get_test_param('uniform_common_log_gain', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('uniform_common_log_gain', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        return [data, np.clip(source, self.MIN_OUTPUT, self.MAX_OUTPUT)],

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.floating
    def test_common_log_gain(self, board_conn, setup_scaler):
        common_log_gain = TEST_CONFIG.get('common_log_gain', 10)
        if any(chan.SCALER.USE_COMPLEX_GAINS for chan in self.board.chan):
            pytest.skip("Platform does not support floating point gains")
        gains = np.random.randint(0, 2**11, 1024) * 2**np.random.randint(0, 2**5 - common_log_gain, 1024) #11 bits linear, 5 bits log
        gains = gains.astype(np.float64)
        gains *= 2**common_log_gain
        gains[0] = 1 #ensure there is no common log gain by chance
        self.board.set_gains(gains)
        logger = self.get_logger()
        for ch in range(len(self.board.chan)):
            if not self.board.chan[ch].SCALER.USE_FLOAT_GAINS:
                logger.error(f'Floating point gains not enabled in channel {ch}')
                assert(False)
            if not self.board.chan[ch].SCALER.SHIFT_LEFT == common_log_gain - 10:
                logger.error(f'Common log gain incorrectly set to {self.board.chan[ch].SCALER.SHIFT_LEFT} in channel {ch}')
                assert(False)
        min = get_test_param('uniform_common_log_gain', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('uniform_common_log_gain', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        return [data, np.clip(np.repeat(gains, 2) * source // 2**self.IDENTITY_POSTSCALER, self.MIN_OUTPUT, self.MAX_OUTPUT)],
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.floating
    def test_ramp_float_gains(self, board_conn, setup_scaler):
        if any(chan.SCALER.USE_COMPLEX_GAINS for chan in self.board.chan):
            pytest.skip("Platform does not support floating point gains")
        log_gains = gen_data('ramp', min=self.IDENTITY_POSTSCALER-11, max=self.IDENTITY_POSTSCALER+4, samples=1024)
        lin_gains = gen_data('periodic_ramp', min=0, max=2**6-1, samples=1024) * 2**4
        gains = lin_gains * 2**log_gains
        self.board.set_gains(gains)
        source, data = self._set_capture_scaler('a', a=1)
        ref_data = np.clip((source * np.repeat(gains, 2)) * 2**self.IMPLICIT_SHIFT // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data],

    @compare_plot_data
    @pytest.mark.scaler
    #TODO: fix this for CRS
    @pytest.mark.parametrize('val', TEST_CONFIG['rounding'].get('test_values', [1]))
    @pytest.mark.parametrize('num_fractional_bits', range(1, 8))
    @pytest.mark.parametrize('rounding_mode', (1, 2))
    def test_rounding(self, val, num_fractional_bits, rounding_mode, board_conn, setup_scaler):
        '''
        Tests the 2 non-truncation rounding modes of the scaler by ensuring the input number is rounded up or down correctly according to the value of its fractional bits.

        test_values: list of values to be tested
        num_fractional_bits: number of fractional bits
        '''
        max_val = 2**(self.INPUT_WIDTH - num_fractional_bits - 1) - 1
        min_val = -max_val - 1
        val = np.clip(val, min_val, max_val)
        self.board.set_gains((1, self.IDENTITY_POSTSCALER-num_fractional_bits))
        self.board.set_scaler_rounding_mode(rounding_mode)
        source, data = self._set_capture_scaler('ramp', min=(val * 2**num_fractional_bits), max=((val + 1) * 2**num_fractional_bits - 1))
        bottom = abs(source % (2**num_fractional_bits))
        if rounding_mode == 1:
            round_up = bottom >= 2**(num_fractional_bits - 1)
        elif rounding_mode == 2:
            round_up = (bottom > 2**(num_fractional_bits - 1)) | ((bottom == 2**(num_fractional_bits - 1)) & (val % 2 == 1))
        ref_data = np.clip(val + round_up, self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data], f'Rounding (value={val}, # of fractional bits={num_fractional_bits}, rounding mode={self.ROUNDING_MODES[rounding_mode]}]'
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('rounding_mode', (1, 2))
    @pytest.mark.parametrize('symmetric_saturation', (False, True))
    @pytest.mark.parametrize('num_fractional_bits', range(1, 8))
    @pytest.mark.parametrize('force_float_gains', (False, True))
    def test_post_rounding_saturation(self, rounding_mode, symmetric_saturation, num_fractional_bits, force_float_gains, board_conn, setup_scaler):
        '''
        Tests that if the value saturates post-rounding, it is corrected
        '''
        #ensure we can saturate with this number of fractional bits
        if self.INPUT_WIDTH - num_fractional_bits <= self.CAPTURE_WIDTH:
            pytest.skip(f"input is insufficently wide to allow saturation to occur while leaving {num_fractional_bits} fractional bits")
        self.board.set_scaler_rounding_mode(rounding_mode)
        self.board.set_symmetric_saturation(symmetric_saturation)
        #set postscaler #minimum value to get saturations even with no rounding
        if force_float_gains:
            if any(chan.SCALER.USE_COMPLEX_GAINS for chan in self.board.chan):
                pytest.skip("Platform does not support floating point gains")
            self.board.set_gains(2**(self.IDENTITY_POSTSCALER-num_fractional_bits))
            assert(all(ch.SCALER.USE_FLOAT_GAINS == True for ch in self.board.chan))
        else:
            self.board.set_gains(1, postscaler=self.IDENTITY_POSTSCALER-num_fractional_bits)
            assert(all(ch.SCALER.USE_FLOAT_GAINS == False for ch in self.board.chan))
        min = get_test_param('post_rounding_saturation', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('post_rounding_saturation', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = source * 2**self.IMPLICIT_SHIFT * 2**(self.IDENTITY_POSTSCALER-num_fractional_bits)  // 2**self.SCALER_SHIFT
        bottom = abs(source % (2**num_fractional_bits))
        if rounding_mode == 1:
            round_up = bottom >= 2**(num_fractional_bits - 1)
        elif rounding_mode == 2:
            round_up = (bottom > 2**(num_fractional_bits - 1)) | ((bottom == 2**(num_fractional_bits - 1)) & (ref_data % 2 == 1))
        else:
            round_up = np.zeros(2048)
        ref_data += round_up
        ref_data = np.clip(ref_data, self.MIN_OUTPUT + symmetric_saturation, self.MAX_OUTPUT)
        return [data, ref_data], f'Post-rounding Saturation (# of fractional bits={num_fractional_bits}, symmetric saturation={symmetric_saturation}, rounding_mode={self.ROUNDING_MODES[rounding_mode]})'
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('symmetric_saturation', (False, True))
    def test_zero_on_sat(self, symmetric_saturation, board_conn, setup_scaler):
        '''
        Tests the zero on saturation functionality by ensuring that both the real and imaginary components are zeroed when either exceeds the bounds.
        
        
        The input ranges from ramp_min to ramp_max. Note that unlike in earlier tests, this is a complex ramp, so the complex component must cover the full range before the real part is incremented by one)
        '''
        
        min = get_test_param('zero_on_sat', 'ramp_min', self.MIN_OUTPUT - 1)
        max = get_test_param('zero_on_sat', 'ramp_max', self.MAX_OUTPUT + 1)
        self.board.set_gains(1, self.IDENTITY_POSTSCALER)
        self.board.set_zero_on_sat(True)
        self.board.set_symmetric_saturation(symmetric_saturation)
        source, data = self._set_capture_scaler(func='complex_ramp', min=min, max=max) 
        self.board.set_zero_on_sat(False)
        self.board.set_symmetric_saturation(False)
        mask = (source < (self.MIN_OUTPUT + symmetric_saturation)) | (source > self.MAX_OUTPUT)
        mask = np.repeat(mask[::2] | mask[1::2], 2) #spill from Re or Im into pair
        ref_data = source
        ref_data[mask] = 0
        return [data, ref_data], f'Zero on saturation (symmetric saturation={bool(symmetric_saturation)})', {'split_complex':True}

    
    @compare_plot_data
    @pytest.mark.scaler
    def test_offset_encoding(self, postscaler, board_conn, setup_scaler):
        '''
        Tests that the normal output of the scaler is correctly mapped into a binary offset encoding.

        The input ranges from ramp_min to ramp_max.
        '''
        
        min = get_test_param('offset_encoding', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('offset_encoding', 'ramp_max', self.MAX_INPUT)
        self.board.set_gains(1, postscaler)
        self.board.set_offset_binary_encoding(True)
        source, data = self._set_capture_scaler(func='ramp', min=min, max=max)
        ref_data = np.clip(source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        sign = (ref_data >= 0) * 2 - 1
        ref_data -= sign * (self.MAX_OUTPUT + 1)
        return [data, ref_data], f'Offset encoding (postscaler={postscaler})'

       
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('mode', (1, 2, 3))
    @pytest.mark.parametrize('symmetric_saturation', (False, True))
    def test_overflow_detection(self, postscaler, mode, symmetric_saturation, board_conn, setup_scaler):
        '''
        Ensures that the alternate output modes of the scaler work correctly and output the correct pattern (1+0j or 0+1j) on an overflow
        '''
        for ch in self.board.chan:
            ch.SCALER.DATA_TYPE = mode
            ch.SCALER.BYPASS = 1
            ch.SCALER.CAP_DATA_TYPE = 0
        self.board.set_gains(1, postscaler)
        self.board.set_symmetric_saturation(symmetric_saturation)
        min = get_test_param('overflow_detection', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('overflow_detection', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        if self.CAPTURE_WIDTH > 4: #even in 8bit mode, the 1 is placed in the 4th bit, so need to correct for that
            data //= 16
        #only checks re saturation
        if mode == 1:
            out = source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT
            ref_data = (out < self.MIN_OUTPUT + symmetric_saturation) | (out > self.MAX_OUTPUT)
            ref_data[::2] = ref_data[1::2] #spread from imag to re
            ref_data[1::2] = 0  #zero out imag
        else:
            comp = (source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT)[mode-2::2] #either real or im depending on mode
            underflow = comp < self.MIN_OUTPUT + symmetric_saturation
            overflow = comp > self.MAX_OUTPUT
            ref_data = np.zeros(2048)
            ref_data[::2] = overflow
            ref_data[1::2] = underflow
        return [data, ref_data], f'Overflow detection (postscaler={postscaler}, mode={mode}, symmetric_saturation={symmetric_saturation})', {'split_complex': True}
    
    @compare_plot_data
    @pytest.mark.scaler
    def test_bypass(self, board_conn, setup_scaler):
        for ch in self.board.chan:
            ch.SCALER.CAP_DATA_TYPE = 1
        min = get_test_param('bypass', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('bypass', 'ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('periodic_ramp', min=min, max=max)
        return [data, source * 2**self.IMPLICIT_SHIFT // 2**(self.FFT_WIDTH - self.CAPTURE_WIDTH)],
    
    
    @pytest.mark.scaler
    @pytest.mark.asyncio
    @pytest.mark.parametrize("frame_cnt", (1, 100, 30000))
    #@pytest.mark.parametrize('postscaler, symmetric_saturation, frame_cnt', product(range(TEST_CONFIG['overflow_stats'].get('postscaler_min', 0), TEST_CONFIG['overflow_stats'].get('postscaler_max', 31)), (False, True), TEST_CONFIG['overflow_stats'].get('frame_cnt', 1)))
    async def test_scaler_overflow_stats(self, frame_cnt, board_conn, setup_scaler):
        '''
        Tests the collection of scaler overflow statistics by ensuring that the number of detected overflows is correct.


        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        frame_cnt: number of frames to integrate the statistics over
        '''
        self.board.set_gains(1, self.IDENTITY_POSTSCALER)
        #source, _ = self._set_capture_scaler(read=False, func='ramp', min=min, max=max)
        data = np.zeros(2048)
        data[0] = 127 
        data[-1] = -128 #2 overflows per frame 
        _, _ = self._set_capture_scaler(read=False, func='arb', data=data)
        for ch in range(len(self.board.chan)):
            overflow_stats = (await self.board.get_channel_metrics_async(ch=ch, frame_cnt=frame_cnt))[0]
            assert(overflow_stats == 2*frame_cnt)

    @pytest.mark.scaler
    @pytest.mark.asyncio
    @pytest.mark.parametrize("frame_cnt", (1, 100, 30000))
    async def test_adc_overflow_stats(self, frame_cnt, board_conn, setup_scaler):
        for ch in self.board.chan:
            ch.FUNCGEN.BYTE_A = 1 #set adc overflow flag to true
        _, _ = self._set_capture_scaler(read=False, func='a', a=0) #we don't care about the data we send
        for ch in range(len(self.board.chan)):
            overflow_stats = (await self.board.get_channel_metrics_async(ch=ch, frame_cnt=frame_cnt))[1]
            assert(overflow_stats == frame_cnt)


    @pytest.mark.scaler
    def test_delay_counter(self, board_conn, setup_scaler):
        for ch in self.board.chan:
            ch.SCALER.RESET = 1
        sleep(0.1)
        for ch in self.board.chan:
            ch.SCALER.RESET = 0
        _, _ = self._set_capture_scaler('a', a=1)
        delay_ctrs = [ch.SCALER.DELAY_CTR for ch in self.board.chan]
        logger = self.get_logger()
        logger.debug(delay_ctrs)
        assert(len(set(delay_ctrs)) == 1) #ensure all delay counters are the same

    @compare_plot_data
    @pytest.mark.scaler
    #TODO: get frames closer to switch to ensure precision
    def test_gain_bank_switching(self, board_conn, setup_scaler, interval=int(10e5)): #10 000 frames
        '''
        Test that the scaler can switch between two independant gain banks in semi-real time by ensuring that the data frames on either side of the switch reflect the change
        '''
        self.board.set_gains(2, self.MAPPING_POSTSCALER, bank=1)
        self.board.set_gains(1, self.MAPPING_POSTSCALER, bank=0, when='now')
        source = gen_data(func='ramp', min=self.MIN_INPUT, max=self.MAX_INPUT)
        self.board.set_data_source(source='arb', data=source)
        self.board.switch_gains(bank=1, when=5*interval)
        receiver = self.board.get_data_receiver()
        ref_before_frame = np.clip(source * 2**self.IMPLICIT_SHIFT * 2**self.MAPPING_POSTSCALER // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        ref_after_frame = np.clip(ref_before_frame * 2, self.MIN_OUTPUT, self.MAX_OUTPUT)
        assert(all(ch.SCALER.CURRENT_GAIN_BANK == 0 for ch in self.board.chan))
        self.board.start_data_capture(burst_period_in_frames=interval, source='scaler', frames_per_burst=2)
        ts, data, _ = receiver.read_raw_frames(0.5, 10) #5 pairs of 2 frames, with 0.5 second between each pair
        for i in range(1, len(data)):
            if (data[i] != data[i-1]).any():
                before_frame = data[i-1]
                after_frame = data[i]
                before_ts = ts[i-1]
                after_ts = ts[i]
                break
        else:
            logger = self.get_logger()
            logger.error("No gain bank switch occured")
            assert(False)
        assert((before_frame == ref_before_frame).all() and (after_frame == ref_after_frame).all())
        assert(before_ts == interval*5 and after_ts == interval*5+1)
        return [after_frame, ref_after_frame],

    def sat_percent(self, postscaler: int, symmetric_saturation: bool):
        '''
        Returns the percentage of inputs that are expected to saturate the scaler when the log gain is set to postscaler, assuming a uniform distribution over all possible 8 bit inputs.
        '''
        count = 0
        for v in range(-128, 128):
            out = v * 2.0**(postscaler + self.IMPLICIT_SHIFT - self.SCALER_SHIFT)
            count += (out >= self.MAX_OUTPUT) or (out <= self.MIN_OUTPUT + symmetric_saturation)
        return count / 256


    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("bank", (0, 1))
    def test_flags(self, postscaler, bank, board_conn, setup_scaler):
        self.board.set_gains(1, postscaler=postscaler, bank=bank, when='now')
        min = get_test_param('all_ones', 'ramp_min', self.MIN_INPUT)
        max = get_test_param('all_ones', 'ramp_max', self.MAX_INPUT)
        source, flags = self._set_capture_scaler('ramp', min=min, max=max, get_flags=True)
        ref_data = source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT
        overflow = (ref_data > self.MAX_OUTPUT) | (ref_data < self.MIN_OUTPUT)
        bank_flag = np.zeros(2048)
        bank_flag[-4:] = bank * 2
        return [flags, overflow*12 + bank_flag], f'Flags (postscaler={postscaler}, bank={bank})'

    @compare_plot_data(approximate=True)
    @pytest.mark.scaler
    @pytest.mark.statistical
    @pytest.mark.parametrize('rounding_mode', (0, 1, 2))
    @pytest.mark.parametrize('symmetric_saturation', (False, True))
    def test_averages(self, rounding_mode, symmetric_saturation, board_conn, setup_scaler, num_frames=get_test_param('averages', 'num_frames', 10)):
        '''
        Returns the average scaler output for a range of postscalers given a uniform, random distribution of input values (white noise). Performs the averaging for all possible rounding modes and with symmetric saturation enabled and disabled.
        '''
        logger = self.get_logger()
        for ch in range(len(self.board.chan)):
            self.board.chan[ch].FUNCGEN.BYTE_A = randint(0, 255)
            self.board.chan[ch].FUNCGEN.BYTE_B = randint(0, 255)
        self.board.set_data_source('noise')
        self.board.start_data_capture(source='scaler', period=1)
        self.board.set_scaler_rounding_mode(rounding_mode)
        self.board.set_symmetric_saturation(symmetric_saturation)
        receiver = self.board.get_data_receiver()
        avgs = np.zeros(self.POSTSCALER_MAX  - self.POSTSCALER_MIN)
        n = 2048 * 16 * num_frames
        for postscaler in range(self.POSTSCALER_MIN, self.POSTSCALER_MAX): #for all possible postscalers
            self.board.set_gains(1, postscaler)
            for i in range(num_frames):
                _, data, _ = receiver.read_raw_frames()
                data //= 2 ** self.READOUT_SHIFT
                avgs[postscaler-self.POSTSCALER_MIN] += np.sum(data)
        avgs /= n
        logger.debug(f'Average: {[s for s in avgs]}')
        if rounding_mode == 0 and not symmetric_saturation:
            ref_data = -0.5 * np.ones(self.POSTSCALER_MAX - self.POSTSCALER_MIN)
        elif rounding_mode == 0 and symmetric_saturation:
            ref_data = -0.5 * (1 - np.vectorize(self.sat_percent)(np.arange(self.POSTSCALER_MIN, self.POSTSCALER_MAX), symmetric_saturation=symmetric_saturation))
        elif rounding_mode > 0 and not symmetric_saturation:
            ref_data = -0.5 * np.vectorize(self.sat_percent)(np.arange(self.POSTSCALER_MIN, self.POSTSCALER_MAX), symmetric_saturation=symmetric_saturation)
        elif rounding_mode > 0 and symmetric_saturation:
            ref_data = np.zeros(self.POSTSCALER_MAX - self.POSTSCALER_MIN)
        return [avgs, ref_data], f'Average (rounding mode={self.ROUNDING_MODES[rounding_mode]}, symmetric_saturation={symmetric_saturation}]', {'y_range': (-0.6, 0.1), 'xlabel': 'Postscaler', 'ylabel': 'Average'}
            
    def dont_test_noise(self, board_conn, setup_scaler, frames=10):
        for ch in self.board.chan:
            ch.SCALER.CAP_DATA_TYPE = 1
            ch.FUNCGEN.BYTE_A = randint(0, 255)
            ch.FUNCGEN.BYTE_B = randint(0, 255)
        self.board.set_data_source('noise')
        self.board.start_data_capture(source='scaler', period=1)
        receiver = self.board.get_data_receiver()
        counts = dict.fromkeys(range(self.MIN_OUTPUT, self.MAX_OUTPUT + 1), 0)
        for _ in range(frames):
            _, data, _ = receiver.read_raw_frames()
            data //= 2**(self.READOUT_SHIFT)
            for chan in data:
                for val in chan:
                    counts[val] += 1