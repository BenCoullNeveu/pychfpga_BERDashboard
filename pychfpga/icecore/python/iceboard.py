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
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import reconstructor, object_session, class_mapper
from sqlalchemy.orm.collections import attribute_mapped_collection

import hardware_map
import tuber

import fmc_mezzanine # used import x to avoid circular import problem
import fpga_bitstream


class IceCrate(hardware_map.HWMResource, hardware_map.HWMHandlerManager):
    __tablename__ = 'icecrates'
    __table_args__ = (
        UniqueConstraint('serial'),
    )
    __mapper_args__ = {'polymorphic_identity': __package__}

    _pk = Column(Integer, primary_key=True)
    serial = Column(String,
                    doc="The serial number written on the board (verbatim!)")

    slots = relationship(
        "IceBoard",
        lazy="dynamic",
        query_class=hardware_map.HWMQuery,
        doc='''A SQLAlchemy subquery corresponding to this IceCrate's
            IceBoards. If you want to index this array using slot index,
            you should use 'iceboard' instead.''')

    slot = relationship(
        "IceBoard",
        backref=backref("crate"),
        collection_class=attribute_mapped_collection('slot'),
        doc="The IceCrate's IceBoards, indexed as you would expect.")

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.serial)

# *** JFC:To be removed
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
        'polymorphic_identity': 'IceBoard', # ***JFC: why core.iceboard.IceBoard
        'polymorphic_on': '_cls'
    }

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    _icecrate_pk = Column(Integer, ForeignKey('icecrates._pk'), index=True)

    serial_number = Column(String,
                    doc="The serial number written on the board (verbatim!)")

    slot_number = Column(Integer, doc="The IceCrate slot occupied by this board")

    subarray = Column(Integer)

    tuber_uri = Column(String) # The URI used to access remote handlers (used to be 'hostname')

	# *** JFC: those might be redundant now
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

	# *** JFC: just used for logging during debugging. will be removed.
    def __init__(self, *args, **kwargs):
        """ Create a new Iceboard object from scratch and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('%r: Creating instance' % (self))
        super(IceBoard, self).__init__(*args, **kwargs)

	# *** JFC: just used for logging during debugging. will be removed.
    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self, **kwargs):
        """ Create an Iceboard object from database and link it with its handler. """
        self.logger = logging.getLogger(__name__)
        self.logger.info('%r: Recreating instance from database' % (self))

    def set_application_handler(self, application_name=None):
        self.app_handler_name = application_name
        self.init_handler()

    def init_handler(self):
        """ Create or re-attach a handler to this HWM object.

        This is called whenever this instance of an HWM object has been
        created, recreated from the database, or changed.

        The default action is to connect to a handler that is registered under
        the name specified in '_cls'. In addition to offering its
        own attributes, the handler also provides the methods and properties
        obtained from Tuber for the default object name defined by the handler.

        The default handler for IceBoard is IceBoardHandler, which provides
        Tuber's 'IceBoard' methods and properties in addition to basic Pyhton
        helper methods.

        A subclass if IceBoard can or course redefine this method to connect
        to any other handler and Tuber object.
        """
        self.set_handler(object_id= self._pk, handler_name = self.app_handler_name or self._cls, tuber_uri = self.tuber_uri)

    def __repr__(self):
        """ Provides a concise string representation of this Iceboard that is informative enough to be used for logs.

        This string is typically used in syslog tags (32 characters max, alphanumeric characters only).
        """
        return "%s%s(%s)" % (repr(self.crate) + '.' if self.crate else '', # *** JFC: Is '.' accepted in the syslog tag?
                              self.__class__.__name__,
                              ('slot=%s' % self.slot) if self.crate
                                  else ('serial=%s' % self.serial_number) if self.serial_number
                                  else ('hostname=%s' % self.tuber_uri)
                              )


    def set_fpga_bitstream(self, buf, force=True):
        '''
        Configures the FPGA with the specified buffer.

        The buffer is an ordinary string object or similar, and
        contains an already loaded .BIT or .BIN file.

        Alternatively, the buf can be a FPGABitstream object.
        '''

        import base64

        # *** JFC: Could just use str(buf) and define FpgaBistream accordingly.
        if isinstance(buf, fpga_bitstream.FpgaBitstream):
            buf = buf.get_bitstream_data()

        if hasattr(self, 'close'):
            self.close()

        if not self.is_fpga_programmed() or force: # if the FPGA has not replied, we program it
            self.logger.info('%r: Configuring FPGA' % self)
            b64_string = base64.b64encode(buf)
            self._set_fpga_bitstream_base64(b64_string)
            self.logger.info('%r: Done configuring FPGA' % self)
        else:
            self.logger.info('%r: FPGA is already configured. Skipping configuration' % self)

    set_fpga_firmware = set_fpga_bitstream #*** JFC: for short-term compatibility

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

# ***************
# ** JFC: I would think FMCMezzanine should live in a separate file since this file is nabed iceboard.py.
# ***************

	# *** JFC: Maybe should just assert if the the mezzanine type is corect, with optional database update
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
    Basic Python handler for the IceBoard.

    It provides:
       - access to the methods and attributes provided by the ARM-based software through Tuber
       - offers a standardized memory-mapped interface to the FPGA firmware through the mmi_read() and mmi_write() methods.

    Firmware-specific application handlers should subclass this class.

    For now, the MMI interface is provided through Tuber using the SPI peek/poke methods
    assuming the core firmware provides such an interface. But this will
    evolve as we a faster PCIe link to the FPGA. Also, mmi_read/write might one day
    completely bypass Tuber's HTTP/JSON overhead and go through an ARM's port that forwards the
    packets directly to the FPGA for maximum speed.

    Note that CHIME's chFPGA handler overrides these methods in a superclass to implement an
    MMI that interfaces directly to the FPGA through the SFP Ethernet port
    using a separate socket.
    """
    __handler_for__ = IceBoard
    __handler_name__ = 'IceBoard'

    def __init__(self, tuber_uri=None, tuber_object = 'IceBoard', **kwargs):

        if tuber_uri and tuber_object:
            self.core_handler = tuber.TuberObject(tuber_uri, tuber_object)
        else:
            self.core_handler = None

        super(IceBoardHandler, self).__init__(**kwargs)

    def __dir__(self):
        class_attributes = [item  for class_ in type(self).mro() for item in class_.__dict__.keys()]
        instance_attributes = self.__dict__.keys()
        core_handler_attributes = dir(self.core_handler)
        return list(set(class_attributes + instance_attributes + core_handler_attributes))

    def __getattr__(self, name):
        if self.core_handler:
            return getattr(self.core_handler, name)
        else:
            return AttributeError

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
        return self._fpga_spi_peek(addr)

    def mmi_write(self, addr, value):
        """ Write a single 32-bit word at specified byte address."""
        self._fpga_spi_poke(addr, value)


    def get_number_of_mezzanine_slots(self):
        """ Returns the number of mezzanine slots supported by this board .

        NOTE: It would be nice if the ARM could provide this function.
        """
        return 2

    def get_slot_number(self):
        """ Reads the GPIO to determine in which slot number this IceBoard is connected.
            Will return None of the board is not connected to a backplane (i.e. if the backplane I2C EEPROM does not respond).
        """
        raise NotImplementedError()

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
