#!/usr/bin/env python
"""
REST Server and clients for the Dataset Broker.

"""

import sys
import thread
import datetime

from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return
from rest import run_client  # generic REST servers and clients
import toro  # conditional variables for tornado coroutines

import log  # logging helper functions

WAIT_TIME = 40


def datetime_to_float(d):
    epoch = datetime.datetime.utcfromtimestamp(0)
    total_seconds = (d - epoch).total_seconds()
    # total_seconds will be in decimals (millisecond precision)
    return total_seconds


def float_to_datetime(fl):
    return datetime.datetime.utcfromtimestamp(fl)

class DSBrokerAsyncRESTServer(AsyncRESTServer):
    """
    REST interface for Dataset Broker.
    """

    DEFAULT_PORT = 12050

    def __init__(self, address='', port=DEFAULT_PORT, logging_params={}):
        """
        List of dict with entries 'type', 'name', and 'address'
        """
        self.states = dict()
        self.datasets = dict()
        self.timestamps = dict()
        self.signal_states_updated = toro.Condition()
        self.signal_datasets_updated = toro.Condition()
        self.lock_datasets = thread.allocate_lock()
        self.lock_states = thread.allocate_lock()
        super(DSBrokerAsyncRESTServer, self).__init__(address=address,
                                                      port=port,
                                                      heartbeat_string='Gs')

    ##################
    # Server commands
    ##################

    @coroutine
    @endpoint('status')
    def status(self, handler):
        """ Get status of dataset-broker.

        Shows all datasets and states registered by the broker.

        curl
        -X GET
        http://localhost:12050/status
        """
        self.log.debug('%.32r: Received status request' % self)
        reply = dict()
        with self.lock_datasets:
            reply["states"] = self.states.keys()
        with self.lock_states:
            reply["datasets"] = self.datasets.keys()
        coroutine_return(reply)
        self.log.debug('%.32r: states: %r' % (self, self.states.keys()))
        self.log.debug('%.32r: datasets: %r' % (self, self.datasets.keys()))

    @coroutine
    @endpoint('register-state')
    def registerState(self, handler, hash):
        """ Register a dataset state with the broker.

        This should only ever be called by kotekan's datasetManager.
        """
        self.log.debug('%.32r: Received register state request, hash: %r'
                       % (self, hash))
        reply = dict(result="success")
        with self.lock_states:
            if self.states.get(hash) is None:
                # we don't know this state, ask for it
                reply['request'] = "get_state"
                reply['hash'] = hash
                self.log.debug('%.32r: Asking for state, hash: %r'
                               % (self, hash))
        coroutine_return(reply)

    @coroutine
    @endpoint('send-state')
    def sendState(self, handler, hash, state):
        """ Send a dataset state to the broker.

        This should only ever be called by kotekan's datasetManager.
        """
        self.log.debug('%.32r: Received state %r' % (self, hash))
        reply = dict()

        # do we have this state already?
        with self.lock_states:
            found = self.states.get(hash)
            if found is not None:
                # if we know it already, does it differ?
                if found != state:
                    reply['result'] = "error: a different state is know to " \
                                      "the broker with this hash: %r" % found
                    self.log.warn('%.32r: Failure receiving state: a '
                                  'different state with the same hash is: %r'
                                  % (self, found))
                else:
                    reply['result'] = "success"
            else:
                self.states[hash] = state
                reply['result'] = "success"
                self.signal_states_updated.notify_all()
        coroutine_return(reply)

    @coroutine
    @endpoint('register-dataset')
    def registerDataset(self, handler, hash, ds):
        """ Register a dataset with the broker.

        This should only ever be called by kotekan's datasetManager.
        """
        self.log.debug('%.32r: Registering new dataset with hash %r : %r' %
                       (self, hash, ds))
        dataset_valid = yield self.checkDataset(ds)
        reply = dict()

        # dataset already known?
        with self.lock_datasets:
            found = self.datasets.get(hash)
            if found is not None:
                # if we know it already, does it differ?
                if found != ds:
                    reply['result'] = "error: a different dataset is know to" \
                                    " the broker with this hash: %r" % found
                    self.log.warn('%.32r: Failure receiving dataset: a'
                                  ' different dataset with the same hash is: %r'
                                  % (self, found))
                else:
                    reply['result'] = "success"
            elif dataset_valid:
                # add a timestamp to the dataset (ms precision)
                self.timestamps[hash] = datetime_to_float(datetime.datetime.utcnow())

                # save the dataset
                self.datasets[hash] = ds
                reply['result'] = "success"
                self.signal_datasets_updated.notify_all()
            else:
                reply['result'] = "dataset invalid."
                self.log.debug(
                    '%.32r: Received invalid dataset with hash %r : %r' %
                    (self, hash, ds))

            coroutine_return(reply)

    @coroutine
    def checkDataset(self, ds):
        """ Checks if a dataset is valid.

        For a dataset to be valid, the state and base dataset it references to
        have to exist. If it is a root dataset, the base dataset does not have
        to exist.
        """
        if not self.wait_for_state(ds['state']):
            self.log.debug('%.32r: State of dataset unknown: %r' %
                           (self, ds))
            coroutine_return(False)
        if ds['is_root']:
            coroutine_return(True)
        if not self.wait_for_dset(ds['base_dset']):
            self.log.debug('%.32r: Base dataset of dataset unknown: %r' %
                           (self, ds))
            coroutine_return(False)
        coroutine_return(True)

    @coroutine
    @endpoint('request-state')
    def requestState(self, handler, id):
        """ Request the state with the given ID.

        This is called by kotekan's datasetManager.

        curl
        -d '{"state_id":42}'
        -X POST
        -H "Content-Type: application/json"
        http://localhost:12050/request-state
        """
        self.log.debug('%.32r: Received request for state with ID %r'
                       % (self, id))
        reply = dict()
        reply['id'] = id

        # Do we know this state ID?
        self.log.debug(
            '%.32r: waiting for state ID %r' % (self, id))
        found = yield self.wait_for_state(id)
        if not found:
            reply['result'] = "state ID %r unknown to broker." % id
            self.log.info('%.32r: State %r unknown to broker' % (self, id))
            coroutine_return(reply)
        self.log.debug(
            '%.32r: found state ID %r' % (self, id))

        with self.lock_states:
            reply['state'] = self.states[id]

        reply['result'] = "success"
        self.log.debug(
            '%.32r: Replying with %r' % (self, reply))
        coroutine_return(reply)

    @coroutine
    def wait_for_dset(self, id):
        found = True
        self.lock_datasets.acquire()

        if self.datasets.get(id) is None:
            # wait for half of kotekans timeout before we admit we don't have it
            self.lock_datasets.release()
            notified = True
            self.log.debug('%.32r: Waiting for dataset %r' % (self, id))
            try:
                while True:
                    notified = yield self.signal_datasets_updated.wait(
                        deadline=datetime.timedelta(seconds=WAIT_TIME))
                    # did someone send it to us by now?
                    with self.lock_datasets:
                        if self.datasets.get(id) is not None:
                            break
            except toro.Timeout as e:
                pass
            self.lock_datasets.acquire()
            if self.datasets.get(id) is None:
                self.log.warn('%.32r: Timeout (%rs) when waiting for dataset %r'
                              % (self, WAIT_TIME, id))
                found = False
        self.lock_datasets.release()

        coroutine_return(found)

    @coroutine
    def wait_for_state(self, id):
        found = True
        self.lock_states.acquire()
        if self.states.get(id) is None:
            # wait for half of kotekans timeout before we admit we don't have it
            self.lock_states.release()
            notified = True
            self.log.debug('%.32r: Waiting for state %r' % (self, id))
            try:
                while True:
                    notified = yield self.signal_states_updated.wait(
                        deadline=datetime.timedelta(seconds=WAIT_TIME))
                    # did someone send it to us by now?
                    with self.lock_states:
                        if self.states.get(id) is not None:
                            break
            except toro.Timeout as e:
                pass
            self.lock_states.acquire()
            if self.states.get(id) is None:
                self.log.warn('%.32r: Timeout (%rs) when waiting for state %r'
                              % (self, WAIT_TIME, id))
                found = False
        self.lock_states.release()

        coroutine_return(found)

    @coroutine
    @endpoint('update-datasets')
    def updateDatasets(self, handler, ds_id, ts):
        """
        Request all ancestors of the given dataset that where added after
        the given timestamp.

        This is called by kotekan's datasetManager.

        curl
        -d '{"ds_id":2143,"ts":0}'
        -X POST
        -H "Content-Type: application/json"
        http://localhost:12050/update-datasets
        """
        self.log.debug('%.32r: Received request for ancestors of dataset %r '
                       'since timestamp %r.' % (self, ds_id, ts))
        reply = dict()

        # Do we know this ds ID?
        found = yield self.wait_for_dset(ds_id)
        if not found:
            reply['result'] = "Dataset ID %r unknown to broker." % ds_id
            self.log.info('%.32r: Dataset ID %r unknown to broker' % (self, ds_id))
            coroutine_return(reply)

        if ts is 0:
            ts = datetime_to_float(datetime.datetime.min)
            self.log.debug('%.32r: Zero timestamp: %r' % (self, ts))

        with self.lock_datasets:
            # add a timestamp to the result while datasets locked
            reply['ts'] = datetime_to_float(datetime.datetime.utcnow())
            reply['datasets'] = dict()

            # Get all update since timestamp
            while ts < self.timestamps[ds_id]:
                self.log.debug('%.32r: Adding dataset %r' % (self, self.datasets[ds_id]))

                reply['datasets'][ds_id] = self.datasets[ds_id]

                # Stop at the root.
                if self.datasets[ds_id]['is_root']:
                    break

                ds_id = self.datasets[ds_id]['base_dset']


        reply['result'] = "success"
        self.log.debug('%.32r: Answering with %r.' % (self, reply))
        coroutine_return(reply)


