"""Hardware mapper.

This HardwareMapper actually returns a SQLAlchemy session object, which we've
extended slightly. Here is a sample session that creates a couple of new
hardware map entries:

    >>> sqc = SQUIDController(serial=123, type="MGNGSQC01")
    >>> mezz = DfmuxMezzanine(serial=234, type="MGMEZZ04", sqc=sqc)
    >>> d = Dfmux(serial=345, revision=1, mezz1=mezz)

We'll create an empty hardware map (instead of loading one, for now) and add
our elements to it:

    >>> hwm = HardwareMap()
    >>> hwm.add(d)

Since the iceboard object references the other two, we don't need to add them
explicitly.

You can now query a particular element in the hardware map:

    >>> ds = hwm.query(Dfmux)

You can ask them questions in bulk:

    >>> ds.get_frequency(...)
    (1.23e6, 2.34e6, 3.45e6)

Note that these calls were dispatched in parallel (multi-threaded), so this is
much faster than the equivalent Python code:

    >>> print [ d.get_frequency(...) for d in ds ]
    [1.23e6, 2.34e6, 3.45e6]

You can retrieve a single IceBoard, and interact with its properties
(including the structures it links with):

    >>> d = hwm.query(IceBoard).filter_by(serial=345).first()
    >>> print ib.get_frequency(...)
    1.23e6
    >>> m = ib.mezz1
    >>> print m.type
    U'MGMEZZ04'

...et cetera. Beneath the hood, the query language is provided by SQLAlchemy,
which allows rich queries and handles object mapping for us. It's slick, and
it's code we don't have to write or maintain.

TODO: Turn "echo" on when instantiating the HardwareMapper and see how many
SQL queries are generated -- lots. It is probably worth playing with
SQLAlchemy's "eager" options and ensuring there are indices on the right
columns.
"""

__all__ = [
    "Base", "HWMQueryException",
    "HWMQuery", "HWMResource",
    "macro", "algorithm", "HardwareMap",
    "Boolean",
    "Session",
    "set_session_class",
]

import tornado.gen
import tornado.ioloop

import functools
import collections
import time
import logging
from collections import OrderedDict

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.ext.declarative
import sqlalchemy.types

from . import tuber

Base = sqlalchemy.ext.declarative.declarative_base()


class HWMQueryException(Exception):
    pass


