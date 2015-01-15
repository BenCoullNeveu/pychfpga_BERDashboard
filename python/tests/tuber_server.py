'''
Fake server for TuberObjects, using a Tornado event loop.
'''

import json
import threading
import inspect

from tornado.ioloop import IOLoop
from tornado.gen import Task, coroutine, Return
from tornado.web import RequestHandler, Application

# Object registry, indexed by (port, object) tuple.
_objectregistry = {}
_thread = None


class TuberHandler(RequestHandler):
    @coroutine
    def post(self):

        requests = json.loads(self.request.body)

        if type(requests) == dict:
            results = yield self.tuber_handler(requests)
        else:
            results = yield [self.tuber_handler(r) for r in requests]

        self.write(json.dumps(results))

    @coroutine
    def tuber_handler(self, request):
        objname = request['object'] if 'object' in request else None
        methodname = request['method'] if 'method' in request else None
        propertyname = request['property'] if 'property' in request else None

        if not objname:
            raise Return({'error': 'Object not specified'})

        port = int(self.request.host.split(':')[-1])

        global _objectregistry

        if (port, objname) not in _objectregistry:
            raise RuntimeError(
                'Port %i or object %s not found in registry.' % (
                    port, objname))

        obj = _objectregistry[(port, objname)]

        if not methodname and not propertyname:
            # Returning object metadata.
            methods = []
            properties = []

            for c in dir(obj):
                if c[0] == '_':
                    continue

                if callable(getattr(obj, c)):
                    methods.append(c)
                else:
                    properties.append(c)

            explanation = summary = ''
            if hasattr(obj, '__doc__'):
                summary = obj.__doc__.splitlines()[0]
                explanation = '\n'.join(obj.__doc__.splitlines()[1:])

            raise Return({
                'result': {
                    'name': obj.__class__.__name__,
                    'explanation': explanation,
                    'summary': summary,
                    'methods': methods,
                    'properties': properties,
                }})

        if methodname and hasattr(obj, methodname):
            # Returning the results from a method call
            method = getattr(obj, methodname)
            args = request['args'] if 'args' in request else []
            kwargs = request['kwargs'] if 'kwargs' in request else {}
            try:
                result = yield method(*args, **kwargs)
            except Exception as e:
                raise Return({'error': {'message': e.message}})
            raise Return({'result': result})

        if propertyname and hasattr(obj, propertyname):
            # Returning a method description or property evaluation
            attr = getattr(obj, propertyname)

            # Simple case: just a property evaluation
            if not callable(attr):
                raise Return({'result': attr})

            # Complex case: return a description of a method
            args = []
            (a, _, _, _) = inspect.getargspec(attr)
            for p in a:
                args.append({
                    "type": -1,  # no type information provided
                    "name": a,
                    "description": "no description",
                })

            explanation = summary = ''
            if hasattr(obj, '__doc__'):
                summary = obj.__doc__.splitlines()[0]
                explanation = '\n'.join(obj.__doc__.splitlines()[1:])

            raise Return({
                'result': {
                    "name": propertyname,
                    "explanation": explanation,
                    "summary": summary,
                    "args": []
                },
            })

        raise Return({'error': 'Property or method not found.'})


def register(port, objname, obj):
    _objectregistry[(port, objname)] = obj


def launch():

    # We need to ensure the server thread starts up fully before creating any
    # client interactions. We do this using a semaphore.
    s = threading.Semaphore(0)

    # Start up a background webserver
    def start_tornado():
        application = Application([
            (r"/tuber", TuberHandler),
        ])
        for (port, _) in _objectregistry:
            application.listen(port)

        # The client may now resume
        s.release()

        IOLoop.instance().start()

    global _thread
    _thread = threading.Thread(target=start_tornado)
    _thread.start()
    s.acquire()


def kill():
    # Tell the web server to shut down
    ioloop = IOLoop.instance()
    ioloop.add_callback(lambda x: x.stop(), ioloop)
    _thread.join()


# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
