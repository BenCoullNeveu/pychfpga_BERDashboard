""" Provide direct access to the Python modules located in the /python/icecore folder

We redefine the __path__ variable of this module so the user can access the
icecore Python modules without having to specify the whole path. For example, we can do:

    >>> import icecore.iceboard

instead of

    >>> import icecore.python.icecore.iceboard

The contents of the following folders are directly exposed:
    icecore/python/icecore => icecore
    icecore/python/icecore/iceboard => iceboard

"""
__path__=['icecore/python/icecore']
#__path__=['icecore/python/icecore', 'icecore/python/icecore/iceboard']
# from python.icecore import icearray
# from python.icecore import attribute_publisher
# from python.icecore.iceboard import iceboard
# from python.icecore.iceboard import fpgabitfile
# from python.icecore.iceboard import fpga as fpga_firmware

