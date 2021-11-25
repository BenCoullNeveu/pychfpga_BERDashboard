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

        Crate handler that provides access to the backplane through an
        IceBoard.

        This defines the attributes and methods that are available to all
        Crates (including those inherited from CrateHandler).

        Any attributes added by the user must be accessed after it has been
        ensured that the correct Crate has been instantiated.

        NOTE: attempting to access an unknown attribute might cause an
        infinite recursion loop as Tuber tries to access the master_iceboard
        object that may not already exist.
        """
        if self.serial and not self.part_number:
            raise RuntimeError('Cannot create a generic Crate with a serial number')
        if isinstance(serial, int):  # make sure serial is a string
            serial = f'{serial:03d}'

        super().__init__(serial=serial, **kwargs)
        self.crate_number = crate_number

        self.logger = logging.getLogger(__name__)
        self.logger.debug('%r: Instantiating Crate object' % self)

        self.logger.debug(f"{self!r}: Created {self.__class__.__name__}(serial={serial}, crate_number={crate_number})")

    def __repr__(self):
        # return "Crate(%s)" % self.get_id()[0]
        return '%s(%s)' % (self.__class__.__name__, self.get_id())

    @classmethod
    def get_unique_instance(cls, new_class=None, serial=None, crate_number=None):
        """
        Creates a new Crate instance if one with matching crate_number or
        serial number does not exist, otherwise return an existing one
        augmented with the new serial or crate_number information.

        """
        matching_crates = [
            c for c in cls._instance_registry
            if (crate_number is not None and c.crate_number == crate_number)
            or ((new_class or cls).part_number and serial and c.part_number == (new_class or cls).part_number and c.serial == serial)
            ]
        # print(f'{cls!r}: Found crates {matching_crates}')
        if not len(matching_crates):  # no matching crate, create one
            return (new_class or cls)(serial=serial, crate_number=crate_number)
        elif len(matching_crates) == 1:  # one match, update existing one
            return matching_crates[0].update_instance(new_class=new_class, serial=serial, crate_number=crate_number)
        else:
            raise RuntimeError('Multiple Crates with same keys (should never happen)')

    def update_instance(self, new_class=None,  serial=None, crate_number=None):
        """
        Update the class, serial or crate_number info of specified Crate
        subclass instance. If the class needs to be changed, a new class
        instance is created and the IceBoard references are updated to the new class.

        Parameters:

            new_class


        """
        new_args = dict(
            serial=serial or self.serial,
            crate_number=crate_number if crate_number is not None else self.crate_number)
        if new_class and self.__class__ is not new_class:
            other = new_class(**new_args)
            self.delete_instance()
            other.slot = self.slot  # copy over the slot info
            # Update all IceBoard crate references to the new instance
            for ib in self.get_all_instances('IceBoard'):
                if ib.crate is self:
                    ib.crate = other
            return other
        else:  # otherwise update serial and crate_number
            if serial and not self.part_number:
                raise RuntimeError('Cannot assign a serial number to  generic Crate')
            for k, v in new_args.items():
                setattr(self, k, v)
            return self
