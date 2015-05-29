'''
YAML session tests.

You must execute these tests from the top level:

    icecore$ nosetests

...in order to correctly locate the right code.
'''

from hardware_map import HardwareMap, HWMResource
from schema import IceBoard
from session import load_session

import unittest


class YAMLTestCase(unittest.TestCase):

    def test_basic_sanity(self):
        '''Trying to parse some trivial YAML'''
        assert load_session('this is a string') == 'this is a string'

    def test_create_iceboard(self):
        '''Trying to create a single IceBoard'''
        hwm = load_session('''
                !HardwareMap
                    - !IceBoard
                        hostname: iceboard004.local
                        serial: "004"
        ''')

        ib = hwm.query(IceBoard).one()
        assert ib.serial == "004"
        assert ib.hostname == 'iceboard004.local'

    def test_create_crate(self):
        '''Trying to create an IceCrate with two IceBoards'''
        hwm = load_session('''
                !HardwareMap
                    - !IceCrate
                        slots:
                            1: !IceBoard
                                hostname: iceboard004.local
                                serial: "004"
                            5: !IceBoard
                                hostname: iceboard005.local
                                serial: "005"
        ''')

        (ib1, ib2) = hwm.query(IceBoard).all()
        assert ib1.serial == "004"
        assert ib1.hostname == 'iceboard004.local'
        assert ib2.serial == "005"
        assert ib2.hostname == 'iceboard005.local'


# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