class HWMQuery(sqlalchemy.orm.Query):
    '''HWMQuery object: A parallel-call extension to Query objects.

    This is also pretty well internal; you shouldn't have to use it directly.
    Please look at the DocStrings for HardwareMap instead.

    This is an extension to SQLAlchemy's Query object. A HWMQuery can be
    used to dispatch method calls on every class it contains.
    '''

    _algorithm_registry = {}

    def __getattr__(self, name):
        '''Teach a collection of query results how to parallelize.

        You would ordinarily retrieve a bunch of query results as
        follows (assuming "serial" is some property of the underlying
        object):

            >>> objects = hwm.query(ObjectClass)
            >>> for o in objects:
            ...     o.do_something()

        Since objects like "o" tend to be network resources, and calls
        like "o.do_something()" tend to be I/O-limited, we are
        interested in running this kind of function call in a
        multi-threaded context. We use green threads to avoid the
        overhead from threading -- which seems minimal, until we pile
        on the SQLAlchemy housekeeping that's required.

        This call allows you to do exactly that, as follows:

            >>> objects.do_something()

        It does so by trapping calls it doesn't recognize itself, and
        delegating them to each object in the Query results. It returns
        an array of results corresponding to each underlying object.
        '''

        # Since this is a SQLAlchemy "Query" subclass, we can use it
        # as a collection and call things like "count()" on it.

        # Refuse to parallellize access to special names
        if name in ('_orm_only_adapt', '_calls'):
            raise AttributeError()

        # First, try algorithms from the registry.
        for (cls, algs) in self._algorithm_registry.iteritems():
            if not issubclass(self.column_descriptions[0]['type'], cls):
                continue
            for a in algs:
                if name == a.__name__:
                    @functools.wraps(a)
                    def alg(*args, **kwargs):
                        return a(self, *args, **kwargs)
                    return alg

        # Next, try attributes/methods from contained objects.
        # Special case: if the query returned no results, we can't reliably
        # ask it for attributes. Treat this as an error (we can sometimes
        # do the right thing, but not always.)
        if self.count() == 0:
            raise AttributeError("Can't request attribute '%s' from a Query "
                                 "with no results!" % name)

        # Generate an exception of only some of the objects have the
        # desired attribute. (If none of the objects have the attribute,
        # we want to raise the ordinary Python AttributeError. This
        # happens below.)
        attr_present = [hasattr(obj, name) for obj in self]
        if not any(attr_present):
            raise AttributeError(
                "Attribute '%s' does not exist on any element "
                "of the query" % name)
        elif not all(attr_present):
            raise AttributeError(
                "Attribute '%s' does not exist on *ALL* elements "
                "of the query" % name)

        # Get the specified attribute from all objects.
        attrs = [getattr(x, name) for x in self]

        return HWMQueryAttributes(attrs)

    def __dir__(self):
        """Retrieve a list of interesting attributes."""

        # ***JFC: This original following line just returns the dir of a super
        # object, which is not the dir of a Query object.
        # s = set(dir(super(HWMQuery, self)))

        # Get instance attributes
        # Add class attributes from all classes in the MRO
        # Add methods/propertiescommon to all query objects
        s = set(self.__dict__.keys()) | \
            set.union(*[set(dir(cls)) for cls in type(self).mro()]) | \
            set.intersection(*[set(dir(obj)) for obj in self])

        # Add algorithms from the registry.
        for (cls, algs) in self._algorithm_registry.iteritems():
            if issubclass(self.column_descriptions[0]['type'], cls):
                s.update([a.__name__ for a in algs])

        return [str(item) for item in s]  # Remove unicode stings

    def call_with(self, func, *args, **kwargs):
        """Call some function across a collection of Query results.

        if 'func' possess the variable '_hwm_call_with_outer', that function
        is called with the whole HWMQuery passed as its first argument
        followed by the *args and **kwargs (as if 'func' was an unbound method
        of the HWMQuery object)

        Otherwise, the function is treated as an unbound method and will be
        concurrently called for each instance of the Query results by passing
        it that instance as its first argument, followed by the common
        arguments *args and **kwargs (as if 'func' was an unbound method of
        the objects selected by the query).

        Let's say you want to do "something" with a set of Query results:

            >>> [do_something(r, foo, bar) for r in results]

        ...but you'd like to parallelize the call (i.e. run it in a
        multi-threaded context.) Using this function, you can do so as
        follows:

            >>> results.call_with(do_something, foo, bar)
        """
        # If 'func' is smart enough not to want a parallelized call, obey it.
        if hasattr(func, '_hwm_call_with_outer'):
            return func(self, *args, **kwargs)

        return concurrent_call([func] * self.count(), self, *args, **kwargs)

    def as_dict(self, keys=None, convert_fn=None):
        """
        Returns the query results as a dictionary-like HMWQueryAttribute
        object which is indexed with the specified keys. The collection can be
        used the same way as a HWMQuery, except that the results are will be
        indexed by the specified keys.

        if 'keys' is an Instrumented Attribute, the dictionary will be indexed
        by the value of this attribute. If convert_fn is specified, the
        attribute values will be converted using that function.

        If 'keys' is a iterable, the values of 'keys' are used directly as an
        index.

        If the keys parameter is omitted or evaluates as False, the objects are
        indexed from 0 to len(x)-1 and the returned collection will behave
        similarly to a list or tuple.

        if 'convert_fn' is specified, the key values are passed through the
        specified function before being passed to the HWMQueryAttributes
        object. Note: once the object is converted to a HWMQueryAttribute,
        query operations can no longer be performed, and the collection will
        no longer track database changes.

        Example:
            >>> d = ca.query(IceBoard).as_dict(IceBoard.serial_number, int)
            >>> d[7] # returns the iceboard with serial number 7
        """
        if isinstance(keys, sqlalchemy.orm.attributes.InstrumentedAttribute):
            keys = [key[0] for key in self.values(keys)]
            if convert_fn:
                keys = [convert_fn(key) for key in keys]
        return HWMQueryAttributes(self, keys)


