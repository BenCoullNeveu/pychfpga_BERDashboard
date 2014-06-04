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
import os, sys, traceback
import urlparse
import threading
import concurrent.futures
import operator
import functools
import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy import Column, Integer, String, Boolean, Binary, LargeBinary, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Query, sessionmaker, backref, reconstructor, scoped_session, object_session

Base = declarative_base()

class HWMQueryException(Exception):
    pass

class HWMQueryAttribute(object):
    def __new__(cls, query_object, attribute_chain):
        """ Return a HWMQueryAttributeBase instance with a __call__
        method that has been tweaked to return the docstring of the target
        method, and is initialized with a *copy* of the original query and attribute list.
        """
        logger = logging.getLogger(__name__)
        logger.debug('calling __new__')
        # ClassWithDoc = type(HWMQueryAttributeBase.__name__, HWMQueryAttributeBase.__bases__, dict(HWMQueryAttributeBase.__dict__))
        class HWMQueryAttributeWithDoc(HWMQueryAttributeBase): pass
        try:
            target_method = HWMQueryAttributeBase.get_object(query_object.first(), attribute_chain) # get the attribute (method) described by the attribute object
            call_method = lambda self_, *args, **kwargs: HWMQueryAttributeBase.__call__(self_,*args, **kwargs) # Create a new call method that we can modify below
            HWMQueryAttributeWithDoc.__call__ = functools.update_wrapper(call_method, target_method) # Create a __call__ method that inherits the docstring from the target method
        except AttributeError:
            call_method = lambda self_: None
            call_method.__doc__ = 'This object is not callable'
            HWMQueryAttributeWithDoc.__call__ = call_method #functools.update_wrapper(call_method, lambda:None)
        return HWMQueryAttributeWithDoc(query_object, attribute_chain)

class HWMQueryAttributeBase(object):
    """
    Class representing an attribute or subattribute attached to Query results. The class does not store the attribute
    objects itself, but rather keeps track of the attribute chain (i.e.
    attr1.attr2.attr3 ...) that leads to the desired object. This allows the
    objects to be reaccessed from another root object (i.e. from another session), allowing thread-safe operations.
    """

    # initialize variables so __getattr__() will not be called when they are accessed on a fresh instance
    _query = None # iterable providing objects with common attributes
    _attribute_chain = None # list of strings representing the attributes to access in order

    def __init__(self, query_object, attribute_chain):
        """ Creates an attribute object. 'attribute_chain' is a list of
        attributes names that, when applied sequentially to the root object
        'query_object', yields the desired attribute object.
        """
        self._logger = logging.getLogger(__name__)
        self._query = query_object#._clone()
        self._attribute_chain = list(attribute_chain)

    def __repr__(self):
        # return '%r.%s = [%r]' % (Query.__repr__(self._query), '.'.join(self._attribute_chain), ','.join(repr(obj) for obj in self))
        return 'HWMQuery.%s= [%s]' % ('.'.join(self._attribute_chain), ','.join(repr(obj) for obj in self) )

    def __iter__(self):
        if self._query._use_concurrent_get:
            return iter(self._query._concurrent_call(self._attribute_chain, None))
        else:
            return (self.get_object(obj, self._attribute_chain) for obj in self._query)

    def __getattr__(self, attr_name):
        """ Return another HWMQueryAttribute object that points to the specified sub-attribute"""
        return HWMQueryAttribute(self._query, self._attribute_chain + [attr_name])


    def __getitem__(self, index):
        return self.get_object(self._query[index], self._attribute_chain)

    def __len__(self):
        return self._query.count()

    def __dir__(self):
        """
        Lists all the attributes that are accessible from this attribute. Useful for tab completion.
        """
        self._logger.debug('Calling dir')
        query_attr = [set(dir(obj)) for obj in self]
        return list(set.intersection(*query_attr))


    def __call__(self, *args, **kwargs):
        """ Call the the attribute (method) on all elements of the root object concurrently with the specifid arguments. All calls are made with the same arguments."""
        if self._query._use_concurrent_call:
            return self._query._concurrent_call(self._attribute_chain, '__call__', *args, **kwargs)
        else:
            return [obj(*args, **kwargs) for obj in self]

    @staticmethod
    def get_object(source_obj, attribute_chain):
        """
        Returns the object represented by the attribute chain, starting from object source_obj.
        """
        attr = getattr(source_obj, attribute_chain[0])
        for attr_name in attribute_chain[1:]:
            attr = getattr(attr, attr_name)
        return attr

