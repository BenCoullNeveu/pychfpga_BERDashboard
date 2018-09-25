#!/usr/bin/env python
"""
REST Server and clients for the Dataset Broker.

"""

import sys
import thread

from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return
from rest import run_client  # generic REST servers and clients

import log  # logging helper functions


class DSBrokerAsyncRESTServer(AsyncRESTServer):
    """
    REST interface for Dataset Broker.
    """

    DEFAULT_PORT = 12050

    def __init__(self,  address='', port=DEFAULT_PORT, logging_params={}):
        """
        List of dict with entries 'type', 'name', and 'address'
        """
        self.states = dict()
        self.datasets = list()
        self.lock_ds = thread.allocate_lock()
        self.lock_states = thread.allocate_lock()
        super(DSBrokerAsyncRESTServer, self).__init__(address=address, port=port, heartbeat_string='Gs')

    ##################
    # Server commands
    ##################

    @coroutine
    @endpoint('status')
    def status(self, handler):
    #     # ps_names = self._parse_names(ps_names)
        self.log.info('%.32r: Received status request' % self)
    #     stati = dict(is_started=bool(self.power_supplies),
    #                  ps_names=self.power_supplies.keys())
    #     for ps_name, ps in self.power_supplies.items():
    #         stati[ps_name] = ps.status()
    #         self.log.info('%.32r: Status of %s is %s' % (self, ps_name, stati[ps_name]))
    #     coroutine_return(stati)

    @coroutine
    @endpoint('register-state')
    def registerState(self, handler, hash):
        self.log.info('%.32r: Received register state request' % self)
        self.log.info('%.32r: hash: %r' % (self, hash))
        reply = dict(result="success")
        self.lock_states.acquire()
        if self.states.get(hash) is None:
            # we don't know this state, ask for it
            reply['request'] = "get_state"
            reply['hash'] = hash
        # FIXME: lock until state is sent?
        self.lock_states.release()
        coroutine_return(reply)

    @coroutine
    @endpoint('send-state')
    def sendState(self, handler, hash, state):
        self.log.info('%.32r: Received state %r : %r' % (self, hash, state))
        reply = dict()

        # do we have this state already?
        self.lock_states.acquire()
        found = self.states.get(hash)
        if found is not None:
            # if we know it already, does it differ?
            if found != state:
                reply['result'] = "error: a different state is know to the broker with this hash: %r" % found
                self.log.info('%.32r: Failure receiving state: a different state with the same hash is: %r'
                              % (self, found))
            else:
                reply['result'] = "success"
        else:
            self.states[hash] = state
            reply['result'] = "success"
        self.lock_states.release()
        coroutine_return(reply)

    @coroutine
    @endpoint('register-dataset')
    def registerDataset(self, handler, state_id, base_ds_id):
        self.log.info('%.32r: Received register dataset request (state: %r, base_ds: %r)' % (self,state_id, base_ds_id))
        reply = dict(result="success")

        # dataset already known?
        self.lock_ds.acquire()
        if self.datasets.count((state_id, base_ds_id)) > 0:
            reply['new_ds_id'] = self.datasets.index((state_id, base_ds_id))
        else:
            self.datasets.append((state_id, base_ds_id))
            reply['new_ds_id'] = len(self.datasets) - 1
        self.lock_ds.release()
        reply['state_id'] = state_id
        reply['base_dset_id'] = base_ds_id
        coroutine_return(reply)

    @coroutine
    @endpoint('request-ancestors')
    def requestAncestors(self, handler, ds_id):
        self.log.info(
            '%.32r: Received request for ancestors of dataset %r' % (self, ds_id))
        reply = dict()

        self.lock_ds.acquire()
        self.lock_states.acquire()

        # Do we know this dset ID?
        if ds_id >= len(self.datasets):
            reply['result'] = "error: dataset ID unknown to broker."
            coroutine_return(reply)

        reply["ancestors"] = yield self.ancestors(ds_id);

        self.lock_states.release()
        self.lock_ds.release()

        reply['result'] = "success"
        coroutine_return(reply)

    @coroutine
    def ancestors(self, ds_id, js=dict(datasets=dict(), states=dict())):
        js["datasets"][ds_id] = self.datasets[ds_id]
        state_id = self.datasets[ds_id][0]
        js["states"][state_id] = self.states[state_id]

        if ds_id == -1:
            coroutine_return(js)
        result = yield self.ancestors(self.datasets[ds_id][1], js)
        coroutine_return(result)

#########################################
# Dataset Broker REST client
#########################################

class DSBrokerAsyncRESTClient(AsyncRESTClient):
    """
    Implements an asynchronous client that exposes the functions of the specified remote dataset broker.

    The client is implemented using a Tornado AsyncHTTPClient. It exposes the dataset broker methods
    (i.e REST endpoints) as local methods. The local methods are Tornado coroutines so requests to
    multiple clients can be made in parallel. This is especially beneficial since the data requests
    from the server are slow IO operations which benefit the mist from co-execution.

    The client will operate only if the IOloop in which is was created is running.

    Parameters:

        name (str): Name of the client, to be used in logging etc.

        hostname (str): The hostname of the dataset broker. If `host` is None, an (experimental,
             Python-based) dataset broker REST server will be created locally.

        port (int): The port number to which the dataset broker REST server is listening. Default is port 80.
    """
    DEFAULT_PORT = DSBrokerAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):
        super(DSBrokerAsyncRESTClient, self).__init__(
            hostname=hostname, port=port,
            server_class= DSBrokerAsyncRESTServer,
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
    def registerDataset(self, state_id, base_ds_id):
        result = yield self.post('register-dataset', state_id, base_ds_id)
        coroutine_return(result)

    @coroutine
    def status(self):
        result = yield self.get('status')
        coroutine_return(result)



def main():
    """ Command-line interface to launch and operate the dataset broker.
    """
    # Setup logging
    log.setup_basic_logging('DEBUG')
    client, server = run_client(sys.argv[1:], DSBrokerAsyncRESTServer, DSBrokerAsyncRESTClient,
                                object_name ='DSETBROKER', server_config_path='dsetbroker.servers')
    return client, server

if __name__ == '__main__':
    client, server = main()
