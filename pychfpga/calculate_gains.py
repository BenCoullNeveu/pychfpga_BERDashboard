#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
calculate_gains.py script
 computes and sets ideal gain for 4bit gaussian noise.



#
History:
    2011-08-14 JFC: Created from chFPGA, which now only contains top test code.
    2011-09-09 JFC: Added global FREF
    2011-10-11 JFC: Updated delay tables
    2014-02-21 KMB: Created from top test
"""
# import logging
import argparse
import time
import pickle
import os

# from pychfpga.core import chFPGA_controller
#from pychfpga.core import chFPGA_receiver
# from pychfpga.core.icecore import async, async_moment, async_sleep
# from timestream_receiver import get_frame

import numpy as np


class GainCalc(object):

    # States
    SET_GAINS = 'set_gains'  # call get_gains() and set the gains of the fpga to the specified values
    SEND_DATA = 'send_data' # call process_data() with a new set of data that has the new gains
    DONE = 'done'
    NBINS = 1024

    def __init__(self, stream_ids):
        """ Computes the frequency-dependent digital gains of the specified
            channels to bring the signals within the target RMS values across
            the band.

        Parameters:

            stream_ids (list of int): list of stream_ids that identify the
                channels for whish we wish to
        """

        self.stream_ids = stream_ids
        self.stream_id_to_index_map = {sid:index for index, sid in enumerate(self.stream_ids)}
        self.nchan = len(self.stream_ids)
        self.n_rms_iterations = 3
        self.n_rms_samples = 100
        # Set initial default gains of (glin, glog) = (1, 22)
        # We will start converging towards the final value from there
        self.default_glog = 22
        self.default_glin = 1.0
        #for 4 bit number *sqrt2 since real and imag, check this
        self.ideal_rms = 1.5 * np.sqrt(2) #2.83 is 1.5bits  1.5 is 0.6bits

        # Buffer in which we'll accumulate the incoming data
        self.data = np.zeros((self.nchan, self.NBINS), dtype=np.float32) # We store  abs(x)**2
        self.temp_gains = np.zeros((self.nchan, self.NBINS), dtype=np.float32)  # temp buffer

        self.glin = np.ones((self.nchan, self.NBINS), dtype=np.int16) * self.default_glin
        self.glog = np.ones((self.nchan), dtype=np.int8) * self.default_glog
        # self.state = self.SET_GAINS

        # useful constants
        # channels = range(16)

        # RMS averaging
        # keep track of the iteration number
        self.frame_count = np.zeros((self.nchan), dtype=np.int8)
        self.rms_iteration_number = np.zeros((self.nchan ), dtype=np.int8)
        self.done = np.zeros((self.nchan), dtype=np.int8)
    def get_gains(self):
        """
        """
        return self.stream_ids, self.glin, self.glog


    def process_data(self, stream_ids, data):
        """ Process incoming data, and return gains that need to be applied to the pipleine as the algorithm converges.


        Parameters:

            stream_ids (ndarray): list of integer stream ids that uniquely identify each channel.

            data (ndarray): array of complex data .

        Returns:

            (stream_ids, glin, glog, done): Gains (glin, glog) that need to be
            set on the specified stream_ids before new data is sent form those
            channels. `done` is a vector that indicates if the stream_id gain
            computation is complete, in which case the specified gain is the
            final solution.

        """

        ######################
        # Phase 1: iteratively converge the gain until we reach the target RMS
        ######################
        # Accumulate square of FFT values
        ix = np.array([self.stream_id_to_index_map[sid] for sid in stream_ids if not self.done[self.stream_id_to_index_map[sid]]])
        # self.rms_done
        self.data[ix] += np.abs(data) ** 2
        self.frame_count[ix] += 1

        # Find which channels have accumulated 100 frames and compute new gains for those
        # return ix, self.frame_count
        ix_frame_done = ix[self.frame_count[ix] == self.n_rms_samples]
        if ix_frame_done.size:
            print 'Computing gain for %i channels from %i RMS samples' % (ix_frame_done.size, self.n_rms_samples)
            self.data[ix_frame_done] = np.sqrt(self.data[ix_frame_done] / self.frame_count[ix_frame_done, None])
            # Scale the current gain to the value that would get us the target RMS
            # new_gain = ideal_rms / (data / current_gain)

            self.temp_gains[ix_frame_done] = self.glin[ix_frame_done] * (2.**self.glog[ix_frame_done, None])  # 2 has to be a float, otherwise it returns the ** result as int8
            # return self.temp_gains[ix_frame_done]
            self.temp_gains[ix_frame_done] *= 0.8 + (0.2 * self.ideal_rms / self.data[ix_frame_done])  #  g[j].shape=(1024)    idealRMS*glin*(2**(glog-4))/outrms

            # # but we want to slowly ease into that gain, so just take 20% of thhat target and 80% of the old gain
            # self.temp_gains[ix_frame_done][...] = (20.0 * target_gains + 80.0 * self.temp_gains[ix_frame_done]) / 100.0
            # Convert linear gain into (glin, glog) values
            self.glin[ix_frame_done], self.glog[ix_frame_done] = self.calc_gains(self.temp_gains[ix_frame_done])  # glin.shape=(16,1024), glog.shape=(16)
            # self.gains_ready[ix_frame_done] = 1
            # prepare for the next RMS round
            self.data[ix_frame_done] = 0 # restart a new integration
            self.frame_count[ix_frame_done] = 0
            self.rms_iteration_number [ix_frame_done] += 1
            # return self.glin[ix_frame_done], self.glog[ix_frame_done]
            print self.rms_iteration_number [ix_frame_done]

            # #####################################
            # Phase 2: Compute gains without RFI spikes
            # #####################################
            # Find which  channels have completed their i8 gain update iterations and compute the final filtered gain for those
            ix_rms_done = ix[self.rms_iteration_number [ix_frame_done] == self.n_rms_iterations]
            if ix_rms_done.size:
                # We start with gain, which is set in the set_gain() format [(ch,(glin, glog),...]
                self.glin[ix_rms_done], self.mask[ix_rms_done] = self.filter(self.glin[ix_rms_done])

                self.done[ix_rms_done] = True
                print 'Finished %i channels' % ix_rms_done.size
        return



    def calc_gains(self, g, target_glin=2**13):
        """ Convert an array of linear gain into a (glin, glog) gain format.

        Parameters:

            g:  is a linear global complex gain array, with the last dimension corresponding to the frequency bin axis.

        Returns:

            (glin, glog):

                - `glin` is an array with the same shape than `g`, containing complex gains that are around 2**13.

                - `glog` is an array with one less dimension than 'g', and contain a power-of-two scaling factor that is needed to express the target gain `g` such as g = glin* 2**glog.


        The maximum ``glin`` positive gain values is (2**15 - 1) (int16). We
        normalize the gain to aim for a median gain of 2**13 so we have the
        maximum resolution (13 bits) in the gain value but still keep a dynamic
        range headroom of about 4.


        #2**14 is max for linear gain
        #ignore dc component
        #check for nans

        benchmark:
            2019-03-29: 776 ms on TP520 with gains(2048, 1024). original version

        """
        #print g

        # Eliminate gains that would be too high from the computations by creating
        # a masked array
        bad_values = (g > 2**31) | ~ np.isfinite(g)
        g = np.ma.array(g, mask=bad_values)

        # ############
        # Compute glog
        # ############
        # np.abs(g) / 2**13 is the postscaler gain that needs to be applied to have glin be 2**13
        #
        # we take the median of that postscaler across all frequencies (the last
        # domension of `g`) to be less sensitive to outliers, and take the log2 of
        # it, which is rounded up so we keep our headroom of at least 4.
        #
        # glog has one less dimension than `g`.
        glog = (np.ceil(np.log2(np.ma.median(np.abs(g) / target_glin , axis=-1)))).astype(np.int)
        # ma.median will result in a masked value if all elements are masked. In
        # these cases, give to glog the the median glog from all channels
        # (hopefully there is at lease one good glog) .
        #
        # glog will also be masked if log2 is invalid (zero or negative gain)
        glog[glog.mask] = np.ma.median(glog)

        # ############
        # Compute glin
        # ############

        glin = g / (2.**glog[..., None])  # glog is broadcasted along the last dimension of g.
        glin[bad_values] = 2**14 # Set a high gain the saturated gains (should probably be 2**15-1)
        # saturate gains that are getting too close to the maximum range
        glin[glin > 2**14] = 2**14
        # truncate to integer, and convert to complex (necessary?)
        # np.floor(glin, out=glin)
        #glin = glin.astype(np.int).astype(np.complex)

        return glin, glog

    def filter(self, signal, filtertype='hybrid', num_components=50, zero=False):
        """ Create a filtered version of a signal that excludes spikes.

        Parameters:

            signal (ndarray): signal to filter across the last dimension.

            filtertype (str): type of filtering.

                - 'fourier' : Applies low pass filter, with a bandpass
                  frequency of `num_components` frequency samples.

                - 'poly' : Use an iteratively higher order polynomial fit to
                  mark outliers and generate a smoothed version of the signal.

                - 'hybrid': Applies both the 'poly' and 'fourier' filter, in
                  that order

            num_components (int): Bandpass of the Fourier low pass filter,
                expressed in number of frequency samples

            zero: if True, spoked identified by the 'poly' filter are zeroed out.
        """
        signal = np.array(signal)
        # mask = np.ma.make_mask_none((len(signal),))
        #The first bin is always bad for some reason
        # mask[0] = True
        # self.masked = np.ma.array(np.log(signal), mask=mask)


        if filtertype == 'fourier':
            filtered_signal = self.fourier_filter(signal, num_components)
            mask = None
        elif filtertype == 'poly' or filtertype == 'hybrid':
            filtered_signal, mask = self.iterative_poly_filter(signal)
            if filtertype == 'hybrid':
                # Take a copy of the signal and replacce the values that were masked due to RFU by interpolated values
                in_arr = signal.copy()
                in_arr[mask] = filtered_signal[mask]
                # Apply fourir filter
                filtered_signal = self.fourier_filter(in_arr, num_components)
            if zero:
                filtered_signal[mask] = 0
            else:
                filtered_signal[mask] = signal[mask]
        else:
            raise ValueError
        filtered_signal = (filtered_signal.real).astype(np.int).astype(np.complex)
        return filtered_signal, mask



    def fourier_filter(self, signal, num_components):
        """ Apply an ideal low-pass filter in the Fourier domain across the last dimension.

        The signal is padded on each end with mirror of itself to improve edge behavior.


        Parameters:

            signal (ndarray): signal(s) to filter. The array can contain any dimensions. Filtering is done on each signal individually across the last dimension.

        Should extend to other windows.
        not assured to maintain signal size
        """
        signal = np.array(signal)
        signal_length = signal.shape[-1] # take the last dimension
        # Pad. If we represent the signal by 0123, we build the array 21+0123+ 3
        padded_signal = np.concatenate((signal[..., signal_length/2:0:-1], signal, signal[..., -1:-signal_length/2:-1]), axis = -1)
        f_signal = np.fft.fft(padded_signal)
        # We eliminate all high frequency beyond num_components
        f_signal[..., num_components:-num_components] = 0
        filtered = np.fft.ifft(f_signal)[..., signal_length/2:-signal_length/2+1]
        filtered = (filtered.real).astype(np.int).astype(np.complex)
        return filtered

    def flag_rfi(self, signal, filtered_signal, threshold):
        """
        Set the mask flag of the element of `signal` that deviate from `filtered_signal` by a factor that exceeds `threshold`.

        Parameters:

            signal (numpy.MaskedArray): Signal to mask

            filtered_signal (ndarray): Smoothed out version of signal.

            threshold (float): threshold for flagging the data points as bad

        Returns:

             None, but the mask of the masked array `signal` is modified in-place.
        """
        rfmask = abs(signal) < abs(filtered_signal / threshold)
        signal.mask = rfmask|signal.mask

    def poly_filter(self, signal, threshold, degree):
        """ Filters signal using a polynomial fit across the last dimension of
        the array, ignoring masked values, AND masks values of  `signal` that
        deviate too much from its filtered version

        Parameters:

            signal (MaskedArray): 2D masked array. Fit is perforemed across the last dimension

            threshold (float): Threshold used to flag `signal` data

            degree (int): degree of the polynomial fit


        Returns:

            (ndarray): filtered signal. `signal` mask is modified in-place.
        """
        #
        x = np.arange(signal.shape[-1])
        filtered_signal = np.empty(signal.shape)

        # Unfortunately, ma.polyfit() does not treat the masks of each
        # seriesin a 2D array individually. It somehow combines them, which is
        # useless to us. So we need to process the data line by line.
        for i in signal.shape[0]:
            fit_coeff = np.ma.polyfit(x, signal, degree)  # ma.polyfit does not use masked data points in signal to compute the polynomial coefficients
            filtered_signal[i, :] = np.poly1d(fit_coeff)(x)
        self.flag_rfi(signal, filtered_signal, threshold)
        return filtered_signal

    def iterative_poly_filter(self, signal):
        """ Compute a filtered version `signal` using iteratively more refined
        polynomial fits and also return a array that indicate which of
        'signal' data points deviate too much from its filtered verison.


        A polynomial fit of increasing order is iteratively fitted to the
        signal. At each iteration, part of the signal that exceed the fit by a threshold factor are masked in `signal`. More and more of `signal`
        gets flagged by each iteration. The final polynomial fitted signal and
        the final mask are then returned.

        Parameters:

            signal (ndarray): 2D array of signals to process. Filtering is done across the second dimension.

        Returns:

            (filtered_signal, mask) tuple, where:

                - filtered_signal  (ndarray): filtered version of `signal`. The array has the same dimension as `signal`

                - mask (ndarray) : array of booleans indicating whether
                  `signal` samples have deviated too much from the filtered
                  version during the iterative filtering process.
        """
        #The first bin is always bad for some reason
        degree = 1
        threshold = 1.2
        masked_signal = np.ma.array(np.log(signal), mask=np.zeros(signal.shape))
        masked_signal.mask[..., 0] = 0  # the first bin is always bad (JFC probably because of DC component in bin 0)
        filtered_signal = np.empty(signal.shape)
        while threshold > 1.01:
            filtered_signal[...] = self.poly_filter(masked_signal, threshold, degree)  # this masked_signal mask is modified to remove RFI
            threshold = 1 + (threshold - 1)*0.8
            if degree < 15:
                degree += 2
        np.exp(filtered_signal, out=filtered_signal)
        np.floor(filtered_signal, out=filtered_signal)
        # filtered_signal = (filtered.real).astype(np.int).astype(np.complex)
        return filtered_signal, masked_signal.mask



def get_frames(port):
    """
    Returns:
        Numpy array, dtype=complex, shape=(100,16,1024) containing FFT data for 100 channelizer frames (16 channel each)
    """

    chanIndex = np.arange(16)
    channels = np.arange(16)
    number_of_frames = 0
    frames = 100
    data_list = np.zeros((frames, 16, 2048))
    while number_of_frames < frames:
        try:
            a = get_frame(port)
            data_list[number_of_frames, :, :] = a.values()[0]
            #for chanNum in chanIndex:
            #    data_list[number_of_frames,chanNum, :] = a[channels[chanNum]]
            number_of_frames += 1
        except KeyError:
            pass
            print "missed some data..."
    #data_list = data_list.astype(np.int8)
    #data_list ^= np.int8(128)
    #data_list /= 2**4
    data_list = (data_list.astype(np.int8) ^ np.int8(128)) >> 4
    #data_list = (np.bitwise_xor(data_list.astype(np.int8), 128*np.ones(data_list.shape, dtype=np.int8)).astype(np.int8))/2**4 #data_list/2**4
    data = data_list[:,:,::2] + 1.0j*data_list[:,:,1::2]
    return data



# @async
def calculate_gains(c, gain_folder='/home/chime/ch_acq/gains'):
    '''Calculate digital gains for all the inputs of an iceboard c
    '''
    slot_0based = c.slot - 1 if c.slot else 0
    crate = c.crate.crate_number if c.crate and c.crate.crate_number is not None else 0
    print 'Calculating digital gains for crate %02i slot %02i (FCC%02i%02i)' % (crate, slot_0based, crate, slot_0based)


    # Get current state. Assumes all inputs have the same state
    data_source = c.get_data_source()[0]
    adc_mode = c.get_adc_mode()
    fft_bypass = c.get_fft_bypass()[0]
    fft_shift = c.get_fft_shift()[0]
    scaler_bypass = c.get_scaler_bypass()[0]
    local_data_port_number = c.get_local_data_port_number()

    # Configure channelizer
    # FFT enabled
    c.set_data_source('adc')
    c.set_adc_mode('data')
    c.set_fft_bypass(0)
    c.set_fft_shift(1367)
    c.set_scaler_bypass(0)
    #c.set_send_flags()
    c.set_offset_binary_encoding()

    # Set initial default gains of (glin, glog) = (1, 22)
    # We will start converging towards the final value from there
    default_log2_gain = 22
    c.set_gains((1, default_log2_gain))  # startup gain is (1, 22)
    #c.set_local_data_port_number(int(port))
    temp_gains = np.ones(16, 1024) *  2**default_log2_gain


    # Start capturing FFT data
    port = 42500 # Picked randomly. Hack
    c.set_local_data_port_number(port)
    c.start_data_capture(burst_period_in_seconds=0.001) # default source = 'scaler' (i.e FFT data after scaler)
    c.sync()



    # Save the cleaned-up gains
    output = open(os.path.join(gain_folder, 'gains_FCC%02i%02i.pkl' % (crate, slot_0based)),'wb')
    pickle.dump(gain, output)
    output.close()
    print "Scaler Gain set and saved"


    # restore normal iceboard operation
    c.stop_data_capture()
    # restore iceboard state
    c.set_data_source(data_source)
    c.set_adc_mode(adc_mode)
    c.set_fft_bypass(fft_bypass)
    c.set_fft_shift(fft_shift)
    c.set_scaler_bypass(scaler_bypass)
    c.set_local_data_port_number(local_data_port_number)


def unused():
        # Compute RMS value across the 100 frames
        # We are computing the RMS of a series FFT frequency samples, *not* the RMS of a timestream. ``std`` is defined as::
        #
        #     std = sqrt(mean(abs(x - x.mean())**2))
        #
        # where x.mean() tends toward
        # zero because the noise or RFI is uncorrelated with the frame rate.
        # This means this is roughly equivalent to::
        #
        #     std = sqrt(mean(abs(x)**2))
        #
        # where ``abs(x)**2`` is the power in that bin, so we end up computing the average power with all bins of the same frequency.
        measured_rms = data[:, :, :].std(axis=0) # shape=(16, 1024) std for each (chan, bin) across 100 samples
        measured_rms[measured_rms < 0.8] = 0.8  # low-saturate rms to 0.8
        # rmss.append(outrms.mean())
        print measured_rms.mean(axis=1) # show average RMS across all channels for all bins
        # if i == 0: # initial gain
        #     g = ideal_rms * 2**(default_log2_gain) / measured_rms  #shape=(16, 1024)   ideal_rms*2**(default_log2_gain-4)/measured_rms
        # else:
        #     for j, glog1 in enumerate(glog):
        #         # compute the digital gain that would get us to the target RMS
        #         # new_gain = ideal_rms / (data / current_gain)
        #         target_gains[j] = ideal_rms * temp_gains[j] / measured_rms[j]  #  g[j].shape=(1024)    ideal_rms*glin*(2**(glog-4))/measured_rms
        #         # but we want to slowly ease into that gain, so just take 20% of thhat target and 80% of the old gain

        #         new_gains[j] = (20.0 * g[j] + 80.0 * temp_gains[j]) / 100.0


        # Save the gains. These were converged to using median values, and they contain outliers due to RFI
        out1 = open(os.path.join(gain_folder, 'gains_noisy_FCC%02i%02i.pkl' % (crate, slot_0based)), 'wb')
        pickle.dump(gain, out1)
        out1.close()