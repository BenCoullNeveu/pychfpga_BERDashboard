#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
icearray.py module
Provides access to an array of ICEBoards and ICEBoxes (backplanes)

 History:
        2014-03-04 JFC: Created
"""
import argparse
import logging

import hardware_map
# reload(hardware_map) # make sure we get a new Base

import iceboard
from iceboard import IceBoard
from icecore.fpga_bitstream import FpgaBitstream

class IceException(Exception):
    pass

class IceArray(object):
    """
    Provides access to the ressources of the IceArray by using the HardwareManager.

    This class specializes the HardwareManager by providing methods that are aware of specific hardware such as:
       - IceBoards
       - IceBoxes
       - IceBoard mezzanines

    More specifically, this class allow auto-discovery of these ressources
    and/or and loading of those from a file.

    Also, the class allows the specification of the Ethernet interface IP
    address needed for direct host-to-FPGA communications (which is not needed
    if communications are done through the ARM).
    """

    @staticmethod
    def close_all_sessions():
        """
        Close all existing sessions.
        """
        from sqlalchemy.orm.session import Session
        Session.close_all()

    def __init__(self, uri='sqlite:///:memory:', interface_ip_addr=None,  *args, **kwargs):
        """
        'interface_ip_addr' is the IP address of the Ethernet interface
            that will be used for direct FPGA communications (either discovery
            broadcasts or for opening command/data sockets)

        Todo:

        2014-03-03 JFC: If interface_ip is not specified, the first call to
            discover() could scan all adapters and find on which one there are
            ICEBoards.
        """

        # super(type(self), self).__init__(uri='sqlite:///:memory:', *args, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Init IceArray parent')
        self.interface_ip_addr = interface_ip_addr

        # set the interface IP address on the FPGA irmware class attribute so
        # this address is used for any firmware instances created on this
        # computer.
        import fpga_core
        fpga_core.FpgaCoreFirmware.interface_ip_addr = interface_ip_addr

        self._hwmap = hardware_map.HardwareMap(uri=uri, *args, **kwargs)
        # Remove the logger handlers that is created for the SQLAlchemy Engine. We want to use our own top level handler.
        # If we don't do this, the SQLAlchemy messages get displayed twice
        sa_logger =  logging.getLogger('sqlalchemy.engine.base.Engine')
        while sa_logger.handlers:
            sa_logger.removeHandler(sa_logger.handlers[0])

    def __getattr__(self, name):
        """
        Redirects all attributes access to the hardware map (Session) object.
        We do this because we can't just inherit a HardwareMap, because it
        does not return a HardwareMap object
        """
        return getattr(self._hwmap, name)

    def __dir__(self):
        # return type(self).__dict__ + self.__dict__ + dir(self._hwmap)
        return dir(self._hwmap)

    def discover(self, source_subarrays = [0] , timeout=0.1):
        """
        Discover all hardware and firmware resources on the specified
        interface(s) and add them to the database.
        """
        iceboard.discover(self, timeout = timeout)
        self.commit() # commit any changes made during discovery
        #
    def load_iceboards(self, filename):
        """
        """
        iceboard.load(self, filename)
        self.commit() # commit any changes made during discovery

    def get_fpga_bitstream(self, *args, **kwargs):
        """ Get a bitstream from the database or create one if it does not exist. Returns the database object.
        This is a proxy for FpgaBitstream.get_bitstream()
        """
        return FpgaBitstream.get_bitstream(self,*args, **kwargs)


    def get_iceboards(self, serials=[], *args, **kwargs):
        """
        Returns a list of all ICEBoards covered by the specified scope
        """
        if serials:
            args.append(IceBoard.serial_number.in_(serials))
        kwargs['locked']=0 # force selection of non-locked boards
        if 'present' not in kwargs:
            kwargs['present'] = 1
        return self.query(IceBoard).filter(*args).filter_by(**kwargs)

    def status(self):
        print 'The array contains the following resources'
        print self.get_iceboards()

def close_all_sockets():
    """
    Close all the sockets that has been opened and were registered in the main module __opened_sockets__ attribute.
    """
    import __main__
    if '__opened_sockets__' in vars(__main__): # i.e. if __main__ has an __opened_sockets__ attribute
        while __main__.__opened_sockets__: # close all sockets so we won't get a 'socket already opened' error because of a previous run
            __main__.__opened_sockets__.pop().close()


if __name__ == '__main__':
    logging.getLogger('iceboard.arm.FpgaBitFile').setLevel(logging.INFO)
    logging.getLogger('requests.packages').setLevel(logging.WARN)
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)

    close_all_sockets()

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=['info','debug'], default='debug', help='Logging level')
    parser.add_argument('-i', '--if_ip', action = 'store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. If not specified, the controller will attempt to identify the proper host based on the FPGA IP address.')
    args = parser.parse_args()

    log_level = {'info': logging.INFO, 'debug': logging.DEBUG}[args.log_level]
    logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')

    logger = logging.getLogger(__name__)
    logger.info('------------------------')
    logger.info('icearray')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))

    ice = IceArray(args.if_ip)

    bitfile = arm.FpgaBitFile('../../../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')#('../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')
    c = ice.get_iceboards([7, 14, 19]) # get one or more IceBoards
