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
import threading

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, inspect
from sqlalchemy.orm import relationship, backref, reconstructor, object_session
from sqlalchemy import event

from lib.attribute_publisher import AttributeUser
from hardware_map import HWMResource
# from tuber import TuberHWMResource
from fmc_mezzanine import FMCMezzanine


from fpga_bitstream import FpgaBitstream
from fpga_core import FpgaCoreFirmware
from iceboard_hardware import IceBoardHardware
import icebox # don't use from .. import ... because of circular import problems
from tuber import LocalPythonHandler
from tuber import Tuber

# import arm # object giving access to the ARM firmware
# import hardware handlers

# iceboard_list = {}

class IceBoardException(Exception):
    pass

# class State(object):
#     def __init__(ORM_class):
#         self.ORM_class = ORM_class


class IceBoard(HWMResource, LocalPythonHandler):
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
            'polymorphic_identity': 'iceboard',
            'polymorphic_on': 'cls'
    }


    #--------------------------
    # Define database columns associated with this object (in
    #    addition to those inherited by tuber)
    #--------------------------

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    serial_number = Column(Integer)
    revision = Column(Integer)
    locked = Column(Integer)
    subarray = Column(Integer)
    present = Column(Integer, default = 0) # indicates if the board is currently present in the array
    slot_number = Column(Integer)
    backplane_serial_number = Column(Integer) # should be replaced by a backplane reference object

    # ARM firmware-related definition
    # tuber_uri = Column(String)
    # tuber_objname = Column(String, nullable=False)
    # tuber_objname = Column(String, default='iceboard')
    arm_serial_number = Column(String)

    # FPGA firmware-related definition
    fpga_ip_addr = Column(String)
    fpga_serial_number = Column(Integer)
    fpga_bitstream_pk = Column(Integer, ForeignKey('fpga_bitstream.pk'), index=True)
    fpga_bitstream = relationship("FpgaBitstream", foreign_keys=[fpga_bitstream_pk], uselist=False, lazy='joined')
    fpga_is_configured = Column(Boolean)
    # fpga_firmware_crc = Column(Integer)
    # fpga_firmware_class = Column(String)
    # interface_ip_addr = Column(String)

    # fpga_pk = Column(Integer, ForeignKey('fpgafirmware.pk'))
    # fpga = relationship("FpgaFirmware", uselist=False, cascade="all, delete, delete-orphan", single_parent=True) # one-to-one relationship with the firmware object. Make sure there is only one firmware object.
    # fpga = relationship("FpgaCoreFirmware", uselist=False, backref='iceboards', foreign_keys=[FpgaCoreFirmware.iceboard_pk], cascade="all, delete, delete-orphan", single_parent=True) # one-to-one relationship with the firmware object. Make sure there is only one firmware object.



    # The core handler describes where to find the methods and attributes needed to operate the
    # core functionnalities of the Iceboard (typically offered by the on-board ARM
    # processor through a JSON/HTTP interface (tuber)
    core_handler = None
    core_handler_uri = Column(String)
    core_handler_class = Column(String)
    # core_handler = relationship("TuberHWMResource", uselist=False, cascade="all, delete, delete-orphan", single_parent=True, lazy='joined') # one-to-one relationship with the firmware object. Make sure there is only one firmware object.
    # core_handler_pk = Column(Integer, ForeignKey('armfirmware.pk'))


    # The application handler describes where to find the application-specific
    # methods and attributes to operate the Iceboard programmed with a
    # specific ARM and FPGA firmware
    app_handler = None
    app_handler_uri = Column(String)
    app_handler_class = Column(String)
    # app_handler = relationship("AppHandlerHWMResource", uselist=False, cascade="all, delete, delete-orphan", single_parent=True, lazy='joined') # one-to-one relationship with the firmware object. Make sure there is only one firmware object.
    # app_handler_pk = Column(Integer, ForeignKey('app_handler.pk'))


    # Set up explicit mezz1 / mezz2 links.
    mezz1_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz1 = relationship("FMCMezzanine", foreign_keys=[mezz1_pk], uselist=False, lazy='joined')

    mezz2_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz2 = relationship("FMCMezzanine", foreign_keys=[mezz2_pk], uselist=False, lazy='joined')

    # # Although we've already catalogued the mezz linkages, it's sometimes
    # # useful to use an array. (For example, it lets us trivially write
    # # join() calls in HWM queries.)
    mezz = relationship("FMCMezzanine",
        uselist=True,
        primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)", lazy='joined'
    )

    def __init__(self, **kwargs):
        """
        Creates an Iceboard that is accessed through the networking parameters specified in the database.
        The created object does not have any fpga or hardware handlers yet. Those will be created when the Iceboard is opened.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info('Creating instance for IceBoard S/N %r' % (self.serial_number))

        super(type(self), self).__init__(**kwargs)

        self._init()

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self, **kwargs):
        """
        Creates an Iceboard that is accessed through the networking parameters specified in the database.
        The created object does not have any fpga or hardware handlers yet. Those will be created when the Iceboard is opened.
        """

        self.logger = logging.getLogger(__name__)
        self.logger.info('Recreating instance from database for for IceBoard S/N %r' % (self.serial_number))

        self._init()

    def _init(self):
        """
        Creates an Iceboard that is accessed through the networking parameters specified in the database.
        The created object does not have any fpga or hardware handlers yet. Those will be created when the Iceboard is opened.
        """

        # Assign the core handler. It is always a tuber handler because in the minimum we need to have fpga programming methods that can only exist remotely on the ARM processor.
        self.core_handler = Tuber(self.core_handler_uri, self.core_handler_class)

        # Assign the application handler. In this case, this one can be a local Python handler class or a remote tuber handler
        if self.is_local_python_handler(self.app_handler_class):
            self.app_handler = self.get_local_python_handler(self.app_handler_class, self.serial_number, iceboard = self)
        elif self.app_handler_uri and Tuber.ping(self.app_handler_uri):
            self.app_handler = Tuber(self.app_handler_uri, self.app_handler_class)
        else:
            self.app_handler = None
        if not self.app_handler:
            self.logger.error('IceBoard S/N %r does not have a valid application handler' % (self.serial_number))
        else:
            self.logger.info('IceBoard S/N %r application handler is %r' % (self.serial_number, self.app_handler))

    def __repr__(self):
        return 'Iceboard S/N %s @%08X' % ('%03i' % self.serial_number if self.serial_number else self.serial_number, id(self))

    # __getattr__ = attribute_publisher.AttributeUser.get_registered_attribute
    def __dir__(self):
        """ Returns the list of attributes of this class and of those of the core and application handlers."""
        return type(self).__dict__.keys() + self.__dict__.keys() + dir(self.core_handler) + dir(self.app_handler)

    def __getattr__(self, name):
        if hasattr(self.core_handler, name):
            return getattr(self.core_handler, name)
        else:
            return getattr(self.app_handler, name)


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

        self.logger.debug('Assigning firmware object to board S/N%03i' % (self.serial_number))
        # if self.fpga:
        #     del self.fpga

        #  Get the class that corresponds to the polymorphic identity name
        # fpga_firmware_class = self.fpga_bitstream.get_firmware_class()

        self.logger.info("The FPGA firmware object for iceBoard S/N %i is %r" % (self.serial_number, self.fpga_bitstream))

        # self.fpga = firmware_class() # Create a FPGA firmware object. This does not do much more than linking the database object

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


        # bitfile = self.fpga_bitstream.firmware_bitstream_data


        if self.locked or (self.locked is None):
                raise IceBoardException('Iceboard with serial %016X is locked and its FPGA cannot be configured' % self.serial_number)

        already_configured = False

        if not force:
            # First, try to get the FPGA configuration from the FPGA IP address  so we can decide if the FPGA needs reprogramming
            self.logger.info('Checking the FPGA on board S/N %03i configuration' % self.serial_number)
            (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)
            already_configured = (serial and serial == self.fpga_serial_number)

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
            if not hasattr(self, 'load_fpga_bitstream'):
                raise IceBoardException("The Iceboard does not have the 'load_fpga_bitstream' method needed to configure the FPGA")
            self.logger.info('Configuring FPGA on board S/N %i' % (self.serial_number))
            md5_string = self.fpga_bitstream.md5_string
            b64_string = base64.b64encode(self.fpga_bitstream.get_bitstream_data())
            self.load_fpga_bitstream(b64_string, md5_string)
            # Configure the FPGA networking foe the freshly programmed firmware
            self.logger.info('Done configuring FPGA on board S/N %i' % (self.serial_number))

            if self.fpga_serial_number:
                pass
                # self.logger.info('Configuring FPGA networking parameters after reprogramming')
                # FpgaCoreFirmware.set_networking_parameters(serial_number=self.fpga_serial_number, interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, broadcast_group = 0, check=False)
                # # Check if the firmware is now responding with proper configuration info
                # (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)

                # # if the FPGA still does not reply to its assigned address after programming, raise an error
                # if not serial:
                #     raise IceBoardException('Failed to program the FPGA on board S/N %03i. The board did not reply after its IP address was configured.' % (self.serial_number))
                # elif serial != self.fpga_serial_number:
                #     raise IceBoardException('Failed to program the FPGA on board S/N %03i. Expected serial %014X, got %014X' % (self.serial_number, self.fpga_serial_number, serial))
            else:
                self.logger.warning('IP address on FPGA on board S/N %i is not set because the FPGA serial number is not known' % (self.serial_number))
            self.fpga_is_configured = True
        else:
            self.logger.info('FPGA on IceBoard S/N %03i is already configured. Skipping configuration' % (self.serial_number))
            self.fpga_is_configured = True

    def get_info(self):
        """Loads the info data on the motherboard"""
        pass

    def status(self):
        """Displays the status of the motherboard"""


# A few hooks to log when SQLAlchemy manipulates ORM objects . This is for
# debugging, to better understand how often an object is being changed.
# Results are often surprising.

@event.listens_for(IceBoard, 'expire')
def receive_expire(target, attrs):
    "listen for the 'expire' event"
    logger = logging.getLogger(__name__)
    logger.warn('IceBoard ??? has expired the following attribute(s): %r' % (attrs)) # cannot use target.serial_number for some reason

@event.listens_for(IceBoard, 'refresh')
def receive_refresh(target, context, attrs):
    "listen for the 'refresh' event"
    if attrs or (attrs is None):
        logger = logging.getLogger(__name__)
        logger.warn('IceBoard %03i is refreshed (context=%r, attr=%r) ' % (target.serial_number, context, attrs))
        target._init_from_database()

@event.listens_for(IceBoard, 'resurrect')
def receive_resurrect(target):
    "listen for the 'resurrect' event"
    logger = logging.getLogger(__name__)
    logger.error('IceBoard %03i is resurrected!' % (target.serial_number))

def load(session, filename):
    """
    Adds the Iceboard entries listed in the specified CSV file into the database.
    """
    import csv

    logger = logging.getLogger(__name__)

    iceboards = session.query(IceBoard) # get all the iceboards from the database
    keymap = dict(iceboards.values(IceBoard.serial_number, IceBoard.pk)) # get a dictionnary that maps the serial number to primary keys

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
                ib.core_handler_uri = tuber_uri
                ib.core_handler_class = 'iceboard'
                ib.app_handler_uri = None
                ib.app_handler_class = 'chfpga'

                ib.arm_serial_number = arm_serial_number
                ib.fpga_ip_addr = fpga_ip_addr
                ib.fpga_serial_number = fpga_serial_number
                ib.locked = locked
                ib.subarray = subarray
            else:
                logger.info('IceBoard S/N %03i does not exist in the database. Creating from file.' % serial_number)
                ib = IceBoard(
                    serial_number=serial_number,
                    # arm = TuberHWMResource(tuber_uri=tuber_uri, tuber_objname = 'iceboard'),
                    core_handler_uri = tuber_uri ,
                    core_handler_class = 'iceboard',
                    app_handler_uri = None ,
                    app_handler_class = 'chfpga',
                    arm_serial_number=arm_serial_number,
                    fpga_ip_addr=fpga_ip_addr,
                    fpga_serial_number=fpga_serial_number,
                    locked=locked ,
                    subarray = subarray)
                session.add(ib)
    session.flush()


def discover(session, timeout):
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
    logger = logging.getLogger(__name__)
    logger.debug('Discovering boards')

    logger.debug('Querying existing database entries')

    iceboards = session.query(IceBoard) # get all the iceboards from the database

    # Check if each iceboard actually responds to tuber requests
    for ib in iceboards:
        if ib.core_handler_uri:
            ib.present = Tuber.ping(ib.core_handler_uri)
            logger.info('Discovery: The IceBoard S/N %03i ping result at URI= %s is %s' % (ib.serial_number, ib.core_handler_uri, bool(ib.present)))
    session.commit()

    # Issue log messages for FPGA serial that were detected but are not already in the database
    # This can help manually adding boards in the database
    database_serials = dict(iceboards.values(IceBoard.fpga_serial_number, IceBoard.pk)) # get the serial numbers of all known FPGAs
    serials = FpgaCoreFirmware.discover_fpgas()
    for ser in serials:
        if ser not in database_serials:
            logger.info('A FPGA with serial number %08X was detected on the network but is not in the database. Is this a new board?' % ser)
    #         ib = IceBoard(
    #             fpga_serial_number = int(ser))
    #         session.add(ib)
    # session.commit()



    return

    # Now add any iceboard that we discover on the network and that is not already in the database

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
