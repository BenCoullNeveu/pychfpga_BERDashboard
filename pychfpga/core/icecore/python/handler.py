"""Handler management classes.

A Handler is a user-defined, persistent Python object that is dynamically
linked to a volatile object in order to into extend its attributes and
methods. They are typically used to provide stateful methods to SQLAlchemy ORM
objects

Handlers behave as normal Python objects.  All their instance attributes will
persist until the object is no longer used, as opposed to ORM objects that
might have their non-database attributes erased as part of
the background operation of the ORM engine. This, for instance, allows the
handler to store hardware state information, opened sockets or other runtime-
specific information that should not live in the database.

Handlers instances are only created only once, and are reattached to the
parent object if the handler link has been erased by the parent.

Multiple Handler classes can be registered to an ORM class, allowing the ORM
object to dynamically switch functionality. For example, different handlers
can be activated depending on what firmware has been loaded on the hardware
represented by the parent object.

This module exposes the following classes:

    - HandlerObject: is inherited by the parent object to which we want to
      associate a handler. The class ensures the handler is reconnected to the
      object, and forwards attribute accesses to the handler.

    - Handler: is inherited by the application-specific handler. The class
      registers the handler to the parent object, and provides means for the
      handler to grab information from the parent.
"""

import logging
import collections
import sys

# from sqlalchemy.event import listen


