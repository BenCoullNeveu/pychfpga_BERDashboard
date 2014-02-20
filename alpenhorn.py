#!/usr/bin/python

import h5py
import logging

# Set up logger.
logging.basicConfig(level = logging.INFO)
log = logging.getLogger("")
log.setLevel(logging.INFO)

import os
import peewee as pw
import re
from ch_util import data_index as di

# Parameters.
basedir     = "/data/ahincks_test"
acq_fmt     = re.compile("[0-9]{8}T[0-9]{6}Z_[A-Za-z]*_[A-Za-z]*")
file_fmt    = re.compile("[0-9]{8}_[0-9]{4}.h5")
log_fmt     = re.compile("ch_master\.log")

def get_corrinfo_keywords_from_h5(path):
  f = h5py.File(path, "r")
  n_freq = f["/"].attrs["n_freq"][0]
  n_prod = len(f["/"].attrs["chan_indices"])
  integration = f["/"].attrs["acq.udp.spf"][0] * \
                f["/"].attrs["fpga.int_period"][0]
  f.close()
  return {"integration" : integration,
          "nfreq"       : n_freq,
          "nprod"       : n_prod}


if __name__ == "__main__":
  log.info("Crawling base directory \"%s\" for new files." % basedir)
  for path, d, f_list in os.walk(basedir):
    # Parse the path.
    basename = os.path.basename(path)
    try:
      ts, inst, atype = di.parse_acq_name(basename)
    except di.Validation:
      log.info("Skipping non-acquisition path %s." % basename)
      continue

    # Figure out which acquisition this is; add if necessary.
    try:
      acq = di.ArchiveAcq.get(di.ArchiveAcq.name == basename)
    except pw.DoesNotExist:
      acq = di.add_acq(basename)
      log.info("Acquisition \"%s\" added to DB." % basename)

    # If it is a correlator acquisition, see if the info has been added.
    have_info = True
    if atype == "corr":
      if not acq.corrinfos.count():
        have_info = False

    # Now go through all the files.
    for f in sorted(f_list):
      fullpath = "%s/%s/%s" % (basedir, basename, f)
      # What is it?
      ftype = di.detect_file_type(f)
      if ftype == None:
        log.info("Skipping unrecognised file %s/%s." % (basename, f))
        continue

      # Make sure information about the acquisition exists in the DB.
      if not have_info:
        if atype == "corr" and ftype.name == "corr":
          di.CorrAcqInfo.create(acq=acq,
                                **get_corrinfo_keywords_from_h5(fullpath))
          log.info("Added information for correlator acquisition \"%s\" to " \
                   "DB." % basename)
          have_info = True
