"""FMC Mezzanine schema object."""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref

from hardware_map import HWMResource

import iceboard

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
    iceboard = relationship(
        "IceBoard",
        uselist=False,
        primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    )

    pk = Column(Integer, primary_key=True)

    cls = Column(String, nullable=False)
    type = Column(String, nullable=False)
    serial = Column(Integer, nullable=False)

    revision = Column(Integer)

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