class HWMQueryAttributes(object):
    """
    Class representing a collection of objects that can be accessed and/or
    called concurrently at any level in a hierarchy of objects. This enable
    concurrent access in object-oriented programs.

    The collection is stored as a mapping, and is populated with the elements
    of the iterable 'objects' using the keys provided in 'keys'. If 'keys' is
    None, the keys are integers from 0 to len(objects)-1 to mimic a list.

    The mapping operates like an ordered dictionary and offers the same methods
    (.items(), .keys(), __len__() etc...) with the exception that the mapping
    itself returns an iterable to the objects, not their keys. This behavior is
    consistent with a HWMQuery object.

    Calling the mapping will concurrently call every object with the provided
    arguments and will return the result in another HWMQueryAttributes with
    identical keys.

    Accessing an attribute of the mapping will return a new HWMQueryAttribute
    containing the that attribute for each of the element of the mapping.

    Indexing the mapping will return the object with the corresponding key.
    Slices are not supported.

    Calling .getitem(index) on the array will return another mapping where each
    element was indexed with index.

    As a convenience, the object masquerade as the first element of its
    collection if that object is callable, and therefore inherits its docstring
    and call signature, which allows ipython to provide useful hilts during
    interactive sessions.

    Examples:

    >>> class Obj(object):
    >>>     def __init__(self, x): self.x = x
    >>>     def fn(self, y): return (self.x,y)
    >>>     z=5
    >>>
    >>> coll = HWMQueryAttributes([Obj(1), Obj(2), Obj(3), Obj(4)])
    >>> print coll[3]
    >>> <__main__.Obj object at 0x000000000BF68320>
    >>> print list(coll)
    [<__main__.Obj object at 0x000000000BF68278>, <__main__.Obj object at 0x000000000BF682B0>, <__main__.Obj object at 0x000000000BF682E8>, <__main__.Obj object at 0x000000000BF68320>]
    >>> print list(coll.z)
    [5, 5, 5, 5]
    >>> t1 = coll.fn(10)
    >>> print list(t1)
    [(1, 10), (2, 10), (3, 10), (4, 10)]
    >>> t1[3]
    (4, 10)
    >>> print list(t1.getitem(1))
    [10, 10, 10, 10]
    """

    # We define those so __setattr__ does not try to send them to objects
    # during __init__.
    _has_keys = None
    _proto = None
    _dict = None
    logger = None

    def __init__(self, objects, keys=None):
        # Do not define a docstring here: for some reason ipython will use it
        # instead of the dynamic __doc__ defined below.
        self.logger = logging.getLogger(__name__)
        self._has_keys = bool(keys)
        object_list = list(objects)  # in case object = generator or HWMQuery
        # Get the object that this class will mimic
        self._proto = object_list[0] if object_list else None
        self._dict = OrderedDict(
            zip(keys or range(len(object_list)), object_list))

    def __repr__(self):
        if self._has_keys:
            return '%s containing:\n{%s}' % (
                type(self).__name__,
                ',\n'.join('%s:%r' % (key, value) for
                           (key, value) in self.items())
                )
        else:
            return '%s containing:\n[%s]' % (
                type(self).__name__,
                ',\n'.join(['%r' % value for value in self])
                )

    def __dir__(self):
        """Retrieve a list of interesting attributes."""
        s = (set(self.__dict__.keys()) |
             set.union(*[set(dir(cls)) for cls in type(self).mro()]) |
             set.intersection(*[set(dir(obj)) for obj in self]))
        return [str(item) for item in s]

    # Copy the main attributes of _proto so this class can masquerade as it.
    __doc__ = property(lambda self: self._proto.__doc__)
    __class__ = property(lambda self: self._proto.__class__)
    __name__ = property(lambda self: self._proto.__name__)
    im_func = property(lambda self: self._proto.im_func)
    func_code = property(lambda self: self._proto.func_code)
    func_defaults = property(lambda self: self._proto.func_defaults)

    # Offer a subset of OrderedDict methods. We could just have inherited dict,
    # but methods that change the dict would have been available, and it is
    # also tricky to redefine __iter__
    def __iter__(self): return self._dict.itervalues()
    def __len__(self): return self._dict.__len__()
    def __reversed__(self): return self._dict.__reversed__()
    def items(self): return self._dict.items()
    def iteritems(self): return self._dict.iteritems()
    def keys(self): return self._dict.keys()
    def iterkeys(self): return self._dict.iterkeys()
    def values(self): return self._dict.values()
    def itervalues(self): return self._dict.itervalues()
    def __getitem__(self, index): return self._dict.__getitem__(index)

    def __call__(self, *args, **kwargs):
        """ Concurrently calls every element of the collection with the
        provided arguments, and resurn the results in a new HWMQueryAttributes
        object.

        It is assumed that we have either functions or already bound methods,
        so we don't have to pass those an object-specific parameter.
        """
        results = concurrent_call(self.values(), None, *args, **kwargs)
        return HWMQueryAttributes(results,
                                  self._has_keys and self._dict.keys())

    def getitem(self, index):
        return self.__getattr__('__getitem__')(index)

    def __getattr__(self, name):
        """Return a collection of attribute 'name' from each of the current
        objects.
        """
        if not self:
            raise AttributeError("There are no objects in the list")
        self._check_collection_attributes(name)
        return HWMQueryAttributes(
            [getattr(obj, name) for obj in self],
            self._has_keys and self._dict.keys())

    def __setattr__(self, name, value):
        """ Sets a value on a collection of objects.
        """
        try:
            object.__getattribute__(self, name)  # check is attribute exists
            return object.__setattr__(self, name, value)
        except AttributeError:  # if attributes does not exist
            if self._dict:  # 'for obj in self' will call _dict.__len__()
                self._check_collection_attributes(name)
                for obj in self:
                    setattr(obj, name, value)

    def _check_collection_attributes(self, name):
        """ Checks if all members of the collection has the specified
        attribute name, otherwise raise an exception"""
        attr_present = [hasattr(obj, name) for obj in self]
        if not any(attr_present):
            raise AttributeError("Attribute %s does not exist on any element "
                                 "of the current results" % name)
        elif not all(attr_present):
            raise AttributeError("Attribute %s must exist on all elements "
                                 "of the current results" % name)


