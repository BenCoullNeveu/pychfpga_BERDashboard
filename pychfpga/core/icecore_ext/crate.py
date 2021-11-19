# Standard library packages
import logging

# Local packages
from .hardware_map import HardwareMap


class Crate(HardwareMap):
    """Base class for all HardwareMap-managed crates. 

    """
    # Define the class and instance registries that will be used by all subclasses.
    _class_registry = {}  # {part_number:class}
    _instance_registry = {}  # {(model,serial):instance}
    crate_number = None

    NUMBER_OF_SLOTS = 0

    def __init__(self, serial=None, crate_number=None, **kwargs):
        """ Create all the objects needed to interface the backplane hardware.

        __init__ should only passively create objects. It must not attempt to
        access methods provided by the ARM as the Crate may be created before
        IceBoards are associated to it.

        IceCrate handler that provides access to the backplane through an
        IceBoard.

        This defines the attributes and methods that are available to all
        IceCrates (including those inherited from IceCrateHandler).

        Any attributes added by the user must be accessed after it has been
        ensured that the correct IceCrate has been instantiated.

        NOTE: attempting to access an unknown attribute might cause an
        infinite recursion loop as Tuber tries to access the master_iceboard
        object that may not already exist.
        """
        if self.serial and not self.part_number:
            raise RuntimeError('Cannot create a generic IceCrate with a serial number')
        if isinstance(serial, int):  # make sure serial is a string
            serial = f'{serial:03d}'

        super().__init__(serial=serial, **kwargs)
        self.crate_number = crate_number

        self.logger = logging.getLogger(__name__)
        self.logger.debug('%r: Instantiating IceCrate object' % self)

        self.logger.debug(f"{self!r}: Created {self.__class__.__name__}(serial={serial}, crate_number={crate_number})")

    def __repr__(self):
        # return "IceCrate(%s)" % self.get_id()[0]
        return '%s(%s)' % (self.__class__.__name__, self.get_id())