class HandlerObject(object):

    """Automatically create and persistently associate a python class (a
    handler) to a 'volatile' parent object and forwards attribute accesses to it.

    HandlerObject is useful to add memory-persistent attributes and methods to
    SQLAlchemy's ORM objects which otherwise regularly clear all their non-
    database attributes as those objects come in and out of existence at
    various memory locations as part of normal SQLAlchemy operations.

    When a handler needs to be accessed on a parent object instance,
    HandlerObject looks for an already existing one in its handler instance
    registry using the unique parent instance key provided by the 'handler_id'
    property which is provided by the parent class.

    If no handler is found, HandlerObject looks into its handler class
    registry to see if there is a handler class that matches the handler name
    provided by the 'handler_name' attribute. If a matching handler class is
    found, a new handler instance is created and registered. Otherwise, an
    error is raised.

    The user shall define a handler by defining a class that inherits from the
    Handler class. This will cause the class to be automatically registered
    with the parent object class.

    HandlerObject defines __getattr__ and __dir__ to give the parent object
    access to all of the handler's attributes. Setting an attribute sets it in
    the parent object.

    To have a handler, the parent object only need to inherit from this class
    and optionally define 'handler_id' and 'handler_name' to uniquely identify
    the parent instance and which of the registered handler is to be used with
    this parent instance.

    The default 'handler_id' assumes the parent is a SQLAlchemy ORM object and
    will use its primary keys as a unique instance id.

    The default 'handler_name' refers to the last Handler to be defined for
    this particular parent class.
    """

    # Default fallback values to prevents recursive __getattr__ calls
    _handler = None
    _handler_enable = True

    @classmethod
    def register_handler(cls, class_, class_name):
        """ Register a Python class 'class_' as a handler named 'class_name'
        for the target Hardware Map object.
        """
        # Make sure this subclass has its own registery of handlers classes.
        # We use .__dict__ to avoid accessing a superclass version of it.
        # We use an OrderedDict so we can access the last registered class.
        if '_handler_class_registry' not in cls.__dict__:
            cls._handler_class_registry = collections.OrderedDict()

        cls._handler_class_registry[class_name] = class_  # Add the class

    @property
    def handler(self):
        """ Return the handler object to be used with a parent object
        instance.

        This method needs the following:
            - 'object_id': property that returns a key that uniquely
              identifies the parent object instance (such as a database
              primary key).
            - 'handler_name': attribute or property that returns the name of
              the handler object used to create a new handler for the parent
              object.

        If the handler already exists handler instance registry under the
        'object_id' key, then this handler is returned.

        If no handler exist in the handler instance registry, a new one is
        created by looking up the handler class registry for 'handler_name'.

        In both cases, the handler's hwm_update() method is called to give the
        handler the opportunity to grab data from the parent object.

        If 'handler_name' is None, no handler is created for this object.

        The value of the handler is cached in the _handler attribute for fast
        access. The handler is looked-up or created only if a valid _handler
        does not exist yet or was deliberately deleted (for example because
        the parent object was recreated.)

        NOTE: If this property raises an AttributeError when accessed, Python
        will automatically (and annoyingly) call __getattr__('handler').
        """

        if not self._handler_enable:
            return None

        # self._check_for_local_attribute_corruption()  # Temporary. See method.

        if self._handler:  # Promptly return cached value if available
            return self._handler

        # Executing past this point should be rare now
        logger = logging.getLogger(__name__)

        try:
            # Disable handler system to prevent recursion
            old_handler_enable = self._handler_enable
            self._handler_enable = False

            # Get the handler id and name. Note that those might throw
            # exceptions if the ORM attributes they refer to do not exist yet.
            object_id = self.handler_id
            handler_name = self.handler_name
        finally:  # make sure we set _handle_enable to its previous state
            self._handler_enable = old_handler_enable

        if not object_id or not handler_name:  # No unique id, no handler
            return None

        handler_key = (object_id, handler_name)

        # Make sure this subclass has its own registery of handlers.
        # We use .__dict__ to avoid accessing a superclass version of it
        if '_handler_instance_registry' not in type(self).__dict__:
            type(self)._handler_instance_registry = {}

        # If the key exists in the handler registry, retreive the handler
        # from it
        if handler_key in self._handler_instance_registry:
            logger.info(
                "%r: Reusing registered handler for handler key (%s, %s)" %
                (self, object_id, handler_name))
            handler = self._handler_instance_registry[handler_key]
            self._handler = handler
            handler.hwm_update(self)
            return handler

        # If not, let's create a handler by looking up the handler class
        # in the handler class registry.
        if handler_name in self._handler_class_registry:
            handler_class = self._handler_class_registry[handler_name]
            logger.info(
                "%r: Handler key (%s, %s) does not exist. "
                "Creating a new handler %s" %
                (self, object_id, handler_name, handler_name))
            handler = handler_class(parent_getter=self.self_getter())
            # register the handler for this instance
            type(self)._handler_instance_registry[handler_key] = handler
            self._handler = handler
            handler.hwm_update(self)
            return handler

        # Oops, we could not create a handler
        logger.error("%r: No handler was found with the name '%s.'" %
                     (self, handler_name))
        raise NameError("No handler named '%s' was found for %r" %
                        (handler_name, self))

    def __dir__(self):
        """ Return the list of attributes of this class and of those of the
        handler.
        """
        h = self.handler
        return list(
            set(self.__dict__.keys()) |
            set.union(*[set(dir(cls)) for cls in type(self).mro()]) |
            set(dir(h) if h else []))

    def __getattr__(self, name):
        """ Return the value of an attribute if it exists in the handler """
        logger = logging.getLogger(__name__)
        # logger.info("%s: calling __getattr__('%s') with enable=%s" % (type(self).__name__, name, self._handler_enable))

        # __getattr__ will be called if *properties* fail with AttributeError.
        # We don't want to look up some of those in the handler.
        if name in ['handler', 'handler_id', 'handler_name']:
            logger.warn("%s: '%s' property raised an AttributeError" %
                        (type(self).__name__, name))
            raise AttributeError

        if name in ['_sa_instance_state']:
            raise AttributeError

        # self._check_for_local_attribute_corruption()  # Temporary. See method.

        # Exceptions in the handler getting code means something is wrong.
        # Promote AttributeErrors to RuntimeErrors, to make sure these errors
        # don't pass as a benign 'attribute not present' exception. Note that
        # hasattr() ignores the RuntimeError in Python 2.7.
        try:
            h = self.handler
        except AttributeError:  # Re-raise, but preserve traceback info
            raise RuntimeError, sys.exc_info()[1], sys.exc_info()[2]
        if h:
            try:
                old_parent_enable = h._parent_enable
                h._parent_enable = False
                return getattr(h, name)
            except AttributeError:
                pass
            finally:
                h._parent_enable = old_parent_enable
        # Not found, pass request to next subclass
        # logger.info("%s: handler.%s not found. Calling super." % (type(self).__name__, name))
        try:
            return super(HandlerObject, self).__getattr__(name)
        except AttributeError:
            raise AttributeError("Attribute '%s' cannot be found in %s" %
                             (name, object.__repr__(self)))

    def update_handler(self):
        """ Forces the handler to be reconnected to the HWM object, which also
        allows the handler to update its knowledge of HWM object attributes.
        """
        self._handler = None
        self.handler  # Force handler reconnection and update

    @property
    def handler_id(self):
        """ Default method to get key that identifies uniquely this parent
        instance.

        The default behavior assume that the parent object is a SQLAlchemy ORM
        object which is uniquely identified by a tuple containing the values
        of all its primary keys (which exist only once the object has been
        added to the database).
        """
        return tuple(self.__mapper__.primary_key_from_instance(self))

    @property
    def handler_name(self):
        """ Default method to get handler name associated with this object.

        The default behavior retuns None, which means that we will use the
        last handler registered for this class.
        """
        return None

    # *** JFC: This method will be deleted when we are satisfied that
    #     SQLAlchemy behaves as we expect
    def _check_for_local_attribute_corruption(self):
        """ Debugging method used to check if the ORM object's non-database
        attributes have been corrupted due to SQLAlchemy operations.

        Normally we expect SQLAlchemy to create brand new object instances
        when objects are created, loaded from the database or moved in memory,
        so all non-database local attributes should disappear. If not, this is
        a serious problem as local attributes can change values without our
        knowledge.

        We check for corruption by saving the values of the ORM object primary
        keys in a local attribute, and checking that the values are still the
        same if the attribute exist.
        """
        # print 'checking integrity'
        if not self._handler_enable:
            return
        handler_enabled = self._handler_enable
        self._handler_enable = False
        try:
            primary_key_values = [getattr(self, key.name)
                                  for key in self.__mapper__.primary_key]
        except AttributeError:
            primary_key_values = [None]
        if all(primary_key_values):  # if all primary keys exist
            if hasattr(self, '_primary_key_values') and \
                           self._primary_key_values != primary_key_values:
                message = 'Parent local instance attributes have been corrupted!'
                logger = logging.getLogger(__name__)
                logger.error(message)
                raise RuntimeError(message)
            else:
                self._primary_key_values = primary_key_values
        self._handler_enable = handler_enabled


