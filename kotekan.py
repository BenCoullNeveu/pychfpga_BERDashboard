#!/usr/bin/env python
"""
REST Client to configure and operate
kotekan nodes and dummy kotekan REST Servers
"""

from __future__ import absolute_import, division, print_function

import logging
import argparse
import sys
from platform import system as system_name  # Returns the system/OS name
from subprocess import call as system_call  # Execute a shell command
import tornado
import tornado.web
import tornado.httpclient
from pychfpga import NameSpace, load_yaml_config
from rest import AsyncRESTClient, AsyncRESTServer, coroutine, coroutine_return
from rest import endpoint, RunSyncWrapper, IOLoop

##########################
# Kotekan RESTful Server #
##########################


class KotekanAsyncRESTServer(AsyncRESTServer):
    """
    Asynchronous Kotekan RESTful server.
    """

    DEFAULT_PORT = 12048

    def __init__(self, address='', port=DEFAULT_PORT, logging_params={}):
        super(KotekanAsyncRESTServer, self).__init__(address=address,
                                                     port=port,
                                                     heartbeat_string='Ks')

    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        """
        Start Kotekan
        """
        self.log.info('%.32r: Received start command with %r' % (self, config))
        coroutine_return('Started kotekan')

    @coroutine
    @endpoint('stop')
    def stop(self, handler):
        """
        Stop Kotekan
        """
        self.log.info('%.32r: Received stop command' % (self))
        coroutine_return("Stopped kotekan")

    @coroutine
    @endpoint('status')
    def status(self, handler):
        """
        GET Status
        """
        self.log.info('%.32r: Received status command' % (self))
        coroutine_return("Got Status from kotekan")

##########################
# Kotekan RESTful Client #
##########################


class KotekanAsyncRESTClient(AsyncRESTClient):
    """
    Provides access to the remote GPU node kotekan processes through the
    REST interface.

    Uses Tornado AsyncHTTPClient. All methods are Tornado coroutines so
    that operations can be performed concurrently on multiple nodes.
    """
    DEFAULT_PORT = KotekanAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname=None,
                 port=DEFAULT_PORT,
                 heartbeat_period=10000,
                 **config):
        super(KotekanAsyncRESTClient, self).__init__(
            hostname=hostname,
            port=port,
            heartbeat_period=heartbeat_period,
            # server_class=KotekanAsyncRESTServer,
            heartbeat_string=None)
        # self.name = name
        self.kotekan_config = config
        self.hostname = hostname
        self.port = port
        # self.ping_cb = tornado.ioloop.PeriodicCallback(self.ping, 60e3)
        # self.ping_cb.start()

    # Operation -- POST RESTful Endpoints
    @coroutine
    def start(self, config):
        """
        Start a kotekan process with a provided config
        """
        self.kotekan_config = config
        yield self.post('start', **config)

    # Operation -- GET RESTful Endpoints
    @coroutine
    def stop(self):
        """
        Stop a kotekan threads.
        """
        yield self.get('stop')

    @coroutine
    def kill(self):
        """
        Kill the kotekan process gracefully.
        """
        result = yield self.get('kill')
        coroutine_return(result)

    @coroutine
    def status(self):
        """
        GET status from a kotekan process.
        """
        result = yield self.get('status')
        coroutine_return(result)

    @coroutine
    def version(self):
        """
        Returns the current kotekan version information,
        including build options.
        """
        result = yield self.get('version')
        coroutine_return(result)

    @coroutine
    def running_config(self):
        """
        Returns the current running kotekan config.
        """
        result = yield self.get('config')
        coroutine_return(result)

    @coroutine
    def config_md5sum(self):
        """
        Returns an MD5 hash of the config file (based on the json string with
        no spaces). Only exists if kotekan was build with OpenSSL support.
        """
        result = yield self.get('config_md5sum')
        coroutine_return(result)

    # FRB Parameters -- POST RESTful Endpoints
    @coroutine
    def update_gains(self, gains_dir):
        """
        Update CHIME/FRB/PULSAR EigenValue Gains Directory
        """
        command = {"gain_dir": gains_dir}
        endpoints = []
        for gpu_id in range(4):
            endpoints.append(
                "/gpu/gpu_{0}/frb/update_gains/{0}".format(gpu_id))
        result = yield {gpu_id: self.post(endpoint, command)
                        for endpoint in endpoints}
        coroutine_return(result)

    @coroutine
    def update_north_south_beam(self, northmost_beam):
        """
        Update CHIME/FRB North-South Beam
        """
        command = {"northmost_beam": northmost_beam}
        endpoints = []
        for gpu_id in range(4):
            endpoints.append(
                "/gpu/gpu_{0}/frb/update_NS_beam/{0}".format(gpu_id))
        result = yield {gpu_id: self.post(endpoint, command)
                        for endpoint in endpoints}
        coroutine_return(result)

    @coroutine
    def update_east_west_beam(self, east_west_id, east_west_beam):
        """
        Update CHIME/FRB East-West Beam
        """
        command = {"ew_id": east_west_id,
                   "ew_beam": east_west_beam}
        endpoints = []
        for gpu_id in range(4):
            endpoints.append(
                "/gpu/gpu_{0}/frb/update_EW_beam/{0}".format(gpu_id))
        result = yield {gpu_id: self.post(endpoint, command)
                        for endpoint in endpoints}
        coroutine_return(result)

    @coroutine
    def update_beam_offset(self, offset):
        """
        Update CHIME/FRB Network Beam Offset
        """
        result = yield self.post('beam_offset', offset)
        coroutine_return(result)

    # Pulsar Parameters -- POST RESTful Endpoints
    @coroutine
    def update_pulsar_pointing(self, beam, ra, dec, scaling):
        """
        Update CHIME/Pulsar beam pointing
        """
        command = {"beam": beam,
                   "ra": ra,
                   "dec": dec,
                   "scaling": scaling}
        endpoints = []
        for gpu_id in range(4):
            endpoints.append("/gpu/gpu_{0}/update_pulsar/{0}".format(gpu_id))
        result = yield {gpu_id: self.post(endpoint, command)
                        for endpoint in endpoints}
        coroutine_return(result)

    # Node Endpoints
    @coroutine
    def ping(self):
        """
        Ping a Kotekan Node

        Returns True if host (str) responds to a ping request.
        Note: Host may not respond to a ping (ICMP) request even if
              the host name is valid.
        """
        # Ping command count option as function of OS
        param = '-n 1' if system_name().lower() == 'windows' else '-c 1'

        # Building the command. Ex: "ping -c 1 google.com"
        command = ['ping', param, self.hostname]

        # Pinging
        result = system_call(command) == 0
        coroutine_return(result)


