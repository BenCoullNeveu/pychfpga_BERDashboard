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

    # Since there are two "mezz" references per ICEBoard, the backreference
    # has to be smart enough to accept either in the join.
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

    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self._board_is_present


# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
