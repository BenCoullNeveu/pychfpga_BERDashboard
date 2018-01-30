#!/usr/bin/env python

"""RESTful Server & Client Module to run KotekanMaster object used to initialize and operate the CHIME GPU Backend.
"""

#Imports
import sys
import numpy as np
import log
from pychfpga import Metrics, NameSpace
from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return, sleep, IOLoop
from rest import RunSyncWrapper, SocketContext, run_client  # generic REST Server/Client

class KotekanMasterAsyncRESTServer(AsyncRESTServer):
    """
    Async Restful Server for Kotekan Master
    """
    DEFAULT_PORT = 12048
    KOTEKAN_MASTER_HOSTNAME = None

    def __init__(self,  address=KOTEKAN_MASTER_HOSTNAME, port=DEFAULT_PORT, logging_params={}):
        """KotekanMaster Server Initialization
        """
        super(KotekanMasterAsyncRESTServer, self).__init__(address=address, port=port, heartbeat_string='KMs')
        self.last_time = None
        self.config = None

    #Kotekan Master Server Commands
    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        """ Start the Kotekan Master server with provided config
        """
        self.log.info('%r: Received start command' % self)
        self.config = NameSpace(config)
        coroutine_return('KotekanMaster server started.')

    @coroutine
    @endpoint('stop')
    def stop(self, handler):
    	"""Stop the Kotekan Master server
    	"""
        self.config = None
        coroutine_return('KotekanMaster server stopped.')

    @coroutine
    @endpoint('node_status')
    def node_status(self, handler):
    	pass
    
    @coroutine
    @endpoint('node_start')
    def node_start(self, handler):
    	pass

    @coroutine
    @endpoint('node_stop')
    def node_stop(self, handler)
    	pass

class KotekanMasterAsyncRESTClient(AsyncRESTClient):
    """
    Async Restful Server for Kotekan Master
    """
    DEFAULT_PORT = KotekanMasterAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):
    	"""KotekanMaster Client Initialization
    	"""
        super(KotekanMasterAsyncRESTClient, self).__init__(
            hostname=hostname, port=port,
            server_class= KotekanMasterAsyncRESTServer,
            heartbeat_string='KMc')


    @coroutine
    def start(self, config):
        """ If the remote kotekan server is not started, start it with the specified configuration

        Parameters:

            config (str or dict): If a string, the configuration is loaded from the specified
                configuration file and name. if a dict, it is passed directly to the server.

        """
        #print('start!')
        self.log.info('%s: Starting KotekanMasterServer at %s:%i with config: %r' % (self, self.hostname, self.port, config))
        if isinstance(config, str):
            config = load_yaml_config(config)
        result = self.post('start', **config)
        coroutine_return('KotekanMaster server started')

    @coroutine
    def stop(self):
    	self.log.info('%s: Stoping KotekanMasterServer at %s:%i' % (self, self.hostname, self.port))
        result = yield self.get('stop')
        coroutine_return(result)

def main():
    """CLI for operating Kotekan Master
    """
    #TODO: Add Configuration Here
    #TODO: Add click based CLI similar to ch_master
    config = None
    log.setup_basic_logging('INFO')
    client, server = run_client(config, KotekanMasterAsyncRESTServer, KotekanMasterAsyncRESTClient, object_name ='KotekanMaster')
    cm = None
    if server and server.chime_master:
        cm = RunSyncWrapper(server.chime_master)
        print("   cm: ChimeMaster object")
    return client, server, cm

if __name__ == '__main__':
    """Kotekan Master CLI Instantiation
    """
    client, server, cm = main()

