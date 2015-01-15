'''
Hardware mapper tests.

You must execute these tests from the top level:

    icecore$ nosetests

...in order to correctly locate the right code.

We construct two parent classes and two child classes as follows:

    DummyParentSubclass(125) => DummyChild(123)
    DummyParent(126)         => DummyChild(124)

We use this combination to test the following:

    * class inheritence (DummyParentSubclass derives from DummyParent)
    * relationships (DummyChild entries are associated with DummyParents)
    * parallel property accesses
    * parallel method dispatch
'''

from hardware_map import HardwareMap, HWMResource

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref

import unittest


# Create a dummy resource we can use for our tests
class DummyParent(HWMResource):
    __tablename__ = __name__ + 'dummy_parent'
    __table_args__ = (UniqueConstraint('cls', 'serial'), )
    __mapper_args__ = {'polymorphic_identity': 'base', 'polymorphic_on': 'cls'}

    child = relationship("DummyChild", uselist=False)
    child_pk = Column(Integer, ForeignKey('dummy_child.pk'), index=True)

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    serial = Column(Integer, nullable=False)


class DummyChild(HWMResource):
    __tablename__ = 'dummy_child'
    __table_args__ = (UniqueConstraint('cls', 'serial'), )
    __mapper_args__ = {'polymorphic_identity': 'base', 'polymorphic_on': 'cls'}

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    serial = Column(Integer, nullable=False)

    SOME_PROPERTY = "property of the underlying object"

    @property
    def negative_serial(self):
        return -self.serial

    def double_serial(self):
        return 2*self.serial

    def double_argument(self, arg):
        return 2*arg

class DummyParentSubclass(DummyParent):
    __mapper_args__ = {'polymorphic_identity': 'subclass'}
    extra_col = Column(String)


class InstantiationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls._hwm = HardwareMap()
        c1 = DummyChild(serial=123)
        c2 = DummyChild(serial=124)

        p1 = DummyParentSubclass(serial=125, extra_col='something', child=c1)
        p2 = DummyParent(serial=126, child=c2)

        cls._hwm.add_all([p1, p2])
        cls._hwm.commit()

    def test_parent_subclass(self):
        '''Testing if querying a subclass returns only subclasses'''
        s = self._hwm.query(DummyParentSubclass)
        assert s.count() == 1
        assert set(s.serial) == set([125])

    def test_parents(self):
        '''Testing if querying a class returns itself and its subclasses'''
        s = self._hwm.query(DummyParent)
        assert s.count() == 2
        assert set(s.serial) == set([125, 126])

    def test_children(self):
        '''Testing to see if we can access child classes'''
        s = self._hwm.query(DummyChild)
        assert s.count() == 2

        # properties from ORM columns
        assert set(s.serial) == set([123, 124])

        # ordinary properties defined in subclass
        assert set(s.SOME_PROPERTY) == set([DummyChild.SOME_PROPERTY])

        # properties defined with @property decorator
        assert set(s.negative_serial) == set([-123, -124])

        # method calls
        assert set(s.double_serial()) == set([2*123, 2*124])

        # method calls with arguments
        assert list(s.double_argument(3)) == [6, 6]

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
