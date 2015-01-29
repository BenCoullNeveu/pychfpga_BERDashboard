""" Base object for IceCrate (McGill Model MGK7BP).
"""

import sqlalchemy
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm import reconstructor, object_session, class_mapper
from sqlalchemy.orm.collections import attribute_mapped_collection

from . import hardware_map
from . import handler

class IceCrate(hardware_map.HWMResource, handler.HWMHandlerManager):
    __tablename__ = 'icecrates'
    __table_args__ = (
        UniqueConstraint('serial'),
    )
    __mapper_args__ = {
        'polymorphic_on': '_cls',
        'polymorphic_identity': 'MGK7BP'
    }

    _pk = Column(Integer, primary_key=True)
    _cls = Column(String, nullable=False)
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
        # *** JFC changed temporarily for slot_number
        collection_class=attribute_mapped_collection('slot_number'),
        doc="The IceCrate's IceBoards, indexed as you would expect.")

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self.serial)

    def init_handler(self):
        """ Create or re-attach a handler to this HWM object.
        """
        self.set_handler(object_id=self._pk, handler_name=self._cls)


class IceCrateHandler(handler.Handler):
    """
    Basic Python handler for the IceCrate.
    """

    # The following attributes must be redefined in every subclasses
    __handler_for__ = IceCrate
    # Icecrate handlers are identified by polymorphic name
    __handler_name__ = IceCrate.__mapper__.polymorphic_identity

    serial_number = None
    iceboards = []

    def __init__(self, **kwargs):
        super(IceCrateHandler, self).__init__(**kwargs)

    def __repr__(self):
        return '%s (handler for %r SN%s)' % (self.__class__.__name__,
                                             self.__handler_for__.__name__,
                                             self.serial_number)

    def hwm_update(self, hwm_object):
        """Is called when the Hardware Map object might have changed to reflect
        those changes in the handler.
        """
        super(IceCrateHandler, self).hwm_update(hwm_object)
        self.logger.info('%r: hwm_update()' % (self))
        self.serial_number = hwm_object.serial
        self.iceboards = dict(hwm_object.slot)
        self.logger.info(' %r.hwm_update(): slots have %r' %
                         (self, self.iceboards))
        self.master_iceboard = self.get_master_iceboard()

    def get_master_iceboard(self):
        """ Return the IceBoard handler that is designated to talk to the
        backplane.
        """
        if self.iceboards:
            # Just return the IceBoard in the lowest slot number
            return sorted(self.iceboards.items())[0][1]
        else:
            return None
# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
