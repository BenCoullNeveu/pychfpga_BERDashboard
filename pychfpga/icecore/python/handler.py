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
# from fmc_mezzanine import FMCMezzanine

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
from iceboard_hardware import IceBoardHardware
from tuber import TuberObject, TuberRemoteError
import fpga_core
import iceboard
import icebox # don't use from .. import ... because of circular import problems

# import arm # object giving access to the ARM firmware
# import hardware handlers

# iceboard_list = {}


class IceBoardException(Exception):
    pass


class chFPGAHandler(iceboard.IceBoardHandler, fpga_core.FpgaCoreFirmware):
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
    class AutoOpenHardware(object):
        """ This class is a placeholder for the unopened hardwre interface object. Whenever
        someone tried to access a hardware attribute or method, the hardware object is created.
        """
        def __init__(self, iceboard):
            self.iceboard = iceboard
        def __getattr__(self, name):
            if not self.iceboard.is_core_open(): # make sure we have all the core funtionnalities (i.e. I2C) before creating hardware objects
                self.iceboard.open_core()
            self.iceboard.hw = IceBoardHardware(iceboard=self.iceboard)
            return getattr(self.iceboard.hw, name)


    def __init__(self, hwm_object= None, core_handler=None, **kwargs):
        """
        Creates an Iceboard that is accessed through the networking parameters specified in the database.
        The created object does not have any fpga or hardware handlers yet. Those will be created when the Iceboard is opened.
        """

        super(chFPGAHandler, self).__init__(**kwargs)
        self._mezzanine_ipmi_cache = {1:None, 2: None}
        self._is_open = None
        self.hw = self.AutoOpenHardware(self)


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

        self.logger.info('Instantiating core FPGA firmware handlers for IceBoard #%i. FPGA address is %s:%i' % (self.serial_number, self.fpga_ip_addr, self.fpga_port_number))

        # Open communication with the FPGA memory-mapped interface to access the FPGA resources
        # self.open_core(ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, fpga_serial_number = self.fpga_serial_number) # open the core functionnalities only for now
        self.open_core() # open the core functionnalities only for now



        # Instantiate python-based hardware managers. These will be gradually be replaced by ARM-based functions.
        # This requires a standardized I2C interface
        self.logger.info('Instantiating IceBoard S/N%i hardware handlers' % (self.serial_number))
        # if self.hw is None:
        #     self.hw = IceBoardHardware(iceboard=self)
        self.hw.init()

        self.hw.set_led('GP_LED2',1) # Hardware link is on
        self.hw.set_led('GP_LED1',0) # Full FPGA firmware is not yet on

        # ----------------------------------
        # Read basic backplane information (backplane S/N, slot number) so we
        # know where this board is in the array
        self.slot_number = self.get_slot_number() # this method is provided by hw or arm
        (self.backplane_serial, __) = icebox.IceBox.get_backplane_info(iceboard = self)

        # Detect the mezzanines
        # self.detect_mezz(force_type_string=forced_mezz_type)

        self._is_open = True

    def close(self):
        # self.unregister_all()
        if self.fpga:
            self.logger.info('Closing application-specific FPGA firmware handlers for board #%i' % (self.serial_number))
            # self.unregister(self.fpga)
            self.fpga.close()

        if self.hw:
            self.logger.info('Closing IceBoard hardware handlers for board #%i' % (self.serial_number))
            self.hw.close()
            self.hw = self.AutoOpenHardware(self)

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

    def get_slot_number(self):
        """ Reads the slot number from the IO Expander. This is not necessarily the slot number stored in the hardware map.
        Slots numbers range from 1 to 16. A slot number of 0 or None indicates that the board is not connected to a backplane.
        NOTE: It would be nice if the ARM could provide this function.
        """
        return self.hw.get_slot_number()

    def get_number_of_mezzanine_slots(self):
        """ Returns the number of mezzanine slots supported by this board (not the number of boards actually populated).
        NOTE: It would be nice if the ARM could provide this function.
        """
        return self.hw.NUMBER_OF_FMC_SLOTS

    def _mezzanine_eeprom_read(self, mezzanine, addr, length,**kwargs):
        """ Reads the EEPROM on the specified mezzanine.
        NOTE: It would be nice if the ARM could provide this function.
        NOTE: Why not maintain the action_scope naming: _read_mezzanine_eeprom() to be consistent with the rest of the API
        """
        return self.hw.read_mezzanine_eeprom(mezzanine, addr, length, **kwargs)

    def _get_mezzanine_ipmi(self, mezzanine):
        """ Returns the IMPI data for the mezzanine located on slot 'mezzanine' (1 or 2). Returns None if no mezzanine is present.

        This method overrides the ARM method of the same name so we can correctly read MGADC08 mezzanines which have a non-standard EEPROM data structure.
        """
        if not self.is_mezzanine_present(mezzanine): # Check mezzanine presence using the FMC PRSNT line.
            return None

        try:
            return self.core_handler._get_mezzanine_ipmi(mezzanine) # Try to get the ipmi data from tuber
        except TuberRemoteError:
            return self._get_mezzanine_mcgill_ipmi(mezzanine)


    def _get_mezzanine_mcgill_ipmi(self, mezzanine, retry=10):
        """ Loads the info data block from the mezzanine EEPROM using the old
        proprietary McGill format (not the FMC standard), and return the data
        converted into the standard FRU object..

        The ad-hoc McGill format is deprecated. It consists of a ID byte (0x0d
        for MGADC08) followed by a ASCII-pickeled dictionary of properties. The
        end of the dictionary is detected by the closing curly brace '}'.
        """
        import struct
        import zlib
        import ast # used for safe McGill-format mezzanine EEPROM parsing

        if self._mezzanine_ipmi_cache[mezzanine]:
            return self._mezzanine_ipmi_cache[mezzanine]

        self._mezzanine_ipmi_cache[mezzanine] = None

        id_byte = ord(self._mezzanine_eeprom_read(mezzanine, addr=0 , length=1, noerror=True)[0])

        if id_byte != 0x0d:
            self.logger.error('The EEPROM on mezzanine %i dies not have a valid ID' % mezzanine)
            return None

        # Read the eeprom block by block until we detect the end of the dictionary
        block_size = 32
        string = ''
        for i in range(512 / block_size): # read 32 blocks of 16 bytes
            data_block = self._mezzanine_eeprom_read(mezzanine, addr= i * block_size, length=block_size, retry=retry)
            string += data_block
            if ('}' in data_block) or (chr(255) in data_block):
                break

        last_char = string.find('}')
        if last_char<0:
            self.logger.error('No dictionary found on EEPROM. Did the board pass the quality control test?')
            return None

        string = string[1:last_char+1] # keep only the dict definition string: remove first char (board ID) and stop at last '}'.

        # Read checksum
        crc_string = self._mezzanine_eeprom_read(mezzanine, last_char+1, length=4, retry=retry)
        crc = struct.unpack('i', crc_string)[0]
        computed_crc = zlib.crc32(string)
        if computed_crc != crc:
            raise self.IceBoardException('FMC EEPROM CRC is invalid. Read crc = %08X, computed crc = %08X' % (crc, computed_crc))
        dict_out = ast.literal_eval(string) # safer than using eval

        from hw.ipmi_fru import FRU, Board, Product, MultiDict
        from datetime import datetime

        # Extract standard FRU information from McGill data structure
        part_number = dict_out.pop('Model', 'Unknown')
        serial_number = dict_out.pop('Serial #', 'Unknown')
        product_version = dict_out.pop('Rev #', 'Unknown')
        mfg_date_str = dict_out.get('Date of last test', None)
        if mfg_date_str:
            mfg_date = datetime.strptime(mfg_date_str, '%d/%m/%Y')
        else:
            mfg_date = None


        fru = FRU(
            board=Board(
                mfg_date=mfg_date,
                manufacturer="Winterland",
                product_name="McGill Mezzanine",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=Product(
                manufacturer="Winterland",
                product_name="McGill Mezzanine",
                part_number=part_number,
                product_version=product_version,
                serial_number=serial_number,
                asset_tag="",
                fru_file="",
            ),
            multi=MultiDict(dict_out)
        )


        self._mezzanine_ipmi_cache[mezzanine] = fru

        return fru

    def _get_mezzanine_type(self, mezzanine):
        """ Returns the type of mezzanine located on slot 'mezzanine' (1 or 2). Returns None if no mezzanine is present.

        This method overrides the ARM method of the same name so we can correctly identify MGADC08 mezzanines which have a non-standard EEPROM data structure.
        """
        ipmi = self._get_mezzanine_ipmi(mezzanine)
        if ipmi and hasattr(ipmi,'product') and hasattr(ipmi.product, 'part_number'):
            return  ipmi.product.part_number
        else:
            return None




# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
