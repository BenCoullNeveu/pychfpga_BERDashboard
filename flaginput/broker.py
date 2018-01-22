#!/usr/bin/env python
"""
REST server and client for flagging bad correlator inputs.
"""
__version__ = '0.1'

import os
import sys
import glob
import Queue
import concurrent.futures
import datetime
import time

import numpy as np
import h5py
import log

import flag_raw

from pychfpga import NameSpace, Metrics, load_yaml_config
from pychfpga import Hdf5Archive, OrderedSetLifoQueue, OrderedSetFifoQueue
from rest import AsyncRESTClient, AsyncRESTServer   # generic REST servers and clients
from rest import coroutine, coroutine_return, endpoint, run_client

from ch_util.ephemeris import unix_to_datetime, datetime_to_unix, timestr_to_datetime
from ch_util import tools

#ARCHIVE = "/mnt/gong/archive"
ARCHIVE = "/home/ssiegel/chime/flag_input/archive"
RAW_ACQ_SUFFIX = "_chime_rawadc"

OUTPUT_DIR = "/home/ssiegel/chime/flag_input"
OUTPUT_SUFFIX = "flaginput"

METRIC_NAME = "flaginput"
MAX_METRICS_SIZE = 5

MAX_FILE_SIZE = 4000000000

THREADPOOL_MAX_WORKERS = 8

def format_filename(filename):

    return os.path.join(os.path.basename(os.path.dirname(filename)),
                        os.path.basename(filename))

def filename_to_datetime(filename):

    acq_date = timestr_to_datetime(os.path.basename(os.path.dirname(filename)))
    file_date = acq_date + datetime.timedelta(seconds=int(os.path.splitext(os.path.basename(filename))[0]))

    return file_date

def ensure_unix(val):

    if isinstance(val, (float, int, long)):
        return val

    elif isinstance(val, basestring):
        return datetime_to_unix(timestr_to_datetime(val))

    elif isinstance(val, datetime.datetime):
        return datetime_to_unix(val)

    elif isinstance(val, dict):
        return datetime_to_unix(datetime.datetime(**val))

    elif isinstance(val, tuple) or isinstance(val, list):
        return datetime_to_unix(datetime.datetime(*val))

    else:
        ValueError("Do not recognize %.32r as time." % type(val))



