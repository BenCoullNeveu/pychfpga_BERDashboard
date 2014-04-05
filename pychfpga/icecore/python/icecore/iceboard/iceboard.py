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

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref, reconstructor

from .. import attribute_publisher
from .. import hardware_map
from .. import tuber

# Force reloading of the hardware map module to allow this module
# reloads to succeed We need to make sure we use a freshly created
# hardware_map module because HWMResource uses with a new dynamically
# created Base class that statically remembers the current schema.
# Therefore, SQLAlchemy will complain that the table already exist) if
# we reloan this module and try to create an instrumented class that
# already exists in the schema.

reload(hardware_map)
reload(tuber)

# from .. import fmc_mezzanine

from fpga import FpgaFirmware # Object giving access to the FPGA firmware
from iceboard_hardware import IceBoardHardware

# import arm # object giving access to the ARM firmware
# import hardware handlers

class IceBoardException(Exception):
    pass

class IceBoard(hardware_map.HWMResource, attribute_publisher.AttributeUser):
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

    # Set up explicit mezz1 / mezz2 links.
    # mezz1_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    # mezz1 = relationship("FMCMezzanine", foreign_keys=[mezz1_pk])

    # mezz2_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    # mezz2 = relationship("FMCMezzanine", foreign_keys=[mezz2_pk])

    # # Although we've already catalogued the mezz linkages, it's sometimes
    # # useful to use an array. (For example, it lets us trivially write
    # # join() calls in HWM queries.)
    # mezz = relationship("FMCMezzanine",
    #     uselist=True,
    #     primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    # )

    #--------------------------
    # Define database columns associated with this object (in
    #    addition to those inherited by tuber)
    #--------------------------

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    tuber_uri = Column(String, nullable=False)
    tuber_objname = Column(String, nullable=False)
    tuber_objname = Column(String, nullable=False, default='iceboard')
    serial_number = Column(Integer)
    arm_serial_number = Column(String)
    fpga_ip_addr = Column(String)
    fpga_serial_number = Column(Integer)
    interface_ip_addr = Column(String)

    revision = Column(Integer)
    locked = Column(Integer)

    # ------------------------
    # Define default non-database variables.
    # ------------------------
    arm = None
    fpga_user_cls = None # Class used to create the application-specific FPGA firmware handler. Is set when the FPGA is configured.
    fpga_core = None # object handling the core FPGA fimware
    fpga_user = None # object handling the application-specific FPGA firmware
    hardware = None

    _self_reference = None # Used to ensure the object stays in memory and to check of the object has been opened
    # The direct UDP FPGA interface needs to know on which interface
    # the socket is to be opened. This information cannot be
    # reconstructed from the database. We define the interface_ip_addr
    # as a property that returns an error if accessed when not
    # defined.
    # def _interface_ip_addr_error(self):
    #     logger = logging.getLogger(__name__)
    #     logger.error('Currently do not support opening FPGA links with Iceboards objects created from the database because the interface address in unknown for UDP binding')

    # interface_ip_addr = property(_interface_ip_addr_error) # This will be overriden

    def __init__(self, **kwargs):
        """
        Creates an Iceboard that is accessed through the networking parameters specified in the database.
        """

        super(type(self), self).__init__(tuber_objname='iceboard', **kwargs)

        self.fpga_port_number = 41000 + 4*(self.serial_number)
        self.fpga_subarray = 0 # another thing we probably won't need

        self.logger = logging.getLogger(__name__)
        self.logger.debug('Instantiating Iceboard S/N %03i from direct instantiation' % (self.serial_number))
        self.logger.debug('S/N=%03i, uri=%s, fpga ip=%s' % (self.serial_number, self.tuber_uri, self.fpga_ip_addr))

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self):
        """
        Reconstructs the Iceboard basic information from the database
        entry and open the link to the Iceboard.
        """
        self.fpga_port_number = 41000 + 4*(self.serial_number)
        self.fpga_subarray = 0 # another thing we probably won't need

        self.logger = logging.getLogger(__name__)
        self.logger.debug('Reconstructing Iceboard object S/N %03i from database entry' % (self.serial_number))

    def __repr__(self):
        return 'Iceboard S/N %03i' % self.serial_number

    # __getattr__ = attribute_publisher.AttributeUser.get_registered_attribute
    # __dir__ = attribute_publisher.AttributeUser.get_dir

    def open(self):
        """
        Establishes the connection with the hardware and firmware on the IceBoard and create all appropriate handling classes.
        """

        self.close() # Make sure we cleanly close everything and free resources before creating new ones

        # Instantiate the ARM firmware handling object
        # We could skip this phase if we don't want to use the ARM (and the FPGA is programmed by other means)
        self.arm = tuber.TuberHWMResource(self.tuber_uri, self.tuber_objname)
        self.register(self.arm) # Allow access to the fpga_core methods/attributes from this class

        # Open communication with the FPGA and initialize the core firmware object (but leave the firmware in its current state)
        # We need this now to create the basic interface to the hardware (I2C, buck sync, FMC etc)
        self.logger.info('Instantiating core FPGA firmware handlers for board #%i' % (self.serial_number))
        self.fpga_core = FpgaFirmware(self, self.fpga_ip_addr, self.fpga_port_number, interface_ip_addr=self.interface_ip_addr, serial_number = self.fpga_serial_number)
        self.fpga_core.open()
        self.register(self.fpga_core) # Allow access to the fpga_core methods/attributes from this class

        # Instantiate hardware managers.
        # This requires an I2C link to the hardware, which for now is provided by the FPGA.
        self.logger.info('Instantiating IceBoard hardware handlers for board #%i' % (self.serial_number))
        self.hardware = IceBoardHardware(self.fpga_core)
        self.hardware.open()
        self.register(self.hardware) # Allow access to the hardware methods/attributes from this class

        # We can now create the application-specific firmware handlers, if there is any
        if self.fpga_user_cls:
            self.logger.info('Instantiating Application-specific FPGA firmware handlers for board #%i' % (self.serial_number))
            self.fpga_user = self.fpga_user_cls(self) # here we need the serial number because we use the FPGA Ethernet interface.
            self.fpga_user.open()
            self.register(self.fpga_user) # Allow access to the fpga_user methods/attributes from this class
        else:
            self.logger.info('No application-specific FPGA firmware handlers available for IceBoard S/N #%i. Only basic functionnalities will be available' % (self.serial_number))

        self._self_reference = self # Create circular reference to prevent the object from being removed from memory until closed.

    def close(self):

        if self.fpga_user:
            self.logger.info('Closing application-specific FPGA firmware handlers for board #%i' % (self.serial_number))
            self.unregister(self.fpga_user)
            self.fpga_user.close()
            self.fpga_user = None

        if self.hardware:
            self.logger.info('Closing IceBoard hardware handlers for board #%i' % (self.serial_number))
            self.unregister(self.hardware)
            self.hardware.close()
            self.hardware = None

        if self.fpga_core:
            self.logger.info('Closing core FPGA firmware handlers for board #%i' % (self.serial_number))
            self.unregister(self.fpga_core)
            self.fpga_core.close()
            self.fpga_core = None

        if self.arm:
            self.logger.info('Closing core arm firmware handlers for board #%i' % (self.serial_number))
            self.unregister(self.arm)
            # self.arm.close() # Tuber has no close()
            self.arm = None

        self._self_reference = None # Now the object can be garbage collected if no one else uses it

    def configure_fpga(self, bitfile, fpga_firmware_cls=None):
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
        """

        import base64

        if self.locked or (self.locked is None):
                raise IceBoardException('Iceboard with serial %016X is locked and its FPGA cannot be configured' % self.serial_number)
        # First, we check if the desired FPGA already replies to broadcasts.
        # If so, we know it is programmed with *some* firmware and we can do further checks
        # and potentially could avoid reprogramming the FPGA

        # Blindly attempts to configure the FPGA networking is case its firmware is already loaded. This will allow us to check if the firmware is already loaded.
        self.logger.info('Configuring FPGA networking parameters before checking if it is already programmed')
        FpgaFirmware.set_networking_parameters(serial_number=self.fpga_serial_number, interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, broadcast_group = 0)

        # Get FPGA configuration info so we can decide if the FPGA needs reprogramming
        self.logger.info('Checking if the FPGA on board S/N %03i is already programmed' % self.serial_number)
        (serial, timestamp) = FpgaFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)

        # Program the FPGA if it did not return the proper config info
        if serial != self.fpga_serial_number: # if the FPGA has not replied, we program it
            self.logger.info('Configuring FPGA on board #%i through tuber at  %s' % (self.serial_number, self.tuber_uri))
            md5_string = bitfile.md5_string
            b64_string = base64.b64encode(bitfile.data)
            with tuber.TuberHWMResource(self.tuber_uri, self.tuber_objname) as arm:
                arm.load_fpga_bitstream(b64_string, md5_string)
            # Configure the FPGA networking foe the freshly programmed firmware
            self.logger.info('Configuring FPGA networking parameters after reprogramming')
            FpgaFirmware.set_networking_parameters(serial_number=self.fpga_serial_number, interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, broadcast_group = 0)
            # Check if the firmware is now responding with proper configuration info
            (serial, timestamp) = FpgaFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)

            # if the FPGA still does not reply to its assigned address after programming, raise an error
            if serial != self.fpga_serial_number:
                raise IceBoardException('Failed to program the FPGA on board #%i' % (self.serial_number))
        else:
            self.logger.info('FPGA on board #%i at %s is already configured. Skipping configuration' % (self.serial_number, self.tuber_uri))

        self.fpga_user_cls = fpga_firmware_cls

        # # Check which FPGAs respond to broadcasts after programming
        # self.logger.info('Checking again what FPGAs are on the network')
        # fpga_serials = FpgaFirmware.discover_fpgas(interfaces)
        # if self.fpga_serial_number not in fpga_serials:
        #     self.logger.error('Failed to find FPGA on board #%i' % (self.serial_number))


    def get_info(self):
        """Loads the info data on the motherboard"""
        pass

    def status(self):
        """Displays the status of the motherboard"""

def discover(session, timeout, interface_ip_addr):
    """
    Update the Iceboard table with the list of available
    Iceboards actually found on the network. 'timout' indicates the time we
    wait for an answer before we decide that there is no board.

    For now, this function finds the ARMs by probing all addresses
    from a static tables. The Iceboards are identified by
    verifying if their ARM processors offer a tuber interface.
    Once we have a broadcast discovery protocol in the ARM the
    table will not be necessary. On that case we will broadcast a identification
    request, and every board will reply back a packet, which will reveal their
    IP address and any other information in the packet. Once we have that, we can contact tuber
    to obtain all the information needed to create an IceBoard object. This includes:
        arm serial number: from arm (needed?)
        fpga serial number: from JTAG,
        board serial number: from board's EEPROM

    """
    logger = logging.getLogger(__name__)
    logger.debug('Discovering boards')

    # Temporary lookup table used to determine the ARM address based on the
    # FPGA serial number since we don't have a way to find which ARM
    # processor is out there.  Eventually the ARMs will have a discovery
    # protocol that will allow us to get this information on the fly.  We
    # use the ARM's MAC address as its unique serial number, but it could be
    # anything.
    #
    # Note: JFC: I used to create a table of IceBoard objects but the hidden machinery of SQLAlchemy did not like that. It tried to generate SQL statements during the table creation, but the iceboards table did not exist yet
    ARM_TABLE = [
        # ARM IP address : (ARM Serial (MAC address), FPGA serial , board_number, locked)
        #(serial_number, tuber_uri, arm_serial_number, fpga_ip_addr, fpga_serial_number, locked)
        ( 7, 'http://10.10.10.57:80/tuber', '84:7E:40:6F:4A:F2', '10.10.10.37', 0x2069c2107eb05c, False),
        (18, 'http://10.10.10.18:80/tuber', '84:7E:40:6F:CC:CA', '10.10.10.48', 0x24d046483e301c, True ),
        ( 5, 'http://10.10.10.5:80/tuber' , '84:7E:40:6F:63:18', '10.10.10.35', 0,                False),
        ( 9, 'http://10.10.10.9:80/tuber' , '84:7E:40:6F:D4:CA', '10.10.10.39', 0,                False),
        ( 8, 'http://10.10.10.8:80/tuber' , '84:7E:40:6F:41:E8', '10.10.10.38', 0x6869c2107eb05c, False),
        (19, 'http://10.10.10.19:80/tuber', '84:7E:40:6F:CC:82', '10.10.10.49', 0x1829c2107eb05c, False),
        (14, 'http://10.10.10.14:80/tuber', '84:7E:40:6F:CC:BE', '10.10.10.44', 0x3829c2107eb05c, False),
        (17, 'http://10.10.10.17:80/tuber', '84:7E:40:6F:CC:9C', '10.10.10.47', 0,                False),
        (16, 'http://10.10.10.16:80/tuber', '84:7E:40:70:01:CA', '10.10.10.46', 0,                False),
    ]
    logger.debug('Querying existing database entries')

    iceboards = session.query(IceBoard) # get all the iceboards from the database
    database_serials = [ib.serial_number for ib in iceboards] # get the serial numbers of all boards known to the database

    # Now add any iceboard that we discover on the network and that is not already in the database
    for (serial_number, tuber_uri, arm_serial_number, fpga_ip_addr, fpga_serial_number, locked) in ARM_TABLE:
        if tuber.TuberHWMResource.ping(tuber_uri):
            if serial_number in database_serials:
                # print serial_number
                logger.debug('Board S/N %i at %s already in database!' % (serial_number, tuber_uri))
            else:
                # print ib.serial_number
                logger.debug('Found new board S/N %i at %s!' % (serial_number, tuber_uri))
                ib = IceBoard(serial_number=serial_number, tuber_uri=tuber_uri, arm_serial_number=arm_serial_number, fpga_ip_addr=fpga_ip_addr, fpga_serial_number=fpga_serial_number, locked=locked, interface_ip_addr = interface_ip_addr)
                ib.interface_ip_addr = interface_ip_addr # FIXME: to be removed
                session.add(ib)
    session.flush()
    return

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
