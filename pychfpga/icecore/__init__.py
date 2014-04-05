""" Exposes the modules we want accessible to the user

Assuming the user can access to top icecore folder, all the icecore functionnalities can be accessed by
    >>> import icecore
which gives access to icecore.icearray, icecore.iceboard etc.

This *won't* allow the user to do:
    >>> import icecore.iceboard # WON'T WORK
because import does not use the 'icecore' object while processing the module path but
"""
from python.icecore import icearray
from python.icecore import attribute_publisher
from python.icecore.iceboard import iceboard
from python.icecore.iceboard import fpgabitfile
from python.icecore.iceboard import fpga as fpga_firmware

