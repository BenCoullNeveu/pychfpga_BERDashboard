'''
Tuber tests.

These test cases must be able to find "icecore" in the PYTHONPATH.
you can then execute them as follows:

    $ python -m icecore.tests.tuber_tests

We create a Python webserver that acts like a Tuber back-end server,
and interrogate it using our parallel-processing interface.
'''

from icecore.hardware_map import HardwareMap, HWMResource
from icecore.tuber import TuberHWMResource

from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import reconstructor

import tornado.ioloop
import tornado.web

import unittest
import json
import threading
import inspect

###
### Mock Tuber objects.
###

class DummyRemoteObject(object):
    '''A fake TuberObject.'''

    __n = 0

    def set_n(self, new_n):
        '''Set up some parameter.'''
        self.__n = new_n

    def get_n(self):
        '''Retrieve some parameter.'''
        return self.__n

    @property
    def n(self):
        '''Another way to retreive 'n'.'''
        return self.__n

# Index object registries by URI, so we can give each web-server port
# a separate class instance. That way, local changes stay local.
TuberObjectRegistry = {
    'localhost:9877': {
        "DummyRemoteObject": DummyRemoteObject(),
    },
    'localhost:9878': {
        "DummyRemoteObject": DummyRemoteObject(),
    },
}

class TuberHandler(tornado.web.RequestHandler):
    def post(self):

        requests = json.loads(self.request.body)

        if type(requests) == dict:
            results = self.tuber_handler(requests)
        else:
            results = []
            for r in requests:
                results.append(self.tuber_handler(r))

        self.write(json.dumps(results))

    def tuber_handler(self, request):
        objname = request['object'] if 'object' in request else None
        methodname = request['method'] if 'method' in request else None
        propertyname = request['property'] if 'property' in request else None

        if not objname:
            return { 'error': 'Object not specified' }

        if self.request.host not in TuberObjectRegistry:
            raise RuntimeError('Host not found in registry.')

        if objname not in TuberObjectRegistry[self.request.host]:
            return { 'error': "Object '%s' not registered" % objname }

        obj = TuberObjectRegistry[self.request.host][objname]

        if not methodname and not propertyname:
            # Returning object metadata.
            methods = []
            properties = []

            for c in dir(obj):
                if c[0]=='_':
                    continue

                if callable(getattr(obj, c)):
                    methods.append(c)
                else:
                    properties.append(c)

            explanation = summary = ''
            if hasattr(obj, '__doc__'):
                summary = obj.__doc__.splitlines()[0]
                explanation = '\n'.join(obj.__doc__.splitlines()[1:])

            return { 'result':
                {
                    'name': obj.__class__.__name__,
                    'explanation': explanation,
                    'summary': summary,
                    'methods': methods,
                    'properties': properties,
                }
            }

        if methodname and hasattr(obj, methodname):
            # Returning the results from a method call
            attr = getattr(obj, methodname)
            args = request['args'] if 'args' in request else []
            kwargs = request['kwargs'] if 'kwargs' in request else {}
            return {
                'result': attr(*args, **kwargs),
            }

        if propertyname and hasattr(obj, propertyname):
            # Returning a method description or property evaluation
            attr = getattr(obj, propertyname)

            # Simple case: just a property evaluation
            if not callable(attr):
                return { 'result': attr }

            # Complex case: return a description of a method
            args = []
            (a, _, _, _) = inspect.getargspec(attr)
            for p in a:
                args.append({
                    "type": -1, # no type information provided
                    "name": a,
                    "description": "no description",
                })

            explanation = summary = ''
            if hasattr(obj, '__doc__'):
                summary = obj.__doc__.splitlines()[0]
                explanation = '\n'.join(obj.__doc__.splitlines()[1:])

            return {
                'result': {
                    "name": propertyname,
                    "explanation": explanation,
                    "summary": summary,
                    "args": []
                },
            }

        return { 'error': 'Property or method not found.' }

###
### Mock ORM objects
###

class DummyTuberClass(TuberHWMResource):
    __tablename__ = 'dummy_parent'
    __table_args__ = (UniqueConstraint('cls','serial'),)
    __mapper_args__ = { 'polymorphic_identity': 'base', 'polymorphic_on': 'cls' }

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    serial = Column(Integer, nullable=False)

class DummyTuberSubclass(DummyTuberClass):
    __mapper_args__ = { 'polymorphic_identity': 'subclass' }

###
### Test Cases
###

class InstantiationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Start up a number of background webservers.
        def start_tornado():
            application = tornado.web.Application([
                (r"/tuber", TuberHandler),
            ])
            for host in TuberObjectRegistry.keys():
                port = host.split(':')[1]
                application.listen(port)
            tornado.ioloop.IOLoop.instance().start()

        cls.t = threading.Thread(target=start_tornado)
        cls.t.start()
 
        # Create our hardware mapper
        cls._hwm = HardwareMap()

        p1 = DummyTuberSubclass(
                serial=125,
                tuber_uri='http://localhost:9878/tuber',
                tuber_objname='DummyRemoteObject',
        )
        p2 = DummyTuberClass(
                serial=126,
                tuber_uri='http://localhost:9877/tuber',
                tuber_objname='DummyRemoteObject',
        )

        cls._hwm.add_all([p1, p2])
        cls._hwm.commit()

    @classmethod
    def tearDownClass(cls):
        # Tell the web server to shut down
        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.add_callback(lambda x: x.stop(), ioloop)
        cls.t.join()

    def test_random_tuber_calls(self):

        # Set "n" on all tuber classes
        tubers = self._hwm.query(DummyTuberClass)
        assert tubers.count() == 2
        tubers.set_n(0)
        assert set(tubers.get_n()) == set([0])

        # Query the subclass, set n to 100
        s = self._hwm.query(DummyTuberSubclass)
        assert s.count()==1
        s.set_n(100)
        assert set(s.get_n()) == set([100])
        assert set(s.n) == set([100])

        # Now ensure the superclass got updated too.
        assert set(tubers.get_n()) == set([0, 100])
        assert set(tubers.n) == set([0, 100])

if __name__ == '__main__':
    unittest.main()

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
