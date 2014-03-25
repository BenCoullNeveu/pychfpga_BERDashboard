#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
icearray.py module
Provides access to an array of ICEBoards and ICEBoxes (backplanes)

 History:
        2014-03-04 JFC: Created
"""
#import time
import argparse
import logging
#import sys
# import struct
# import socket

import re
import numpy as np
# from Module import Module_base, BitField
# import fpga_mmi
import hardware_map
import iceboard.iceboard as iceboard


class IceException(Exception):
    pass

# class IceResource(object):
#     """
#     Object representing a ressource in the ICEArray. It can be:
#         - ICEBoard (through FPGA or ARM)
#         - ICEBox (backplane)

#     This might end up just being a database record.
#     """
#     ICEBOARD = 'iceboard'
#     ICEBOX = 'icebox'

#     #board info
#     serial_number = 0 # unique number, used as a database key index
#     ressource_type = None
#     index = None # slot number
#     info = None
#     locked = True # if True, we cannot change anything on the board
#     parent = None # To associate IceBoxes with ICeBoards?

#     # ARM info
#     arm_ip_addr = None
#     arm_serial_number = None # Its MAC address for now
#     arm = None # the actual arm object that provides us services

#     #FPGA info
#     interface_ip_addr = None
#     fpga_ip_addr = None # will become obsolete one day when all comms are done through the arm
#     fpga_serial_number = 0
#     fpga = None # the actual fpga object that provides us with services
#     port = None

#     # Iceboard info
#     iceboard = None # the iceboard object that defines interface to the hardware resourcces

#     protocol = None # TCP, UDP ... might not be needed

#     def __str__(self):
#         """
#         Returns a human-readable string representing this ressource entry
#         """
#         return '%s ARM IP: %15s S/N: %11s, FPGA IP: %15s S/N: %16x Group: %2i, IF IP: %15s' % (self.ressource_type, self.arm_ip_addr, self.arm_serial_number,  str(self.fpga_ip_addr), self.fpga_serial_number, self.fpga_subarray, str(self.interface_ip_addr))

#     def __hash__(self):
#         """
#         Returns a unique value representing the resource. Is used to allow the object to be used in a set of unique elements.
#         """
#         if self.serial_number:
#             return self.serial_number
#         else:
#             return 0

#     @classmethod
#     def keys(cls):
#         """
#         Returns a list of valid keys used to represent the ICE resource.
#         """
#         return [key for key in cls.__dict__.keys() if key[0].islower() and key.islower()];

# class IceResourceFilter(object):
#     """
#     Represent a resource database filter rule
#     """
#     match_criteria = {}

#     def __init__(self, *args, **kwargs):
#         """
#         Creates a filter object.
#         """
#         self.match_criteria = {}
#         for arg in args:
#             if isinstance(arg, IceResourceFilter):
#                 self._add_criteria(arg.match_criteria)
#             elif isinstance(arg, dict):
#                 self._add_criteria(arg)
#             else:
#                 self._add_criteria({'serial_number': arg})
#         if kwargs:
#             self._add_criteria(kwargs)

#     def __iadd__(self, other):
#         self._add_criteria(IceResourceFilter(other))
#         return self

#     # def items(self):
#     #     return self.match_criteria.items()

#     def _add_criteria(self, new_criteria):
#         """
#         Adds new elements to the filter.
#         """
#         for (key, value) in new_criteria.items():
#             if not hasattr(IceResource, key):
#                 raise IceException('Unknown ICE Resource property. Valid properties are \n%s' % '\n'.join(IceResource.keys()))
#             # if the item does not exist create it with an empty list
#             if key not in self.match_criteria:
#                 self.match_criteria[key] = []
#             # Add the new value to the item
#             if isinstance(value, list):
#                 self.match_criteria[key] += value
#             else:
#                 self.match_criteria[key].append(value)

