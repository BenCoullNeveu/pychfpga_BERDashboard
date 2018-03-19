#!/usr/bin/env python

"""
RESTful Server & Client Module to run KotekanMaster object used to initialize
and operate the CHIME GPU Backend.
"""

# Imports
import sys
import os
import numpy as np
import log
from pychfpga import NameSpace
from kotekan import KotekanAsyncRESTClient
from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return, sleep, IOLoop
# REST Server/Client
from rest import RunSyncWrapper, SocketContext, run_client


class KotekanMaster(object):
    """
    KotekanMaster Object to interact with the kotekan processes running
    on CHIME GPU Nodes.
    """

    # Logging setup without config file.
    DEFAULT_LOGGING = {
        'handlers':
            {
                'stderr': {
                    'class': 'logging.StreamHandler',
                    'level': 'DEBUG'
                    }
            },
        'loggers':
            {
             '': {
                'handlers': ['stderr']
                }  # root logger
            }
    }

    def __init__(self):
        log.setup_logging(self.DEFAULT_LOGGING)
        self.log = log.get_logger(self)
        self.log.debug('%r: Creating KotekanMaster Instance' % self)
        # KotekanMaster Parameters
        self.state = 'off'
        self.config = None
        self.start_time = None

        # Kotekan Client Objects
        self.kotekan = None

        # Logging Parameters
        # Absolute path name to this module
        self.PROGRAM = os.path.realpath(__file__)
        # TODO: Add a git hook here.
        self.GIT_VERSION = "DEV"
        self.log.info("program %s" % self.PROGRAM)
        self.log.info("version %s" % self.GIT_VERSION)

    def set_config(self, config):
        self.config = NameSpace(config)

    #####################################
    # Kotekan Methods                   #
    #####################################

    # These methods manage and operate kotekan clients
    @coroutine
    def create_kotekan_clients(self):
        # Create Kotekan REST clients
        self.nodes = {}
        nodes = self.config.nodes or {}
        result = [self.nodes, self.config]
        for node_name, node_params in nodes.items():
            #config = self.config.common_config.copy()
            #config.update(node_params)
            self.nodes[node_name] = KotekanAsyncRESTClient(name=node_name, **node_params)


    @coroutine
    def start_kotekan_clients(self):
        """
        Start Kotekan servers with the proper config.
        """
        conf = self.config
        yield [node.start(config=merge_dict(conf.common_config, conf.nodes[node_name]).as_dict()) for node_name, node in self.nodes.items()]

    @coroutine
    def stop_kotekan_clients(self):
        """
        Stop Kotekan Servers
        """
        yield [kotekan.stop() for kotekan in self.kotekan]

    @coroutine
    def ping_kotekan_clients(self):
        """
        Ping all kotekan clients.
        """
        conf = self.config
        yield [node.ping()for node_name, node in self.nodes.items()]

    @coroutine
    def status_kotekan_clients(self):
        result = yield [node.status() for node_name, node in self.nodes.items()]
        coroutine_return(result)

    #####################################
    # Kotekan Master Methods            #
    #####################################
    @coroutine
    def start_kotekan_master(self, config):
        """
        Start Kotekan clients defined in the provided config
        """
        # Store the kotekan config
        self.state = 'on'
        self.config = NameSpace(config)
        print 'STARTED KOTEKAN MASTER'
        yield self.create_kotekan_clients()
        #yield self.start_kotekan_clients()
        coroutine_return('KotekanMaster: start received, server now running.')


    @coroutine
    def stop_kotekan_master(self):
        """
        Stop Kotekan Master
        """
        if self.state == "on":
            self.state = "stopping"
            self.log.info("Stopping Kotekan Master")
            if self.kotekan != None:
                yield self.stop_kotekan_clients()
            #log.stop_logging(self.logging_handlers)
            #reap_cached_sockets()
        self.state = 'off'
        coroutine_return('KotekanMaster: stop received.')

    @coroutine
    def status_kotekan_master(self):
        result = "KotekanMaster State: " + self.state
        coroutine_return(result)

###############################################################################
# KotekanMaster Server                                                        #
###############################################################################

