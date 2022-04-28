from .fpga_bitstream import FPGABitstream

class FPGAFirmware():
    # FIRMWARE_URL = None
    # PLATFORM_MODEL = None
    _bitstream_cache = {}
    _class_registry = {}  # {class_name:class}

    PLATFORM_SUPPORT = {} # Indicates the platform/config-specific bitstream filename and parameters. Overriden by subclasses

    def __init_subclass__(cls, **kwargs):
        """ Keep track of all created firmware subclasses in __class_registry__"""
        super().__init_subclass__(**kwargs)
        cls._class_registry[cls.__name__] = cls

    # @classmethod
    # def get_fpga_firmware_class_by_name(cls, name):
    #     """ Returns the firmware class that has the name `name`.
    #     """
    #     return cls._class_registry[name]

    @classmethod
    def get_bitstream_object(cls, url, folder=None):
        """ Returns the bitstream object for the specified platform and bitstream configuration.
        """
        if url not in cls._bitstream_cache:
            cls._bitstream_cache[url] = FPGABitstream(url, folder=folder)
        cls.bitstream = cls._bitstream_cache[url]
        cls.bitstream.load_bitstream()  # reload bitstream if it has changed
        return cls.bitstream


    @classmethod
    def get_firmware(cls, platform_name, firmware_name, folder=None):
        """ Search all the FPGAFirmware classes and return the FPGAFirmware subclass
        and Bitstream that matches the specified firmware for the specified
        platform.

        Returns:

            a (fw_cls, bs_instance, fw_info) tuple where:

                fw_cls: The FPGAArray subclass that matches the target firmware

                bs_instance: An instance of the FPGABitstream loaded with the firmware corresponding with the target firmware

                fw_info: A dict containing any other additional firmware information specific to the firmware name and platform.
        """
        fw = [(fw_cls, pf_info.copy())
                    for (fw_cls_name, fw_cls) in cls._class_registry.items()
                    for (pf_name, fw_name), pf_info in fw_cls.PLATFORM_SUPPORT.items()
                    if pf_name == platform_name and fw_name == firmware_name]

        if not fw:
            raise RuntimeError(f'Could not find firmware named {firmware_name} for platform {platform_name}')
        elif len(fw) > 1:
            raise RuntimeError(f'FOund multiple matches for firmware named {firmware_name} and platform {platform_name}')
        fw_cls, pf_info = fw[0]
        bs = cls.get_bitstream_object(pf_info.pop('firmware_url'), folder=folder)
        return fw_cls, bs, pf_info

