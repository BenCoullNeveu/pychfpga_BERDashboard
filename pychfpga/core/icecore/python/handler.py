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
import hardware_map

# from sqlalchemy.event import listen


class HWMHandlerManager(object):

    """Connects an ORM object to a handler and forwards attribute accesses to it.

    An ORM object only need to inherit from this class in order to have a
    handler that is managed automatically.


    HWMHandlerManager maintains a registry of handler classes and handler
    instances and make sure the handlers are created and re-linked to the
    relevant HardwareMap ORM object. The handler is thus always available even
    if the ORM object comes in and out of existence at various memory
    locations as part of normal SQLAlchemy operations.

    The manager looks into its handler instance registry to find a handler
    already existing for this ORM instance based on a unique key.

    If not, the manager looks into its handler class registry to see if there
    is a handler class that matches the handler name associated with this HWM
    object. The handler name is typically the polymorphic name of the HWM
    object. If a matching  handler class is found, a new handler is created
    and registered.

    HWMHandlerManager defines __getattr__ and __setattr__ so that  handler's
    attributes and methods can be accessed as if they were part of the ORM
    object.

    Handlers classes are registered using the 'register_handler()' class
    method. This is usually done automatically when the Handler class is
    created.
    """

    # If no instance _handler exist, access to _handler will invoke the data
    # descriptor to create the instance _handler
    _handler = None
    _handler_enable = True

    @classmethod
    def register_handler(cls, class_, class_name):
        """ Register a Python class 'class_' as a handler named 'class_name'
        for the target Hardware Map object.

        This handler will be used as an application handler if its name
        matches the name provided with set_handler(), otherwise a tuber
        handler will be used.

        If the handler is passed a core handler at initialization, it must
        make visible the methods and attributes of this core object.
        """
        # Make sure this class has its own handler registry so we don't access
        # the subclass' registry
        if '_handler_class_registry' not in cls.__dict__:
            cls._handler_class_registry = {}

        # Add the class to the registry
        cls._handler_class_registry[class_name] = class_

        # logger = logging.getLogger(__name__)
        # logger.debug(
        #     '%r: HWMHandlerManager: Registering Handler %r '
        #     'under handler_name=%s' %
        #     (cls, class_, class_name))

    @property
    def handler(self):
        """ Return the current handler for this Hardware Map instance.
        """
        # This is a shortcut to speed-up access
        if self._handler_enable and self._handler:
            return self._handler
        if not self._handler_enable:
            return None

        # The following is called only when the handler is new, was lost
        # because of SQLAlchemy operations or because we forced it. It should
        # not happen often.

        # We temporarily disable handler access while calling
        # get_handler() so it can access attributes without causing
        # infinite recursion loops
        handler_enable = self._handler_enable
        self._handler_enable = False
        try:
            self._handler = self.get_handler()
        except AttributeError:
            self._handler = None
            raise AttributeError
        finally:
            self._handler_enable = handler_enable
            return self._handler

    def _get_handler(self, object_id=None, handler_name=None, **kwargs):
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

        logger.info(
            '%r: HWMHandlerManager: setting handler with id=%r and '
            'handler_name=%s, using  arguments %r ' %
            (self, object_id, handler_name, kwargs))

        # we include handler_name to properly handle boards with multiple
        # personnalities
        handler_key = (object_id, handler_name)

        if object_id and handler_name:

            # Make sure the top superclass has its own registery of handlers.
            # We use .__dict__ to ensure we do not access the subclass version
            # of the attribute
            if '_handler_instance_registry' not in type(self).__dict__:
                type(self)._handler_instance_registry = {}

            # If the key exists in the handler registry, retreive the handler
            # from it
            if handler_key in self._handler_instance_registry:
                logger.info(
                    '%r: HWMHandlerManager: Reusing registered handler' % self)
                new_handler = self._handler_instance_registry[handler_key]
                new_handler.hwm_update(self)
                return new_handler
            # If not, let's create a handler by looking up the handler class
            # in the handler class registry.
            elif handler_name in type(self)._handler_class_registry:
                handler_class = type(self)._handler_class_registry[handler_name]
                logger.info(
                    '%r: HWMHandlerManager:Creating handler %s' %
                    (self, handler_name))
                new_handler = handler_class(**kwargs)
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
        else: #  if we don't have a valid handler key
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

        if self._handler_enable:
            self._check_for_local_attribute_corruption()
        # logger = logging.getLogger(__name__)
        # import inspect, os
        # # # logger.debug('%r: getattr: handler_enable is %s' % (self, self._handler_enable))
        # tracebackString = '\n'.join([
        #     '    %s in .../%s:%i' %
        #     (fn, os.path.split(filename)[1], line) for
        #     (__, filename, line, fn, code,__) in inspect.stack()])
        # logger.debug("getattr: %s is getting '%s'\n%s" % (type(self), name,  tracebackString))

        # Quick access bypass: catch most of the calls.
        # if self._handler_enable and self._handler:
        #     return getattr(self._handler, name)

        h = self.handler
        if h:
            result = getattr(h, name)
            if callable(result):  # cache callable objects for faster access
                setattr(self, name, result)
            return result
        else:
            # JFC: I used to associate am AttributeError message that includes
            # the repr of the failing object, but this repr can potentially
            # check for non-existing attributes (like 'crate') which creates
            # an infinite loop. So we stick with a plain AttributeError.
            raise AttributeError

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


    def get_handler(self):
        """ Default method to get the handler for this object.

        This method shall return the handler obtained by calling
            self._get_handler(object_id=..., handler_name=..., kwarg1, kwarg2... )

        The user shall override this method to specify the parameter that
        uniquely identified the HWM object instance (object_id), and if no
        handler already exist, what is the name of the target handler class
        (handler_name) and what keyword arguments to pass during its creation
        (kwargs1, kwargs2...).

        The default behavior is to:
            - Identify the HWM object instance by its primary keys (which
               exist only once the object has been added to the database).
            - Use the name of the only handler registered for this HWM object.
              If there are more than one registerd handler, raise an exception.
            - Pass no additional argument to the handler initializer.

        See the IceBoard.get_handler() for an example.
        """
        # get a unike instance ID based on the value of all primary keys
        object_id = [getattr(self, key.name)
                     for key in self.__mapper__.primary_key]

        # Get the handler name of the only available handler (we use __dict__ to check on this class handler registry, not its subclasses)
        if '_handler_class_registry' in type(self).__dict__ and len(self._handler_class_registry) == 1:
            handler_name = self._handler_class_registry[0]
        else:
            raise RuntimeError('%r: HWMHandlerManager: The default get_handler() requires that exactly one handler be registerd for this object.' % self)

        return self._get_handler(object_id=object_id,
                                 handler_name=handler_name)

    # @classmethod
    # def __declare_last__(cls):
    #     """Define the event listeners that let the system know that the handler
    #     needs to be refreshed.

    #     __declare_last__ is a special SQLAlchemy class method that is called
    #     when the class definition is complete.
    #     """

    #     def _hwm_init_event(instance, event_name):
    #         logger = logging.getLogger(__name__)
    #         logger.debug("%r: HWMHandlerManager: Init Event '%s' " %
    #                      (instance, event_name))
    #         # invalidate the handler, so it will be created
    #         instance._handler = None

    #     listen(cls, 'load', lambda target,
    #            context: _hwm_init_event(target, event_name='load'))
    #     # useless: it is called before the object's attribute are populated
    #     listen(cls, 'init', lambda target, *args, **
    #            kwargs: _hwm_init_event(target, event_name='init'))
    #     listen(cls, 'refresh', lambda target, context,
    #            attrs: _hwm_init_event(target, event_name='refresh'))
    #     listen(cls, 'after_update', lambda mapper, connection,
    #            target: _hwm_init_event(target, event_name='after_update'))
    #     # add after_insert?


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

        # Check if __handler_for__ is defined and get its value. We look it up
        # in dict_ and not cls to make sure it is defined in this new
        # superclass, not a subclass
        if '__handler_for__' not in dict_:
            raise AttributeError(
                "'__handler_for__' must be specified in Handler class %r"
                % classname)
        base = cls.__handler_for__
        if base is not None and not issubclass(base, HWMHandlerManager):
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
    class or one of its superclass are overriden.
    """
    __metaclass__ = HandlerMeta

    __handler_for__ = None  # Do not register this handler
    __handler_name__ = None

    def __init__(self, **kwargs):
        """ Initialize a basic handler.

        By convention, all handlers __init__() only take keyword arguments to
        ensure consistency across the super/subclass hierarchy.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('%r: Instantiating Handler' % (self))
        super(Handler, self).__init__(**kwargs)

    def hwm_update(self, hwm_object):
        """ Allow the handler to obtain data from the HWM object to which it
        is associated.

        This is called when the handler is created or reconnected to the HWM,
        which also happens when the HWM object's update_handler() method is invoked.
        """
        pass