class KotekanMasterAsyncRESTServer(AsyncRESTServer):
    """
    Wraps KotekanMaster into a Async Restful Server which can recieve HTTP GET
    or POST requests and call the appropritate KotekanMaster method.
    """

    DEFAULT_PORT = 12048
    KOTEKAN_MASTER_HOSTNAME = None

    def __init__(self, address=KOTEKAN_MASTER_HOSTNAME,
                 port=DEFAULT_PORT, logging_params={}):
        """KotekanMaster Server Initialization
        """
        super(KotekanMasterAsyncRESTServer, self).__init__(
            address=address,
            port=port,
            heartbeat_string='KMs')
        self.last_time = None
        self.config = None
        self.kotekan_master = KotekanMaster()

    #####################################
    # Kotekan Client RESTful Endpoints  #
    #####################################
    @coroutine
    @endpoint('create-kotekan-clients')
    def create_kotekan_clients(self, handler): #, **config):
        """
        Create Kotekan Clients with the provided config.
        """
        print('%r: Received kotekan client create command' % self)
        self.log.info('%r: Received kotekan client create command' % self)
        #self.config = NameSpace(config)
        yield self.kotekan_master.create_kotekan_clients()
        coroutine_return('Kotekan clients Created')

    @coroutine
    @endpoint('status-kotekan-clients')
    def status_kotekan_clients(self, handler):
        result = yield self.kotekan_master.status_kotekan_clients()
        coroutine_return(result)

    @coroutine
    @endpoint('ping-kotekan-clients')
    def ping_kotekan_clients(self, handler):
        """
        Ping kotekan clients.
        """
        self.log.info('%r: Pinging kotekan clients...' % self)
        self.kotekan_master.ping_kotekanclients()
        coroutine_return('kotekan clients pinged.')

    @coroutine
    @endpoint('stop-kotekan-clients')
    def stop(self, handler):
    	"""
        Stop the Kotekan Master server
        """
        self.config = None
        coroutine_return('KotekanMaster server stopped.')

    #####################################
    # Kotekan Master RESTful Endpoints  #
    #####################################
    @coroutine
    @endpoint('status-kotekan-master')
    def status_kotekan_master(self, handler):
        result = yield self.kotekan_master.status_kotekan_master()
        coroutine_return(result)

    @coroutine
    @endpoint('start-kotekan-master')
    def start_kotekan_master(self, handler, **config):
        result = yield self.kotekan_master.start_kotekan_master(config)
        coroutine_return(result)

    @coroutine
    @endpoint('stop-kotekan-master')
    def stop_kotekan_master(self, handler):
        result = yield self.kotekan_master.stop_kotekan_master()
        coroutine_return(result)
###############################################################################
# Kotekan Master Client                                                       #
###############################################################################
class KotekanMasterAsyncRESTClient(AsyncRESTClient):
    """Async Restful Server for Kotekan Master
    """
    DEFAULT_PORT = KotekanMasterAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):
    	"""
        KotekanMaster Client Initialization
        """
        super(KotekanMasterAsyncRESTClient, self).__init__(
            hostname=hostname, port=port,
            server_class=KotekanMasterAsyncRESTServer,
            heartbeat_string='KMc')

    @coroutine
    def start(self, config):
        """
        If the remote kotekan server is not started, start it with
        the specified configuration.

        Parameters:
            config (str or dict): If a string, the configuration is
            loaded from the specified configuration file and name.
            if a dict, it is passed directly to the server.
        """
        self.log.info('%s: Starting KotekanMasterServer at %s:%i with config: %r' % (self, self.hostname, self.port, config))
        if isinstance(config, str):
            config = load_yaml_config(config)
        result = self.post('start-kotekan-master', **config)
        coroutine_return(result)

    @coroutine
    def stop(self):
        self.log.info('%s: Stoping KotekanMasterServer at %s:%i' % (self, self.hostname, self.port))
        result = yield self.get('stop-kotekan-master')
        coroutine_return(result)

    @coroutine
    def start_kotekan_clients(self):
        result = yield self.get('start-kotekan-clients')
        coroutine_return(result)

    @coroutine
    def stop_kotekan_clients(self):
        result = yield self.get('stop-kotekan-clients')
        coroutine_return(result)

    @coroutine
    def status_kotekan_clients(self):
        result = yield self.get('status-kotekan-clients')
        coroutine_return(result)


###############################################################################
# Command Line Interface to operate KotekanMaster Server                      #
###############################################################################
def main():
    """CLI for operating Kotekan Master
    """
    # TODO: Add Configuration Path Here
    # TODO: Add click based CLI similar to kotekan_master
    config = "config.yaml"
    log.setup_basic_logging('DEBUG')
    client, server = run_client(config,
                                KotekanMasterAsyncRESTServer,
                                KotekanMasterAsyncRESTClient,
                                object_name='KotekanMaster',
                                server_config_path = 'kotekan_master.servers')
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
