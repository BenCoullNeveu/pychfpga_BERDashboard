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
    "HWMQuery", "HWMResource", "TuberHWMResource",
    "macro", "algorithm", "HardwareMap",
    "Boolean",
    "Session",
    "set_session_class",
]

# Monkey patching will work fine until "real" asynchronous hits the major
# Python distributions. After a long wade through the various options, it
# looks like Tulip (3.x) / Trollius (2.x) are the future. But, Trollius
# is still stabilizing. In particular, we want aiohttp, and we want it on
# Windows, OS X, and Linux, in standard distributions. We're not there yet.
#
# See, for example, http://sdiehl.github.io/gevent-tutorial/
# 'While monkey-patching is still evil, in this case it is a "useful evil".'
#
# For now, this does the trick, and it's *so* much faster and cleaner than
# trying to keep threading and SQLAlchemy integrated.
import gevent
import gevent.monkey
u'foo'.encode('idna')  # workaround for github.com/gevent/gevent/issues/349
gevent.monkey.patch_socket()  # comment this out to disable green threads.

import os, sys, traceback

import functools
import collections
import time
import logging

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.ext.declarative
import sqlalchemy.types

import tuber

# *** To cleanup
# Make commonly used sqlalchemy classes available through this module
from sqlalchemy import create_engine, inspect
from sqlalchemy import Column, Integer, String, Boolean, Binary, LargeBinary, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Query, sessionmaker, backref, reconstructor, scoped_session, object_session
from sqlalchemy.event import listen

Base = sqlalchemy.ext.declarative.declarative_base()


class HWMQueryException(Exception):
    pass

