"""Base object for IceBoard objects.

To specialize an IceBoard object for a particular experiment, you're
encouraged to create a subclass. There should be good examples
available.
"""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from .hardware_map import Boolean
from .hardware_assets import IceCrateBase, IceBoardBase, FMCMezzanineBase

from . import hardware_map, tuber, tworoutine

from .hw import ipmi_fru

import asyncio


@tuber.TuberCategory("Backplane", lambda b: b.slots.first())
class IceCrate(IceCrateBase, hardware_map.HWMResource):
    __tablename__ = "icecrates"
    __table_args__ = (UniqueConstraint("serial"),)
    __mapper_args__ = {"polymorphic_identity": __package__}

    _pk = Column(Integer, primary_key=True)
    serial = Column(String, doc="The serial number written on the board (verbatim!)")

    slots = relationship(
        "IceBoard",
        lazy="dynamic",
        query_class=hardware_map.HWMQuery,
        doc="""A SQLAlchemy subquery corresponding to this IceCrate's
            IceBoards. If you want to index this array using slot index,
            you should use 'iceboard' instead.""",
    )

    slot = relationship(
        "IceBoard",
        backref=backref("crate"),
        collection_class=attribute_mapped_collection("slot"),
        doc="The IceCrate's IceBoards, indexed as you would expect.",
    )


class IceBoard(IceBoardBase, hardware_map.HWMResource):
    __tablename__ = "iceboards"
    __table_args__ = (UniqueConstraint("serial"),)
    __mapper_args__ = {"polymorphic_identity": "IceBoard", "polymorphic_on": "_cls"}

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    _icecrate_pk = Column(Integer, ForeignKey("icecrates._pk"), index=True)

    hostname = Column(String, doc="The hostname (or IP) to use for this resource.")
    serial = Column(String, doc="The serial number written on the board (verbatim!)")
    slot = Column(Integer, doc="The IceCrate slot occupied by this board")

    backplane_serial = Column(
        String, doc="The serial number of IceCrate occupied by this board"
    )

    online = Column(Boolean, default=True)

    mezzanines = relationship(
        "FMCMezzanine",
        lazy="dynamic",
        query_class=hardware_map.HWMQuery,
        doc="""A SQLAlchemy subquery corresponding to this IceBoard's
            mezzanines. If you want to index this array using logical
            keys (1 or 2), you should use 'mezzanine' instead.""",
    )

    mezzanine = relationship(
        "FMCMezzanine",
        backref=backref("iceboard"),
        collection_class=attribute_mapped_collection("mezzanine"),
        doc="""The IceBoard's mezzanines, indexed as you would expect
            (1 for mezzanine A, 2 for mezzanine B).""",
    )


@tuber.TuberCategory("Mezzanine", lambda m: m.iceboard, mezzanine=lambda m: m.mezzanine)
class FMCMezzanine(FMCMezzanineBase, hardware_map.HWMResource):
    """FMC Mezzanine schema object.

    This is an abstract class. To specialize it for a particular FMC
    mezzanine, create a subclass. There should be some good examples
    to borrow from; you should refer to them rather than this code.
    """

    __tablename__ = "fmc_mezzanines"
    __mapper_args__ = {
        "polymorphic_identity": "fmc_mezzanine",
        "polymorphic_on": "_cls",
    }
    __table_args__ = (
        CheckConstraint("mezzanine >= 1 and mezzanine <= 2", name="check_mezz_number"),
    )

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
    _iceboard_pk = Column(Integer, ForeignKey("iceboards._pk"), index=True)

    serial = Column(String)
    mezzanine = Column(Integer)


@hardware_map.algorithm(IceBoard, register=True)
async def resolve(boards):
    await asyncio.gather(*[(~ib.resolve)() for ib in boards])

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
