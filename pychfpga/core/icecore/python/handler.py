"""Handler management classes.

A Handler is a Python objects that is attached to a SQLAlchemy ORM database
object to extend its attributes and methods. They are typically used to
implement application-specific code that need to store data in persistent,
non-database attributes.

Handlers behave as normal Python objects.  All their instance attributes will
persist until the object is no longer used, as opposed to ORM objects that
might have their non-database attributes erased as part of
the background operation of the ORM engine. This, for instance, allows the
handler to store hardware state information, opened sockets or other runtime-
specific information that should not live in the database.

Handlers instances are created only once when an instance of an ORM object is
first created or loaded from database, and are reattached to that ORM as that
object is moved in and out of memory as part of the standard ORM management
engine operations.

Multiple Handler classes can be registered to an ORM class.

This module exposes the following classes:

    - HWMHandlerManager: is inherited by an HWM ORM object to which we want to
      associate a handler. The class ensures the handler is reconnected to the
      object, and forwards HWM object attribute accesses to the handler.

    - Handler: is inherited by the application-specific handler. The class
      registers the handler to the ORM object, and provides means for the ORM
      information to be passed to it.
"""

import logging
import collections

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

    The parent object only need to inherit from this class and define
    'handler_id' and 'handler_name' in order to have handler that is
    automatically managed.

    The default 'handler_id' assumes the parent is a SQLAlchemy ORM object and
    will use the primary keys as a unique instance id.

    The default 'handler_name' refers to the last Handler to be defined for
    this particular parent object. This works only if the user intends to use
    a single handler for this parent object.
    """

    # Default fallback values for new objects (prevents infinite recursive
    # __getattr__)
    _handler = None
    _handler_enable = True

    @classmethod
    def register_handler(cls, class_, class_name):
        """ Register a Python class 'class_' as a handler named 'class_name'
        for the target Hardware Map object.
        """
        # Make sure this class has its own handler registry so we don't access
        # the registry from a superclass. We keep track of the registeration
        # order with an OrderedDict so we can use the last registered class by
        # default.
        if '_handler_class_registry' not in cls.__dict__:
            cls._handler_class_registry = collections.OrderedDict()

        # Add the class to the registry
        cls._handler_class_registry[class_name] = class_

    @property
    def handler(self):
        """ Return the current handler for this Hardware Map instance. Also cache the handler value for fast access.
        """
        if not self._handler_enable:
            return None
        elif self._handler:  # Return cached value if available
            return self._handler
        else:
            # The following is called only when the handler is new, was lost
            # because of SQLAlchemy operations or because we forced it. It should
            # not happen often.
            self._handler = self._get_handler()
            return self._handler

    def _get_handler(self):
        """ Return the handler to be used with this Hardware Map instance.

        'object_id' is the key that uniquely identifies the HWM object
        instance.

        If the handler already exists handler instance registry under the
        'object_id' key, then this handler is returned.

        If no handler exist in the handler instance registry, a new one is
        created by looking up the handler class registry for 'handler_name'.
        All additional keywords parameters are passed to the handler
        constructor. If no handler is found in the class registry, an error is
        raised.
        """
        # self._check_for_local_attribute_corruption()

        logger = logging.getLogger(__name__)

        # Get the handler id and name.
        # We temporarily disable handler access while accessing
        # handler_id and handler_name to avoid causing
        # infinite recursion loops (especially in in __getattr__)
        try:
            old_handler_enable = self._handler_enable
            self._handler_enable = False
            object_id = self.handler_id
            handler_name = self.handler_name
        except:
            raise
        finally:  # Make sure we always re-enable handler access
            self._handler_enable = old_handler_enable

        logger.info(
            '%r: HWMHandlerManager: setting handler with id=%r and '
            'handler_name=%s' %
            (self, object_id, handler_name))

        if object_id and handler_name:

            # Make sure the top superclass has its own registery of handlers.
            # We use .__dict__ to ensure we do not access the subclass version
            # of the attribute
            if '_handler_instance_registry' not in type(self).__dict__:
                type(self)._handler_instance_registry = {}

            handler_key = (object_id, handler_name)

            # If the key exists in the handler registry, retreive the handler
            # from it
            if handler_key in self._handler_instance_registry:
                logger.info(
                    '%r: HWMHandlerManager: Reusing registered handler' % self)
                handler = self._handler_instance_registry[handler_key]
                handler.hwm_update(self)
                return handler
            # If not, let's create a handler by looking up the handler class
            # in the handler class registry.
            elif handler_name in type(self)._handler_class_registry:
                handler_class = type(self)._handler_class_registry[handler_name]
                logger.info(
                    '%r: HWMHandlerManager:Creating handler %s' %
                    (self, handler_name))
                new_handler = handler_class()
                # register the handler for this instance
                type(self)._handler_instance_registry[handler_key] = new_handler
                new_handler.hwm_update(self)
                return new_handler
            else:
                logger.error(
                    "%r: HWMHandlerManager: No handler was found with the "
                    " name '%s.'" %
                    (self, handler_name))
                raise NameError("No handler named '%s' was found for %r" %
                                (handler_name, self))
        else:  # if we don't have a valid handler key
            logger.info(
                '%r: HWMHandlerManager: does not have a valid handler (yet)' %
                self)
            return None

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

        # ** JFC: For debugging. Remove when we are satisfied with this check.
        if self._handler_enable:
            self._check_for_local_attribute_corruption()

        h = self.handler
        if h and hasattr(h, name):
            result = getattr(h, name)
            if callable(result):  # cache callable objects for faster access
                setattr(self, name, result)
            return result
        else:
            sup = super(HandlerObject, self)
            if hasattr(sup, name):
                return getattr(sup, name)
            raise AttributeError("Attribute '%s' cannot be found in %s" % (name, object.__repr__(self)))

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
        handler_enabled = self._handler_enable
        self._handler_enable = False
        try:
            primary_key_values = [getattr(self, key.name)
                                  for key in self.__mapper__.primary_key]
        except AttributeError:
            primary_key_values = [None]
        if all(primary_key_values):  # if all primary keys exist
            if hasattr(self, '_primary_key_values') and self._primary_key_values != primary_key_values:
                message = 'HWM local instance attributes have been corrupted!'
                logger = logging.getLogger(__name__)
                logger.error(message)
                raise RuntimeError(message)
            else:
                self._primary_key_values = primary_key_values
        self._handler_enable = handler_enabled

    def update_handler(self):
        """ Forces the handler to be reconnected to the HWM object, which also
        allows the handler to update its knowledge of HWM object attributes.
        """
        self._handler = None
        self.handler  # Force handler reconnection and update

    @property
    def handler_id(self):
        """ Default method to get key that identifies uniquely this HWM instance.

        The default behavior is to Identify the HWM object instance by a tuple
        containing the values of all its primary keys (which exist only once
        the object has been added to the database).
        """
        return [getattr(self, key.name)
             for key in self.__mapper__.primary_key]

    @property
    def handler_name(self):
        """ Default method to get handler name associated with this object.

        The default behavior is to use the last handler registered for this
        class.
        """

        # Get the handler name of the only available handler (we use __dict__ to check on this class handler registry, not its subclasses)
        if '_handler_class_registry' in type(self).__dict__ and len(self._handler_class_registry) >= 1:
            return self._handler_class_registry.keys()[-1]
        else:
            raise RuntimeError('%r: HWMHandlerManager: The default get_handler() requires that at least one handler be registerd for this object.' % self)


class HandlerMeta(type):
    """ Automatically register a Handler to its associated HWM object when the
    Handler class is defined.

    Every Handler class must define the '__handler_for__' and assign to it the
    HWM object to which this handler is associated with. The HWM object must
    be a subclass of HWMHandlerManager. If __handler_for__ is None, the
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
                "'__handler_for__' must be specified in Handler class %r"
                % classname)
        base = cls.__handler_for__
        if base is not None and not issubclass(base, HandlerObject):
            raise AttributeError(
                "%s defined '__handler_for__'=%r, but the target class "
                "is not a superclass of HWMHandlerManager" %
                (classname, base))

        # Get the handler name. If not defined, use the class name and add a __handler_name__ attribute.
        if '__handler_name__' in dict_ and cls.__handler_name__:
            name = cls.__handler_name__
        else:
            name = classname
            cls.__handler_name__ = name

        # Register the handler class to the HWM object
        logger.debug(
            "%s: Registering handler to HWM object '%s' under the name '%s'"
            % (cls.__name__, base.__name__ if base else None, name))

        if base and name:
            base.register_handler(cls, name)
        # cls.__handler_name__ = name
        # print 'After init, class %s has name %s' % (base, name)


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

    def __init__(self):
        """ Initialize a basic handler.

        By convention, all handlers __init__() only take keyword arguments to
        ensure consistency across the super/subclass hierarchy.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('%r: Instantiating Handler' % (self))
        super(Handler, self).__init__()

    def hwm_update(self, hwm_object):
        """ Allow the handler to obtain data from the HWM object to which it
        is associated.

        This is called when the handler is created or reconnected to the HWM,
        which also happens when the HWM object's update_handler() method is invoked.
        """
        pass
