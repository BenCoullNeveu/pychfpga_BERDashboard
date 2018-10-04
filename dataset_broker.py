#!/usr/bin/env python
"""
REST Server and clients for the Dataset Broker.

"""

import sys
import thread
import time
import datetime

from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return
from rest import run_client  # generic REST servers and clients
import toro # conditional variables for tornado coroutines

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
        self.cv_states = toro.Condition()
        self.cv_dsets = toro.Condition()
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
        self.log.info('%.32r: Received register state request, hash: %r' % (self, hash))
        reply = dict(result="success")
        with self.lock_states:
            if self.states.get(hash) is None:
                # we don't know this state, ask for it
                reply['request'] = "get_state"
                reply['hash'] = hash

        self.log.info('%.32r: Received register state request DONE, hash: %r' % (self, hash))
        coroutine_return(reply)

    @coroutine
    @endpoint('send-state')
    def sendState(self, handler, hash, state):
        self.log.info('%.32r: Received state %r : %r' % (self, hash, state))
        reply = dict()

        # do we have this state already?
        with self.lock_states:
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
                self.cv_states.notify_all()

        self.log.info('%.32r: Received state DONE %r : %r' % (self, hash, state))
        coroutine_return(reply)

    @coroutine
    @endpoint('register-dataset')
    def registerDataset(self, handler, state_id, base_ds_id):
        self.log.info('%.32r: Registering new dataset: (state: %r, base_ds: %r)' % (self, state_id, base_ds_id))
        reply = dict(result="success")

        # dataset already known?
        with self.lock_ds:
            known = self.datasets.count((state_id, base_ds_id)) > 0

        if known:
            with self.lock_ds:
                reply['new_ds_id'] = self.datasets.index((state_id, base_ds_id))

            self.log.info('%.32r: Dataset %r already registered (state: %r, base_ds: %r)' % (self, reply['new_ds_id'],
                                                                                         state_id, base_ds_id))
        else:
            # is the base ds id known?
            known = yield self.wait_for_dset(base_ds_id)
            if not known:
                reply["result"] = "error: base dataset ID %r unknown to broker." % base_ds_id
                self.log.info('%.32r: %r' % reply["result"])
                coroutine_return(reply)
            with self.lock_ds:
                self.datasets.append((state_id, base_ds_id))
                reply['new_ds_id'] = len(self.datasets) - 1

            self.log.info('%.32r: Registered new dataset %r (state: %r, base_ds: %r)' % (self, reply['new_ds_id'],
                                                                                         state_id, base_ds_id))
            self.cv_dsets.notify_all()
        reply['state_id'] = state_id
        reply['base_dset_id'] = base_ds_id
        coroutine_return(reply)

    @coroutine
    @endpoint('request-ancestors')
    def requestAncestors(self, handler, ds_id):
        self.log.info(
            '%.32r: Received request for ancestors of dataset %r' % (self, ds_id))
        reply = dict()

        # Do we know this dset ID?
        found = yield self.wait_for_dset(ds_id)
        if not found:
            reply['result'] = "error: dataset ID %r unknown to broker." % ds_id
            self.log.info(
                '%.32r: Dataset %r unknown to broker' % (self, ds_id))
            coroutine_return(reply)

        try:
            reply["ancestors"] = yield self.ancestors(ds_id);
        except Exception as error:
            reply["result"] = error.message
            self.log.error('%.32r: %r' % (self, error))
            coroutine_return(reply)

        reply['result'] = "success"
        self.log.info(
            '%.32r: Answering %r' % (self, reply))
        coroutine_return(reply)

    @coroutine
    def wait_for_dset(self, id):
        found = True
        self.lock_ds.acquire()
        if id >= len(self.datasets):
            # wait for half of kotekans timeout before we admit we don't have it
            start_time = time.time()
            #while time.time() - start_time < 15:
            self.lock_ds.release()
                #yield gen.sleep(0.5)
            notified = True
            try:
                while notified:
                    notified = yield self.cv_dsets.wait(deadline=datetime.timedelta(seconds=15))
                    # did someone send it to us by now?
                    with self.lock_ds:
                        if id < len(self.datasets):
                            break
            except:
                pass
            self.lock_ds.acquire()
            if id >= len(self.datasets):
                self.log.warn('%.32r: Timeout when waiting for dataset %r' % (self, id))
                found = False
        self.lock_ds.release()

        coroutine_return(found)

    @coroutine
    def wait_for_state(self, id):
        found = True
        self.lock_states.acquire()
        if self.states.get(id) is None:
            # wait for half of kotekans timeout before we admit we don't have it
            self.lock_states.release()
            notified = True
            try:
                while notified:
                    notified = yield self.cv_states.wait(deadline=datetime.timedelta(seconds=15))
                    # did someone send it to us by now?
                    with self.lock_states:
                        if self.states.get(id) is not None:
                            break
            except:
                pass
            self.lock_states.acquire()
            if self.states.get(id) is None:
                found = False
        self.lock_states.release()

        coroutine_return(found)

    @coroutine
    def ancestors(self, ds_id, js=dict(datasets=dict(), states=dict())):
        self.log.info(
            '%.32r: Collecting ancestors: %r' % (self, js))

        with self.lock_ds:
            js["datasets"][ds_id] = self.datasets[ds_id]
            state_id = self.datasets[ds_id][0]

        found = yield self.wait_for_state(state_id)
        if not found:
            raise Exception("Error: Broker is in bad state. Found reference to not existing state ID.")

        with self.lock_states:
            js["states"][state_id] = self.states[state_id]

        if ds_id == -1:
            coroutine_return(js)

        with self.lock_ds:
            next_ds = self.datasets[ds_id][1]

        found = yield self.wait_for_dset(next_ds)
        if not found:
            raise Exception("Error: Broker is in bad state. Found reference to not existing dataset ID.")
        result = yield self.ancestors(next_ds, js)
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

    @coroutine
    def requestAncestors(self, ds_id):
        result = yield self.post('request-ancestors')
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
