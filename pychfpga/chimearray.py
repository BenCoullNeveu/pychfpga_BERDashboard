#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
chimearray.py module
Example code that demonstrate the use of the 'icecore' library to access arrays of IceBoards in the context of CHIME.

 History:
        2014-03-24 JFC: Created
        2015-04-20 JM: cleaned and simplified (was very messy). Tested with chfpga firmware git tag 8428bb965 and ch_acq software tag adfad2520
"""
#import time
import argparse
import logging
import logging.handlers
import __main__

# IT IS IMPORTANT TO START THE PATH AT CHFPGA
from pychfpga.MGADC08 import MGADC08
from pychfpga.core.icecore.session import load_session as load_yaml
from pychfpga.core.icecore import IceBoardPlus
from pychfpga.core.chFPGA_controller import chFPGA_controller
from pychfpga.core import close_all_sockets

#####################################


if __name__ == '__main__':

    reload(logging) # clear any previous logger set-up that is stored in the logging module
    reload(logging.handlers) # we need to reload the handlers as well so they are inheriting from the newly loaded Handler class defined in freshly reloaded logging, not the old one. Otherwise we get errors.

    close_all_sockets()

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('-t', '--log_target', action='store', type=str, default='syslog', help="Logging target ('stream', 'syslog' or a filename)")
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=['info','debug'], default='debug', help='Logging level')
    parser.add_argument('-s', '--subarray', action = 'store', type=int, help='Subarrays to include')
    parser.add_argument('-f', '--force', action = 'store', type=int, default=0, help='Forces reprogramming of the FPGAs even if they are already programmed')
    parser.add_argument('-i', '--if_ip', action = 'store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. If not specified, the controller will attempt to identify the proper host based on the FPGA IP address.')
    parser.add_argument('-b', '--bitfile', action = 'store', type=str, default= '../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit',  help='Filename of the bitfile used to to program the FPGAs')
    parser.add_argument('-y', '--yamlfile', action = 'store', type=str, default= 'yaml_iceboard_list.txt',  help='Yaml file with list of boards and their respective IP addresses and handlers.')
    args = parser.parse_args()
    log_levels = {'info': logging.INFO, 'debug': logging.DEBUG}

    #__main__._host_interface_ip_addr = args.if_ip # NOT NEEDED SO FAR BUT ANYWAYS

    # -------------------------------
    # Set-up logging
    # -------------------------------

    logger = logging.getLogger('')
    logger.handlers = []  # Clear all existing handlers

    # Make sure SQLAlchemy does not log too much
    sql_logger = logging.getLogger('sqlalchemy.engine.base.Engine')
    sql_logger.setLevel(logging.INFO)

    if args.log_target == 'stream':
        log_handler = logging.StreamHandler()
    elif args.log_target == 'syslog':
        log_handler = logging.handlers.SysLogHandler()
    else:
        log_handler = logging.FileHandler(args.log_target)

    # Set-up log for this test run
    logger.setLevel(log_levels[args.log_level])
    logger.addHandler(log_handler)

    logger.info('%s: ------------------------' % __file__)
    logger.info('%s: C H I M E A R R A Y' % __file__)
    logger.info('%s: ------------------------' % __file__)
    logger.info('%s: Called with: %s' % (__file__, ', '.join('%s=%s' % (key, repr(value)) for (key,value) in args.__dict__.items())))
    # Create the new chFPGA object.

    # Get fpga bitstream
    with open(args.bitfile, 'rb') as bitfile:
        fpga_bitstream = bitfile.read()

    # Create new fpga query object
    with open(args.yamlfile, 'rb') as yamlfile:
        ca =  load_yaml(yamlfile)   
    c = ca.query(IceBoardPlus).filter_by(subarray=args.subarray) # c is kind of standard notation for a list of iceboards now.
    
    # Associate the fpga_bitstream with the target Handler    
    c.set_handler(chFPGA_controller, fpga_bitstream)
    
    # Program fpga
    c.set_fpga_bitstream(force = args.force)

    # Print resuts
    print 'The following IceBoards were found in Subarray %r through interface %s:' % (args.subarray, args.if_ip)
    for ib in c:
        print "  c%i = IceBoard SN%s in slot %r. Handler = '%s'" % (int(ib.serial), ib.serial, ib.slot, ib.handler_name)
        #setattr(__main__, 'c%i' % int(ib.serial), ib) #TAB COMPLETION DOES NOT WORK WITH THIS