def concurrent_call(func_list, variable_arg_list, *args, **kwargs):
    """ Concurrently call all functions or methods listed in 'func_list'. If
    'variable_arg_list' is not none, each function will be called with its
    first argument taken from the corresponding element in that list.
    Position- and keyword arguments common to all calls can also be passed.
    """

    if variable_arg_list is not None:
        func_list = [functools.partial(func, arg) for (func, arg)
                     in zip(func_list, variable_arg_list)]

    # If the underlying calls can be parallelized using a Tornado IO
    # loop, do so. Because we use call_sync, we create a new IOLoop
    # instance to contain the execution.
    if all([isinstance(f, tuber.Parallelizable) for f in func_list]):
        old_loop = tornado.ioloop.IOLoop.current()
        io_loop = tornado.ioloop.IOLoop()
        io_loop.make_current()
        fs = [f.__call_async__(io_loop, *args, **kwargs)
              for f in func_list]
        io_loop.run_sync(tornado.gen.coroutine(lambda: (yield fs)))
        old_loop.make_current()
        return [f.result() for f in fs]
    else:
        # Otherwise, fall back on a looped invocation.
        return [f(*args, **kwargs) for f in func_list]


class HWMResource(Base):
    '''Base class for Hardware Mapper resources to share.

    You should inherit from this class in order to create a Hardware-Mapped
    resource. It's declared for convenience, since "Base" is an instantiated
    class (see the top of this file.)
    '''
    __abstract__ = True

    @property
    def hwm(self):
        '''Retrieve the :class:`HardwareMap` that stores this object.'''
        return sqlalchemy.orm.object_session(self)

    def self_getter(self):
        """ Returns a getter function that returns a reference to the current ORM
        object. This function can safely be called anytime from anywhere to
        access this ORM object. The object will be loaded from the database if
        it is not already in memory.
        """
        keys = sqlalchemy.orm.object_mapper(self).primary_key_from_instance(self)
        session = sqlalchemy.orm.object_session(self)
        if all(keys) and session is not None:
            query = session.query(type(self))
            return lambda: query.get(keys)  # Closure: closes on query and keys
        raise RuntimeError('Cannot get a dynamic reference to an object '
                           ' that is not yet added to the database')

    def __init__(self, *args, **kwargs):

        # SQLAlchemy 's Base is not collaborative: it will break the MRO
        # access chain, so some subclass objects might never be initialized.
        # We explicitely call Base's __init__() and the next item in the MRO
        # chain to solve this problem.

        Base.__init__(self, *args, **kwargs)
        # Go to the next MRO object *after* Base. The Base Init will have
        # consumed all the parameters, so we pass none to the next level.
        super(Base, self).__init__()


