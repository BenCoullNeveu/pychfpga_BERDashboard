"""icecrate_handler.py module: Provides a class to access the hardware of ICE backplane (McGill Model MGK7BP).
"""

import logging

from ..icecore import IceCrateHandler


# This class is necessarily loaded *after** IceCrateHandler, as it was
# imported above in the icecrate module. So this handler overrides the
# standard IceCrate handler since it uses the same handler name as the default
# handler.
class IceCrateHandlerExt(IceCrateHandler):
    """ IceCrate handler that provides access to the backplane through the IceBoard's 'bp' object:
    """

    __handler_name__ = IceCrateHandler.__handler_name__ # Overrides the standard IceCrate handler

    def __getattr__(self, name):
        """ Fetches attributes from the master iceboard's backplane handling object 'bp'
        """
        if self.master_iceboard:
            return getattr(self.master_iceboard.bp, name)
        else:
            return AttributeError("%r does not have an attribute '%s'" % (self, name))

    def __dir__(self):
        class_attributes = [item  for class_ in type(self).mro() for item in dir(class_)]
        instance_attributes = self.__dict__.keys()
        backplane_attributes = dir(self.master_iceboard.bp) if self.master_iceboard else []
        return list(set(class_attributes + instance_attributes + backplane_attributes))






































