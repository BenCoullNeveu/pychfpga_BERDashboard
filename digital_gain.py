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

from pychfpga import Hdf5Archive

__version__ = u'0.3'
ARCHIVE_VERSION = u'3.2.0'

MAX_NUM = 1
MAX_FILE_SIZE = 100000000

class DigitalGainArchive(Hdf5Archive):
    """ Interface to an Hdf5Archive containing digital gains.
    """

    _uniq_id = 'update_id'
    _grow_ax = 'update_time'

    _axes = {
        'update_time': {'dtype': np.float64},
        'freq':  {'dtype': [('centre', '<f8'), ('width', '<f8')]},
        'input': {'dtype': [('chan_id', 'u2'), ('correlator_input', 'S32')]},
    }

    _dataset_spec = {
        'update_id': {
            'axes': ['update_time', ],
            'dtype': h5py.special_dtype(vlen=bytes),
            'metric': False,
        },
        'compute_time': {
            'axes': ['update_time', 'input'],
            'dtype': np.float32,
            'metric': False,
        },
        'gain_coeff': {
            'axes': ['update_time', 'freq', 'input'],
            'dtype': np.complex64,
            'metric': False,
        },
        'gain_exp': {
            'axes': ['update_time', 'input'],
            'dtype': np.int32,
            'metric': False,
        }
    }

    _input_to_sma = [12, 13, 14, 15, 8, 9, 10, 11, 4, 5, 6, 7, 0, 1, 2, 3]

    def __init__(self, output_dir=None, output_suffix="digitalgain", search=True,
                       instrument_name="chime", notes="", max_num=MAX_NUM, max_file_size=MAX_FILE_SIZE,
                       *args, **kwargs):
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
        """

        # Save axes
        self.axes = {}
        for ax in self._axes.keys():
            if ax != self._grow_ax:
                if ax in kwargs:
                    self.axes[ax] = kwargs.pop(ax)
                else:
                    ValueError("Must pass the axis %s as a keyword when initializing %s." % (ax, self))

        # Set parameters that specify output file format
        self.output_dir = output_dir
        self.output_suffix = output_suffix

        # Determine correlator based on instrument_name
        if 'correlator' in kwargs:
            self.correlator = kwargs['correlator']
        elif instrument_name.lower() == 'pathfinder':
            self.correlator = 'K7BP16-0004'
        elif instrument_name.lower() == 'chime':
            self.correlator = 'FCC'
        else:
            self.correlator = None

        # Search for previous files
        if search:
            output_files = sorted(glob.glob(os.path.join(self.output_dir,
                              '*' + instrument_name + '_' + self.output_suffix, '*.h5'))) or None
        else:
            output_files = None

        # Call superclass
        super(DigitalGainArchive, self).__init__(archive_files=output_files,
                                                 max_num=max_num, max_file_size=max_file_size,
                                                 *args, **kwargs)

        # Set attributes
        self.set_attrs(**{'instrument_name':instrument_name, 'version':__version__, 'notes':notes,
                          'archive_version':ARCHIVE_VERSION})

        # Initialize the gain buffer
        self.buffer = {}
        datasets = [dset for dset in self._dataset_spec.keys() if dset != self._uniq_id]
        for dset in datasets:
            dspec = self._dataset_spec[dset]
            axes = [ax for ax in dspec['axes'] if ax != self._grow_ax]
            if axes:
                shp = [self.axes[ax].size for ax in axes]
                self.buffer[dset] = np.zeros(shp, dtype=dspec['dtype'])

        # Save the last update to the buffer
        if self.current_file is not None:
            lastup = self.last_update
            for dset in datasets:
                self.buffer[dset] = self.read(lastup, dset)


    def get_output_file(self, smp, **kwargs):
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

        if 'acquisition' in kwargs:
            base_prefix = kwargs['acquisition'][0:16]
        else:
            base_prefix = datetime.datetime.utcfromtimestamp(smp).strftime("%Y%m%dT%H%M%SZ")

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
        seconds_elapsed = smp - start_time

        output_file = os.path.join(output_dir, "%08d.h5" % seconds_elapsed)

        return output_file


    def write(self, smp=None, **kwargs):

        if smp is None:
            smp = time.time()

        for key, value in self.axes.items():
            kwargs[key] = value

        for key, value in self.buffer.items():
            kwargs[key] = value

        if 'update_id' not in kwargs:
            kwargs['update_id'] = '_'.join([self.output_suffix,
                                            datetime.datetime.utcfromtimestamp(smp).strftime("%Y%m%dT%H%M%S.%fZ")])

        # Call superclass
        super(DigitalGainArchive, self).write(smp, **kwargs)


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

                chan_id = self.chan_id[sn]

                self.buffer['gain_coeff'][:, chan_id] = gains[0]
                self.buffer['gain_exp'][chan_id] = gains[1]
                self.buffer['compute_time'][chan_id] = this_calc_time


    def set_gain(self, inputs, gain_coeff, gain_exp, compute_time=None):

        if compute_time is None:
            compute_time = time.time()

        index = np.array([self.chan_id[inp] for inp in inputs])

        self.buffer['gain_exp'][index] = gain_exp
        self.buffer['gain_coeff'][:, index] = gain_coeff
        self.buffer['compute_time'][index] = compute_time


    @property
    def chan_id(self):
        try:
            return self._chan_id

        except AttributeError:
            self._chan_id = {inp['correlator_input']:inp['chan_id']
                                      for inp in self.axes['input']}
            return self._chan_id
