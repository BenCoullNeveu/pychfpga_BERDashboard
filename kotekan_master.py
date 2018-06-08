#!/usr/bin/env python

"""
RESTful Server & Client Module for KotekanMaster to initialize,
manage and operate the CHIME GPU Backend.
"""

# Imports
import os
import subprocess
import time
import requests
import log
from pychfpga import NameSpace, load_yaml_config, merge_dict
from kotekan import KotekanAsyncRESTClient
from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return, sleep, IOLoop

# REST Server/Client
from rest import RunSyncWrapper, SocketContext, run_client


# KotekanMaster Class
class KotekanMaster(object):
    """
    KotekanMaster class to manage individual Kotekan Objects which interact
    with the CHIME GPU nodes over RESTful API.
    """

    # Logging setup when no config file is provided.
    DEFAULT_LOGGING = {
        'handlers':
            {
                'stderr': {
                    'class': 'logging.StreamHandler',
                    'level': 'INFO'
                    }
            },
        'loggers':
            {
                '': {
                    'handlers': ['stderr']
                    }
            }
    }

    def __init__(self):
        # Default Logger
        log.setup_logging(self.DEFAULT_LOGGING)
        self.log = log.get_logger(self)
        self.log.info("%r: Creating KotekanMaster Class Instance", self)

        # Logging Parameters -- Absolute path name to this module
        self.program = os.path.realpath(__file__)

        # Tracked KotekanMaster Parameters
        # Valid state parameters: 'on', 'off', 'stopping'
        self.state = 'off'
        self.start_time = None
        self.startup_config = None
        self.current_config = None

        # KotekanAsyncRESTClient instances which are managed by KotekanMaster
        # Format {{node_name: KotekanMasterObj}}
        self.nodes = {}
        # KotekanAsyncRESTClient instances blacklisted
        self.blacklist_nodes = []

        # Watchdog parameters
        self.watchdog_enabled = False
        self.watchdog_interval = 10
        self.watchdog_stats = {}

        # GPS Parameters
        self.gps_status = {}
        self.gps_server = 'http://carillon.chime:54321/get-frame-time'
        self.gps_time = {}

        # Revision Control Logging
        self.git_version = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
        self.log.info("%s : Program : %s", self, self.program)
        self.log.info("%s : Git Ver : %s", self, self.git_version)

    # Helper Methods
    #   NOTE: These methods are not coroutines!
    def set_config(self, config):
        """
        Convert list or dict to an object with attributes
        """
        self.current_config = NameSpace(config)

    @coroutine
    def _get_gps_time(self):
        """
        Get gps time for chime master to sync the kotekan nodes
        """
        gps_request = requests.get(self.gps_server)
        # Check if the request worked out.
        if gps_request.raise_for_status() is None:
            self.gps_time = gps_request.json()
            self.log.info('%s : successfully retrieved gps_time', self)
            coroutine_return(result="PASSED")
        else:
            self.log.error('%s : failed to get gps time with exception:%s',
                           self, gps_request.raise_for_status())
            coroutine_return(result="FAILED")

    # KotekanMaster Methods
    @coroutine
    def start_kotekan_master(self, config):
        """
        Start KotekanMaster and create a KotekanAsyncRESTClient for each node
        specified in the config file.
        """
        # Start KotekanMaster if the current state is off.
        if self.state == 'off':
            self.log.info('%s : KotekanMaster server starting ...', self)
            self.start_time = time.time()
            self.isotime = time.strftime("%Y%m%dT%H%M%SZ",
                                         time.gmtime(self.start_time))
            self.localtime = time.strftime("%Y/%m/%d %H:%M:%S",
                                           time.localtime(self.start_time))
            self.log.info('%s : Start Time : %s', self, self.localtime)
            # startup_config is never changed throughout the operation of
            # the array. All dynamic updates to the configuration are
            # applied against the current_config
            self.startup_config = NameSpace(config)
            self.current_config = self.startup_config
            # Setup logging paths
            self.run_name = self.startup_config.run_name % dict(
                    isotime=self.isotime,
                    localtime=self.localtime,
                    corr_name=self.startup_config.corr_name)
            self.log.info("%s : Run Name : %s", self, self.run_name)
            str_args = dict(isotime=self.isotime,
                            corr_name=self.startup_config.corr_name,
                            run_name=self.run_name)
            self.run_folder = self.startup_config.run_folder % str_args
            self.run_folder = os.path.expanduser(self.run_folder)
            self.log.info("%s : Run Folder : %s", self, self.run_folder)
            self.current_folder = os.path.expanduser(self.startup_config.current_folder % str_args)
            self.log.info("%s : Current Folder : %s", self, self.current_folder)
            # Create run folders
            try:
                os.makedirs(self.run_folder)
            except OSError:
                errmsg = "Could not create directory '%s'!" % self.run_folder
                self.log.critical(errmsg)
                raise RuntimeError(errmsg)

            # Make a symlink to the run folder
            if hasattr(os, 'symlink'):
                try:
                    os.remove(self.current_folder)
                except OSError as e:
                    self.log.warn(
                        "%r : Could not remove current symlink '%s'. The error is \n%s" %
                        (self, self.current_folder, e))
                try:
                    os.symlink(self.run_folder, self.current_folder)
                except OSError as e:
                    self.log.warning(
                        "%r : Could not create a symlink '%s' to the run folder '%s'. The error is:\n%s" %
                        (self, self.current_folder, self.run_folder, e))
            # Setting up logging handlers
            self.logging_handlers = log.setup_logging(
                        self.startup_config.logging.dict_config,
                        self.startup_config.logging.log_levels,
                        base_package_name=self.startup_config.logging.base_package_name,
                        actual_package_name=__name__.rpartition('.')[0],
                        script_name=self.startup_config.logging.script_name,
                        run_folder=self.run_folder % str_args )
            self.log.info('%r : Logging Configured.'% self)
            # Get gps_time from the gps_server
            self.log.info('%s : Retreiving GPS Time ...', self)
            self.gps_status = yield self._get_gps_time()

            # TODO: Put this is a sysexit() try/Except.
            # Append current_config with a new key called gps_time

            self.current_config.common_config.gps_time = self.gps_time
            self.log.info('%s : Creating Kotekan Node Clients ...', self)
            yield self._create_node_clients()
            self.log.info('%s : Kotekan Clients Created.', self)
            self.state = 'on'
            self.log.info('%s : KotekanMaster State : %s', self, self.state)
            coroutine_return('KotekanMaster Server Started.')
        # If already running, do nothing.
        if self.state == 'on':
            self.log.info('%s : KotekanMaster State : %s', self, self.state)
            coroutine_return('KotekanMaster Already Running!')

    @coroutine
    def _create_node_clients(self):
        """
        Create KotekanAsyncRESTClient instances for each GPU node listed in the
        startup_config

        This routine is only called at startup and is not accessible as an
        endpoint.
        """
        self.nodes = {}
        # This actually points to current_config.servers.default_server.nodes
        # in the kotekan_config.yaml
        nodes = self.current_config.nodes or {}
        for node_name, node_params in nodes.items():
            self.nodes[node_name] = KotekanAsyncRESTClient(name=node_name,
                                                           **node_params)
        self.log.info('%s : Created kotekan clients for nodes: %s',
                      self, self.nodes.keys())
        coroutine_return({})

    @coroutine
    def stop_kotekan_master(self):
        """
        Stop KotekanMaster and release node clients.
        """
        if self.state == "on":
            self.state = "stopping"
            self.log.info('%s : KotekanMaster State : %s', self, self.state)
            if self.nodes is not None:
                self.nodes = None
            self.current_config = None
            reap_cached_sockets()
            # self.log.stop_logging(self.logging_handlers)

        self.state = 'off'
        self.log.info('%s : KotekanMaster State : %s', self, self.state)
        coroutine_return('KotekanMaster Server Stopped.')

    @coroutine
    def status_kotekan_master(self):
        """
        Current status of services KotekanMaster Status
        """
        result = {'state': self.state,
                  'current_config': self.current_config.as_dict(),
                  'nodes': self.nodes.keys(),
                  'blacklist_nodes': self.blacklist_nodes,
                  'watchdog_enabled': self.watchdog_enabled,
                  'watchdog_interval': self.watchdog_interval,
                  'watchdog_stats': self.watchdog_stats,
                  'gps_server': self.gps_server,
                  'gps_status': self.gps_status,
                  'gps_time': self.gps_time,
                  'git_version': self.git_version,
                  'start_time': time.strftime("%Y/%m/%d %H:%M:%S",
                                              time.localtime(self.start_time))
                  }
        coroutine_return(result)

    @coroutine
    def whitelist_node(self, node_list):
        """
        Whitelist Node

        Parameters
        ----------

        """
        self.log.info('%s : Whitelist Nodes Executed : %s', self, node_list)
        whitelisted_nodes = []
        for node_name in node_list.strip('[').strip(']').split(','):
            # Find a node_config or use defaults.
            try:
                node_config = self.current_config.nodes.as_dict()[node_name]
                self.log.info('%s : Found config for node %s', self, node_name)
            except:
                node_config = {'hostname': node_name, 'port': 12048}
                self.log.info('%s : Unable to find config for node %s,\
                               using  defaults', self, node_name)
            # Start a Kotekan Client for the node.
            if node_name not in self.nodes.keys():
                self.nodes[node_name] = KotekanAsyncRESTClient(
                                            name=node_name,
                                            **node_config)
                self.log.info('%s : Whitelisted Node: %s', self, node_name)
            # Remove the node from the blacklist
            if node_name in self.blacklist_nodes:
                self.blacklist.remove(node_name)
                self.log.info('%s : Removed node %s from Blacklist',
                              self, node_name)
            # Keep track of newly whiteliested nodes.
            whitelisted_nodes.append(node_name)
        coroutine_return(whitelisted_nodes)

    @coroutine
    def blacklist_node(self, node_list):
        """
        Blacklist Node
        """
        for node_name, kotekan in self.nodes.items():
            if node_name in node_list:
                if node_name not in self.blacklist_nodes:
                    self.log.info('%s : Blacklisted Node : %s',
                                  self, node_name)
                    self.log.info('%s : Stopping Kotekan on %s',
                                  self, node_name)
                    yield kotekan.kill()
                    self.blacklist_nodes.append(node_name)
                    self.nodes.pop(node_name)
        coroutine_return(self.blacklist_nodes)

    # KotekanMaster Watchdog Methods
    @coroutine
    def start_watchdog(self):
        """
        Start Watchdog
        """
        self.watchdog_enabled = True
        self.watchdog_interval = 60
        self.log.info('%s : KotekanMaster Watchdog Enabled', self)
        self.log.info('%s : KotekanMaster Watchdog Interval : %s seconds',
                      self, self.watchdog_interval)
        coroutine_return(result='KotekanMaster Watchdog Enabled')

    @coroutine
    def stop_watchdog(self):
        """
        Stop Watchdog
        """
        self.watchdog_enabled = False
        self.log.info('%s : KotekanMaster Watchdog Disabled', self)
        coroutine_return('KotekanMaster Watchdog Disabled')

    @coroutine
    def update_watchdog_stats(self, restart_list):
        """
        Statistics for KotekanMaster Watchdog

        Parameters
        ----------
            restart_list : dict-type

        Returns
        -------
            watchdog_stats : dict-type
                {node_name: number_of_restarts}
        """
        for node in restart_list:
            if node not in self.watchdog_stats.keys():
                self.watchdog_stats.update({node: 0})
            self.watchdog_stats[node] += 1
        coroutine_return(self.watchdog_stats)

    # KotekanMaster Validation Routines
    @coroutine
    def validate_config(self):
        running_configs = yield self.kotekan_running_config()
        unique_configs = set(running_configs.values())
        if len(unique_configs) != 1:
            self.log.error('%s : KotekanMaster Config Validation Error')
            self.log.error('%s : %s configs discovered.',
                           self, str(len(unique_configs)))
            result = 'FAILED'
        else:
            result = 'PASSED'
        coroutine_return(result)

    @coroutine
    def validate_checksum(self):
        config_md5sum = yield self.kotekan_master.kotekan_config_md5sum()
        unique_checksums = set(config_md5sum.values())
        if len(unique_checksums) != 1:
            self.log.error('%s : KotekanMaster Checksum Validation Error')
            self.log.error('%s : %s checksums discovered.',
                           self, str(len(unique_checksums)))
            result = 'FAILED'
        else:
            self.log.info('%s : KotekanMaster Checksum Passed')
            result = 'PASSED'
        coroutine_return(result)

    # Kotekan Methods
    #   These methods interact with the kotekan rest server.
    #   See https://github.com/kotekan/kotekan for more information.

    # Operation Based Endpoints
    @coroutine
    def start_kotekan(self):
        """
        Start the kotekan process on all nodes.
        """
        yield {node_name: kotekan.start(
            config=self.current_config.common_config.as_dict())
                for node_name, kotekan in self.nodes.items()}

    @coroutine
    def restart_kotekan(self, node_status):
        """
        Start specific kotekan nodes from the node_status which are not running

        NOTE: This method is not visible as a RESTful endpoint.

        Parameters
        ----------
        Input:
            node_status : dict-type
                {'node_name' : {'running' : boolean }}
        Returns:
            restart_list : list-type
                {'node_1', 'node_2', ... 'node_N'}
        """
        restart_list = []
        for node_name, status in node_status.items():
            if status['running'] is False:
                restart_list.append(node_name)
        self.log.info('Watchdog Restart List: %s', restart_list)
        # Start the nodes
        for node_name, kotekan in self.nodes.items():
            if node_name in restart_list:
                self.log.info('Restart kotekan on %s', node_name)
                kotekan.start(
                    config=self.current_config.common_config.as_dict())
        coroutine_return(restart_list)

    @coroutine
    def stop_kotekan(self):
        """
        Stop the kotekan process on all nodes.
        """
        yield {node_name: kotekan.stop()
               for node_name, kotekan in self.nodes.items()}

    @coroutine
    def kill_kotekan(self):
        """
        Kill the kotekan process on all nodes.
        """
        yield {node_name: kotekan.kill()
               for node_name, kotekan in self.nodes.items()}

    @coroutine
    def kotekan_status(self):
        """
        GET status of the kotekan process from all nodes currently
        managed by kotekan_master.

        Returns: dict
        {"node_name" : {"running": Boolean}}
        """
        result = yield {node_name: kotekan.status()
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def kotekan_version(self):
        """
        GET Kotekan Version.

        Parameters
        ----------
            None

        Returns
        -------
            kotekan_version : dict-type
            { "node_name" : {"available_processes": ["p1","p2", ... "pN"],
                             "branch": "master",
                             "cmake_build_settings" : "BUILD_OPTIONS",
                             "git_commit_hash": "b1ce8aecf",
                             "kotekan_version": "2.3"
                            }
            }
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

        Returns
            config_md5sum : dict-types
                {node_name:md5sum ...}
        """
        result = yield {node_name: kotekan.config_md5sum()
                        for node_name, kotekan in self.nodes.items()}
        self.log.debug(result)
        coroutine_return(result)

    # Parameter Based Endpoints
    @coroutine
    def update_gains(self, gains_dir):
        """
        POST the new gain directory for the beamformingKernel on all nodes
        currently managed by kotekan_master.
        """
        self.log.info('%s : Parameter gains_dir update: %s', self, gains_dir)
        self.current_config.common_config.gpu.gains_dir = gains_dir
        result = yield {node_name: kotekan.update_gains(gains_dir)
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    @coroutine
    def update_beam_offset(self, beam_offset):
        """
        POST the new beam_offset for frbNetworkProcess on all nodes currently
        managed by kotekan_master.
        """
        self.log.info('%s : Parameter beam_offset update: %s', self, beam_offset)
        self.current_config.common_config.frb.network.beam_offset = beam_offset
        result = yield {node_name: kotekan.update_beam_offset(beam_offset)
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)

    # Node Methods
    #   These methods interact the node hardware and have no access to the
    #   kotekan process endpoints.
    @coroutine
    def ping_nodes(self):
        """
        Ping all kotekan clients currently managed by KotekanMaster
        """
        result = yield {node_name: kotekan.ping()
                        for node_name, kotekan in self.nodes.items()}
        coroutine_return(result)


# KotekanMaster Asynchronous RESTful Server
class KotekanMasterAsyncRESTServer(AsyncRESTServer):
    """
    Asynchronous RESTful Server for KotekanMaster

    Wraps KotekanMaster into a Async Restful Server which can recieve HTTP GET,
    POST and PUT requests and call the appropriate KotekanMaster class
    functions to perform the required task.
    """
    # Defaul parameters
    KOTEKAN_MASTER_HOSTNAME = 'localhost'
    DEFAULT_PORT = 54323

    def __init__(self,
                 address=KOTEKAN_MASTER_HOSTNAME,
                 port=DEFAULT_PORT):
        """
        KotekanMaster Server Initialization
        """
        super(KotekanMasterAsyncRESTServer, self).__init__(
            address=address,
            port=port,
            heartbeat_string='KMs',
            heartbeat_period=1000)
        self.log.info("KotekanMasterAsyncRESTServer: %s:%s",
                      str(address), str(port))
        self.current_config = None
        self.kotekan_master = KotekanMaster()
        # Start the watchdog loop.
        # NOTE: This routine only starts the loop, and not the watchdog actions
        # by default. You need to execute `start-watchdog` endpoint for that.
        self._watchdog()

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
    @endpoint('start-watchdog')
    def start_watchdog(self, handler):
        """
        Start Kotekan Watchdog
        """
        result = yield self.kotekan_master.start_watchdog()
        coroutine_return(result)

    @coroutine
    def _watchdog(self):
        """
        KotekanMaster Watchdog Loop

        NOTE: This loop runs prepetually. To enable and disable the watchdog,
        execute the start-watchdog and stop-watchdog endpoints.
        """
        while True:
            # Check if the watchdog is currently enabled.
            if self.kotekan_master.watchdog_enabled:
                print "Watching Running ..."
                # Run get status from each node
                node_status = yield self.kotekan_master.kotekan_status()
                # Execute restarts for nodes with running==false
                restart_list = yield self.kotekan_master.restart_kotekan(
                                        node_status)
                # Update watchdog statistics
                watchdog_stats = yield self.kotekan_master.update_watchdog_stats(restart_list)
                self.log.info('%s : KotekanMaster Watchdog Stats', self)
                self.log.info('%s : %s', self, watchdog_stats)
                self.log.info('%s : Watchdog sleeping for %s seconds',
                              self, self.kotekan_master.watchdog_interval)

            # Wait for the watchdog_interval
            yield sleep(self.kotekan_master.watchdog_interval)

    @coroutine
    @endpoint('stop-watchdog')
    def stop_watchdog(self, handler):
        """
        Stop Kotekan Watchdog
        """
        result = yield self.kotekan_master.stop_watchdog()
        coroutine_return(result)

    @coroutine
    @endpoint('blacklist-node')
    def blacklist_node(self, handler, node_list):
        """
        Blacklist a node[s] from being actively managed by KotekanMaster

        curl -d "node_list=['csDg5']" -X POST http://localhost:54323/blacklist-node
        """
        result = yield self.kotekan_master.blacklist_node(node_list)
        coroutine_return(result)

    @coroutine
    @endpoint('whitelist-node')
    def whitelist_node(self, handler, node_list):
        """
        Whitelist a node to bring it under the control of KotekanMaster

        Parameters
        ----------
            node_list : list-type
                ['cnAg1', 'cnBg1']
        """
        result = yield self.kotekan_master.whitelist_node(node_list)
        coroutine_return(result)

    @coroutine
    @endpoint('status-kotekan-master')
    def status_kotekan_master(self, handler):
        """
        Get the current status of KotekanMaster
        """
        result = yield self.kotekan_master.status_kotekan_master()
        self.log.info('%s : KotekanMaster Status', self)
        self.log.info('%s : %s', self, result)
        coroutine_return(result)

    # KotekanMaster Validation Routines
    #   These routines run on the entire node cluster in order to deduce
    #   consensus in the array.
    @coroutine
    @endpoint('validate-config')
    def validate_running_configuration(self, handler):
        """
        Validate if nodes in the array are running the same config.
        """
        result = yield self.kotekan_master.validate_config()
        coroutine_return(result)

    @coroutine
    @endpoint('validate-checksum')
    def validate_checksum(self, handler):
        """
        Validate the md5checksum for all running kotekan configs against the
        md5checksum of the self.current_config
        """
        result = yield self.kotekan_master.validate_checksum()
        coroutine_return(result)

    # Kotekan RESTful Endpoints
    #   These endpoints interact with the kotekan process.
    #   There are two types of Kotekan RESTful endpoints
    #       Parameter Endpoints: Dynamically tracked which have a corresponding
    #                            config paramter
    #       Operation Endpoints: Not tracked, and no corresponding config
    #                            parameter, e.g. start_baseband_dump

    # Operation Endpoints
    @coroutine
    @endpoint('start-kotekan')
    def start_kotekan(self, handler):
        """
        Start kotekan process on all nodes with current_config
        """
        watchdog = yield self.kotekan_master.start_watchdog()
        result = yield self.kotekan_master.start_kotekan()
        coroutine_return(result)

    @coroutine
    @endpoint('stop-kotekan')
    def stop_kotekan(self, handler):
        """
        Stop the kotekan process on all nodes.
        """
        watchdog = yield self.kotekan_master.stop_watchdog()
        result = yield self.kotekan_master.stop_kotekan()
        coroutine_return(result)

    @coroutine
    @endpoint('kill-kotekan')
    def kill_kotekan(self, handler):
        """
        Kill the kotekan process on all nodes.
        """
        watchdog = yield self.kotekan_master.stop_watchdog()
        result = yield self.kotekan_master.kill_kotekan()
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

    # Returns all the unique running configurations found in the array.
    @coroutine
    @endpoint('kotekan-running-config')
    def kotekan_running_config(self, handler):
        """
        Queries the current running configuration from the kotekan process.
        """
        result = yield self.kotekan_master.kotekan_running_config()
        coroutine_return(result)

    # Returns all the unique config checksums found in the array.
    @coroutine
    @endpoint('kotekan-config-md5sum')
    def kotekan_config_md5sum(self, handler):
        """
        Queries for the MD5 hash of the running configuration.
        """
        result = yield self.kotekan_master.kotekan_config_md5sum()
        coroutine_return(result)

    # Parameter Endpoints.
    @coroutine
    @endpoint('update-gains')
    def update_gains(self, handler, gains_dir):
        """
        POST to update the gain_dir parameter.
        """
        result = yield self.kotekan_master.update_gains(gains_dir)
        coroutine_return(result)

    @coroutine
    @endpoint('update-beam-offset')
    def update_beam_offset(self, handler, beam_offset):
        """
        POST to update the beam_offset parameter.
        """
        result = yield self.kotekan_master.update_beam_offset(beam_offset)
        coroutine_return(result)

    @coroutine
    @endpoint('update-pulsar-pointing')
    def update_pulsar_pointing(self, handler, pulsar_pointing):
        """
        POST to update the pulsar_pointing parameter.
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

    def __init__(self,
                 hostname='localhost',
                 port=DEFAULT_PORT):
        """
        KotekanMaster Client Initialization
        """
        super(KotekanMasterAsyncRESTClient, self).__init__(
            hostname=hostname,
            port=port,
            server_class=KotekanMasterAsyncRESTServer,
            heartbeat_string='KMc',
            heartbeat_period=3000)

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
        self.log.info('%s:Starting KotekanMasterServer at %s:%i with config:%r',
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

    @coroutine
    def start_watchdog(self):
        """
        Start KotekanMaster Watchdog
        """
        result = yield self.post('start-watchdog')
        coroutine_return(result)

    @coroutine
    def stop_watchdog(self):
        """
        Stop KotekanMaster Watchdog
        """
        result = yield self.get('stop-watchdog')
        coroutine_return(result)

    @coroutine
    def blacklist_node(self, node_dict):
        """
        Blacklist node[s] from being managed by KotekanMaster
        """
        result = yield self.post('blacklist-node', node_dict)
        coroutine_return(result)

    @coroutine
    def whitelist_node(self, node_list):
        """
        Whitelist nodes[s]
        """
        result = yield self.post('whitelist-node', node_list)
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
    def kill_kotekan(self):
        """
        Kill kotekan process on all nodes.
        """
        result = yield self.get('kill-kotekan')
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


# Cleanup Opened Sockets
def reap_cached_sockets():
    import __main__
    logger = log.get_logger(__name__, 'reap_cached_sockets()')
    if hasattr(__main__, '__opened_sockets__'):
        for port, socket in __main__.__opened_sockets__.items():
            logger.debug("closing cached socket on port %d" % port)
            socket.close()
        del __main__.__opened_sockets__


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
    # TODO: This needs to be fixed.
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