class HandlerMeta(type):
    """ Automatically register a Handler to its associated parent object when
    the Handler class is defined.

    Every Handler class must define the '__handler_for__' and assign to it the
    parent object to which this handler is associated with. The parent object
    must be a subclass of HandlerObject. If __handler_for__ is None, the
    handler is not registered.

    The Handler class can also define '__handler_name__' and assigning it a
    string defining the handler name. If not specified, the Handler class name
    is used.
    """
    def __init__(cls, classname, bases, dict_):
        logger = logging.getLogger(__name__)

        type.__init__(cls, classname, bases, dict_)

        # Check if __handler_for__ is defined and get its value.
        if not hasattr(cls, '__handler_for__'):
            raise AttributeError(
                "'__handler_for__' must be specified in %r" % classname)
        base = cls.__handler_for__
        if base is not None and not issubclass(base, HandlerObject):
            raise AttributeError(
                "%s defined '__handler_for__'=%r, but the target class "
                "is not inheriting from HandlerObject" %
                (classname, base))

        # Get the handler name. If not defined, use the class name and add a
        # __handler_name__ attribute.
        if '__handler_name__' in dict_ and cls.__handler_name__:
            name = cls.__handler_name__
        else:
            name = classname
            cls.__handler_name__ = name

        # Register the handler class to the HWM object
        if base and name:
            logger.info("%s: Registering to parent object '%s' as '%s'"
                        % (cls.__name__, base.__name__, name))
            base.register_handler(cls, name)
        else:
            logger.info("%s: Was not registered" % (cls.__name__))


class Handler(object):
    """
    Basic generic handler base class. All handlers should be derived from this
    class.

    Be sure to call super(...)._method_name(...) if one of the methods in this
    class or one of its subclass are overriden.
    """
    __metaclass__ = HandlerMeta

    __handler_for__ = None  # Do not register this handler
    __handler_name__ = None

    @classmethod
    def get_handler_name(cls):
        return cls.__handler_name__

    def __init__(self, parent_getter=None, **kwargs):
        self._parent_getter = parent_getter
        self._parent_enable = bool(parent_getter)
        for (name, value) in kwargs.items():
            setattr(self, name, value)

    def get_parent(self):
        return self._parent_getter() if self._parent_getter else self

    def __getattr__(self, name):
        import inspect
        logger = logging.getLogger(__name__)
        ss = '\n'.join("%25s:%3i in %15s(...) --> %s" % (ss[1][-25:],ss[2],ss[3],ss[4]) for ss in inspect.stack()[1:15])
        # logger.info("%s: calling __getattr__('%s'), stack=\n%s" % (type(self).__name__, name, ss))

        if self._parent_getter and self._parent_enable:
            parent = self._parent_getter()
            try:
                old_handler_enable = parent._handler_enable
                parent._handler_enable = False
                logger.info("%s: getting parent.%s" % (type(self).__name__, name))
                return getattr(parent, name)
            except AttributeError:
                logger.info("%s: parent.%s raised an AttributeError, passing to super" % (type(self).__name__, name))
            finally:
                parent._handler_enable = old_handler_enable
        try:
            return super(Handler, self).__getattr__(name)
        except AttributeError:
            raise AttributeError("Attribute '%s' cannot be found in %s" %
                                 (name, object.__repr__(self)))

    def hwm_update(self, parent):
        """ Allow the handler to obtain data from the parent object to which
        it is associated.

        This is called when the handler is created or reconnected to the
        parent, which also happens when the parent object's update_handler()
        method is invoked in the parent object.

        This method is meant to make a local *copy* of the attributes of the
        parent that may be needed for the handler operation. It is very
        important to never store references to any object that may move or
        disappear (such as ORM other objects).
        """
        pass
