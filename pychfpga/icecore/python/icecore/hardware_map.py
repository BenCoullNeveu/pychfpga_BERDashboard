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

import Queue as queue
import urlparse
import concurrent.futures
import operator
import functools

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Query, sessionmaker

Base = declarative_base()

class HWMQueryException(Exception):
    pass

class HWMQuery(Query):
    '''HWMQuery object: A parallel-call extension to Query objects.

    This is also pretty well internal; you shouldn't have to use it directly.
    Please look at the DocStrings for HardwareMap instead.

    This is an extension to SQLAlchemy's Query object. A HWMQuery can be
    used to dispatch method calls on every class it contains.
    '''
    _hold_dispatcher = False

    def hold(self, on_hold=True):
        self._hold_dispatcher = on_hold
        if not on_hold:
            return self.flush()

    def flush(self):
        # Always, after flushing, assume single-stepping.
        self._hold_dispatcher = False

        # Claim all pending calls. If there's nothing to do, don't try.
        try: calls = self._calls
        except AttributeError: return
        del self._calls

        runner = lambda calls: ( c() for c in calls )

        # Uncomment this line to run single-threaded (debugging only!)
        #return zip(map(runner, calls))

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as e:
            # If you get a "zip() argument after * must be a sequence" error
            # here, see "http://bugs.python.org/issue4806". You can mask the
            # interpreter bug by running single-threaded (see above)
            return zip(*e.map(runner, calls))

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
        multi-threaded context.

        This call allows you to do exactly that, as follows:

            >>> objects.do_something()

        It does so by trapping calls it doesn't recognize itself, and
        delegating them to each object in the Query results. It returns
        an array of results corresponding to each underlying object.
        '''

        # Since this is a SQLAlchemy "Query" subclass, we can use it
        # as a collection and call things like "count()" on it.

        # Refuse to parallellize access to _some_types_of_name
        if name[0] == '_': raise AttributeError("Refusing to parallelize name '%s'" % name)

        # See if this is something we can parallelize. Note that
        # AttributeError is the correct exception to return for
        # "didn't-find-it" errors. If objects are mismatched, indicating a
        # programmer error, we return something angrier.
        if self.count() == 0:
            raise AttributeError

        # Generate an exception of only some of the objects have the
        # desired attribute. (If none of the objects have the attribute,
        # we want to raise the ordinary Python AttributeError. This
        # happens below.)
        if len(set([hasattr(x,name) for x in self])) != 1:
            raise HWMQueryException("Called with mismatching objects!");

        # Get the specified attribute from all object
        # Note that this raises an AttributeError, so it'll fail in just the
        # right way if we are missing the attribute..
        attrs = [ getattr(x, name) for x in self ]

        # Ensure attributes are always, or never, callable.
        # JFC: A class is callable. Are we safe here, or should we check the presence of __call__?
        if len(set([callable(x) for x in self])) != 1:
            raise HWMQueryException("Called with mismatching objects!");

        # For non-callable attributes: treat like a property.
        if not callable(attrs[0]):
            return attrs

        # Fall-through to a function call.
        return self._call_proto(attrs, True)

    def call_with(self, func, *args, **kwargs):
        """Call some function across a collection of Query results.

        Let's say you want to do "something" with a set of Query results:

            >>> [ do_something(r, foo, bar) for r in results ]

        ...but you'd like to parallelize the call (i.e. run it in a
        multi-threaded context.) Using this function, you can do so as
        follows:

            >>> results.call_with(do_something, x, foo, bar)
        """

        return self._call_proto(func, False, *args, **kwargs)()

    def _call_proto(self, func, already_bound=False, *args, **kwargs):
        """Generate a function suitable for queueing a call and return it.

        This function is called with either unbound functions (e.g. which
        don't have a "self" associated with them yet) or partially-bound
        functions (which already have selves.) The "already_bound" parameter
        allows both cases to be handled uniformly.

        If "already_bound", then func should be an array of functions. If not,
        provide a single function and we'll specialize it our selves.
        """

        if not hasattr(self, '_calls'):
            self._calls = [ list() for o in self ]

        if already_bound:
            try:
                if len(func) != self.count(): raise TypeError
            except TypeError:
                raise HWMQueryException("Expected 'func' to be a list of %i functions!" % self.count())

        # The decorator just steals the DocStrings etc. from the underlying
        # function. It's a shame about the function signature: it's destroyed
        # by Python, and there's no standard way to get it back. (There's an
        # external 'decorators' module, but it's apparently hinky.)
        @functools.wraps(func[0] if already_bound else func)
        def proto(*args, **kwargs):

            # Queue a function call.
            if already_bound:
                for (l, f) in zip(self._calls, func):
                    l.append(functools.partial(f, *args, **kwargs))
            else:
                for (l, o) in zip(self._calls, self):
                    l.append(functools.partial(func, o, *args, **kwargs))

            # If we're supposed to dispatch it, do so after queueing.
            if not self._hold_dispatcher:
                return self.flush().pop()

        return proto

class HWMResource(Base):
    '''Base class for Hardware Mapper resources to share.

    You should inherit from this class in order to create a Hardware-Mapped
    resource. It's declared for convenience, since "Base" is an instantiated
    class (see the top of this file.)
    '''
    __abstract__ = True

class HardwareMap(object):

    def __new__(self, uri='sqlite:///:memory:', echo=False, **kwargs):
        # Connect to the database
        e = create_engine(
                uri,
                echo=echo,
                connect_args={'check_same_thread':False}
        )

        # It's possible we're operating on an empty, in-memory database
        # (that's one of the use cases we anticipate) -- so ensure all
        # of the relevant tables have been created.
        Base.metadata.create_all(e)

        # A HardwareMapper is actually just an augmented SQLAlchemy Session.
        return sessionmaker(bind=e, query_cls=HWMQuery, **kwargs)()

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
