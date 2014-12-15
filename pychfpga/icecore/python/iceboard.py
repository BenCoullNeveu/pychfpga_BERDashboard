""" Base object for IceBoard (McGill Model MGK7MB) objects.

To specialise an IceBoard object for a particular experiment, you can simply
change the 'app_handler_name' field in the hardware map to your specific
application, and the object will connect to the appropriate code either on the
on-board ARM processor or to local Python objects, assuming those exist. If no
application is provided, the board will provide only its core
functionnalities.

Alternatively, you can subclass IceBoard to hard-code the application handler
name and add additional hardware map properties if needed.
"""

import logging


import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import reconstructor, object_session, class_mapper
from sqlalchemy.orm.collections import attribute_mapped_collection

from . import hardware_map, tuber
import fmc_mezzanine # used import x to avoid circular import problem
from fpga_bitstream import FpgaBitstream

class IceBoardException(Exception):
    pass


class IceBoard(hardware_map.HWMResource, hardware_map.HWMHandlerManager):
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

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    # backplane_serial_number = Column(Integer) # should be replaced by a backplane reference object
    # _icebox_pk = Column(Integer, ForeignKey('icebox._pk'), index=True)

    # serial = Column(String, doc="The serial number written on the board (verbatim!)") # used by Graeme
    serial_number = Column(Integer, doc="The serial number written on the board") # used by JF

    # slot = Column(Integer, doc="The IceCrate slot occupied by this board") # used by Graeme
    slot_number = Column(Integer, doc="The IceBox slot occupied by this board (1-16)") # used by JF

    locked = Column(Integer)
    subarray = Column(Integer)
    present = Column(Integer, default = 0) # indicates if the board is currently present in the array

    # FPGA firmware-related definition
    fpga_ip_addr = Column(String)
    fpga_serial_number = Column(Integer) # will be obsolete when we can get this from the ARM
    fpga_bitstream_pk = Column(Integer, ForeignKey('fpga_bitstream.pk'), index=True)
    fpga_bitstream = relationship("FpgaBitstream", foreign_keys=[fpga_bitstream_pk], uselist=False, lazy='joined')

    tuber_uri = Column(String) # The URI used to access remote handlers (used to be 'hostname')

    # The core handler describes where to find the methods and attributes needed to operate the
    # core functionnalities of the Iceboard (typically offered by the on-board ARM
    # processor through a JSON/HTTP interface (tuber)
    core_handler_name = Column(String)
    app_handler_name = Column(String)


    # Is this useful?
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
        super(IceBoard, self).__init__(*args, **kwargs)

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self, **kwargs):
        """ Create an Iceboard object from database and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('IceBoard: Recreating instance from database for for IceBoard S/N %r' % (self.serial_number))

    def init_handler(self):
        self.set_handler(self.tuber_uri, self.core_handler_name, self.app_handler_name, self._pk)

    def __repr__(self):
        """ Provide a nice human-friendly representation of this Iceboard object.
        This representation is often used as a tag for logging.
        """
        return '%s S/N %r @%08X' % (self.__class__.__name__, self.serial_number, id(self)) # Used by JF
        # return "%s(%r)" % (self.__class__.__name__, self.hostname)

    def set_fpga_firmware(self, bitstream_object, force=False):
        '''
        Configures the FPGA with the specified bitstream object.
        '''

        import base64

        # if self.fpga_bitstream:
        #     del self.fpga_bitstream

        # Assign the new bitstream object. Since this bistream object comes
        # from another session, we cannot use it directly in this thread-
        # specific session. We therefore need to find its corresponding entry
        # in the database from this session.
        # session = object_session(self)
        # self.fpga_bitstream = session.merge(bitstream_object)
        self.fpga_bitstream = bitstream_object
        self.logger.debug('IceBoard S/N %03i.set_fpga_firmware: Assigning firmware %r' % (self.serial_number, self.fpga_bitstream))
        self.close()



        if self.locked or (self.locked is None):
                raise IceBoardException('%r: Iceboard is locked and its FPGA cannot be configured' % self)

        if not self.is_fpga_programmed() or force: # if the FPGA has not replied, we program it
            self.logger.info('%r: Configuring FPGA' % self)
            b64_string = base64.b64encode(self.fpga_bitstream.get_bitstream_data())
            self._set_fpga_bitstream_base64(b64_string) # SD Card v2.3
            self.logger.info('%r: Done configuring FPGA' % self)
        else:
            self.logger.info('%r: FPGA is already configured. Skipping configuration' % self)

        # maybe try to do a mmi read check here

    def _eeprom_write_ipmi(self, *args, **kwargs): # for backwards compatibility to suggested new name
        return  self._write_motherboard_spi_eeprom_ipmi(*args, **kwargs)

    def _write_motherboard_spi_eeprom_base64(self, *args, **kwargs): # method renaming
        return  self._motherboard_eeprom_write_base64(*args, **kwargs)

    def _write_motherboard_spi_eeprom_ipmi(self, part_number, serial_number, product_version):
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
        return self._write_motherboard_spi_eeprom_base64(b64_string)

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
                for sc in class_mapper(fmc_mezzanine.FMCMezzanine).self_and_descendants:
                    if sc.polymorphic_identity == part_number:
                        MezzClass = sc.class_
            if MezzClass:
                self.logger.info('IceBoard SN%r detect_mezzanines: Creating Mezzanine Serial %s in Mezzanine %i' % (self.serial_number, serial, m))
                new_mezz = MezzClass(mezzanine=m, serial=serial, type='') # 'type' cannnot be None so we give it an empty string
                self.hwm.add(new_mezz)
                self.hwm.commit()
                self.mezzanine[m] = new_mezz
            else:
                self.logger.warning("IceBoard SN%r detect_mezzanines(): There is no known FMC Mezzanine object with polymorphic map name '%r' for Mezzanine %r" % (self.serial_number, part_number, m))
                # self.mezzanine[m] = None
        self.update_handler() # added by JF to let the handlers update for the new mezz


class IceBoardHandler(hardware_map.Handler):
    """
    Basic Python handler for the IceBoard, which provides a standardized
    Memory-Mapped interface to the FPGA firmware. This firmware-specific
    application handler should subclass this class.

    The MMI is provided through the mmi_read() and mmi_write() methods.

    For now, those are provided through Tuber using the SPI peek/poke methods
    assuming the core firmware provides such an interface. But this will
    evolve as we a faster PCIe link to the FPGA. Also, mmi_read/write might
    completely bypass Tuber's HTTP/JSON overhead and go through an ARM's port that forwards the
    packets directly to the FPGA for maximum speed.

    Note that CHIME's chFPGA handler overrides these methods in a superclass to implement an
    MMI that interfaces directly to the FPGA through the SFP Ethernet port
    using a separate socket.
    """
    # # Define types of Memory-Mapped interfaces to the firmware
    # MMI_FPGA_ETHERNET = "fpga" # Talk directly to the FPGA through its Ethernet SFP module. This interface requires self.fpga_ip_addr, self.fpga_port_number and self.fpga_serial_number
    # MMI_ARM_TUBER = "tuber" # (Tentative) Interface through Tuber's peek & poke methods.
    # MMI_ARM_DIRECT = "direct" # (Tentative) Direct bypass MMI interface through the ARM. The address:port is provided by Tuber.


    # fpga_mmi_type = MMI_FPGA_ETHERNET # Have this as a static attribute for now. Later we'll pass it as an argument


    def __init__(self, **kwargs):
        super(IceBoardHandler, self).__init__(**kwargs)

    def hwm_update(self, hwm_object):
        """ Is called when the Hardware Map object might have changed to reflect those changes in the handler.
        """
        super(IceBoardHandler, self).hwm_update(hwm_object)
        self.logger.info('IceBoardHandler: %r.hwm_update()' % (self))
        self.serial_number = hwm_object.serial_number
        self.mezzanine = {key: hwm_mezz.handler for (key, hwm_mezz) in hwm_object.mezzanine.items()}
        self.logger.info('IceBoardHandler: %r.hwm_update(): has mezzanines %r' % (self, self.mezzanine))

    def mmi_read(self, addr):
        """ Read a single 32-bit word at specified byte address."""
        return self.fpga_spi_peek(addr)

    def mmi_write(self, addr, value):
        """ Write a single 32-bit word at specified byte address."""
        self._fpga_spi_poke(addr, value)


    def get_slot_number(self):
        """ Reads the GPIO to determine in which slot number this IceBoard is connected.
            Will return None of the board is not connected to a backplane (i.e. if the backplane I2C EEPROM does not respond).
        """
        raise NotImplementedError()

    def get_fpga_serial_number(self):
        """ Returns the FPGA DNA 57-bit unique serial number from the FPGA itself.
        """
        raise NotImplementedError()

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