#     def match(self, ice_ressource):
#         """
#         Determines if the ressource matches  filter. The rules are:
#             - If the filter value  is a number, it must match the resource value exactly
#             - If the filter is a string but the resource value is a number, the filter must match the hex representation of the resource value
#             - Otherwise we attempt to match them as strings.

#             String filters are matched as follows:
#                  '*' matches any number of characters, and '?' or '.' matches exactly one character.
#                  The pattern must match the entire string from beginning to end.
#                  The match is case insentivie.
#         """
#         # resource_filter = IceResourceFilter(*args, **kwargs) # converts the arguments into a filter

#         match_status = True
#         for (key, test_values) in self.match_criteria.items():
#             # if not isinstance(test_values, (list, tuple)):
#             #     test_values = [test_values]
#             resource_value = getattr(ice_ressource, key)
#             key_match = False
#             for test_value in test_values:
#                 if isinstance(test_value, (int, long)):
#                     key_match |= (test_value == resource_value)
#                 elif isinstance(test_value, str):
#                     if isinstance(resource_value, (int, long)):
#                         resource_value = ('%016x' % resource_value)
#                     # convert '*' and '?' into their equivalent regex matching patterns
#                     test_value = test_value.replace('*', '.*')
#                     test_value = test_value.replace('?', '.')
#                     test_value = '^' + test_value + '$' # make sure we match the whole string from beginning to end
#                     # print 'testing', resource_value, type(resource_value), 'against ', test_value
#                     key_match |= bool(re.match(test_value, resource_value, re.IGNORECASE))
#             match_status &= key_match
#         return match_status

# class AttributeIterator(object):
#     """
#     Calls a function on multiple iceboards
#     Probably should inherit a dict
#     """
#     data = {}

#     def __init__(self, data):
#         self.data = data

#     def __call__(self, *args, **kwargs):
#         r = {}
#         for (board, method) in self.data.items():
#             # print 'Calling method %s for ressource #%i' % (method, board)
#             result = method(*args, **kwargs)
#             if result is not None:
#                 r[board]= result
#         if r:
#             return type(self)(r)
#         else:
#             return None

#     def __getattr__(self, attr):
#         """
#         Intercept attribute access (including method calls) and return an object that will iterate and pass the request to the arm or fpga objects.
#         """
#         # this method is not called if the attribute exists in the class so we don't have to check for that.
#         r= {}
#         for (board, obj) in self.data.items(): # acessing self.db does not cause call to __getattr__ because it already exists
#             if hasattr(obj, attr):
#                 r[board] = getattr(obj, attr)
#                 # access_count += 1
#         # if not access_count:
#         #     raise AttributeError("Attribute '%s' does not exist in the arm or fpga objects" % attr)
#         if r:
#             return AttributeIterator(r) # wrap the dict in case the list is being called
#         else:
#             return None

#     def __getitem__(self, index):
#         return self.data[index]
#     def __str__(self):
#         return str(self.data)
#     def __repr__(self):
#         return repr(self.data)
#     def __len__(self):
#         return len(self.data)
#     def values(self):
#         return self.data.values()

# class IceResourceTable(object):
#     """
#     Class representing an array of ICE Resources with methods to filter specific elements.
#     This is implemented here as a simple list, but it could be implemented using an underlying database system.
#     """
#     # We need to define all attributes as part of the class so the first assignment to those (in __init__) will be done locally by __setattr__ and will not make it search for those in the arm and fpga objects.
#     db = {} # make sure the attribute exists so that __getattr__ and __setattr__ will always see it.
#     logger = None

#     def __init__(self):
#         """
#         Creates an empty ICE ressource database.
#         """
#         self.logger = logging.getLogger(__name__)
#         self.db = {}

#     def __iter__(self):
#         """
#         Allows the object to be iterable and have it iterate over all ressource items.
#         """
#         return iter(self.db)

#     def __str__(self):
#         """
#         Returns a string containing a human-representation of the database.
#         """
#         return '\n'.join(["%3i : %s" % (serial_number, str(res)) for (serial_number, res) in self.db.items()])

