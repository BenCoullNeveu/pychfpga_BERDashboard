# Standard Python packages
import logging

# Local packages
from .motherboard import Motherboard
from .async_utils import run_async, async_to_sync
from .hardware_map import HardwareMap


class Mezzanine(HardwareMap):
    """
    Provides the basic methods needed to operate a mezzanine.
    """


    # We don't define class and instance registries as we don't track mezzanines separately from the motherboards. 

    part_number = None
    _ipmi_part_numbers = None  # Must match part number in IPMI data


    def __init__(self, serial=None, mezzanine=None, iceboard=None):
        self.logger = logging.getLogger(__name__)
        self.serial = serial
        self.mezzanine = mezzanine  # mezzanine slot number on IceBoard
        self.iceboard = iceboard  # carrier IceBoard object

    def get_id(self):
        """ Return a string that identifies uniquely the mezzanine board.
        Comprises the model number and the serial number.
        """
        return f'{self.part_number}_SN{self.serial}'