class HWMQuery(Query):
    '''HWMQuery object: A parallel-call extension to Query objects.

    This is also pretty well internal; you shouldn't have to use it directly.
    Please look at the DocStrings for HardwareMap instead.

    This is an extension to SQLAlchemy's Query object. A HWMQuery can be
    used to dispatch method calls on every class it contains.
    '''
    _hold_dispatcher = False
    _index_column = None
    _call_list = []
    _use_concurrent_get = None
    _use_concurrent_set = None
    _use_concurrent_call = None

    def __init__(self, entities, session=None, index_by = None, use_concurrent_get=False, use_concurrent_set=False, use_concurrent_call=True):
        self._logger = logging.getLogger(__name__)
        super(type(self), self).__init__(entities, session)
        self._index_column = index_by
        self._use_concurrent_get = use_concurrent_get
        self._use_concurrent_set = use_concurrent_set
        self._use_concurrent_call = use_concurrent_call

    def hold(self, on_hold=True):
        self._hold_dispatcher = bool(on_hold)
        if not on_hold:
            return self.flush()

    def flush(self):
        # Always, after flushing, assume single-stepping.
        self._hold_dispatcher = False
        return self._execute_concurrent_calls()

    def _concurrent_call(self, attribute_chain, access_method_name, *args, **kwargs):
        """ Add a concurrent call to the list and execute if we are not on hold."""
        assert not (self._hold_dispatcher==False and self._call_list), ' Hold is inactive but there are pending tasks in the call list'
        self._call_list.append((attribute_chain, access_method_name, args, kwargs))
        if not self._hold_dispatcher:
            return self._execute_concurrent_calls()[0]

    def _execute_concurrent_calls(self):
        """ Concurrently calls the methods on the attributes specified in the call list for every object
        represented by the query. If the access method is 'None', the object itself is returned.

        call_list is a list of tuples consisting of: (attribute, method, args, kwargs)
        Where:
            attribute_object: HWMQueryAttribute object representing the chain of attributes leading to the desired object
            args (tuple) and kwargs (dict): arguments to pass to the method
            method: if Null, the attribute is returned. If callable, the method is called with an query result as argument, plus arg and kwargs. If a string, the call is made with the method of the same name for this attribute.


        To call an attribute (method): q._execute_concurrent_call(attr, '__call__', arg1, arg2, ... )
        To set an attribute: q._execute_concurrent_call(attr, '__setattr__', attr_name, value)
        To get an attribute: q._execute_concurrent_call(attr, None) # where attr describes the attribute itself
                 or:         q._execute_concurrent_call(attr, '__getattr__', attr_name) # where attr describes the parent attribute
        """
        # define the function performed by each thread on each object
        def runner((query_result, call_list, database_lock)):
            logger = logging.getLogger(__name__)
            try:
                local_session = HardwareMap.scoped_session(autoflush=False) # get a thread-local session
                # local_obj = local_session.query(type(query_result)).filter_by(pk=query_result.pk).one() # this works, but might not be very efficient
                with database_lock:
                    local_source_obj = local_session.merge(query_result) # this works as well
                    object_session(query_result).expunge(query_result) # make sure the object from the original session will be reloaded once we are finished processing its counterpart in the thread-local session.
                results = list()
                for (attribute_chain, method, local_args, local_kwargs) in call_list:
                    # if attribute_chain:
                    target_obj = HWMQueryAttributeBase.get_object(local_source_obj, attribute_chain) # follow the attribute chain to get the last object
                    logger.debug('Running thread calling object (%r).%s.%s(%s,%s) in session %r' % (query_result, '.'.join(attribute_chain), method, ','.join([repr(a) for a in local_args]), ','.join(['%s=%s' % (key,value) for (key,value) in local_kwargs.items()]), local_session))
                    # else:
                    #     target_obj = local_source_obj

                    exc = None
                    try:
                        if callable(method):
                            result = method(target_obj, *local_args, **local_kwargs)
                        elif method:
                            attribute_method = getattr(target_obj, method)
                            result = attribute_method(*local_args, **local_kwargs)
                        else:
                            result = target_obj
                    except Exception as exc:
                        result = None
                        # tracebackString = traceback.format_exc(limit=1)
                        (exception_type, exception_args, exception_tb) = sys.exc_info()
                        tb = traceback.extract_tb(exception_tb)
                        tracebackString = ['    %s in .../%s:%i' % (fn, os.path.split(filename)[1], line) for (filename, line, fn, code) in tb]
                        tracebackString[-1] += ('=> %r' % exception_args)
                        e = HWMQueryException('Thread exception on object (%r.%s) = %r\nTraceback:\n%s' % (local_source_obj, '.'.join(attribute_chain), target_obj, '\n'.join(tracebackString)))
                        self._logger.error(e)
                        result = exc
                    logger.debug('Thread for object %r.%s is returning %r' %  (local_source_obj, '.'.join(attribute_chain), result))
                    results.append(result)
                with database_lock:
                    local_session.commit()
                    local_session.close()
                return results
            except Exception as ee:
                logger.error('Thread global exception %r' % ee)
                return [None]
        exception_list = []
        database_lock = threading.Lock()
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as e:
            results = e.map(runner, zip(list(self), [self._call_list]*self.count(), [database_lock]*self.count()) ) # return a generator that will yield the results (in the right order)  as they become available.
            try:
                transposed_results= zip(*results) # rearrange the results in a tuple where each element is a vector containing the result of one call for all query objects.
            except Exception as exc:
                transposed_results = None
                exception_list.append(exc)
                self._logger.error('Exception in thread results : %r' % (exc))
        self._call_list = [] # empty the call list
        self._logger.debug('All threads returned %r' % transposed_results)
        if exception_list:
            raise HWMQueryException('The concurrent call generated the following exceptions: %s' % ','.join(repr(e) for e in exception_list))
        else:
            return transposed_results

    def __dir__(self):
        """
        Lists all the attributes that are accessible from this instance and those that are common to all the results in the query.
        Useful for tab completion.
        """
        # return type(self).__dict__ + self.__dict__ + dir(self._hwmap)
        self._logger.info('calling dir')
        local_attr = dir(type(self)) + self.__dict__.keys()
        query_attr = [set(dir(x)) for x in self]
        return local_attr + list(set.intersection(*query_attr))

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
#        self.logger.debug('call __getattr__')
        # Since this is a SQLAlchemy "Query" subclass, we can use it
        # as a collection and call things like "count()" on it.

        # Refuse to parallellize access to _some_types_of_name
        if name[0] == '_':
            raise AttributeError("Refusing to parallelize name '%s' (because it begins with a '_')" % name)

        # See if this is something we can parallelize. Note that
        # AttributeError is the correct exception to return for
        # "didn't-find-it" errors. If objects are mismatched, indicating a
        # programmer error, we return something angrier.
        if self.count() == 0:
            raise AttributeError("Query is empty: there are no attributes to be found")

        # Generate an exception of only some of the objects have the
        # desired attribute. (If none of the objects have the attribute,
        # we want to raise the ordinary Python AttributeError. This
        # happens below.)
        attr_present = [hasattr(x, name) for x in self]
        if not any(attr_present):
            raise AttributeError
        elif not all(attr_present):
            raise HWMQueryException("Not all elements of the query contain the attribute '%s'" % name);
        else:
            return HWMQueryAttribute(self, [name])

    def index_by(self, index_column=None):
        """
        Specifies the column to use as an index when indexing this object
        using '[]'. If none is specified, the objects are indexed by the order
        they were queried (original SQLAlchemy's Query behavior)

        Example:
            >>> c=ca.query(IceBoard).index_by(IceBoard.serial_number)
            >>> c[7] # returns the iceboard with serial number 7
        """
        self._index_column = index_column
        return self

    # def __len__(self):
    #     return self.count()

    def __getitem__(self, index):
        """
        If an indexing colums was specified with index_by(...) and the
        provided index is a scalar (a string or an integer), return the
        database where the indexing column matches the index. Otherwise
        executes default SQLAlchemy indexing (indexes the object in the order
        they were returned) which supports slices.

        In the column indexing mode, an exception will be raised if the query
        does not produce exactly one result (we call the .one() method)
        """
        if self._index_column and not isinstance(index, slice):  # we must not process slices because  Query.first() and Query.__getitem__ use self[slice] and would be really confused
            return self.filter(self._index_column == index).one()
        else:
            return super(type(self), self).__getitem__(index)

    def __repr__(self):
        """
        Returns a human-readable representaion of the query results.
        """
        return 'HWMQuery= [%s]' % ','.join(repr(obj) for obj in self)

    def call_with(self, func, *args, **kwargs):
        """Call some function across a collection of Query results.

        Let's say you want to do "something" with a set of Query results:

            >>> [ do_something(r, foo, bar) for r in results ]

        ...but you'd like to parallelize the call (i.e. run it in a
        multi-threaded context.) Using this function, you can do so as
        follows:

            >>> results.call_with(do_something, x, foo, bar)
        """
        return self._concurrent_call(None, func, *args, **kwargs)
        # return self._call_proto(func, False, *args, **kwargs)()

class HWMResource(Base):
    '''Base class for Hardware Mapper resources to share.

    You should inherit from this class in order to create a Hardware-Mapped
    resource. It's declared for convenience, since "Base" is an instantiated
    class (see the top of this file.)
    '''
    __abstract__ = True

class HardwareMap(object):
    #class attributes
    scoped_session = None

    def __new__(self, uri='sqlite:///:memory:', echo=False, *args, **kwargs):
        # Connect to the database
        e = create_engine(
                uri,
                echo=echo,
                connect_args={'check_same_thread':False}
        )
        print 'using', uri
        # It's possible we're operating on an empty, in-memory database
        # (that's one of the use cases we anticipate) -- so ensure all
        # of the relevant tables have been created.
        Base.metadata.create_all(e)

        # A HardwareMapper is actually just an augmented SQLAlchemy Session.
        session_factory = sessionmaker(
                bind=e,
                query_cls=HWMQuery,
                *args,
                **kwargs)
        self.scoped_session = scoped_session(session_factory)
        # return scoped_session(session_factory)
        return session_factory()
# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
