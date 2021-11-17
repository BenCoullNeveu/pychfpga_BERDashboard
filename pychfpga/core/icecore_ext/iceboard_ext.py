""" Handler for the IceBoard's FPGA core UDP communication and hardware management firmware.
"""
# Standard Python packages
import logging
from datetime import datetime, timedelta
from calendar import timegm
import time
import struct
import base64
from collections import OrderedDict
import socket
import asyncio

import nest_asyncio
# External private packages

from wtl.metrics import Metrics

# Local packages
from .motherboard import Motherboard
from .async_utils import run_async, async_to_sync
from ..icecore.hardware_assets import IceBoardBase
from ..icecore.tuber import TuberError, TuberNetworkError, TuberRemoteError
from .hardware_map import HardwareMap
from .lib.bsb_mmi import BSB_MMI  # Byte-serial interface protocol definition
from .icecrate_ext import IceCrate
from .icemezz_ext import FMCMezzanine
from .ccoll import Ccoll

from .. import I2C as i2c
from .. import GPIO as fpga_gpio

# from lib import tmp100  # I2C Temperature sensor
from .lib import pca9575  # I2C 16-bit IO Expander
from .lib import tca9548a  # I2C switch
from .lib import ina230  # I2C Voltage and current monitor
from .lib import eeprom
from .lib import qsfp
from .lib import gpio



