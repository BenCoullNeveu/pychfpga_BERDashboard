#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: C0301

"""iceboard.py module: Defines the base object for an IceBoard
(McGill Model MGK7MB).

To specialize an IceBoard object for a particular experiment, you're
encouraged to create a subclass. There should be good examples
available.


 History:
    2014-03-04 JFC: Created
    2014-03-18 JM: Added get_temperature and init_temp_sensors
    2014-03-26 JFC: Integrated tuber
    2014-11-24 JFC: Modified IceBoard into IceBoardAppHandler
"""

import logging
# import threading

from sqlalchemy import inspect
# from sqlalchemy.orm import relationship, backref, reconstructor, object_session
# from sqlalchemy import event

# from lib.attribute_publisher import AttributeUser
# from hardware_map import HWMResource
# from tuber import TuberHWMResource
# from tuber import Handler
from fmc_mezzanine import FMCMezzanine

# Force reloading of the hardware map module to allow this module
# reloads to succeed. We need to make sure we use a freshly created
# hardware_map module because HWMResource uses with a new dynamically
# created Base class that statically remembers the current schema.
# Therefore, SQLAlchemy will complain that the table already exist) if
# we reloan this module and try to create an instrumented class that
# already exists in the schema.

# reload(hardware_map)
# reload(tuber)

# import fpga
from fpga_bitstream import FpgaBitstream
from fpga_core import FpgaCoreFirmware
from iceboard_hardware import IceBoardHardware
from iceboard_hardware import I2CInterface

import icebox # don't use from .. import ... because of circular import problems

# import arm # object giving access to the ARM firmware
# import hardware handlers

# iceboard_list = {}

class IceBoardException(Exception):
    pass

# class State(object):
#     def __init__(ORM_class):
#         self.ORM_class = ORM_class


