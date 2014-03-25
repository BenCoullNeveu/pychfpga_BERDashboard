"""Base schema for McGill hardware.

You are strongly encouraged to use this framework for additional hardware. For
example:

   * An IceBoard committed to a particular purpose should be a subclass.
     (See, for example, the dfmux schema in "schema_dfmux.py".)

   * An entirely new kind of asset (e.g. a cable, a network switch, or a power
     supply) should be a new class deriving from HWMResource.

HWMResource is a subclass of the SQLAlchemy "declarative_base()" object. You
are encouraged to consult their documentation for details.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref

from hardware_map import HWMResource
from tuber import TuberHWMResource

class IceBoard(TuberHWMResource):
    __tablename__ = 'iceboards'
    __table_args__ = (
        UniqueConstraint('serial'),
    )
    __mapper_args__ = {
            'polymorphic_identity': 'iceboard',
            'polymorphic_on': 'cls'
    }

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)

    # Set up explicit mezz1 / mezz2 links.
    mezz1_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz1 = relationship("FMCMezzanine", foreign_keys=[mezz1_pk])

    mezz2_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz2 = relationship("FMCMezzanine", foreign_keys=[mezz2_pk])

    # Although we've already catalogued the mezz linkages, it's sometimes
    # useful to use an array. (For example, it lets us trivially write
    # join() calls in HWM queries.)
    mezz = relationship("FMCMezzanine",
        uselist=True,
        primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    )

    serial = Column(Integer)
    revision = Column(Integer)

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
