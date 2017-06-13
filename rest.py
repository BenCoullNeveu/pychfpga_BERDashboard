""" REST Clients and Servers for CHIME
"""
from __future__ import print_function

import logging
import signal
import traceback
import inspect
import requests
import functools

import tornado.ioloop
import tornado.web
from tornado.gen import coroutine, sleep
from tornado.ioloop import IOLoop


def coroutine_return(*args, **kwargs):
    """ Normally just takes a single positional argument like the return statement. However, for
    convenience, of only keyword arguments are passed, return these arguments as a dict.
    """
    if kwargs and not args:  # if we only have keyword arguments
        raise tornado.gen.Return(kwargs)  # return keyword arguments as a dict
    else:
        raise tornado.gen.Return(*args, **kwargs)  # just pass everything

class RESTClient(object):
    """ This is a Requests-based client (non asynchronous)
    """
    TIMEOUT = 60 # seconds
    DEFAULT_HOST = 'localhost'
    DEFAULT_PORT = 54321

    def __init__(self, hostname=DEFAULT_HOST, port=DEFAULT_PORT):
        self.hostname = hostname
        self.port = port
        self.log = logging.getLogger()

    def __repr__(self):
        return '%s(%s:%s)' % (self.__class__.__name__, self.hostname, self.port)

    def print(self, msg):
        print(msg)

    def print_error(self, msg):
        print(msg)

    def error(self, msg):
        self.print_error(msg)
        raise

    def url(self, endpoint):
        return 'http://%s:%d/%s' % (self.hostname, self.port, endpoint)

    def get(self, endpoint):
        try:
            return requests.get(self.url(endpoint), timeout=self.TIMEOUT).json()
        except requests.exceptions.ConnectionError:
            self.error("Can't connect to REST server at %s:%d for GET request" % (self.hostname, self.port))

    def post(self, endpoint, **kvs):
        try:
            return requests.post(self.url(endpoint), json=kvs, timeout=self.TIMEOUT).json()
        except requests.exceptions.ConnectionError:
            self.error("Can't connect to REST server at %s:%d for PORT request" % (self.hostname, self.port))

class AsyncMixin(object):
    """ Adds heartbeat, keyboard interrupt and shutdown handling methods"""
    def add_periodic_callback(self, callback, period):
        return tornado.ioloop.PeriodicCallback(callback, period).start()

    def add_heartbeat(self, period=1000, heartbeat_string='.'):
        def heartbeat_callback():
            print(heartbeat_string, end='')
        self.add_periodic_callback(heartbeat_callback, period)

    def add_shutdown_handler(self):
        @coroutine
        def shutdown():
            print("Received SHUTDOWN signal")
            yield self.shutdown()
            IOLoop.current().stop()

            # A bit of a hack: close all sockets opened by the HTTP server so we can restart a new
            # server in the same iPython session
            for sock in self.http_server._sockets.values():
                print('Closing socket ', sock.getsockname())
                sock.close()

        def handler(sig, frame):
            IOLoop.current().add_callback_from_signal(shutdown)
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    @coroutine
    def shutdown(self):
        pass

    def __getattr__(self, name):
        if name.startswith('sync_'):
            return functools.partial(self.run_sync, name[5:])
    def __dir__(self):
        attrs = dir(type(self)) + vars(self).keys()
        for name, method in vars(type(self)).items():
            if callable(method) and not name.startswith('_'):
                attrs.append('sync_' + name)
        return attrs

    def run_sync(self, method_name, *args, **kwargs):
        """ Runs `method_name` in a ioloop and returns when completed"""
        return IOLoop.current().run_sync(functools.partial(getattr(self, method_name), *args, **kwargs))

    def run(self):
        try:
            IOLoop.current().start()
        finally:
            IOLoop.current().stop() # make sure the loop is stopped in case the code was interrupted

