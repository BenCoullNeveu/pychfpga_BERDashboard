# standard Python packages
import logging
import asyncio


# local Packages
from .hardware_map import HardwareMap

class Motherboard(HardwareMap):
    """
    Defines a generic motherboard (Iceboard or others) with hardware map
    management methods. A motherboard is uniquely identified by its model
    number and serial number, and has a network hostname.

    A motherboard can optinally be connected to one crate and have multiple mezzanines.
    """

    # Define the class and instance registry that will be used by HardwareMap to track all Motherboard subclass instances.
    # This should *not* be defined in further subclasses.
    _class_registry = {}  # {part_number:class}
    _instance_registry = {}  # {(model,serial):instance}


    # Define the part number associated with this class. This *must* be defined in subclasses.
    part_number = None  # shall be a string in real classes
    _ipmi_part_numbers = None #  list of strings listing all models by which the board can be self-identified (via EEPROM, IPMI, mDNS etc)

    NUMBER_OF_FMC_SLOTS = 0  # Number of supported mezzanines


    def __init__(self, hostname=None, serial=None, slot=None, subarray=None, **kwargs):
        """ Create or update an Motherboard object.

        Do not instantiate hardware map objects directly. 
        Instead use  the get_unique_instance(...) class method to ensure that objects with matching hostname or serial numbers will be reused if available. 


        Parameters:

            hostname (str):  host name or IP address of the board.  If `hostname` is 'None' but the
                instance has a serial number, then the board hostname can
                potentially be resolved using mDNS discovery.

            serial (str or int): Serial number of the board, in the exact
                format that is published by the board. For
                convenience, if `serial` is an integer, it is converted into a
                properly formatted string serial.

            slot (int):  virtual slot number for use of multiple boards in an
                array. A value of  0 or None (i.e. bool(slot) == False)
                indicates that there is no slot information.

            subarray: Arbitrary value that is used to group boards in logical
                categories.


        Notes:

        __init__() only sets the object key parameters and manages the
        hardware map and does not initiate connection with the hardware it
        represents. Indeed, Hardware map objects (and their subclasses) can be
        created and destroyed freely  during the process of hardware map
        creation. __init__() therefore shall not initiate communication with
        the hardware or do complex set-up; this is done by init(), which will
        be called when the hardware map is completed and stable.

        """
        if not serial and not hostname:
            raise ValueError(f'Must specify either a serial number or hostname for {self.__class__.__name__}')

        if isinstance(serial, int):  # make sure serial is a string
            serial = f'{serial:04d}'  # Motherboard serials have 4 digits

        super().__init__(**kwargs)  # pass on the remaining kwargs. crate and mezzanine are cleared.

        self.hostname = hostname
        self.serial = serial
        self.slot = slot
        self.subarray = subarray

        self.crate = None
        self._cached_repr = None  # important to avoid infinite recursions through repr(). Clear on updates to account for the new parameters.
        self.logger = logging.getLogger(__name__)

        self.logger.debug(
            f"{self!r}: Created {self.__class__.__name__}(hostname={hostname}, "
            f"serial={serial}, slot={slot}, subarray={subarray}), "
            f"crate={self.crate}")

    def __repr__(self):
        """ Provides a concise string representation of this Motherboard that is
        informative enough to be used for logs.
        """

        if self._cached_repr:
            return self._cached_repr
        else:
            self._cached_repr = f"{self.__class__.__name__}({self.get_string_id()})"
            return self._cached_repr

    def get_string_id(self):
        """ Return a string that identifies uniquely the Motherboard in the most convenient representation.

        Preference order:

            - (0,3)  # crate 0 , 4th slot (tuples always use zero-based indices)
            - (MGK7BP16_SN025, 3)  # Same, but without crate number info
            - MGK7MB_SN0234 # no crate info at all (even with virtual slot)
            - 10.10.10.244 # motherboard serial number not discovered
            - id=140529531550992 # nothing, last resort

        """
        if self.crate and self.crate.crate_number is not None and self.slot:
            return f"({self.crate.crate_number},{self.slot-1})"
        if self.crate and self.crate.part_number and self.crate.serial and self.slot:
            return f"({self.crate.part_number}_SN{self.crate.serial},{self.slot-1})"
        elif self.serial:
            return f"{self.part_number}_SN{self.serial}"
        elif self.hostname:
            return self.hostname
        else:
            return f"id={id(self)}"


    @classmethod
    def get_unique_instance(cls,
                            new_class=None,
                            serial=None,
                            hostname=None,
                            slot=None,
                            subarray=None,
                            crate_number=None,
                            **kwargs):
        """
        Creates a new Motherboard instance if one with matching hostname or
        serial number does not exist, otherwise return an existing one
        augmented with the new serial or hostname information.

        Existing instances are those who match either the specified hostname
        or part_number/serial number. If no board is found, a new instance of
        class `new_class` is created. Otherwise, the existing instance is
        updated with the parameters  that are not `None`.


        All creation and update operations maintain the integrity of the
        references between Motherboards, Crates and Mezzanines.

        Use this method to create Motherboard objects instead of instantiating
        them directly from the target class in order to maintain the hardware
        map integrity.

        Parameters:

            new_class (Motherboard or subclass): class desired for the returned instance. If None, the class of an existing object is not changed, and a new object is created with the class `cls`

            serial (str): serial number of the Motherboard to look for, and to assign to a new instance or existing matching instance.

            hostname (str): hostname of the Motherboard to look for, and to assign to a new instance or existing matching instance.

            slot (int): slot number in which the board is located in a crate
                or backplane, or virtual slot number if the board is not in a
                crate. Is assigned to the new or existing matching Motherboard.

                If the slot number is changed, the associated IceCrate slot mapping is updated.

            subarray: Arbitrary value used to group Motherboards in logical arrays. Is assigned to new instance or existing matching instance.

            crate_number: For convenience, if `crate_number` is specified, the
                new or existing board is associated with the IceCrate instance
                that matches the specified crate number, or one is created
                with that crate number to hold the desired crate number value.
        """
        # print(f"In et_unique_instance")

        matching_crates = [
            c for c in cls._instance_registry
            if (hostname is not None and c.hostname == hostname)
            or ((new_class or cls).part_number and serial and c.part_number == (new_class or cls).part_number and c.serial == serial)]

        # print(f"Matches: {matching_crates}")
        if not len(matching_crates):  # no matching crate, create one
            # print(f"{cls!r}: Creating Motherboard")
            ib = (new_class or cls)(serial=serial, hostname=hostname, slot=slot, subarray=subarray, **kwargs)
            # print(f"{cls!r}: Updating Motherboard with crate_number={crate_number}")
            return ib.update_instance(crate_number=crate_number)
        elif len(matching_crates) == 1: # one match, update existing one
            return matching_crates[0].update_instance(new_class=new_class, serial=serial, hostname=hostname, slot=slot, subarray=subarray, crate_number=crate_number, **kwargs)
        else:
            raise RuntimeError('Multiple Motherboards with same keys (should never happen)')

    def update_instance(self,
                        new_class=None,
                        serial=None,
                        hostname=None,
                        slot=None,
                        subarray=None,
                        crate_number=None,
                        crate=None,
                        **kwargs):
        """
        Update the class, serial or hostname info of specified Motherboard
        subclass instance. If the class needs to be changed, a new class
        instance is created and the Motherboard references are updated to the new class.

        Paremeters:

        """
        serial = serial or self.serial
        hostname = hostname or self.hostname
        slot = slot if slot is not None else self.slot
        subarray = subarray if subarray is not None else self.subarray
        crate_number = crate_number if crate_number is not None else self.crate.crate_number if self.crate else None

        if new_class and self.__class__ is not new_class:
            other = new_class(serial=serial, hostname=hostname, slot=slot, subarray=subarray, **kwargs)
            self.logger.debug(f"{self!r}: Updating newly created instance...")
            other.update_instance(crate_number=crate_number, crate=self.crate) # update crate and backrefs
            # Update Mezzanine references to the new instance
            for fmc, mezz in self.mezzanine.items():
                other.mezzanine[fmc] = mezz
                mezz.iceboard = other
            self.delete_instance()
            return other
        else:  # otherwise update serial and hostname
            if kwargs:
                raise NotImplementedError(f'Cannot update existing {self.__class__.__name__} instance with additional keyword arguments {kwargs}')
            self.hostname = hostname
            self.serial = serial
            self.subarray = subarray
            # remove previous crate backref if it exists
            if self.crate and self.slot:
                self.crate.slot.pop(self.slot, None)
            # Assign new slot
            self.slot = slot
            # eattach crate by crate number if specified
            self.logger.debug(f"{self!r}: Updating with with crate_number={crate_number}...")
            if crate_number is not None:
                self.crate = IceCrate.get_unique_instance(crate_number=crate_number)
            elif crate:
                self.crate = crate
            # Create new crate backref
            if self.crate and self.slot:
                self.crate.slot[self.slot] = self

            self._cached_repr = None  # Clear on updates to account for the new parameters.
            return self


    def set_cache(self):
        """ Caches key values to accelerate the code.
        """
        self._cached_repr = None
