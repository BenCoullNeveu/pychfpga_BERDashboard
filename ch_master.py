#!/usr/bin/env python
"""
Module that provide the classes used to run the top-level ChimeMaster object used to initialize and operate the CHIME telescope.

"""
from __future__ import absolute_import, division, print_function

import argparse
import collections
import getpass
import logging
import numpy
import os
import socket
import subprocess
import sys
import time
import yaml
import json
import functools

import tornado
import tornado.tcpclient
import tornado.web

import pychfpga  # used to access .calculate_gain.
from pychfpga import FPGAArray, NameSpace, load_yaml_config, AgilentN5764AHandler, Metrics
from ps import PowerSupplyAsyncRESTClient
from rest import RESTClient, AsyncRESTServer, endpoint, coroutine, coroutine_return, sleep, RunSyncWrapper, IOLoop  # generic REST servers and clients
from kotekan import KotekanAsyncRESTClient
from chrx import ChrxAsyncRESTClient
from raw_acq import RawAcqAsyncRESTClient


def convert_types(val):
    # Do the annoying conversion of numpy types to native Python types. Sigh.

    def flatten(x):
        """ Flatten arbitrarily deep nested lists. (inspired from stack overflow)"""
        result = []
        for el in x:
            if hasattr(el, "__iter__") and not isinstance(el, basestring):
                result.extend(flatten(el))
            else:
                result.append(el)
        return result

    found_complex = False
    if isinstance(val, (list, tuple)):
        if len(val) == 0:
            val = [0]
        #if isinstance(val[0], (list, tuple)):
        val = flatten(val)
        if not isinstance(val[0], str):
            try:
                if val[0].dtype.kind in ('i', 'u', 'f'):
                    val = list(numpy.asscalar(x) for x in val)
            except:
                if type(val[0]) == bool:
                    val = list(int(x) for x in val)
                else:
                    val = list(x for x in val)
            for i, val_element in enumerate(val):
                #print val_element
                if isinstance(val_element, complex):
                        val[i] = [val_element.real, val_element.imag]
                        found_complex = True
                if isinstance(val_element, (int,numpy.uint8)):
                        val[i] = float(val_element)
            if found_complex:
                val = flatten(val)
            else:
                val = list(int(x) for x in val)
    else:
        if isinstance(val, long):
            val = int(val)
        elif isinstance(val, bool):
            val = int(val)
        elif isinstance(val, unicode):
            val = str(val)
        elif isinstance(val, int):
            pass
        elif isinstance(val, float):
            pass
        elif not isinstance(val, str):
            try:
                if val.dtype.kind in ('i', 'u', 'f', 'b'):
                    val = numpy.asscalar(val)
            except:
                    # Hopefully already a int/float
                    pass
    return val

def sanitize_for_json(obj):
    """
    Modify an object to make it JSON-compatible. Contents of dicts and
    lists contained in the object are recursively converted.

        - dict-like object with string keys are converted to Python dict
        - dict-like objects with non-string keys are converted into a Python list of (key,value) tuples.
        - list objects are converted into Python list
        - other objects stay the same.

    """
    if isinstance(obj, collections.Mapping) or hasattr(obj, 'items'):
        if not all(isinstance(k,str) for k in obj.keys()):
            return [(k, sanitize_for_json(v)) for k, v in obj.items()]
        else:
            return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    else:
        return obj



#
## Constants ##

# Current archive format version. Prefixed by "NT_" to signify that
# these data do not have the time-transpose completed.
ARCHIVE_VERSION = "NT_2.2.0"


# # Full path to this file.
# PROGRAM = os.path.realpath(__file__)

def get_git_version():
    # Git version.
    PROGRAM = os.path.realpath(__file__)
    try:
        return subprocess.check_output(
            'git describe --all --dirty --long'.split(),
            cwd = os.path.dirname(PROGRAM)).strip()
    except WindowsError:
        print('GIT was not found')
        return 'unknown' # JFC: To allow tests in windows





def reap_cached_sockets():
    import __main__
    log = logging.getLogger(__name__+'.reap_cached_sockets()')
    if hasattr(__main__, '__opened_sockets__'):
        for port, socket in __main__.__opened_sockets__.items():
            log.debug("closing cached socket on port %d" % port)
            socket.close()
        del __main__.__opened_sockets__