class IceBoard(IceBoardBase, Motherboard):
    """ Provide the methods needed to operate the Iceboard hardware and its FPGA firmware.

    The class gives access to the methods provided by the on-board ARM processor via the Tuber protocol.

    Adds:
        - Lightweight list-based Hardware map management
        - Model, serial, slot, crate and mezzanine self discovery through the Iceboard (no mDNS required)
        - Access to the memory-mapped registers in the FPGA's firmware using the ARM-FPGA SPI link
            through the `fpga_core_reg_read_async()` and `fpga_core_reg_write_async()` methods.

    Parameters:

    """
    """ Extension to the basic Python Iceboard object .

    Adds:



    `IceBoardPlusHandler` can be created as a standard Python object initialized with a number of
    parameters which set corresponding attributes (see below). If a `parent_getter` function is
    provided, the value of these attributes will instead be fetched
    dynamically from the parent object. Note that any explicitely specified parameter overrides a
    parent parameter.

    Parameters:
        hostname (str): hostname or IP address of the ICEBoard ARM processor (mandatory)
        serial (str): Serial number of the board. Can be provided by the ARM.
        part_number (str): Part number of the IceBoard. Can be obtained from the ARM.
        crate (IceCrateHandler): = object that handle the backplane on which the board is connected. `None` if the board is not connected to a backplane.
        slot (int): Slot number in which the board is installed ona backplane. None if there is no backplane.
        mezzanine (dict): Map {mezzanine_number: Mezzanine Handler, ...} describing the installed mezzanines. Can be obtained from the ARM.
        tuber_objname (str): name of the set of software functions that will be provided by the ARM processor through the Tuber interface.



    .. Any object provided by this this handler can be accessed at any
    .. hierarchical level. However, objects that are probided by Tuber have these
    .. restrictions:
    ..
    ..    - attributes and methods whise name begin with '_' are not accessible
    ..    - modification to the object attributes must be done by a setter
    ..      function provided by the object.
    ..    - methods or attribute access can only return string or numeric values,
    ..      or lists or dictionnary thereof


    Notes:
        - The SPI MMI interface is currently provided by peek/poke methods accessed through Tuber.
          However, if one day the ARM supports it, a faster access could potentially be provided by
          overriding the fpga_core_reg_read_async/write methods to send the commands to a dedicated ARM port
          and thus bypass Tuber's HTTP/JSON overhead. Since the SPI link is relatively slow anyway, this might not be useful until a faster ARM-FPGA link is in place (such as the unused PCIe link).

        - This handler does *not* define a MMI interface that uses the FPGA's
          ethernet port directly through the SFP+ connector. Such functionnality is to be provided by a
          subclass of this class if the firmware supports it.
    """



    part_number = 'MGK7MB'
    _ipmi_part_numbers = ['MGK7MB']

    # Define the set of functions provided by the IceBoard's ARM processor. This is used by Tuber, which comes with IceBoardBase.
    tuber_objname = 'IceBoard'

    NUMBER_OF_FMC_SLOTS = 2

    # subarray = None  # Arbitrary string used to group and select subsets of Iceboard"

    # _bitstream_register contains a list of bitstreams that are associated
    # with this object. Format: tag: bitstream_object
    _bitstream_register = {}

    _backplane_initialized = False  # Indicate if we have initialized the backplane access yet
    _cached_repr = None

    def __init__(self, hostname=None, serial=None, slot=None, subarray=None, fpga_ip_addr=None,**kwargs):
        """ Create or update an IceBoard object.

        If the hardware map features of the object are to be used, use
        IceBoard.get_unique_instance(...) to create an IceBoard object (or
        reuse one that matches the serial or hostname, with the possibility of
        updating the class type and other Iceboard parameters)


        Parameters:

            hostname (str): passed to Tuber. If `hostname` is None, methods
                provided by the IceBoard ARM processor (over Tuber) cannot be
                used on this instance. If `hostname` is 'None' but the
                instance has a serial number, then the board hostname can
                potentially be resolved using mDNS discovery.

            serial (str or int): Serial number of the board, in the exact
                fromat it is found on the IPMI info of the board. For
                convenience, if `serial` is an integer, it is converted into a
                properly formatted string serial.

            slot (int): slot number on a crate, or virtual slot number for
                crate-less standalone boards. Ranges from 1 to NUMBER_OF_SLOTS
                in the particular icecrate. A value of  0 or None (i.e.
                bool(slot) == False)  indicates that there is no slot
                information.

            subarray: Arbitrary value that is used to group boards in logical
                categories.


        Notes:

        __init__() only sets the IceBoard key parameters and manages the
        hardware map. IceBoard objects (and their subclasses) are created and
        destroyed freely  during the process of hardware map creation.
        __init__() therefore shall not initiate communication with the
        hardware or do complex set-up; this is done by init(), which will be
        called when the hardware map is completed and stable.

        """





        super().__init__(hostname=hostname, serial=serial, **kwargs)  # pass on the remaining kwargs. crate and mezzanine are cleared.


        # Store object-specific local paramaters
        self.mmi = None
        self.i2c = None
        self.core_gpio = None
        self.core_i2c = None
        self.hw = None


        # Initialize local variables

        self._mezzanine_ipmi_cache = {1: None, 2: None}
        self._is_core_open = None
        self._is_hw_open = None
        # self._is_bp_open = None
        # self._is_open = None


    # def update_instance(self, new_class=None, fpga_ip_addr=None, **kwargs):
    #     fpga_ip_addr = fpga_ip_addr or self.fpga_ip_addr
    #     if new_class and new_class is not self.__class__:
    #         return super().update_instance(new_class=new_class, fpga_ip_addr=fpga_ip_addr, **kwargs)
    #     else:
    #         super().update_instance(**kwargs)
    #         self.fpga_ip_addr = fpga_ip_addr
    #         return self


    async def ping_async(self, timeout=0.1):
        """
        Returns a boolean indicating whether a tuber object is available at
        the specified ARM hostname.
        """
        # print(f'{self!r} Ping_async()')
        self.logger.info('%r: Pinging %s' % (self, self.tuber_uri))
        try:
            await self._tuber_get_meta_async()
            await self._tuber_sleep_async(0)
            return True
        except TuberError as e:
            self.logger.debug(
                f'{self!r}: Tuber Ping returned an error. '
                f'Board is considered to be absent. Error is \n{e!r}')
            return False





    ###################################
    # Auto discovery methods
    ###################################



    async def discover_serial_async(self, update=True):
        """
        Discover the serial number of this IceBoard from its IPMI data, and update the hardware map accordingly if `update=True`
        """
        self.logger.debug(f'{self!r}: discovering the serial number of board at {self.tuber_uri}')
        try:
            actual_serial = str((await self.tuber_get_motherboard_serial_async()))
        except Exception as e:  #  Deal with uninitialized boards
            self.logger.warning('%r: Error while attempring to read the board serial number. The exception is %r' % (self, e))
            actual_serial = None
        self.logger.debug(f'{self!r}: got the serial number of board at {self.tuber_uri} to be {actual_serial}')
        await asyncio.sleep(0)
        if update:
            if not actual_serial:
                self.logger.warning('%r: Could not read the board serial number from IPMI storage or serial number is null. Serial number is not updated.' % (self))
            elif self.serial and actual_serial != self.serial:
                self.logger.warning('%r: The discovered serial number differs from the current (hardware map) one. Updating to the discovered value.' % (self))
            self.update_instance(serial=actual_serial)
        self.logger.debug(f'{self!r}: finished discovering the serial number of board at {self.tuber_uri}')
        return(self.serial)

    async def discover_slot_async(self, update=True):
        """ Discover the slot number of this IceBoard, and update the hardware map accordingly if `update=True`"""
        actual_slot = await self.tuber_get_backplane_slot_async()
        if update:
            if not actual_slot:
                self.logger.warning('%r: The board is not connected to a backplane. Slot number is not updated.' % (self))
            elif self.slot and actual_slot != self.slot:
                self.logger.warning('%r: The discovered slot (%s) number differs from the current (hardware map) one (%s). Updating to the discovered slot.' % (self, actual_slot, self.slot))
            self.update_instance(slot=actual_slot)
        return(self.slot)

    async def discover_mezzanines_async(self, update=True):
        '''Detect mezzanines attached to the Iceboard and update the hardware map accordingly if
        update=True.

        This method uses IPMI data on the mezzanine's EEPROMs to guide itself.
        New Mezzanine objects that match the IPMI product number are added in
        the hardware map if found.

        You do NOT need to use this method if the mezzanines present in the
        system are already explicitely specified in the YAML hardware maps.
        '''
        mezz_class = {}
        for m in range(1, self.NUMBER_OF_FMC_SLOTS + 1):

            # MezzClass = MissingMezzanine # Used by Graeme
            part_number = None
            serial = None
            mezz_class[m] = None
            # if there is no mezzanine in this slot, proceed to the next one
            if not (await self.tuber_is_mezzanine_present_async(m)):
                continue

            # If a mezzanine is present, get its EEPROM data and search for the first mezzanine class that can decode it.
            try:
                eeprom_data = await self._mezzanine_eeprom_read_async(m)  # this does not read all eeprom for some mezzanines...
                # eeprom_data = self.hw.read_mezzanine_eeprom(m,0,512)
            except (TuberRemoteError, AttributeError):  # If the method does not exist
                eeprom_data = None

            # Find a registered Mezzanine class that can decode the EEPROM data
            # This is useful to recognize legacy EEPROM data format
            ipmi = None
            if eeprom_data is not None:
                for cls in FMCMezzanine.get_all_classes():
                    if hasattr(cls, 'decode_eeprom'):
                        ipmi = cls.decode_eeprom(eeprom_data)
                        if ipmi:
                            break
            if not ipmi:
                try:
                    ipmi = await self._tuber_get_mezzanine_ipmi_async(m)  # Read IPMI from the ARM's cache
                    self.logger.debug(
                        f'{self!r}: detect_mezzanines(): '
                        f'read Mezzanine {m} EEPROM using the ARM')
                except TuberRemoteError:
                    pass
            if not ipmi:  # If we still did not get an IPMI block, give up and proceed to the next mezzanine
                self.logger.debug(
                    f'{self!r}: detect_mezzanines(): Could not decode '
                    f'the EEPROM in Mezzanine {m}')
                continue

            # Extract the useful information from IPMI
            part_number = ipmi.product.part_number
            serial = ipmi.product.serial_number

            self.logger.debug(
                f'{self!r}: detect_mezzanines(): Detected Mezzanine '
                f'Model: {part_number} Serial {serial} in Mezzanine {m}')

            # Look through the Mezzanine classes to see if one matches the model number found in the EEPROM
            # for mapper in class_mapper(FMCMezzanine).self_and_descendants:
            #         if mapper.class_._ipmi_part_numbers == part_number:
            #             mezz_class[m] = mapper.class_
            #             break
            mezz_class[m] = FMCMezzanine.get_class_by_ipmi_part_number(part_number)

            if update:
                # if not self.hwm:
                #     raise SystemError(
                #         '%r: detect_mezzanines(): Attempt to add new '
                #         'mezzanine objects while the IceBoard is not yet '
                #         'added to the  hardware map. ' % self)

                if m in self.mezzanine:
                    del(self.mezzanine[m])

            if not mezz_class[m]:
                self.logger.warning(
                    "%r: detect_mezzanines(): There is no known "
                    "class for Mezzanine object of type '%r' "
                    "in mezzanine slot %r" % (self, part_number, m))
            elif update:
                self.logger.debug(
                    '%r: detect_mezzanines(): Creating Mezzanine '
                    'Serial %s in Mezzanine %i on iceboard %r' % (self, serial, m, self))
                # new_mezz = get_unique_class_instance(
                #     mezz_class[m],
                new_mezz = mezz_class[m](
                    serial=serial,
                    mezzanine=m,  # mezzanine number (FMC slot)
                    iceboard=self)  # back reference to the carrier iceboard
                new_mezz.iceboard=self
                self.mezzanine[m] = new_mezz
                self.logger.debug(f'{self!r} mezzanines on FMC {m} are {self.mezzanine[m]}')
        return(mezz_class)

    async def discover_crate_async(self, update=True):
        """ Detect the Icecrate and slot number on which this Iceboard is
        attached by reading the backplane IPMI data, and update the hardware
        map accordingly if `update=True`.

        The crate object is then set with the (part_number, serial_number) tuple, which is replaced later by the actual crate object.

        This method does *not* use mDNS. It relies of the IPMI data stored in
        the backplane's EEPROM, which is obtaines through the Iceboard's ARM
        processor.

        You do NOT need to use this method if the backplane is already
        explicitely specified for this IceBoard in the YAML hardware maps.
        """

        icecrate_class = None
        part_number = None
        serial = None
        slot_number = None
        if (await self.is_backplane_present_async()):
            try:
                ipmi = await self._tuber_get_backplane_ipmi_async()  # Tuber call

                part_number = ipmi.product.part_number
                serial = ipmi.product.serial_number
                icecrate_class = self.get_class_by_ipmi_part_number(base_class_name='IceCrate', part_number=part_number)
                slot_number = await self.tuber_get_backplane_slot_async()
                self.logger.debug(
                    f'{self!r}: discover_crate(): Detected Backplane '
                    f'Model {part_number} Serial {serial}')
            except TuberRemoteError:
                self.logger.warning(
                    f'{self!r}: discover_crate(): Detected Backplane '
                    f'but it has no IPMI information')

        if not icecrate_class:
            self.logger.warning(
                f"{self!r}: discover_crate(): There is no known backplane object "
                f"with part number '{part_number}'")

        if icecrate_class and update:
            crate_number = self.crate.crate_number if self.crate else None
            crate = IceCrate.get_unique_instance(new_class=icecrate_class, serial=serial, crate_number=crate_number)
            self.update_instance(crate=crate) # update crate info and repr
            self.logger.debug(f"{self} now has crate {self.crate}")
            # if slot_number:
            #     self.crate.slot[slot_number] = self

        return icecrate_class




    # ----------------------------
    # Bitstream management
    # ----------------------------

    async def is_fpga_programmed_async(self):
        return await self.tuber_is_fpga_programmed_async()


    async def set_fpga_bitstream_async(self, buf=None, tag=None, force=False):
        '''
        Configures the FPGA with the specified bitstream.

        The bitstream associated with the current handler with the specifiec
        'tag' will be loaded. However, if a buffer 'buf' is explicitely
        provided, that bitstream will be used instead.,

        The 'buf' can be  a ``bytes`` or object with .bytes or .base64 attributes
        .BIT or .BIN file.

        By default, the FPGA will not be reconfigured it already has a
        bitstream with the same CRC signature. That behavior can be changed by
        specifying the 'force' argument:

            force = True: FPGA will always be configured
            force = False: FPGA will be configured if it is not configured or
                    if bitstream CRC differ
            force = None: FPGA will be configured only if it is not configured
        '''

        t0 = time.time()
        self.logger.debug(f'{self!r}: called set_fpga_bitstream')

        if hasattr(self, 'close'):
            self.close()

        # If the bitstream is not explicitely provided, ask the handler to
        # provide it. The str() of the returned object must yield the valid
        # bitstream buffer in a string.
        if buf is None:
            buf = self.get_fpga_bitstream(tag)

        if hasattr(buf, 'crc32'):
            crc32 = buf.crc32
        else:
            crc32 = zlib.crc32(str(buf))  # compute CRC32 of the data if it not already precomputed in the 'buf' object
        crc32 &= 0xFFFFFFFF
        # buf = buf.bytes()

        self.logger.debug(f'{self!r}: Getting is_programmed')
        is_fpga_programmed = await self.tuber_is_fpga_programmed_async()
        t1 = time.time()
        self.logger.debug(f'{self!r}: Getting FPGA crc')
        fpga_bitstream_crc = await self.get_fpga_bitstream_crc_async()
        self.logger.debug(
            f'{self!r}: fpga_programmed={is_fpga_programmed}, force={force}, '
            f'fpga_crc={fpga_bitstream_crc or 0:08X}, bitstream_crc={crc32 or 0:08X}')
        t2 = time.time()
        if not is_fpga_programmed or force \
           or (force is not None and (fpga_bitstream_crc != crc32)):
            self.logger.debug(f'{self!r}: Configuring FPGA')

    # ----------------------------
    # open & close methods
    # ----------------------------

    async def open_fpga_async(self, **kwargs):
        """ Open communication with the FPGA """

        self.logger.debug(f'{self!r}: open() is called')


        await self.fpga.open_async(**kwargs)
        self.hw = IceBoardHardware(self)
        await self.hw.open_async()

        await self.hw.set_led('GP_LED2', 1)  # Hardware link is on
        await self.hw.set_led('GP_LED1', 0)  # Full FPGA firmware not initialized yet


    def close_fpga(self):
        if self.hw:
            self.hw.close()

        if self.fpga:
            self.fpga.close()

    async def init_fpga_async(self, **kwargs):
        """ Initializes the FPGA firmware
        """
        await self.fpga.init_async(**kwargs)
        await self.hw.set_led('GP_LED1', 1)  # Full FPGA firmware is initialized




    #**********************************
    # Local methods
    #**********************************

    # Backplane/crate-related methods
    # -------------------------------
    async def is_backplane_present_async(self):
        return await self.tuber_is_backplane_present_async()

    async def get_slot_number(self):
        """ Reads the GPIO to determine in which slot number this IceBoard is
        connected.

        """
        if await self.is_backplane_present_async():  # Is this test necessary?
            return await self.tuber_get_backplane_slot_async()
        else:
            return None

    # Motherboard-related methods
    # ---------------------------
    # *** JFC: method rename
    async def _write_motherboard_spi_eeprom_base64(self, *args, **kwargs):
        result = await self._tuber_motherboard_eeprom_write_base64_async(*args, **kwargs)
        return(result)

    # def get_motherboard_serial(self):
    #     """ Read the motherboard serial number from the IPMI data. """
    #     ipmi = self._get_motherboard_ipmi()
    #     return str(ipmi.board.serial_number)

    # *** JFC: We now have the equivalent ARM method. Will delete this when we
    #     confirm it behaves the same.


    # Mezzanine-related methods
    # -------------------------

    async def _mezzanine_eeprom_read_async(self, mezzanine):
        """ Returns the contents of the specified mezzanine's EEPROM.
        """
        data = await self._tuber_mezzanine_eeprom_read_base64_async(mezzanine) # returns a str
        return base64.decodebytes(data.encode())  # encode the str into bytes before calling base64.decodebytes()



    async def get_iceboard_clock_source_async(self):
        return await self.tuber_get_clock_source_async()

    get_iceboard_clock_source_sync = async_to_sync(get_iceboard_clock_source_async)

    def get_motherboard_temperature(self, sensor):
        """ Synchronous wrapper to return motherboard temperature sensor value.
        """
        return run_async(self.tuber_get_motherboard_temperature_async(sensor))


    # Tuber-related methods
    # -------------------------

    async def check_tuber_version_async(self):
        """ Check if the ARM processor provides the methods required to run this code. """

        required_tuber_methods = [ # Use the unmangled name as published by the ARM
            'is_fpga_programmed']#, '_mezzanine_eeprom_read_base64']

        (meta, props, tuber_methods) = await self._tuber_get_meta_async()  # get the meta info
        if not tuber_methods:
            raise RuntimeError("%r: The ARM does not publish any methods under the object name '%s'. Was the right Tuber object name used for this ARM firmware?" % (self, self.tuber_objname))

        for method in required_tuber_methods:
            if method not in tuber_methods:
                raise RuntimeError("%r: The current version of the ARM firmware does not provide the method '%s' that is needed for this application" % (self, method))

        return True

    def print_tuber_methods(self):
        """ Print all the methods and properties provided by the Iceboard's
        ARM processor through the Tuber protocol.
        """
        (meta, props, methods) = self._tuber_get_meta()  # get the meta info
        print("Methods for tuber object '%s':" % self.tuber_objname)
        print('-----------------------------------------')
        for method_name, method_properties in sorted(methods.items()):
            print('%-30s: %s' % (method_name, method_properties.summary))
        print()
        print("Properties for tuber object '%s':" % self.tuber_objname)
        print('-----------------------------------------')
        for prop_name, prop_properties in sorted(props.items()):
            try:
                values = ', '.join('.%s' % p for p in prop_properties)
            except TypeError:
                values = '= %s' % prop_properties
            print('%-30s: %s' % (prop_name, values))

   # ARM shell commands
   # ------------------




    async def _call_subprocess(self, cmd):
        """
        Executes a subprocess in a non-blocking way.
        """
        pipe = subprocess.PIPE

        # ssh_cmd = "ssh root@%s '%s'" % (self.hostname, cmd)
        split_cmd = shlex.split(cmd)
        p = subprocess.Popen(split_cmd, stdout=pipe, stderr=pipe)
        while p.poll() is None:
            await asyncio.sleep(0)
        if p.returncode:
            raise RuntimeError(
                "The command '%s' returned with the error code %i. "
                "stderr is displayed below:\n %s" % (
                     cmd,
                     p.returncode,
                     ''.join(p.stderr.readlines())))
        return p.stdout.readlines()

    async def arm_exec(self, cmd):
        """
        Executes a command on the ARM over SSH.
        """
        self.logger.info("%r: Executing command '%s' on the ARM" % (self, cmd))
        ssh_cmd = 'ssh -o "StrictHostKeyChecking no" root@%s "%s"' % (self.hostname, cmd)
        result = await self._call_subprocess(ssh_cmd)
        return result

    async def arm_scp(self, source_filename, destination_filename='/tmp'):
        """
        Sends a file to the arm using scp.
        """
        self.logger.info('%r: Sending image file %s to the ARM in %s' % (
            self,
            source_filename,
            destination_filename))
        scp_cmd = 'scp -o "StrictHostKeyChecking no" %s root@%s:%s' % (
            source_filename,
            self.hostname,
            destination_filename)
        result = await self._call_subprocess(scp_cmd)
        return result

    async def _update_arm_firmware(self, image_filename, delay=120):
        """
        Overwrites the ARM firmware on the SD card with the specified image compressed with bzip2.

        !!! WARNING: This is a very ugly hack that can make the SD card
        inoperable. You must do this only if you are in a position to manually
        replace a SD card if this fails!!!

        !!! The image must be in BZIP2 format. If not, the ARM won't boot
        again unless you replace the SD card !!!

        You must power-cycle the board after this command. The normal reboot()
        method won't work because this corrupts the ARMs filesystem (did we
        say this was a bad hack?).
        """
        image_header = '\xfa\xb8\x00\x10\x8e\xd0\xbc\x00'
        with bz2.BZ2File(image_filename) as fh:
            data = fh.read(100)  # read a few bytes to make sure this is really a bz2 file
            if not data.startswith(image_header):
                raise RuntimeError('The image does not seem to contain a compressed SDcard image')
        print('%r: Sending file...' % self)
        await self.arm_scp(image_filename, '/tmp/image.bz2')
        print('%r: Writing SD card' % self)
        await self.arm_exec('bzcat /tmp/image.bz2 >/dev/mmcblk0')
        self.logger.info('%r: Command completed. Waiting %i seconds to ensure cache is flushed' % (self, delay))
        print('%r: Waiting %i seconds' % (self, delay))
        await asyncio.sleep(delay)
        return True

    async def _upload_fpga_bitstream(self, filename, card_filename=None, delay=120):
        """
        Remounts the filesystem as read write
        Uploads the bit file to the SD card in folder /usr/lib/iceboard/
        Remounts the file system back to read only
        """

        if card_filename is not None:
            filename_sd_card = '/usr/lib/iceboard/' + card_filename
        else:
            filename_sd_card = '/usr/lib/iceboard/' + os.path.basename(filename)

        print('%r: Remounting the SD card file system as readwrite' % self)
        await self.arm_exec('mount / -o remount,rw')

        print('%r: Making /usr/lib/iceboard folder if needed' % self)
        await self.arm_exec('mkdir -p /usr/lib/iceboard')

        print('%r: Sending file to /usr/lib/iceboard/' % self)
        await self.arm_scp(filename, filename_sd_card)

        self.logger.info('%r: Command completed. Waiting %i seconds to ensure cache is flushed' % (self, delay))
        print('%r: Waiting %i seconds' % (self, delay))
        await asyncio.sleep(delay)

        print('%r: Remounting the SD card file system as readonly' % self)
        await self.arm_exec('mount / -o remount,ro')
        return True

    async def _delete_fpga_bitstream(self, filename, delay=120):
        """
        Remounts the filesystem as read write
        Removes  the bit file on the SD card in folder /usr/lib/iceboard/
        Remounts the file system back to read only
        """

        print('%r: Remounting the SD card file system as readwrite' % self)
        await self.arm_exec('mount / -o remount,rw')

        remove_file = 'rm /usr/lib/iceboard/' + os.path.basename(filename)
        print('%r: Removing the requested file' % self)
        await self.arm_exec(remove_file)

        self.logger.info('%r: Command completed. Waiting %i seconds to ensure cache is flushed' % (self, delay))
        print('%r: Waiting %i seconds' % (self, delay))
        await asyncio.sleep(delay)

        print('%r: Remounting the SD card file system as readonly' % self)
        await self.arm_exec('mount / -o remount,ro')
        return True





