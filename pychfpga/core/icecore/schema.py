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

from . import hardware_map, tuber, tworoutine

from .hw import ipmi_fru

import datetime
import base64
import asyncio


@tuber.TuberCategory("Backplane", lambda b: b.slots.first())
class IceCrate(hardware_map.HWMResource):
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

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.serial)


class IceBoard(hardware_map.HWMResource, tuber.TuberObject):
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

    def __repr__(self):
        return "%r.%s(%s)" % (
            self.crate,
            self.__class__.__name__,
            "slot=%s" % self.slot
            if self.crate
            else "serial=%s" % self.serial
            if self.serial
            else "hostname=%s" % self.hostname,
        )

    def set_fpga_bitstream(self, buf):
        """
        Configures the FPGA with the specified buffer.

        The buffer is an ordinary string object or similar, and
        contains an already loaded .BIT or .BIN file.
        """
        b64_string = base64.b64encode(buf)
        self._set_fpga_bitstream_base64(b64_string)

    def _eeprom_write_ipmi(self, part_number, serial_number, product_version):
        """Write IPMI-formatted EEPROM for IceBoards.

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
        """

        fru = ipmi_fru.FRU(
            board=ipmi_fru.Board(
                mfg_date=datetime.datetime.now(),
                manufacturer="Winterland",
                product_name="IceBoard",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=ipmi_fru.Product(
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
        b64_string = base64.b64encode(fru.encode())
        return self._motherboard_eeprom_write_base64(b64_string)

    def _backplane_eeprom_write_ipmi(self, part_number, serial_number, product_version):
        """Write IPMI-formatted EEPROM for IceCrates.

        These fields are read back and parsed by software, so you have
        to get them right or things will misbehave. This method currently
        expects the following formatting:

        >>> m._backplane_eeprom_write_ipmi(
        ...     part_number="MGK7BP",
        ...     serial_number="001",
        ...     product_version="00")

        DON'T fill incorrect values unless they're visibly incorrect,
        since this data tends to be useful when debugging physical
        problems (e.g. tracing board history). Incorrect data that
        pretends to be valid can make this kind of debugging very painful.

        This method is attached to an IceBoard instead of an IceCrate since
        you can't properly address an IceCrate unless its EEPROM has already
        been programmed. Chickens and eggs.
        """

        fru = ipmi_fru.FRU(
            board=ipmi_fru.Board(
                mfg_date=datetime.datetime.now(),
                manufacturer="Winterland",
                product_name="IceCrate",
                part_number=part_number,
                serial_number=serial_number,
                fru_file="",
            ),
            product=ipmi_fru.Product(
                manufacturer="Winterland",
                product_name="IceCrate",
                part_number=part_number,
                product_version=product_version,
                serial_number=serial_number,
                asset_tag="",
                fru_file="",
            ),
            # multi=Multi(...), when it's supported by this code
        )
        b64_string = base64.b64encode(fru.encode())
        return self._backplane_eeprom_write_base64(b64_string)

    @property
    def tuber_uri(self):
        """Smarter, IceBoard-aware tuber_uri.

        The version of 'tuber_uri' in tuber.py doesn't know about calculating
        hostnames from serials, for instance.
        """

        if self.hostname:
            # We have a hostname; just use it.
            return "http://{}/tuber".format(self.hostname)

        if self.serial:
            # We have a serial number; compute the hostname.
            return "http://iceboard{}.local/tuber".format(self.serial)

        if self.slot and self.crate:
            # We have a slot and crate,
            # we can use the crate-based hostname (i.e. slot3.crate001.local).
            return "http://slot{0}.icecrate{1}.local/tuber".format(
                self.slot, self.crate.serial
            )

        raise NameError(
            "Couldn't figure out a Tuber URI for this object! "
            "I need serial or crate information."
        )

    @tworoutine.tworoutine
    async def resolve(self):
        await (~self._tuber_get_meta)()

@tuber.TuberCategory("Mezzanine", lambda m: m.iceboard, mezzanine=lambda m: m.mezzanine)
class FMCMezzanine(hardware_map.HWMResource):
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

    def __repr__(self):
        return "%r.%s(%r,%r)" % (
            self.iceboard,
            self.__class__.__name__,
            self.mezzanine,
            self.serial,
        )

    def eeprom_write(self, buf):
        """Writes a collection of bytes to the internal EEPROM.

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
        """
        b64_string = base64.b64encode(buf)
        self.iceboard._mezzanine_eeprom_write_base64(self.mezzanine, b64_string, 0)


@hardware_map.algorithm(IceBoard, register=True)
async def resolve(boards):
    await asyncio.gather(*[(~ib.resolve)() for ib in boards])

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