#########################################
# Dataset Broker REST client
#########################################

class DSBrokerAsyncRESTClient(AsyncRESTClient):
    """
    Implements an asynchronous client that exposes the functions of the
    specified remote dataset broker.

    The client is implemented using a Tornado AsyncHTTPClient. It exposes the
    dataset broker methods
    (i.e REST endpoints) as local methods. The local methods are Tornado
    coroutines so requests to
    multiple clients can be made in parallel. This is especially beneficial
    since the data requests
    from the server are slow IO operations which benefit the mist from
    co-execution.

    The client will operate only if the IOloop in which is was created is
    running.

    Parameters:

        name (str): Name of the client, to be used in logging etc.

        hostname (str): The hostname of the dataset broker. If `host` is None,
        an (experimental,
             Python-based) dataset broker REST server will be created locally.

        port (int): The port number to which the dataset broker REST server is
        listening. Default is port 80.
    """
    DEFAULT_PORT = DSBrokerAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):
        super(DSBrokerAsyncRESTClient, self).__init__(
            hostname=hostname, port=port,
            server_class=DSBrokerAsyncRESTServer,
            heartbeat_string='Gc')

    @coroutine
    def registerState(self, hash):
        result = yield self.post('register-state', hash)
        coroutine_return(result)

    @coroutine
    def sendState(self, hash, state):
        result = yield self.post('send-state', hash, state)
        coroutine_return(result)

    @coroutine
    def registerDataset(self, hash, ds):
        result = yield self.post('register-dataset', hash, ds)
        coroutine_return(result)

    @coroutine
    def status(self):
        result = yield self.get('status')
        coroutine_return(result)

    @coroutine
    def requestState(self, state_id):
        result = yield self.post('request-state', id)
        coroutine_return(result)

    @coroutine
    def updateDatasets(self, ds_id, ts):
        result = yield self.post('update-datasets', ds_id, ts)


def main():
    """ Command-line interface to launch and operate the dataset broker.
    """
    # Setup logging
    log.setup_basic_logging('DEBUG')
    client, server = run_client(sys.argv[1:],
                                DSBrokerAsyncRESTServer,
                                DSBrokerAsyncRESTClient,
                                object_name='DSETBROKER',
                                server_config_path='dsetbroker.servers')
    return client, server


if __name__ == '__main__':
    client, server = main()