class AsyncRESTClient(AsyncMixin):
    """Implements a kotekan REST client using a Tornado AsyncHTTPClient .

    All methods are Tornado coroutines so that operations can be performed concurrently on multiple nodes.
    """
    DEFAULT_HOST = 'localhost'
    DEFAULT_PORT = 80

    def __init__(self, hostname=DEFAULT_HOST, port=DEFAULT_PORT):
        self.hostnamename = hostname
        self.port = port
        self.log = logging.getLogger()
        self.client = tornado.httpclient.AsyncHTTPClient()
        self.add_heartbeat()
        self.add_shutdown_handler()

    def url(self, endpoint):
        return 'http://%s:%d/%s' % (self.hostname, self.port, endpoint)

    @coroutine
    def post(self, endpoint, **kws):
        """ Send POST request to the target endpoint, with all keywords arguments being JSON-encoded"""
        coroutine_return((yield self._fetch(endpoint, 'POST', **kws)))

    @coroutine
    def get(self, endpoint):
        coroutine_return((yield self._fetch(endpoint, 'GET')))

    @coroutine
    def _fetch(self, endpoint, method, **kws):
        url = self.url(endpoint)
        if method == 'POST':
            body = tornado.escape.json_encode(kws)
        else:
            body = None
        resp = yield self.client.fetch(url, method=method, headers={"Content-Type": "application/json"}, body=body, raise_error=False)
        try:
            decoded_reply = tornado.escape.json_decode(resp.body)
            if isinstance(decoded_reply, dict):
                error = decoded_reply.get('error','')
            else:
                error = ''
        except ValueError:
            error = 'Invalid JSON reply string %r' % resp.body
        if resp.error:
            error = str(resp.error) + '\n' + error
        if error:
            print('****ERROR****:', error)
            raise RuntimeError(error)
        coroutine_return(decoded_reply)


class JsonRequestHandler(tornado.web.RequestHandler):
    """ RequestHandler than can accept both JSON-encoded and standard HTML POST arguments. Also overrides the `write_error` method to set the 'error' result with the traceback when exceptions occured.

    The user must add the get() or post() method.
    """

    def prepare(self):
        if not self.request.body: return
        print('Headers=', str(list(self.request.headers)))
        content_type = self.request.headers['Content-Type']
        if content_type == 'application/json':
            print('post body=', self.request.body)
            try:
                args = tornado.escape.json_decode(self.request.body)
                self.request.arguments.update(args)
            except ValueError:
                self.send_error(400, error="can't parse JSON")
        elif content_type == 'application/x-www-form-urlencoded':
            print('post body=', self.request.body, 'pre args=', self.request.arguments )
            args = { k:v[-1] for k,v in self.request.arguments.items() }
            self.request.arguments.update(args)

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def write_error(self, status_code, **kvs):
        if 'exc_info' in kvs:
            exc_info = kvs.pop('exc_info')
            kvs['error'] = ''.join(traceback.format_exception(*exc_info))
        # self.set_status(200, reason='There were errors, though') # Prevent the client from raising an HTTP error. The client will recognize errors by looking at the error field.
        print('writing', kvs['error'])
        self.write(kvs)  # kvs is a dict, so it will be json-encoded


