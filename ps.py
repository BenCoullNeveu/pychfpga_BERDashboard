#!/usr/bin/env python
"""
Control module for CHIME receiver hut power supplies, including REST interface.

"""

import logging
import numpy
import os
import sys
import argparse
import requests
import time

import tornado
import tornado.tcpclient
import tornado.web

from pychfpga.Agilent_N5764A.agilent_N5700 import agilent_N5700
from pychfpga.Agilent_N5764A import AgilentN5764AHandler
from rest import AsyncRESTClient, AsyncRESTServer, endpoint, coroutine, coroutine_return, sleep, IOLoop  # generic REST servers and clients

class Metric(object):
    def __init__(self, metric_name, value, type='UNDEFINED' , documentation=' No docs', **labels):
        self.metric_name = metric_name
        self.type = type.upper()
        self.doc = documentation
        self.labels = labels
        self.value = value
        self.time = time.time() * 1000
    def  __str__(self):
        return ('# HELP %s %s\n' % (self.metric_name, self.doc) +
               '# TYPE %s %s\n' % (self.metric_name, self.type) +
               '%s{%s} %s %i' % (self.metric_name, ','.join('%s="%s"' % (k,v) for k,v in self.labels.items()), self.value, self.time))


class PowerSupplyRESTServer(AsyncRESTServer):
    """
    REST interface for receiver hut power supplies. Work in progress
    """

    # TODO: Look into appropriate default port / address
    DEFAULT_PORT = 33221

    # TODO: Control multiple PS?
    def __init__(self, name="PowerSupply", address='', port=DEFAULT_PORT, ps_address='', ps_port=5025, logging_params={}):
        self.ps = agilent_N5700(ip_addr=ps_address, ip_port=ps_port)
        self.name = name
        print self.name
        super(PowerSupplyRESTServer, self).__init__(address=address, port=port)

    @coroutine
    @endpoint
    def powerOn(self, handler):
        self.log.info('%.32r: Received power on command' % self)
        if self.ps.output()['PowerEnabled']:
            raise RuntimeError("Power ouput already enabled.")
        else:
            self.ps.output(state='on', readonly=False)

    @coroutine
    @endpoint
    def powerOff(self, handler):
        self.log.info('%.32r: Received power off command' % self)
        if not self.ps.output()['PowerEnabled']:
            raise RuntimeError("Power ouput already disabled.")
        else:
            self.ps.output(state='off', readonly=False)

    @coroutine
    @endpoint
    def powerEnabled(self, handler):
        self.log.info('%.32r: Received power output status request' % self)
        coroutine_return(self.ps.output()['PowerEnabled'])

    @coroutine
    @endpoint
    def status(self, handler):
        self.log.info('%.32r: Received status request' % self)
        meas = self.ps.status()
        for key in meas:
            self.log.info('%.32r:     Status[%r] %r' % (self, key, meas[key]))
        coroutine_return(meas)

    @coroutine
    @endpoint
    def psName(self, handler):
        self.log.info('%.32r: Received name request' % self)
        coroutine_return(self.name)

    @coroutine
    @endpoint
    def monitoringMetrics(self, handler):
        self.log.info('%.32r: Received monitoring metrics request' % self)
        metrics = []
        status = self.ps.status()
        metrics.append(Metric('power_supply_voltage', name=self.name, value=status['voltage'], type='gauge'))
        metrics.append(Metric('power_supply_current', name=self.name, value=status['current'], type='gauge'))
        metrics.append(Metric('power_supply_power', name=self.name, value=status['power'], type='gauge'))
        metrics.append(Metric('power_supply_status', name=self.name, value=int(status['status']=='OK'), type='gauge'))
        coroutine_return([ str(m) for m in metrics ])

