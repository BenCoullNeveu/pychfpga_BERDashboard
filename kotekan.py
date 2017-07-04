#!/usr/bin/env python
""" REST Client to configure and operate kotekan nodes and dummy kotekan REST Servers"""

from __future__ import absolute_import, division, print_function

import tornado
import tornado.web
import tornado.httpclient

from rest import AsyncRESTClient, AsyncRESTServer, coroutine, coroutine_return, endpoint

################################################
# Dummy kotekan REST Server
################################################

class KotekanRESTServer(AsyncRESTServer):
    """
    Asynchronous dummy kotekan REST server.

    """

    DEFAULT_PORT = 54323

    def __init__(self, address='', port=DEFAULT_PORT, logging_params={}):
        super(KotekanRESTServer, self).__init__(address=address, port=port, heartbeat_string='Ks')

    @coroutine
    def shutdown(self):
        pass

    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        self.log.info('%.32r: Received start command with %r' % (self, config))
        coroutine_return('Started kotekan')

    @coroutine
    @endpoint('stop')
    def stop(self, handler):
        self.log.info('%.32r: Received stop command' % (self))
        coroutine_return("Stopped kotekan")

    @coroutine
    @endpoint('update')
    def update(self, handler, **config):
        self.log.info('%.32r: Received update command with %r' % (self, config))
        coroutine_return("Updated kotekan")

    @coroutine
    @endpoint('status')
    def status(self, handler):
        self.log.info('%.32r: Received status command' % (self))
        coroutine_return("Status")


################################################
# kotekan REST Client
################################################


class KotekanAsyncRESTClient(AsyncRESTClient):
    """
    Provides access to the remote GPU node kotekan processes through its REST interface.

    Uses Tornado AsyncHTTPClient. All methods are Tornado coroutines so that operations can be
    performed concurrently on multiple nodes.
    """
    DEFAULT_PORT = KotekanRESTServer.DEFAULT_PORT

    def __init__(self, name, hostname=None, port=DEFAULT_PORT, **config):

        def make_server(self, address, port):
            """ Called to create a server if hostname is None or empty"""
            return KotekanRESTServer(address=address, port=port)

        super(KotekanAsyncRESTClient, self).__init__(hostname=hostname, port=port, make_server_func=make_server, heartbeat_string='Kc')
        self.name = name
        self.config = config
        self.ping_cb = tornado.ioloop.PeriodicCallback(self.ping, 60e3)
        self.ping_cb.start()

    @coroutine
    def ping(self):
        try:
            yield self.get('status')
            self.log.info("%.32r: Pinged kotekan at %s:%s" % (self, self.hostname, self.port))
        except Exception as e:
            self.log.debug(repr(e))
            self.log.warning("%.32r: Cannot ping kotekan at %s:%s" % (self, self.hostname, self.port))
            coroutine_return(False)
        coroutine_return(True)  # we dont want this in the try block, as by design it raises an exception

    @coroutine
    def start(self, config):
        newconfig = self.config.copy()
        newconfig.update(self.config)
        result = yield self.post('start', **newconfig)
        coroutine_return(result)

    @coroutine
    def stop(self):
        result = yield self.get('stop')
        coroutine_return(result)

    @coroutine
    def update(self, config):
        result = yield self.post('update', **config)
        coroutine_return(result)


if __name__ == '__main__':
    pass
