'''
Tuber tests.

You must execute these tests from the top level:

    icecore$ nosetests

...in order to correctly locate the right code.

We create a Python webserver that acts like a Tuber back-end server,
and interrogate it using our parallel-processing interface.
'''

from hardware_map import HardwareMap, HWMResource, TuberHWMResource

from sqlalchemy import Column, Integer, String, UniqueConstraint

import unittest
import time

import tuber_server

from tornado.ioloop import IOLoop
from tornado.gen import Task, coroutine


# Mock Tuber objects.
class RemoteObject(object):
    '''A fake TuberObject.'''

    def __init__(self, port):
        self.__port = port
        self.__n = 0

    @coroutine
    def set_n(self, new_n):
        '''Set up some parameter.'''
        self.__n = new_n

    @coroutine
    def get_n(self):
        '''Retrieve some parameter.'''
        return self.__n

    @coroutine
    def get_port(self):
        return self.__port

    @coroutine
    def sleep(self, delay):
        yield Task(IOLoop.instance().add_timeout, time.time() + delay)


# Mock ORM objects
class DummyTuberClass(TuberHWMResource):
    __tablename__ = __name__ + 'dummy_parent'
    __table_args__ = (UniqueConstraint('cls', 'port'),)
    __mapper_args__ = {'polymorphic_identity': 'base', 'polymorphic_on': 'cls'}

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    port = Column(Integer, nullable=False)


# Test Cases
class InstantiationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Create our hardware mapper
        cls._hwm = HardwareMap()

        for n in range(10):
            port = n + 9876

            # Register a remote object
            tuber_server.register(port,
                                  "DummyTuberClass",
                                  RemoteObject(port=port))

            # Add local references to the HWM at the same time
            cls._hwm.add(DummyTuberClass(
                port=port,
                hostname="localhost:%i" % port))

        # Launch the server
        tuber_server.launch()

        cls._hwm.commit()

    @classmethod
    def tearDownClass(cls):
        tuber_server.kill()

    def test_random_tuber_calls(self):

        # Set "n" on all tuber classes
        tubers = self._hwm.query(DummyTuberClass)
        assert tubers.count() == 10
        tubers.set_n(10)
        assert set(tubers.get_n()) == set([10])

        # Ensure we can retrieve the correct, distinct port numbers from
        # each object and compare them with our ORM ports.
        assert tuple(tubers.get_port()) == tuple(tubers.port)

    def test_concurrency(self):
        # See if we can sleep for 0.5s per object, and come back in ~0.5s
        tubers = self._hwm.query(DummyTuberClass)
        t1 = time.time()
        tubers.sleep(0.5)
        t2 = time.time()

        assert t2-t1 < 1

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