class FlagCorrInputArchive(Hdf5Archive):
    """ Interface to an Hdf5Archive containing flags derived
    from raw adc data (and associated data products).
    """

    _uniq_id = 'filename'
    _grow_ax = 'time'

    _axes = {
        'time': {'dtype': np.float64},
        'input': {'dtype': str},
        'lsb': {'dtype': np.float32},
        'freq': {'dtype': np.float32}
    }

    _dataset_spec = {
        'filename': {
            'axes': ['time', ],
            'dtype': h5py.special_dtype(vlen=bytes),
            'metric': False,
        },
        'histogram_threshold': {
            'axes': ['time', ],
            'dtype': np.float32,
            'metric': True,
        },
        'histogram_template': {
            'axes': ['time', 'lsb'],
            'dtype': np.float32,
            'metric': True,
        },
        'spectrum_threshold': {
            'axes': ['time', ],
            'dtype': np.float32,
            'metric': True,
        },
        'spectrum_template': {
            'axes': ['time', 'freq'],
            'dtype': np.float32,
            'metric': True,
        },
        'nframe': {
            'axes': ['time', 'input'],
            'dtype': np.int16,
            'metric': True,
        },
        'mean': {
            'axes': ['time', 'input'],
            'dtype': np.float32,
            'metric': False,
        },
        'rms': {
            'axes': ['time', 'input'],
            'dtype': np.float32,
            'metric': False,
        },
        'skew': {
            'axes': ['time', 'input'],
            'dtype': np.float32,
            'metric': True,
        },
        'kurtosis': {
            'axes': ['time', 'input'],
            'dtype': np.float32,
            'metric': True,
        },
        'histogram': {
            'axes': ['time', 'input', 'lsb'],
            'dtype': np.float32,
            'metric': True,
        },
        'histogram_corr_coeff': {
            'axes': ['time', 'input'],
            'dtype': np.float32,
            'metric': True,
        },
        'histogram_fail': {
            'axes': ['time', 'input'],
            'dtype': np.bool,
            'metric': True,
        },
        'spectrum': {
            'axes': ['time', 'input', 'freq'],
            'dtype': np.float32,
            'metric': False,
        },
        'spectrum_corr_coeff': {
            'axes': ['time', 'input'],
            'dtype': np.float32,
            'metric': True,
        },
        'spectrum_fail': {
            'axes': ['time', 'input'],
            'dtype': np.bool,
            'metric': True,
        },
        'layout_fail': {
            'axes': ['time', 'input'],
            'dtype': np.bool,
            'metric': False,
        }
    }

    def __init__(self, output_dir=OUTPUT_DIR, output_suffix=OUTPUT_SUFFIX, instrument='chime', *args, **kwargs):
        """ Instantiates a FlagCorrInputArchive object.

        Parameters
        ----------
        output_dir:  str
            Directory where the hdf5 archive files will be saved.

        output_suffix: str
            Suffix appended to the hdf5 archive filenames.

        instrument:  str
            Name of the instrument/correlator.  Included in hdf5 archive filenames,
            and also saved to file attributes. (Default 'chime')
        """

        # Call superclass
        super(FlagCorrInputArchive, self).__init__(*args, **kwargs)

        # Set parameters that specify output file format
        self.output_dir = output_dir
        self.output_suffix = output_suffix

        # Set attributes
        self.set_attrs(**{'instrument':instrument, 'version':__version__})

        # Set metric name
        self._metric_name = METRIC_NAME


    def get_output_file(self, **kwargs):
        """ Defines the filenaming conventions for the archive files:

            {output_dir}/{YYYYMMDD}T{HHMMSS}Z_{instrument}_{suffix}_v{version}.h5

        Parameters
        ----------
        filename: str
            Full path to the current raw acquisition file.  The timestamp from the
            raw acquisition name is used as prefix to the archive file basename.
        """

        # Determine new filename
        if not 'filename' in kwargs:
            RuntimeError("Must include raw acquisition filename in call to write.")

        base_prefix = os.path.basename(os.path.dirname(kwargs['filename']))[0:16]
        version = 'v' + '_'.join(self.attrs['version'].split('.'))
        output_file = os.path.join(self.output_dir, '_'.join([base_prefix, self.attrs['instrument'],
                                   self.output_suffix, version]) + '.h5')

        return output_file



