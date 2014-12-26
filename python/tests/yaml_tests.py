'''
YAML session tests.

You must execute these tests from the top level:

    icecore$ nosetests

...in order to correctly locate the right code.
'''

from hardware_map import HardwareMap, HWMResource
from iceboard import IceBoard
from session import load_session

import unittest


class YAMLTestCase(unittest.TestCase):

    def test_basic_sanity(self):
        assert load_session('this is a string') == 'this is a string'

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
