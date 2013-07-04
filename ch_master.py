#/usr/bin/python

"""
Master control program for CHIME.
#
History:
2013-05-13 ADH: First version.
"""

from chrx import chrx
from pychime.core import chFPGA_controller
from configobj import *
from ch_conf import conf_dict
from validate import Validator
import argparse
import getpass
import numpy as np
import time

# Swop this out if the FMC serial number changes.
#ADC_DELAY_TABLE = ADC_DELAYS_REV2_SN0001_KC705_FMC700

if __name__ == "__main__":
  # Get command line arguments.
  parser = argparse.ArgumentParser(description = __doc__.split('\n')[0])
  parser.add_argument("-m", "--message", required = True, \
                      help = "Additional message to write to data header, " +\
                             "quotes (\"example message\")")
  parser.add_argument("-c", "--conf_file", action = "store", \
                      default = "ch_master.conf", \
                      help = "Configuration file.")
  parser.add_argument("-s", "--spec_file", action = "store", \
                      default = "ch_master.spec", \
                      help = "Configuration file specifications.")
  args = parser.parse_args()

  val_conf = Validator()
  conf = ConfigObj(args.conf_file, configspec = args.spec_file)
  ret = conf.validate(val_conf, preserve_errors = True)

  if ret != True:
    for entry in flatten_errors(conf, ret):
      sec_list, key, error = entry
      if key is not None:
        sec_list.append(key)
      else:
        sec_list.append("[missing section]")
      sec_string = ".".join(sec_list)
      if error == False:
        error = "Missing value or section."
      print "Error parsing %s: %s" % (sec_string, error)
    exit()
        
  print "Sampling frequency is %0.3f MHz." % float(conf["fpga"]["samp_freq"])

  # Build up the adc_delay_table.
  n = int(conf["n_antenna"])
  adc_delay = []
  for i in range(n):
    name = "ch%02d" % i
    tmp_delay = []
    if not name in conf["fpga"]["adc_delay"]:
      print "Could not find fpga.adc_delay.%s entry in configuration file." % \
            (name)
      exit()
    else:
      this_chan = conf["fpga"]["adc_delay"][name]
    for j in range(len(this_chan)):
      k = int(this_chan[j])
      tmp_delay.append(k)
    if len(tmp_delay) != 8:
      print "Entry fpga.adc_delay.%s needs eight integer entries." % (name)
      exit()
    adc_delay.append(tmp_delay)

  # Create the acquisition object. Pass it the configuration settings so that it
  # can initialise.
  print conf
  acq = chrx.acq(conf)

  # Create the FPGA controller object.
  fpga = chFPGA_controller.chFPGA_controller( \
             ip_address = conf["fpga"]["ip_address"], \
             port_number = conf["fpga"]["port"], \
             adc_delay_table = adc_delay, \
             init = 1, \
             sampling_frequency = conf["fpga"]["samp_freq"] * 1e6, \
             reference_frequency = conf["fpga"]["ref_freq"])

  # Set FPGA controller parameters.
  all_chan = range(conf["n_antenna"])
  fpga.set_data_source("adc") # This should come first.
  fpga.set_FFT_bypass(False, channels = all_chan)
  fpga.set_FFT_shift(conf["fpga"]["fft_shift"], channels = all_chan)
  fpga.set_gain(conf["fpga"]["log2_gain"], channels = all_chan)

  #Make sure FPGA throttling is fast enough to send all the data
  #FPGA doesn't seem to change this without a reset...
  #read_rate = int(np.floor(np.log2(conf["fpga"]["int_period"] * 4 * 125e6 / \
  #                2 / (conf["n_antenna"] * (conf["n_antenna"] + 1)))))
  #fpga.GPIO.HOST_FRAME_READ_RATE = read_rate

  # Pass FPGA configuration variables to header.
  fpga_conf = vars(fpga.get_config())
  for name in fpga_conf:
    val = fpga_conf[name]

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
  fpga.start_corr_capture(integration_period = conf["fpga"]["int_period"])
  print "Correlator started with an integration time of %.1f s" % \
        (conf["fpga"]["int_period"])

  # Start the acquisition.
  acq.start()

  try:
    while True:
      # Pass the acquisition object the board temperatures.
      acq.pass_fpga_amb_temp(0, fpga.ADC_BOARD.AmbTemp.get_temperature())
      time.sleep(1.0)
    acq.stop()
  except(KeyboardInterrupt, SystemExit):
    acq.stop()
