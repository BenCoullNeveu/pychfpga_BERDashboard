import os
import sys
import glob
import subprocess
import re

import datetime
import time
from calendar import timegm

import pickle
import h5py
import numpy as np

__version__ = '0.2'
ARCHIVE_VERSION = u'3.1.0'

class DigitalGainWriter(object):
    """ Interface to an HDF5 file containing digital gains.
    """

    _axes = {
        'freq':  {'dtype': [('centre', '<f8'), ('width', '<f8')]},
        'input': {'dtype': [('chan_id', 'u2'), ('correlator_input', 'S32')]},
    }

    _dataset_spec = {
        'compute_time': {
            'axes': ['input'],
            'dtype': np.float32,
        },
        'gain_coeff': {
            'axes': ['freq', 'input'],
            'dtype': np.complex64,
        },
        'gain_exp': {
            'axes': ['input'],
            'dtype': np.int32,
        }
    }

    _input_to_sma = [12, 13, 14, 15, 8, 9, 10, 11, 4, 5, 6, 7, 0, 1, 2, 3]

    def __init__(self, output_dir=None, output_suffix="digitalgain", instrument_name="chime", notes="",
                                        last_file=None, append=False, **kwargs):
        """ Instantiates a DigitalGainWriter object.  This will create a file on disk to hold the
        gains if not appending to existing file.

        Parameters
        ----------
        output_dir:  str
            Directory where the digital gain acquisitions will be saved.

        output_suffix: str
            Suffix appended to the acquisition name.  Default is 'digitalgain'.

        instrument_name:  str
            Name of the instrument/correlator.  Included in acquisition name,
            and also saved to file attributes.  Default is 'chime'.

        notes: str
            User notes that are saved to file attributes.

        last_file: list of file paths
            Read the gains from existing file.  If None will search output_dir
            for the most recent file.  Default is None.

        append: boolean
            Append to last file.  Default is False.

        """

        # Create dictionaries to hold attrs, index_map, and datasets
        self.attrs = {}
        self.index_map = {}
        self.datasets = {}

        # Set parameters that specify output file format
        self.output_dir = output_dir
        self.output_suffix = output_suffix

        # Check for
        if 'correlator' in kwargs:
            self.correlator = kwargs['correlator']
        elif instrument_name.lower() == 'pathfinder':
            self.correlator = 'K7BP16-0004'
        elif instrument_name.lower() == 'chime':
            self.correlator = 'FCC'
        else:
            self.correlator = None

        # Search the directory for any existing files
        if last_file is None:
            last_file = sorted(glob.glob(os.path.join(self.output_dir,
                              '*' + instrument_name + '_' + self.output_suffix, '*.h5')))
            last_file = last_file[-1] if last_file else None

        do_read = last_file is not None

        # Read gains from most recent file
        if do_read:
            self.read_hdf5(last_file)
        else:
            self.initialize(**kwargs)

        # Check if we are appending to an existing file
        if do_read and append:
            self.output_file = last_file

        else:
            # Set attributes
            self.set_attrs(**{'instrument_name':instrument_name, 'version':__version__, 'notes':notes,
                              'archive_version':ARCHIVE_VERSION})

            # Determine output filename
            self.output_file = self.get_output_file(**kwargs)

            # Create the file
            self.create_file()


    def initialize(self, **kwargs):

        for key, spec in self._axes.iteritems():
            self.index_map[key] = kwargs[key][:]

        for key, spec in self._dataset_spec.iteritems():
            shp = tuple([self.index_map[axis].size for axis in spec['axes']])
            self.datasets[key] = np.zeros(shp, dtype=spec['dtype'])


    def read_hdf5(self, filename):

        with h5py.File(filename, 'r') as handler:

            for key in self._axes.keys():
                self.index_map[key] = handler['index_map'][key][:]

            for key in self._dataset_spec.keys():
                self.datasets[key] = handler[key][:]

            for key, val in handler.attrs.iteritems():
                self.attrs[key] = val


    def read_pickle(self, files):

        for ff in sorted(files):

            mo = re.match('gains_%s(\d{2})(\d{2}).pkl' % self.correlator, os.path.basename(ff))
            crate = int(mo.group(1))
            slot = int(mo.group(2))

            with open(ff, 'r') as handler:
                all_gains = pickle.load(handler)

            this_calc_time = os.path.getmtime(ff)

            for ind, gains in all_gains:

                sn = '%s%02d%02d%02d' % (self.correlator, crate, slot, self._input_to_sma[ind])

                chan_id = self.correlator_input[sn]

                self.datasets['gain_coeff'][:, chan_id] = gains[0]
                self.datasets['gain_exp'][chan_id] = gains[1]
                self.datasets['compute_time'][chan_id] = this_calc_time


    def create_file(self):

        with h5py.File(self.output_file, 'w') as handler:

            # Set attributes
            for key, val in self.attrs.iteritems():
                handler.attrs[key] = val

            # Create index_map
            index_map = handler.create_group('index_map')
            for key, val in self.index_map.iteritems():
                index_map.create_dataset(key, data=val)

            # Create datasets
            for key, val in self.datasets.iteritems():
                dset = handler.create_dataset(key, data=val)
                dset.attrs['axis'] = self._dataset_spec[key]['axes']


    def write(self):

        with h5py.File(self.output_file, 'a') as handler:

            for key, val in self.datasets.iteritems():
                handler[key][:] = val


    def set_gain(self, inputs, gain_coeff, gain_exp, compute_time=None):

        if compute_time is None:
            compute_time = time.time()

        index = np.array([self.correlator_input[inp] for inp in inputs])

        self.compute_time[index] = compute_time

        self.gain_exp[index] = gain_exp
        self.gain_coeff[:, index] = gain_coeff


    def get_output_file(self, **kwargs):
        """ Defines the filenaming conventions for the archive files:

            {output_dir}/{YYYYMMDD}T{HHMMSS}Z_{instrument}_{output_suffix}/{SSSSSSS}.h5

        Parameters
        ----------
        time: unix time
            Time at which the datasets in kwargs were collected.

        acquisition: str
            Full path to the current acquisition file.  The timestamp from the
            raw acquisition directory name is used in the archive file directory name.
        """

        this_time = kwargs.get('time', time.time())

        if 'acquisition' in kwargs:
            base_prefix = kwargs['acquisition'][0:16]
        else:
            base_prefix = datetime.datetime.utcfromtimestamp(this_time).strftime("%Y%m%dT%H%M%SZ")

        start_time = timegm(datetime.datetime.strptime(base_prefix, "%Y%m%dT%H%M%SZ").timetuple())

        # Determine directory
        output_dir = os.path.join(self.output_dir, '_'.join([base_prefix, self.attrs['instrument_name'],
                                                             self.output_suffix]))
        try:
            os.makedirs(output_dir)
        except OSError:
            if not os.path.isdir(output_dir):
                raise

        # Determine filename
        seconds_elapsed = this_time - start_time

        output_file = os.path.join(output_dir, "%08d.h5" % seconds_elapsed)

        return output_file


    def set_attrs(self, **kwargs):

        # Include important attributes
        # that we want all archive files to have
        self.attrs['type'] = str(type(self))
        self.attrs['git_version_tag'] = subprocess.check_output(["git", "-C", os.path.dirname(__file__),
                                                                 "describe", "--always"]).strip()
        self.attrs['collection_server'] = subprocess.check_output(["hostname"]).strip()
        self.attrs['system_user'] = subprocess.check_output(["id", "-u", "-n"]).strip()

        # Save input attributes
        for key, value in kwargs.iteritems():
            self.attrs[key] = value

    @property
    def correlator_input(self):
        try:
            return self._correlator_input

        except AttributeError:
            self._correlator_input = {inp['correlator_input']:inp['chan_id']
                                      for inp in self.index_map['input']}
            return self._correlator_input


    @property
    def gain(self):
        return self.datasets['gain_coeff'] * 2**(self.datasets['gain_exp'][np.newaxis, :])
