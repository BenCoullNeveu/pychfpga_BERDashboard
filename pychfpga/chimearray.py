#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
chimearray.py module
Defines ChimeArray class that Provides access to an array of ICEBoards and ICEBoxes (backplanes) configured for CHIME operation.

 History:
        2014-03-24 JFC: Created
"""
#import time
import argparse
import logging
import logging.handlers
reload(logging) # clear any previous logger set-up that is stored in the logging module
reload(logging.handlers) # we need to reload the handlers as well so they are inheriting from the newly loaded Handler class defined in freshly reloaded logging, not the old one. Otherwise we get errors.
#import icecore.python.icecore as icecore
#import icecore
# import core.chFPGA_controller
from icecore.icearray import IceArray, close_all_sockets
from icecore.iceboard.fpgabitfile import FpgaBitFile

# class ChimeException(IceException):
#     pass

#ChimeIceBoard = IceBoard(icecore.arm.ArmFirmware, ChimeFpgaFirmware)
from core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware

class ChimeArray(IceArray):
    """
    Provides access to arrays of ICEBoards and ICEBoxes.
    """

    def __init__(self, interface_ip_addr, **kwargs):
        """
            'interface_ip' is the IP address of the Ethernet interface through which the array will be accessed.
            If it is specified, a discovery request will be sent on this interface

        Todo:
        2014-03-03 JFC: If interface_ip is not specified, the first call to discover() could scan all adapters and find on which one there are ICEBoards.
        """

        self.logger = logging.getLogger('%s.%s' % (type(self).__module__, type(self).__name__))
        super(type(self), self).__init__(interface_ip_addr = interface_ip_addr, **kwargs)



#####################################
# Configure the various loggers to provide adequate levels of details


if __name__ == '__main__':

    logging.getLogger('iceboard.arm.FpgaBitFile').setLevel(logging.INFO)
    logging.getLogger('requests.packages').setLevel(logging.WARN)
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.DEBUG)

    close_all_sockets()

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    # parser.add_argument('--init', action = 'store', type=int, default=1, help='Initialization level: -1: Just create sockets, 0: connect and read only. 1: initialize hardware')
    # parser.add_argument('-f', '--sampling_frequency', action = 'store', type=float, default=850, help='Sampling frequency of the ADC in MHz')
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=['info','debug'], default='debug', help='Logging level')
    # parser.add_argument('-w', '--data_width', action = 'store', type=int, choices=[4,8], default=8, help='Data width of each Re and Im component of the channelizer output')
    # parser.add_argument('-g', '--group_frames', action = 'store', type=int, default=4, help='Number of frames to group before sending to the GPU or FPGA correlator. The total size of the frame, including the header and ethernet obverhead, cannot exceed 8 kibytes.')
    # parser.add_argument('--enable_gpu_link', action = 'store', type=int, default=0, help='Enables the GPU link transmission')
    # parser.add_argument('--ip', action = 'store', type=str, default='10.10.10.11', help='IP address of the board')
    parser.add_argument('-i', '--if_ip', action = 'store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. If not specified, the controller will attempt to identify the proper host based on the FPGA IP address.')
    args = parser.parse_args()

    log_level = {'info': logging.INFO, 'debug': logging.DEBUG}[args.log_level]
    # logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')

    try:
        del logger
    except NameError:
        pass
    logger = logging.getLogger('')
    logger.setLevel(log_level)
    handler = logging.handlers.SysLogHandler()
    # handler = logging.StreamHandler()
    logger.addHandler(handler)

    logger.info('------------------------')
    logger.info('chimearray')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))
    # Create the new chFPGA object.

    ca = ChimeArray(args.if_ip, uri='sqlite:///test.db')
    ca.load_iceboards('iceboard_list.txt')
    #ca.close_all_sessions() # make sure all sessions that might be still open (for instance, if we run this script many times interactively) are closed. Otherwise an object might end up being assigned to multiple sessions.
    ca.discover() # automatically update the hardware map database with discovered resources
    # ice.status()

    bitfile = FpgaBitFile('../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')#('../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')
#    c = ca.get_iceboards([7, 14, 19]) # get one or more IceBoards
    c = ca.get_iceboards() # get one or more IceBoards
    # c.configure_fpga(bitfile)
    c.configure_fpga(bitfile, ChimeFpgaFirmware)
    # c0 = ca.get_iceboards([7]).one() # get one IceBoards
    # c0.configure_fpga(bitfile, ChimeFpgaFirmware)
    # c0.configure_fpga(bitfile)
    # c0.open()
    cc=c[0]

    # bp=ca.get_iceboxes().one()
    # bp[0].get_slot_number()
