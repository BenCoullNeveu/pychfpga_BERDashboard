"""FMC Mezzanine schema object."""
import logging

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import reconstructor

import hardware_map
from . import handler

class FMCMezzanine(hardware_map.HWMResource, handler.HWMHandlerManager):
    """FMC Mezzanine schema object.

    This is an abstract class. To specialize it for a particular FMC
    mezzanine, create a subclass. There should be some good examples
    to borrow from; you should refer to them rather than this code.
    """

    __tablename__ = 'fmc_mezzanines'
    __mapper_args__ = {
        'polymorphic_identity': 'fmc_mezzanine',
        'polymorphic_on': '_cls'
    }
    __table_args__ = (
        CheckConstraint(
            'mezzanine >= 1 and mezzanine <= 2',
            name='check_mezz_number'
        ),
    )

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    _iceboard_pk = Column(Integer, ForeignKey('iceboards._pk'), index=True)

    # serial = Column(String) # Used by Graeme
    serial = Column(Integer) # Used by JFC
    mezzanine = Column(Integer)

    # # Since there are two "mezz" references per ICEBoard, the backreference
    # # has to be smart enough to accept either in the join.
    # iceboard = relationship(
    #     "IceBoard",
    #     uselist=False,
    #     primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    # )

    type = Column(String, nullable=False) # should this be equivalent to _cls?
    revision = Column(Integer)

    class FMCMezzanineException(Exception):
        pass

    def __init__(self, **kwargs):
        """ Create a new Mezzanine object from scratch and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('Creating instance for Mezzanine %r' % (self))

        super(FMCMezzanine, self).__init__(**kwargs) # allow the superclasses to initialize
        # self.set_handler(app_handler_name=self._cls, object_id=self._pk)

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self, **kwargs):
        """ Create an Mezzanine object from database and link it with its handler """
        self.logger = logging.getLogger(__name__)
        self.logger.info('Recreating instance from database for Mezzanine %r' % (self))
        # self.set_handler(app_handler_name=self._cls, object_id=self._pk)

    def init_handler(self):
        self.set_handler(app_handler_name=self._cls, object_id=self._pk)

    def eeprom_write(self, buf):
        '''Writes a collection of bytes to the internal EEPROM.

        Don't do this unless you're at McGill, and you're commissioning
        and testing a new mezzanine! This method makes it trivial to
        delete non-volatile data. Figuring out how to re-write the original
        data is a tougher nut to crack.

        According to FMC specs, the EEPROM is required to contain an
        IPMI FRU descriptor. If you want to insert this kind of data,
        you should use the 'ipmi_fru' module included in this Python
        repository.

        Since EEPROM contents are parsed by machine and used during
        board bring-up, it's important that the data you write is valid.
        You should refer to reference code (likely in the QC suite) rather
        than trying to guess what structures belong in here.
        '''

        import base64

        b64_string = base64.b64encode(buf)
        self.iceboard._mezzanine_eeprom_write_base64(
            self.mezzanine,
            b64_string,
            0
        )

    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self.iceboard.is_mezzanine_present(self.mezzanine)

class FMCMezzanineHandler(handler.Handler):
    """
    Defined a basic FMC Mezzanine Python handler.
    """
    __handler_for__ = FMCMezzanine
    __handler_name__= 'FMCMezzanine'

    def hwm_update(self, hwm_object):
        """ Import the main Mezzanine properties needed by the handler to operate the mezzanine.
        """
        self.motherboard = hwm_object.iceboard.handler
        self.mezzanine_number = hwm_object.mezzanine

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
