#!/usr/bin/env python

"""
RESTful Server & Client Module for KotekanMaster to initialize,
manage and operate the CHIME GPU Backend.
"""

# Imports
import os
import subprocess
import ch_acq.log as log
from ch_acq.pychfpga import NameSpace, load_yaml_config
from ch_acq.kotekan import KotekanAsyncRESTClient
from ch_acq.rest import AsyncRESTClient, AsyncRESTServer, endpoint
from ch_acq.rest import coroutine, coroutine_return, sleep, IOLoop

# REST Server/Client
from ch_acq.rest import RunSyncWrapper, SocketContext, run_client


class KotekanMaster(object):
    """
    KotekanMaster Object to manage individual Kotekan Objects which interact with
    the individual CHIME GPU nodes over RESTful API.
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
                '' : {
                    'handlers': ['stderr']
                    }
            }
    }

    def __init__(self):
        # Default Logger
        log.setup_logging(self.DEFAULT_LOGGING)
        self.log = log.get_logger(self)
        self.log.debug("%r: Creating KotekanMaster Class Instance", self)

        # Logging Parameters -- Absolute path name to this module
        self.program = os.path.realpath(__file__)

        # Tracked KotekanMaster Parameters
        # Valid state parameters: 'on', 'off', 'stopping'
        self.state = 'off'
        self.startup_config = None
        self.current_config = None

        # GPU nodes which are managed by KotekanMaster
        self.nodes = None

        # Revision Control Logging
        self.git_version = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
        self.log.info("program: %s", self.program)
        self.log.info("git ver: %s", self.git_version)

    def set_config(self, config):
        """
        Convert
        """
        self.current_config = NameSpace(config)

    # Kotekan Master Methods
    @coroutine
    def start_kotekan_master(self, config):
        """
        Start KotekanMaster and create a KotekanAsyncRESTClient for each nodes
        specified in the config file.
        """
        # Start KotekanMaster if the current state is off.
        if self.state == 'off':
            self.log.info('%s : KotekanMaster server starting.', self)
            # startup_config is never changed throughout the operation of
            # the array. All dynamic updates to the configuration are
            # applied against current_config
            self.startup_config = NameSpace(config)
            self.current_config = self.startup_config
            self.log.info('%s : Creating kotekan node clients.', self)
            yield self.create_node_clients()
            self.log.info('%s : kotekan node clients created.', self)
            self.state = 'on'
            coroutine_return('%s : KotekanMaster server started.', self)

        if self.state == 'on':
            coroutine_return('%s : KotekanMaster already running.', self)

    @coroutine
    def create_node_clients(self):
        """
        Create KotekanRESTClient to manage for each node listed in the
        startup_config file
        """
        self.nodes = {}
        nodes = self.current_config.nodes or {}
        for node_name, node_params in nodes.items():
            self.nodes[node_name] = KotekanAsyncRESTClient(name=node_name, **node_params)
        coroutine_return('Created clients for each kotekan node.')

    @coroutine
    def stop_kotekan_master(self):
        """
        Stop KotekanMaster and release node clients.
        """
        if self.state == "on":
            self.state = "stopping"
            self.log.info('%s : Stopping KotekanMaster.', self)
            if self.nodes is not None:
                self.nodes = None
            self.current_config = None
            # self.log.stop_logging(self.logging_handlers)
            # reap_cached_sockets()
        self.state = 'off'
        coroutine_return('%s : KotekanMaster server stopped.', self)

    @coroutine
    def status_kotekan_master(self):
        """
        KotekanMaster Status
        """
        result = {'state': self.state,
                  'current_config': self.current_config,
                  'watchdog': self.watchdog,
                  'watch_interval': self.watch_interval}
        coroutine_return(result)


    # Kotekan Methods
    #   These methods interact with the kotekan rest server.
    #   See https://github.com/kotekan/kotekan for more information about kotekan.
    @coroutine
    def start_kotekan(self):
        """
        Start the kotekan process on all nodes currently managed by kotekan_master.
        """
        conf = self.current_config
        yield [kotekan.start(config=merge_dict(conf.common_config,conf.nodes[node_name]).as_dict()) for node_name, kotekan in self.nodes.items()]

    @coroutine
    def stop_kotekan(self):
        """
        Stop the kotekan process on all nodes currently managed by kotekan_master.
        """
        yield [kotekan.stop() for kotekan in self.nodes]

    @coroutine
    def kotekan_status(self):
        """
        GET status of the kotekan process from all nodes currently
        managed by kotekan_master.
        """
        result = yield {node_name: kotekan.status()
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def kotekan_version(self):
        """
        GET Kotekan Version.
        """
        result = yield {node_name: kotekan.version()
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def kotekan_running_config(self):
        """
        GET current kotekan configuration.
        """
        result = yield {node_name: kotekan.running_config()
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def kotekan_config_md5sum(self):
        """
        GET md5sum of current running configuration.
        """
        result = yield {node_name: kotekan.config_md5sum()
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def update_gains(self, gains_dir):
        """
        POST the new gain directory for the beamformingKernel on all nodes
        currently managed by kotekan_master.
        """
        result = yield {node_name: kotekan.update_gains(gains_dir)
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def update_beam_offset(self, beam_offset):
        """
        POST the new beam_offset for frbNetworkProcess on all nodes currently
        managed by kotekan_master.
        """
        result = yield {node_name: kotekan.update_beam_offset(beam_offset)
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    # Node Methods
    #   These methods interact the node hardware and have no access to the kotekan
    #   process endpoints.
    @coroutine
    def ping_nodes(self):
        """
        Ping all kotekan clients currently managed by KotekanMaster
        """
        yield [node.ping()for node_name, node in self.nodes.items()]

# KotekanMaster Asynchronous RESTful Server
class KotekanMasterAsyncRESTServer(AsyncRESTServer):
    """
    Asynchronous RESTful Server for KotekanMaster

    Wraps KotekanMaster into a Async Restful Server which can recieve HTTP GET,
    POST and PUT requests and call the appropriate KotekanMaster class functions
    to perform the required task.
    """
    DEFAULT_PORT = 12048
    KOTEKAN_MASTER_HOSTNAME = None
    WATCHDOG = True
    WATCH_INTERVAL = 30

    def __init__(self, address=KOTEKAN_MASTER_HOSTNAME, port=DEFAULT_PORT, logging_params={},
                 watchdog=WATCHDOG, watch_interval=WATCH_INTERVAL):
        """
        KotekanMaster Server Initialization
        """
        super(KotekanMasterAsyncRESTServer, self).__init__(
            address=address,
            port=port,
            heartbeat_string='KMs')
        self.log.info("KotekanMasterAsyncRESTServer: %s:%s", str(address), str(port))
        self.current_config = None
        self.kotekan_master = KotekanMaster()
        self.watchdog = watchdog
        self.watch_interval = watch_interval

    # KotekanMaster RESTful Endpoints
    #   API to interact with KotekanMaster.
    #   These endpoints do not interact with kotekan process or the nodes.
    @coroutine
    @endpoint('start-kotekan-master')
    def start_kotekan_master(self, handler, **config):
        """
        Initialization KotekanMaster
        """
        result = yield self.kotekan_master.start_kotekan_master(config)
        coroutine_return(result)

    @coroutine
    @endpoint('stop-kotekan-master')
    def stop_kotekan_master(self, handler):
        """
        Stop KotekanMaster
        """
        result = yield self.kotekan_master.stop_kotekan_master()
        coroutine_return(result)

    @coroutine
    @endpoint('status-kotekan-master')
    def status_kotekan_master(self, handler):
        """
        Get the current status of KotekanMaster
        """
        result = yield self.kotekan_master.status_kotekan_master()
        coroutine_return(result)

    @coroutine
    @endpoint('validate-running-config')
    def validate_running_configuration(self, handler):
        """
        Validate that all nodes in the array are running the same current config.
        """
        running_configs = yield self.kotekan_master.kotekan_running_config()
        unique_configs = set(running_configs.values())
        if len(unique_configs) != 1:
            coroutine_return(True)
        else:
            coroutine_return(False)

    @coroutine
    @endpoint('validate-checksum')
    def validate_checksum(self, handler):
        """
        Validate the md5checksum for all running kotekan configs against the
        md5checksum of the self.current_config
        """
        result = "Not Implemented."
        coroutine_return(result)

    # Kotekan RESTful Endpoints
    #   These endpoints interact with the kotekan process running on all the nodes.
    #   There are two types of Kotekan RESTful endpoints
    #       Parameter Endpoints: Dynamically tracked, have a corresponding config paramter
    #       Operation Endpoints: Not tracked, time dependent calls, no corresponding
    #                            config parameter

    # Operation Endpoints
    @coroutine
    @endpoint('start-kotekan')
    def start_kotekan(self, handler):
        """
        Start kotekan process on all nodes with current_config
        """
        result = yield self.kotekan_master.start_kotekan()
        coroutine_return(result)

    @coroutine
    @endpoint('stop-kotekan')
    def stop_kotekan(self, handler):
        """
        Stop the kotekan process on all nodes.
        """
        result = yield self.kotekan_master.stop_kotekan()
        coroutine_return(result)

    @coroutine
    @endpoint('kotekan-status')
    def kotekan_status(self, handler):
        """
        GET status of all kotekan from all nodes.
        """
        result = yield self.kotekan_master.kotekan_status()
        coroutine_return(result)

    @coroutine
    @endpoint('kotekan-version')
    def kotekan_version(self, handler):
        """
        GET version of kotekan process from all nodes.
        """
        result = yield self.kotekan_master.kotekan_version()
        coroutine_return(result)

    @coroutine('kotekan-running-config')
    def kotekan_running_config(self, handler):
        """
        Queries the current running configuration from the kotekan process.
        """
        result = yield self.kotekan_master.kotekan_running_config()
        coroutine_return(result)

    @coroutine
    @endpoint('kotekan-config-md5sum')
    def kotekan_config_md5sum(self, handler):
        """
        Queries the current kotekan for the MD5 hash of the running configuration.
        """
        result = yield self.kotekan_master.kotekan_config_md5sum()
        coroutine_return(result)

    # Parameter Endpoints.
    @coroutine
    @endpoint('update-gains')
    def update_gains(self, handler, gains_dir):
        """
        Update the gain_dir on all nodes.
        """
        result = yield self.kotekan_master.update_gains(gains_dir)
        coroutine_return(result)

    @coroutine
    @endpoint('update-beam-offset')
    def update_beam_offset(self, handler, beam_offset):
        """
        Update the beam_offset endpoint on all nodes.
        """
        result = yield self.kotekan_master.update_beam_offset(beam_offset)
        coroutine_return(result)

    @coroutine
    @endpoint('update-pulsar-pointing')
    def update_pulsar_pointing(self, handler, pulsar_pointing):
        """
        Update pulsar pointing
        """
        result = "Not Implemented."
        coroutine_return(result)

    # Node RESTful Endpoints
    #   These endpoints interact with the hardware in the GPU SeaCans.
    @coroutine
    @endpoint('ping-nodes')
    def ping_nodes(self, handler):
        """
        Ping kotekan nodes.
        """
        self.log.info('%r: Pinging kotekan nodes...', self)
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

# KotekanMaster Asynchronous RESTful Client
class KotekanMasterAsyncRESTClient(AsyncRESTClient):
    """Async Restful Server for Kotekan Master
    """
    # Default Port for KotekanMaster as assigned in bao.phas wikipage.
    # TODO: Add a link to the wikipedia page.
    DEFAULT_PORT = KotekanMasterAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):
        """
        KotekanMaster Client Initialization
        """
        super(KotekanMasterAsyncRESTClient, self).__init__(
            hostname=hostname, port=port,
            server_class=KotekanMasterAsyncRESTServer,
            heartbeat_string='KMc')

    # Kotekan Master Routines
    # These routines are not executed on any kotekan node but are rather
    # specific to the current state of KotekanMaster
    @coroutine
    def start(self, config):
        """
        Start a KotekanMaster process with the specified configuration.

        Parameters:
            config (str or dict): If a string, the configuration is
            loaded from the specified configuration file and name.
            if a dict, it is passed directly to the server.
        """
        self.log.info('%s: Starting KotekanMasterServer at %s:%i with config:%r',
                      self, self.hostname, self.port, config)
        if isinstance(config, str):
            config = load_yaml_config(config)
        result = self.post('start-kotekan-master', **config)
        coroutine_return(result)

    @coroutine
    def stop(self):
        """
        Stop kotekan_master from managing any nodes.
        """
        self.log.info('%s: Stoping KotekanMasterServer at %s:%i',
                      self, self.hostname, self.port)
        result = yield self.get('stop-kotekan-master')
        coroutine_return(result)

    @coroutine
    def status(self):
        """
        Current status of the kotekan_master.
        """
        result = yield self.get('status-kotekan-master')
        coroutine_return(result)

    # Kotekan Routines
    # Routine endpoints which interact with kotekan nodes.
    @coroutine
    def start_kotekan(self):
        """
        Start kotekan on all nodes with the current configuration.
        """
        result = yield self.get('start-kotekan')
        coroutine_return(result)

    @coroutine
    def stop_kotekan(self):
        """
        Stop kotekan on all nodes.
        """
        result = yield self.get('stop-kotekan')
        coroutine_return(result)

    @coroutine
    def kotekan_status(self):
        """
        Get status of kotekan from all nodes.
        """
        result = yield self.get('kotekan-status')
        coroutine_return(result)

    @coroutine
    def kotekan_version(self):
        """
        Kotekan Version
        """
        result = yield self.get('kotekan-version')
        coroutine_return(result)

    @coroutine
    def kotekan_running_config(self):
        """
        Current running kotekan configuration.
        """
        result = yield self.get('kotekan-running-config')
        coroutine_return(result)

    @coroutine
    def kotekan_config_md5sum(self):
        """
        Returns an MD5 hash of the config file
        """
        result = yield self.get('kotekan-config-md5sum')
        coroutine_return(result)

    # Parameter Endpoints
    #   All parameter endpoints have a corresponding value in the kotekan config.
    @coroutine
    def update_gains(self, gains_dir):
        """
        Update FRB Gains directory on all nodes.
        """
        result = yield self.post('update-gains', gains_dir)
        coroutine_return(result)

    @coroutine
    def update_beam_offset(self, beam_offset):
        """
        Update FRB Beam Offset on all nodes.
        """
        result = yield self.post('update-beam-offset', beam_offset)
        coroutine_return(result)

    @coroutine
    def config_checksum(self):
        """
        Get the md5sum of the current running configuration
        """
        result = 'Not Implemented.'
        coroutine_return(result)

    # Node Routines
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

# Command Line Interface to operate KotekanMaster Server
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
    kotekan_master = None
    if server:
        kotekan_master = RunSyncWrapper(server.kotekan_master)
    return client, server, kotekan_master

# Command Line Instantiation of KotekanMaster
if __name__ == '__main__':
    """
    Kotekan Master Command Line Instantiation
    """
    CLIENT, SERVER, KM = main()