class AsyncRESTServer(AsyncMixin):
    """
    Creates a Tornado Web application that will call the endpoint handlers registered with the RESTserver.endpoint decorator.

    GET endpoint methods are coroutines and are tagged with the @endpoint decorator:

        @coroutine
        @endpoint
        def my_GET_endpoint_method(self, handler):
            ...

    POST endpoints are similarly defines::

        @coroutine
        @endpoint
        def my_POST_endpoint_method(self, handler, args):
            ...

    Methods with 2 arguments (i.e method(self, handler)) will only answer to GET requests.

    Methods with 3 arguments (i.e method(self, handler, some_arg_name)) will answer to POST
    requests, and the posted arguments will be passed to `some_arg_name`.

    The method can access to the AsyncRESTServer instance ('self') to obtain context information.


    `handler` is the RequestHandler that is handling the current request and can be used for more sophisticated
    processing or error handling.

    Endpoint methods must be Tornado co-routines, and should therefore `yield` when doing lengthy
    IO-bound operations and shall use `coroutine_return` to return values (do not use the 'return' statement).

    If the endpoint handler is successful, its return value is sent to the client.

    If an uncatched exception has occured, a dictionary containing the 'error' key set with the error information (and traceback) is sent back.

    User can signal an error condition by raising an exception or by returning a dictionary with the 'error' key.
    """


    def __init__(self, hostname='', port=80):
        """ Create a Web server responding to the endpoints defined in the class.

        Parameters:

            hostanme (str): if specified, selects on which interface the server will respond to
                requests. If left empty, the server will respond to all interfaces. If a hostname is
                given (as opposed to a IP address), all IP addresses associated with thtis hostname will
                be used.

            port (int): Port number to which the server will listen to requests. Defaults to port 80.

        """
        self.port = port
        self.log = logging.getLogger()
        # Create the endpoints registered with the @endpoint decorator
        endpoints = [self._create_endpoint(*info) for info in self.get_endpoint_info()]
        self.app = tornado.web.Application(endpoints) # Create the Web application serving those endpoints
        self.http_server = self.app.listen(self.port, hostname=hostname) # Create the web server on the target port in the current ioloop.
        self.add_heartbeat()
        self.add_shutdown_handler()
        # The server will run when the ioloop is started.

    def get_endpoint_info(self):
        """ Return a list of tuples (method_name, endpoint_name, method_args) describing all the
        endpoints supported by the server"""
        info = []
        for method in vars(type(self)).values():
            method_name, endpoint_name, method_args = getattr(method, 'endpoint_info', (None, None, None))
            if method_name:
                info.append((method_name, endpoint_name, method_args))
        return info

    def _create_endpoint(self, method_name, endpoint_name, method_args):
        """ Create an handler tuple (endpoint, handler) for the method `method_name`.

        Parameters:

            method_name (str): Name of the method in this class that handles the endpoint.
                The method must have been decorated @endpoint so it will have been registered.

            endpoint_name (str): Name to be used for the end point on the HTTP requests. Utually the
                same as the method name, with undrscores replaced by dashes.

            method_args (dict): dictionary listing the method parameters. If there are more than two
                (i.e. self and handler), this will be a POST endpoint, otherwise it will be a GET.

        Returns: A endpoint handler tuple (endpoint_name, handler) that will be passed to the
            :meth:`tornado.web.Application()` to answer to that secific handler by calling the
            target method with the passed argument (if a POST request).

        """
        method = getattr(self, method_name)
        has_args = len(method_args) > 2  # any other arguments beyound the mandatory 'self' and 'handler'?
        print('%s: Creating a REST %s endpoint %s for method %s(%s)' % (self.__class__.__name__, ('GET','POST')[has_args], endpoint_name, method_name, ', '.join(method_args)))
        if has_args:
            class Handler(JsonRequestHandler):
                @coroutine
                def post(self):
                    result = yield method(self, **self.request.arguments)
                    # print('Sending POST reply:', result)
                    self.write(tornado.escape.json_encode(result)) # arg must be a string or a dict that will be json-encoded

        else:
            class Handler(JsonRequestHandler):
                @coroutine
                def get(self):
                    result = yield method(self)
                    self.write(tornado.escape.json_encode(result))
        return tornado.web.url(r'/%s' % endpoint_name, Handler)


    @classmethod
    def endpoint(cls, fn, endpoint_name=None):
        """ Decorator that tags the target method as a REST endpoint handler.

        It does that by adding an endpoint_info attribute to the method.

        """
        method_name = fn.__name__
        if endpoint_name is None:
            endpoint_name = method_name.replace('_','-')
        argspecs = inspect.getargspec(fn)
        method_args  = argspecs.args + ['**' + argspecs.keywords] if argspecs.keywords else []
        fn.endpoint_info = (method_name, endpoint_name, method_args)  # add the endpoint info in the function
        return fn # return the original function

endpoint = AsyncRESTServer.endpoint # shortcut