#     def __repr__(self):
#         return '%s containing \n%s' % (object.__repr__(self), str(self))

#     def __add__(self, other):
#         """
#         Merge two ressource tables.
#         """
#         if not isinstance(other, IceResourceTable):
#             raise TypeError()
#         new_table = IceResourceTable()
#         new_table.db = self.db + other.self.db
#         return new_table

#     def __iadd__(self, other):
#         if isinstance(other, IceResourceTable):
#             self.db.update(other)
#         elif isinstance(other, IceResource):
#             self.db[other.serial_number] = other
#         else:
#             raise TypeError('The argument must be an IceResource or IceResourceTable object')
#         return self

#     def __len__(self):
#         """
#         Returns the number of entries in the ICE resource database.
#         """
#         return len(self.db)

#     def __getitem__(self, index):
#         """

#         """
#         return self.db[index]

#     def __getattr__(self, attr):
#         """
#         Intercept attribute access (including method calls) and return an object that will iterate and pass the request to the arm or fpga objects.
#         """
#         # this method is not called if the attribute exists in the class so we don't have to check for that.
#         r= {}
#         for (serial_number, res) in self.db.items(): # acessing self.db does not cause call to __getattr__ because it already exists
#             source_objects = [res.iceboard, res.arm, res.fpga]
#             access_count = 0
#             for obj in source_objects:
#                 if hasattr(obj, attr):
#                     r[res.serial_number] = getattr(obj, attr)
#                     access_count += 1
#             if not access_count:
#                 raise AttributeError("Attribute '%s' does not exist in the arm or fpga objects" % attr)
#         if r:
#             return AttributeIterator(r) # wrap the dict in case the list is being called
#         else:
#             return None

#     def __setattr__(self, attr, value):
#         """
#         Intercept attribute setting. Writes to the arm or fpga objects if the attributes exist these, otherwise write it to the local object.

#         Todo: should give a warning if an attribute exists in more than one object
#         """

#         # Set the variable locally if it exists locally.
#         # Don't use hasattr(self, attr) because it will call __getattr__ and if the object exist on the arm of fpga it will find it and will return True
#         # Dont use vars(self) or self.__dict__ because we want to do a local assignment if the variable exist int he class but not yet in the instance
#         if attr in dir(self):
#             # print attr, 'is local', locals()
#             object.__setattr__(self, attr, value) # don't assign directly to avoid calling __setattr__ recursively
#         else:
#             assignment_count = 0
#             for (serial_number, res) in self.db.items():
#                 source_objects = [res.iceboard, res.arm, res.fpga]
#                 for obj in source_objects:
#                     if hasattr(obj, attr):
#                         # print 'setting ', attr
#                         setattr(obj, attr, value)
#                         assignment_count += 1
#             if not assignment_count:
#                 raise AttributeError("Attribute '%s' does not exist locally, in the arm or in the fpga objects, so we cannot set its value" % attr)


#     def pop(self):
#         """
#         Removes one element from the database and returns it.
#         """
#         return self.db.popitem()

#     def select(self,*args, **kwargs):
#         """
#         Selects (i.e. filter) specific elements of the Ressource Table and returns the filtered table.
#         This is a very brain dead way of doing this.
#         """
#         if args or kwargs:
#             new_table = IceResourceTable()
#             resource_filter = IceResourceFilter(*args, **kwargs)
#             for (serial_number, resource) in self.db.items():
#                 if resource_filter.match(resource):
#                     new_table += resource
#             return new_table
#         else:
#             return self

#     def configure_fpga(self, bitfile):
#         """
#         Configure the FPGAs on the ICEboard(s)
#         """
#         # For now we do this the worst possible way: by programming each FPGA one aftet the other.
#         # This should be rewritten to allow concurrent programming of all FPGAs, maybe using zeroMQ.

#         interfaces=set()
#         for res in self.db.values():
#             interfaces.add(res.interface_ip_addr)
#         if len(interfaces) != 1:
#             raise IceException('The code currently supports only one Ethernet interface');
#         else:
#             interfaces = interfaces.pop()

