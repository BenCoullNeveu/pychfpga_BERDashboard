"""Handler management classes.

Handlers are user-defined classes that are attached to a SQLAlchemy ORM
database object to extend the attributes and methods accessible to that ORM
object. They are typically used to implement application-specific code.

Handlers behave as normal Python objects.  All their instance attributes will
persist until the object is no longer used, as opposed to ORM objects that
might have their non-database attributes erase (or even corrupted) as part of
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

from sqlalchemy.event import listen


class HWMHandlerManager(object):

    """Connects an ORM object to a handler and forwards attribute accesses to it.

    An ORM object only need to inherit from this class in order to have a
    handler that is managed automatically.


    HWMHandlerManager maintains a registry of handler classes and instances and make sure the
    handlers are created and re-linked to the relevant HardwareMap ORM object
    so that the handler's attributes and methods are always available to that
    object even if the ORM object comes in and out of existence at various
    memory locations as part of normal SQLAlchemy operations.


    Handlers classes are registered using the 'register_handler()' class
    method. This is usually done automatically when the Handler class is
    created.

    If someone attemps to access an attribute that does not exist in the HWM
    object, the attribute is fetched from the handler.

    If a current handler is not defined, the manager looks into its handler
    instance registry to find a handler already existing for this ORM instance
    based on a unique key (typically the ORM's primary key). If the handler is
    found, the current handler is set to this one.

    If not, the manager looks into its handler class registry to see if there
    is a handler class that matches the handler name associated with this HWM
    object. The handler name is typically the polymorphic name of the HWM
    object. If a matching  handler class is found, a new handler is created
    and registered.

    Changes to the ORM object are tracked using event listeners. Any change to
    the ORM object invalidate the current handler in order to force the
    handler-instance to be re-linked. This also force the manager to call the
    handler's HWM_update() method so that the handler known about ORM object
    changes and can grab column values if needed.
    """

    # If no instance _handler exist, access to _handler will invoke the data
    # descriptor to create the instance _handler
    _handler = None

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
        # Make sure this class has its own handler registry so we don't access
        # the subclass registry
        if '_handler_class_registry' not in cls.__dict__:
            cls._handler_class_registry = {}

        if not class_name:
            class_name = class_.__name__
        cls._handler_class_registry[class_name] = class_
        logger = logging.getLogger(__name__)
        logger.debug(
            '%r: HWMHandlerManager: Registering Handler %r '
            'under handler_name=%s' %
            (cls, class_, class_name))

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

    def set_handler(self, object_id=None, handler_name=None, **kwargs):
        """
        Sets the handler to be used with this Hardware Map instance uniquely
        identified by 'object_id'. If a handler has been created previously, it
        is reattached, otherwise a new one is created.

        Arguments:
            - tuber_uri: Address used to access remote handlers (typically the
              ARM processor on an iceBoard)
            - core_handler_name: Name of the core handler, (typically a remote
              handler)
            - app_handler_name: Name of the application-specific handler, found
              locally or remotely
            - object_id: ID used to uniquely identify each instance of the
              class. This is preferably linked to a unique hardware serial
              number, but a database primary key can probably be used safely.
        """
        logger = logging.getLogger(__name__)

        logger.info(
            '%r: HWMHandlerManager: setting handler with id=%r and '
            'handler_name=%s, using  arguments %r ' %
            (self, object_id, handler_name, kwargs))

        # we include handler_name to properly handle boards with multiple
        # personnalities
        handler_key = (object_id, handler_name)
        self._handler = None
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
                self._handler = self._handler_instance_registry[handler_key]
                self.update_handler()

            # If not, let's create a handler.
            # If there is a local python class for the specified application
            # handler, create it. We pass it a tuber core handler.
            elif handler_name in type(self)._handler_class_registry:
                handler_class = type(self)._handler_class_registry[handler_name]
                logger.info(
                    '%r: HWMHandlerManager:Creating handler %s' %
                    (self, handler_name))
                self._handler = handler_class(**kwargs)
                # register the handler for this instance
                type(self)._handler_instance_registry[
                    handler_key] = self._handler
                self.update_handler()
            else:
                logger.error(
                    "%r: HWMHandlerManager: No handler was found with the "
                    " name '%s.'" %
                    (self, handler_name))
                raise NameError("No handler named '%s' was found for %r" %
                                (handler_name, self))
                # self._handler = Handler(**kwargs)

        if not self._handler:
            logger.info(
                '%r: HWMHandlerManager: does not have a valid handler (yet)' %
                self)
        else:
            logger.info('%r: HWMHandlerManager: handler is %r' %
                        (self, self._handler))

    def __dir__(self):
        """ Return the list of attributes of this class and of those of the
        handler.
        """
        if not self._handler:
            self.init_handler()
        return list(
            set(self.__dict__.keys()) |
            set.union(*[set(dir(cls)) for cls in type(self).mro()]) |
            set(dir(self._handler) if self._handler else []))

    def __getattr__(self, name):
        """ Return the value of an attribute if it exists in the handler """
        if not self._handler:
            self.init_handler()
        if self._handler:
            return getattr(self._handler, name)
        else:
            raise AttributeError(
                'Unknown attribute %s for %r. This could be because this '
                'instance has no valid handler yet' % (name, self))

    def update_handler(self):
        """ Calls the hwm_update() method of the handler with this hardware
        mapped object as an argument to inform on changes in the database
        object.
        """
        if hasattr(self._handler, 'hwm_update'):
            self._handler.hwm_update(self)

    def __init__(self, *args, **kwargs):
        # logger = logging.getLogger(__name__)
        # logger.debug('HWMHandlerManager: calling __init__ for %r' % (self))
        # self.init_handler()
        # This essentially call object.__init(), so there are no  parameters to
        # pass.
        super(HWMHandlerManager, self).__init__()

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
        primary_key_values = [getattr(self, key.name)
                              for key in self.__mapper__.primary_key]
        self.set_handler(object_id=primary_key_values, handler_name=self._cls)

    @classmethod
    def __declare_last__(cls):
        """Define the event listeners that let the system know that the handler
        needs to be refreshed.

        __declare_last__ is a special SQLAlchemy class method that is called
        when the class definition is complete.
        """

        def _hwm_init_event(instance, event_name):
            logger = logging.getLogger(__name__)
            logger.debug("%r: HWMHandlerManager: Init Event '%s' " %
                         (instance, event_name))
            # invalidate the handler, so it will be created
            instance._handler = None

        listen(cls, 'load', lambda target,
               context: _hwm_init_event(target, event_name='load'))
        # useless: it is called before the object's attribute are populated
        listen(cls, 'init', lambda target, *args, **
               kwargs: _hwm_init_event(target, event_name='init'))
        listen(cls, 'refresh', lambda target, context,
               attrs: _hwm_init_event(target, event_name='refresh'))
        listen(cls, 'after_update', lambda mapper, connection,
               target: _hwm_init_event(target, event_name='after_update'))
        # add after_insert?


class HandlerMeta(type):
    """ Intercept the creation of a Handler subclass to automatically register
    it with the associated HWM object.

    The Handler subclass must define the following attributes:

        - __handler_for__ = HWM_object #  HWM object to which this handler is
          associated with. HWM_object must be a subclass of HWMHandlerManager.

        - __handler_name__ = 'some string' #  The name under which the handler
          can be found. If not specified, the Handler class name is used.
    """
    def __init__(cls, classname, bases, dict_):
        logger = logging.getLogger(__name__)
        # logger.debug('%r: Calling meta' % cls)
        type.__init__(cls, classname, bases, dict_)
        if '__handler_for__' not in dict_:
            raise AttributeError(
                "'__handler_for__' must be specified in Handler class %r"
                % classname)
        base = cls.__handler_for__

        if '__handler_name__' in dict_ and dict_['__handler_name__']:
            name = cls.__handler_name__
        else:
            name = classname
            cls.__handler_name__ = name
            # print '%r: %s has no handler name. Use %s' % (cls, classname, name) # *** JFC debug

        logger.debug(
            "%r: Registering to %r under handler_name '%s'"
            % (cls, base, name))

        if base and name:
            if not issubclass(base, HWMHandlerManager):
                raise AttributeError(
                    "%s defined '__handler_for__'=%r, but the target class "
                    "is not a superclass of HWMHandlerManager" %
                    (classname, base))
            base.register_handler(cls, name)
        # cls.__handler_name__ = name
        # print 'After init, class %s has name %s' % (base, name)


class Handler(object):

    """
    Basic generic handler base class. All handlers should be derived from this
    class.
    """
    __metaclass__ = HandlerMeta

    __handler_for__ = None
    __handler_name__ = None

    def __init__(self, **kwargs):
        """ Initialize a basic handler.

        By convention, all handlers __init__() only take keyword arguments to
        ensure consistency across the super/subclass hierarchy.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Handler: Instantiating Handler for %r' % (self))
        super(Handler, self).__init__(**kwargs)

    def hwm_update(self, hwm_object):
        """ Is called when the Hardware Map object might have changed to
        reflect those changes in the handler. The superclass mush redefine
        this and can use super(). This class is mainly provided to allow safe
        super() calls.
        """
        pass
