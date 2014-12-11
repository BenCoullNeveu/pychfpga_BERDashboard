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
from fpga_bitstream import FpgaBitstream

class IceException(Exception):
    pass

class IceArray(object):
    """
    Provides access to the ressources of the IceArray by using the
    HardwareManager. An IceArray is essentially a SQL Session, from which you can issue
    queries to retrieve hardware items described in the HardwareManager
    database. This class also adds some helper functions to simplify operations of the array.

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
            that will be used for direct UDP FPGA communications.

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
        from lib import fpga_mmi # used for direct FPGA serial discovery
        # import fpga_core
        fpga_mmi.FpgaMmi.interface_ip_addr = interface_ip_addr

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
        return dir(self._hwmap) + self.__dict__.keys()

    def discover(self, timeout=0.1):
        """
        Discover all hardware and firmware resources on the specified
        interface(s) and add them to the database.
        """
        self.discover_iceboards(timeout = timeout)
        self.commit() # commit any changes made during discovery
        #

    def get_fpga_bitstream(self, *args, **kwargs):
        """ Get a bitstream from the database or create one if it does not exist. Returns the database object.
        This is a proxy for FpgaBitstream.get_bitstream()
        """
        return FpgaBitstream.get_bitstream(self,*args, **kwargs)

    def get_iceboards(self, serials=[], subarray=[], *args, **kwargs):
        """
        Returns a list of all ICEBoards covered by the specified scope
        """
        new_args = list()
        if serials:
            new_args.append(IceBoard.serial_number.in_(serials))
        if subarray:
            new_args.append(IceBoard.subarray.in_(subarray))
        kwargs['locked']=0 # force selection of non-locked boards
        if 'present' not in kwargs:
            kwargs['present'] = 1
        return self.query(IceBoard).filter(*tuple(new_args + list(args))).filter_by(**kwargs)

    def discover_iceboards(self, timeout=0.1):
        """
        Update the Iceboard table with the list of available
        Iceboards actually found on the network. 'timout' indicates the time we
        wait for an answer before we decide that there is no board.

        For now, this function just checks if all IceBoards currently in the database are present by
        verifying if their ARM processors offer a tuber interface.

        Once we have a broadcast discovery protocol in the ARM we will be able to add complete new fields.
        In that case we will broadcast a identification
        request, and every board will reply back a packet, which will reveal their
        IP address and any other information in the packet. Once we have that, we can contact tuber
        to obtain all the information needed to create an IceBoard object. This includes:
            arm serial number: from arm (needed?)
            fpga serial number: from JTAG,
            board serial number: from board's EEPROM

        """
        from tuber import TuberObject
        logger = logging.getLogger(__name__)
        logger.debug('Discovering IceBoards')

        iceboards = self.query(IceBoard) # get all the iceboards from the database

        # Check if each iceboard actually responds to tuber requests
        for ib in iceboards:
            if ib.tuber_uri:
                ib.present = TuberObject.ping(ib.tuber_uri)
                logger.info('Discovery: The IceBoard S/N %03i ping result at URI= %s is %s' % (ib.serial_number, ib.tuber_uri, bool(ib.present)))

    def discover_fpga_serial_numbers(self, timeout=0.3, only_new = True, print_on_screen=True):
        """
        Scans the network for FPGAs whose serial numbers. If only_new=True, only those that are not already in the database are returned.
        This works only for FPGAs offering a direct Ethernet interface. This method will become obsolete as the FPGA serials can be discovered through the ARM processor.
        The FPGAs to be discovered must be configured for them to be discovered.

         ^
        /!\ WARNING: This can disrupt operations of all FPGAs on the network as we are requesting all FPGAs to direct their Ethernet packets on the broadcast port of this machine.
        """

        from lib import fpga_mmi # used for direct FPGA serial discovery

        logger = logging.getLogger(__name__)
        logger.debug('Discovering new FPGAs')

        iceboards = self.query(IceBoard) # get all the iceboards from the database
        database_serials = dict(iceboards.values(IceBoard.fpga_serial_number, IceBoard._pk)) # get the serial numbers of all known FPGAs

        new_serials = []
        serials = fpga_mmi.discover_fpgas(interface_ip_addr = self.interface_ip_addr, timeout=timeout)
        for ser in serials:
            if ser not in database_serials or not only_new:
                message = 'A FPGA with serial number %i (0x%08X) was detected on the network.' % (ser, ser)
                if ser not in database_serials:
                    message += ' It is not in the database.'
                logger.info(message)
                if print_on_screen: print message
                new_serials.append(ser)
        return new_serials

    def load_iceboards(self, filename):
        """
        Adds the Iceboard entries listed in the specified CSV file into the database.
        """
        import csv
        session = self
        logger = logging.getLogger(__name__)

        iceboards = session.query(IceBoard) # get all the iceboards from the database
        keymap = dict(iceboards.values(IceBoard.serial_number, IceBoard._pk)) # get a dictionnary that maps the serial number to primary keys

        with open(filename, 'rb') as file:
            reader = csv.reader((line.split('#')[0].rstrip() for line in file if line.split('#')[0].strip())) # uses a generator to strip the comments
            for (serial_number, tuber_uri, arm_serial_number, fpga_ip_addr, fpga_serial_number, locked, subarray) in reader:
                serial_number = int(serial_number, 0)
                tuber_uri = tuber_uri.strip("' ")
                arm_serial_number = arm_serial_number.strip("' ")
                fpga_ip_addr = fpga_ip_addr.strip("' ")
                fpga_serial_number = int(fpga_serial_number, 0)
                locked = int(locked, 0)
                subarray = int(subarray, 0)

                if serial_number in keymap:
                    logger.info('IceBoard S/N %03i already exists in the database. Updating columns from file.' % serial_number)
                    ib = iceboards.get(keymap[serial_number])
                    ib.tuber_uri = tuber_uri
                    ib.core_handler_name = 'IceBoard'
                    ib.app_handler_name = 'chfpga'

                    ib.arm_serial_number = arm_serial_number
                    ib.fpga_ip_addr = fpga_ip_addr
                    ib.fpga_serial_number = fpga_serial_number
                    ib.locked = locked
                    ib.subarray = subarray
                else:
                    logger.info('IceBoard S/N %03i does not exist in the database. Creating from file.' % serial_number)
                    ib = IceBoard(
                        serial_number=serial_number,
                        # arm = TuberHWMResource(tuber_uri=tuber_uri, tuber_objname = 'IceBoard'),
                        tuber_uri = tuber_uri ,
                        core_handler_name = 'IceBoard',
                        app_handler_name = 'chfpga',
                        arm_serial_number=arm_serial_number,
                        fpga_ip_addr=fpga_ip_addr,
                        fpga_serial_number=fpga_serial_number,
                        locked=locked ,
                        subarray = subarray
                        )
                    session.add(ib)
        session.flush()
        session.commit()

    def status(self):
        print 'The array contains the following resources'
        print self.get_iceboards()

    # def detect_mezz(self, force_type_string=None):

    #     # get a list of all polymorphic strings of classes derived from FMCMezzanine
    #     available_mezz_types = {m.polymorphic_identity:m.class_ for m in inspect(FMCMezzanine).polymorphic_map.values()}

    #     mezz_list = enumerate(['FMCA','FMCB'])

    #     if self.mezz1:
    #         del self.mezz1
    #     if self.mezz2:
    #         del self.mezz2

    #     for (fmc_number, fmc_name) in mezz_list:
    #         if force_type_string:
    #             type_string = force_type_string
    #         else:
    #             type_string = FMCMezzanine.get_type_string(self.i2c, fmc_name)

    #         if type_string in available_mezz_types:
    #             self.logger.info("FMC Mezzanine of type '%s' was detected in FMC slot #%i (%s)" % (type_string, fmc_number, fmc_name))
    #             mezz_class = available_mezz_types[type_string]
    #             setattr(self, 'mezz%i' % (fmc_number+1), mezz_class(motherboard=self, fmc_number=fmc_number, fmc_name=fmc_name))
    #         else:
    #             self.logger.info("No recognized FMC Mezzanine was found in FMC slot #%i (%s)" % (fmc_number, fmc_name))

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
