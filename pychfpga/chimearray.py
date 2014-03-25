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

#import icecore.python.icecore as icecore
import icecore



# class ChimeException(IceException):
#     pass

class ChimeArray(icecore.IceArray):
    """
    Provides access to arrays of ICEBoards and ICEBoxes.
    """

    def __init__(self, interface_ip_addr):
        """
            'interface_ip' is the IP address of the Ethernet interface through which the array will be accessed.
            If it is specified, a discovery request will be sent on this interface

        Todo:
        2014-03-03 JFC: If interface_ip is not specified, the first call to discover() could scan all adapters and find on which one there are ICEBoards.
        """

        self.logger = logging.getLogger('%s.%s' % (type(self).__module__, type(self).__name__))
        super(type(self), self).__init__(interface_ip_addr = interface_ip_addr, iceboard_class = icecore.IceBoard, mezz_class = None)



#####################################
# Configure the various loggers to provide adequate levels of details

logging.getLogger('iceboard.arm.FpgaBitFile').setLevel(logging.INFO)
logging.getLogger('requests.packages').setLevel(logging.WARN)
logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)

if __name__ == '__main__':

    if '__opened_sockets__' in globals(): # i.e. if __main__ has an __opened_sockets__ attribute
        while __opened_sockets__: # close all sockets so we won't get a 'socket already opened' error because of a previous run
            __opened_sockets__.pop().close()
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
    logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')

    logger = logging.getLogger(__name__)
    logger.info('------------------------')
    logger.info('chimearray')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))
    # Create the new chFPGA object.


    ca = ChimeArray(args.if_ip)
    # ice.status()

    bitfile = icecore.FpgaBitFile('../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')#('../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')
    c = ca.get_iceboards([7, 14, 19]) # get one or more IceBoards
#    c.configure_fpga(bitfile)


    # # Top level example #1
    # c = ice.get_iceboard(['*5c', '*22'], lock = false) # get one or more IceBoards
    # c.configure_fpga(bitfile= 'bitfile', ip_addr = 'auto', port = 'auto') # set the firmware and networking if using the FPGA direct networking system
    # c.set_id(set_id_from_slot_and_crate) # Assign an experiment-specific id like 'R0C00S01' for Rack 0 Crate 0 Slot 1
    # c.sortby('id')

    # c.open() # establish connection to the firmware.  A ZMQ socket could be used if possible


    # c.status() # each board shows its status in turn
    # c.set_data_source('funcgen') # set data source on all boards at once
    # c.get_fpga_serial() # returns a dictionary of values with the keys being the id
    # c.close()


    # # Top level example #1
    # c.configure_fpga(['*5C', '*1c'], bitfile= 'bitfile', ip_addr = ['auto', '10.10.10.900'], port = ['auto', 41005]) # set the firmware and networking if using the FPGA direct networking system


    # c = ice.get_iceboard('*5c') # get one or more IceBoards
    # c.open() # establish connection to the firmware.  A ZMQ socket is used if possible

    # c.status() # each board shows its status in turn
    # c.set_data_source('funcgen') # set data source on all boards at once
    # c.close()