class PowerSupplyRESTClient(AsyncRESTClient):
    """
    ...
    """

    def __init__(self, name='PowerSupply', hostname='localhost', port=PowerSupplyRESTServer.DEFAULT_PORT):

        # save hostname and port so __repr__ will work right away. Will be rewritten by super()
        self.hostname = hostname
        self.port = port
        self.log = logging.getLogger(__name__).getChild(self.__class__.__name__) # we need the logger right away
        print ('client, host=', hostname)
        #if not hostname:
        #    hostname = 'localhost'
        #    address = '' # server listens to all interfaces by default
        #    print('allo')
        #    self.log.info('%32r: Creating local PowerSupply server at %s:%i' % (self, address, port))
        #    self.server = PowerSupplyRESTServer(address=address, port=port)
        #    self.server.add_heartbeat(period=1000, heartbeat_string='R')

        self.log.info('%32r: Creating PowerSupply Client at %s:%i' % (self, hostname, port))
        super(PowerSupplyRESTClient, self).__init__(hostname=hostname, port=port)
        self.name = name

    @coroutine
    def powerOn(self):
        try:
            yield self.get('powerOn')
            self.log.info("Successfully sent power on command to %s server at %s:%i" % (self.name, self.host, self.port))
        except Exception as e:
            self.log.debug(repr(e))
            self.log.error("Can't power on %s server at %s:%i" % (self.name, self.host, self.port))

    @coroutine
    def powerOff(self):
        try:
            yield self.get('powerOff')
            self.log.info("Successfully sent power off command to %s server at %s:%i" % (self.name, self.host, self.port))
        except Exception as e:
            self.log.debug(repr(e))
            self.log.error("Can't power off %s server at %s:%i" % (self.name, self.host, self.port))

    @coroutine
    def status(self):
        try:
            meas = yield self.get('status')
            self.log.info("Successfully sent status request to %s server at %s:%i" % (self.name, self.host, self.port))
        except Exception as e:
            self.log.debug(repr(e))
            self.log.error("Can't get status from %s server at %s:%i" % (self.name, self.host, self.port))
        coroutine_return(meas)

class PowerSupplyEasyRESTClient(object):
    def __init__(self, hostname='localhost', port=PowerSupplyRESTServer.DEFAULT_PORT):
        self.port = port
        self.host = hostname
        self.url = "http://{}:{:d}/".format(self.host, self.port)
        response = requests.get(self.url + "psName")
        self.check_code(response.status_code)
        self.name = response.text
        print "Connected to server {}".format(self.name)

    def check_code(self, code):
        if not code == 200:
            raise RuntimeError("Got code {:d} from server at {}:{:d}".format(code, self.host, self.port))

    def powerOn(self):
        print "Sending power on command..."
        response = requests.get(self.url + "powerOn")
        self.check_code(response.status_code)
        print "Successfully sent power on!"

    def powerOff(self):
        print "Sending power off command..."
        response = requests.get(self.url + "powerOff")
        self.check_code(response.status_code)
        print "Successfully sent power off!"

    def powerEnabled(self):
        print "Requesting power_enabled status..."
        response = requests.get(self.url + "powerEnabled")
        self.check_code(response.status_code)
        power_state = bool(response.json())
        print "Power state: {}".format("Enabled" if power_state else "Disabled")
        return power_state

    def status(self):
        print "Requesting status..."
        response = requests.get(self.url + "status")
        self.check_code(response.status_code)
        print "Status: {}".format(response.json())
        return response.json()

    def monitoringMetrics(self):
        print "Requesting monitoring metrics..."
        response = requests.get(self.url + "monitoringMetrics")
        self.check_code(response.status_code)
        return response.json()


def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="Raw_acq: ADC Raw data acquisition server", epilog="""
        """)
    parser.add_argument('args', type=str, choices=['client', 'server'], default='',  help='"server" or "client" ')
    parser.add_argument('-p', '--port', default=33221, type=int, help="Server port")
    parser.add_argument('-n', '--host', default='localhost', type=str, help="Server hostname")
    parser.add_argument('-s', '--power-supply', default='A-N8731A-1553P', type=str, help="Power supply hostname")
    return parser.parse_args(argv)

if __name__ == '__main__':
    """
    Stolen from raw_acq!

    Command-line interface to the raw_acq engine.
        raw_acq server --port 33221 # starts the server on localhost.
        raw_acq client --port 33221 --host localhost # starts a client in variable 'rc' to operate the server at localhost:33221

    Default port is 33221 if not specified.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # pass all messages to the handlers
    logger.handlers = []  # clear all existing handlers
    # formatter = logging.Formatter(self.LOG_FORMAT, self.LOG_DATE_FORMAT)

    def add_handler(h, log_level):
        # h.setFormatter(formatter)
        level = log_level if isinstance(log_level, int) else log_level.upper()
        h.setLevel(level)
        logger.addHandler(h)

    add_handler(logging.StreamHandler(sys.stderr), 'warning')
    add_handler(logging.handlers.SysLogHandler(), 'debug')


    ioloop = IOLoop()
    ioloop.make_current()
    args = parse_cmdline_args(sys.argv[1:])

    print(args)
    first_arg = args.args.lower()
    if first_arg == 'server':
        rs = PowerSupplyRESTServer(port=args.port, ps_address=args.power_supply)
        print("Raw Acq REST Server started. Waiting for REST commands.")
        ioloop.start()
        print("\nI'm done. Bye!")
    elif first_arg == 'client':
        rc = PowerSupplyEasyRESTClient(hostname=args.host, port=args.port)
        #print('Use rc.run_sync(method_name, args...) to call and run asynchronous (coroutine) client methods in a ioloop. Alternativeny, one can use rc.sync_method_name(args, ...).')
