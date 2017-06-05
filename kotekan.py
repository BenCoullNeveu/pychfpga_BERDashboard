#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import sys

import tornado
import tornado.web

from rest import AsyncRESTClient, coroutine, coroutine_return


class KotekanAsyncRESTClient(AsyncRESTClient):
    """Implements a kotekan REST client using a Tornado AsyncHTTPClient .

    All methods are Tornado coroutines so that operations can be performed concurrently on multiple nodes.
    """
    def __init__(self, name, host=None, port=80, **kvs):

        super(KotekanAsyncRESTClient, self).__init__(host=host, port=port)
        self.name = name
        self.node_specific_config = kvs
        self.ping_cb = tornado.ioloop.PeriodicCallback(self.ping, 60e3)
        self.ping_cb.start()

    @coroutine
    def ping(self):
        try:
            resp = yield self.post('status')
            self.log.info("pinged kotekan %s" % self.host)
        except Exception as e:
            self.log.debug(repr(e))
            self.log.debug("can't ping kotekan %s" % self.host)

    @coroutine
    def start(self, config):
        # XXX:HACK for pathfinder
        newconfig = config.copy()
        newconfig.update(self.node_specific_config)
        try:
            result = yield self.post('start', **newconfig)
        except Exception as e:
            result = dict(error=repr(e))
        coroutine_return(result)


class Handler(tornado.web.RequestHandler):

    def initialize(self, port):
        self.port = port

    def post(self, path):
        body = self.request.body
        print(self.port, path, body)
        self.write(body)


#
# fake Kotekan server, for testing
#
if __name__ == '__main__':

    port = int(sys.argv[1])
    loop = tornado.ioloop.IOLoop.instance()
    url = tornado.web.url
    app = tornado.web.Application([
        url(r'/(.*)', Handler, dict(port=port)),
    ])
    app.listen(port)
    loop.start()