def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="Kotekan Client/Server CLI",
                                     epilog=""" """)
    parser.add_argument('args',
                        type=str,
                        nargs='*',
                        default='',
                        help='config name and/or command')
    parser.add_argument('-p', '--port',
                        default=KotekanAsyncRESTServer.DEFAULT_PORT, type=int,
                        help="server port")
    parser.add_argument('-n', '--host',
                        default='localhost', type=str,
                        help="Server hostname")
    parser.add_argument('-s', '--server',
                        action='store_true',
                        help='Start a server')
    return parser.parse_args(argv)


if __name__ == '__main__':
    # Create our own IOLoop so we don't interfere with ipython's own ioloop.
    ioloop = IOLoop()
    ioloop.make_current()

    # Setup logging
    # log.setup_logger(__name__,
    #                  stderr_log_level='warning',
    #                  syslog_level='debug')
    logging.getLogger().setLevel('INFO')

    args = parse_cmdline_args(sys.argv[1:])
    port = args.port
    host = args.host
    is_server = args.server
    args = args.args
    first_arg = args[0].lower() if args else None
    node_config = None
    server = None  # PowerSupply server object
    client = None  # PowerSupply client object
    # print(args.args[1:], first_arg)

    if args and not hasattr(KotekanAsyncRESTClient, args[0]):
        if len(args) >= 2:
            print('Loading %s from config %s ' % (args[1], args[0]))
            config = NameSpace(load_yaml_config(args[0]))
            node_name = args[1]
            node_config = config.kotekan.nodes[node_name]
            args = args[2:]
        else:
            raise RuntimeError('Please specify both a config root name and power supply name')

    if is_server:
        server_port = node_config.port if node_config else port
        server = RunSyncWrapper(KotekanAsyncRESTServer(port=server_port))
        if node_config:
            server.start(None, name=node_name, **node_config)
        print("Kotekan REST Server started. Waiting for REST commands.")
        server.run()
        print("\nI'm done. Bye!")

    else:
        client_port = node_config.port if node_config else port
        client_host = node_config.hostname if node_config else host
        client = RunSyncWrapper(KotekanAsyncRESTClient(hostname=client_host, port=client_port))
        if node_config:
            client.start(node_config)
        # If the client started a server, get it for the interactive session
        if hasattr(client,'server'):
            server = RunSyncWrapper(client.server)
        # If there are further arguments, assume they are commands
        if args:
            cmd = args[0]
            if cmd and hasattr(client, cmd):
                print('Sending command %s(%s) to CHIME Master server %s:%s' % (cmd, ', '.join(args[1:]), client_host, client_port))
                print(getattr(client, cmd)(*args[1:]))


    print()
    print("If this was run in an interactive session (ipython -i), the following variables are now accessible:")
    if server: print("   server: Kotekan REST server")
    if client: print("   client: Kotekan REST client")