class FlagCorrInput(object):
    """ Manages flagging of bad correlator inputs.  Specifically:

    Queries layout database to flag inputs not connected to CHIME antennas. (layout)

    Queries bulkhead servers to flag inputs whose FLAs are not currently powered. (fla_power)
        Not yet implemented.

    Queries raw acquisition server to flag inputs with low or high RMS. (rms)
        Not yet implemented.

    Processes raw acquisition data files to flag inputs with anomalous
        histogram or spectrum. (raw_adc)
    """

    def __init__(self, archive=ARCHIVE, raw_acq_suffix=RAW_ACQ_SUFFIX,
                       output_dir=OUTPUT_DIR, output_suffix=OUTPUT_SUFFIX,
                       correlator='chime', start_time=0.0, lifo=False,
                       do_raw_adc=True, do_layout=True):
        """ Instantiates a FlagCorrInput object.

        """

        # Save configuration parameters
        self.archive = archive
        self.raw_acq_suffix = raw_acq_suffix
        self.output_dir = output_dir
        self.output_suffix = output_suffix
        self.correlator = correlator

        self.do_raw_adc = do_raw_adc
        self.future_raw_adc = None

        self.do_layout = do_layout
        self.future_layout = None

        # Setup logger
        self.log = log.get_logger(self)

        # Create queue for metrics
        self.metrics_queue = Queue.Queue(maxsize=MAX_METRICS_SIZE)

        # Create queue for files that need to be analyzed
        self.file_queue = OrderedSetLifoQueue(maxsize=0) if lifo else OrderedSetFifoQueue(maxsize=0)

        # Check if any output files exist
        output_files = sorted(glob.glob(os.path.join(self.output_dir, '*' + self.output_suffix +
                                                    '_v' + '_'.join(__version__.split('.')) + '.h5'))) or None

        # Create hdf5 reader/writer
        self.read_write = FlagCorrInputArchive(output_dir=self.output_dir, output_suffix=self.output_suffix,
                                               instrument=self.correlator, archive_files=output_files)

        # Create pool of threads for asynchronous computations
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=THREADPOOL_MAX_WORKERS)

        # Query the layout database to obtain list of current correlator inputs
        self.query_layout_database()

        # Will search for raw acquisition files after input start_time
        self.search_time = ensure_unix(start_time)

        # Start processing the raw adc files on thread from pool
        self.future_raw_adc = self.executor.submit(self.process_raw_adc_files)


    def get_raw_adc_files(self):

        # Find all raw acquisition files in archive
        all_files = sorted(glob.glob(os.path.join(self.archive, '*' + self.raw_acq_suffix, '*.h5')))
        if not all_files:
            return

        # Remove files whose last modified time is before the time of the most recent update
        #all_files = [ff for ff in all_files if (os.path.getmtime(ff) > self.search_time)]
        all_files = [ff for ff in all_files if (ensure_unix(filename_to_datetime(ff)) > self.search_time)]
        if not all_files:
            return

        # Remove files that have already been analyzed
        if self.read_write:
            all_files = [ff for ff in all_files if format_filename(ff) not in self.read_write]
            if not all_files:
                return

        # Remove files that are currently locked
        all_files = [ff for ff in all_files if not os.path.isfile(os.path.splitext(ff)[0] + '.lck')]
        if not all_files:
            return

        # Add new files in the queue
        self.log.info('Adding %d files to queue.' % len(all_files))
        for ff in all_files:
            self.file_queue.put(ff, block=False)

        # Update the time
        self.search_time = time.time()


    def process_raw_adc_files(self):

        while self.do_raw_adc:

            try:
                my_file = self.file_queue.get(block=False)
            except Queue.Empty:
                continue

            try:
                # Call the main routine to process data
                self.log.info('Processing file %s' % my_file)
                outcls = flag_raw.main(my_file, output_csv=False, output_plot=False, output_tex=False, compute_template=True)

                self.log.info('Finished analysis of file %s' % my_file)

                # Extract the time associated with this file
                with h5py.File(my_file, 'r') as hf:
                    this_time = 0.5 * (hf['timestamp']['ctime'][0, 0] + hf['timestamp']['ctime'][-1, 0])

                # Query layout database for correlator inputs
                inputs = tools.get_correlator_inputs(unix_to_datetime(this_time), correlator=self.correlator)

                input_axis = np.array([(inp.id, inp.input_sn) for inp in inputs],
                                  dtype=[('chan_id', 'u2'), ('correlator_input', 'S32')])

                # Save results to dictionary.  First define axes.
                self.log.info('Reordering results from file %s' % my_file)
                res = dict()
                res['input'] = input_axis

                for axis in self.read_write._axes:
                    if (axis not in ['input', self.read_write._grow_ax]) and (axis in outcls.__dict__):
                        res[axis] = outcls.__dict__[axis]

                # Save results to dictionary, ordered using the cylinder based scheme
                for dset in self.read_write._dataset_spec:
                    if dset in outcls.__dict__:

                        # Extract the specifications for this dataset
                        dspec = self.read_write._dataset_spec[dset]
                        dtype = dspec['dtype']
                        axes = [ax for ax in dspec['axes'] if ax != self.read_write._grow_ax]

                        # Check if dataset has input axis to reorder
                        if 'input' in axes:
                            shp = tuple(res[axis].size for axis in axes)
                            default = True if dtype is np.bool else np.nan

                            res[dset] = np.full(shp, default, dtype=dtype)
                            for ind, key in input_axis:
                                try:
                                    res[dset][ind] = outcls.__dict__[dset][key]
                                except KeyError:
                                    pass
                        else:
                            res[dset] = outcls.__dict__[dset]

                res['input'] = input_axis

                # Add layout database flag for this time to results
                res['layout_fail'] = ~np.array(tools.is_chime_on(inputs))

                # Add filename to results
                res['filename'] = format_filename(my_file)

                # Write to output file
                self.log.info('Writing to disk results from file %s' % my_file)
                self.read_write.write(this_time, **res)

                # Get metrics for this file and add to queue
                self.log.info('Grabbing metrics for file %s' % my_file)
                metrics = self.read_write.get_metrics(this_time)

                while True:
                    try:
                        self.metrics_queue.put(metrics, block=False)
                    except Queue.Full:
                        self.metrics_queue.get(block=False)
                        self.metrics_queue.task_done()
                    else:
                        break

            finally:
                self.file_queue.task_done()
                self.log.info('Finished processing file %s' % my_file)


    def query_layout_database(self):

        if self.do_layout:
            self.future_layout = self.executor.submit(self._get_correlator_inputs)


    def _get_correlator_inputs(self, timestamp=None):

        if timestamp is None:
            timestamp = time.time()

        # Query layout database
        inp = tools.get_correlator_inputs(unix_to_datetime(timestamp), correlator=self.correlator)
        self._input = inp

        # Add layout database results to metrics
        metrics = Metrics(default_type='gauge')
        for inp in self._input:
            metrics.add('/'.join([METRIC_NAME, 'layout_fail']), value=not tools.is_chime_on(inp), time=timestamp*1000,
                                                                chan_id=inp.id, correlator_input=inp.input_sn)

        while True:
            try:
                self.metrics_queue.put(metrics, block=False)
            except Queue.Full:
                self.metrics_queue.get(block=False)
                self.metrics_queue.task_done()
            else:
                break


    def get_metrics(self, timestamp=None):

        return self.executor.submit(self.read_write.get_metrics, timestamp)


    def stop(self):
        """ Exit routine:  Closes hdf5 archive, turns off flagging,
        and shuts down thread pool executor.
        """

        self.log.info('Closing %.32r.' % self.read_write)
        self.do_raw_adc = False
        self.do_layout = False
        self.read_write.close_all()
        self.executor.shutdown(wait=False)
        self.log.info('Closed cleanly.')


    @property
    def flag(self):
        """ Provides the most recent correlator input flags.  Defines how the
        flags from various sources are combined into a single boolean value.
        """

        now = time.time()

        flag = np.zeros((self.ninput, 3), dtype=np.bool)

        flag[:, 0] = ~np.array(tools.is_chime_on(self._input))

        if self.read_write:
            flag[:, 1] = self.read_write.read(now, 'histogram_fail')
            flag[:, 2] = self.read_write.read(now, 'spectrum_fail')

        return [not any(flg) for flg in flag]


    @property
    def input(self):
        return [(inp.id, inp.input_sn) for inp in self._input]

    @property
    def ninput(self):
        return len(self._input)

