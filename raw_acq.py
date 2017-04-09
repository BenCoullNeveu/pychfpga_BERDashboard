#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

from rest import AsyncRESTClient, coroutine, coroutine_return


class RawAcqAsyncRESTClient(AsyncRESTClient):
    """Implements a RawAcq REST client using a Tornado AsyncHTTPClient .

    All methods are Tornado coroutines so that operations can be performed concurrently on multiple nodes.
    The client will operate only if the IOloop is running.
    """
    def __init__(self, name, host=None, port=80, **kwargs):

        super(RawAcqAsyncRESTClient, self).__init__(host=host, port=port)
        self.name = name
        self.kwargs= kwargs

    @coroutine
    def ping(self):
        try:
            resp = yield self.get('status')
            self.log.info("Successfully pinged raw_acq server at %s:%i" % (self.host, self.port))
        except Exception as e:
            self.log.debug(repr(e))
            self.log.error("Can't ping raw_acq server at %s:%i" % (self.host, self.port))

    @coroutine
    def start(self, config):
        try:
            result = yield self.post('start', **config)
        except Exception as e:
            result = dict(error=repr(e))
        coroutine_return(result)



#
# fake raw_acq server, for testing
#
if __name__ == '__main__':
    pass