class HWMQueryAttribute(object):
    def __new__(cls, query_object, attribute_chain):
        """ Return a HWMQueryAttributeBase instance with a __call__
        method that has been tweaked to return the docstring of the target
        method, and is initialized with a *copy* of the original query and attribute list.
        """
        logger = logging.getLogger(__name__)
        logger.debug('calling HWMQueryAttribute.__new__')
        # ClassWithDoc = type(HWMQueryAttributeBase.__name__, HWMQueryAttributeBase.__bases__, dict(HWMQueryAttributeBase.__dict__))
        class HWMQueryAttributeWithDoc(HWMQueryAttributeBase): pass
        try:
            target_method = HWMQueryAttributeBase._get_object(query_object.first(), attribute_chain) # get the attribute (method) described by the attribute object
            call_method = lambda self_, *args, **kwargs: HWMQueryAttributeBase.__call__(self_,*args, **kwargs) # Create a new call method that we can modify below
            HWMQueryAttributeWithDoc.__call__ = functools.update_wrapper(call_method, target_method) # Create a __call__ method that inherits the docstring from the target method
        except AttributeError:
            call_method = lambda self_: None
            call_method.__doc__ = 'This object is not callable'
            HWMQueryAttributeWithDoc.__call__ = call_method #functools.update_wrapper(call_method, lambda:None)
        logger.debug('Done creating new HWMQueryAttribute')

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
        return 'HWMQuery%s = [%s]' % (self._get_access_chain_repr(), ','.join(repr(obj) for obj in self))

    def _get_access_chain_repr(self):
        """ Return a string representation of the access chain.
        """
        return ''.join(['.'+ access if isinstance(access,str) else access[3] for access in self._attribute_chain])

    def __iter__(self):
        if self._query._use_concurrent_get:
            return iter(self._query._concurrent_call(self._attribute_chain, None))
        else:
            return (self._get_object(obj, self._attribute_chain) for obj in self._query)

    def __getattr__(self, attr_name):
        """ Return another HWMQueryAttribute object that points to the specified sub-attribute"""
        return HWMQueryAttribute(self._query, self._attribute_chain + [attr_name])


    def __getitem__(self, *args, **kwargs):
        # return self._get_object(self._query[index], self._attribute_chain)
        # return [self._get_object(obj)[index] for obj in self] # could be parallelized easily
        return HWMQueryAttribute(self._query, self._attribute_chain + [('__getitem__', args, kwargs, '[%r]' % args[0])])

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
    def _get_object(source_obj, access_chain):
        """
        Returns the object represented by the access chain, starting from object source_obj.
        access_chain is a list of elements, each of which is:
            - a string, which indicates the name of the attribute to fetch the derired value
            - a (method_name, args, kwargs) tuple, indicating the method to call to fecth the desired value
        The first element must be an attribute name string (i.e. no function calls are allowed).
        """
        attr = getattr(source_obj, access_chain[0])
        for attr_name in access_chain[1:]:
            if isinstance(attr_name, str):
                attr = getattr(attr, attr_name)
            else:
                (method_name, args, kwargs, _) = attr_name
                method = getattr(attr, method_name)
                attr = method(*args, **kwargs)
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
        def runner(query_result, call_list):
            logger = logging.getLogger(__name__)
            # Create a thread-local session, since SQLAlchemy sessions are not thread-safe.
            # We used to have autoflush=False to make sure flushing will not occur until we ask for it because we get Database is busy errors, but that does not seem to be needed anymode with the improved code
            # We disable 'expire_on_commit' to prevent SA from reloading the expired objects just after commit, which would then get rollbacked on the close()
            # local_session = HardwareMap.scoped_session(expire_on_commit=False) # get a thread-local session
            try: # for now on catch any error and rollback the database if any error occur (except for errors caused by the method called by the user, see other try block below).
                # local_source_obj = local_session.merge(query_result) # move the object from the source session into out thread-local session
                results = list()
                for (attribute_chain, method, local_args, local_kwargs) in call_list:
                    # if attribute_chain:
                    target_obj = HWMQueryAttributeBase._get_object(query_result, attribute_chain) # follow the attribute chain to get the last object
                    logger.debug('Running thread calling object (%r).%s.%s(%s,%s)' % (query_result, '.'.join(attribute_chain), method, ','.join([repr(a) for a in local_args]), ','.join(['%s=%s' % (key,value) for (key,value) in local_kwargs.items()])))

                    # Perform the desired function on the attribute. Catch any error and return them in the result set instead of raisong an exception.
                    try:
                        exc = None
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
                        e = HWMQueryException('Exception on object (%r.%s) = %r\nTraceback:\n%s' % (query_result, '.'.join(attribute_chain), target_obj, '\n'.join(tracebackString)))
                        self._logger.error(e)
                        result = exc
                    logger.debug('Thread for object %r.%s is returning %r' %  (query_result, '.'.join(attribute_chain), result))
                    results.append(result)
                    logger.debug('Added  %r for object %r result list' %  (result, query_result))
                # with database_lock:
                    # self._logger.info('Flushing thread-local session for %r' % (target_obj))
                    # local_session.flush() # probably not necessary with close
                    # self._logger.info('Commiting thread-local session for %r' % (target_obj))
                    # local_session.commit() # probably not necessary with close
                    # self._logger.info('Closing thread-local session for %r' % (target_obj))
                    # local_session.close()
                    # self._logger.info('Thread-local session for %r is closed' % (target_obj))
                    # new_obj = object_session(query_result).merge(local_source_obj) # make sure the changes to the object are reflected in the original session. Hopefully this will not create a new object in a new memoty location...
                    # if new_obj is not local_source_obj: print 'oops the object has changed'
                # object_session(query_result).expunge(query_result) # make sure the changes to the object are reflected in the original session. Hopefully this will not create a new object in a new memoty location...
                # self._logger.info('Refreshing object %r in original session' % (query_result))
                # object_session(query_result).refresh(query_result) # make sure the changes to the object are reflected in the original session. Hopefully this will not create a new object in a new memoty location...
                # object_session(query_result).refresh(query_result) # make sure the changes to the object are reflected in the original session. Hopefully this will not create a new object in a new memoty location...
                # self._logger.info('Original object is refreshed. Exiting thread session for %r' % (query_result))
                return results
            except Exception as ee:
                logger.error('Thread exception %r' % ee)
                # local_session.rollback()
                raise ee
                # return [None]
        exception_list = []
        # database_lock = threading.Lock()

        threads = [ gevent.spawn(runner, query_result, self._call_list) for query_result in self]
        gevent.joinall(threads)

        # Look for any exceptions; raise them if they exist.
        for t in threads:
            if t.exception:
                exception_list.append(t.exception)


        # Results are indexed backwards (i.e. [thread][call]). Transpose.
        transposed_results = zip(*( t.value for t in threads ))

        # with concurrent.futures.ThreadPoolExecutor(max_workers=100) as e:
        #     results = e.map(runner, zip(list(self), [self._call_list]*self.count(), [database_lock]*self.count()) ) # return a generator that will yield the results (in the right order)  as they become available.
        #     try:
        #         transposed_results= zip(*results) # rearrange the results in a tuple where each element is a vector containing the result of one call for all query objects.
        #     except Exception as exc:
        #         transposed_results = None
        #         exception_list.append(exc)
        #         self._logger.error('Exception in thread results : %r' % (exc))

        self._call_list = [] # empty the call list
        # self._logger.debug('All threads returned %r' % transposed_results) # resilting string is sometimes too big for syslog.
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
        multi-threaded context. We use green threads to avoid the
        overhead from threading -- which seems minimal, until we pile
        on the SQLAlchemy housekeeping that's required.

        This call allows you to do exactly that, as follows:

            >>> objects.do_something()

        It does so by trapping calls it doesn't recognize itself, and
        delegating them to each object in the Query results. It returns
        an array of results corresponding to each underlying object.
        '''
#        self.logger.debug('call __getattr__')
        # Since this is a SQLAlchemy "Query" subclass, we can use it
        # as a collection and call things like "count()" on it.

        # Refuse to parallellize access to special names
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
            self._logger.error('Atttribute %s does not exist on any element of the query.' % name)
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

            >>> [do_something(r, foo, bar) for r in results]

        ...but you'd like to parallelize the call (i.e. run it in a
        multi-threaded context.) Using this function, you can do so as
        follows:

            >>> results.call_with(do_something, x, foo, bar)
        """
        return self._concurrent_call(None, func, *args, **kwargs)
        # return self._call_proto(func, False, *args, **kwargs)()

class HWMHandlerManager(object):
    """ Proof of concept of a handler object, which is an object that provides
    methods and attributes located remotely or locally.

    Local access to Python object is performed if the object's class is
    registered to the Handler. Otherwise remote access is done through Tuber.

    Remote (Tuber) handlers have these restrictions:
       - attributes and methods whise name begin with '_' are not accessible
       - modification to the object attributes must be done by a setter
         function provided by the object.
       - methods or attribute access can only return string or numeric values,
         or lists or dictionnary thereof

    Local (Python) handlers do not have access restrictions. They can be used
    as any other Python object.

    Notes:

       - JFC: The way this is written, direct local access of python classes
         is currently more flexible than remote access because we do not need
         the return value to be serializable. We therefore can dig down the
         hierarchies and index objects directly, which is heavily used for
         debugging. Remote access through Tuber would not allow this,
         therefore potentially causing code compatibility issues if the code
         is moved remotely. Depending on the philosophy of the system, we
         might want to restrict local access capabilities to match that of
         remote access (unless we use a more flexible RPC protocol (like RpyC)
         and are willing run python remotely).
    """
    class UpdateHandler(object):
        """ Create an instance-based '_handler' attribute when accessed.
        This is a non-data descriptor (no __set__() method) , so Python will access the instance attribute instead if it exists.
        """
        def __get__(self, obj, objtype):
            obj._handler = obj.init_handler()
            return obj._handler
        def __delete__(self, obj):
            pass

    # Class attributes
    # _handler_registry = {} # (handler_key: handler)
    _handler = UpdateHandler() # If no instance _handler exist, access to _handler will invoke the data descriptor to create the instance _handler
    _handler = None # If no instance _handler exist, access to _handler will invoke the data descriptor to create the instance _handler

    # Instance attributes

    @classmethod
    def register_handler(cls, class_, class_name=None):
        """ Register a Python class 'class_' as a handler named 'class_name'
        for the target Hardware Map object.

        This handler will be used as an application handler if its name
        matches the name provided with set_handler(), otherwise a tuber
        handler will be used.

        If the handler is passed a core handler at initialization, it must
        make visible the methods and attributes of this core object.
        """
        # Make sure this class has its own handler registry so we don't access the subclass registry
        if '_local_python_handler_classes' not in cls.__dict__:
            cls._local_python_handler_classes = {}

        if not class_name:
            class_name = class_.__name__
        cls._local_python_handler_classes[class_name]=class_

    def get_handler(self):
        """ Return the current handler for this Hardware Map instance.
        """
        if not self._handler:
            self.init_handler()
        return self._handler

    @property
    def handler(self):
        """ Return the current handler for this Hardware Map instance.
        """
        if not self._handler:
            self.init_handler()
        return self._handler

    def set_handler(self, object_id=None, handler_name = None, **kwargs):
        """
        Sets the handler to be used with this Hardware Map instance uniquely
        identified by 'object_id'. If a handler has been created previously,
        it is reattached, otherwise a new one is created.

        Arguments:
            tuber_uri: Address used to access remote handlers (typically the ARM processor on an iceBoard)
            core_handler_name: Name of the core handler, (typically a remote handler)
            app_handler_name: Name of the application-specific handler, found locally or remotely
            object_id: ID used to uniquely identify each instance of the class. This is preferably linked to a unique hardware serial number, but a database primary key can probably be used safely.
        """
        logger = logging.getLogger(__name__)

        logger.info('%r(HWMHandlerManager): setting handler with id=%r and handler_name=%s, using  arguments %r ' % (self, object_id, handler_name, kwargs))

        handler_key = (object_id, handler_name) #we include handler_name to properly handle boards with multiple personnalities
        self._handler = None
        if object_id and handler_name:

            # Make sure the top superclass has its own registery of handlers.
            # We use .__dict__ to ensure we do not access the subclass version of the attribute
            if  '_handler_registry' not in type(self).__dict__:
                type(self)._handler_registry = {}

            # If the key exists in the handler registry, retreive the handler from it
            if handler_key in self._handler_registry:
                logger.info('%r(HWMHandlerManager): Reusing registered handler' % self)
                self._handler = self._handler_registry[handler_key]
                self.update_handler()

            # If not, let's create a handler.
            # If there is a local python class for the specified application handler, create it. We pass it a tuber core handler.
            elif handler_name in self._local_python_handler_classes:
                handler_class = self._local_python_handler_classes[handler_name]
                logger.info('%r(HWMHandlerManager): Creating handler %s' % (self, handler_name))
                self._handler = handler_class(**kwargs)
                type(self)._handler_registry[handler_key] = self._handler # register the handler for this instance
                self.update_handler()
            else:
                logger.error('%r: HWMHandlerManager: No handler was found with the name %r. Using an empty handler instead.' % (self, handler_name))
                self._handler = Handler(**kwargs)

        if not self._handler:
            logger.info('%r(HWMHandlerManager): does not have a valid handler (yet)' % self)
        else:
            logger.info('%r(HWMHandlerManager): handler is %r' % (self, self._handler))

    def __dir__(self):
        """ Return the list of attributes of this class and of those of the handler."""
        if not self._handler: # if the handler is invalid, try to get a valid one
            self.init_handler()
        return list(set(type(self).__dict__.keys() + self.__dict__.keys() + (dir(self._handler) if self._handler else [])))

    def __getattr__(self, name):
        """ Return the value of an attribute if it exists in the handler """
        # print "Handler is getting attribute '%s' for %r's handler" % (name, self)
        # If we have a valid handler, try to access the attribute from it immediately
        if self._handler:
            return getattr(self._handler, name)
        # If we do not have a valid handler, try to create one and get the attribute from it
        self.init_handler()
        if self._handler:
            return getattr(self._handler, name)
        raise AttributeError('Unknown attribute %s for %r. This could be because this instance has no valid handler yet' % (name, self))

    def update_handler(self):
        """ Calls the hwm_update() method of the handler with this hardware
        mapped object as an argument to inform on changes in the database
        object.
        """
        if hasattr(self._handler,'hwm_update'):
            self._handler.hwm_update(self)

    def __init__(self, *args, **kwargs):
        # logger = logging.getLogger(__name__)
        # logger.debug('HWMHandlerManager: calling __init__ for %r' % (self))
        # self.init_handler()
        super(HWMHandlerManager, self).__init__() # This essentially call object.__init(), so there are no  parameters to pass.

    def init_handler(self):
        """ Default handler initializer.

        The user shall override this function to specify what handlers to use
        for this specific Hardware map object.

        This is called whenever a managed HWM object is created from scratch,
        has been reloaded from the database.

        This function shall call self.set_handler(...) and provide a unique
        object_id that uniquely identifies this HWM object instance, and a
        handler_name that will tell which class to use to create a new handler
        if needed.
        """
        # get a unike instance ID based on the value of all primary keys
        primary_key_values = [getattr(self, key.name) for key in self.__mapper__.primary_key]
        self.set_handler(object_id=primary_key_values, handler_name=self._cls)

    @classmethod
    def __declare_last__(cls):
        """Define the event listeners that let the system know that the handler needs to be refreshed.

        __declare_last__ is a special SQLAlchemy class method that is called when the class
        definition is complete.
        """

        def _hwm_init_event(instance, event_name):
            logger = logging.getLogger(__name__)
            logger.info("%r(HWMHandlerManager): Init Event '%s' " % (instance, event_name))
            instance._handler = None # invalidate the handler, so it will be created

        listen(cls, 'load', lambda target, context: _hwm_init_event( target, event_name='load'))
        listen(cls, 'init', lambda target, *args, **kwargs: _hwm_init_event( target, event_name='init')) # useless: it is called before the object's attribute are populated
        listen(cls, 'refresh', lambda target, context, attrs: _hwm_init_event( target, event_name='refresh'))
        listen(cls, 'after_update', lambda mapper, connection, target: _hwm_init_event( target, event_name='after_update'))
        # add after_insert?

class HandlerMeta(type):
    """ Intercept the creation of a Handler subclass to automatically register it with the associated HWM object.

    The Handler subclass must define the following attributes:
        __handler_for__ = HWM_object #  HWM object to which this handler is associated with. HWM_object must be a subclass of HWMHandlerManager.
        __handler_name__ = 'some string' #  The name under which the handler can be found. Allows the
    """
    def __init__(cls, classname, bases, dict_):
        if '__handler_for__' not in dict_ or '__handler_name__' not in dict_:
            raise AttributeError("Both '__handler_for__' and '__handler_name__' must be specified in Handler class %r" % classname)
        base = dict_['__handler_for__']
        name = dict_['__handler_name__']
        if base and name:
            if not issubclass(base, HWMHandlerManager):
                raise AttributeError("The class assigned to '__handler_for__' must be a subclass of HWMHandlerManager for %r" % classname)
            base.register_handler(cls, name)
        type.__init__(cls, classname, bases, dict_)

class Handler(object):
    """
    Basic generic handler base class. All handlers should be derived from this class.
    """
    __metaclass__ = HandlerMeta

    __handler_for__ = None
    __handler_name__ = None

    def __init__(self, **kwargs):
        """ Initialize a basic handler.

        By convention, all handlers __init__() only take keyword arguments to ensure
        consistency across the super/subclass hierarchy.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Handler: Instantiating Handler for %r' % (self))
        super(Handler, self).__init__() # This is just calling 'object', so we strip all parameters

    def hwm_update(self, hwm_object):
        """ Is called when the Hardware Map object might have changed to
        reflect those changes in the handler. The superclass mush redefine
        this and can use super(). This class is mainly provided to allow safe
        super() calls.
        """
        pass


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

    def __init__(self, *args, **kwargs):
        Base.__init__(self, *args, **kwargs)
        super(Base, self).__init__(*args, **kwargs) # Go to the next MRO object *after* Base


class TuberHWMResource(HWMResource, tuber.TuberObject):
    '''A base class for HWMResources that correspond to TuberObjects.'''
    __abstract__ = True

    hostname = sqlalchemy.Column(
        sqlalchemy.String,
        doc="The hostname (or IP) to use for this resource.")

    def __init__(self, *args, **kwargs):
        super(TuberHWMResource, self).__init__(*args, **kwargs) # Needed to allow multiple inheritance to work

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
                self, func.__name__, t2-t1))

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