#########################################
# FlagCorrInput REST server
#########################################

class FlagCorrInputAsyncRESTServer(AsyncRESTServer):
    """
    REST interface for FlagCorrInput
    """

    DEFAULT_PORT = 54327

    def __init__(self,  address='', port=DEFAULT_PORT, logging_params={}):

        self.flg = False
        super(FlagCorrInputAsyncRESTServer, self).__init__(address=address, port=port, heartbeat_string='Is')

    @coroutine
    def _get_raw_adc_files(self):
        """ Process new raw acquisition files.
        """
        self.log.info('%.32r: Searching for new raw ADC acquisition files.' % self)
        try:
            # Add new files to the queue
            self.flg.get_raw_adc_files()

            # Make sure the file processor has not died
            if self.flg.do_raw_adc:
                try:
                    exc = self.flg.future_raw_adc.exception(timeout=0.25)

                except concurrent.futures.TimeoutError:
                    pass

                else:
                    self.log.error('%.32r: Raw ADC file processor failed with error:  %s' % (self, exc))
                    self.log.info('%.32r: Restarting raw ADC file processor.' % self)
                    self.flg.future_raw_adc = self.flg.executor.submit(self.flg.process_raw_adc_files)


        except Exception as e:
            self.log.error(e)
            raise

    @coroutine
    def _query_layout_database(self):
        """ Query the layout database and find feeds not connected to an antenna.
        """
        self.log.info('%.32r: Querying layout database.' % self)
        try:
            self.flg.query_layout_database()

        except Exception as e:
            self.log.error(e)
            raise

    ##################
    # Server commands
    ##################

    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        """ Start the FlagCorrInput server with provided config
        """
        self.log.info('%r: Received start command' % self)
        if self.flg:
            raise RuntimeError('%.32r: FlagCorrInput server is already started' % self)

        # Save configuration file
        self.config = NameSpace(config)

        self.log.debug('%r: Creating FlagCorrInput handler' % self)
        self.flg = FlagCorrInput(**config)

        # Add periodic callbacks
        self.add_periodic_callback(self._get_raw_adc_files, 1000*60*1.2)
        self.add_periodic_callback(self._query_layout_database, 1000*60*3)

        # Server started
        coroutine_return('FlagCorrInput server started.')

    @coroutine
    @endpoint('stop')
    def stop(self, handler):
        if not self.flg:
            self.log.warning('%.32r: FlagCorrInput server is not started' % self)
        else:
            self.flg.stop()
            self.flg = False

        # Server stopped
        coroutine_return('FlagCorrInput server stopped.')

    @coroutine
    @endpoint('correlator-inputs')
    def correlator_inputs(self, handler):
        self.log.info('%.32r: Received request for correlator inputs.' % self)
        if self.flg:
            coroutine_return( self.flg.input )

        else:
            coroutine_return( "FlagCorrInput server is not started" )

    @coroutine
    @endpoint('good-correlator-inputs')
    def good_correlator_inputs(self, handler):
        self.log.info('%.32r: Received request for good correlator inputs.' % self)
        if self.flg:
            coroutine_return( [inp for inp, good in zip(self.flg.input, self.flg.flag) if good] )

        else:
            coroutine_return( "FlagCorrInput server is not started" )

    @coroutine
    @endpoint('bad-correlator-inputs')
    def bad_correlator_inputs(self, handler):
        self.log.info('%.32r: Received request for bad correlator inputs.' % self)
        if self.flg:
            coroutine_return( [inp for inp, good in zip(self.flg.input, self.flg.flag) if not good] )

        else:
            coroutine_return( "FlagCorrInput server is not started" )

    @coroutine
    @endpoint('correlator-input-flags')
    def correlator_input_flags(self, handler):
        self.log.info('%.32r: Received request for correlator input flag.' % self)
        if self.flg:
            coroutine_return( self.flg.flag )

        else:
            coroutine_return( "FlagCorrInput server is not started" )

    @coroutine
    @endpoint('monitoring-data')
    def monitoring_data(self, handler):
        self.log.info('%.32r: Received monitoring metrics request.' % self)
        t0 = time.time()
        try:
            metrics = self.flg.metrics_queue.get(block=False)

        except Queue.Empty:
            handler.set_header('Content-Type', 'text/plain')
            handler.write('')
            self.log.info('%.32r: Monitoring metrics queue is empty.' % self)

        else:
            encoding = self.config.encoding if hasattr(self.config, 'encoding') else 'gzip'
            if encoding == 'gzip':
                handler.set_header('Content-Encoding', 'gzip')
                handler.write(metrics.get_gzip())
            else:
                handler.set_header('Content-Type', 'text/plain')
                handler.write(str(metrics))
            self.log.info('%.32r: Returning %i flaginput metrics. The request took %.3f seconds' % (self, len(metrics), time.time()-t0))
            self.flg.metrics_queue.task_done()

    @coroutine
    @endpoint('metrics')
    def metrics(self, handler):
        self.log.info('%.32r: Received metrics request.' % self)
        t0 = time.time()
        try:
            metrics = yield self.flg.get_metrics(t0)

        except Exception as e:
            self.log.error(e)
            raise

        else:
            encoding = self.config.encoding if hasattr(self.config, 'encoding') else 'gzip'
            if encoding == 'gzip':
                handler.set_header('Content-Encoding', 'gzip')
                handler.write(metrics.get_gzip())
            else:
                handler.set_header('Content-Type', 'text/plain')
                handler.write(str(metrics))
            self.log.info('%.32r: Returning %i flag_raw metrics. The request took %.3f seconds' % (self, len(metrics), time.time()-t0))


