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

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, inspect
from sqlalchemy.orm import relationship, backref, reconstructor

from lib.attribute_publisher import AttributeUser
from  hardware_map import HWMResource
from  tuber import TuberHWMResource
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
from fpga_firmware import FpgaFirmware
from fpga_core import FpgaCoreFirmware
from iceboard_hardware import IceBoardHardware
from icebox import IceBox

# import arm # object giving access to the ARM firmware
# import hardware handlers

class IceBoardException(Exception):
    pass

class IceBoard(HWMResource, AttributeUser):
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
    mezz1_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz1 = relationship("FMCMezzanine", foreign_keys=[mezz1_pk])

    mezz2_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz2 = relationship("FMCMezzanine", foreign_keys=[mezz2_pk])

    # # Although we've already catalogued the mezz linkages, it's sometimes
    # # useful to use an array. (For example, it lets us trivially write
    # # join() calls in HWM queries.)
    mezz = relationship("FMCMezzanine",
        uselist=True,
        primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    )

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
    backplane_serial_number = Column(Integer)

    # ARM firmware-related definition
    # tuber_uri = Column(String)
    # tuber_objname = Column(String, nullable=False)
    # tuber_objname = Column(String, default='iceboard')
    arm_serial_number = Column(String)

    # FPGA firmware-related definition
    fpga_ip_addr = Column(String)
    fpga_serial_number = Column(Integer)
    # fpga_firmware_crc = Column(Integer)
    # fpga_firmware_class = Column(String)
    interface_ip_addr = Column(String)

    fpga_pk = Column(Integer, ForeignKey('fpgafirmware.pk'))
    fpga = relationship("FpgaFirmware", uselist=False, cascade="all, delete, delete-orphan", single_parent=True) # one-to-one relationship with the firmware object. Make sure there is only one firmware object.

    arm_pk = Column(Integer, ForeignKey('armfirmware.pk'))
    arm = relationship("TuberHWMResource", uselist=False, cascade="all, delete, delete-orphan", single_parent=True) # one-to-one relationship with the firmware object. Make sure there is only one firmware object.

    # ------------------------
    # Define default non-database variables.
    # ------------------------
    # arm = None # object handling the ARM firmware
    hw = None # Object handling the IceBoard hardware

    _self_reference = None # Used to ensure the object stays in memory and to check of the object has been opened

    def __init__(self, auto_open=True, **kwargs):
        """
        Creates an Iceboard that is accessed through the networking parameters specified in the database.
        """

        super(type(self), self).__init__(**kwargs)

        if self.serial_number:
            self.fpga_port_number = 41000 + 4*(self.serial_number)
        self.fpga_subarray = 0 # another thing we probably won't need
        # self._auto_open = auto_open
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Instantiating Iceboard S/N %s from direct instantiation' % ('%03i' % self.serial_number if self.serial_number else self.serial_number))
        self.logger.debug('S/N=%s, uri=%s, fpga ip=%s' % ('%03i' % self.serial_number if self.serial_number else self.serial_number, self.arm.tuber_uri if self.arm else None, self.fpga_ip_addr))

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self):
        """
        Reconstructs the Iceboard basic information from the database
        entry and open the link to the Iceboard.
        """
        if self.serial_number:
            self.fpga_port_number = 41000 + 4*(self.serial_number)
        self.fpga_subarray = 0 # another thing we probably won't need

        self.logger = logging.getLogger(__name__)
        self.logger.debug('Reconstructing Iceboard object S/N %s from database entry' % ('%03i' % self.serial_number if self.serial_number else self.serial_number))

    def __repr__(self):
        return 'Iceboard S/N %s' % ('%03i' % self.serial_number if self.serial_number else self.serial_number)

    # __getattr__ = attribute_publisher.AttributeUser.get_registered_attribute
    # __dir__ = attribute_publisher.AttributeUser.get_dir
    def __getattr__(self,name):
        self.logger.debug('calling top-level __getattr__(%s) for Iceboard object S/N %03i' % (name, self.serial_number))
        # if not self._self_reference:
        #     self.logger.debug('Automatically opening Iceboard object S/N %03i' % (self.serial_number))
        #     self.open()
        return super(type(self), self).__getattr__(name)

    def open(self, *args, **kwargs):
        """
        Establishes the connection with the hardware and firmware on the IceBoard and create all appropriate handling classes.
        """

        self.close() # Make sure we cleanly close everything and free resources before creating new ones

        # Instantiate the ARM firmware handling object
        # We could skip this phase if we don't want to use the ARM (and the FPGA is programmed by other means)
        # self.arm = TuberHWMResource(self.tuber_uri, self.tuber_objname)
        if self.arm:
            self.register(self.arm) # Allow access to the fpga methods/attributes from this class


        # Log a warning if no firmware has been associated with the FPGA
        if not self.fpga:
            self.logger.warning('FPGA firmware is not specified for this board. The FPGA-related methods will not be available. Use set_fpga_firmware() to set the firmware to use')

        # Open communication with the FPGA and initialize the core firmware object (but leave the firmware in its current state)
        # We need this now to create the basic interface that is needed for low-level hardware interface (I2C, buck sync, FMC SPI etc)
        if self.fpga:
            self.logger.info('Instantiating core FPGA firmware handlers for board #%i' % (self.serial_number))
            self.fpga.open_core(ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, interface_ip_addr=self.interface_ip_addr, serial_number = self.fpga_serial_number) # open the core functionnalities only for now
            self.register(self.fpga, self.fpga.get_core_attributes()) # get attributes of the core FPGA firmware only. We'll add the full application-specific attributes later.

        # Instantiate hardware managers.
        # This requires an I2C link to the hardware (i2c_write_read() and i2c_set_port()), which should be provided either by the ARM or by the FPGA.
        self.logger.info('Instantiating IceBoard hardware handlers for board #%i' % (self.serial_number))
        self.hw = IceBoardHardware(iceboard=self)
        self.hw.open()
        self.register(self.hw) # Allow access to the hardware methods/attributes from this class
        self.i2c = self.hw.get_i2c_interface() # get standardized I2C interface that can be used more easily by the user firmware

        # Read basic backplane information (backplane S/N, slot number) so we know where this board is in the array
        (self.backplane_serial, self.slot_number) = IceBox.get_backplane_info(iceboard=self)

        # We can now create the full-fledged application-specific FPGA firmware handlers
        if self.fpga:
            self.logger.info('Instantiating Application-specific FPGA firmware handlers for board #%i' % (self.serial_number))
            self.unregister(self.fpga)
            self.fpga.open(*args, **kwargs) # Open the application-specific firmware
            self.register(self.fpga) # Allow access to the fpga_user methods/attributes from this class

        self._self_reference = self # Create circular reference to prevent the object from being removed from memory until closed.

    def close(self):

        if self.fpga:
            self.logger.info('Closing application-specific FPGA firmware handlers for board #%i' % (self.serial_number))
            self.unregister(self.fpga)
            self.fpga.close()

        if self.hw:
            self.logger.info('Closing IceBoard hardware handlers for board #%i' % (self.serial_number))
            self.unregister(self.hw)
            self.hw.close()
            self.hw = None

        if self.fpga:
            self.logger.info('Closing core FPGA firmware handlers for board #%i' % (self.serial_number))
            self.fpga.close_core()

        if self.arm:
            self.logger.info('Closing core arm firmware handlers for board #%i' % (self.serial_number))
            self.unregister(self.arm)
            # self.arm.close() # Tuber has no close()
            # self.arm = None

        self._self_reference = None # Now the object can be garbage collected if no one else uses it

    def detect_mezz(self, force_type_string=None):

        # get a list of all polymorphic strings of classes derived from FMCMezzanine
        available_mezz_types = {m.polymorphic_identity:m.class_ for m in inspect(FMCMezzanine).polymorphic_map.values()}

        mezz_list = [(0, 'FMCA'), (1, 'FMCB')]

        if self.mezz:
            del self.mezz

        for (fmc_number, fmc_name) in mezz_list:
            if force_type_string:
                type_string = force_type_string
            else:
                type_string = FMCMezzanine.get_type_string(self.i2c, fmc_name)

            if type_string in available_mezz_types:
                mezz_class = available_mezz_types[type_string]
                self.mezz[fmc_number] = mezz_class(motherboard=self, fmc_number=fmc_number, fmc_name=fmc_name)

    def set_fpga_firmware(self, bitstream_object, firmware_class, configure_fpga = True):

        self.close()

        self.logger.debug('Assigning firmware object to board S/N%03i' % (self.serial_number))
        if self.fpga:
            del self.fpga
        self.fpga = firmware_class(motherboard=self, bitstream_object = bitstream_object) # Create a FPGA firmware object. This just initializes variables for now.

        # Configure the fpga if we asked for it.
        if configure_fpga:
            self.configure_fpga()

    def configure_fpga(self):
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
        if not self.fpga:
            raise IceBoardException('Please set the firmware associated with the IceBoard using set_fpga_firmware(bistream_object, firmware_class')


        bitfile = self.fpga.firmware_bitstream_object

        import base64

        if self.locked or (self.locked is None):
                raise IceBoardException('Iceboard with serial %016X is locked and its FPGA cannot be configured' % self.serial_number)

        already_configured = False

        # First, try to get the FPGA configuration from the FPGA IP address  so we can decide if the FPGA needs reprogramming
        self.logger.info('Checking the FPGA on board S/N %03i configuration' % self.serial_number)
        (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)

        # if the FPGA did not respond, maybe it is programmed but its IP address is not set.
        #  So if we know the FPGA serial number, set its IP address and try again
        if not serial and self.fpga_serial_number:
            #  blindly attempts to configure the FPGA networking is case its firmware is already loaded. This will allow us to check if the firmware is already loaded.
            self.logger.info('The FPGA on board S/N %03i did not respond. Attempting to configure its networking parameters' % self.serial_number)
            FpgaCoreFirmware.set_networking_parameters(serial_number=self.fpga_serial_number, interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, broadcast_group = 0)
            self.logger.info('Rechecking the FPGA on board S/N %03i configuration' % self.serial_number)
            (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)
            self.logger.info('The FPGA on board S/N %03i replied with serial=%r, timestamp=%r' % (self.serial_number, serial, timestamp))


        already_configured = (serial and serial == self.fpga_serial_number)

        # Program the FPGA if it did not return the proper config info
        if not already_configured: # if the FPGA has not replied, we program it
            if not self.arm:
                raise IceBoardException('The Iceboard does not have an ARM firmware object needed to configure the FPGA')
            self.logger.info('Configuring FPGA on board S/N %i through tuber at  %s' % (self.serial_number, self.arm.tuber_uri))
            md5_string = bitfile.md5_string
            b64_string = base64.b64encode(bitfile.data)
            # with TuberHWMResource(self.tuber_uri, self.tuber_objname) as arm:
            self.arm.load_fpga_bitstream(b64_string, md5_string)
            # Configure the FPGA networking foe the freshly programmed firmware

            if self.fpga_serial_number:
                self.logger.info('Configuring FPGA networking parameters after reprogramming')
                FpgaCoreFirmware.set_networking_parameters(serial_number=self.fpga_serial_number, interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number, broadcast_group = 0)
                # Check if the firmware is now responding with proper configuration info
                (serial, timestamp) = FpgaCoreFirmware.get_fpga_config(interface_ip_addr=self.interface_ip_addr, ip_addr=self.fpga_ip_addr, port_number=self.fpga_port_number)

                # if the FPGA still does not reply to its assigned address after programming, raise an error
                if not serial:
                    raise IceBoardException('Failed to program the FPGA on board S/N %03i. The board did not reply after its IP address was configured.' % (self.serial_number))
                elif serial != self.fpga_serial_number:
                    raise IceBoardException('Failed to program the FPGA on board S/N %03i. Expected serial %014X, got %014X' % (self.serial_number, self.fpga_serial_number, serial))
            else:
                self.logger.warning('IP address on FPGA on board S/N %i is not set because the FPGA serial number is not known' % (self.serial_number))
        else:
            self.logger.info('FPGA on IceBoard S/N %03i is already configured. Skipping configuration' % (self.serial_number))

    def get_info(self):
        """Loads the info data on the motherboard"""
        pass

    def status(self):
        """Displays the status of the motherboard"""

