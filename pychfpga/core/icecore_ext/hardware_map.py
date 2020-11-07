class HardwareMap(dict):

    def __init__(self, *args, **kwargs):
        super().__init(*args, **kwargs)

    def query(self, obj_type):
        return [obj for obj in self.values() if isinstance(obj, obj_type)]

    def add(self, obj):
        key = (obj.part_number, obj.serial)
        self[key] = obj

    def flush(self):
        pass

    def commit(self):
        pass

    @classmethod
    def get_class(cls, part_number):
        return cls._class_registry__.get(part_number, None)

    @classmethod
    def get_registered_classes(cls, baseclass=object):
        return [c for c in cls._class_registry__.values() if issubclass(c, baseclass)]



def register_class():
    """
    Class decorator that adds a hardware map resource to the hardwareMap
    class registry.
    """
    def decorator(cls):
        cls._class_registry[cls.part_number] = cls
        return cls
    return decorator

def get_class_by_part_number(cls, part_number):
        new_class = cls._class_registry.get(part_number, None)
        return new_class

def get_class_by_name(cls, name):
        classes_by_name = {c. __name__: c for c in cls._class_registry.values()}
        return classes_by_name.get(name, None)

def get_unique_class_instance(cls, serial, **kwargs):
    if (cls.part_number, serial) in cls._instance_registry:
        return cls._instance_registry[(cls.part_number, serial)]
    else:
        # new_class = get_class(cls, cls.part_number)
        cls._instance_registry[(cls.part_number, serial)] = obj = cls(serial=serial, **kwargs)
        return obj
def get_all_class_instances(cls):
        return list(cls._instance_registry.values())

def get_all_classes(cls):
        return list(cls._class_registry.values())