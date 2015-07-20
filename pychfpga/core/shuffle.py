"""
shuffle.py module
    Implements interface to the backplane or intercrate shuffle module

History:
    2013-10-29 : JFC : Created
"""
import xglink

from Module import BitField

# Types of memory-mapped registers
CONTROL = BitField.CONTROL
STATUS = BitField.STATUS
DRP = BitField.DRP


class Shuffle(xglink.XGLinkArray):
    """ Instantiates an object that represents the backplane shuffle

    A backplane shuffle object is a pure xglink_array object, so nothing is added to the class.
    """
    pass