# class IceBoardExt(IceBoardPlus):
    """ Extends the basic IceBoard class by providing additional SPI MMI -based firmware features, direct UDP MMI
    with the FPGA,  and methods to access to IceBoard hardware directly via the FPGA.

    This class provides:

    - UDP/IP/Ethernet-based direct Memory Map Interface (MMI) to the FPGA using its Ethernet port. Note
      that this accesses an address space that is separate from the one accessed throughthe ARM SPI interface.
      Methods to initialize the Ethernt networking parameters through the ARM SPI interface are provided.

    - Alternate access to the IceBoard and Backplane hardware through the FPGA I2C interface through
      the `hw` object. Access to the hardware is normally done through the high-level ARM-provided
      methods, but these methods are useful for development and debugging. The exception is the the
      IceCrate handler which uses the FPGA to access backplane resources.

    - Overriden mezzanine identification methods that support non-IPMI McGill ADC mezzanine boards.

    - IRIG-B subsystem operation (through the ARM SPI interface)

    `IceBoardExtHandler` can be created as a standard Python object
    initialized with a number of parameters which set corresponding attributes
    (see below). If a `parent_getter` function is provided, the value of some
    of these attributes will instead be fetched dynamically from the parent
    object unless explicit values (i.e. not None) are provided here. An
    explicittly provided parameter will always use the provided value and will
    no longer be fetched from the parent, nor will it be set on the parent.


    Parameters:

        parent_getter (func): Function that dynamically return the parent object from which the
            following parameters will be fetched. Is `None` if there is no parent.

        hostname (str): hostname or IP address of the ICEBoard ARM processor (mandatory)

        serial (str): Serial number of the board. Can be provided by the ARM.

        part_number (str): Part number of the IceBoard. Can be obtained from the ARM.

        crate (IceCrateHandler): = object that handle the backplane on which the board is connected.
            `None` if the board is not connected to a backplane.

        slot (int): Slot number in which the board is installed ona backplane. None if there is no
            backplane.

        mezzanine (dict): Map {mezzanine_number: Mezzanine Handler, ...} describing the installed
            mezzanines. Can be obtained from the ARM.

        tuber_objname (str): name of the set of software functions that will be provided by the ARM
            processor through the Tuber interface.



    Python-based application-specific FPGA firmware and hardware handler are meant to be derived
    from this class.
    """


    # ---------------------------------------
    # Instance attributes
    # ---------------------------------------

