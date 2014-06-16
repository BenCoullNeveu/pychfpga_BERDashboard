#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
chimearray.py module
Example code that demonstrate the use of the 'icecore' library to access arrays of IceBoards in the context of CHIME.

 History:
        2014-03-24 JFC: Created
"""
#import time
import argparse
import logging
import logging.handlers
reload(logging) # clear any previous logger set-up that is stored in the logging module
reload(logging.handlers) # we need to reload the handlers as well so they are inheriting from the newly loaded Handler class defined in freshly reloaded logging, not the old one. Otherwise we get errors.

# class MyLogger(logging.Logger):
#     def __init__(self, name):
#         logging.Logger.__init__(self, name)


#     def makeRecord(self, *args, **kwargs):
#         rec=super(type(self), self).makeRecord(*args, **kwargs)
#         rec.context = __name__
#         # rec.name = 'wowo'
#         return rec

# logging.setLoggerClass(MyLogger)

def delete_modules(module_name):
    import sys
    for name in [n for n in sys.modules.keys() if n.startswith(module_name)]:
        del sys.modules[name]

# delete_modules('sqlalchemy')
# delete_modules('icecore')

from icecore import hardware_map
from icecore import tuber
# reload(hardware_map)
# reload(tuber)

from icecore.icearray import IceArray, close_all_sockets
from icecore.fpga_bitstream import FpgaBitstream
from icecore.iceboard import IceBoard

from core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware

#####################################

import inspect
import __main__

class CompletionFilter(object):
    @staticmethod
    def filter(record):
        return not any(('completer.py' in ss[1] for ss in inspect.stack()))

if __name__ == '__main__':

    # Configure the various loggers to provide adequate levels of details
    logging.getLogger('icecore.fpga_bitstream.FpgaBitstream').setLevel(logging.DEBUG)
    # logging.getLogger('requests.packages').setLevel(logging.WARN)
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)

    close_all_sockets()

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    # parser.add_argument('--init', action = 'store', type=int, default=1, help='Initialization level: -1: Just create sockets, 0: connect and read only. 1: initialize hardware')
    # parser.add_argument('-f', '--sampling_frequency', action = 'store', type=float, default=850, help='Sampling frequency of the ADC in MHz')
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=['info','debug'], default='debug', help='Logging level')
    parser.add_argument('-s', '--subarray', action = 'store', nargs='+', type=int, help='Space-separated list of subarrays to include')
    # parser.add_argument('-g', '--group_frames', action = 'store', type=int, default=4, help='Number of frames to group before sending to the GPU or FPGA correlator. The total size of the frame, including the header and ethernet obverhead, cannot exceed 8 kibytes.')
    # parser.add_argument('--enable_gpu_link', action = 'store', type=int, default=0, help='Enables the GPU link transmission')
    parser.add_argument('--force', action = 'store', type=int, default=0, help='Forces reprogramming of the FPGAs even if they are already programmed')
    parser.add_argument('-i', '--if_ip', action = 'store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. If not specified, the controller will attempt to identify the proper host based on the FPGA IP address.')
    parser.add_argument('--bitfile', action = 'store', type=str, default= '../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit',  help='Filename of the bitfile used to to program the FPGAs')
    parser.add_argument('--bitfile_crc', action = 'store', type=int, help='CRC of the bitfile used to to program the FPGAs')
    #parser.add_argument('--subarray', action = 'store', type=int, default=2, help='Which subarray to use')
    args = parser.parse_args()
    log_level = {'info': logging.INFO, 'debug': logging.DEBUG}[args.log_level]

    # logging.basicConfig(level=log_level, format='%(asctime)s  %(context)s %(name)-32s %(levelname)-10s : %(message)s')

    try:
        del logger
    except NameError:
        pass
    logger = logging.getLogger('')
    logger.setLevel(log_level)
    handler = logging.handlers.SysLogHandler()
    # handler = logging.StreamHandler()
    # handler.addFilter(CompletionFilter)
    logger.addHandler(handler)

    logger.info('------------------------')
    logger.info('chimearray')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))
    # Create the new chFPGA object.

    IceArray.close_all_sessions() # close all previously opened sessions

    ca = IceArray(uri='sqlite:///test.db', interface_ip_addr=args.if_ip)
    ca.load_iceboards('iceboard_list.txt')
    ca.discover() # automatically update the hardware map database with discovered resources

    bitfile_filename = args.bitfile
    # fpga_bitstream = FpgaBitstream(bitfile_filename, ChimeFpgaFirmware) #
    # fpga_bitstream = FpgaBitstream.get_bitstream(ca, bitfile_filename, ChimeFpgaFirmware) # Get a new bitstream from the database (or create a new database entry if it does not exist yet)
    if args.bitfile_crc:
        fpga_bitstream = ca.get_fpga_bitstream(crc = args.bitfile_crc) # Get a new bitstream from the database
    else:
        fpga_bitstream = ca.get_fpga_bitstream(args.bitfile, ChimeFpgaFirmware) # Get a new bitstream from the database (or create a new database entry if it does not exist yet)


    # c = ca.get_iceboards(subarray=args.subarray).index_by(IceBoard.serial_number) # get one or more IceBoards from specified subarray
    c = ca.get_iceboards(subarray=args.subarray) # get one or more IceBoards from specified subarray

    # shortcut to index c[7] as c7 etc.
    for (serial,ice) in [(ice.serial_number, ice) for ice in c]:
        setattr(__main__, 'c%i' % serial, ice)
    # c23.set_fpga_firmware(fpga_bitstream,  configure_fpga=True, force=args.force, store_in_database=True) # associate boards with specified firmware and configure the selected FPGA
    # c24.set_fpga_firmware(fpga_bitstream,  configure_fpga=True, force=args.force, store_in_database=True) # associate boards with specified firmware and configure the selected FPGA
    # c19.set_fpga_firmware(fpga_bitstream,  configure_fpga=True, force=args.force, store_in_database=True) # associate boards with specified firmware and configure the selected FPGA
    # c23.open()
    # c24.open()
    # c19.open()
    # b23=c23.fpga.BP_SHUFFLE
    # b24=c24.fpga.BP_SHUFFLE
    # b19=c19.fpga.BP_SHUFFLE
    # g0=b24.gtx[0]
    # g1=b23.gtx[1]
    # g2=b24.gtx[3]
    # g3=b19.gtx[2]

    # cc.set_fpga_firmware(crc32=1910844937,  configure_fpga=True, force=args.force, store_in_database=True) # associate boards with specified firmware and configure the selected FPGA
    # c.open() # establish communication with the boards so we can access their attributes and methods
