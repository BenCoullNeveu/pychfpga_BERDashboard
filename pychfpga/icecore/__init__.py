# Exposes the class we want accessible to the user
# Assuming the user can access to top icecore folder, all the icecore functionnalities can be accessed by
# >>> import icecore
# which gives access to icecore.IceArray, icecore.IceBoard etc.
from python.icecore.icearray import IceArray
from python.icecore.iceboard.iceboard import IceBoard
from python.icecore.iceboard.fpgabitfile import FpgaBitFile