#         self.logger.info('Checking if the FPGAs can be found on the network')
#         fpga_serials = fpga.Fpga.discover_fpgas(interfaces)

#         # print 'discovered fpgas are ', fpga_serials

#         for ice in self.db.values():
#             if ice.fpga_serial_number not in fpga_serials:
#                 self.logger.info('Configuring FPGA on board #%i through ARM at address %s' % (ice.serial_number, ice.arm_ip_addr))
#                 if ice.locked:
#                     IceException('Iceboard with serial %016X is locked and its FPGA cannot be configured' % ice.serial_number)
#                 # arm_ = arm.Arm(ice.arm_ip_addr)
#                 ice.arm.configure_fpga(bitfile)
#             else:
#                 self.logger.info('FPGA on board #%i,  ARM address %s is already configured. Skipping configuration' % (ice.serial_number, ice.arm_ip_addr))

#         self.logger.info('Checking again what FPGAs are on the network')
#         fpga_serials = fpga.Fpga.discover_fpgas(interfaces)

#         self.logger.info('Instantiating FPGAs and IceBoards')

#         for (serial_number, ice) in self.db.items():
#             if ice.fpga_serial_number not in fpga_serials:
#                 self.logger.error('Failed to find FPGA on board #%i' % (serial_number))
#             else:
#                 self.logger.info('Creating FPGA and Iceboard handlers for board #%i' % (serial_number))
#                 if ice.fpga:
#                     ice.fpga.close()
#                 ice.fpga = fpga.Fpga(ice.interface_ip_addr, ice.fpga_ip_addr, ice.fpga_port, serial_number = ice.fpga_serial_number) # here we need the serial number because we use the FPGA Ethernet interface.
#                 if ice.iceboard:
#                     ice.iceboard.close()
#                 ice.iceboard = iceboard.IceBoard(ice.arm, ice.fpga)
#             # arm_.close()
#     def close(self):
#         """
#         Close all ressources.
#         """
#         for (serial_number, ice) in self.db.items():
#             self.logger.info('Closing FPGA and Iceboard handlers for board #%i' % (serial_number))
#             if ice.fpga:
#                 ice.fpga.close()
#                 ice.fpga = None
#             if ice.arm:
#                 ice.arm.close()
#                 ice.arm = None
#             if ice.iceboard:
#                 ice.iceboard.close()
#                 ice.iceboard = None


# # class IceObjects:
# #     """
# #     Represents a list of ICE resources that can be used to access ATM of FPGA methods directly.
# #     """

# #     db = {}

# #     def __init__(self, resource_table):
# #         self.db = resource_table.db

# #     def __str__(self):
# #         """
# #         Returns a string containing a human-representation of the database.
# #         """
# #         # return '\n'.join([str(res) for res in self.db])
# #         return 'IceObject'
# #     def __repr__(self):
# #         return repr(self.db)



