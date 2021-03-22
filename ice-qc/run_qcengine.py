#!/usr/bin/env python

from wtl.xreport import util
import os

if __name__ == '__main__':
    """ Run the test in this file."""
    config_filename = os.path.realpath(os.path.join(os.path.dirname(__file__), 'qcengine_test_config.yaml'))
    v = util.run_tests(config_filename)
    locals().update(v)  # bring local variables from the test runner into the current namespace for easier debugging
