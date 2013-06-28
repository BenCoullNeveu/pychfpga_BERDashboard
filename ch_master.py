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
import getpass
import numpy as np
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
  parser.add_argument("-m", "--message", required = True, \
                      help = "Additional message to write to data header, " +\
                             "quotes (\"example message\")")
  parser.add_argument("-f", "--samp_freq", action = "store", type = float, \
                      default = 800, \
                      help = "Sampling frequency of the ADC in MHz.")
  args = parser.parse_args()

  print "Sampling frequency is %0.3f MHz." % args.samp_freq

  # Create the FPGA controller object.
  fpga = chFPGA_controller.chFPGA_controller(ip_address = "10.10.10.11", \
             port_number = 41000, adc_delay_table = ADC_DELAY_TABLE, init = 1, \
             sampling_frequency = args.samp_freq * 1e6, \
             reference_frequency = 10e6) # pylint: disable=C0103

  # Set FPGA controller parameters.
  all_chan = range(8)
  Nant = 8
  int_period = 0.25
  fpga.set_data_source("adc") # This should come first.
  fpga.set_FFT_bypass(False, channels = all_chan)
  fpga.set_FFT_shift(fft_shift = 2**5 - 1, channels = all_chan)
  fpga.set_gain(log2_gain = 1, channels = all_chan)
  #Make sure FPGA throttling is fast enough to send all the data
  #FPGA doesn't seem to change this without a reset...
  #read_rate = int(np.floor(np.log2(int_period*4*125e6/2/(Nant*(Nant+1)))))
  #fpga.GPIO.HOST_FRAME_READ_RATE = read_rate

  # Create the acquisition object.
  acq = chrx.acq()

  # Pass FPGA configuration variables to header.
  config = vars(fpga.get_config())
  for name in config:
    val = config[name]

    # Do the annoying conversion of numpy types to native Python types. Sigh.
    if isinstance(val, (list, tuple)):
      if isinstance(val[0], (list, tuple)):
        val = reduce(lambda a, b: a + b, val)
      if not isinstance(val[0], str):
        try:
          if val[0].dtype.kind in ('i', 'u', 'f'):
            val = list(np.asscalar(x) for x in val)
        except:
          if type(val[0]) == bool:
            val = list(int(x) for x in val)
          else:
            val = list(x for x in val)
    else:
      if not isinstance(val, str):
        try:
          if val.dtype.kind in ('i', 'u', 'f'):
            val = np.asscalar(val)
        except:
          a = 1  # Placeholder.

    # Now send FPGA information send to acquisition object's header.
    acq.add_header_item(name, val)

  # Add some more stuff to the header.
  acq.add_header_item("run_message", args.message)
  acq.add_header_item("system_user", getpass.getuser())

  # Start the correlator.
  fpga.start_corr_capture(integration_period = int_period)
  print "Correlator started with an integration time of %.1f s" % (int_period)

  # Start the acquisition.
  acq.start(port = 41001, samp_per_frame = 40, frame_per_file = 360)

  try:
    while True:
      # Pass the acquisition object the board temperatures.
      acq.pass_fpga_amb_temp(0, fpga.ADC_BOARD.AmbTemp.get_temperature())
      time.sleep(1.0)
    acq.stop()
  except(KeyboardInterrupt, SystemExit):
    acq.stop()
