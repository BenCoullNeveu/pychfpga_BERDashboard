""" attribute_publisher module.

This module provides a base class that allow the data attributes (i.e. non-
callable attributes) and methods (i.e.callable attributes) of a class to be
accessed directly as attributes of another class. The result is similar to
inheritance, but can be implemented dynamically.

Access to the attributes can be obtained in two ways:

   1) The parent can redefine its __get_attr__ to redirect access to one of the AttributePublisher-derived class
   2) The parent can call AttributePublisher.import_attributes(self) to add the attributes to itself.

"""
import logging



class AttributeUser(object):
    """
    Allows the use of published attributes in a class.
    """
    _registered_objects = {}  # Dictionary containing all the object attributes attributes accessible directly from this class. Works in tandem with __get_attr__

    def __getattr__(self, name):
        """
        Forward attribute access to one of the registered object.

        Reminder: __get_attr__ is not called if the attribute is found in the
        class
        """
        if name not in self._registered_objects:
            AttributeError('The attribute %s cannot be found in any object registered with this class' % name)
        obj = self._registered_objects[name]
        return getattr(obj, name)


    def __dir__(self):
        """
        """
        return type(self).__dict__.keys() + self.__dict__.keys() + self._registered_objects.keys()

    def register(self, obj, get_attributes_func=None, import_methods = True):
        """
        Register an object so its 'published' attributes can be accessed
        as if they were attributes of the object 'self'.

        If the 'get_attributes_func' dunction is provided,  it is called to obtain the list of attributes to publish.
        Otherwise, if the source object has a get_attributes() method, this method is used to get the list.
        If none of those exist, the default attribute list is dir(obj) minus any attributes starting with '_'.

        NOTE: to make access more efficient, we could import the methods
        directly in the target class and use AttributeAccessor for the other
        attributes. But we need to store enough info in the registration table
        so we can find there attributes and delete them from the base class.
        """
        self.logger.warning("Registering attributes from '%s'." % repr(obj))

        if get_attributes_func:
            attribute_names = get_attributes_func(obj)
        elif hasattr(obj, 'get_attributes'):
            attribute_names = obj.get_attributes()
        else:
            attribute_names = [name for name in dir(obj) if name[0] !='_']

        for name in attribute_names:
            name = str(name) # remove unicode encoding
            if name in self._registered_objects:
                self.logger.warning("Attribute collision while registering the attribute '%s'. The attribute will be overriden." % name)
            # value = getattr(obj, name)
            # if import_methods and callable(value): # if this is a method
            #     setattr(self, name, value) # just copy the method in the destination object
            # else:
            self._registered_objects[name] = obj # otherwise add the attribute name and ource object in the dictionnary so __getattr__ can look it up when needed.

    def unregister(self, obj):
        """
        """
        for name,target in self._registered_objects.items():
            if target is obj:
                self.logger.warning("Unregistering attribute %s from '%s' if %s." % (name, target, repr(obj)))
                del self._registered_objects[name]

# The following code is not used
# ------------------------------
class AttributeAccessor(object):
    """
    Data descriptor that forward access to an attribute to another object.
    """
    def __init__(self, target, attribute_name):
        self._target = target
        self._attribute_name = attribute_name
    def __set__(self, value):
        return setattr(self._target, self._name, value)
    def __get__(self):
        return getattr(self._target, self._name)

class AttributePublisher(object):

    def get_attributes(self):
        """
        Default method that returns the list of attributes the class whished
        to make available directly from another class.
        """
        return [name for name in dir(self) if name[0] !='_' and name not in dir(AttributePublisher)]

    def get_data_attributes(self):
        return [name for name in self.get_attributes() if not callable(getattr(self, name))]

    def get_methods(self):
        return [name for name in self.get_attributes() if callable(getattr(self, name))]

    # @classmethod
    def import_attributes(self, target, attribute_list = None, callable_only = True):
        """
        Imports the attributes into the target object.

        If the attribute is callable, the target object is assigned directly
        with the method bound to the source object. Otherwise, the attributes
        are populated as data descriptors that dynamically access the source object.

        if 'callable_only' is True, only the methods are populated in the
        target object. The other attributes must be accessed through a
        __get_attr__ hook in the target object. This allows fast method access
        while keeping dynamic access to data attribute that may change over
        time.

        Note that once imported, access to the attributes won't cause __get_attr__ to be called.

        It is not necessary to use this method if the target object defines a
        __get_attr__ method to redirect attribute accesses to the source
        object.
        """
        if attribute_list is None:
            attribute_names = self.get_attributes()
        else:
            attribute_names = attribute_list

        for name in attribute_names:
            value = getattr(self, name)
            if callable(value):
                setattr(target, name, value)
            elif not callable_only:
                setattr(target, name, AttributeAccessor(self, name))



