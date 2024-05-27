"""
Objects for Dfmux Experiments
=============================
"""

__all__ = [
    "IceBoard",
    "IceCrate",
    "Dfmux",
    "FMCMezzanine",
    "FMCDAQ2",
    "ReadoutModule",
    "ReadoutChannel",
]

from .hardware_map import HWMResource, HWMQuery
from .schema import IceCrate, IceBoard, FMCMezzanine
from .session import HWMConstructor

from sqlalchemy import Column, ForeignKey, Integer, String, Float
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import attribute_mapped_collection

from . import tuber, session
import sys


class YAMLLoader(session.YAMLLoader):

    # This is the default flavour
    flavour = sys.modules[__name__]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Plumbing
        self.add_constructor(u"!flavour", yaml_flavour_constructor)

        # Readout chain
        self.add_constructor(
            u"!IceCrate",
            HWMConstructor(
                lambda loader: getattr(loader.flavour, "IceCrate"),
                AttributeMappingTouchup("slots", "slot"),
            ),
        )

        self.add_constructor(
            u"!Dfmux",
            HWMConstructor(
                lambda loader: getattr(loader.flavour, "Dfmux"),
                AttributeMappingTouchup("mezzanines", "mezzanine"),
            ),
        )

        self.add_constructor(
            u"!FMCDAQ2",
            HWMConstructor(
                lambda loader: getattr(loader.flavour, "FMCDAQ2"),
                AttributeMappingTouchup("modules", "module"),
            ),
        )

        self.add_constructor(
            u"!ReadoutModule",
            HWMConstructor(
                lambda loader: getattr(loader.flavour, "ReadoutModule"),
                AttributeMappingTouchup("channels", "channel"),
            ),
        )

        self.add_constructor(
            u"!ReadoutChannel",
            HWMConstructor(lambda loader: getattr(loader.flavour, "ReadoutChannel")),
        )


class Dfmux(IceBoard):
    """An IceBoard running Dfmux firmware."""

    __mapper_args__ = {"polymorphic_identity": __package__}

    def __init__(self, *args, **kwargs):
        # If no mezzanines are specified, default to 1 FMCDAQ2.
        if "mezzanine" not in kwargs and "mezzanines" not in kwargs:
            kwargs["mezzanines"] = [FMCDAQ2(mezzanine=1)]

        super().__init__(*args, **kwargs)


class FMCDAQ2(FMCMezzanine):
    """An FMC mezzanine for subclass for the FMCDAQ2 Mezzanine."""

    __mapper_args__ = {"polymorphic_identity": "FMCDAQ2"}

    def __init__(self, *args, **kwargs):
        if "module" not in kwargs and "modules" not in kwargs:
            self.modules = [ReadoutModule(module=m + 1) for m in range(1)]

        super().__init__(*args, **kwargs)

    module = relationship(
        "ReadoutModule",
        backref=backref("mezzanine"),
        collection_class=attribute_mapped_collection("module"),
        doc="""Readout modules associated with this mezzanine.

            You can use these modules to write more legible function calls.
            For example, the following two calls are equivalent::

                >>> x = d.get_fast_samples(100, d.UNITS.ADC_COUNTS,
                ...                        average=False,
                ...                        target=d.TARGET.DEMOD,
                ...                        module=1,
                ...                        mezzanine=1)

                >>> mod = d.mezzanine[1].module[1]
                >>> mod.get_fast_samples(100, d.UNITS.ADC_COUNTS,
                ...                      average=False,
                ...                      target=d.TARGET.DEMOD)

            When writing Python code that involves multiple operations in
            sequence to a single hardware element, the second form is often
            much clearer.""",
    )

    modules = relationship(
        "ReadoutModule",
        lazy="dynamic",
        query_class=HWMQuery,
        doc="This is a SQLAlchemy subquery; you probably want 'module'",
    )


@tuber.TuberCategory(
    "ReadoutModule",
    lambda m: m.iceboard,
    module=lambda m: m.module,
    mezzanine=lambda m: m.mezzanine.mezzanine,
)
class ReadoutModule(HWMResource):
    """ReadoutModule provides a home for module-scope Dfmux functions."""

    __tablename__ = "readout_modules"
    __mapper_args__ = {"polymorphic_identity": __package__, "polymorphic_on": "_cls"}

    def __init__(self, *args, **kwargs):
        if "channel" not in kwargs and "channels" not in kwargs:
            kwargs["channels"] = [ReadoutChannel(channel=c + 1) for c in range(64)]

        super().__init__(*args, **kwargs)

    def __repr__(self):
        return "%r.%s(%r)" % (self.mezzanine, self.__class__.__name__, self.module)

    # Boilerplate
    _cls = Column(String, nullable=False)
    _pk = Column(Integer, primary_key=True)
    _mezz_pk = Column(Integer, ForeignKey("fmc_mezzanines._pk"), index=True)

    module = Column(Integer, index=True, doc="Module number (1-4)")

    channel = relationship(
        "ReadoutChannel",
        backref=backref("module"),
        collection_class=attribute_mapped_collection("channel"),
        doc="""Readout channels (indexed 1-4) associated with this module.

            You can use these modules to write more legible function calls.
            For example, the following two calls are equivalent::

                >>> x = d.get_frequency(d.UNITS.HZ, d.TARGET.DEMOD,
                ...                        channel=1,
                ...                        module=1,
                ...                        mezzanine=1)

                >>> c = d.mezzanine[1].module[1].channel[1]
                >>> c.get_frequency(d.UNITS.HZ, d.TARGET.DEMOD)

            When writing Python code that involves multiple operations in
            sequence to a single hardware element, the second form is often
            much clearer.""",
    )

    channels = relationship(
        "ReadoutChannel",
        lazy="dynamic",
        query_class=HWMQuery,
        doc="This is a SQLAlchemy subquery; you probably want 'channel'",
    )

    # HWM shortcuts
    iceboard = property(lambda x: x.mezzanine.iceboard if x.mezzanine else None)