########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################
########################################################################################################


class IceBoardHardware(object):
    """
    Provides access to the hardware of an IceBoard Rev2/Rev3, including:
        - LED control
        - GPIO input/output
        - Temperature sensors
        - Power monitoring for every rail (voltage,current)
        - Motherboard EEPROM

    This class implements these methods by issuring I2C commands
    through the I2C interface provided either by the FPGA or by the
    ARM.

    Part or all of of functionnalities described in this class might
    eventually be implemented in the ARM processor itself. In thise
    case, these those will be available through the ARM's Tuber
    interface.
    """

    # ------------------------------------
    # Define hardware-specific constants
    # ------------------------------------
    NUMBER_OF_FMC_SLOTS = 2  # Indicates the number of FMC slots supported by this platform

    # I2C switch addresses (visible on all buses on a specific port)
    _FPGA_I2C_SWITCH_ADDR = 0b1110100  # 0x74
    _ARM0_I2C_SWITCH_ADDR = 0b1110000  # 0x70
    _ARM1_I2C_SWITCH_ADDR = 0b1110001  # 0x71
    _ARM2_I2C_SWITCH_ADDR = 0b1110010  # 0x72
    _ARM3_I2C_SWITCH_ADDR = 0b1110011  # 0x73

    FPGA_I2C_BUS_LIST = {
        # Bus name, (FPGA I2C port, I2C switch enable bit)
        "FMC":   (0, 0),  # equivalent to FMCA. Included for backwards compatibility with single-FMC code
        "FMCA":  (0, 0),
        "FMCB":  (0, 1),
        "QSFPA": (0, 2),
        "QSFPB": (0, 3),
        "SFP":   (0, 4),
        "SMPS":  (0, 5),
        "BP":    (0, 6),
        "GPIO":  (0, 7)
        }

    # FMC EEPROM, on FMCA or FMCB
    _FMC_EEPROM_ADDR = 0x50  # 0x50 (0x51 is also used for the 2nd page of large eeprom with address width > 16 bits).
    _FMC_EEPROM_ADDR_WIDTH = 7  # FMC EEPROM internal addresses are 7 bits wide.
    _FMC_EEPROM_PAGE_SIZE = 8  #

    # Oversize , non-FMC-standard EEPROM found on some McGill Mezzanines

    # FMC EEPROM internal addresses are is 17 bits wide. (2 bytes as data, 1 bit in lsb of I2C address)
    _MCGILL_FMC_EEPROM_ADDR_WIDTH = 17
    _MCGILL_FMC_EEPROM_PAGE_SIZE = 256  #

    # Motherboard EEPROM
    _MOTHERBOARD_EEPROM_DATA_ADDR = 0x57  #
    _MOTHERBOARD_EEPROM_SERIAL_ADDR = 0x5F  #
    # EEPROM internal addresses are is 17 bits wide. (2 bytes as data, 1 bit in lsb of I2C address)
    _MOTHERBOARD_EEPROM_ADDR_WIDTH = 7
    _MOTHERBOARD_EEPROM_PAGE_SIZE = 8  #

    # IO Expanders, on GPIO bus
    _GPIO_POWER_I2C_ADDR = 0b0100000  # 0x20
    _GPIO_SFP_QSFP_I2C_ADDR = 0b0100001  # 0x21
    _GPIO_SW_LEDS_ADDR = 0b0100010  # 0x22
    _GPIO_ARM_PHY_LEDS_ADDR = 0b0100011  # 0x23

    # # Temperature sensors, on GPIO bus
    # _TMP_ARM_I2C_ADDR   = 0b1001010 #0x4A
    # _TMP_PHY_I2C_ADDR   = 0b1001100 #0x4C
    # _TMP_FPGA_I2C_ADDR  = 0b1001011 #0x4B
    # _TMP_POWER_I2C_ADDR = 0b1001000 #0x48

    # # Power monitors, on SMPS bus
    # _POWER_ICEVADJ_I2C_ADDR   = 0b1000011 #0x43
    _POWER_ICE12V0_I2C_ADDR = 0b1000111  # 0x47
    # _POWER_ICE5V0_I2C_ADDR    = 0b1001000 #0x48
    # _POWER_ICE3V3_I2C_ADDR    = 0b1001001 #0x49
    # _POWER_ICE1V5_I2C_ADDR    = 0b1001100 #0x4C
    # _POWER_ICE1V2_I2C_ADDR    = 0b1001101 #0x4D
    _POWER_ICE1V0_I2C_ADDR = 0b1001110  # 0x4E
    # _POWER_ICE1V8_I2C_ADDR    = 0b1001011 #0x4B
    # _POWER_ICE1V0GTX_I2C_ADDR = 0b1001111 #0x4F

    # _POWER_FMCA12V0_I2C_ADDR  = 0b1000000 #0x40
    # _POWER_FMCA3V3_I2C_ADDR   = 0b1000001 #0x41
    # _POWER_FMCAVADJ_I2C_ADDR  = 0b1000010 #0x42

    # _POWER_FMCB12V0_I2C_ADDR  = 0b1000100 #0x44
    # _POWER_FMCB3V3_I2C_ADDR   = 0b1000101 #0x45
    # _POWER_FMCBVADJ_I2C_ADDR  = 0b1000110 #0x46

    def __init__(self, iceboard):
        """
        Creates all the I2C objects needed to interface the hardware. In order
        to do this, the following methods will be required from the iceboard
        object:

            - i2c_set_port(...) # Port number 0 (connected to the FPGA I2C switch) is used for all accesses
            - i2c_write_read(...) # FPGA I2C engine

        Those methods can be provided either by the ARM or the core FPGA firmware.

        For FPGA-based I2C:
            - fpga_core is not Null
            - fpga_core provides the following methods
        """

        self._logger = logging.getLogger(__name__)
        self._iceboard = iceboard

    def __repr__(self):
        return "%r.%s" % (self._iceboard, self.__class__.__name__)


    async def open_async(self):
        """ Initializing objects to access the Iceboard hardware
        """
        self._logger.debug('%r: Initializing Iceboard hardware' % iceboard)
        self._i2c = self._iceboard.i2c
        self._logger.debug('%r: Instantiating Motherboard EEPROM managers' % self._iceboard)
        self._motherboard_eeprom_data = eeprom.eeprom(
            self._i2c, self._MOTHERBOARD_EEPROM_DATA_ADDR, 'GPIO',
            self._MOTHERBOARD_EEPROM_ADDR_WIDTH,
            self._MOTHERBOARD_EEPROM_PAGE_SIZE)
        self._motherboard_eeprom_serial = eeprom.eeprom(
            self._i2c, self._MOTHERBOARD_EEPROM_SERIAL_ADDR, 'GPIO',
            self._MOTHERBOARD_EEPROM_ADDR_WIDTH,
            self._MOTHERBOARD_EEPROM_PAGE_SIZE)

        self._logger.debug('%r:  Instantiating FMC EEPROM managers' % self._iceboard)

        # We check if the EEPROM has multiple pages, and if so, we *assume* that
        # the EEPROM is a large (non-FMC compliant) EEPROM with 2-byte addresses.
        # Otherwise we assume the EEPROM has a single byte of addressing.
        #
        # If the EEPROM is multipage but has a single address byte (4Kbit,
        # 8kbit or 16kbit EEPROMs), then the EEPROM contents will be
        # corrupted, even by read operations, because the second address byte
        # will be interpreted as data to be written. It would be equally bad
        # if there has another I2C device at the address following the EEPROM
        # address.
        if self._i2c.is_present(self._FMC_EEPROM_ADDR+1, bus_name='FMCA'):
            self._logger.debug('%r: Detected multipage EEPROM on FMCA. Assuming >16-bit addressing.' % self._iceboard)
            self._fmca_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCA',
                self._MCGILL_FMC_EEPROM_ADDR_WIDTH,
                self._MCGILL_FMC_EEPROM_PAGE_SIZE)
        else:
            self._fmca_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCA',
                self._FMC_EEPROM_ADDR_WIDTH,
                self._FMC_EEPROM_PAGE_SIZE)

        if self._i2c.is_present(self._FMC_EEPROM_ADDR+1, bus_name='FMCB'):
            self._logger.debug('%r: Detected multipage EEPROM on FMCB. Assuming >16-bit addressing.' % self._iceboard)
            self._fmcb_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCB',
                self._MCGILL_FMC_EEPROM_ADDR_WIDTH, self._MCGILL_FMC_EEPROM_PAGE_SIZE)
        else:
            self._fmcb_eeprom = eeprom.eeprom(
                self._i2c, self._FMC_EEPROM_ADDR, 'FMCB',
                self._FMC_EEPROM_ADDR_WIDTH, self._FMC_EEPROM_PAGE_SIZE)

        self._FMC_EEPROM_TABLE = {
            1: self._fmca_eeprom,
            2: self._fmcb_eeprom
            }

        self._logger.debug('%r: Instantiating I2C GPIO manager' % self._iceboard)
        self._gpio_power = pca9575.pca9575(self._i2c, self._GPIO_POWER_I2C_ADDR, 'GPIO')
        self._gpio_sw_leds = pca9575.pca9575(self._i2c, self._GPIO_SW_LEDS_ADDR, 'GPIO')
        self._gpio_arm_phy_leds = pca9575.pca9575(self._i2c, self._GPIO_ARM_PHY_LEDS_ADDR, 'GPIO')
        self._gpio_sfp_qsfp = pca9575.pca9575(self._i2c, self._GPIO_SFP_QSFP_I2C_ADDR, 'GPIO')

        self._gpio = gpio.GPIO(gpio_table={
            # name : (expander object, byte, lsb bit number,  width)
            'GP_SW1': (self._gpio_sw_leds, 0, 0, 1),
            'GP_SW2': (self._gpio_sw_leds, 0, 1, 1),
            'GP_SW3': (self._gpio_sw_leds, 0, 2, 1),
            'GP_SW4': (self._gpio_sw_leds, 0, 3, 1),
            'GP_SW5': (self._gpio_sw_leds, 0, 4, 1),
            'GP_SW6': (self._gpio_sw_leds, 0, 5, 1),
            'GP_SW7': (self._gpio_sw_leds, 0, 6, 1),
            'GP_SW8': (self._gpio_sw_leds, 0, 7, 1),
            'GP_LED1': (self._gpio_sw_leds, 1, 7, 1),
            'GP_LED2': (self._gpio_sw_leds, 1, 6, 1),
            'GP_LED3': (self._gpio_sw_leds, 1, 5, 1),
            'GP_LED4': (self._gpio_sw_leds, 1, 4, 1),
            'GP_LED5': (self._gpio_sw_leds, 1, 3, 1),
            'GP_LED6': (self._gpio_sw_leds, 1, 2, 1),
            'GP_LED7': (self._gpio_sw_leds, 1, 1, 1),
            'GP_LED8': (self._gpio_sw_leds, 1, 0, 1),
            'GP_LED9': (self._gpio_arm_phy_leds, 0, 0, 1),
            'GP_LED10': (self._gpio_arm_phy_leds, 0, 1, 1),
            'GP_LED11': (self._gpio_arm_phy_leds, 0, 2, 1),
            'GP_LED12': (self._gpio_arm_phy_leds, 0, 3, 1),
            'GTX1V8PowerFault': (self._gpio_arm_phy_leds, 0, 4, 1),
            'PHYAPowerFault': (self._gpio_arm_phy_leds, 0, 5, 1),
            'PHYBPowerFault': (self._gpio_arm_phy_leds, 0, 6, 1),
            'ArmPowerFault': (self._gpio_arm_phy_leds, 0, 7, 1),
            'BP_GPIO0': (self._gpio_arm_phy_leds, 1, 0, 1),
            'BP_GPIO1': (self._gpio_arm_phy_leds, 1, 1, 1),
            'BP_GPIO2': (self._gpio_arm_phy_leds, 1, 2, 1),
            'BP_GPIO3': (self._gpio_arm_phy_leds, 1, 3, 1),
            'BP_GPIO4': (self._gpio_arm_phy_leds, 1, 4, 1),
            'BP_GPIO5': (self._gpio_arm_phy_leds, 1, 5, 1),
            'BP_SLOT_NUMBER': (self._gpio_arm_phy_leds, 1, 0, 4),  # Also corresponds to BP_GPIO0-3
            'QSFPA_ModPrsL': (self._gpio_sfp_qsfp, 0, 0, 1),
            'QSFPA_ResetL': (self._gpio_sfp_qsfp, 0, 2, 1),
            'QSFPA_IntL': (self._gpio_sfp_qsfp, 0, 1, 1),
            'QSFPA_LPMode': (self._gpio_sfp_qsfp, 0, 4, 1),
            'QSFPA_ModSelL': (self._gpio_sfp_qsfp, 0, 3, 1),
            'QSFPB_ModPrsL': (self._gpio_sfp_qsfp, 0, 5, 1),
            'QSFPB_ResetL': (self._gpio_sfp_qsfp, 0, 7, 1),
            'QSFPB_IntL': (self._gpio_sfp_qsfp, 0, 6, 1),
            'QSFPB_LPMode': (self._gpio_sfp_qsfp, 1, 5, 1),
            'QSFPB_ModSelL': (self._gpio_sfp_qsfp, 1, 4, 1),
            'SFP_LOS': (self._gpio_power, 0, 7, 1),
            'SFP_TxFault': (self._gpio_sfp_qsfp, 1, 0, 1),
            'SFP_TxDisable': (self._gpio_sfp_qsfp, 1, 1, 1),
            'SFP_RS0': (self._gpio_sfp_qsfp, 1, 2, 1),
            'SFP_RS1': (self._gpio_sfp_qsfp, 1, 3, 1),
            'SFP_ModSelL': (self._gpio_power, 1, 7, 1),
            'FMCA_PG_M2C': (self._gpio_power, 0, 3, 1),
            'FMCB_PG_M2C': (self._gpio_power, 1, 3, 1)
        })

        self._qsfpa = qsfp.QSFP(self._i2c, bus_name='QSFPA', gpio_prefix='QSFPA_', gpio=self._gpio, parent=self)
        self._qsfpb = qsfp.QSFP(self._i2c, bus_name='QSFPB', gpio_prefix='QSFPB_', gpio=self._gpio, parent=self)

        self.qsfp = Ccoll((self._qsfpa, self._qsfpb))
        # self._logger.info(' Instantiating I2C temperature sensors')
        # self._tmp_power = tmp100.tmp100(self._i2c, self._TMP_POWER_I2C_ADDR, 'GPIO')
        # self._tmp_phy = tmp100.tmp100(self._i2c, self._TMP_PHY_I2C_ADDR, 'GPIO')
        # self._tmp_fpga = tmp100.tmp100(self._i2c, self._TMP_FPGA_I2C_ADDR, 'GPIO')
        # self._tmp_arm = tmp100.tmp100(self._i2c, self._TMP_ARM_I2C_ADDR, 'GPIO')

        # self._logger.info(' Instantiating I2C current/power monitors')
        # self._power_ice_3v3 = ina230.ina230(self._i2c, self._POWER_ICE3V3_I2C_ADDR, 'SMPS')
        self._power_ice_12v0 = ina230.ina230(self._i2c, self._POWER_ICE12V0_I2C_ADDR, 'SMPS')
        # self._power_ice_5v0 = ina230.ina230(self._i2c, self._POWER_ICE5V0_I2C_ADDR, 'SMPS')
        # self._power_ice_1v0_gtx = ina230.ina230(self._i2c, self._POWER_ICE1V0GTX_I2C_ADDR, 'SMPS')
        # self._power_ice_vadj = ina230.ina230(self._i2c, self._POWER_ICEVADJ_I2C_ADDR, 'SMPS')
        # self._power_ice_1v2 = ina230.ina230(self._i2c, self._POWER_ICE1V2_I2C_ADDR, 'SMPS')
        # self._power_ice_1v5 = ina230.ina230(self._i2c, self._POWER_ICE1V5_I2C_ADDR, 'SMPS')
        self._power_ice_1v0 = ina230.ina230(self._i2c, self._POWER_ICE1V0_I2C_ADDR, 'SMPS')
        # self._power_ice_1v8 = ina230.ina230(self._i2c, self._POWER_ICE1V8_I2C_ADDR, 'SMPS')

        # self._power_fmca_12v0 = ina230.ina230(self._i2c, self._POWER_FMCA12V0_I2C_ADDR, 'SMPS')
        # self._power_fmca_3v3 = ina230.ina230(self._i2c, self._POWER_FMCA3V3_I2C_ADDR, 'SMPS')
        # self._power_fmca_vadj = ina230.ina230(self._i2c, self._POWER_FMCAVADJ_I2C_ADDR, 'SMPS')

        # self._power_fmcb_12v0 = ina230.ina230(self._i2c, self._POWER_FMCB12V0_I2C_ADDR, 'SMPS')
        # self._power_fmcb_3v3 = ina230.ina230(self._i2c, self._POWER_FMCB3V3_I2C_ADDR, 'SMPS')
        # self._power_fmcb_vadj = ina230.ina230(self._i2c, self._POWER_FMCBVADJ_I2C_ADDR, 'SMPS')

        # self.TEMPERATURE_SENSOR_TABLE = {
        #     # sensor name: tmp object
        #     'TEMP_POWER': self._tmp_power,
        #     'TEMP_PHY': self._tmp_phy,
        #     'TEMP_FPGA': self._tmp_fpga,
        #     'TEMP_ARM': self._tmp_arm
        # }

        # self.POWER_SENSOR_TABLE = {
        #     # sensor name : (ina230 object, output voltage(volts), rshunt(inductor) (mohm), typical current(amps), current tolerance (0<tol<1))
        #     'ICE_3V3': (self._power_ice_3v3, 3., 2.36, 8., 0.5),         #SER1360-182L
        #     'ICE_12V0': (self._power_ice_12v0, 12., 5.5, 3., 0.5),       #SER1360-602L
        #     'ICE_5V0': (self._power_ice_5v0, 5., 2.36, 11., 0.5),        #SER1360-182L
        #     'ICE_1V0_GTX': (self._power_ice_1v0_gtx, 1., 0.77, 16., 0.5),#SER1360-331L
        #     'ICE_1V2': (self._power_ice_1v2, 1.2, 0.77, 8., 0.5),        #SER1360-651L
        #     'ICE_1V5': (self._power_ice_1v5, 1.5, 2.36, 3., 0.5),        #SER1360-182L
        #     'ICE_1V0': (self._power_ice_1v0, 1., 0.77, 16., 0.5),        #SER1360-331L
        #     'ICE_1V8': (self._power_ice_1v8, 1.8, 5.5, 1., 0.5),         #SER1360-602L
        #     'ICE_VADJ': (self._power_ice_vadj, 2.5, 2.36, 8., 0.5),
        #     'FMCA_12V0': (self._power_fmca_12v0, 12., 5, 2., 0.5),
        #     'FMCB_12V0': (self._power_fmcb_12v0, 12., 5, 2., 0.5),
        #     'FMCA_3V3': (self._power_fmca_3v3, 3., 5, 5., 0.5),
        #     'FMCB_3V3': (self._power_fmcb_3v3, 3., 5, 5., 0.5),
        #     'FMCA_VADJ': (self._power_fmca_vadj, 2.5, 5, 1., 0.5),
        #     'FMCB_VADJ': (self._power_fmcb_vadj, 2.5, 5, 1., 0.5)
        # }


    def close(self):
        self._logger.debug('Closing Iceboard hardware')
        if self._i2c:
            self._i2c = None

    async def init_async(self):
        pass


    def _init_gpio_expanders(self):
        """
        Initializes GPIO expanders

        History

        140304 JM: created. todo: make more flexible for I/O pin configuration
        of each expander. Need to confirm I/O pin config with JF
        """
        self._gpio_power.init(cfg0_def=0b10101000,  # 1 = input, 0=output
                              cfg1_def=0b10101000,
                              out0_default=None,
                              out1_default=None,
                              bken0=0b00,  # We need to disable 100K internal
                              #       pull-ups/down so the PG_M2C can work
                              #       properly (there is another external 100K
                              #       pull up to VCC3V3 which pulls to GND
                              #       when there is no power. Pulling up
                              #       doesn't work when board is off , pull
                              #       down doesn't work when board is ON)
                              bken1=0b00,
                              pupd0=0b00001000,  # don't care, pullups not enabled
                              pupd1=0b00001000
                              )
        self._gpio_sw_leds.init(cfg1_def=0b00000000)
        self._gpio_arm_phy_leds.init(cfg0_def=0b11110000)
        self._gpio_sfp_qsfp.init(cfg0_def=0b01100011, cfg1_def=0b11001111)

    def get_i2c_interface(self):
        """
        Returns an I2C interface object that provides a standardized bus selection.
        """
        return self._i2c

    def get_number_of_fmc_slots(self):
        return self.NUMBER_OF_FMC_SLOTS

    # def get_slot_number(self):
    #     return self._gpio.read('BP_SLOT_NUMBER') + 1

    def read_motherboard_eeprom(self, addr, length, **kwargs):
        return self._motherboard_eeprom_data.read(addr, length, **kwargs)

    def write_motherboard_eeprom(self, addr, data, **kwargs):
        return self._motherboard_eeprom_data.write(addr, data, **kwargs)

    def read_mezzanine_eeprom(self, mezzanine, addr, length, **kwargs):
        """
        Reads the mezzanine EEPROM via the FPGA.

        Return: bytes
        """
        eeprom_object = self._FMC_EEPROM_TABLE[mezzanine]
        return eeprom_object.read(addr, length, **kwargs)

    def write_mezzanine_eeprom(self, mezzanine, addr, data, **kwargs):
        eeprom_object = self._FMC_EEPROM_TABLE[mezzanine]
        return eeprom_object.write(addr, data, **kwargs)

    async def set_mezzanine_power_async(self, fmc_number=list(range(NUMBER_OF_FMC_SLOTS)), state=[True]*NUMBER_OF_FMC_SLOTS):
        """
        Enables or disables power of the specified FMC slot.

        Proper power sequencing is done to prevent the FMC board switchers to
        create too much a current spike when enabled.

        History:
            140223 JFC: Modified to use register names.

            140304 JM: Modified it so a state for every fmc can be specified.
                For now, state is either a boolean or a list of booleans with
                the same length as 'fmc_number' Todo: 140223 JFC: used masked
                writes to avoid side effects.
        """
        if isinstance(fmc_number, int):
            fmc_number = [fmc_number]

        if isinstance(state, (bool, int)):
            state = [state] * len(fmc_number)

        for (fmc, fmc_state) in zip(fmc_number, state):
            if fmc not in list(range(self.NUMBER_OF_FMC_SLOTS)):
                raise ValueError('FMC number %i is not a valid value' % fmc)
            else:
                # out_reg = 'OUT%i' % fmc # sets the register name to access based on the FMC number
                # cfg_reg = 'CFG%i' % fmc
                # Turn off all power signals before we enable the GPIO outputs
                # self._gpio_power.write(out_reg, 0b00000000)
                # self._gpio_power.write(cfg_reg, 0b10101000)

                # Bits are:
                #  7: SFP_LOS/SFM_ModPrsn
                #  6: FMC_CLK_DIR
                #  5: FMC_PRSNT
                #  4: FMC_PG_C2M
                #  3: FMC_PG_M2C
                #  2: FMC_EN_VADJ
                #  1: FMC_EN_3V3
                #  0: FMC_EN_12V
                if fmc_state:
                    # Turn on 12V, 3.3V and VADJ power to board
                    self._gpio_power.write(fmc, 0b00000010, mask=0b00000010)
                    # self._gpio_power.write(fmc, 0b00000110, mask=0b00000110)
                    await asyncio.sleep(0.010)
                    # Turn on 12V, 3.3V and VADJ power to board
                    self._gpio_power.write(fmc, 0b00000100, mask=0b00000100)
                    await asyncio.sleep(0.100)
                    # Turn on 12V, 3.3V and VADJ power to board
                    self._gpio_power.write(fmc, 0b00000001, mask=0b00000001)
                    await asyncio.sleep(0.050)
                    # Set Power Good (start switcher) and CLKDIR to 1
                    self._gpio_power.write(fmc, 0b01010000, mask=0b01010000)
                    await asyncio.sleep(0.050)
                else:
                    # Stop mezzanine switcher (PG=0)
                    self._gpio_power.write(fmc, 0b00000000, mask=0b01010000)
                    await asyncio.sleep(0.030)
                    # Turn off 12V
                    self._gpio_power.write(fmc, 0b00000000, mask=0b00000001)
                    await asyncio.sleep(0.030)
                    # Turn off rail
                    self._gpio_power.write(fmc, 0b00000000, mask=0b00000010)
                    await asyncio.sleep(0.030)
                    # Turn off rail
                    self._gpio_power.write(fmc, 0b00000000, mask=0b00000100)
                    await asyncio.sleep(0.100)

    async def set_led(self, led_name, state):
        """
        Set the LED(s) specified in 'led_name' to the the 'state'.
        'led_name' can be a list of LED names found in
        gpio object.  'state' can be a single boolean value, or
        an array with the same length as 'led_name'
        """
        if isinstance(led_name, str):
            led_name = [led_name]

        if isinstance(state, (bool, int)):
            state = [state] * len(led_name)

        await asyncio.sleep(0)
        for (led, led_state) in zip(led_name, state):
            self._gpio.write(led, led_state)

    async def get_led(self, led_name):
        """
        Returns the status of specified LED(s) in a dictionary
        led_status where each key is a led_name and the respective value
        is the led status.
        """
        led_status = {}
        if isinstance(led_name, str):
            led_name = [led_name]

        for led in led_name:
            led_status[led] = self._gpio.read(led)

        return(led_status)

    # def _init_temperature_sensors(self, temperature_sensor_name=None, bit_resolution=12):
    #     """ Initialize temperature sensors.

    #     'temperature_sensor_name' can be a list of temperature sensor names
    #     found in TEMPERATURE_SENSOR_TABLE. If temperature_sensor_name=None,
    #     all sensors in the list are initialized.

    #     'bit_resolution' is the number of bits of resolution of the
    #     temperature register. It can take values 9, 10, 11, 12

    #     History:
    #     140318 JM: created
    #     """
    #     if bit_resolution<9 or bit_resolution>12:
    #         raise self.ValueError('Bit_resolution is out of range. Must be 9,10,11 or 12 bits')
    #     else:
    #         if temperature_sensor_name == None:
    #             temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
    #         elif isinstance(temperature_sensor_name, str):
    #             temperature_sensor_name = [temperature_sensor_name]

    #         for temp_sensor in temperature_sensor_name:
    #             if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
    #                 raise ValueError(
    #                      'Invalid temperature sensor name. Valid names are %s'
    #                       % ','.join(self.TEMPERATURE_SENSOR_TABLE.keys()))
    #             else:
    #                 tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
    #                 try:
    #                     tmp_object.init(bit_resolution)
    #                 except:
    #                     self._logger.info(
    #                         '%r: Temperature sensor %s failed to initialize.'
    #                          % (self._iceboard, temp_sensor))

    # def _init_power_sensors(self, power_sensor_name=None):
    #     """
    #     initializes current/power monitors
    #
    #     'power_sensor_name' can be a list of current/power monitor names
    #     found in POWER_SENSOR_TABLE. If power_sensor_name=None, all sensors
    #     in POWER_SENSOR_TABLE are initialized.

    #     History:
    #     140320 JM: created
    #     """
    #     if power_sensor_name == None:
    #         power_sensor_name = self.POWER_SENSOR_TABLE.keys()
    #     elif isinstance(power_sensor_name, str):
    #         power_sensor_name = [power_sensor_name]

    #     for power_sensor in power_sensor_name:
    #         if power_sensor not in self.POWER_SENSOR_TABLE:
    #            raise ValueError(
    #                'Invalid power sensor name. Valid names are %s'
    #                % ','.join(self.POWER_SENSOR_TABLE.keys()))
    #         else:
    #             power_sensor_object, v_out, r_shunt, i_typ, tol_i = self.POWER_SENSOR_TABLE[power_sensor]
    #             try:
    #                 power_sensor_object.init(v_out=v_out, r_shunt=r_shunt, i_typ=i_typ, tol_i=tol_i)
    #             except:
    #                 self._logger.info('%r: Power sensor %s failed to initialize.' % (self._iceboard, power_sensor))

    # def get_temperature(self, temperature_sensor_name=None):
    #     """
    #     Returns the current temperature measured on the specified
    #     sensor(s).  NOTE: some temperatures are taken from the FPGA
    #     inetrnal SYSTEM monitor.

    #     initializes temperature expanders
    #     'temperature_sensor_name' can be a list of temperature sensor
    #     names found in TEMPERATURE_SENSOR_TABLE

    #     Returns a dictionary with keys corresponding to the temperature_sensor_name names.

    #     History:
    #     140318 JM: created
    #     """
    #     temperature_dict = {}
    #     if temperature_sensor_name == None:
    #         temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
    #     elif isinstance(temperature_sensor_name, str):
    #         temperature_sensor_name = [temperature_sensor_name]

    #     for temp_sensor in temperature_sensor_name:
    #         if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
    #             raise ValueError('Invalid temperature sensor name')
    #         else:
    #             tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
    #             temperature_dict[temp_sensor] = tmp_object.get_temperature()

    #     return temperature_dict

    # def get_power(self, power_sensor_name=None):
    #     """
    #     Returns the voltage, current and power of the power monitoring system.
    #     Includes power measured internally from  the FPGA's system monitor.
    #     Multiple targets can be specified.

    #     Arguments:

    #        'power_sensor_name' can be a list of temperature sensor
    #         names found in POWER_SENSOR_TABLE. If
    #         power_sensor_name=None, measurements of all sensors in
    #         TEMPERATURE_SENSOR_TABLE are returned.

    #     Returns dictionary with keys corresponding to the
    #     power_sensor_name names. The respective value is a (bus
    #     voltage (V), shunt voltage (V), current (A), power (W)) tuple.

    #     History:
    #     140320 JM: created
    #     """
    #     power_dict = {}
    #     if power_sensor_name == None:
    #         power_sensor_name = self.POWER_SENSOR_TABLE.keys()
    #     elif isinstance(power_sensor_name, str):
    #         power_sensor_name = [power_sensor_name]

    #     for power_sensor in power_sensor_name:
    #         if power_sensor not in self.POWER_SENSOR_TABLE:
    #             raise ValueError(
    #                    'Invalid power sensor name. Valid names are %s.'
    #                    % ','.join(self.POWER_SENSOR_TABLE.keys()))
    #         else:
    #             power_sensor_object = self.POWER_SENSOR_TABLE[power_sensor][0]

    #             try:
    #                 bus_voltage = power_sensor_object.get_bus_voltage()
    #                 shunt_voltage = power_sensor_object.get_shunt_voltage()
    #                 current = power_sensor_object.get_current()
    #                 power =  power_sensor_object.get_power()
    #             except:
    #                 bus_voltage = None
    #                 shunt_voltage = None
    #                 current = None
    #                 power = None
    #             power_dict[power_sensor]=(bus_voltage, shunt_voltage, current, power)

    #     return power_dict

    # def get_serial_number(self):
    #     """
    #     Returns the board's serial number. which is actually the FPGA's
    #     serial number.
    #     """
    #     return self._iceboard.get_serial_number(); # tentative code

    # def get_info(self):
    #     """Loads the info data on the motherboard"""
    #     pass

    # def status(self):
    #     """Displays the status of the motherboard"""


# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
