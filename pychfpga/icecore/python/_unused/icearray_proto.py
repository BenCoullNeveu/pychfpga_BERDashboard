class IceResource(object):
    """
    Object representing a ressource in the ICEArray. It can be:
        - ICEBoard (through FPGA or ARM)
        - ICEBox (backplane)

    This might end up just being a database record.
    """
    ICEBOARD = 'iceboard'
    ICEBOX = 'icebox'

    #board info
    serial_number = 0 # unique number, used as a database key index
    ressource_type = None
    index = None # slot number
    info = None
    locked = True # if True, we cannot change anything on the board
    parent = None # To associate IceBoxes with ICeBoards?

    # ARM info
    arm_ip_addr = None
    arm_serial_number = None # Its MAC address for now
    arm = None # the actual arm object that provides us services

    #FPGA info
    interface_ip_addr = None
    fpga_ip_addr = None # will become obsolete one day when all comms are done through the arm
    fpga_serial_number = 0
    fpga = None # the actual fpga object that provides us with services
    port = None

    # Iceboard info
    iceboard = None # the iceboard object that defines interface to the hardware resourcces

    protocol = None # TCP, UDP ... might not be needed

    def __str__(self):
        """
        Returns a human-readable string representing this ressource entry
        """
        return '%s ARM IP: %15s S/N: %11s, FPGA IP: %15s S/N: %16x Group: %2i, IF IP: %15s' % (self.ressource_type, self.arm_ip_addr, self.arm_serial_number,  str(self.fpga_ip_addr), self.fpga_serial_number, self.fpga_subarray, str(self.interface_ip_addr))

    def __hash__(self):
        """
        Returns a unique value representing the resource. Is used to allow the object to be used in a set of unique elements.
        """
        if self.serial_number:
            return self.serial_number
        else:
            return 0

    @classmethod
    def keys(cls):
        """
        Returns a list of valid keys used to represent the ICE resource.
        """
        return [key for key in cls.__dict__.keys() if key[0].islower() and key.islower()];

class IceResourceFilter(object):
    """
    Represent a resource database filter rule
    """
    match_criteria = {}

    def __init__(self, *args, **kwargs):
        """
        Creates a filter object.
        """
        self.match_criteria = {}
        for arg in args:
            if isinstance(arg, IceResourceFilter):
                self._add_criteria(arg.match_criteria)
            elif isinstance(arg, dict):
                self._add_criteria(arg)
            else:
                self._add_criteria({'serial_number': arg})
        if kwargs:
            self._add_criteria(kwargs)

    def __iadd__(self, other):
        self._add_criteria(IceResourceFilter(other))
        return self

    # def items(self):
    #     return self.match_criteria.items()

    def _add_criteria(self, new_criteria):
        """
        Adds new elements to the filter.
        """
        for (key, value) in new_criteria.items():
            if not hasattr(IceResource, key):
                raise IceException('Unknown ICE Resource property. Valid properties are \n%s' % '\n'.join(IceResource.keys()))
            # if the item does not exist create it with an empty list
            if key not in self.match_criteria:
                self.match_criteria[key] = []
            # Add the new value to the item
            if isinstance(value, list):
                self.match_criteria[key] += value
            else:
                self.match_criteria[key].append(value)

    def match(self, ice_ressource):
        """
        Determines if the ressource matches  filter. The rules are:
            - If the filter value  is a number, it must match the resource value exactly
            - If the filter is a string but the resource value is a number, the filter must match the hex representation of the resource value
            - Otherwise we attempt to match them as strings.

            String filters are matched as follows:
                 '*' matches any number of characters, and '?' or '.' matches exactly one character.
                 The pattern must match the entire string from beginning to end.
                 The match is case insentivie.
        """
        # resource_filter = IceResourceFilter(*args, **kwargs) # converts the arguments into a filter

        match_status = True
        for (key, test_values) in self.match_criteria.items():
            # if not isinstance(test_values, (list, tuple)):
            #     test_values = [test_values]
            resource_value = getattr(ice_ressource, key)
            key_match = False
            for test_value in test_values:
                if isinstance(test_value, (int, long)):
                    key_match |= (test_value == resource_value)
                elif isinstance(test_value, str):
                    if isinstance(resource_value, (int, long)):
                        resource_value = ('%016x' % resource_value)
                    # convert '*' and '?' into their equivalent regex matching patterns
                    test_value = test_value.replace('*', '.*')
                    test_value = test_value.replace('?', '.')
                    test_value = '^' + test_value + '$' # make sure we match the whole string from beginning to end
                    # print 'testing', resource_value, type(resource_value), 'against ', test_value
                    key_match |= bool(re.match(test_value, resource_value, re.IGNORECASE))
            match_status &= key_match
        return match_status

