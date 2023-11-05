"""

Module for capturing and writing raw corelated data from an RFSoC.

The script can be run within an ipython session.

Make sure you've got the latest firmware that supports corr8 mode with all 8 channelizers!

Run from ipython with

    run sifpga_crs_corr_capture.py

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

    def __init__(self):
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

        ca = fpga_array.FPGAArray(hwm = 'crs 0016',
                                  stderr_log_level = 'debug',
                                  prog = 2,
                                  mode = 'corr8'
                                  )

        # Define some useful objects
        self.i = ca.ib[0] # we only need to grab the CRS board
        self.ucap = self.i.UCAP
        self.ucap.MODE = 0 # capture data from all channels
        self.u_receiver = self.ucap.get_data_receiver()

        # Define useful variables
        self.NPOLS = 8 # number of input channels, i.e., polarizations
        self.fs = 3000 # MHz
        self.M = 2**14
        self.NBINS = int(self.M/2)
        self.f_res = self.fs/self.M
        self.f = self.f_res*np.arange(self.NBINS)

        if self.ucap.MODE == 0:
            self.n_frames_per_capture = 2

        # # Configure channelizer
        # self.i.set_channelizer(data_source = 'adc', 
        #     fft_bypass = False, 
        #     scaler_bypass = False, 
        #     # gain = (1, 15)
        #     )
        
        for n in range(self.NPOLS):
            
            # Configure each FFT
            fft = self.i.chan[n].FFT
            fft.FFT_SHIFT = 0b11111111111111 # hardcode shift schedule to all 14 stages
            fft.PIPELINE_DELAY = fft.MEASURED_PIPELINE_DELAY # set pipeline delay equal to measured delay
            print(fft.status())
            
            # Configure each scaler
            scaler = self.i.chan[n].SCALER
            scaler.USE_OFFSET_BINARY = 0 # don't use offset binary encoding
            scaler.ROUNDING_MODE = 2 # 0: truncate, 1: standard rounding, 2: convergent/banker's rounding
            scaler.FOUR_BITS = 1 # scale to 4 bits
            scaler.SATURATE_ON_MINUS_7 = 1 # this is typically set as default
        
        # Add some quick sanity checks to make sure things are 
        # configured correctly:
        if not all([self.i.chan[n].FFT.FFT_SHIFT == int(self.M) - 1 for n in range(self.NPOLS)]):
            raise ValueError('FFT_SHIFT not configured properly on one or more channels.')
            
        # Configure data paths
        # 20230501T113105Z_D3A
        time_string = self.make_time_string()
        self.acq_string = f'{time_string}_D3A'
        self.data_path = f'/home/ih/d3a/rfsoc_data'
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

    def read_fft_frames(self, 
                        n_captures = 50
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
        
        # Set up the channelizer. Input data should be coming
        # from the ADC, the FFT should *not* be bypassed, and
        # the scaler should be bypassed. IMPORTANT: this assumes 
        # gains have been calibrated elsewhere.
        self.i.set_channelizer(data_source = 'adc', 
                               fft_bypass = 0, 
                               scaler_bypass = 1
                               )
        
        # Start data capture, grabbing data at the output of the
        # scaler, which has been bypassed.
        self.i.start_data_capture(0.01, 
                                  source = 'scaler'
                                  )
        
        # Create buffer with shape (channel, capture_number, frequency_bin)
        fft_data = np.zeros((self.n_frames_per_capture*n_captures, self.NPOLS, self.NBINS), dtype = np.complex128)
        
        # Fill the buffer!
        for n in range(n_captures):
            print(f'Capture {n}')
        
            t, d, c = self.u_receiver.read_raw_frames(verbose = 0) # read raw frames from UCAP receiver
            d = d.view('>i2') # view the data in two bytes
            
            # Form complex FFT bins
            re = d[:,  ::2]
            im = d[:, 1::2]
            cmplx_flat = re + 1j*im

            # Split the cmplx_flat array into individual frames:
            cmplx_frames = np.array(np.split(cmplx_flat, self.n_frames_per_capture, axis = 1))
            
            # Fill the buffer. Since we have n_frames_per_capture, we will fill the buffer
            # in sets of length n_frames_per_capture:
            fft_data[self.n_frames_per_capture*n:self.n_frames_per_capture*(n + 1), :, :] = cmplx_frames
        
        return fft_data

    def compute_fft_rms(self, 
                        fft_data
                        ):
        """
        Compute the RMS of FFT data for all 8 channels.
        
        The RMS will be computed along the real and imaginary
        axes independently; i.e., the FFT data will be broken
        into constituent real and imaginary parts, the RMS 
        will be computed for each part, and then the RMS of
        each part will be stitched back together as complex 
        numbers.
        
        E.g., let's say we have
        
            (1+4j), (2+5j), (3+6j).
            
        The real and imaginary RMS values are
        
            rms_re = sqrt((1/3) * (1^2 + 2^2 + 3^2))
            rms_im = sqrt((1/3) * (4^2 + 5^2 + 6^2))
            
        This works because we are applying real gains, which
        scale the real and imaginary parts equally. Therefore,
        we can independently squeeze the real and imaginary parts
        into 4 bits independently.

        Parameters
        ----------
        fft_data : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """

        n_frames = fft_data.shape[0]

        # rms_re = np.sqrt((1/n_frames)*np.sum(np.real(fft_data)**2, axis = 0))
        # rms_im = np.sqrt((1/n_frames)*np.sum(np.imag(fft_data)**2, axis = 0))

        mean_abs = np.mean(np.abs(fft_data), axis = 0)

        # rms = np.sqrt((1/n_frames)*(np.sum(np.real(fft_data)**2, axis = 0) + np.sum(np.real(fft_data)**2, axis = 0)))

        # rms_cmplx = rms_re + 1j* rms_im
        
        return mean_abs # rms_re + rms_im # rms_cmplx

    def read_scaler_frames(self,
                           n_captures = 1
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
        
        # Set up the channelizer. Input data should be coming
        # from the ADC, and both the FFT and SCALER should 
        # *NOT* be bypassed. IMPORTANT: this assumes 
        # gains have been calibrated elsewhere.
        self.i.set_channelizer(data_source = 'adc', 
                               fft_bypass = 0, 
                               scaler_bypass = 0
                               )
        
        # Start data capture, grabbing data at the output of the
        # scaler, which has been bypassed.
        self.i.start_data_capture(0.01, 
                                  source = 'scaler'
                                  )
        
        # Create buffer with shape (channel, capture_number, frequency_bin)
        scaler_data = np.zeros((self.n_frames_per_capture*n_captures, self.NPOLS, self.NBINS), dtype = np.complex128)
        
        # Fill the buffer!
        for n in range(n_captures):
            print(f'Capture {n}')
        
            t, d, c = self.u_receiver.read_raw_frames(verbose = 0) # read raw frames from UCAP receiver
            d = d.view('>i2') # view the data in two bytes
            d = d >> 12 # shift by 12 bits, since SCALER is 4+4 bits
            
            # Form complex FFT bins
            re = d[:,  ::2]
            im = d[:, 1::2]
            cmplx_flat = re + 1j*im

            # Split the cmplx_flat array into individual frames:
            cmplx_frames = np.array(np.split(cmplx_flat, self.n_frames_per_capture, axis = 1))
            
            # Fill the buffer. Since we have n_frames_per_capture, we will fill the buffer
            # in sets of length n_frames_per_capture:
            scaler_data[self.n_frames_per_capture*n:self.n_frames_per_capture*(n + 1), :, :] = cmplx_frames
        
        return scaler_data

    def read_corr_frames(self, 
                         soft_integ_period = 1,
                         number_of_results = 1,
                         filename = None,
                         flush = True,
                         align = True,
                         data_timeout = 0.001,
                         flush_timeout = 0.001,
                         return_format = 'raw',
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

        # Check to make sure gains have been calculated and are set

        # CHECK

        # flush first time this is called, but not subsequent times

        t1 = time.time() # This is our timestamp
        d, count, sat = self.corr_receiver.read_corr_frames(soft_integ_period = soft_integ_period,
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

        return # nothing
  
    def compute_gains(self, 
                      number_of_fft_averages = 100
                      ):
                      # initial_gains = (1.0, 22)):
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
        
        # Capture 100 FFT frames of data and compute their RMS for each bin (computing
        # real and imag parts separately)
        fft_data = self.read_fft_frames(int(number_of_fft_averages/self.n_frames_per_capture))
        fft_rms = self.compute_fft_rms(fft_data)

        # (100, 8, 8192) --> (8, 8192)

        # Compute the gain that shifts the FFT RMS to the target

        fft_rms *= 4 # multiply by 4 since we only capture 16+16 bits of the FFT, and need to shift to 18+18
        fft_rms += 1 # # used for debugging (treating rms values of 0)

        # target = 1.5*np.sqrt(2) * 2**31 # target RMS scaled by 31 bits, since the scaler takes 4 MSBs of 35 bit number
        target = 2 * 2**31

        gain = target / fft_rms # / 4

        # == Copied from calculate_gains.py
        # Eliminate gains that would be too high from the computations by creating
        # a masked array
        # bad_values = (gain > 2**(31+16)) | ~ np.isfinite(gain)
        # # ignore bin 0, which has a DC components that is way larger than the signal in other bins
        # bad_values[:, 0] = True
        # gain = np.ma.array(gain, mask=bad_values)

        # # Treat any possible infinities
        gain[gain == np.inf] = 2**31 
        print(np.where(gain == np.inf))

        # test
        print('log2 gain', np.log2(gain))
        # make a loop to check 
        # let the lin gains absorb some of the bits that would otherwise be used in log gains to save resolution

        # IMPORTANT!
        trim_bits = 12 # need a way to cycle through the number that preserves the largest linear gain
        # need to also check that no linear gains are negative after casting them to np.int16

        # log = np.trunc(np.log2(gain)) - trim_bits
        log = np.clip((np.ceil(np.log2(np.median(gain, axis = 1)))), 0, 31) - trim_bits
        print('log', log)

        # Calculate the median of log gains for each pol. Refactor these "med" log gains
        # into a new array, where each bin has the same med log gain for each pol.
        # med_log = np.median(log, axis = 1)
        # med_log_repeat = np.repeat(med_log.reshape(8, 1), 8192, axis = 1)
        # med_log = [int(n) for n in med_log] # recast to list of int to pass to SHIFT_LEFT
        # print(med_log)

        # Subtract the median logs from  log2(gain), and convert them to linear gains: 
        lin = gain / 2**np.repeat(log.reshape(8, 1), 8192, axis = 1) #med_log_repeat))
        # == copy from calculate_gains.py
        # lin[bad_values] = 2**15 - 1  # Set a high gain for the saturated gains 
        # # saturate gains that are getting too close to the maximum range
        # lin[lin > 2**14] = 2**15
        print('lin before np.int16', lin)
        lin = lin.astype(np.int16) # check trunc/round

        print('lin after np.int16', lin)

        print('Number of zeros after int16', len(np.where(lin < 0)[0]))
        # lin[lin < 0] = 1
        # assert(len(np.where(lin < 0)[0]) == 0)

        # Write and apply the lin/log gains to the SCALERs
        # log = log.astype(int)
        self.set_gains(lin, [int(n) for n in log]) # cast log gains to int

        # Capture SCALER data and check that they are at or near the target
        scaler_data = self.read_scaler_frames(1)

        # Save gains, calling save_gains()
        print('Saving gains')
        self.save_gains(lin,
                        log)

        return fft_data, fft_rms, gain, log, lin, scaler_data 
                      
    def save_gains(self, 
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
        
        log_gain_dset = f.create_dataset('log', 
                                         (self.NPOLS,),
                                         data = log_gain,
                                         dtype = np.int8) # type might be 'int', but small enough that 8 bits is plenty (max log gain is 31)
        
        f.close()
        
        return # nothing
    
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
                n_vis_per_file = 100,
                integration_time = 10,
                ):

        """
        Runs overnight acquisitions, handling data capture and file writing.
        
        Parameters
        ----------

        integrations_per_file (int)
            Number of integrations of length integrations_per_file to save per hdf5 file.

        integrations_per_file (float)
            Total time of firmware & software integration.

        Returns
        -------
        

        """

        # ===========
        # Start by computing gains.

        print('===================================')
        print('')
        print('--- C O M P U T E  G A I N S  ---')
        print('')
        self.compute_gains(number_of_fft_averages = 100)
        print('Gain computation completed!')
        print('')
        print('===================================')

        # ===========
        # Configure the channelizer and correlator. This is done after gain
        # computation because the compute gains algorithm changes the 
        # configuration.

        print('Configuring firmware')

        # Set up the channelizer. Input data should be coming
        # from the ADC, and nothing should be bypassed.
        self.i.set_channelizer(data_source = 'adc', 
                               fft_bypass = 0, 
                               scaler_bypass = 0
                               )

        # Configure correlator
        self.ucap.OUTPUT_SOURCE_SEL = 1 # u.OUTPUT_SOURCE_SEL = 0 --> raw data, u.OUTPUT_SOURCE_SEL = 1 --> correlator data
        self.corr = self.i.CORR # corr object
        self.corr_receiver = self.i.get_corr_receiver() # corr receiver object
        self.corr.AUTOCORR_ONLY = 0 # 0: all products
        self.corr.NO_ACCUM = 0 # 0: do accumulate
        self.NCORR_PROD = int(self.NPOLS*(self.NPOLS + 1) // 2)

        # Generate product array
        prod_idx = np.triu_indices(8)
        prod = np.zeros((len(prod_idx[0]), 2))
        for n in range(prod.shape[0]):
            prod[n] = (prod_idx[0][n], prod_idx[1][n])
        prod = prod.astype(np.int16)

        # ===========
        # CAPTURE AND WRITE DATA

        print('')
        print('')
        print('===================================')
        print('')
        print('--- O B S E R V E  ---')
        print('')

        # Run data capture until keyboard interrupt
        file_number = 0 # starting hdf5 file number

        # Calculate how many frames we need for 10s of integration time

        s_per_frame = 2**14*(1/3e9) # samples/frame * seconds/sample
        set_integration_time = 10 # s
        n_frames = int(set_integration_time / s_per_frame)
        actual_integration_time = n_frames * s_per_frame
        # print(n_frames, actual_integration_time)

        try:
            while True:

                # Create file
                file_name = f'{self.vis_dir_name}/{file_number}.hdf5'
                print(f'Creating new data file \'{file_name}\'')
                f = h5py.File(file_name, 'w')

                # Create data sets
                dset_vis    = f.create_dataset('vis', (n_vis_per_file, self.NBINS, self.NCORR_PROD), dtype = np.complex128) # Create vis dataset
                dset_counts = f.create_dataset('counts', (n_vis_per_file, self.NBINS), dtype = np.uint32) # Create counts dataset
                dset_sat    = f.create_dataset('sat', (n_vis_per_file, self.NBINS, self.NCORR_PROD), dtype = np.complex64) # Create vis dataset

                # Make index map group
                grp = f.create_group('index_map')
                dset_freq = grp.create_dataset('freq', (self.NBINS), dtype = np.float64)
                dset_prod = grp.create_dataset('prod', (self.NCORR_PROD, 2), dtype = np.int16)
                dset_time = grp.create_dataset('time', (n_vis_per_file), dtype = np.float64)

                dset_freq = self.f
                dset_prod = prod

                for n in range(n_vis_per_file):

                    print('')
                    print('+++++++++++++++++++++++++++++++++')
                    print(f'Capture {n} for file {file_name}')

                    # Not very pythonic, but flush on first capture
                    if n == 0:
                        flush = True
                    else:
                        flush = False

                    t_stamp, d, count, sat = self.read_corr_frames(soft_integ_period = n_frames,
                                                                   number_of_results = 1,
                                                                   filename = None,
                                                                   flush = flush,
                                                                   align = False,
                                                                   data_timeout = 0.001,
                                                                   flush_timeout = 0.001,
                                                                   return_format = 'raw',
                                                                   verbose = 0
                                                                   )

                    dset_time[n]     = t_stamp
                    dset_vis[n, ...] = d[0] # d is a 3D array even if we only request 1 result
                    dset_counts[n]   = count[0] # counts is 2D, but 0 axis has length of just 1
                    dset_sat[n, ...] = sat

                # Close file
                print(f'Closing file {file_name}')
                f.close() 

                # Increment file number
                file_number += 1

        except KeyboardInterrupt:
            print('Ending acquisition.')

        return

# Initialize corr capture class
ccc = CRS_CORR_CAPTURE()
ccc.observe(n_vis_per_file = 5, integration_time = 10)

# fft_data, fft_rms, gain, log, lin, scaler_data  = ccc.compute_gains(50)