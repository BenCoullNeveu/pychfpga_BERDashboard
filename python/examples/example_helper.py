"""
Helper module used with example code. It:
   - Gets command-line arguments like iceboard hostnames,  bitfile name,
     desired logging target and level and performs basic checks
   - Clears any previous logging handlers and set the SQLAlchemy logging to a
     known level.
"""

import argparse
import logging


def get_command_line_arguments():

    # This is the bitfile that is generated if implementing the the Vivado
    # project located in
    # icecore/rtl/projects/iceboard_top_example/iceboard_top_example.xpr
    default_bitfile = (
        '../../rtl/projects/iceboard_top_example'
        '/iceboard_top_example.runs/impl_1/iceboard_top_example.bit')

    # Configure the various loggers to provide adequate levels of details
    log_levels = {'info': logging.INFO, 'debug': logging.DEBUG}

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('-t', '--log_target', action = 'store', type=str, default='stream', help="Logging target ('stream', 'syslog' or a filename)")
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=log_levels, default='debug', help='Logging level')
    parser.add_argument('-b', '--iceboards', action = 'store', nargs='+', type=str, help="Space-separated list of the iceboard hostnames (e.g. 10.10.10.7 or iceboard0007.local if the mDNS system is operational")
    parser.add_argument('-s', '--subarray', action = 'store', nargs='+', type=int, help='Space-separated list of subarrays to include')
    parser.add_argument('-f', '--bitfile', action='store', type=str, default= default_bitfile,  help='Filename of the bitfile used to to program the FPGAs')
    args = parser.parse_args()

    log_level = log_levels[args.log_level]

    if args.log_target == 'stream':
        log_handler = logging.StreamHandler()
    elif args.log_target == 'syslog':
        log_handler = logging.handlers.SysLogHandler()
    else:
        log_handler = logging.FileHandler(args.log_target)

    # Check if specified iceboards are on-line
    from icecore import TuberObject
    for arm_hostname in args.iceboards:
        iceboard_is_present = TuberObject.ping(arm_hostname)
        if not iceboard_is_present:
            raise RuntimeError("Iceboard could not be found at '%s'"
                               % arm_hostname)

    logger = logging.getLogger('')
    logger.handlers = []
    sql_logger = logging.getLogger('sqlalchemy.engine.base.Engine')
    sql_logger.setLevel(logging.INFO)

    args.log_handler = log_handler
    args.log_level = log_level
    return args