@tuber.TuberCategory(
    "ReadoutChannel",
    lambda c: c.iceboard,
    mezzanine=lambda c: c.module.mezzanine.mezzanine,
    module=lambda c: c.module.module,
    channel=lambda c: c.channel,
)
class ReadoutChannel(HWMResource):
    """ReadoutChannel provides a home for channel-scope Dfmux functions."""

    __tablename__ = "readout_channels"
    __mapper_args__ = {"polymorphic_identity": __package__, "polymorphic_on": "_cls"}

    def __repr__(self):
        return "%r.%s(%r)" % (self.module, self.__class__.__name__, self.channel)

    # Boilerplate
    _cls = Column(String, nullable=False)
    _pk = Column(Integer, primary_key=True)
    _mod_pk = Column(Integer, ForeignKey("readout_modules._pk"), index=True)

    channel = Column(Integer, index=True, doc="Channel number (1-64)")

    frequency = Column(
        Float,
        doc="DAN frequency. Used for unmapped channels, "
        "e.g. for nulling crosstalk lines.  For normal frequencies "
        "assigned to cryogenic components, use LCChannel.frequency",
    )

    iceboard = property(
        lambda x: x.module.iceboard if x.module else None,
        doc="Shortcut back to the IceBoard",
    )

    mezzanine = property(
        lambda x: x.module.mezzanine if x.module else None,
        doc="Shortcut back to the mezzanine",
    )


def yaml_flavour_constructor(loader, node):
    """!flavour tag for YAML.

    This tag must occur within a HardwareMap directive. Note that it's
    swallowed by the HardwareMap, which ignores its children after
    instantiating them.  (The children add themselves in their instantiation
    methods.)
    """

    name = loader.construct_scalar(node)
    __import__(name)

    flavour = loader.flavour = sys.modules[name]

    if hasattr(flavour, "yaml_hook"):
        loader.register_finalization_hook(flavour.yaml_hook)

    return sys.modules[name]


class AttributeMappingTouchup:
    """Correctly assign indexes for SQLAlchemy attribute_mapped_collections.

    HWM objects like FMCMezzanines come with index columns like "mezzanine",
    which indicate their position in a collection (dfmux.mezzanines) starting
    from 1. This idiom is convenient in ORM-land, but awkward to support in
    YAML serialization. For example, we would have:

        # BROKEN EXAMPLE
        !Dfmux
            hostname: iceboard004.local
            mezzanines: [ !MGMEZZ04 { serial: FMC2_001, mezzanine: 2 } ]

    The mezzanine number is not really a property of the mezzanine itself --
    and it's even more awkward when mezzanines are stored separately from their
    dfmuxes and referred by alias:

        # BROKEN EXAMPLE
        - &foo_mezz !MGMEZZ04 { serial: FMC2_001, mezzanine: 2 }
        - !Dfmux
            hostname: iceboard004.local
            mezzanines: [ *foo_mezz ]

    Instead, this touchup allows us to express mezzanines as ordinary lists:

        !Dfmux
            hostname: iceboard004.local
            mezzanines: [ None, !MGMEZZ04 { serial: FMC2_001 } ]

    ...or as a mapping:

        !Dfmux
            hostname: iceboard004.local
            mezzanines:
                2: !MGMEZZ04 { serial: FMC2_001 }
    """

    def __init__(self, group_attribute, member_attribute):
        self._group_attribute = group_attribute
        self._member_attribute = member_attribute

    def __call__(self, loader, mapping):

        if self._group_attribute in mapping:
            values = mapping[self._group_attribute]

            if isinstance(values, list):
                # We've been provided a list. Start numbering at 1.
                for (index, value) in enumerate(values):
                    if not value:
                        continue

                    # Don't clobber an existing numbering.
                    if getattr(value, self._member_attribute) is not None:
                        continue

                    setattr(value, self._member_attribute, index + 1)

                mapping[self._group_attribute] = [v for v in values if v]

            elif isinstance(values, dict):
                # We've been provided a dictionary. Assume the keys
                # provide the numbering.
                for (key, value) in values.items():
                    if not value:
                        continue
                    setattr(value, self._member_attribute, key)

                mapping[self._group_attribute] = [v for v in values.values() if v]

            else:
                raise TypeError("Expected a list, got '%r'!" % values)


# Tell session to use our YAMLLoader.
session.set_yaml_loader_class(YAMLLoader)

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