#########################################
# FlagCorrInput REST client
#########################################

class FlagCorrInputAsyncRESTClient(AsyncRESTClient):
    """
    Implements an asynchronous client that exposes the functions of the specified remote
    FlagCorrInput server.  This client is used by ch_master to start, configure, and
    operate the FlagCorrInput.

    The client is implemented using a Tornado AsyncHTTPClient. It exposes the FlagCorrInput
    server methods (i.e REST endpoints) as local methods. The local methods are Tornado coroutines
    so requests to multiple clients can be made in parallel. This is especially beneficial since
    the data requests from the server are slow IO operations which benefit the most from co-execution.

    The client will operate only if the IOloop in which it was created is running.

    Parameters:

        hostname (str): The hostname of the FlagCorrInput REST server.

        port (int): The port number to which the FlagCorrInput REST server is listening.
                    Default is port 54327.

    """

    DEFAULT_PORT = FlagCorrInputAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):

        super(FlagCorrInputAsyncRESTClient, self).__init__(hostname=hostname, port=port, heartbeat_string='Ic',
                                                         server_class=FlagCorrInputAsyncRESTServer)

    def print_result(self, d):
        if d == {}:
            print('ok')
        elif 'error' in d:
            print('Error:', d['error'].rstrip())
        else:
            print(json.dumps(d, sort_keys=True, indent=2))

    @coroutine
    def start(self, config):
        """ If the FlagCorrInput remote server is not started, start it with the specified configuration

        Parameters:

            config (str or dict): If a string, the configuration is loaded from the specified
                configuration file and name. if a dict, it is passed directly to the server.

        """

        self.log.info('%s: Starting remote FlagCorrInput server at %s:%i with config: %r' % (self, self.hostname, self.port, config))

        if isinstance(config, str):
            config = load_yaml_config(config)

        result = self.post('start', **config)
        coroutine_return('FlagCorrInput server started')

    @coroutine
    def stop(self):
        result = yield self.get('stop')
        coroutine_return(result)

    @coroutine
    def get_correlator_inputs(self):
        res = yield self.get('correlator-inputs')
        self.print_result(res)

    @coroutine
    def get_good_correlator_inputs(self):
        res = yield self.get('good-correlator-inputs')
        self.print_result(res)

    @coroutine
    def get_bad_correlator_inputs(self):
        res = yield self.get('bad-correlator-inputs')
        self.print_result(res)

    @coroutine
    def get_correlator_input_flags(self):
        res = yield self.get('correlator-input-flags')
        self.print_result(res)



def main():
    """ Command-line interface to launch and operate the FlagCorrInput server.
    """
    # Setup logging
    log.setup_basic_logging('INFO')
    client, server = run_client(sys.argv[1:], FlagCorrInputAsyncRESTServer, FlagCorrInputAsyncRESTClient,
                                              object_name='FlagCorrInput', server_config_path='corrinput.servers')
    return client, server

if __name__ == '__main__':
    client, server = main()