class IceArray(object):
    """
    Provides access to arrays of ICEBoards and ICEBoxes.
    """

    def __init__(self, iceboard_class = iceboard.IceBoard, mezz_class = None, interface_ip_addr=None):
        """
        'interface_ip_addr' is the IP address of the Ethernet interface
            that will be used for direct FPGA communications (either discovery
            broadcasts or for opening command/data sockets)

        Todo:

        2014-03-03 JFC: If interface_ip is not specified, the first call to
            discover() could scan all adapters and find on which one there are
            ICEBoards.
        """

        self.logger = logging.getLogger(__name__)
        # self.resource_database = IceResourceTable()
        self.interface_ip_addr = interface_ip_addr

        # Create a hardware mapper
        self.hwmap = hardware_map.HardwareMap(echo=False) # JFC echo=False because we already have a logger that will catch the messages.

        # Remove the logger handlers that is created for the SQLAlchemy Engine. We want to use our own top level handler.
        # If we don't do this, the SQLAlchemy messages get displayed twice
        sa_logger =  logging.getLogger('sqlalchemy.engine.base.Engine')
        # sa_logger.handlers=[]
        while sa_logger.handlers:
            # print 'removing handler', sa_logger.handlers[0]
            sa_logger.removeHandler(sa_logger.handlers[0])

        self.discover([0])

    # def close(self):
    #     """
    #     Closes all communication sockets with the hardware.
    #     """
    #     self.resource_database.close()


    def discover(self, source_subarrays = [0] , timeout=0.1):
        """
        Discover all hardware and firmware resources on the specified
        interface(s) and in the specified subarray(s) and returns a list of
        those.
        """
        # iceboard_resources = self._discover_iceboards(source_subarrays= source_subarrays, interface_ip= interface_ip, timeout = timeout)
        discovered_iceboards = iceboard.IceBoard.discover(timeout = timeout, interface_ip_addr = self.interface_ip_addr)

        # self.d = discovered_iceboards
        for ice in discovered_iceboards:
            self.hwmap.add(ice)
        #self.hwmap.flush()
        # if iceboard_resources:
        #     resources.update(iceboard_resources)
        # self.resource_database += iceboard_resources


    # def _discover_arms(self, timeout):
    #     """
    #     Populate the resource database with the list of available ARM processors offering a tuber interface.
    #     'timout' indicates the time we wait for an answer before we decide that there is no arm processor.

    #     For now, this function finds the ARMs by probing all addresses from a static tables, but once we have a broadcast discovery protocol the table will not be necessary.
    #     """
    #     for (arm_ip_addr, arm_serial_number, fpga_ip_addr, fpga_serial_number, board_serial_number, lock_flag) in ARM_TABLE:
    #         if arm.Arm.ping_tuber(arm_ip_addr):
    #             self.logger.debug('Found an ARM board with tuber at %s!' % (arm_ip_addr))
    #             res = IceResource()
    #             res.serial_number = board_serial_number # unique number, used as a database key index and as default filtering key
    #             res.ressource_type = IceResource.ICEBOARD
    #             res.interface_ip_addr = self.interface_ip_addr
    #             res.arm_ip_addr = arm_ip_addr
    #             res.arm_serial_number = arm_serial_number
    #             res.fpga_ip_addr = fpga_ip_addr # will become obsolete one day when all comms are done through the arm
    #             res.fpga_port = 41000 + 4*(board_serial_number)
    #             res.fpga_serial_number = fpga_serial_number # We will be able to get this automatically once we can probe the FPGA throught the ARM, but we won't need it anymore at that point since it is used only to configure the FPGA ethernet interface.
    #             res.fpga_subarray = 0 # another thing we probably won't need
    #             res.protocol = None
    #             res.index = None # slot number
    #             res.info = None
    #             res.parent = None
    #             res.locked = lock_flag
    #             res.arm = arm.Arm(res.arm_ip_addr) # create the arm object
    #             # res.arm.open()
    #             self.resource_database += res

    #     #         for serial in serial_list:
    #     #             res = IceResource()
    #     #             res.ressource_type = IceResource.ICEBOARD
    #     #             res.serial_number = int(serial)
    #     #             res.fpga_serial_number = int(serial)
    #     #             res.interface_ip_addr = if_addr
    #     #             res.subarray = subarray
    #     #             # Now, find the ARM info by looking at a static table until we have a way to get the information dynamically.
    #     #             matching_arm_entries = [arm_table_item for arm_table_item in ARM_TABLE if IceResourceFilter(serial_number=arm_table_item[0]).match(res)]
    #     #             if not matching_arm_entries:
    #     #                 self.IceException('No ARM information was found for the ressource with serial %16X' % res.serial_number)
    #     #             elif len(matching_arm_entries) > 1:
    #     #                 self.IceException('Multiple ARM information entries was found for the ressource with serial %16X' % res.serial_number)
    #     #             else:
    #     #                 res.arm_ip_addr = matching_arm_entries[0][2]
    #     #                 res.arm_serial_number = matching_arm_entries[0][1]
    #     #             resources += res

    #     # if not resources:
    #     #    self.logger.info('   No ICE ressource was found on subarray %i through interface %s' % (subarray, if_addr))
    #     #    return []
    #     # else:
    #     #    self.logger.info('The following ICE ressource were discovered')
    #     #    for res in resources:
    #     #         # pass
    #     #        self.logger.info('   Type: %s, S/N: %16X' % (res.ressource_type, res.serial_number))
    #     # # resources.update(dict(zip(serial_list, [None] * len(serial_list))))
    #     # return resources

    # # def _discover_iceboxes(self):
    # #     """
    # #     Scans ICEBoards
    # #     """


    # # def get_fpga_serials(if_addr, port_number=41000):
    # #     """
    # #     Finds the serial number of every FPGA in the network connected to the interface(s) with the address 'if_address'.
    # #     'if_address' can be a list of interfaces.
    # #     """
    # #     sock = broadcast_open(if_addr, port_number)
    # #     serial_list = self.broadcast_read(sock, 0x00080+12, type = np.dtype('>u8'))
    # #     sock.close()
    # #     return serial_list

    # def get_resources(self, *args, **kwargs):
    #     """
    #     Returns the available array resources that match the specified filter.
    #     The scope can be a Scope object, or any object that can be used to create a scope object.
    #        'all': return all resources
    #        'XXX...': the last hexadecimal digits of the board serial number. If there is an ambiguity, an error will be flagged.
    #        [ 'XXX', 'XXX'] : list of serial numbers
    #        { parameter: value, param:value ...}: list of search criterias
    #     """
    #     # scope_obj = Scope(scope)

    #     return self.resource_database.select(*args, **kwargs)

    # def set_active_resources(self, active_resources):
    #     """
    #     Set the active resources. ;active_resources' must be a IceResourceTable.
    #     """
    #     self.active_resources = active_resources;

    # def get_active_resources(self):
    #     """
    #     Return the table of active ICE resources.
    #     """
    #     return self.active_resources

    def get_iceboards(self, serials=[]):
        """
        Returns a list of all ICEBoards covered by the specified scope
        """
        if serials:
            return self.hwmap.query(iceboard.IceBoard).filter(iceboard.IceBoard.serial_number.in_(serials))
        else:
            return self.hwmap.query(iceboard.IceBoard)

        # return self.get_resources(ressource_type=IceResource.ICEBOARD).select(*args, **kwargs)

    def status(self):
        print 'The array contains the following resources'
        print self.get_iceboards()

    # def connect(self, resource_table):
    #     """
    #     Establishes a network connection with the resources specified in 'resource_table'.
    #     """

    #     for res in resource_table:
    #         res.connect()

from sqlalchemy import create_engine, MetaData
# from sqlalchemy.ext.declarative import declarative_base
# Base = declarative_base()
from sqlalchemy.orm import object_session
from sqlalchemy.orm.util import has_identity

logging.getLogger('iceboard.arm.FpgaBitFile').setLevel(logging.INFO)
logging.getLogger('requests.packages').setLevel(logging.WARN)
logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.INFO)

import iceboard.arm as arm

if __name__ == '__main__':

    # %load_ext autoreload
    # %autoreload 2

    # close any ice object that might be in this namespace

    if '__opened_sockets__' in globals(): # i.e. if __main__ has an __opened_sockets__ attribute
        while __opened_sockets__: # close all sockets so we won't get a 'socket already opened' error because of a previous run
            __opened_sockets__.pop().close()


    # try:
    #     ice.close()
    # except NameError:
    #     pass

    # dreload(sys.modules['icearray'])
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
    logger.info('icearray')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))
    # Create the new chFPGA object.


    ice = IceArray(args.if_ip)
    # ice.status()

    bitfile = arm.FpgaBitFile('../../../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')#('../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit')
    c = ice.get_iceboards([7, 14, 19]) # get one or more IceBoards
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
