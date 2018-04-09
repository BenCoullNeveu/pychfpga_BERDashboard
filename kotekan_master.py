#!/usr/bin/env python

"""
RESTful Server & Client Module to run KotekanMaster object used to initialize
and operate the CHIME GPU Backend.
"""

# Imports
import sys
import os
import subprocess
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
        self.log.debug('%r: Creating KotekanMaster Class Instance' % self)

        # KotekanMaster Parameters
        self.state = 'off'
        self.config = None
        self.startup_config = None
        self.current_config = None
        # GPU nodes which are managed by Kotekan Client Objects
        self.nodes = None
        # Logging Parameters -- Absolute path name to this module
        self.PROGRAM = os.path.realpath(__file__)
        # TODO: Add a git hook here.
        self.GIT_VERSION = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'])
        self.log.info("program: %s" % self.PROGRAM)
        self.log.info("git ver: %s" % self.GIT_VERSION)

    def set_config(self, config):
        self.config = NameSpace(config)

    #####################################
    # Kotekan Master Methods            #
    #####################################
    @coroutine
    def start_kotekan_master(self, config):
        """
        Start KotekanMaster and create node clients from config file.
        """
        # Store the kotekan config
        if self.state == 'off':
            self.log.info('%s : KotekanMaster server starting.' % self)
            self.state = 'on'
            self.config = NameSpace(config)
            self.current_config = self.config
            self.startup_config = self.config
            self.log.info('%s : Creating kotekan node clients.' % self)
            yield self.create_node_clients()
            self.log.info('%s : Kotekan node clients created.' % self)
            coroutine_return('%s : KotekanMaster server started.' % self)

        if self.state == 'on':
            coroutine_return('%s : KotekanMaster already running.' % self)

    @coroutine
    def create_node_clients(self):
        # Create RESTClients to manage each kotekan process & node.
        self.nodes = {}
        nodes = self.config.nodes or {}
        result = [self.nodes, self.config]
        for node_name, node_params in nodes.items():
            self.nodes[node_name] = KotekanAsyncRESTClient(name=node_name,
                                                           **node_params)
        coroutine_return('Created clients for each kotekan node.')

    @coroutine
    def stop_kotekan_master(self):
        """
        Stop KotekanMaster and release node clients.
        """
        if self.state == "on":
            self.state = "stopping"
            self.log.info('%s : Stopping KotekanMaster.' % self)
            if self.nodes is not None:
                self.nodes = None
            self.current_config = None
            # log.stop_logging(self.logging_handlers)
            # reap_cached_sockets()
        self.state = 'off'
        coroutine_return('%s : KotekanMaster server stopped...' % self)

    @coroutine
    def status_kotekan_master(self):
        result = {'state': self.state,
                  'current_config': self.current_config}
        coroutine_return(result)

    #####################################
    # Kotekan Methods                   #
    #####################################
    @coroutine
    def start_kotekan(self):
        """
        Start Kotekan servers with the current config.
        """
        conf = self.current_config
        yield [kotekan.start(config=merge_dict(conf.common_config, conf.nodes[node_name]).as_dict()) for node_name, kotekan in self.nodes.items()]

    @coroutine
    def stop_kotekan(self):
        """
        Stop Kotekan Servers
        """
        yield [kotekan.stop() for kotekan in self.nodes]

    @coroutine
    def status_kotekan(self):
        result = yield {node_name: kotekan.status()
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def update_gains(self, gains_dir):
        result = yield {node_name: kotekan.update_gains(gains_dir)
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def update_beam_offset(self, beam_offset):
        result = yield {node_name: kotekan.update_beam_offset(beam_offset)
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    #####################################
    # Node Methods                      #
    #####################################
    @coroutine
    def ping_nodes(self):
        """
        Ping all kotekan clients.
        """
        conf = self.config
        yield [node.ping()for node_name, node in self.nodes.items()]

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
        self.config = None
        self.kotekan_master = KotekanMaster()

    #####################################
    # Kotekan Master RESTful Endpoints  #
    #####################################

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

    @coroutine
    @endpoint('status-kotekan-master')
    def status_kotekan_master(self, handler):
        result = yield self.kotekan_master.status_kotekan_master()
        coroutine_return(result)

    #####################################
    # Kotekan Client RESTful Endpoints  #
    #####################################
    # @coroutine
    # @endpoint('create-kotekan-clients')
    # def create_kotekan_clients(self, handler):
    #     """
    #     Create Kotekan Clients with the provided config.
    #     """
    #     print('%r: Received kotekan client create command' % self)
    #     self.log.info('%r: Received kotekan client create command' % self)
    #     # self.config = NameSpace(config)
    #     yield self.kotekan_master.create_kotekan_clients()
    #     coroutine_return('Kotekan clients Created')

    @coroutine
    @endpoint('start-kotekan')
    def start_kotekan(self, handler):
        """
        Start Kotekan Process
        """
        result = yield self.kotekan_master.start_kotekan()
        coroutine_return(result)

    @coroutine
    @endpoint('stop-kotekan')
    def stop(self, handler):
        """
        Stop the Kotekan Process
        """
        result = yield self.kotekan_master.stop_kotekan()
        coroutine_return(result)

    @coroutine
    @endpoint('status-kotekan')
    def status_kotekan(self, handler):
        result = yield self.kotekan_master.status_kotekan()
        coroutine_return(result)

    @coroutine
    @endpoint('update-gains')
    def update_gains(self, handler, gains_dir):
        result = yield self.kotekan_master.update_gains(gains_dir)
        coroutine_return(result)

    @coroutine
    @endpoint('update-beam-offset')
    def update_beam_offset(self, handler, beam_offset):
        result = yield self.kotekan_master.update_beam_offset(beam_offset)
        coroutine_return(result)

    #####################################
    # Node RESTful Endpoints            #
    #####################################

    @coroutine
    @endpoint('ping-nodes')
    def ping_nodes(self, handler):
        """
        Ping kotekan nodes.
        """
        self.log.info('%r: Pinging kotekan nodes...' % self)
        result = self.kotekan_master.ping_nodes()
        coroutine_return(result)

    @coroutine
    @endpoint('boot-nodes')
    def boot_nodes(self, handler):
        """
        Boot kotekan nodes
        """
        result = 'Not Implemented.'
        coroutine_return(result)

    @coroutine
    @endpoint('shutdown-nodes')
    def shutdown_nodes(self, handler):
        """
        Shutdown kotekan nodes
        """
        result = 'Not Implemented.'
        coroutine_return(result)

    @coroutine
    @endpoint('reboot-nodes')
    def reboot_nodes(self, handler):
        """
        Reboot kotekan nodes
        """
        result = 'Not Implemented.'
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

    ###########################
    # Kotekan Master Routines #
    ###########################

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
    def status(self):
        result = yield self.get('status-kotekan-master')
        coroutine_return(result)

    ###########################
    # Kotekan Routines        #
    ###########################
    @coroutine
    def start_kotekan(self):
        result = yield self.get('start-kotekan')
        coroutine_return(result)

    @coroutine
    def stop_kotekan(self):
        result = yield self.get('stop-kotekan')
        coroutine_return(result)

    @coroutine
    def status_kotekan(self):
        result = yield self.get('status-kotekan')
        coroutine_return(result)

    @coroutine
    def update_gains(self, gains_dir):
        result = yield self.post('update-gains', gains_dir)
        coroutine_return(result)

    @coroutine
    def update_beam_offset(self, beam_offset):
        result = yield self.post('update-beam-offset', beam_offset)
        coroutine_return(result)

    ###########################
    # Node Routines           #
    ###########################
    @coroutine
    def ping_nodes(self):
        result = yield self.get('ping-nodes')
        coroutine_return(result)

    @coroutine
    def boot_nodes(self):
        result = yield self.get('boot-nodes')
        coroutine_return(result)

    @coroutine
    def shutdown_nodes(self):
        result = yield self.get('shutdown-nodes')
        coroutine_return(result)

    @coroutine
    def reboot_nodes(self):
        result = yield self.get('restart-nodes')
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
                                server_config_path='kotekan_master.servers')
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
