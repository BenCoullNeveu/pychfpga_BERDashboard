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

"""

import logging
# import threading


import sqlalchemy
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, inspect
from sqlalchemy.orm import relationship, backref, reconstructor, object_session
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy import event

# from lib.attribute_publisher import AttributeUser
import hardware_map
#from hardware_map import HWMResource
# from tuber import TuberHWMResource
# from fmc_mezzanine import FMCMezzanine
import fmc_mezzanine # used import x to avoid circular import problem


from fpga_bitstream import FpgaBitstream
from fpga_core import FpgaCoreFirmware
# from iceboard_hardware import IceBoardHardware
import icebox # don't use from .. import ... because of circular import problems
# from handler import HWMHandlerManager
from tuber import TuberObject

# import arm # object giving access to the ARM firmware
# import hardware handlers

# iceboard_list = {}

class IceBoardException(Exception):
    pass

#
class IceBoard(hardware_map.HWMResource, hardware_map.HWMHandlerManager):
# class IceBoard(hardware_map.HWMResource):
    """
    Provides access to the basic functions of an IceBoard.

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

    Project-specific classes are meant to be derived from this class.
    """
    __tablename__ = 'iceboards'
    __table_args__ = (
        UniqueConstraint('serial_number'),
    )
    __mapper_args__ = {
        # 'polymorphic_identity': 'core.iceboard.IceBoard',
        'polymorphic_identity': 'IceBoard',
        'polymorphic_on': '_cls'
    }


    #--------------------------
    # Define database columns associated with this object (in
    #    addition to those inherited by tuber)
    #--------------------------

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    # backplane_serial_number = Column(Integer) # should be replaced by a backplane reference object
    # _icebox_pk = Column(Integer, ForeignKey('icebox._pk'), index=True)

    # serial = Column(String, doc="The serial number written on the board (verbatim!)") # used by Graeme
    serial_number = Column(Integer, doc="The serial number written on the board") # used by JF

    # slot = Column(Integer, doc="The IceCrate slot occupied by this board") # used by Graeme
    slot_number = Column(Integer, doc="The IceBox slot occupied by this board (1-16)") # used by JF

    revision = Column(Integer)

    locked = Column(Integer)
    subarray = Column(Integer)
    present = Column(Integer, default = 0) # indicates if the board is currently present in the array

    arm_serial_number = Column(String)

    # FPGA firmware-related definition
    fpga_ip_addr = Column(String)
    fpga_serial_number = Column(Integer)
    fpga_bitstream_pk = Column(Integer, ForeignKey('fpga_bitstream.pk'), index=True)
    fpga_bitstream = relationship("FpgaBitstream", foreign_keys=[fpga_bitstream_pk], uselist=False, lazy='joined')
    fpga_is_configured = Column(Boolean)


    tuber_uri = Column(String) # The URI used to access remote handlers

    # The core handler describes where to find the methods and attributes needed to operate the
    # core functionnalities of the Iceboard (typically offered by the on-board ARM
    # processor through a JSON/HTTP interface (tuber)
    core_handler_name = Column(String)
    app_handler_name = Column(String)



    mezzanines = relationship(
        "FMCMezzanine",
        lazy="dynamic",
        query_class=hardware_map.HWMQuery,
        doc='''A SQLAlchemy subquery corresponding to this IceBoard's
            mezzanines. If you want to index this array using logical
            keys (1 or 2), you should use 'mezzanine' instead.''')

    mezzanine = relationship(
        "FMCMezzanine",
        backref=backref("iceboard"),
        collection_class=attribute_mapped_collection('mezzanine'),
        doc='''The IceBoard's mezzanines, indexed as you would expect
            (1 for mezzanine A, 2 for mezzanine B).''')

    def __init__(self, *args, **kwargs):
        """ Create a new Iceboard object from scratch and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('IceBoard: Creating instance for IceBoard S/N %r' % (self.serial_number))

        super(type(self), self).__init__(*args, **kwargs)
        # self.set_handler(self.tuber_uri, self.core_handler_name, self.app_handler_name, self._pk)

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self, **kwargs):
        """ Create an Iceboard object from database and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('IceBoard: Recreating instance from database for for IceBoard S/N %r' % (self.serial_number))
        # self.set_handler(self.tuber_uri, self.core_handler_name, self.app_handler_name, self._pk)

    def init_handler(self):
        self.set_handler(self.tuber_uri, self.core_handler_name, self.app_handler_name, self._pk)

    def __repr__(self):
        """ Provide a nice human-friendly representation of this Iceboard object"""
        return '%s S/N %r @%08X' % (self.__class__.__name__, self.serial_number, id(self)) # Used by JF
        # return "%s(%r)" % (self.__class__.__name__, self.hostname) # Used by Graeme



    def set_fpga_firmware(self, bitstream_object, configure_fpga = True, force=False):

        # print 'calling with', self, bitstream_object
        # Deleting the previous bitstream object before assinging a new one seems to help SQLAlchemy to get less confused
        if self.fpga_bitstream:
            del self.fpga_bitstream

        # Assign the new bitstream object. Since this bistream object comes
        # from another session, we cannot use it directly in this thread-
        # specific session. We therefore need to find its corresponding entry
        # in the database from this session.
        session = object_session(self)
        self.fpga_bitstream = session.merge(bitstream_object)
        self.logger.debug('IceBoard S/N %03i.set_fpga_firmware: Assigning firmware %r from session %r' % (self.serial_number, self.fpga_bitstream, session))

        self.close()

        self.logger.info("The FPGA firmware object for iceBoard S/N %i is %r" % (self.serial_number, self.fpga_bitstream))


        # Configure the fpga if we asked for it.
        if configure_fpga:
            self.configure_fpga(force=force)

        # session.commit()

    def configure_fpga(self, force=False):
        """
        Configure the FPGAs on the ICEboard(s) with the specified bitstream.

        The buffer is an ordinary string object or similar, and
        contains an already loaded .BIT or .BIN file. We hash it
        here, but the FPGA itself is responsible for accepting
        or rejecting it. (It's got internal checksums and will
        notice if you pass it garbage.)

        We need the interface IP address in self.interface_ip_addr
        to determine on which interface to listen for UDP replies. We
        won't need this parameter once we access the FPGA through the
        ARM using TCP.

        This method avoids using broadcast reads which might get
        confused if multiple configurations are running at the same
        time.

        TODO: Make more generic to support the simplified case where the ARM processor can talk to the FPGA directly.
        """
        import base64

        if not self.fpga_bitstream:
            raise IceBoardException('Please set the firmware associated with the IceBoard using set_fpga_firmware(bistream_object, firmware_class')

        if self.locked or (self.locked is None):
                raise IceBoardException('Iceboard with serial %016X is locked and its FPGA cannot be configured' % self.serial_number)

        already_configured = self.is_fpga_programmed()

        # if not force:
        #     # First, try to get the FPGA configuration from the FPGA IP address  so we can decide if the FPGA needs reprogramming
        #     self.logger.info('Checking the FPGA on board S/N %03i configuration' % self.serial_number)
        #     (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)
        #     already_configured = (serial and serial == self.fpga_serial_number)

            # # if the FPGA did not respond, maybe it is programmed but its IP address is not set.
            # #  So if we know the FPGA serial number, set its IP address and try again
            # if not serial and self.fpga_serial_number:
            #     #  blindly attempts to configure the FPGA networking is case its firmware is already loaded. This will allow us to check if the firmware is already loaded.
            #     self.logger.info('The FPGA on board S/N %03i did not respond. Attempting to configure its networking parameters' % self.serial_number)
            #     FpgaCoreFirmware.set_networking_parameters(serial_number=self.fpga_serial_number, interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, broadcast_group = 0)
            #     self.logger.info('Rechecking the FPGA on board S/N %03i configuration' % self.serial_number)
            #     (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)
            #     self.logger.info('The FPGA on board S/N %03i replied with serial=%r, timestamp=%r' % (self.serial_number, serial, timestamp))

        # Program the FPGA if it did not return the proper config info
        if not already_configured or force: # if the FPGA has not replied, we program it
            self.fpga_is_configured = False
            if not hasattr(self, '_set_fpga_bitstream_base64'):
                raise IceBoardException("The Iceboard does not have the 'load_fpga_bitstream' method needed to configure the FPGA")
            self.logger.info('Configuring FPGA on board S/N %i' % (self.serial_number))
            # md5_string = self.fpga_bitstream.md5_string
            b64_string = base64.b64encode(self.fpga_bitstream.get_bitstream_data())
            self._set_fpga_bitstream_base64(b64_string) # SD Card v2.3
            # self.load_fpga_bitstream(b64_string, md5_string) # SD Card v2.2
            # Configure the FPGA networking foe the freshly programmed firmware
            self.logger.info('Done configuring FPGA on board S/N %i' % (self.serial_number))

            # if self.fpga_serial_number:
            #     pass
            #     # self.logger.info('Configuring FPGA networking parameters after reprogramming')
            #     # FpgaCoreFirmware.set_networking_parameters(serial_number=self.fpga_serial_number, interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, broadcast_group = 0, check=False)
            #     # # Check if the firmware is now responding with proper configuration info
            #     # (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)

            #     # # if the FPGA still does not reply to its assigned address after programming, raise an error
            #     # if not serial:
            #     #     raise IceBoardException('Failed to program the FPGA on board S/N %03i. The board did not reply after its IP address was configured.' % (self.serial_number))
            #     # elif serial != self.fpga_serial_number:
            #     #     raise IceBoardException('Failed to program the FPGA on board S/N %03i. Expected serial %014X, got %014X' % (self.serial_number, self.fpga_serial_number, serial))
            # else:
            #     self.logger.warning('IP address on FPGA on board S/N %i is not set because the FPGA serial number is not known' % (self.serial_number))
            self.fpga_is_configured = True
        else:
            self.logger.info('FPGA on IceBoard S/N %03i is already configured. Skipping configuration' % (self.serial_number))
            self.fpga_is_configured = True

    def _eeprom_write_ipmi(self, part_number, serial_number, product_version):
        '''Write IPMI-formatted EEPROM for IceBoards.

        These fields are read back and parsed by software, so you have
        to get them right or things will misbehave. This method currently
        expects the following formatting:

        >>> m._eeprom_write_ipmi(
        ...     part_number="MGK7MB",
        ...     serial_number="004",
        ...     product_version="2")

        DON'T fill incorrect values unless they're visibly incorrect,
        since this data tends to be useful when debugging physical
        problems (e.g. tracing board history). Incorrect data that
        pretends to be valid can make this kind of debugging very painful.
        '''

        from hw.ipmi_fru import FRU, Board, Product
        from datetime import datetime

        fru = FRU(
            board=Board(
                mfg_date=datetime.now(),
                manufacturer="Winterland",
                product_name="IceBoard",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=Product(
                manufacturer="Winterland",
                product_name="IceBoard",
                part_number=part_number,
                product_version=product_version,
                serial_number=serial_number,
                asset_tag="",
                fru_file="",
            ),
            # multi=Multi(...), when it's supported by this code
        )
        import base64
        b64_string = base64.b64encode(fru.encode())
        return self._motherboard_eeprom_write_base64(b64_string)

    def detect_mezzanines(self):
        '''Detect and instantiate mezzanines attached to a dfmux.

        This method uses IPMI data on the mezzanine's EEPROMs to guide
        itself.

        You do NOT need to use this method if the mezzanines present in the system are
        already explicitely specified in the YAML hardware maps.
        '''
        for m in range(1, self.get_number_of_mezzanine_slots() + 1):

            # Don't re-discover mezzanines.
            if m in self.mezzanine:
                continue

            # MezzClass = MissingMezzanine # Used by Graeme
            MezzClass = None # Used by JF
            part_number = None
            serial = None

            # If a mezzanine is present, ask it (from EEPROM) what kind
            # of mezzanine it is. Try to instantiate a mezz-specific
            # class.
            if self.is_mezzanine_present(m):
                ipmi = self._get_mezzanine_ipmi(m)
                part_number = ipmi.product.part_number
                serial = ipmi.product.serial_number
                self.logger.info('IceBoard SN%r detect_mezzanines(): Detected Mezzanine Model: %s Serial %s in Mezzanine %i' % (self.serial_number, part_number, serial, m))
                for sc in sqlalchemy.orm.class_mapper(fmc_mezzanine.FMCMezzanine).self_and_descendants:
                    if sc.polymorphic_identity == part_number:
                        MezzClass = sc.class_
            if MezzClass:
                self.mezzanine[m] = MezzClass(mezzanine=m, serial=serial)
            else:
                self.logger.warning("IceBoard SN%r detect_mezzanines(): There is no known FMC Mezzanine object with polymorphic map name '%r' for Mezzanine %r" % (self.serial_number, part_number, m))
                self.mezzanine[m] = None
        self.update_handler() # added by JF to let the handlers update for the new mezz

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





    # # Issue log messages for FPGA serial that were detected but are not already in the database
    # # This can help manually adding boards in the database
    # database_serials = dict(iceboards.values(IceBoard.fpga_serial_number, IceBoard._pk)) # get the serial numbers of all known FPGAs
    # serials = FpgaCoreFirmware.discover_fpgas()
    # for ser in serials:
    #     if ser not in database_serials:
    #         logger.info('A FPGA with serial number %08X was detected on the network but is not in the database. Is this a new board?' % ser)
    # #         ib = IceBoard(
    # #             fpga_serial_number = int(ser))
    # #         session.add(ib)
    # # session.commit()


    # Now add any iceboard that we discover on the network and that is not already in the database

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
