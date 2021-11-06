from .fpga_bitstream import FPGABitstream

class FPGAFirmware():
    FIRMWARE_URL = None
    PLATFORM_MODEL = None
    _bitstream_cache = {}
    _class_registry = {}  # {class_name:class}


    def __init_subclass__(cls, **kwargs):
        """ Keep track of all created firmware subclasses in __class_registry__"""
        super().__init_subclass__(**kwargs)
        cls._class_registry[cls.__name__] = cls

    @classmethod
    def get_fpga_firmware_class_by_name(cls, name):
        return cls._class_registry[name]

    @classmethod
    def get_bitstream_object(cls):
        url = cls.FIRMWARE_URL
        if url not in cls._bitstream_cache:
            cls._bitstream_cache[url] = FPGABitstream(url)
        cls.bitstream = cls._bitstream_cache[url]
        cls.bitstream.load_bitstream()  # reload bitstream if it has changed
        return cls.bitstream


