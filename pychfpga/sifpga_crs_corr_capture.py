"""
Module for capturing and writing raw corelated data from an RFSoC.

The script can be run within an ipython session.

Make sure you've got the latest firmware that supports corr8 mode with all 8 channelizers!

Run from ipython with

    run sifpga_crs_corr_capture.py

If you want to change some parameters, write them directly in the file. Command-line
arguments are not yet supported.
"""

# Import common packages
import numpy as np
import h5py
import time
import datetime
import os

# Import custom packages
from pychfpga import fpga_array

class CRS_CORR_CAPTURE:
    # Include a super parent class?
    # Maybe logging needs to be inherited?

    def __init__(self,
                 hwm,
                 stderr_log_level,
                 prog,
                 mode,
                 make_directories = False,
                 data_path = None):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        ca = fpga_array.FPGAArray(hwm = hwm,
                                  stderr_log_level = stderr_log_level,
                                  prog = prog,
                                  mode = mode
                                  )

        # Define some useful objects
        self.i = ca.ib[0] # we only need to grab the CRS board
        self.i.GPIO.HOST_FRAME_READ_RATE = 14
        self.ucap = self.i.UCAP
        self.ucap.MODE = 0 # capture data from all channels
        self.u_receiver = self.ucap.get_data_receiver()

        # Define useful variables
        self.NPOLS = 8 # number of input channels, i.e., polarizations
        self.fs = 3200 # MHz - Old firmware: 3000 MHz
        self.M = 2**14
        self.NBINS = int(self.M/2)
        self.f_res = self.fs/self.M
        self.f = self.f_res*np.arange(self.NBINS)

        if self.ucap.MODE == 0:
            self.n_frames_per_capture = 2

        
        for n in range(self.NPOLS):

            # Configure each FFT
            fft = self.i.chan[n].FFT
            # fft.FFT_SHIFT = 0b11111111111111 # Start with an aggressive shift schedule. This can be adjusted with optimize_fft_shift
            # fft.FFT_SHIFT = 0b11111000000000 # less aggressive shift schedule
            # fft.FFT_SHIFT = 0b11111110000000
            # fft.FFT_SHIFT = 0b11111111100000
            fft.FFT_SHIFT = 0b11111111111000
            fft.PIPELINE_DELAY = fft.MEASURED_PIPELINE_DELAY # set pipeline delay equal to measured delay
            print(fft.status())

            # Configure each scaler
            scaler = self.i.chan[n].SCALER
            scaler.USE_OFFSET_BINARY = 0 # don't use offset binary encoding
            scaler.ROUNDING_MODE = 2 # 0: truncate, 1: standard rounding, 2: convergent/banker's rounding
            scaler.FOUR_BITS = 1 # scale to 4 bits
            scaler.SATURATE_ON_MINUS_7 = 1 # this is typically set as default

        # Define a bool to check if the correlator is configured
        self.corr_is_configured = False # we'll configur the correlator later
            
        if make_directories:
            # Configure data paths
            time_string = self.make_time_string()
            self.acq_string = f'{time_string}_D3A_rfsoc'
            self.data_path = data_path # f'/home/basil/rfsoc/rfsoc_data'
            self.digital_gains_path = f'{self.data_path}/digital_gains'
            self.vis_dir_name = f'{self.data_path}/{self.acq_string}'
            self.gain_file_name = f'{self.digital_gains_path}/{self.acq_string}_digitalgain'

            # Make general directories

            # Data parent directory (vis + digital gains)
            if not os.path.exists(self.data_path):
                print(f'Creating data directory at {self.data_path}')
                os.mkdir(self.data_path)
            else:
                print(f'Data directory is {self.data_path}')

            # General digital gains directory
            if not os.path.exists(self.digital_gains_path):
                print(f'Creating general digital gains directory at {self.digital_gains_path}')
                os.mkdir(self.digital_gains_path)
            else:
                print(f'General digital gains directory is {self.digital_gains_path}')

            # Make acq-specific directories

            # Gains
            if not os.path.exists(self.gain_file_name):
                print(f'Creating general digital gains directory at {self.gain_file_name}')
                os.mkdir(self.gain_file_name)
            else:
                print(f'Acquisition igital gains directory is {self.gain_file_name}')

            # Vis
            if not os.path.exists(self.vis_dir_name):
                print(f'Creating vis directory at {self.vis_dir_name}')
                os.mkdir(self.vis_dir_name)
            else:
                print(f'Acquisition vis directory is {self.vis_dir_name}')

    def read_adc_frames(self,
                        period = 0.02,
                        ncap = 1,
                        split = True,
                        verbose = 0
                        ):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        # Check to make sure we're configured to receive channelizer data, not correlated data:
        if self.ucap.OUTPUT_SOURCE_SEL != 0:
            self.ucap.OUTPUT_SOURCE_SEL = 0

        # Make sure we can get data from all channels:
        if self.ucap.MODE != 0:
            self.ucap.MODE = 0 

        # Check that the FFT is not bypassed, the SCALER is bypassed, and set the data source as desired
        for n in range(self.NPOLS):
            self.i.chan[n].FUNCGEN.set_data_source('adc')
            if not self.i.chan[n].FFT.BYPASS:
                self.i.chan[n].FFT.BYPASS = 1
            if not self.i.chan[n].SCALER.BYPASS:
                self.i.chan[n].SCALER.BYPASS = 1
        
        # Start data capture, grabbing data at the output of the
        # scaler, which has been bypassed.
        self.i.start_data_capture(period = period, 
                                  source = 'adc'
                                  )

        # Capture data!
        t, d_adc, c = self.u_receiver.read_raw_frames(format = '16', 
                                                      ncap = ncap, 
                                                      split = split, 
                                                      verbose = verbose)
        d_adc = d_adc >> 2 # shift to 14 bits

        return d_adc

    def read_fft_frames(self, 
                        data_source = 'adc',
                        period = 0.02,
                        ncap = 50,
                        split = True,
                        verbose = 0
                        ):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        # Check to make sure we're configured to receive channelizer data, not correlated data:
        if self.ucap.OUTPUT_SOURCE_SEL != 0:
            self.ucap.OUTPUT_SOURCE_SEL = 0

        # Make sure we can get data from all channels:
        if self.ucap.MODE != 0:
            self.ucap.MODE = 0 

        # Check that the FFT is not bypassed, the SCALER is bypassed, and set the data source as desired
        for n in range(self.NPOLS):
            self.i.chan[n].FUNCGEN.set_data_source(data_source)
            if self.i.chan[n].FFT.BYPASS:
                self.i.chan[n].FFT.BYPASS = 0
            if not self.i.chan[n].SCALER.BYPASS:
                self.i.chan[n].SCALER.BYPASS = 1
        
        # Start data capture, grabbing data at the output of the
        # scaler, which has been bypassed.
        self.i.start_data_capture(period = period, 
                                  source = 'scaler'
                                  )

        # Capture data!
        t, d_fft, c = self.u_receiver.read_raw_frames(format = '16+16', 
                                                      ncap = ncap, 
                                                      split = split,
                                                      verbose = verbose)
        d_fft *= 2**2 # shift by two bits so we have 18+18 - we need to promote the data to np.float64 to do this!
        
        return d_fft

    def read_scaler_frames(self,
                           data_source = 'adc',
                           period = 0.02, 
                           ncap = 1,
                           split = True,
                           verbose = 0
                           ):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        # Check to make sure we're configured to receive channelizer data, not correlated data:
        if self.ucap.OUTPUT_SOURCE_SEL != 0:
            self.ucap.OUTPUT_SOURCE_SEL = 0

        # Make sure we can get data from all channels:
        if self.ucap.MODE != 0:
            self.ucap.MODE = 0 

        # Check that the FFT and SCALER are not bypassed, and set the data source as desired
        for n in range(self.NPOLS):
            self.i.chan[n].FUNCGEN.set_data_source(data_source)
            if self.i.chan[n].FFT.BYPASS:
                self.i.chan[n].FFT.BYPASS = 0
            if self.i.chan[n].SCALER.BYPASS:
                self.i.chan[n].SCALER.BYPASS = 0
        
        # Start data capture, grabbing data at the output of the
        # scaler, which has been bypassed.
        self.i.start_data_capture(0.01, source = 'scaler')

        t, d_scaler, c = self.u_receiver.read_raw_frames(format = '16+16', 
                                                         ncap = ncap, 
                                                         split = True,
                                                         verbose = verbose)
        d_scaler /= 2**12 # shift by 12 bits so we have 4+4 - we need to promote the data to np.float64 to do this!

        return d_scaler

    def read_corr_frames(self,
                         data_source = 'adc',
                         soft_integ_period = 1,
                         number_of_results = 1,
                         filename = None,
                         flush = True,
                         align = True,
                         data_timeout = 0.1,
                         flush_timeout = 0.01,
                         return_format = 'raw',
                         verbose = 0,
                         corr_is_configured = False
                         ):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        # NOTE: this does not presume that gains have been computed.

        self.ucap.OUTPUT_SOURCE_SEL = 1 # u.OUTPUT_SOURCE_SEL = 0 --> raw data, u.OUTPUT_SOURCE_SEL = 1 --> correlator data

        # Check that the FFT and SCALER are not bypassed, and set the data source as desired
        for n in range(self.NPOLS):
            self.i.chan[n].FUNCGEN.set_data_source(data_source)
            if self.i.chan[n].FFT.BYPASS:
                self.i.chan[n].FFT.BYPASS = 0
            if self.i.chan[n].SCALER.BYPASS:
                self.i.chan[n].SCALER.BYPASS = 0

        # Configure correlator if not done so already
        if not self.corr_is_configured:
            self.corr = self.i.CORR # corr object
            self.corr_receiver = self.i.get_corr_receiver() # corr receiver object
            self.corr.AUTOCORR_ONLY = 0 # 0: all products
            self.corr.NO_ACCUM = 0 # 0: do accumulate
            self.NCORR_PROD = int(self.NPOLS*(self.NPOLS + 1) // 2)
            self.corr.INTEGRATION_PERIOD = 16384 - 1 # 32768 - 1 # 65536 - 1 # 32768 - 1 # Default: 16384 - 1, maximimum: 65536 - 1
            
            # Update corr_is_configured
            self.corr_is_configured = True

        t1 = time.time() # This is our timestamp
        d, count, sat, = self.corr_receiver.read_corr_frames(soft_integ_period = soft_integ_period,
                                                             number_of_results = number_of_results,
                                                             filename = None,
                                                             flush = flush,
                                                             align = align,
                                                             data_timeout = data_timeout,
                                                             flush_timeout = flush_timeout,
                                                             return_format = return_format,
                                                             verbose = verbose
                                                             )
        t2 = time.time()

        print(f'Took {t2 - t1}s to capture corr data')

        return t1, d, count, sat

    def optimize_fft_shift(self,
                           shift_buffer = 3
                           ):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        # First, set the most aggressive shift schedule.
        # <Insert here>

        # I found at that if you want to create a list of an N-bit number that flips one bit at a time, there's a funny
        # Fibonacci-like pattern that describes the decimal value of the binary shift schedule!
        fib = 1
        shifts = []
        for n in range(14):
            shifts.append(0b11111111111111 - fib)
            fib += 2**(n + 1)

        stage = 0
        while True:
            print(f'Testing shift schedule', bin(shifts[stage]))
            ovfl_pols = []
            for n in range(self.NPOLS):
                # Check each pol for overflows, and save the pol number if one is detected
                if self.i.chan[n].FFT.OVERFLOW_COUNT != 0:
                    ovfl_pols.append(n)
            if len(ovfl_pols) !=  0 or stage == 13:
                print('Detected overflows on channel(s)', ovfl_pols)
                # Adjust the shift schedule by shift_buffer stages as soon as we have any overflows, and break
                print(f'Adjusting shift schedule by {shift_buffer} stages')
                stage = stage - shift_buffer
                final_shift = shifts[stage]
                for n in range(self.NPOLS):
                    print(f'Applying final shift schedule to Pol {n}:', bin(shifts[stage]))
                    # Configure each FFT shift
                    self.i.chan[n].FFT.FFT_SHIFT = shifts[stage] 
                break
            else:
                # Change the shift schedule by 1 stage
                stage += 1
                for n in range(self.NPOLS):
                    # Configure each FFT shift
                    self.i.chan[n].FFT.FFT_SHIFT = shifts[stage]

        return final_shift
    
    def set_gains(self, 
                  lin_gain, 
                  log_gain):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        if not type(lin_gain) == np.ndarray:
            # If not passed as an array, create an array of
            # linear gains of constant value
            lin_gain = np.repeat(lin_gain, self.NBINS) #, dtype = '>i2')

            # From this point forward, lin_gain is an ndarray

        # Set gains on all channelizers
        for n in range(self.NPOLS):
            self.i.chan[n].SCALER.set_gain_table(lin_gain[n], bank = 0)
            self.i.chan[n].SCALER.SHIFT_LEFT = log_gain[n]

        return 
  
    def compute_gains(self,
                      target = 1.5*np.sqrt(2), # default value borrowed from CHIME
                      gain_type = 'raw', 
                      number_of_fft_averages = 250,
                      rms_accuracy_tol = None, # %
                      save_gains = False
                      ):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        # Capture ncap FFT frames of data, checking for FFT overflows. If there are any, start the FFT capture again
        # until we have a clean set of data.
        
        ctr = 0
        while True:
            print(f'Gain computation trial {ctr}')
            ctr += 1

            fft_overflows = np.zeros(self.NPOLS)

            for n in range(self.NPOLS):
                # Pulse FFT overflow reset
                self.i.chan[n].FFT.OVERFLOW_RESET = 1
                self.i.chan[n].FFT.OVERFLOW_RESET = 0
            
            # ==================
            # Capture ncap FFT frames of data
            fft_data = self.read_fft_frames(period = 0.02,
                                            data_source = 'adc',
                                            ncap = int(number_of_fft_averages/self.n_frames_per_capture),
                                            split = True,
                                            verbose = 0)

            for n in range(self.NPOLS):
                # Check FFT overflow status on each pol, and pulse the reset again.
                fft_overflows[n] = self.i.chan[n].FFT.OVERFLOW_COUNT
                self.i.chan[n].FFT.OVERFLOW_RESET = 1
                self.i.chan[n].FFT.OVERFLOW_RESET = 0

            print(f'FFT Overflows: {fft_overflows}')

            if all(fft_overflows == 0):
                break
        
        # ==================
        # Compute FFT RMS. The np.abs just converts the np.complex128 to np.float64, since the magnitude is real-valued
        fft_rms = np.sqrt(np.mean(np.abs(fft_data*np.conj(fft_data)), axis = 1))

        # Check the target Scaler RMS
        if target < 0 or target > np.sqrt(7**2 + 7**2):
            raise ValueError(f'Scaler target magnitude {target} is outside of bounds 0 < target < {np.sqrt(7**2 + 7**2)}')
        target *= 2**31 # target RMS is scaled by 31 bits, since the scaler takes 4 MSBs of 35 bit number

        # Compute the gain needed to shift the fft_rms to the target
        gain = target / fft_rms

        # Treat any possible infinities
        gain[gain == np.inf] = 2**31 

        # ==================
        # Break down the raw gains into linear and log gains, where gain = lin * 2**log

        # IMPORTANT! let the linear gains absorb some of the bits that would otherwise 
        # be used in the log gains so that we have better linear gain resolution.
        # print('log2 gain', np.log2(gain)) # need to make a loop to check best log
        trim_bits = 12 # need a way to cycle through the number that preserves the largest linear gain

        # Compute the log gains. Take log2 of the raw gains so that we get an idea of how many bit shifts
        # we need to do (plus some decimal shifting that will be absorbed in the linear gains). Take its
        # ceiling, and clip it just in case it's too big or too small. Reduce this value by trim_bits to
        # obtain the log gain. The rest of the gain will be allocated to the linear gains.
        log = np.clip((np.ceil(np.log2(np.median(gain, axis = 1)))), 0, 31) - trim_bits
        print('log', log)

        # Allocate the remainder of the raw gains to the linear gains. 
        lin = (gain / 2**np.repeat(log.reshape(self.NPOLS, 1), self.NBINS, axis = 1)) + 0.5 # add 0.5 for rounding

        # ==================
        # Now that we have our raw gains, we can apply some additional processing.
        if gain_type == 'raw':
            print('Setting gains to raw')
            # self.set_gains(lin, [int(n) for n in log]) # cast log gains to int

        elif gain_type == 'flat':
            print('Setting gains to flat')
            lin = np.mean(lin[:, np.where(self.f > 300)[0]], axis = 1) # Determine the mean of the linear gains, ignoring frequencies below 300 MHz.
            # self.set_gains(lin_flat, [int(n) for n in log]) # cast log gains to int

        elif gain_type == 'smooth':

            # Functions for fitting polynomials to gain

            def make_A(x, order):
                A = np.zeros((len(x), order))
                for n in range(order):
                    A[:, n] = x**n
                return A

            def lstsqr_fit(x, y, sigma, order):
                sigma = np.diag(sigma) # assume sigma is the variance, not std dev
                sigma_inv = np.linalg.inv(sigma)
                A = make_A(x, order)
                m = np.linalg.inv(A.T @ sigma_inv @ A) @ A.T @ sigma_inv @ y
                return m

            def make_poly(x, coeffs):
                y = np.zeros(len(x))
                for n in range(len(coeffs)):
                    y += coeffs[n]*x**n
                return y

            print('Smoothing gains...')

            # The following is hardcoded for now.
            order = 8
            lin_smooth = np.zeros((self.NPOLS, len(self.f)))
            for n in range(self.NPOLS):
                # Trim first 300 MHz when running the fit
                m = lstsqr_fit(x = self.f, # [np.where(self.f > 50)[0]], 
                               y = lin[n], # , np.where(self.f > 50)[0]], 
                               sigma = np.repeat(10, len(self.f)), # 10 is just a guess
                               # sigma = np.repeat(10, len(self.f[np.where(self.f > 50)[0]])), # 10 is just a guess
                               order = order) 
                lin_smooth[n] = make_poly(x = self.f, coeffs = m)
            # lin_smooth = lin_smooth.astype(np.int16) # cast to np.int16

            # Set lin = lin_smooth
            print('Setting gains to smooth')
            lin = lin_smooth

        # Cast the linear gains to np.int16
        lin = lin.astype(np.int16)

        # Anywhere that the linear gain is saturated (> 32767) or negative shall be set to 0
        lin = np.where((0 < lin) & (lin < 32767), lin, 0)

        # Set the gains
        self.set_gains(lin, [int(n) for n in log]) # cast log gains to int

        # ==================
        # If rms_accuracy_tol is not None, capture SCALER data and check that they are at or near the target

        if rms_accuracy_tol is not None:
            print('Checking RMS of Scaler output is within the specified tolerance.')
            scaler_data = self.read_scaler_frames(data_source = 'adc', ncap = 100)
            scaler_data_rms = np.sqrt(abs(np.mean(scaler_data * scaler_data.conj(), axis = 1)))
            mean_abs_rms = np.mean(scaler_data_rms, axis = 1)

            tol = (rms_accuracy_tol/100) * (target / 2**31) # Calculate 
            tol_range = np.array([(target / 2**31) - tol, (target / 2**31) + tol]) # Tolerance range

            out_of_tol_channels = []
            out_of_tol_mean_rms = []
            for n in range(self.NPOLS):
                if tol_range.min() < mean_abs_rms[n] < tol_range.max():
                    out_of_tol_channels.append(n)
                    out_of_tol_mean_rms.append(mean_abs_rms[n])

            if not len(out_of_tol_channels) == 0:
                raise ValueError(f'Channels {out_of_tol_channels} are outside the allowed Scaler RMS range of {rms_accuracy_tol}%. \n \
                                   The allowed range is {tol_range} LSBs RMS. \n \
                                   The mean values on these channels are {out_of_tol_mean_rms} LSBs RMS.')

        else:
            print('Skipping Scaler tolerance check.')
            scaler_data = None

        if save_gains:
            # Save gains, calling save_gains()
            print('Saving gains')
            self.save_gains(lin, log, gain_type)

        return fft_data, fft_rms, gain, lin, log, scaler_data
                      
    def save_gains(self, 
                   lin_gain,
                   log_gain,
                   gain_type):
        """
        Description.

        Parameters
        ----------
        the : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        # Digital gains
        if not os.path.exists(self.digital_gains_path):
            print(f'Creating digital gains directory at {self.digital_gains_path}')
            os.mkdir(self.digital_gains_path)
        else:
            print(f'Digital gains directory is {self.digital_gains_path}')

        digital_gain_file_name = f'{self.gain_file_name}/gains.hdf5'
        print(f'Creating digital gains file {digital_gain_file_name}')

        # Create the gain hdf5 file
        f = h5py.File(f'{self.gain_file_name}/gains.hdf5', 'w')

        lin_gain_dset = f.create_dataset('lin',
                                         (self.NPOLS, self.NBINS),
                                         data = lin_gain,
                                         dtype = np.int16)

        lin_gain_dset.attrs['gain_type'] = gain_type
        
        log_gain_dset = f.create_dataset('log', 
                                         (self.NPOLS,),
                                         data = log_gain,
                                         dtype = np.int8) # type might be 'int', but small enough that 8 bits is plenty (max log gain is 31)

        f.close()

        return

    def make_time_string(self):
        """
        Breaks down a datetime.datetime.now object into
        constituent units and refactors them in a single
        string. Used for creating file names.

        Parameters
        ----------
        None.

        Returns
        -------
        Datetime string in the format

            YEAR MONTH DAY T HOUR MINUTE SECOND Z

        For example:

            20230501T113105Z

        """

        t = datetime.datetime.now()
        y = t.year
        mth = t.month
        d = t.day
        h = t.hour
        m = t.minute
        s = t.second

        # Hacky, but add a 0 if a given unit is only 1 number
        # to be consistent with ICE file names
        if len(str(mth)) == 1:
            mth = f'0{mth}'

        if len(str(d)) == 1:
            d = f'0{d}'

        if len(str(h)) == 1:
            h = f'0{h}'

        if len(str(m)) == 1:
            m = f'0{m}'

        if len(str(s)) == 1:
            s = f'0{s}'

        return f'{y}{mth}{d}T{h}{m}{s}Z'

    def observe(self, 
                n_vis_per_file = 256,
                integration_time = 10,
                optimize_shift = False,
                gain_target = 1.5*np.sqrt(2), # borrowed from CHIME
                number_of_fft_averages = 1000,
                gain_type = 'raw',
                capture_adc_bursts = True,
                n_adc_bursts = 5,
                capture_fft_bursts = True,
                n_fft_bursts = 5
                ):

        """
        Runs overnight acquisitions, handling data capture and file writing.

        Parameters
        ----------

        Returns
        -------


        """

        # ===========
        # Start by optimizing the FFT shift schedule.
        if optimize_shift:
            print('')
            print('')
            print('===================================')
            print('')
            print('--- O P T I M I Z E   F F T   S H I F T  ---')
            print('')
            final_shift = self.optimize_fft_shift()
            print('')
        else:
            shifts = np.zeros(self.NPOLS)
            for n in range(self.NPOLS):
                shifts[n] = self.i.chan[n].FFT.FFT_SHIFT
            unique_shifts = np.unique(shifts)
            if len(unique_shifts) == 1:
                final_shift = unique_shifts[0]
            # else:
                # raise ValueError('')

        # ===========
        # Compute gains.

        print('')
        print('')
        print('===================================')
        print('')
        print('--- C O M P U T E   G A I N S  ---')
        print('')
        self.compute_gains(target = gain_target,
                           gain_type = gain_type, 
                           number_of_fft_averages = number_of_fft_averages, 
                           rms_accuracy_tol = None, # let's just ignore this parameter for now
                           save_gains = True)
        print('Gain computation completed!')
        print('')

        # ===========
        # Configure the channelizer and correlator. This is done after gain
        # computation because the compute gains algorithm changes the
        # configuration.

        print('')
        print('')
        print('===================================')
        print('')
        print('    --- C O N F I G U R E  ---')
        print('')

        print('Configuring firmware')

        # Set up the channelizer. Input data should be coming
        # from the ADC, and nothing should be bypassed.
        self.i.set_channelizer(data_source = 'adc',
                               fft_bypass = 0,
                               scaler_bypass = 0
                               )

        # Configure correlator
        if not self.corr_is_configured:
            self.ucap.OUTPUT_SOURCE_SEL = 1 # u.OUTPUT_SOURCE_SEL = 1 --> correlator data
            self.corr = self.i.CORR # corr object
            self.corr_receiver = self.i.get_corr_receiver() # corr receiver object
            self.corr.AUTOCORR_ONLY = 0 # 0: all products
            self.corr.NO_ACCUM = 0 # 0: do accumulate
            self.NCORR_PROD = int(self.NPOLS*(self.NPOLS + 1) // 2)
            self.corr.INTEGRATION_PERIOD = 16384 - 1 # 32768 - 1 # 65536 - 1 # 32768 - 1 # Default: 16384 - 1, maximimum: 65536 - 1
            
            # Update the corr configure check
            self.corr_is_configured = True

        print(self.corr.status()) # print corr configuration status

        # ===========
        # Capture and write data

        print('')
        print('')
        print('===================================')
        print('')
        print('      --- O B S E R V E  ---')
        print('')

        # Run data capture until keyboard interrupt
        file_number = 0 # starting hdf5 file number

        # Calculate how many frames we need for desired  integration time
        s_per_frame = 2**14*(1/(self.fs*1e6)) # samples/frame * seconds/sample. Make sure sampling frequency is in Hz
        set_integration_time = integration_time # s
        n_firmware_frames = self.corr.INTEGRATION_PERIOD + 1
        n_software_frames = int(set_integration_time / s_per_frame / n_firmware_frames)
        actual_integration_time = n_firmware_frames * n_software_frames * s_per_frame
        print(f'Target integration time: {set_integration_time} s')
        print(f'Actual integration time: {actual_integration_time} s')

        # Generate product array
        prod_idx = np.triu_indices(8)
        prod = np.zeros((len(prod_idx[0]), 2))
        for n in range(prod.shape[0]):
            prod[n] = (prod_idx[0][n], prod_idx[1][n])
        prod = prod.astype(np.int16)

        try:
            while True:

                # Create vis file
                file_name = f'{self.vis_dir_name}/{file_number}.hdf5'
                print('')
                print('+++++++++++++++++++++++++++++++++')
                print(f'Creating new data file \'{file_name}\'')
                f = h5py.File(file_name, 'w')

                # Create data sets
                dset_vis    = f.create_dataset('vis', (n_vis_per_file, self.NBINS, self.NCORR_PROD), dtype = np.complex128) # Create vis dataset
                dset_counts = f.create_dataset('counts', (n_vis_per_file, self.NBINS), dtype = np.uint32) # Create counts dataset
                dset_sat    = f.create_dataset('sat', (n_vis_per_file, self.NBINS, self.NCORR_PROD), dtype = np.complex64) # Create vis dataset

                # Assign attributes to vis dataset:
                dset_vis.attrs['n_firmware_frames'] = n_firmware_frames # Number of firmware frames per visibility
                dset_vis.attrs['n_software_frames'] = n_software_frames # Number of software frames per visibility
                dset_vis.attrs['fft_shift_schedule'] = final_shift # Final shift schedule, represented as an int

                # Make index_map group
                index_map_grp = f.create_group('index_map')
                dset_freq = index_map_grp.create_dataset('freq', (self.NBINS, ), dtype = np.float64)
                dset_prod = index_map_grp.create_dataset('prod', (self.NCORR_PROD, 2), dtype = np.int16)
                dset_time = index_map_grp.create_dataset('time', (n_vis_per_file, ), dtype = np.float64)

                dset_freq[:] = self.f
                dset_prod[:] = prod

                # Make numpy buffers for index_map
                t_buf = np.zeros(n_vis_per_file, dtype = np.float64)
                vis_buf = np.zeros((n_vis_per_file, self.NBINS, self.NCORR_PROD), dtype = np.complex128)
                counts_buf = np.zeros((n_vis_per_file, self.NBINS), dtype = np.uint32)
                sat_buf = np.zeros((n_vis_per_file, self.NBINS, self.NCORR_PROD), dtype = np.complex64)

                # Make statistics group
                stats_grp = f.create_group('stats')
                dset_FRAME_COUNT = stats_grp.create_dataset('frame_count', (n_vis_per_file, self.NPOLS), dtype = int)
                dset_ADC_OVERFLOWS = stats_grp.create_dataset('adc_overflows', (n_vis_per_file, self.NPOLS), dtype = int)
                dset_FFT_OVERFLOWS = stats_grp.create_dataset('fft_overflows', (n_vis_per_file, self.NPOLS), dtype = int)
                dset_SCALER_OVERFLOWS = stats_grp.create_dataset('scaler_overflows', (n_vis_per_file, self.NPOLS), dtype = int)
                dset_SCALER_STATS_READY = stats_grp.create_dataset('scaler_stats_ready', (n_vis_per_file, self.NPOLS), dtype = int)
                dset_CORR_OVERRUN = stats_grp.create_dataset('corr_overrun', (n_vis_per_file, ), dtype = int)

                # Make numpy buffers for statistics
                frame_count_buf = np.zeros((n_vis_per_file, self.NPOLS), dtype = int)
                adc_overflows_buf = np.zeros((n_vis_per_file, self.NPOLS), dtype = int)
                fft_overflows_buf = np.zeros((n_vis_per_file, self.NPOLS), dtype = int)
                scaler_overflows_buf = np.zeros((n_vis_per_file, self.NPOLS), dtype = int)
                scaler_stats_ready_buf = np.zeros((n_vis_per_file, self.NPOLS), dtype = int)
                corr_overrun_buf = np.zeros(n_vis_per_file, dtype = int)

                if capture_adc_bursts:
                    # Capture ADC data. Note: a single capture for all 8 pols in mode 0 is equal to
                    # 2*16384*16*8/8/1e6 = 0.524288 MB of data.

                    # Create data set
                    dset_adc = f.create_dataset('adc', (self.NPOLS, self.n_frames_per_capture*n_adc_bursts, self.M), dtype = np.int16) 

                    # Capture bursts
                    print(f'Capturing {self.n_frames_per_capture*n_adc_bursts} ADC frames...')
                    d_adc = self.read_adc_frames(period = 0.02,
                                                 ncap = n_adc_bursts,
                                                 split = True,
                                                 verbose = 0)

                    # Write to file
                    dset_adc[...] = d_adc

                if capture_fft_bursts:
                    # Capture FFT data. Note: a single capture for all 8 pols in mode 0 is equal to
                    # 2*8192*(16+16)*8/8/1e6 = 0.524288 MB of data.

                    # Create data set
                    dset_fft = f.create_dataset('fft', (self.NPOLS, self.n_frames_per_capture*n_adc_bursts, self.NBINS), dtype = np.complex128) 
                    
                    # Capture bursts
                    print(f'Capturing {self.n_frames_per_capture*n_adc_bursts} FFT frames...')
                    d_fft = self.read_fft_frames(data_source = 'adc',
                                                 period = 0.02,
                                                 ncap = n_fft_bursts,
                                                 split = True,
                                                 verbose = 0)

                    # Write to file
                    dset_fft[...] = d_fft

                for n in range(n_vis_per_file):

                    # This is done automatically on each capture, but just in case...
                    self.ucap.OUTPUT_SOURCE_SEL = 1 # u.OUTPUT_SOURCE_SEL = 1 --> correlator data

                    print('')
                    print('<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>')
                    print(f'Capture {n} for file {file_name}')

                    # Pulse resets
                    for m in range(self.NPOLS):

                        # ADC stats reset
                        self.i.chan[m].FUNCGEN.RESET_STATS = 1
                        self.i.chan[m].FUNCGEN.RESET_STATS = 0

                        # FFT stats reset
                        self.i.chan[m].FFT.OVERFLOW_RESET = 1
                        self.i.chan[m].FFT.OVERFLOW_RESET = 0

                        # Scaler stats reset
                        self.i.chan[m].SCALER.STATS_CAPTURE = 1

                    # Capture data, filling the numpy buffer on each iteration
                    if n == 0:
                        flush = True # Not very pythonic, but flush on first capture
                    else:
                        flush = False # Otherwise, no flush
                        
                    t, vis, counts, sat = self.read_corr_frames(data_source = 'adc',
                                                                soft_integ_period = n_software_frames,
                                                                number_of_results = 1,
                                                                filename = None,
                                                                flush = flush,
                                                                align = False,
                                                                data_timeout = 0.1,
                                                                flush_timeout = 0.01,
                                                                return_format = 'raw',
                                                                verbose = 0,
                                                                corr_is_configured = self.corr_is_configured)

                    t_buf[n] = t
                    vis_buf[n] = vis[0] # vis is a 3D array even if we only request 1 result
                    counts_buf[n] = counts[0] # counts is 2D, but 0 axis has length of just 1
                    sat_buf[n] = sat

                    # Capture statistics after recording correlator data
                    print('Capturing statistics')
                    for m in range(self.NPOLS):

                        # ADC stats
                        adc_overflows_buf[n, m] = self.i.chan[m].FUNCGEN.ADC_OVERFLOW_CTR

                        # FFT stats
                        fft_overflows_buf[n, m] = self.i.chan[m].FFT.OVERFLOW_COUNT

                        # Scaler stats
                        scaler = self.i.chan[m].SCALER
                        if scaler.STATS_READY:
                            scaler_stats_ready_buf[n, m] = scaler.STATS_READY
                            frame_count_buf[n, m] = scaler.STATS_FRAME_COUNT
                            scaler_overflows_buf[n, m] = scaler.STATS_SCALER_OVERFLOWS
                        else:
                            print('Scaler stats not ready')
                        scaler.STATS_CAPTURE = 0 # reset Scaler stats capture

                    # Correlator stats
                    corr_overrun_buf[n] = self.corr.OVERRUN

                    # Print some statistics:
                    print(f'FFT Overflows: {fft_overflows_buf[n]}')
                    print(f'Scaler Overflows: {scaler_overflows_buf[n]}')
                    print(f'Correlator Overflows: {corr_overrun_buf[n]}')

                # Once the loop is complete, write the numpy buffers to disk
                print('')
                print('=================================')
                print(f'Writing {file_name} to disk...')

                # Write data returned by correlator
                dset_time[...] = t_buf
                dset_vis[...] = vis_buf
                dset_counts[...] = counts_buf
                dset_sat[...] = sat_buf

                # Write statistics
                dset_FRAME_COUNT[...] = frame_count_buf
                dset_ADC_OVERFLOWS[...] = adc_overflows_buf
                dset_FFT_OVERFLOWS[...] = fft_overflows_buf
                dset_SCALER_OVERFLOWS[...] = scaler_overflows_buf
                dset_SCALER_STATS_READY[...] = scaler_stats_ready_buf
                dset_CORR_OVERRUN[...] = corr_overrun_buf

                print('Data written!')

                # Close file
                print(f'Closing file {file_name}')
                f.close()

                # Increment file number
                file_number += 1

        except KeyboardInterrupt:
            print('')
            print('')
            print('===================================')
            print('')
            print('Saving the buffer before ending observation...')

            # Write data returned by correlator
            dset_time[...] = t_buf
            dset_vis[...] = vis_buf
            dset_counts[...] = counts_buf
            dset_sat[...] = sat_buf

            # Write statistics
            dset_FRAME_COUNT[...] = frame_count_buf
            dset_ADC_OVERFLOWS[...] = adc_overflows_buf
            dset_FFT_OVERFLOWS[...] = fft_overflows_buf
            dset_SCALER_OVERFLOWS[...] = scaler_overflows_buf
            dset_SCALER_STATS_READY[...] = scaler_stats_ready_buf
            dset_CORR_OVERRUN[...] = corr_overrun_buf

            print('Done!')
            print('')
            print(f'Ending observation {self.acq_string}.')
            print('')

        return

# Sandbox mode:
# ccc = CRS_CORR_CAPTURE(hwm = 'crs 0016',
#                        stderr_log_level = 'debug',
#                        prog = 2,
#                        mode = 'corr8',
#                        make_directories = False)

# final_fft_shift = ccc.optimize_fft_shift()
# fft_data, fft_rms, gain, lin, log, scaler_data  = ccc.compute_gains(1000)

# Observation mode:
ccc = CRS_CORR_CAPTURE(hwm = 'crs 0022',
                       stderr_log_level = 'debug',
                       prog = 2,
                       mode = 'corr8',
                       make_directories = True,
                       data_path = '/home/ih/D3A_acq/data')

# ccc.observe(n_vis_per_file = 5, # 128,
#             integration_time = 1,
#             optimize_shift = False,
#             gain_target = 1.5*np.sqrt(2),
#             number_of_fft_averages = 1000,
#             gain_type = 'raw',
#             capture_adc_bursts = True,
#             n_adc_bursts = 100,
#             capture_fft_bursts = True,
#             n_fft_bursts = 100
#             )