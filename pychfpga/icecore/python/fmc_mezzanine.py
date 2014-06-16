"""FMC Mezzanine schema object."""
import logging

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref

from hardware_map import HWMResource

# import iceboard.iceboard
from lib.fmc_eeprom import FMC_EEPROM

class FMCMezzanine(HWMResource):
    """FMC Mezzanine schema object.

    This is an abstract class. To specialize it for a particular FMC
    mezzanine, create a subclass. There should be some good examples
    to borrow from; you should refer to them rather than this code.
    """

    __tablename__ = 'fmc_mezzanines'
    __table_args__ = (UniqueConstraint('cls','type','serial'),)
    __mapper_args__ = {
            'polymorphic_identity': 'fmc_mezzanine',
            'polymorphic_on': 'cls'
    }

    # # Since there are two "mezz" references per ICEBoard, the backreference
    # # has to be smart enough to accept either in the join.
    # iceboard = relationship(
    #     "IceBoard",
    #     uselist=False,
    #     primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    # )

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    type = Column(String, nullable=False)
    serial = Column(Integer)
    revision = Column(Integer)

    class FMCMezzanineException(Exception):
        pass

    @staticmethod
    def get_type_string(i2c, bus_name):
        """ Returns the model string of the FMC.
        For not, just returns a string based on the first character of the EEPROM.

        This method is called before the instance is created. It is used to
        determine which object to use for instantiation.

        This method is to be upgraded to read the standard FMC eeprom field, and fall back to
        the first byte if a valid FMC-standard format is not found.
        """
        logger = logging.getLogger(__name__)
        logger.debug("Attempting to read FMC eeprom to determine board presence")
        eeprom = FMC_EEPROM(i2c, bus_name)
        data = eeprom.read(0, length=1, noerror=True, verbose=1)
        logger.debug("FMC eeprom returned the value: %i", data[0])
        return '0x%02X' % data[0]

    def __init__(self, motherboard, fmc_number, fmc_name, verbose=0):
        self.logger = logging.getLogger(__name__)
        self.motherboard = motherboard
        self.verbose = verbose
        self.fmc_number = fmc_number
        self.fmc_name = fmc_name

        # provide access to the resources needed to access the ADC board hardware
        self.i2c = self.motherboard.i2c # I2C bus
        # self.spi = self.motherboard.SPI # SPI bus

        self.logger.debug('  - FMC EEPROM')
        self.eeprom = FMC_EEPROM(self.i2c, self.fmc_name, verbose = verbose)
        self.eeprom.init()


    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self._board_is_present

    # def eeprom_write(self, buf):
    #     '''Writes a collection of bytes to the internal EEPROM.

    #     Don't do this unless you're at McGill, and you're commissioning
    #     and testing a new mezzanine! This method makes it trivial to
    #     delete non-volatile data. Figuring out how to re-write the original
    #     data is a tougher nut to crack.

    #     According to FMC specs, the EEPROM is required to contain an
    #     IPMI FRU descriptor. If you want to insert this kind of data,
    #     you should use the 'ipmi_fru' module included in this Python
    #     repository.

    #     Since EEPROM contents are parsed by machine and used during
    #     board bring-up, it's important that the data you write is valid.
    #     You should refer to reference code (likely in the QC suite) rather
    #     than trying to guess what structures belong in here.
    #     '''

    #     import base64

    #     if self.pk==self.iceboard.mezz1_pk: mezz_number = 1
    #     else: mezz_number = 2

    #     b64_string = base64.b64encode(buf)
    #     self.iceboard.mezz_eeprom_write(mezz_number, b64_string, 0)

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