class macro(object):
    '''Decorator for "macros" that performs some rudimentary typechecking.

    Macros are functions used with query objects that are parallelized
    directly, i.e.

    >>> @macro(ReadoutChannel)
    ... def print_channel(c):
    ...     print c.channel

    >>> hwm.query(ReadoutChannel).call_with(print_channel)

    The "print_channel" function ends up executing once for each
    ReadoutChannel in the query. See the "algorithm" decorator for an
    alternative.

    You do not need to use this macro to get this behaviour; it's the
    default case. We encourage use of the decorator anyway, for
    typechecking and to give context for the function being called.
    '''
    def __init__(dec, cls, register=False):
        if isinstance(cls, collections.Iterable):
            dec.__valid_classes = cls
        else:
            dec.__valid_classes = (cls,)
        dec.__register = register

    def __call__(dec, func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            vcs = dec.__valid_classes
            if vcs and not issubclass(self.__class__, vcs):

                raise TypeError(
                    "Macro called with wrong types! Expected %s, got %s" % (
                        ', '.join([cls.__name__ for cls in vcs]),
                        self.__class__))
            t1 = time.time()
            r = func(self, *args, **kwargs)
            t2 = time.time()

            # Say something about the call
            l = logging.getLogger(__name__)
            l.debug('%r: Invoked %s(...) (%f sec)' % (
                self, func.__name__, t2-t1))

            return r

        # Register this algorithm with the class it's used on.
        if dec.__register:
            for vc in dec.__valid_classes:
                setattr(vc, func.__name__, func)

        return wrapper


class algorithm(object):
    '''Decorator for "algorithms".

    This decorator is used as follows:

    >>> @algorithm(ReadoutChannel)
    ... def print_channel(cs):
    ...     print cs.channel

    >>> hwm.query(ReadoutChannel).call_with(print_channel)

    Note that the "print_channel" function is called *once*, and is passed
    in a HWMQuery of ReadoutChannels that can be iterated over. When we
    bump into the "print" statement, an array of integers is assembled.

    If you do not use the @algorithm decorator, you get @macro behaviour
    (the print_channel function will be called once for each ReadoutChannel
    object in the query results.)
    '''
    def __init__(dec, cls, register=True):
        if isinstance(cls, collections.Iterable):
            dec.__valid_classes = cls
        else:
            dec.__valid_classes = (cls,)
        dec.__register = register

    def __call__(dec, func):

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not issubclass(self.__class__, HWMQuery):
                raise TypeError("Algorithm called with non-HWMQuery!")
            vcs = dec.__valid_classes
            if vcs and not all([issubclass(x.__class__, vcs) for x in self]):
                raise TypeError(
                    "Algorithm called with wrong types! "
                    "Expected %s, got %s" % (
                        ', '.join([cls.__name__ for cls in vcs]),
                        ', '.join(set([x.__class__.__name__ for x in self]))
                    ))

            t1 = time.time()
            r = func(self, *args, **kwargs)
            t2 = time.time()

            # Say something about the call
            l = logging.getLogger(__name__)
            l.debug('%r: Invoked %s(...) (%f sec)' % (
                self, func.__name__, t2 - t1))

            return r

        # Flag so call_with doesn't parallelize
        wrapper._hwm_call_with_outer = True

        # Register this algorithm with the HWMQuery.
        if dec.__register:
            for vc in dec.__valid_classes:
                try:
                    HWMQuery._algorithm_registry[vc].append(func)
                except KeyError:
                    HWMQuery._algorithm_registry[vc] = [func]

        return wrapper


class Boolean(sqlalchemy.types.TypeDecorator):
    '''A Boolean lookalike for column definitions, accepting "true"/"false".

    Use this instead of sqlalchemy.Boolean when the column might be initialized
    with string values, e.g. from CSV entries.
    '''

    impl = sqlalchemy.types.Boolean

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
        return value


class Session(sqlalchemy.orm.Session):
    '''Subclass SQLAlchemy's 'Session' object.

    This subclass is not used here, but it provides a way for experiment code
    (dfmux.py) to extend it.'''

    pass


def set_session_class(cls_):
    '''Override the sqlalchemy.orm.Session class.'''
    global __session_class
    __session_class = cls_

__session_class = Session


def HardwareMap(uri='sqlite:///:memory:', echo=False, *args, **kwargs):
    '''Create a HardwareMap object (which is really a SQLAlchemy Session).'''

    # Connect to the database
    e = sqlalchemy.create_engine(uri, echo=echo)

    # It's possible we're operating on an empty, in-memory database
    # (that's one of the use cases we anticipate) -- so ensure all
    # of the relevant tables have been created.
    Base.metadata.create_all(e)

    return sqlalchemy.orm.sessionmaker(
        bind=e,
        query_cls=HWMQuery,
        class_=__session_class,
        *args, **kwargs)()

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
