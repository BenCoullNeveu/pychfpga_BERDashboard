#/usr/bin/python

"""
Master control program for CHIME.
#
History:
2013-05-13 ADH: First version.
"""

from chrx import chrx
from pychime.core import chFPGA_controller
import argparse
import time

# First 8 values are the delays for bits 0 to 7; 8th value is the delay for the
# clock line.
ADC_DELAYS_REV2_SN0001 = (
  [20, 26, 25, 25, 25, 25, 25, 24], # Ch. 0
  [23, 23, 23, 23, 23, 23, 23, 23], # Ch. 1 
  [24, 22, 20, 20, 20, 20, 20, 17], # Ch. 2 
  [19, 19, 19, 19, 19, 19, 19, 19], # Ch. 3
  [17, 17, 17, 17, 17, 17, 17, 17], # Ch. 4
  [17, 17, 17, 17, 17, 17, 17, 17], # Ch. 5 
  [19, 19, 19, 18, 17, 16, 20, 20], # Ch. 6 
  [16, 16, 16, 16, 16, 16, 16, 16]  # Ch. 7
)

ADC_DELAYS_REV2_SN0001_KC705_FMC700 = (
  [13, 10,  9, 10,  9, 10,  9,  9], # Ch. 0
  [ 7,  7,  7,  7,  7,  7,  7,  7], # Ch. 1 
  [11, 11,  8,  9,  7,  8,  8,  7], # Ch. 2 
  [ 6,  6,  6,  6,  6,  6,  6,  6], # Ch. 3
  [14, 14, 14, 14, 14, 14, 14, 14], # Ch. 4
  [14, 14, 14, 14, 14, 14, 14, 14], # Ch. 5 
  [13, 13, 13, 13, 13, 13, 13, 13], # Ch. 6 
  [ 0,  0,  0,  0,  0,  0,  0,  0], # Ch. 7
)

# Swop this out if the FMC serial number changes.
ADC_DELAY_TABLE = ADC_DELAYS_REV2_SN0001_KC705_FMC700

if __name__ == "__main__":
  # Get command line arguments.
  parser = argparse.ArgumentParser(description = __doc__.split('\n')[0])
  parser.add_argument("-m", "--message", \
                      help = "Additional message to write to data header, " +\
                             "quotes (\"example message\")")
  parser.add_argument("-f", "--samp_freq", action = "store", type = float, \
                      default = 850, \
                      help = "Sampling frequency of the ADC in MHz.")
  args = parser.parse_args()

  print "Sampling frequency is %0.3f MHz." % args.samp_freq

  # Create the acquisition object.
  acq = chrx.acq()

  # Create the FPGA controller object.
  fpga = chFPGA_controller.chFPGA_controller(ip_address = "10.10.10.11", \
             port_number = 41000, adc_delay_table = ADC_DELAY_TABLE, init = 1, \
             sampling_frequency = args.samp_freq * 1e6, \
             reference_frequency = 10e6) # pylint: disable=C0103

  # Set FPGA controller parameters.
  all_chan = range(8)
  int_period = 1.0
  fpga.set_data_source("adc") # This should come first.
  fpga.set_FFT_bypass(False, channels = all_chan)
  fpga.set_FFT_shift(fft_shift = 2**5 - 1, channels = all_chan)
  fpga.set_gain(log2_gain = 1, channels = all_chan)

  # Start the correlator.
  fpga.start_corr_capture(integration_period = int_period)
  print "Correlator started with an integration time of %.1f s" % (int_period)

  # Start the acquisition.
  acq.start(41001)

  time.sleep(10)

  acq.stop()
