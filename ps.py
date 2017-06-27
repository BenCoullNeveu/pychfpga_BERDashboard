#!/usr/bin/env python
"""
Control module for CHIME receiver hut power supplies, including REST interface.

"""
#from __future__ import absolute_import, division, print_function

import logging
import numpy
import os
# import socket
# import subprocess
# import sys
# import time
# import yaml
# import json
# import functools

import tornado
import tornado.tcpclient
import tornado.web

# import pychfpga  # used to access .calculate_gain.
# from pychfpga import FPGAArray, NameSpace, load_yaml_config, AgilentN5764AHandler
from pychfpga.Agilent_N5764A.agilent_N5700 import agilent_N5700
from rest import RESTClient, AsyncRESTServer, endpoint, coroutine, coroutine_return, sleep  # generic REST servers and clients
# from kotekan import KotekanAsyncRESTClient
# from chrx import ChrxAsyncRESTClient
# from raw_acq import RawAcqAsyncRESTClient

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
    ...
    """

    # TODO: Look into appropriate default port / address
    DEFAULT_PORT = 33221

    # TODO: Control multiple PS?
    def __init__(self, address='', port=DEFAULT_PORT, ps_address='', ps_port=1111, logging_params={}):
        self.ps = agilent_N5700(ip_addr=ps_address, ip_port=ps_port)
        super(PowerSupplyRESTServer, self).__init__(address=address, port=port)

    @coroutine
    @endpoint
    def power_on(self):
        self.log.info('%.32r: Received power on command' % self)
        if self.ps.output()['PowerEnabled']:
            raise RuntimeError("Power ouput already enabled.")
        else:
            self.ps.power_on()

    @coroutine
    @endpoint
    def power_off(self):
        self.log.info('%.32r: Received power off command' % self)
        if not self.ps.output()['PowerEnabled']:
            raise RuntimeError("Power ouput already disabled.")
        else:
            self.ps.power_off()

    @coroutine
    @endpoint
    def power_enabled(self):
        self.log.info('%.32r: Received power output status request' % self)
        return self.ps.output()['PowerEnabled']

    @coroutine
    @endpoint
    def status(self):
        self.log.info('%.32r: Received status request' % self)
        meas = self.ps.status()
        for key in meas:
            self.log.info('%.32r:     Status[%r] %r' % (self, key, meas[key]))
        return meas