class IceBoardAppHandler(FpgaCoreFirmware):
    """
    Provides access to the basic functions of an IceBoard Rev2/Rev3.

    This object inherits from a generic Hardware Manager resource,
    which allows the iceboard objects to be added to the hardware
    map database.

    The methods and properties have access to the hardware or firmware
    in one of the the following ways:
        - The low-level hardware access is made directly in python
          through the ARM or FPGA I2C links to the board.
        - The low-level hardware access is implemented in the ARM<
          software, and all methods and properties are imported
          through tuber.

    Python-based application-specific FPGA firmware and hardware handler are meant to be derived from this class.
    """

    def __init__(self, orm_object= None, core_handler = None, *args, **kwargs):
        """
        Creates an Iceboard that is accessed through the networking parameters specified in the database.
        The created object does not have any fpga or hardware handlers yet. Those will be created when the Iceboard is opened.
        """

        # super(type(self), self).__init__(**kwargs)

        # Store iceboard ORM information
        # The iceboard object is an ORM object and is guaranteed to be valid only during this function, so we cannot use ut for future accesses.

        iceboard = orm_object

        self.serial_number = iceboard.serial_number
        self.fpga_ip_addr = iceboard.fpga_ip_addr
        if self.serial_number:
            self.fpga_port_number = 41000 + 4*(self.serial_number)
        # self._auto_open = auto_open
        # self.fpga_firmware_class = iceboard.fpga_bitstream.get_firmware_class()
        self.fpga_serial_number = iceboard.fpga_serial_number
        self.i2c = None
        self.mezz1_handler = iceboard.mezz1 # Fragile. Reference will become stale as ORM object move in and out of memory. Must fix
        self.mezz2_handler = iceboard.mezz2
        self.core_handler = core_handler

        self.logger = logging.getLogger(__name__)
        self.logger.debug('Instantiating Iceboard S/N %r at %r:%r from direct instantiation' % (self.serial_number, self.fpga_ip_addr, self.fpga_port_number))
        # self.logger.debug('S/N=%s, uri=%s, fpga ip=%s' % ( self.arm.tuber_uri if self.arm else None, self.fpga_ip_addr))

        if self.serial_number and self.is_open():
            self.logger.error('Attempting to open object S/N %s from database while an instance already exists' % ('%03i' % self.serial_number if self.serial_number else self.serial_number))
        self.hw = None
        self.arm = None # For iceboard_hardware compatibility. Need to fix.

    def open(self, forced_mezz_type=None, *args, **kwargs):
        """
        Establishes the connection with the hardware and firmware on the IceBoard and create all appropriate handling classes.
        """

        # if the FPGA handler instance was not created, check if one exists create it
        if self.serial_number and self.is_open():
            self.logger.error('Attempting to open IceBoard S/N %s while it is already opened. Aborting.' % ('%03i' % self.serial_number if self.serial_number else self.serial_number))
            return
        # else:
        #     if self.fpga is None:
        #         self.fpga = self.fpga_firmware_class()

        self.logger.info('Instantiating core FPGA firmware handlers for board #%i' % (self.serial_number))
        self.open_core(ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, serial_number = self.fpga_serial_number) # open the core functionnalities only for now


        # # Create a standardized I2C interface to the hardware, whether it goes through the ARM or FPGA.
        # if hasattr(self._iceboard, 'i2c_write_read') and hasattr(self._iceboard, 'i2c_set_port'):
        #     self._i2c = I2CInterface(self._iceboard.arm.i2c_write_read, self._iceboard.arm.i2c_set_port, self._I2C_BUS_LIST, self._ARM0_I2C_SWITCH_ADDR)
        # elif hasattr(self._iceboard.fpga, 'i2c_write_read') and hasattr(self._iceboard.fpga, 'i2c_set_port'):
        if not self.i2c: # If i2c interface not already provided my the ARM
            self.i2c = I2CInterface(self.fpga_i2c_write_read, self.fpga_i2c_set_port, IceBoardHardware.FPGA_I2C_BUS_LIST, IceBoardHardware._FPGA_I2C_SWITCH_ADDR)
        # self.i2c = self.hw.get_i2c_interface() # get standardized I2C interface that can be used more easily by the user firmware

        # else:
        #     raise IceBoardHardwareException('Neither the ARM or FPGA provide a i2c_write_read() method needed to talk to the hardware')


        # Instantiate hardware managers. This requires an I2C link to the
        # hardware (i2c_write_read() and i2c_set_port()), which should be
        # provided either by the ARM or by the FPGA.
        self.logger.info('Instantiating IceBoard hardware handlers for board #%i' % (self.serial_number))
        if self.hw is None:
            self.hw = IceBoardHardware(iceboard=self)
        self.hw.init()
        # self.register(self.hw) # Allow access to the hardware methods/attributes from this class
        self.hw.set_led('GP_LED2',1) # Hardware link is on
        self.hw.set_led('GP_LED1',0) # Full FPGA firmware is not yet on

        # ----------------------------------
        # Read basic backplane information (backplane S/N, slot number) so we
        # know where this board is in the array
        self.slot_number = self.hw.get_slot_number() # this method is provided by hw or arm
        (self.backplane_serial, __) = icebox.IceBox.get_backplane_info(iceboard = self)

        # Detect the mezzanines
        # self.detect_mezz(force_type_string=forced_mezz_type)

        # We can now create the full-fledged application-specific FPGA firmware handlers.
        # The firmware has access to the methods offered by this iceboard. The following are typically used:
        #   i2c, mezz

        self._is_open = True

    def close(self):
        # self.unregister_all()
        if self.fpga:
            self.logger.info('Closing application-specific FPGA firmware handlers for board #%i' % (self.serial_number))
            # self.unregister(self.fpga)
            self.fpga.close()

        if self.hw:
            self.logger.info('Closing IceBoard hardware handlers for board #%i' % (self.serial_number))
            # self.unregister(self.hw)
            self.hw.close()
            self.hw = None
        # type(self)._hw_instances.pop(self.serial_number, None)

        if self.fpga:
            self.logger.info('Closing core FPGA firmware handlers for board #%i' % (self.serial_number))
            self.fpga.close_core()
            self.fpga = None
        # type(self)._fpga_instances.pop(self.serial_number, None)

        # if self.arm:
        #     self.logger.info('Closing core arm firmware handlers for board #%i' % (self.serial_number))
            # self.unregister(self.arm)
            # self.arm.close() # Tuber has no close()
            # self.arm = None

        # self._self_reference = None # Now the object can be garbage collected if no one else uses it
        self._is_open = False
        # type(self)._active_instances.pop(self.serial_number, None)

    def is_open(self):
        return self._is_open
        # return self.serial_number in type(self)._active_instances

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


# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
