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
this_node   = "mistaya"
this_group  = "collection_server"
basedir     = "/data/ahincks_test"
acq_fmt     = re.compile("[0-9]{8}T[0-9]{6}Z_[A-Za-z]*_[A-Za-z]*")
file_fmt    = re.compile("[0-9]{8}_[0-9]{4}.h5")
log_fmt     = re.compile("ch_master\.log")

def add_acq(name, allow_new_inst=True, allow_new_atype=False, comment=None):
    """Add an aquisition to the database.
    """
    ts, inst, atype = di.parse_acq_name(name)

    # Is the acquisition already in the database?
    if di.ArchiveAcq.select(di.ArchiveAcq.id).where(
                     di.ArchiveAcq.name == name).count():
        raise di.AlreadyExists("Acquisition \"%s\" already exists in DB." %
                               name)

    # Does the instrument already exist in the database?
    try:
        inst_rec = di.ArchiveInst.get(di.ArchiveInst.name == inst)
    except pw.DoesNotExist:
        if allow_new_inst:
            di.ArchiveInst.insert(name=inst).execute()
            logging.info("Added new acquisition instrument \"%s\" to DB." %
                         inst)
        else:
            raise di.DataBaseError("Acquisition instrument \"%s\" not in DB." %
                                   inst)

    # Does the archive type already exist in the database?
    try:
        atype_rec = di.AcqType.get(di.AcqType.name == atype)
    except pw.DoesNotExist:
        if allow_new_atype:
            di.AcqType.insert(name=atype).execute()
            logging.info("Added new acquisition type \"%s\" to DB." % atype)
        else:
            raise di.DataBaseError("Acquisition type \"%s\" not in DB." % atype)

    # Giddy up!
    return di.ArchiveAcq.create(name=name, inst=inst_rec, type=atype_rec,
                                comment=comment)

def get_acqcorrinfo_keywords_from_h5(path):
  f = h5py.File(path, "r")
  n_freq = f["/"].attrs["n_freq"][0]
  n_prod = len(f["/"].attrs["chan_indices"])
  integration = f["/"].attrs["acq.udp.spf"][0] * \
                f["/"].attrs["fpga.int_period"][0]
  f.close()
  return {"integration" : integration,
          "nfreq"       : n_freq,
          "nprod"       : n_prod}


def get_filecorrinfo_keywords_from_h5(path):
  f = h5py.File(path, "r")
  start_time = f["timestamp"][0][1] + f["timestamp"][0][2] * 1e-6
  finish_time = f["timestamp"][-1][1] + f["timestamp"][-1][2] * 1e-6
  chunk_number, freq_number = di.parse_corrfile_name(os.path.basename(path))
  f.close()
  return {"start_time"   : start_time,
          "finish_time"  : finish_time,
          "chunk_number" : chunk_number,
          "freq_number"  : freq_number}


if __name__ == "__main__":
  # Get the node and group.
  try:
    node = di.StorageNode.get(name=this_node)
  except:
    raise Exception("Node \"%s\" is not registered in the DB!" % this_node)
  if node.group.name != this_group:
     raise Exception("Group for node \"%s\" is \"%s\", but was expecting " \
                     "\"%s\"." % (node.name, node.group.name, this_group))

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
      log.debug("Acquisition \"%s\" already in DB. Skipping." % basename)
    except pw.DoesNotExist:
      acq = add_acq(basename)
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
        log.info("Skipping unrecognised file \"%s/%s\"." % (basename, f))
        continue

      # Make sure information about the acquisition exists in the DB.
      if not have_info:
        if atype == "corr" and ftype.name == "corr":
          di.CorrAcqInfo.create(acq=acq,
                                **get_acqcorrinfo_keywords_from_h5(fullpath))
          log.info("Added information for correlator acquisition \"%s\" to " \
                   "DB." % basename)
          have_info = True

      # Add the file, if necessary.
      try:
        file = di.ArchiveFile.get(di.ArchiveFile.name == f,
                                  di.ArchiveFile.acq == acq)
        log.debug("File \"%s/%s\" already in DB. Skipping." % (basename, f))
      except pw.DoesNotExist:
        md5sum = di.md5sum_file(fullpath)
        size_b = os.path.getsize(fullpath)
        file = di.ArchiveFile.create(acq=acq, type=ftype, name=f, size_b=size_b,
                                     md5sum = md5sum)
        log.info("File \"%s/%s\" added to DB." % (basename, f))

      # Register the copy of the file here on the collection server, if
      # necessary.
      if not file.copies.where(di.ArchiveFileCopy.node == node).count():
        copy = di.ArchiveFileCopy.create(file=file, node=node, has_file='Y',
                                         wants_file = False)
        log.info("Registered file copy \"%s/%s\" do DB." % (basename, f))

      # Make sure information about the file exists in the DB.
      if ftype.name == "corr":
        # Add if (1) there is no corrinfo or (2) the corrinfo is missing.
        if not file.corrinfos.count():
          do_add = True
        elif not file.corrinfos[0].start_time:
          do_add = True
        else:
          do_add = False

        if do_add:
          try:
            di.CorrFileInfo.create(file=file,
                            **get_filecorrinfo_keywords_from_h5(fullpath))
            log.info("Added information for file \"%s/%s\" to DB." %
                     (basename, f))
          except ValueError:
            if not file.corrinfos.count():
              di.CorrFileInfo.create(file=file)
            log.warning("Missing info for file \"%s/%s\": HDF5 datasets " \
                        "empty. Leaving fields NULL." % (basename, f))
