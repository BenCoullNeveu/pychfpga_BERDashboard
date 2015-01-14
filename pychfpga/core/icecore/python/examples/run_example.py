"""
Helper module used to run example code. It:
   - Offers a command-line interface to pass common arguments like bitfile
     name, desired logging target and level etc.
   - Make sure the icecore package is available (even if the script run in the
     example design folder, and even if the example folder is deep within the
     icecore package itself)
   - Merge the test script variables back into the current ipython session so
     the user can interactively send commands

All example functions are located in the example_scripts.py.
An example function can be invoked in ipython with:

run -i run_example.py example1 --log_target syslog --iceboards 0007 --bitfile ../../rtl/projects/iceboard_top_example/iceboard_top_example.runs/impl_1/iceboard_top_example.bit

You can then explore the objects created by example1(...).
"""

import argparse
import logging
import sys
import os

# This is the bitfile that is generated if implementing the the Vivado project
# located in
#   icecore/rtl/projects/iceboard_top_example/iceboard_top_example.xpr
default_bitfile = (
    '../../rtl/projects/iceboard_top_example'
    '/iceboard_top_example.runs/impl_1/iceboard_top_example.bit')

if __name__ == '__main__':

    try:
        import icecore
    except ImportError:
        # Compute an absolute path of the folder containing icecore (3 levels up)
        icecore_path = os.sep.join(
            os.path.realpath(__file__).split(os.sep)[:-4])

        if icecore_path not in sys.path:
            sys.path.append(icecore_path)
            print "Adding '%s' to path to allow access to icecore" % icecore_path

    # Configure the various loggers to provide adequate levels of details
    log_levels = {'info': logging.INFO, 'debug': logging.DEBUG}

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('example', metavar='S', type=str, nargs='+', help='Example script to run')
    parser.add_argument('-t', '--log_target', action = 'store', type=str, default='stream', help="Logging target ('stream', 'syslog' or a filename)")
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=log_levels, default='debug', help='Logging level')
    parser.add_argument('-b', '--iceboards', action = 'store', nargs='+', type=str, help="Space-separated list of the serial numbers of iceboard to include (keep all leading '0')")
    parser.add_argument('-s', '--subarray', action = 'store', nargs='+', type=int, help='Space-separated list of subarrays to include')
    parser.add_argument('--bitfile', action = 'store', type=str, default= default_bitfile,  help='Filename of the bitfile used to to program the FPGAs')
    args = parser.parse_args()

    log_level = log_levels[args.log_level]

    if args.log_target == 'stream':
        log_handler = logging.StreamHandler()
    elif args.log_target == 'syslog':
        log_handler = logging.handlers.SysLogHandler()
    else:
        log_handler = logging.FileHandler('args.log_target')

    # Check if specified iceboards are on-line
    from icecore import TuberObject
    for serial in args.iceboards:
        iceboard_is_present = TuberObject.ping('iceboard%s.local' % serial)
        if not iceboard_is_present:
            raise RuntimeError("Iceboard serial '%s' could not be found on the network" % serial)

    # Setup logging
    reload(logging)  # clear any previous logger set-up
    reload(logging.handlers)
    logger = logging.getLogger('')
    # logger.setLevel(log_level)
    logger.addHandler(log_handler)
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)

    # Load the test script module
    import example_scripts
    reload(example_scripts)
    from example_scripts import *

    # Call the main example script
    for example in args.example:
        try:
            print '----------------------------------------------'
            print 'Running example %s' % example
            print '----------------------------------------------'
            if not hasattr(example_scripts, example):
                raise NameError("Function '%s' does not exist" % example)
            example_locals = getattr(example_scripts, example)(
                log_handler=log_handler,
                log_level=log_level,
                bitfile=args.bitfile,
                iceboard_serial_numbers = args.iceboards)
            locals().update(example_locals)
        finally:
            print '----------------------------------------------'
            print 'Finished running %s' % example
            print '----------------------------------------------'
