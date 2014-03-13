#!/usr/bin/python

"""
Master control program for CHIME.
#
History:
2013-05-13 ADH: First version.
"""

import chrx
from configobj import *
from pychfpga.core import chFPGA_controller
from validate import Validator
import argparse
import getpass
import logging
import numpy as np
import os
import sys
import time
#import MySQLdb

if __name__ == "__main__":
  # Set up logger.
  log = logging.getLogger("")
  log.setLevel(logging.DEBUG)
  log_stdout = logging.StreamHandler(sys.stdout)
  log_stdout.setLevel(logging.DEBUG)
  log_fmt = logging.Formatter("%(asctime)s %(levelname)s >> %(message)s", \
                              "%b %d %H:%M:%S")
  log_stdout.setFormatter(log_fmt)
  log.addHandler(log_stdout)

  #db = MySQLdb.connect(host = "142.103.235.202", user = "chime", \
  #                     passwd = "penticton", db = "ch_data")
  #dbc = db.cursor()

  # Get command line arguments.
  parser = argparse.ArgumentParser(description = __doc__.split('\n')[0])
  parser.add_argument("-g", "--git-tag", action = "store", \
                      default = "", help = "Git tag for current version.")
  parser.add_argument("-c", "--conf_file", action = "store", \
                      default = "ch_master.conf", \
                      help = "Configuration file.")
  parser.add_argument("-s", "--spec_file", action = "store", \
                      default = "ch_master.spec", \
                      help = "Configuration file specifications.")
  args = parser.parse_args()

  # Be paranoid: if the executable is being run from /usr/sbin we can be 
  # reasonably assured that the git tag recorded in /etc/CHIME is correct. If it
  # is not being run from there, force the user manually insert the git tag as 
  # an option.
  if sys.argv[0] != "/usr/sbin/ch_master.py":
    if not len(args.git_tag):
      print "If you are not running this as a daemon from \"/usr/sbin\", you "
      print "MUST use the -g option and manually specify which git tag you are "
      print "running (e.g., ./ch_master -g `git describe --tags`)."
      exit()

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
      log.critical("Error parsing %s: %s" % (sec_string, error))
    exit()

  # Create the output directory.
  time_str = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
  acq_base_dir = "%s/%s" % (conf["acq"]["base_path"], time_str)
  os.makedirs(acq_base_dir)
  if not os.path.exists(acq_base_dir):
    log.critical("Could not create directory \"%s\"." % (acq_base_dir))
    exit()

  # Create a symbolic link to the output directory.
  os.unlink(conf["acq"]["curfile"])
  os.symlink(acq_base_dir, conf["acq"]["curfile"])

  # Start writing to a log file in this directory.
  acq_log_path = "%s/%s.log" % (acq_base_dir, time_str)
  log_file = logging.FileHandler(acq_log_path)
  log_file.setLevel(logging.DEBUG)
  log_file.setFormatter(log_fmt)
  log.addHandler(log_file)
  log.info("Now logging to \"%s\"." % (acq_log_path))
        
  log.info("Sampling frequency is %0.3f MHz." % \
           float(conf["fpga"]["samp_freq"]))

  # Build up the adc_delay_table.
  n = int(conf["n_antenna"])
  adc_delay = []
  for i in range(n):
    name = "ch%02d" % i
    tmp_delay = []
    if not name in conf["fpga"]["adc_delay"]:
      log.critical("Could not find fpga.adc_delay.%s entry in configuration " \
                   "file." % (name))
      exit()
    else:
      this_chan = conf["fpga"]["adc_delay"][name]
    for j in range(len(this_chan)):
      k = int(this_chan[j])
      tmp_delay.append(k)
    if len(tmp_delay) != 16:
      log.critical("Entry fpga.adc_delay.%s needs 16 integer entries." % \
                   (name))
      exit()
    adc_delay.append((tmp_delay[:8],tmp_delay[8:]))

  # Create the acquisition object. Pass it the configuration settings so that it
  # can initialise.
  acq = chrx.acq(conf, log)

  # Create the FPGA controller object.
  fpga = chFPGA_controller.chFPGA_controller( \
             ip_address = conf["fpga"]["ip_address"], \
             port_number = conf["fpga"]["port"], \
             adc_delay_table = adc_delay, \
             verbose = 0, \
             init = 1, \
             sampling_frequency = conf["fpga"]["samp_freq"] * 1e6, \
             reference_frequency = conf["fpga"]["ref_freq"], \
             data_width=conf["fpga"]["data_width"], \
             group_frames=conf["fpga"]["group_frames"], \
             enable_gpu_link = conf["fpga"]["enable_gpu_link"], \
             host_ip = conf["fpga"]["host_ip"])

  # Set FPGA controller parameters.
  all_chan = range(conf["n_antenna"])
  fpga.set_data_source("adc") # This should come first.
  fpga.set_FFT_bypass(False, channels = all_chan)
  fpga.set_FFT_shift(conf["fpga"]["fft_shift"], channels = all_chan)
  fpga.set_gain((1,conf["fpga"]["gain"]), channels = all_chan)
  fpga.sync()
  fpga.set_send_flags()
  fpga.set_offset_binary_encoding()
  fpga.sync()
  #Make sure FPGA throttling is fast enough to send all the data
  #FPGA doesn't seem to change this without a reset...
  #read_rate = int(np.floor(np.log2(conf["fpga"]["int_period"] * 4 * 125e6 / \
  #                2 / (conf["n_antenna"] * (conf["n_antenna"] + 1)))))
  #fpga.GPIO.HOST_FRAME_READ_RATE = read_rate

  # Start the correlator.
  ##fpga.start_corr_capture(integration_period = conf["fpga"]["int_period"])
  #log.info("Correlator started with an integration time of %.1f s" % \
  #         (conf["fpga"]["int_period"]))

  # Pass FPGA configuration variables to header.
  fpga_conf = vars(fpga.get_config())
  for name in fpga_conf:
    if name == 'antenna_scaler_log2_gain':
      val = 27
    elif name == 'antenna_adc_data_acquisition_delay_tables':
      val = 42
    else:
      val = fpga_conf[name]

    # Do the annoying conversion of numpy types to native Python types. Sigh.
    if isinstance(val, (list, tuple)):
      if len(val) == 0:
       val = [0]
      if isinstance(val[0], (list, tuple)):
        val = [item for sublist in val for item in sublist] #reduce(lambda a, b: a + b, val)
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

  # Add the system user to the header, for kicks. (It should normally be root.)
  acq.add_header_item("system_user", getpass.getuser())

  # Get the git tag and write it to the header.
  if not len(args.git_tag):
    fp = open("/etc/CHIME/version", "r")
    if not fp:
      log.critical("Could not find git tag in \"/etc/CHIME/version\".")
      exit()
    tag = fp.read().replace("\n", "")
  else:
    tag = args.git_tag
  log.info("Git version is %s." % (tag))
  acq.add_header_item("git_version_tag", tag)

  # Start the acquisition.
  acq.start(acq_base_dir)

  # Push into the database.
#  dbc.execute("INSERT INTO archive (name) VALUES (\"%s\");" % (acq.full_path))
#  archive_id = db.insert_id()
#  dbc.execute("INSERT INTO config (comment) VALUES (\"%s\");" % (args.message));
#  config_id = db.insert_id()
#  dbc.execute("UPDATE archive SET config_id = %d WHERE id = %d;" % \
#              (config_id, archive_id))
#  db.commit()

  try:
    while True:
      # Pass the acquisition object the board temperatures. This is a temporary
      # way of doing this!
      acq.pass_fpga_amb_temp(0, fpga.SYSMON.temperature())
      time.sleep(1.0)
    acq.stop()
  except(KeyboardInterrupt, SystemExit):
    acq.stop()

log.info("Exiting ch_master now.")