class AttributeIterator(object):
    """
    Calls a function on multiple iceboards
    Probably should inherit a dict
    """
    data = {}

    def __init__(self, data):
        self.data = data

    def __call__(self, *args, **kwargs):
        r = {}
        for (board, method) in self.data.items():
            # print 'Calling method %s for ressource #%i' % (method, board)
            result = method(*args, **kwargs)
            if result is not None:
                r[board]= result
        if r:
            return type(self)(r)
        else:
            return None

    def __getattr__(self, attr):
        """
        Intercept attribute access (including method calls) and return an object that will iterate and pass the request to the arm or fpga objects.
        """
        # this method is not called if the attribute exists in the class so we don't have to check for that.
        r= {}
        for (board, obj) in self.data.items(): # acessing self.db does not cause call to __getattr__ because it already exists
            if hasattr(obj, attr):
                r[board] = getattr(obj, attr)
                # access_count += 1
        # if not access_count:
        #     raise AttributeError("Attribute '%s' does not exist in the arm or fpga objects" % attr)
        if r:
            return AttributeIterator(r) # wrap the dict in case the list is being called
        else:
            return None

    def __getitem__(self, index):
        return self.data[index]
    def __str__(self):
        return str(self.data)
    def __repr__(self):
        return repr(self.data)
    def __len__(self):
        return len(self.data)
    def values(self):
        return self.data.values()