class ChimeMaster(object):
    """ Object that provide methods to initialize, control, monitor and shutdown a CHIME telescope
    array (or subarray)
    """

    LOG_FORMAT =  "%(asctime)s %(levelname)s %(name)s.%(funcName)s() %(filename)s:%(lineno)d>> %(message)s"
    LOG_DATE_FORMAT = "%b %d %H:%M:%S"


    def __init__(self):

        self.setup_parent_logger(stderr_log_level='WARNING')
        self.log = logging.getLogger(__name__).getChild(self.__class__.__name__) # i.e. ch_master.ChimeMaster

        self.state = 'off'
        self.config = None

        # Remote service provider objects
        self.chrx = None  # CHRX REST clients
        self.raw_acq = None # Raw FPGA data acquisitoin REST clients
        self.kotekan = None # Kotekan REST clients
        self.fpgas = None # fpga_array object
        self.power_supply_servers = None # power supply REST server

        self.PROGRAM = os.path.realpath(__file__) # absolute path name to this module
        self.GIT_VERSION = get_git_version()

        self.log.info("program %s" % self.PROGRAM)
        self.log.info("version %s" % self.GIT_VERSION)

    def set_config(self, config):
        self.config = NameSpace(config)



    #####################################
    # Power supply management
    #####################################
    # Operates the power supplies via the power supply server(s)

    @coroutine
    def create_power_supplies(self):
        """ create clients object that operate on the power supply server
        """
        ps_config = self.config.power_supplies

        # First create the client to the servers, and start the server if it is not already started
        self.power_supply_servers = {}
        server_nodes = ps_config.nodes or {}
        for server_name, server_params in server_nodes.items():
            ps = PowerSupplyAsyncRESTClient(hostname=server_params.hostname, port=server_params.port) # we pass the whole server config to the client in case it needs th create and/or start the server
            yield ps.start(server_params)
            self.power_supply_servers[server_name] = ps

        # figure out which servers controls the power supply units we want to use in this experiment
        units = ps_config.power_on.units or []  # units used by csh_master
        ps_names = set(units)
        self.power_supply_units = {}
        for server_name, server in self.power_supply_servers.items():
            server_ps_names = set((yield server.list_names()))
            common_ps_names = ps_names & server_ps_names # set intersection
            if common_ps_names:
               self.power_supply_units[server] = list(common_ps_names)
               ps_names -= common_ps_names
        if ps_names:
            raise RuntimeError('%.32r: Could not find a power supply server to handle the following supplies: %s' % (self, ps_names))

    @coroutine
    def power_on(self):
        """ Turn on the power supplies listed in the `power_supplies.power_on.units` config field.

        If the power supply is already ON, no action is taken. If not, it is turned on, and we wait
        for the power on delay specified in `power_supplies.power_on.delay`.
        """

        yield [ps.power_on(ps_names) for ps, ps_names in self.power_supply_units.items()]

    @coroutine
    def power_off(self):
        """ Turn off the power supplies listed in the `power_supplies.power_on.units` config field.
        """
        yield [ps.power_off(ps_names) for ps, ps_name in self.power_supply_units.items()]

    @coroutine
    def is_power_supply_ready(self):
        """ Check is all power supplies listed in the `power_supplies.power_on.units` config field are ready.
        """
        # Get the is_ready dict for each power supply server as [ {ps_name: state,...}, {ps_name: state, ...}]
        is_ready = yield [ps.is_ready() for ps, ps_names in self.power_supply_units.items()]
        # Check if the flag for each supply associated with each server is True
        coroutine_return(all(is_ready[i][ps_name]
                             for i, ps_names in enumerate(self.power_supply_units.values())
                             for ps_name in ps_names))

    @coroutine
    def wait_for_power_supply(self):
        while not (yield self.is_power_supply_ready()):
            self.log.warn('Waiting for power supplies')
            yield sleep(5)

    @coroutine
    def get_power_supply_metrics(self):
        """ Return the metrics for every power supply server.

        Data is gathered for **all** servers, not just the ones that serve a power supply we use in this run.

        Returns:
            A `Metrics` object with the supply monitiring data.
        """

        metrics = Metrics((yield [ps.get_metrics() for ps in self.power_supply_servers.values()]))
        coroutine_return(metrics)

    #####################################
    # CHRX management methods
    #####################################

    @coroutine
    def create_chrx_clients(self):
        """ Create CHRX REST clients, which communicate with the CHRX remote processes that receive
        the data processed from the GPUs.

        TODO:
            - Make parallel if needed
        """
        self.chrx = {}
        nodes = self.config.chrx.nodes or {} # return {} if None (no YAML entries)
        for node_name, node_params in nodes.items():
            conf = node_params.copy()
            conf.update(self.config.chrx.common_config)
            self.chrx[node_name] = ChrxAsyncRESTClient(name=node_name, **conf)  # will use only the parameters it needs for now (host, port etc)

    # def make_chrx_headers(self):
    #     # Add some acquisition information to the header, for kicks.
    #     conf = self.config
    #     headers = {
    #         'acquisition_name': self.acq_name,
    #         'acquisition_type': 'corr',
    #         'archive_version': ARCHIVE_VERSION,
    #         'collection_server': socket.gethostname(),
    #         'instrument_name': conf.corr_name,
    #         'git_version_tag': get_git_version(),
    #         'system_user': getpass.getuser(),
    #         'notes': conf.get('notes','(no notes)'),
    #     }

    #     # # Pass FPGA configuration variables to header.
    #     # for fpga_slot, slot_conf in self.fpga_conf.items():
    #     #     for name in slot_conf:
    #     #         if name != 'antenna_scaler_gain':
    #     #             val = convert_types(slot_conf[name])
    #     #             name = 'Slot_'+ str(fpga_slot) + '_' + name
    #     #             headers[name] = val
    #     return headers


    @coroutine
    def start_chrx_clients(self):
        """ Start all CHRX remote process in parallel """
        @coroutine
        def start_chrx_client(chrx):
            crate_sn = self.fpga.ic[0].get_string_id() # Hack. Works with pathfinder only. Have to rewrite for full CHIME.
            fpga_hk_fields = { "core_temp": "deg C" } # To be rewritten with new chrx
            headers = {
                'acquisition_name': self.acq_name,
                'acquisition_type': 'corr',
                'archive_version': ARCHIVE_VERSION,
                'collection_server': socket.gethostname(),
                'instrument_name': self.config.corr_name,
                'git_version_tag': get_git_version(),
                'system_user': getpass.getuser(),
                'notes': self.config.get('notes','(no notes)'),
            }
            # headers = self.make_chrx_headers()
            self.log.info("starting CHRX %s..." % chrx.name)
            # Start the chrx remote process with additional updated configuration parameters
            yield chrx.start(
                acq_base_dir= self.acq_base_dir,
                crate_sn=crate_sn,
                fpga_hk_fields=fpga_hk_fields,
                headers=headers)
            self.log.info("finished starting CHRX %s" % chrx.name)

        yield [start_chrx_client(chrx) for chrx in self.chrx.values()]

    @coroutine
    def stop_chrx_clients(self):
        yield [chrx.stop() for chrx in self.chrx.values()]


    @coroutine
    def pass_gains_to_chrx(self, gain_map):
        """ *** To be rewritten *** """
        @coroutine
        def update_gains(chrx):
            chan_map = [12, 13, 14, 15,  8, 9, 10, 11,  4,  5,  6,  7, 0, 1, 2, 3]
            slot_map    = [ 5,  1,  4,  0, 13, 9, 12,  8, 15, 11, 14, 10, 7, 3, 6, 2]
            for (crate, slot, chan), gains in gain_map.items():
                remapped_slot = slot_map[slot-1]
                remapped_chan = chan_map[chan]
                # for val in slot_gain:
                converted_gains = convert_types(gains)
                input_number = remapped_slot * 16 + remapped_chan
                yield chrx.send_config(input_number, converted_gains)  # pass_fpga_gain(inp, v)
        # update all gains in parallel
        yield [update_gains(chrx) for chrx in self.chrx.values()]

    #####################################
    # KOTEKAN management methods
    #####################################

    @coroutine
    def create_kotekan_clients(self):
        # Create Kotekan REST clients
        self.kotekan = {}
        nodes = self.config.kotekan.nodes or {}
        for node_name, node_params in nodes.items():
            config = node_params.copy()
            config.update(self.config.kotekan.common_config)
            self.kotekan[node_name] = KotekanAsyncRESTClient(name=node_name, **config)

    #####################################
    # RAW_ACQ management methods
    #####################################

    @coroutine
    def create_raw_acq_clients(self):
        """ Create RawAcq REST clients.
        """
        self.raw_acq = {}
        nodes = self.config.raw_acq.nodes or {}
        for node_name, node_params in nodes.items():
            self.raw_acq[node_name] = RawAcqAsyncRESTClient(name=node_name, **node_params)

    def get_iceboards(self, ib):
        """ Return the iceboard object(s) corresponding to the  `ib` tuple.

        Parameters:

            ib (tuple): A (crate_number, slot_number) tuple describing an iceboard. A value of None
                is equivalent to a '*' wildcard. Missing tuple entries are considered to be None.

        Returns:
            list of iceboard objects

        Examples:

            - (0,), (0, None), (0, '*'), {crate:0} : All boards in Crate 0
        """
        if isinstance(ib, (tuple, list)):
            crate_number = ib[0] if len(ib) > 1 else None
            slot_number = ib[1] if len(ib) > 2 else None
        elif isinstance(ib, dict):
            crate_number = None
            slot_number = None
            for k,v in ib.items():
                if k.lower()=='crate':
                    crate_number = v
                elif k.lower() == 'slot':
                    slot_number = v
                else:
                    raise RuntimeError("Unknown element '%s' in iceboard selection item %s" % (k, ib))
        else:
            raise ValueError('Unknown iceboard selection format %s', ib)

        crate_number = None if crate_number == '*' else crate_number
        slot_number = None if slot_number == '*' else slot_number
        iceboards = []
        print('get_iceboard: looking for ', crate_number, slot_number)
        for ib in self.fpgas.ib:
            ib_id = ib.get_id()
            print('   checking', ib_id)
            if (crate_number is None or crate_number == ib_id[0]) and (slot_number is None or slot_number== ib_id[1]):
                iceboards.append(ib)
        return iceboards

    @coroutine
    def start_raw_acq_servers(self):
        """ Start raw data acquisition servers and set the FPGAs raw data transmit addresses.

        Requires the FPGAs to be initialized.

        Creates the self.raw_acq_ibs dictionary which lists the iceboards objects associated with each RawAcq server.
        """
        self.log.info('%.32r: starting raw_acq servers' % self)
        conf = self.config.raw_acq

        # Make a list of all all iceboards for each of the RawAcq node
        self.raw_acq_ibs = {}
        for node_name, node_conf in conf.nodes.items():
            self.raw_acq_ibs[node_name] = set()
            for ib in node_conf.iceboards:  # ib is a (crate, slot) tuple)
                self.raw_acq_ibs[node_name].update(self.get_iceboards(ib))

        print('self.raw_acq_ibs=', self.raw_acq_ibs)
        # Check that an iceboard is assigned to only one server
        for node_name, ibs in self.raw_acq_ibs.items():
            if not all(ibs.isdisjoint(other_ibs) for other_name, other_ibs in self.raw_acq_ibs.items() if other_name != node_name):
                raise RuntimeError('Some FPGA board(s) is/are assigned to send raw data to multiple RawAcq nodes. Check your config')

        # Start each RawAcq server with a port for each assigned iceboard. For each port, we provide
        # the address of the (only) source FPGA board. The server will ping this address back to
        # set-up the switches routing tables and figure out on which interface the data will be
        # arriving. It will then return the addresses (ip_addr, port, mac_addr) to which the data
        # should be sent.
        #
        # First, prepare the receiver parameters for each node
        recv_ports = {}
        recv_names = {}
        for node_name, ibs in self.raw_acq_ibs.items():  # for each raw_acq node
            recv_name = '%sRecv' % node_name  # Name of the receiver object. Each node runs one receiver, which can hande multiple ports.
            recv_names[node_name] = '%sRecv' % node_name

            recv_ports[node_name] = []
            for i, ib in enumerate(ibs):
                # We have one port per Iceboard, although we could have multiple iceboards per port if the receiver supported it.
                if conf.use_fixed_port_numbers:
                    crate_number = 0 if not ib.crate else ib.crate.crate_number or 0
                    slot_number = ib.slot or 0
                    port_name = 41000 + 100*(crate_number + 1) + slot_number  # ***TODO: make resilient to no-crate and no slot info
                else:
                    port_name = '%sPort%i' % (recv_name, i)
                recv_ports[node_name].append(dict(port=port_name, sources=[(ib.hostname, 80)]))

        # Start the receivers concurrently
        start_results = yield {node_name: self.raw_acq[node_name].start(name=recv_names[node_name], ports=recv_ports[node_name]) for node_name in self.raw_acq_ibs.keys()}

        # Configure the FPGA transmit addresses based on what the receiver returned
        for node_name, start_result in start_results.items(): # for each RawAcq node
            # The start command returned the target address to use for each data source as a list in the format
            #    [ ((src_ip, src_port),(if_ip, port, mac)) ...].
            # We convert this to a dict {(src_ip, src_port):(if_if, port, mac),...} for easy lookup
            targets = {tuple(src_addr):target_addr for src_addr,target_addr in start_result['target_addr']}
            for ib in self.raw_acq_ibs[node_name]:
                ip_addr, port, eth_addr = targets[(ib.hostname, 80)]
                ib.set_data_target_address(ip_addr, port, eth_addr)
        self.log.info('%.32r: RawAcq server setup successfully' % self)

    @coroutine
    def start_fpga_raw_data_transmission(self, capture_rate=None, capture_source=None):
        """ Configure the FPGAs to transmit raw data.

        If no arguments are provided, the FPGA will be set to transmit data at the idle rate and from source defined in the config file.
        """
        conf = self.config.raw_acq.common_config
        capture_rate = capture_rate or conf.idle_capture_rate
        capture_period = 1.0 / float(capture_rate)
        capture_source = capture_source or conf.capture_source
        for node_name, ibs in self.raw_acq_ibs.items():
            for ib in ibs:
                offset = (ib.slot or 1) - 1
                self.log.info('%.32r: Starting data capture on %r with period=%f, source=%s' % (self, ib, capture_period, capture_source))
                ib.start_data_capture(period=capture_period, source=capture_source, offset=offset)

    @coroutine
    def start_hdf5_capture(self, capture_folder=None, capture_filename=None, capture_rate=None, capture_duration=None, capture_source=None, capture_elements_per_file=None):

        conf = self.config.raw_acq.common_config
        capture_rate = capture_rate or conf.hdf5_capture_rate
        capture_source = capture_source or conf.capture_source
        capture_folder = capture_folder or conf.capture_folder
        capture_folder = os.path.join(self.acq_base_dir, capture_folder)
        capture_filename = capture_filename or conf.capture_filename
        capture_duration = capture_duration or conf.capture_duration
        capture_elements_per_file = capture_elements_per_file or conf.capture_elements_per_file

        yield self.start_fpga_raw_data_transmission(capture_rate, capture_source)

        yield [node.start_hdf5(
            base_dir=capture_folder,
            base_filename=capture_filename,
            capture_duration=capture_duration + 60,  # stop HDF5 capture 1 min after the desired time in case ch_master does not do it.
            elements_per_file=capture_elements_per_file
            )         for node_name, node in self.raw_acq.items()]


        self.log.info('%.32r: HDF5 data writer will be stopped in %f seconds' % (self, capture_duration))
        self.call_later(capture_duration, self.stop_hdf5_capture)

    @coroutine
    def stop_hdf5_capture(self):

        yield [node.stop_hdf5() for node_name, nnode in self.raw_acq.items()]
        yield self.start_fpga_raw_data_transmission()


    def set_state(self, new_state):
        """ Sets the state to a specified value. Used for debugging. """
        self.state = new_state


    def get_parent_logger(self):
        """
        Return the parent logger of this module.

        If the module is not imported as part of a package (i.e. this module is named 'ch_master'
        instead if 'ch_acq.ch_master'), then return the rool logger.
        """

        return logging.getLogger(__name__.rsplit('.', 1)[0] if '.' in __name__ else '')

    def setup_parent_logger(self,
                            stdout_log_level=None,
                            stderr_log_level=None,
                            syslog_log_level=None,
                            file_log_level=None,
                            log_filename=None):
        """
        Configure the logging parameters for the parent logger of this module.

        All logging messages from ch_master classes, pychfpga package modules, raw_acq etc... are named
        hierarchically with their module name and trickle down to the ``ch_acq`` logger. We configure
        this `ch_acq` logger to have the desired formatting.

        """


        logger = self.get_parent_logger()
        logger.setLevel(logging.DEBUG) # pass all messages to the handlers
        logger.handlers = []  # clear all existing handlers
        formatter = logging.Formatter(self.LOG_FORMAT, self.LOG_DATE_FORMAT)

        def add_handler(h, log_level):
            h.setFormatter(formatter)
            level = log_level if isinstance(log_level, int) else log_level.upper()
            h.setLevel(level)
            logger.addHandler(h)

        # Stderr logger
        if stdout_log_level is not None:
            add_handler(logging.StreamHandler(sys.stdout), stdout_log_level)
        if stderr_log_level is not None:
            add_handler(logging.StreamHandler(sys.stderr), stderr_log_level)
        if syslog_log_level is not None:
            add_handler(logging.handlers.SysLogHandler(), syslog_log_level)
        if file_log_level is not None:
            add_handler(logging.FileHandler(log_filename), file_log_level)
            self.log.info("Now logging to \"%s\"." % log_filename)


    def stop_parent_logger(self):
        self.log.info("Removing all loggers")
        logger = self.get_parent_logger()
        logger.handlers = []  # just wipe all handlers


    # def add_parent_file_logger(self,log_filename):

    #     # Start writing to a log file in this directory.
    #     logger = self.get_parent_logger()
    #     formatter = logging.Formatter(self.LOG_FORMAT, self.LOG_DATE_FORMAT)
    #     handler = logging.FileHandler(log_filename)
    #     handler.setFormatter(formatter)
    #     logger.addHandler(handler)



    @coroutine
    def start(self, **config):
        """ Make the telescope operational by starting and initializing the FPGA F-Engine and the GPU X Engine (Kotekan), CHRX, and raw_acq remote processes. """
        print('%r: start' % (self))
        if self.state != 'off':
            coroutine_return(dict(error='already started'))

        if config:
            self.set_config(config)
        conf = self.config # Shortcut. We use `conf` a lot below.

        self.state = 'starting'

        if not hasattr(conf, 'corr_name'):
            raise RuntimeError('CHIME master configuration data does not define the correlator name. Was the correct object selected in the configuration file (i.e. config.yaml:object)')

        # Create output directories
        time_str = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.acq_name = "%s_%s" % (time_str, conf.corr_name)
        self.acq_base_dir = os.path.join(os.path.expanduser(conf.base_path), self.acq_name)

        try:
            os.makedirs(self.acq_base_dir)
        except:
            errmsg = "Could not create directory '%s'!" % self.acq_base_dir
            self.log.critical(errmsg)
            coroutine_return({'error':errmsg})


        log_filename = os.path.join(self.acq_base_dir, "ch_master.log")

        self.setup_parent_logger(
            stderr_log_level=conf.logging.stderr_log_level,
            syslog_log_level=conf.logging.syslog_log_level,
            file_log_level=conf.logging.file_log_level,
            log_filename=log_filename)


        # Now that the housekeeping is done, let's start the real work

        # Create objects to communicates to the remote processes needed to run the array
        yield self.create_power_supplies()
        yield self.create_chrx_clients() # CHRX nodes receive data processed by the GPU nodes
        yield self.create_kotekan_clients() # Kotekan processes run on the GPU nodes; they receive the data from the FPGAs over dedicated point-to-point FPGA-GPU 10G Ethernet links, perform the correlation on the data, and forward the processed data to the CHRX nodes
        yield self.create_raw_acq_clients() # Raw acq clients receive raw ADC data sent by the FPGA over the control network


        # power on the array
        yield self.power_on()
        yield self.wait_for_power_supply()

        # Create FPGA Array object and and initialize FPGAs
        yield self.create_fpga_array()

        # Read the FPGA setting back from the FPGA
        self.log.info("Getting configuration data from all FPGAs")
        self.fpga_conf = yield self.fpgas.get_fpga_config.async()


        # Configre and start CHRX remote processes

        self.configure_fpgas_post_acq()
        self.current_bank = 0



        yield self.start_raw_acq_servers()

        # Start raw_data capture
        if conf.raw_acq.common_config.capture_duration is not None:
            yield self.start_hdf5_capture()
        else:
            Yield self.start_fpga_raw_data_transmission()


        self.state = 'on'
        coroutine_return({})

    @coroutine
    def create_fpga_array(self):
        self.log.info("initializing FPGAs...")

        # shortcuts
        conf = self.config  # shortcut to shorten the code below
        fpga_array_params = conf.fpga.fpga_array_params

        #Define some FPGA-related system constants
        self.SAMPLING_FREQUENCY = float(fpga_array_params.samp_freq)*1e6  # frequency in Hz
        self.SAMPLES_PER_FRAME = 2048
        self.SECONDS_PER_FRAME = self.SAMPLES_PER_FRAME / self.SAMPLING_FREQUENCY

        self.log.info("Sampling frequency is %0.3f MHz." % (self.SAMPLING_FREQUENCY/1e6))

        # Create the FPGAArray object. This object will create a database of all FPGA boards, crates and
        # mezzanines as described by the ``fpga_array_params`` parameters.fpga_array_params If specified
        # in the parameters, the FPGAs will be loaded with their bitstream, communication with the FPGAs
        # will be established and all the Python objects needed to operate the FPGA firmware will be
        # created and initialized.
        self.fpgas = ca = FPGAArray(**fpga_array_params)  # Starts an independent ioloop while initializing. Web clients/server stop while


        if not ca.ib: # if there ar eno boards in the array
            if conf.debug.get('allow_empty_fpga_array', False):
                return
            else:
                raise RuntimeError('No IceBoard could be found. Are the boards powered up? Is the network connection functional?')

        # # if this needed?
        # ca.ib.set_adc_mask(0) # null the ADC data before it gets to the channelizers to reduce power consumption

        # Set ADC delays from delay files. Recompute and save new delays if the files do not exist or if
        # the delays loaded from them do not work.
        ca.set_adc_delays(**conf.fpga.adc_delay_params)


        # Reset the correlator. Not sure if this is necesssary?
        ca.ib.set_corr_reset(1)
        time.sleep(0.1)
        ca.ib.set_corr_reset(0)


        # Compute gains if requested
        if conf.fpga.compute_gains.enable:
            self.compute_gains()


        # Set-up channelizers to process data normally
        self.log.info("Setting-up channelizers")
        ca.set_channelizers(**conf.fpga.channelizer_params)

        # Set-up initial gains in gain bank #0
        if conf.fpga.load_initial_gains:
            self.log.info("Loading initial SCALER gains in bank #0")
            # ca.set_synchronized_gain_switching_mode(enable=0)  # Disable synchronized gain switching
            # ca.set_next_gain_bank(bank=0)  # immediately select bank zero to load initial gains
            gains = ca.load_gains() # load gains from gain files
            ca.set_gains(gains, bank=0, when='now') # Upload to bank 0 and immediately activate gain bank
        # for bankset in ca.ib.get_current_gain_bank():
        #     log.info('Using gain banks %s' % (', '.join([str(i) for i in bankset])))

        # if conf.enable_gain_switching:
        #     # set frame number to switch gains at.
        #     ca.set_gain_switch_frame_number(frame=0) # XXX:???
        #     # set to only change when at configured frame number
        #     ca.set_synchronized_gain_switching_mode(enable=1)
        #     # set to use bank 1 next, change in loop below.
        #     # have to do this after config to wait for frame number


        # Is the logging below useful? We just set them...

        # for bankset in ca.ib.get_current_gain_bank():
        #     log.info('Using gain banks %s' % (', '.join([str(i) for i in bankset])))

        # for enabled_sync in ca.ib.get_synchronized_gain_switching():
        #     log.info('Gain sync status is %s' % (', '.join([str(i) for i in enabled_sync])))

        # for frames_set in ca.ib.get_gain_switch_frame_number():
        #     log.info('Gain sync frame is %s' % (', '.join([str(i) for i in frames_set])))

        # log.info("Sending local sync to each board")
        # ca.ib.sync()

        # Setup raw data capture
        #yield self.start_raw_acq_servers()

        # Setup noise injection for normal operation
        self.setup_noise_injection(conf.fpga.noise_injection)


        # Initialize data shufling and transmission to the GPU
        # log.info("Setting FPGA operational mode")
        # ca.set_operational_mode(conf.fpga.operational_mode, frames_per_packet=fpga_array_params.group_frames)

        self.log.info("Synchronizing the array...")
        ca.sync()  # synchronize all the boards in the array

        # log.info("Unmasking the ADC data")
        # ca.ib.set_adc_mask(0xFF) # restore normal ADC data, necessary anymore?

        self.log.info("Waiting for 2 seconds")
        time.sleep(2)

        self.log.info("finished initializing FPGAs")

    def configure_fpgas_post_acq(self):
        """
        """
        # shortcuts
        # ca = self.fpgas

        # JFC: not sure why we had those:
        # ca.ib.CROSSBAR.LANE_MONITOR_RESET = 1
        # ca.ib.CROSSBAR.LANE_MONITOR_RESET = 0
        # ca.ib.CROSSBAR2.LANE_MONITOR_RESET = 1
        # ca.ib.CROSSBAR2.LANE_MONITOR_RESET = 0
        # ca.ib.CROSSBAR.LANE_MONITOR_SEL = 6
        # ca.ib.CROSSBAR2.LANE_MONITOR_SEL = 6

        # if self.config.enable_gain_switching:
        #     ca.set_next_gain_bank(bank=1)
        # for bankset in ca.ib.get_next_gain_bank():
        #     log.info('Set next gain bank to %s' % ', '.join([str(i) for i in bankset]))
        # for bankset in ca.ib.get_current_gain_bank():
        #     log.info('Currently using gain banks %s' % ', '.join([str(i) for i in bankset]))


    def setup_noise_injection(self, ni_params):
        """
        Setup the noise gating PWM signals for all the boards specified in `ni_params`.

        `ni_params` is a dictionary containing the parameters passed to the fpga_array's setup_noise_injection() method.

        If no board is specified for an entry (.board evaluates to False), the parameters are ignored.
        """
        for source_name, source_params in ni_params.items():
            self.log.info("Setting noise injection for source '%s' with parameters %s" % (source_name, source_params))
            if source_params.board:
                self.fpgas.set_noise_injection(local_sync=True, **source_params)

    ###################################
    # Gains management
    ###################################


    # def load_gains(self):
    #     """ Reload a new set of FPGA F-Engine complex gains from the gain files in the currently unused gain bank"""

    #     ca = self.fpgas
    #     gains = ca.load_gains(self.config.gain_folder)
    #     ca.set_gains(gains, when='now')
    #     # current_bank = self.current_bank
    #     # next_bank = (current_bank + 1) % 2
    #     # iceboards = self.fpgas.ib

    #     # # log current gains
    #     # for bankset in iceboards.get_current_gain_bank():
    #     #     log.info('Using gain banks ' + ', '.join(map(str,bankset)))

    #     # # load gains into next bank
    #     # fpga_gains = self.fpga.load_gains(bank=next_bank)
    #     # log.info("Loaded gains into bank %d" % next_bank)

    #     # return fpga_gains


    def get_next_gain_switch_frame(self):
        """ Get the frame number of first frame of the next integration period and the remaining time before this frame occurs.
        """
        ib = self.fpgas.ib[0]
        gain_switch_delay = self.config.fpga.gain_switch_delay # how much extra time do we need to set-up the gains before switching
        gpu_integration_period = self.config.gpu.gpu_integration_period

        current_frame_number = ib.get_frame_number()
        next_gain_switch_frame = (1 + (current_frame_number + gain_switch_delay)//gpu_integration_period)*gpu_integration_period
        time_until_switch = (next_gain_switch_frame - current_frame_number)*self.SECONDS_PER_FRAME
        return (next_frame_number, time_until_switch)


    # def set_gain_switch_frame(self):

    #     iceboards = self.fpgas.ib
    #     gain_switch_delay = self.config.fpga.gain_switch_delay
    #     gpu_integration_period = self.config.gpu.gpu_integration_period

    #     # set gain switch time
    #     frame_number = iceboards[0].get_frame_number()
    #     new_gain_switch_frame = (1 + (frame_number + gain_switch_delay)//gpu_integration_period)*gpu_integration_period
    #     iceboards.set_gain_switch_frame_number(frame=new_gain_switch_frame)

    #     sleep = (new_gain_switch_frame - frame_number)*self.SECONDS_PER_FRAME
    #     return sleep

    # def switch_gain_banks(self):
    #     current_bank = self.current_bank
    #     next_bank = (current_bank + 1) % 2
    #     iceboards = self.fpgas.ib

    #     self.fpgas.set_next_gain_bank(bank=current_bank)
    #     self.current_bank = next_bank
    #     log.debug("changed which gain bank will be written to over to %d"
    #         % current_bank)

    #     # log current gains
    #     for bankset in iceboards.get_current_gain_bank():
    #         log.info('Using gain banks ' + ', '.join(map(str,bankset)))


    def compute_gains(self):
        """
        Compute the gains of the SCALER module so that the conversion of the FFT output to (4+4) bit complex values syays within range for the current signal conditions.

        This method will have to be rewritten to use data obtained over REST-based raw data receivers.
        """

        # shortcuts
        cg = self.config.fpga.compute_gains
        if not cg.enable:
            return
        # setup noise injection using noise injection parameters that are specific to the gain calculation operation.
        self.setup_noise_injection(cg.noise_injection)
        for ib in self.fpgas.ib:
            if ib.slot in cg.slots:
                pychfpga.calculate_gains.calculate_gains(ib, str(ib.fpga_port_number + 1)) # use of fixed port numbers is obsolete

    @coroutine
    def switch_gains(self, gain_map):
        """ Start using the specified gain map for the next available integration period and inform CHRX of the new gains.
        """
        if self.state != 'on':
            coroutine_return(dict(error='not started'))

        # get the currently inactive active gain bank from one single board. We want all boards to
        # use the same bank number to make the system more robust to gain qdesynchronization (if one
        # board misses its gain switch for instance).
        next_bank = self.fpgas.get_next_gain_bank()

        # Set the gains in the unused gain bank, but don't switch to them yet. This will take some unknown time
        self.fpgas.set_gains(gain_map, bank=next_bank)

        # Now that all the gains are stored, find out when we can switch them in.
        # This will be the next integer number of interation period. This includes a guard period to leave us time to instruct the FPGAs when to switch.
        (next_gain_switch_frame_number, time_until_switch) = self.get_next_gain_switch_frame()

        # Tell all the channels to switch to the currently unused bank at that frame number. That should be done within the guard period.
        self.fpgas.switch_gains(bank=next_bank, when=next_gain_switch_frame_number)

        # Tell chrx which gains are coming and when
        yield self.pass_gains_to_chrx(next_gain_switch_frame_number, gain_map)


    def status(self):
        """ Get the operational status of the telescope as a dictionary"""
        status = dict(state=self.state)
        if self.state == 'on':
            status['config'] = self.config.as_dict()
        return status


    @coroutine
    def stop(self):
        """ Stop the F-engine and the correlator data acquisition processes"""
        if self.state == 'on':
            self.state = 'stopping'
            self.log.info("stopping acquisition")
            self.iceboard_cb.stop()
            if self.chrx:
                yield self.stop_chrx_clients()
            self.stop_parent_logger()
            reap_cached_sockets()
            self.state = 'off'
        coroutine_return({})


    def get_frequency_map(self):
        return self.fpgas.get_frequency_map()

    def run_sync(self, method_name, *args, **kwargs):
        """ Runs `method_name` in a ioloop and returns when completed"""

        def heartbeat_callback():
            print('M', end='')
        heartbeat = tornado.ioloop.PeriodicCallback(heartbeat_callback, 1000).start()
        return IOLoop.current().run_sync(functools.partial(getattr(self, method_name), *args, **kwargs))

    def run(self):
        """ Run the IOLoop until interrupted """
        IOLoop.current().start()

class DummyChimeMaster(ChimeMaster):
    """
    A variant of ChimeMaster that doesn't do anything hardware related.
    """

    def start(self, **config):
        self.config = NameSpace(config)
        return config

    def status(self):
        return self.config.as_dict()

    def stop(self):
        return {}


class ChimeMasterAsyncRESTServer(AsyncRESTServer):
    """ Wraps the ChimeMaster into a REST server which receives HTTP GET or POST requests and calls
    the correspnding ChimeMaster methods.
    """

    def __init__(self, port, dummy=False):

        self.port = port # port on which the web server will be run
        self.dummy = dummy

        # # Create a kotekan client for each node specified in the gpu_config_file
        # # We may want to make this part of ChimeMaster initialization
        # gpu_config = yaml.load(open(gpu_config_file)) if gpu_config_file else {}
        # self.kotekan_clients = [KotekanAsyncRESTClient(k, **v) for k,v in gpu_config.items()]

        # Use a dummy CHIME Master object if dummy is True
        ChimeMasterClass = DummyChimeMaster if self.dummy else ChimeMaster

        self.chime_master = ChimeMasterClass()
        super(ChimeMasterAsyncRESTServer, self).__init__(port=port)

        self.add_periodic_callback(self.print_iceboard_info_callback, period=60000)

    @coroutine
    def shutdown(self):
        print('Shutting down CHIME Master')
        yield self.chime_master.stop()
        yield sleep(3)
        print('CHIME Master is shut down')

    def print_iceboard_info_callback(self):
        if self.chime_master.fpgas:
            self.chime_master.fpgas.print_iceboard_info()
        else:
            self.log.info('FPGA array not yet initialized. No houskeeping info to show.')

    ##########################
    # Target endpoint methods
    ##########################


    @coroutine
    @endpoint('echo') # must be applied before coroutine because we lose the method signature
    def echo(self, handler, **args):
        coroutine_return(args)

    @coroutine
    @endpoint('set-state')
    def set_state(self, handler, state=None):
        self.chime_master.set_state(state)
        coroutine_return(args)

    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        def encode_utf8(x):
            """Convert unicode strings to utf-8 strings for the target object and any objects in lists or dictionaries"""
            if type(x) is unicode:
                return x.encode('utf8')
            elif type(x) is dict:
                return {encode_utf8(k):encode_utf8(v) for k,v in x.items()}
            elif type(x) is list:
                return map(encode_utf8, x)
            else:
                return x
        config = encode_utf8(config)  # convert all strings in the config dict into utf8
        result = yield self.chime_master.start(**config)
        coroutine_return(result)

    @coroutine
    @endpoint('methods')
    def methods(self, handler):
        coroutine_return(results=self.get_endpoint_info())

    @coroutine
    @endpoint('status')
    def status(self, handler):
        coroutine_return(self.chime_master.status())

    @coroutine
    @endpoint('stop')
    def stop(self, handler):
        results = yield self.chime_master.stop()
        coroutine_return(results)

    @coroutine
    @endpoint('switch_gains')
    def switch_gains(self, handler, gain_map):
        results = yield self.chime_master.switch_gains(gain_map)
        coroutine_return(results)

    @coroutine
    @endpoint('kotekan-start')
    def kotekan_start(self, handler, **config):
        results = yield [k.start(**config) for k in self.kotekan_clients]
        coroutine_return(results=results)

    @coroutine
    @endpoint('get_frequency_map')
    def get_frequency_map(self, handler):
        coroutine_return(results=sanitize_for_json(self.chime_master.get_frequency_map()))

    @coroutine
    @endpoint('abort')
    def abort(self, handler):
        """ Savagely stop the server for debugging purposes."""
        tornado.ioloop.IOLoop.instance().stop()
        coroutine_return(results='ABORTING NOW!')
        # sys.exit(-1)

    @coroutine
    @endpoint('power-on')
    def power_on(self, handler):
        """ Power up only the power supplies used in this run"""
        result = yield self.ch_master.power_on()
        coroutine_return(result)

    @coroutine
    @endpoint('power-off')
    def power_off(self, handler):
        """ Power down only the power supplies used in this run"""
        result = yield self.ch_master.power_off()
        coroutine_return(result)

    @coroutine
    @endpoint('abort')
    def abort(self, handler):
        """ Savagely stop the server for debugging purposes."""
        tornado.ioloop.IOLoop.instance().stop()
        coroutine_return(results='ABORTING NOW!')
        # sys.exit(-1)

    @coroutine
    @endpoint('call-fpga-array-method')
    def call_fpga_array_method(self, handler, **args):
        """  For debuging: calls any fpga_array method. """
        if not hasattr(self.chime_master, 'fpgas') or not self.chime_master.fpgas:
            handler.write(dict(error='FPGA array is not created yet'))
            return
        r = getattr(self.chime_master.fpgas, args['method_name'])(**args)
        coroutine_return(results=sanitize_for_json(r))


    @coroutine
    @endpoint('get-monitoring-data')
    def get_monitoring_data(self, handler):
        metrics = Metrics()
        try:
            metrics.add((yield self.chime_master.get_power_supply_metrics()))
        except:
            pass

        if self.chime_master.fpgas:
            try:
                metrics.add((yield self.chime_master.fpgas.get_metrics.async()))
            except:
                pass
        if self.chime_master.power_supply_servers:
            try:
                metrics.add((yield self.chime_master.get_power_supply_metrics()))
            except:
                pass

        # Make the HTTP reply a plain text response for Prometheus, not JSON,
        handler.set_header('Content-Type', 'text/plain')
        handler.write(str(metrics))

class ChimeMasterRESTClient(RESTClient):

    def print_result(self, d):
        if d == {}:
            self.print('ok')
        elif 'error' in d:
            self.print_error(d['error'].rstrip())
        else:
            self.print(json.dumps(d, sort_keys=True, indent=2))

    def nop(self):
        self.print('Doing nothing')

    def get_methods(self):
        return self.get('methods')


    def ping(self):
        """
        Test connection to ch_master.
        """
        import random
        nonce = random.getrandbits(32)
        r = self.post('echo', nonce=nonce)
        if 'nonce' in r and nonce == int(r['nonce']):
            self.print("ok")
            return
        self.print("internal error!. Server reply was: \n%s" % '\n'.join('%s:%s' % (k,v) for (k,v) in r.items()))

    def set_state(self, state):
        r = self.post('set-state', state=state)
        self.print_result(r)

    def start(self, yaml=None):
        """
        Start ch_master with specified config file.
        """
        if not yaml:
            raise ValueError('A YAML configuration filename:object must be specified')
        config = load_yaml_config(yaml.encode('ascii'))
        r = self.post('start', **config)
        self.print_result(r)

    def status(self):
        """
        Print ch_master status.
        """
        r = self.get('status')
        self.print_result(r)

    def stop(self):
        """
        Stop ch_master.
        """
        r = self.get('stop')
        self.print_result(r)

    def switch_gains(self):
        """
        Change gains.
        """
        r = self.post('switchgains')
        self.print_result(r)

    def kotekan_start(self, yaml):
        """
        Start kotekan with specified config file.
        """
        if not yaml:
            raise ValueError('A YAML configuration filename must be specified')
        config = load_yaml_config(yaml.encode('ascii'))
        r = self.post('kotekan-start', **config)
        self.print_result(r)

    def get_frequency_map(self):
        """
        Print ch_master status.
        """
        m = self.get('get_frequency_map')
        self.print_result(m)


def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="CHIME Master", epilog="""
        """)
    parser.add_argument('args', type=str, nargs='*', default='',  help='"server", "client" or a YAML filename:subconfig. "server" Starts the CHIME Master REST server. Control is returned only after server is stopped')
    parser.add_argument('-d', '--debug', action='store_true',
                        help="debug mode")
    parser.add_argument('-p', '--port', default=54321, type=int, help="port used by the server")
    parser.add_argument('-n', '--host', default='localhost', type=str, help="server hostname")
    return parser.parse_args(argv)

