#!/usr/bin/env python

from __future__ import division, print_function

import argparse
import logging
import os
import signal
import struct
import sys
import pickle
import traceback

import tornado
import tornado.tcpclient
import tornado.web

import kotekan
from pychfpga import fpga_array


class ChimeMaster(object):
    """
    """

    def __init__(self, log):
        self.config = {}
        self.log = log

    def start(self, **kvs):
        self.config = kvs

        self.log.info("initializing FPGAs...")
        self.fpgas = fpga_array.FPGAArray(**kvs['fpga_array'])
        self.log.info("finished initializing FPGAs")

        # Starts frame acquisition whenever the software tells it to.
        # GPS time is not used. Multiple boards are not synchronized
        # simultaneously.
        self.fpgas.set_sync_method('local_soft_trigger')

        self.fpgas.set_operational_mode('shuffle16', frames_per_packet=2)

        return {}

    def status(self):
        return self.config

    def stop(self):
        return {}


class DummyChimeMaster(ChimeMaster):
    """
    A variant of ChimeMaster that doesn't do anything hardware related.
    """

    def start(self, **kvs):
        self.config = kvs
        return kvs

    def status(self):
        return self.config

    def stop(self):
        return {}


class JsonRequestHandler(tornado.web.RequestHandler):
    """
    Accept and return JSON instead of HTML.
    """

    def prepare(self):
        if not self.request.body: return
        content_type = self.request.headers['Content-Type']
        if content_type == 'application/json':
            try:
                args = tornado.escape.json_decode(self.request.body)
                self.request.arguments.update(args)
            except ValueError:
                self.send_error(400, error="can't parse JSON")
        elif content_type == 'application/x-www-form-urlencoded':
            args = { k:v[-1] for k,v in self.request.arguments.items() }
            self.request.arguments.update(args)

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def write_error(self, status_code, **kvs):
        if 'exc_info' in kvs:
            exc_info = kvs.pop('exc_info')
            kvs['error'] = ''.join(traceback.format_exception(*exc_info))
        self.write(kvs)


class EchoHandler(JsonRequestHandler):
    """
    /echo REST endpoint handler. Echoes back POSTed arguments, for debugging.
    """
    def post(self):
        a = self.request.arguments
        self.write(a)


class StartHandler(JsonRequestHandler):
    """
    /start REST endpoint handler.
    """
    def initialize(self, cm):
        self.cm = cm

    def post(self):
        self.write(self.cm.start(**self.request.arguments))


class StatusHandler(JsonRequestHandler):
    """
    /status REST endpoint handler.
    """
    def initialize(self, cm):
        self.cm = cm

    def get(self):
        self.write(self.cm.status())


class StopHandler(JsonRequestHandler):
    """
    /stop REST endpoint handler.
    """
    def initialize(self, cm):
        self.cm = cm

    def get(self):
        self.write(self.cm.stop())


class KotekanHandler(JsonRequestHandler):
    """
    /kotekan REST endpoint handler. Just passes messages through.
    """
    def initialize(self, kotekan):
        self.kotekan = kotekan

    @tornado.gen.coroutine
    def post(self):
        args = self.request.arguments.copy()
        type = args.pop('msg_type')
        msg = kotekan.KotekanMessage(type, **args)
        yield self.kotekan.send(msg)


class KotekanConnection(object):

    def __init__(self, host, port, callback):
        self.host = host
        self.port = port
        self.on_msg = callback
        self.msg_uid = 0

    @tornado.gen.coroutine
    def start(self):
        client = tornado.tcpclient.TCPClient()
        while True:
            try:
                self.stream = yield client.connect(self.host, self.port)
                print("connected to kotekan")
                while True:
                    msg = yield self.receive()
                    self.on_msg(msg) # yield?
            except tornado.iostream.StreamClosedError:
                print("can't connect to kotekan")
                yield tornado.gen.sleep(10)

    @tornado.gen.coroutine
    def send(self, msg):
        self.msg_uid += 1
        s = msg.serialize(self.msg_uid)
        b = struct.pack('!I', len(s))
        yield self.stream.write(b + s)

    @tornado.gen.coroutine
    def receive(self):
        b = yield self.stream.read_bytes(4)
        n,= struct.unpack('!I', b)
        s = yield self.stream.read_bytes(n)
        msg = kotekan.KotekanMessage.deserialize(s)
        raise tornado.gen.Return(msg)


def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="Chime Master")
    parser.add_argument('--debug', action='store_true',
                        help="debug mode")
    parser.add_argument('--log', action='store', default='stream',
                       help="")
    parser.add_argument('--loglevel', action='store', default='debug',
                       help="")
    return parser.parse_args(argv)


def setup_log(log_target, log_level):
    log_level_dict = {'info': logging.INFO, 'debug': logging.DEBUG,
                      'warn': logging.WARNING, 'error': logging.ERROR}
    log_level = log_level_dict[log_level]

    log = logging.getLogger('ch_master')
    log.handlers = []  # Clear all existing handlers
    # pass all messages to the handlers which will filter what they want
    log.setLevel(logging.DEBUG)

    if log_target == 'stream':
        handlers = [logging.StreamHandler()]
    elif log_target == 'syslog':
        handlers = [logging.handlers.SysLogHandler(), logging.StreamHandler()]
    else:
        handlers = [logging.FileHandler(log_target), logging.StreamHandler()]

    for handler in handlers:
        handler.setLevel(log_level)
        log.addHandler(handler)

    return log


def main(args):

    # create event loop
    loop = tornado.ioloop.IOLoop.instance()
    handler = lambda sig,frame: \
        loop.add_callback_from_signal(lambda: loop.stop())
    signal.signal(signal.SIGINT, handler)

    # start logging
    log = setup_log(args.log, args.loglevel)
    log.info("booting ch_master...")

    if args.debug:
        cm = DummyChimeMaster(log)
    else:
        cm = ChimeMaster(log)

    # kotekan
    k = KotekanConnection('localhost', kotekan.PORT,
            lambda msg: print('received', msg))
    loop.add_callback(k.start)

    # setup REST endpoints
    port = 54321
    url = tornado.web.url
    app = tornado.web.Application([
        url(r'/echo', EchoHandler),
        url(r'/kotekan', KotekanHandler, dict(kotekan=k)),
        url(r'/start', StartHandler, dict(cm=cm)),
        url(r'/status', StatusHandler, dict(cm=cm)),
        url(r'/stop', StopHandler, dict(cm=cm)),
    ])
    app.listen(port)

    # start event loop
    log.info("ready")
    loop.start()


if __name__ == '__main__':
    args = parse_cmdline_args(sys.argv[1:])
    main(args)

