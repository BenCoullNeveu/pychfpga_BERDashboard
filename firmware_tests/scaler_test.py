import logging
import numpy as np
from test_setup import delete_plots, board_conn, setup_scaler, get_widths, TEST_CONFIG
from utils import compare_plot_data, gen_data
import pytest
from itertools import product
from random import randint

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
    POSTSCALER_MIN, POSTSCALER_MAX = TEST_CONFIG.get('global_postscaler_min', 0), TEST_CONFIG.get('global_postscaler_max', 31)

    @classmethod
    def get_logger(cls):
        logger = logging.getLogger(cls.__class__.__name__)
        logger.setLevel(TEST_CONFIG['logleveltest'])
        return logger
    

    def _set_capture_scaler(self, func, read=True, **func_kwargs):
        '''
        Sets the function generator to output a specific set of values and then captures data from the scaler.
        '''
        source = gen_data(func, **func_kwargs)
        self.board.set_data_source(source='arb', data=source)
        self.board.start_data_capture(period=1, source='scaler')
        if not read:
            return source, source
        receiver = self.board.get_data_receiver()
        _, data, _ = receiver.read_raw_frames()
        return source, data//(2 ** self.READOUT_SHIFT)
    
    @compare_plot_data
    @pytest.mark.scaler
    def test_scaler_all_zeroes(self, board_conn, setup_scaler):
        '''
        Set all gains to 0 and tests if output is uniformly 0.
        The input ranges from ramp_min to ramp_max.
        '''
        self.board.set_gains(0)
        min = TEST_CONFIG['all_zeroes'].get('ramp_min', self.MIN_INPUT)
        max = TEST_CONFIG['all_zeroes'].get('ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = source * 0
        return [data, ref_data],
    

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("postscaler", range(TEST_CONFIG['all_ones'].get('postscaler_min', POSTSCALER_MIN), TEST_CONFIG['all_ones'].get('postscaler_max', POSTSCALER_MAX)))
    def test_scaler_all_ones(self, postscaler, board_conn, setup_scaler):
        '''
        Sets all gains to 1 and tests if the output is merely a shifted and truncated copy of the input.

        
        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        '''
        self.board.set_scaler_rounding_mode(0)
        self.board.set_gains(1, postscaler=postscaler)
        min = TEST_CONFIG['all_ones'].get('ramp_min', self.MIN_INPUT)
        max = TEST_CONFIG['all_ones'].get('ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
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
        self.board.set_gains(gains, self.IDENTITY_POSTSCALER)
        min = TEST_CONFIG['alternating_gain'].get('ramp_min', self.MIN_OUTPUT)
        max = TEST_CONFIG['alternating_gain'].get('ramp_max', self.MAX_OUTPUT)
        source, data = self._set_capture_scaler('periodic_ramp', min=min, max=max)
        ref_data = np.clip(source * np.repeat(gains, 2), self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data], f"alternating_gain[period={period}]", {'split_plots': True}

    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize(
        "postscaler,gain", product(
            range(TEST_CONFIG['constant_gain'].get('postscaler_min', POSTSCALER_MIN), TEST_CONFIG['constant_gain'].get('postscaler_max', POSTSCALER_MAX)), 
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
        min = TEST_CONFIG['constant_gain'].get('ramp_min', self.MIN_INPUT)
        max = TEST_CONFIG['constant_gain'].get('ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = np.clip(gain * source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data], f"constant_gain[glin={gain}, glog={postscaler}]"


    @compare_plot_data
    @pytest.mark.scaler
    #TODO: fix this for CRS
    @pytest.mark.parametrize("val, sig_bit, rounding_mode", product(TEST_CONFIG['rounding'].get('test_values', [1]), range(1, 8), (1, 2)))
    def test_rounding(self, val, sig_bit, rounding_mode, board_conn, setup_scaler):
        '''
        Tests the 2 non-truncation rounding modes of the scaler by ensuring the input number is rounded up or down correctly according to the value of its fractional bits.

        test_values: list of values to be tested
        sig_bit: number of fractional bits
        '''
        max_val = 2**(TEST_CONFIG.get('input_width', 8) - sig_bit - 1) - 1
        min_val = -max_val - 1
        val = np.clip(val, min_val, max_val)
        self.board.set_gains((1, self.IDENTITY_POSTSCALER-sig_bit))
        self.board.set_scaler_rounding_mode(rounding_mode)
        source, data = self._set_capture_scaler('ramp', min=(val * 2**sig_bit), max=((val + 1) * 2**sig_bit - 1))
        bottom = abs(source % (2**sig_bit))
        if rounding_mode == 1:
            round_up = bottom >= 2**(sig_bit - 1)
        elif rounding_mode == 2:
            round_up = (bottom > 2**(sig_bit - 1)) | ((bottom == 2**(sig_bit - 1)) & (val % 2 == 1))
        ref_data = np.clip(val + round_up, self.MIN_OUTPUT, self.MAX_OUTPUT)
        return [data, ref_data], f"rounding[val={val}, sig_bit={sig_bit}, rounding={'normal' if rounding_mode == 1 else 'convergent'}]"
 
      
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("postscaler", range(TEST_CONFIG['symmetric_saturation'].get('postscaler_min', POSTSCALER_MIN), TEST_CONFIG['symmetric_saturation'].get('postscaler_max', POSTSCALER_MAX)))
    def test_symmetric_saturation(self, postscaler, board_conn, setup_scaler):
        '''
        Similar to the all_ones test above, except with symmetric saturation enabled.
        
        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        '''
        self.board.set_symmetric_saturation(True)
        self.board.set_gains(1, postscaler)
        min = TEST_CONFIG['symmetric_saturation'].get('ramp_min', self.MIN_INPUT)
        max = TEST_CONFIG['symmetric_saturation'].get('ramp_max', self.MAX_INPUT)
        source, data  = self._set_capture_scaler(func='ramp', min=min, max=max)
        self.board.set_symmetric_saturation(False)
        ref_data = np.clip(source * 2**self.IMPLICIT_SHIFT * 2**postscaler // 2**self.SCALER_SHIFT, self.MIN_OUTPUT + 1, self.MAX_OUTPUT)
        return [data, ref_data], f"symmetric_saturation[glog={postscaler}]"
    

    #TODO: generalise this test
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize('rounding_mode, symmetric_saturation, upper, sig_bit', product((1, 2), (True, False), (True, False), range(1, 8)))
    def test_post_rounding_saturation(self, rounding_mode, symmetric_saturation, upper, sig_bit, board_conn, setup_scaler):
        '''
        Tests that if the value saturates post-rounding, it is corrected
        '''
        #only works if capture width is less than input_width
        if self.CAPTURE_WIDTH >= self.INPUT_WIDTH:
            return
        self.board.set_scaler_rounding_mode(rounding_mode)
        self.board.set_symmetric_saturation(symmetric_saturation)
        self.board.set_gains(1, self.IDENTITY_POSTSCALER-sig_bit) #minimum value to get saturations even with no rounding
        min = TEST_CONFIG['post_rounding_saturation'].get('ramp_min', self.MIN_INPUT)
        max = TEST_CONFIG['post_rounding_saturation'].get('ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('ramp', min=min, max=max)
        ref_data = source * 2**self.IMPLICIT_SHIFT * 2**(self.IDENTITY_POSTSCALER-sig_bit)  // 2**self.SCALER_SHIFT
        bottom = abs(source % (2**sig_bit))
        if rounding_mode == 1:
            round_up = bottom >= 2**(sig_bit - 1)
        elif rounding_mode == 2:
            round_up = (bottom > 2**(sig_bit - 1)) | ((bottom == 2**(sig_bit - 1)) & (ref_data % 2 == 1))
        else:
            round_up = np.zeros(2048)
        ref_data += round_up
        ref_data = np.clip(ref_data, self.MIN_OUTPUT + symmetric_saturation, self.MAX_OUTPUT)
        return [data, ref_data], f'Post-rounding Saturation [rounding_mode={rounding_mode}, symmetric_saturation={symmetric_saturation}, {"upper" if upper else "lower"}, sig_bit={sig_bit}]'
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("symmetric_saturation", (False, True))
    def test_zero_on_sat(self, symmetric_saturation, board_conn, setup_scaler):
        '''
        Tests the zero on saturation functionality by ensuring that both the real and imaginary components are zeroed when either exceeds the bounds.
        
        
        The input ranges from ramp_min to ramp_max. Note that unlike in earlier tests, this is a complex ramp, so the complex component must cover the full range before the real part is incremented by one)
        '''
        min = TEST_CONFIG['zero_on_sat'].get('ramp_min', self.MIN_OUTPUT - 1)
        max = TEST_CONFIG['zero_on_sat'].get('ramp_max', self.MAX_OUTPUT + 1)
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
        return [data, ref_data], f"zero_on_sat[symmetric_saturation={bool(symmetric_saturation)}]", {'split_complex':True}

    
    @compare_plot_data
    @pytest.mark.scaler
    def test_offset_encoding(self, board_conn, setup_scaler):
        '''
        Tests that the normal output of the scaler is correctly mapped into a binary offset encoding.

        The input ranges from ramp_min to ramp_max.
        '''
        min = TEST_CONFIG['offset_encoding'].get('ramp_min', self.MIN_OUTPUT - 1)
        max = TEST_CONFIG['offset_encoding'].get('ramp_max', self.MAX_OUTPUT + 1)
        self.board.set_gains(1, self.IDENTITY_POSTSCALER)
        self.board.set_offset_binary_encoding(True)
        source, data = self._set_capture_scaler(func='ramp', min=min, max=max)
        self.board.set_offset_binary_encoding(False)
        ref_data = np.clip(source * 2**self.IMPLICIT_SHIFT * 2**self.IDENTITY_POSTSCALER // 2**self.SCALER_SHIFT, self.MIN_OUTPUT, self.MAX_OUTPUT)
        ref_data[:2048//18 * 9] -= self.MIN_OUTPUT
        ref_data[2048//18 * 9:] += self.MIN_OUTPUT
        return [data, ref_data], 

       
    
    @compare_plot_data
    @pytest.mark.scaler
    @pytest.mark.parametrize("postscaler, mode, symmetric_saturation", product(range(TEST_CONFIG['overflow_detection'].get('postscaler_min', POSTSCALER_MIN), TEST_CONFIG['overflow_detection'].get('postscaler_max', POSTSCALER_MAX)), (1, 2, 3), (False, True)))
    def test_overflow_detection(self, postscaler, mode, symmetric_saturation, board_conn, setup_scaler):
        for ch in self.board.chan:
            ch.SCALER.DATA_TYPE = mode
            ch.SCALER.BYPASS = 1
            ch.SCALER.CAP_DATA_TYPE = 0
        self.board.set_gains(1, postscaler)
        self.board.set_symmetric_saturation(symmetric_saturation)
        min = TEST_CONFIG['overflow_detection'].get('ramp_min', self.MIN_INPUT)
        max = TEST_CONFIG['overflow_detection'].get('ramp_max', self.MAX_INPUT)
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
        return [data, ref_data], f'Overflow detection[postscaler={postscaler}, mode={mode}, symmetric_saturation={symmetric_saturation}]', {'split_complex': True}
    
    @compare_plot_data
    @pytest.mark.scaler
    def test_bypass(self, board_conn, setup_scaler):
        for ch in self.board.chan:
            ch.SCALER.CAP_DATA_TYPE = 1
        min = TEST_CONFIG['bypass'].get('ramp_min', self.MIN_INPUT)
        max = TEST_CONFIG['bypass'].get('ramp_max', self.MAX_INPUT)
        source, data = self._set_capture_scaler('periodic_ramp', min=min, max=max)
        return [data, source * 2**self.IMPLICIT_SHIFT // 2**(self.FFT_WIDTH - self.CAPTURE_WIDTH)],
    """
    @pytest.mark.scaler
    @pytest.mark.asyncio
    #@pytest.mark.parametrize("postscaler, symmetric_saturation, frame_cnt", product(range(TEST_CONFIG['overflow_stats'].get('postscaler_min', 0), TEST_CONFIG['overflow_stats'].get('postscaler_max', 31)), (False, True), TEST_CONFIG['overflow_stats'].get('frame_cnt', 1)))
    async def test_overflow_stats(self, board_conn, setup_scaler, postscaler=IDENTITY_POSTSCALER, symmetric_saturation=False, frame_cnt=1000):
        '''
        Tests the collection of scaler overflow statistics by ensuring that the number of detected overflows is correct.


        The input ranges from ramp_min to ramp_max.
        The postscaler ranges from postscaler_min to postscaler_max.
        frame_cnt: number of frames to integrate the statistics over
        '''
        min = TEST_CONFIG['overflow_stats'].get('ramp_min', 2 * MIN_OUTPUT)
        max = TEST_CONFIG['overflow_stats'].get('ramp_max', 2 * MAX_OUTPUT)
        self.board.set_gains(1, postscaler)
        self.board.set_symmetric_saturation(symmetric_saturation)
        source, _ = self._set_capture_scaler(read=False, func='ramp', min=min, max=max)
        ref_data = source * 2**IMPLICIT_SHIFT * 2**postscaler // 2**SCALER_SHIFT
        overflow_stats = (await self.board.get_channel_metrics_async(ch=0, frame_cnt=frame_cnt))[0]
        overflow_cnt = np.sum((ref_data < (MIN_OUTPUT + symmetric_saturation)) | (ref_data > MAX_OUTPUT))
        assert(overflow_stats == 0)#overflow_cnt * frame_cnt)
    """
    @compare_plot_data
    @pytest.mark.scaler
    def test_gain_bank_switching(self, board_conn, setup_scaler, interval=int(10e5)): #10 000 frames
        '''
        Test that the scaler can switch between two independant gain banks in semi-real time by ensuring that the data frames on either side of the switch reflect the change
        '''
        logger = self.get_logger()
        bank1 = np.ones(1024)
        self.board.set_gains(bank1 * 2, self.IDENTITY_POSTSCALER, bank=1)
        self.board.set_gains(bank1, self.IDENTITY_POSTSCALER, bank=0, when='now')
        source = gen_data(func='ramp', min=self.MIN_OUTPUT, max=self.MAX_OUTPUT)
        self.board.set_data_source(source='arb', data=source)
        self.board.switch_gains(bank=1, when=5*interval)
        self.board.start_data_capture(burst_period_in_frames=interval, source='scaler')
        receiver = self.board.get_data_receiver()
        #how to capture multiple frames?
        frames = []
        for i in range(10):
            ts, data, _ = receiver.read_raw_frames()
            #logger.debug(str(ts) + ' ' + str(data[0][700]))
            frames.append(data//2**self.READOUT_SHIFT)
        #find the frame  where switch occurs
        switch = 0
        for i in range(1, len(frames)):
            if (frames[i] != frames[i-1]).any():
                switch = i
                logger.debug(f"Bank switch occured between frames {i*interval} and {(i+1)*interval}")
                break
        assert(switch == 4)
        return [frames[switch], np.clip(source * 2, self.MIN_OUTPUT, self.MAX_OUTPUT)],



    def sat_percent(self, postscaler: int, symmetric_saturation: bool):
        '''
        Returns the percentage of inputs that are expected to saturate the scaler when the log gain is set to postscaler, assuming a uniform distribution over all possible 8 bit inputs.
        '''
        count = 0
        for v in range(-128, 128):
            out = v * 2.0**(postscaler + self.IMPLICIT_SHIFT - self.SCALER_SHIFT)
            count += (out >= self.MAX_OUTPUT) or (out <= self.MIN_OUTPUT + symmetric_saturation)
        return count / 256



    @compare_plot_data(approximate=True)
    @pytest.mark.scaler
    @pytest.mark.statistical
    @pytest.mark.parametrize("rounding_mode, symmetric_saturation, num_frames", product(range(3), (False, True), (100,)))
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
        avgs = np.zeros(self.POSTSCALER_MAX  - self.POSTSCALER_MIN)
        n = 2048 * 16 * num_frames
        for postscaler in range(self.POSTSCALER_MIN, self.POSTSCALER_MAX): #for all possible postscalers
            self.board.set_gains(1, postscaler)
            for i in range(num_frames):
                _, data, _ = receiver.read_raw_frames()
                data //= 2 ** self.READOUT_SHIFT
                avgs[postscaler-self.POSTSCALER_MIN] += np.sum(data)
        avgs /= n
        logger.debug(f"Average: {[s for s in avgs]}")
        if rounding_mode == 0 and not symmetric_saturation:
            ref_data = -0.5 * np.ones(self.POSTSCALER_MAX - self.POSTSCALER_MIN)
        elif rounding_mode == 0 and symmetric_saturation:
            ref_data = -0.5 * (1 - np.vectorize(self.sat_percent)(np.arange(self.POSTSCALER_MIN, self.POSTSCALER_MAX), symmetric_saturation=symmetric_saturation))
        elif rounding_mode > 0 and not symmetric_saturation:
            ref_data = -0.5 * np.vectorize(self.sat_percent)(np.arange(self.POSTSCALER_MIN, self.POSTSCALER_MAX), symmetric_saturation=symmetric_saturation)
        elif rounding_mode > 0 and symmetric_saturation:
            ref_data = np.zeros(self.POSTSCALER_MAX - self.POSTSCALER_MIN)
        return [avgs, ref_data], f'average[rounding_mode={rounding_mode}, symmetric_saturation={symmetric_saturation}]'#, {'y_range': (-0.6, 0.1)}
            
    