class IceResourceTable(object):
    """
    Class representing an array of ICE Resources with methods to filter specific elements.
    This is implemented here as a simple list, but it could be implemented using an underlying database system.
    """
    # We need to define all attributes as part of the class so the first assignment to those (in __init__) will be done locally by __setattr__ and will not make it search for those in the arm and fpga objects.
    db = {} # make sure the attribute exists so that __getattr__ and __setattr__ will always see it.
    logger = None

    def __init__(self):
        """
        Creates an empty ICE ressource database.
        """
        self.logger = logging.getLogger(__name__)
        self.db = {}

    def __iter__(self):
        """
        Allows the object to be iterable and have it iterate over all ressource items.
        """
        return iter(self.db)

    def __str__(self):
        """
        Returns a string containing a human-representation of the database.
        """
        return '\n'.join(["%3i : %s" % (serial_number, str(res)) for (serial_number, res) in self.db.items()])

    def __repr__(self):
        return '%s containing \n%s' % (object.__repr__(self), str(self))

    def __add__(self, other):
        """
        Merge two ressource tables.
        """
        if not isinstance(other, IceResourceTable):
            raise TypeError()
        new_table = IceResourceTable()
        new_table.db = self.db + other.self.db
        return new_table

    def __iadd__(self, other):
        if isinstance(other, IceResourceTable):
            self.db.update(other)
        elif isinstance(other, IceResource):
            self.db[other.serial_number] = other
        else:
            raise TypeError('The argument must be an IceResource or IceResourceTable object')
        return self

    def __len__(self):
        """
        Returns the number of entries in the ICE resource database.
        """
        return len(self.db)

    def __getitem__(self, index):
        """

        """
        return self.db[index]

    def __getattr__(self, attr):
        """
        Intercept attribute access (including method calls) and return an object that will iterate and pass the request to the arm or fpga objects.
        """
        # this method is not called if the attribute exists in the class so we don't have to check for that.
        r= {}
        for (serial_number, res) in self.db.items(): # acessing self.db does not cause call to __getattr__ because it already exists
            source_objects = [res.iceboard, res.arm, res.fpga]
            access_count = 0
            for obj in source_objects:
                if hasattr(obj, attr):
                    r[res.serial_number] = getattr(obj, attr)
                    access_count += 1
            if not access_count:
                raise AttributeError("Attribute '%s' does not exist in the arm or fpga objects" % attr)
        if r:
            return AttributeIterator(r) # wrap the dict in case the list is being called
        else:
            return None

    def __setattr__(self, attr, value):
        """
        Intercept attribute setting. Writes to the arm or fpga objects if the attributes exist these, otherwise write it to the local object.

        Todo: should give a warning if an attribute exists in more than one object
        """

        # Set the variable locally if it exists locally.
        # Don't use hasattr(self, attr) because it will call __getattr__ and if the object exist on the arm of fpga it will find it and will return True
        # Dont use vars(self) or self.__dict__ because we want to do a local assignment if the variable exist int he class but not yet in the instance
        if attr in dir(self):
            # print attr, 'is local', locals()
            object.__setattr__(self, attr, value) # don't assign directly to avoid calling __setattr__ recursively
        else:
            assignment_count = 0
            for (serial_number, res) in self.db.items():
                source_objects = [res.iceboard, res.arm, res.fpga]
                for obj in source_objects:
                    if hasattr(obj, attr):
                        # print 'setting ', attr
                        setattr(obj, attr, value)
                        assignment_count += 1
            if not assignment_count:
                raise AttributeError("Attribute '%s' does not exist locally, in the arm or in the fpga objects, so we cannot set its value" % attr)


    def pop(self):
        """
        Removes one element from the database and returns it.
        """
        return self.db.popitem()

    def select(self,*args, **kwargs):
        """
        Selects (i.e. filter) specific elements of the Ressource Table and returns the filtered table.
        This is a very brain dead way of doing this.
        """
        if args or kwargs:
            new_table = IceResourceTable()
            resource_filter = IceResourceFilter(*args, **kwargs)
            for (serial_number, resource) in self.db.items():
                if resource_filter.match(resource):
                    new_table += resource
            return new_table
        else:
            return self

    def configure_fpga(self, bitfile):
        """
        Configure the FPGAs on the ICEboard(s)
        """
        # For now we do this the worst possible way: by programming each FPGA one aftet the other.
        # This should be rewritten to allow concurrent programming of all FPGAs, maybe using zeroMQ.

        interfaces=set()
        for res in self.db.values():
            interfaces.add(res.interface_ip_addr)
        if len(interfaces) != 1:
            raise IceException('The code currently supports only one Ethernet interface');
        else:
            interfaces = interfaces.pop()

        self.logger.info('Checking if the FPGAs can be found on the network')
        fpga_serials = fpga.Fpga.discover_fpgas(interfaces)

        # print 'discovered fpgas are ', fpga_serials

        for ice in self.db.values():
            if ice.fpga_serial_number not in fpga_serials:
                self.logger.info('Configuring FPGA on board #%i through ARM at address %s' % (ice.serial_number, ice.arm_ip_addr))
                if ice.locked:
                    IceException('Iceboard with serial %016X is locked and its FPGA cannot be configured' % ice.serial_number)
                # arm_ = arm.Arm(ice.arm_ip_addr)
                ice.arm.configure_fpga(bitfile)
            else:
                self.logger.info('FPGA on board #%i,  ARM address %s is already configured. Skipping configuration' % (ice.serial_number, ice.arm_ip_addr))

        self.logger.info('Checking again what FPGAs are on the network')
        fpga_serials = fpga.Fpga.discover_fpgas(interfaces)

        self.logger.info('Instantiating FPGAs and IceBoards')

        for (serial_number, ice) in self.db.items():
            if ice.fpga_serial_number not in fpga_serials:
                self.logger.error('Failed to find FPGA on board #%i' % (serial_number))
            else:
                self.logger.info('Creating FPGA and Iceboard handlers for board #%i' % (serial_number))
                if ice.fpga:
                    ice.fpga.close()
                ice.fpga = fpga.Fpga(ice.interface_ip_addr, ice.fpga_ip_addr, ice.fpga_port, serial_number = ice.fpga_serial_number) # here we need the serial number because we use the FPGA Ethernet interface.
                if ice.iceboard:
                    ice.iceboard.close()
                ice.iceboard = iceboard.IceBoard(ice.arm, ice.fpga)
            # arm_.close()
    def close(self):
        """
        Close all ressources.
        """
        for (serial_number, ice) in self.db.items():
            self.logger.info('Closing FPGA and Iceboard handlers for board #%i' % (serial_number))
            if ice.fpga:
                ice.fpga.close()
                ice.fpga = None
            if ice.arm:
                ice.arm.close()
                ice.arm = None
            if ice.iceboard:
                ice.iceboard.close()
                ice.iceboard = None


class IceObjects:
    """
    Represents a list of ICE resources that can be used to access ATM of FPGA methods directly.
    """

    db = {}

    def __init__(self, resource_table):
        self.db = resource_table.db

    def __str__(self):
        """
        Returns a string containing a human-representation of the database.
        """
        # return '\n'.join([str(res) for res in self.db])
        return 'IceObject'
    def __repr__(self):
        return repr(self.db)
