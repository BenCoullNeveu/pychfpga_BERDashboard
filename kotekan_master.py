#!/usr/bin/env python

"""RESTful Server & Client Module to run KotekanMaster object used to initialize and operate the CHIME GPU Backend.
"""

#Imports
import sys
import numpy as np
import log
from pychfpga import NameSpace
from kotekan import KotekanAsyncRESTClient      
from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return, sleep, IOLoop
from rest import RunSyncWrapper, SocketContext, run_client  # generic REST Server/Client


class KotekanMaster(object):
    """KotekanMaster Object to interact with the kotekan processes running on CHIME GPU Nodes.
    """

    # Logging setup without config file.
    DEFAULT_LOGGING = {
        'handlers': 
            {
            'stderr': {'class': 'logging.StreamHandler', 'level': 'INFO'}
            },
        'loggers': 
            {
            '': {'handlers': ['stderr']}  # root logger
            }
    }

    def __init__(self):
        log.setup_logging(self.DEFAULT_LOGGING)
        self.log.debug('%r: Creating KotekanMaster Instance' % self)
        #KotekanMaster Parameters
        self.state = 'off'
        self.config = None
        self.start_time = None

        #Kotekan Client Objects
        self.kotekan_master = None

        #Logging Parameters
        self.PROGRAM = os.path.realpath(__file__) # absolute path name to this module
        self.GIT_VERSION = "DEV" #TODO: Add a git hook here.
        self.log.info("program %s" % self.PROGRAM)
        self.log.info("version %s" % self.GIT_VERSION)

    def set_config(self, config):
        self.config = NameSpace(config)

    #####################################
    # KOTEKAN Methods                   #
    #####################################

    #These methods manage and operate kotekan clients
    @coroutine
    def create_kotekan_clients(self):
        # Create Kotekan REST clients
        self.kotekan = {}
        nodes = self.config.kotekan.nodes or {}
        for node_name, node_params in nodes.items():
            #config = self.config.kotekan.common_config.copy()
            #config.update(node_params)
            self.kotekan[node_name] = KotekanAsyncRESTClient(name=node_name, **node_params)

    @coroutine
    def start_kotekan_servers(self):
        """
        Start Kotekan serers with the proper config.
        """
        conf = self.config.kotekan
        yield [node.start(config=merge_dict(conf.common_config, conf.nodes[node_name]).as_dict()) for node_name, node in self.kotekan.items()]

    @coroutine
    def stop_kotekan_servers(self):
        """
        Stop Kotekan Servers
        """
        yield [kotekan.stop() for kotekan in self.kotekan]

    #####################################
    # Management Methods                #
    #####################################

    @coroutine
    def start(self):
        """
        Start KotekanMaster
        """
        #Line 631
        coroutine_return({})

    @coroutine
    def stop(self):
        """
        Stop KotekanMaster
        """
        #Line 1036
        if self.state == "on":
            self.state = "stopping"
            self.log.info("Stopping Kotekan Master")
            if self.kotekan:
                yield self.stop_kotekan_clients()
            log.stop_logging(self.logging_handlers)
            reap_cached_sockets()
            self.state("off")
        coroutine_return({})

###############################################################################
# KotekanMaster Server                                                        #
###############################################################################
class KotekanMasterAsyncRESTServer(AsyncRESTServer):
    """Wraps KotekanMaster into a Async Restful Server which can recieve HTTP GET
    or POST requests and call the appropritate KotekanMaster method.
    """
    #Line 1131
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
    def node_stop(self, handler):
    	pass

###############################################################################
# Kotekan Master Client                                                       #
###############################################################################
class KotekanMasterAsyncRESTClient(AsyncRESTClient):
    """Async Restful Server for Kotekan Master
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



###############################################################################
# Command Line Interface to operate KotekanMaster Server                      #
###############################################################################
def main():
    """CLI for operating Kotekan Master
    """
    #TODO: Add Configuration Path Here
    #TODO: Add click based CLI similar to kotekan_master
    config = "config.yaml"
    log.setup_basic_logging('INFO')
    client, server = run_client(config, 
                                KotekanMasterAsyncRESTServer,
                                KotekanMasterAsyncRESTClient, 
                                object_name ='KotekanMaster')
    km = None
    if server:
        km = RunSyncWrapper(server.kotekan_master)
        print("   km: KotekanMaster Object")
    return client, server, km

###############################################################################
# Command Line Instantiation of Kotekan Master                                #
###############################################################################
if __name__ == '__main__':
    """Kotekan Master CLI Instantiation
    """
    client, server, km = main()