def load(session, filename, interface_ip_addr=None):
    """
    Adds the Iceboard entries listed in the specified CSV file into the database.
    """
    import csv

    iceboards = session.query(IceBoard) # get all the iceboards from the database
    keymap = dict(iceboards.values(IceBoard.serial_number, IceBoard.pk)) # get a dictionnary that maps the serial number to primary keys

    with open(filename, 'rb') as file:
        reader = csv.reader((line for line in file if not line.lstrip().startswith('#'))) # uses a generator to trip the comments
        for (serial_number, tuber_uri, arm_serial_number, fpga_ip_addr, fpga_serial_number, locked, subarray) in reader:
            serial_number = int(serial_number, 0)
            tuber_uri = tuber_uri.strip("' ")
            arm_serial_number = arm_serial_number.strip("' ")
            fpga_ip_addr = fpga_ip_addr.strip("' ")
            fpga_serial_number = int(fpga_serial_number, 0)
            locked = int(locked, 0)
            subarray = int(subarray, 0)

            if serial_number in keymap:
                ib = iceboards.get(keymap[serial_number])
                ib.arm = TuberHWMResource(tuber_uri = tuber_uri, tuber_objname = 'iceboard')
                ib.arm_serial_number = arm_serial_number
                ib.fpga_ip_addr = fpga_ip_addr
                ib.fpga_serial_number = fpga_serial_number
                ib.locked = locked
                ib.subarray = subarray
                ib.interface_ip_addr = interface_ip_addr
            else:
                ib = IceBoard(
                    serial_number=serial_number,
                    arm = TuberHWMResource(tuber_uri=tuber_uri, tuber_objname = 'iceboard'),
                    arm_serial_number=arm_serial_number,
                    fpga_ip_addr=fpga_ip_addr,
                    fpga_serial_number=fpga_serial_number,
                    locked=locked ,
                    subarray = subarray,
                    interface_ip_addr = interface_ip_addr)
                session.add(ib)
    session.flush()


def discover(session, timeout, interface_ip_addr=None):
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

    # Add entries for every new FPGA serial that is not already in the database
    database_serials = dict(iceboards.values(IceBoard.fpga_serial_number, IceBoard.pk)) # get the serial numbers of all known FPGAs
    serials = FpgaCoreFirmware.discover_fpgas(interface_ip_addr = interface_ip_addr)
    for ser in serials:
        if ser not in database_serials:
            ib = IceBoard(
                fpga_serial_number = int(ser),
                interface_ip_addr = interface_ip_addr)
            session.add(ib)
    session.commit()

    # Check if each iceboard actually responds to tuber requests
    for ib in iceboards:
        if ib.arm and ib.arm.tuber_uri:
            ib.present = TuberHWMResource.ping(ib.arm.tuber_uri)
    session.commit()
    return

    # Now add any iceboard that we discover on the network and that is not already in the database

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