if __name__ == '__main__':

    # Create our own IOLoop so we don't interfere with ipython's own ioloop.
    ioloop = IOLoop()
    ioloop.make_current()

    args = parse_cmdline_args(sys.argv[1:])
    first_arg = args.args[0].lower() if args.args else None
    cm = None
    cms = None
    cmc = None

    if first_arg == 'server':
        ################################################################################
        # Create and run a CHIME Master REST server
        ################################################################################
        print('Starting CHIME Master REST server on %s:%i' % (args.host, args.port))
        cms = RunSyncWrapper(ChimeMasterAsyncRESTServer(port=args.port, dummy=args.debug)) # server will be added to the current ioloop
        if len(args.args) > 1:
            cms.start(None, **load_yaml_config(args.args[1:]))
        cms.run()
        cm = RunSyncWrapper(cms.chime_master)
        print("CHIME Master REST server has stopped.")

    elif first_arg == 'client':
        ################################################################################
        # Create CHIME Master REST client, and optionally invoke a command
        ################################################################################
        print('Starting CHIME Master REST client connected to %s:%s' % (args.host, args.port))
        # create a CHMasterClient object. The client is asynchronous, so no need to run the ioloop.
        m = ChimeMasterRESTClient(port=args.port)
        cmd = args.args[1] if len(args.args) > 1 else None
        if cmd and hasattr(m, cmd):
            print('Sending command %s to CHIME Master server %s:%s' % (cmd, args.host, args.port))
            getattr(m, cmd)(*args.args[2:])

    else:
        ################################################################################
        # Create CHIME Master object directly, and optionally start it with the specified config file
        ################################################################################
        cm = RunSyncWrapper(ChimeMaster())
        if first_arg:
            print('Starting ChimeMaster object with configuration %s' % first_arg)
            cm.start(**load_yaml_config(first_arg))
        else:
            print('No yaml_filename:subconfig_name was specified. Starting an uninitialized ChimeMaster object')


    print()
    print("If this was run in an interactive session (ipython -i), the following variables are now accessible:")
    if cms:
        print("   cms: CHIME Master REST server")
    if cmc:
        print("   cmc: CHIME Master REST client")
    if cm:
        print("   cm: CHIME Master object")
