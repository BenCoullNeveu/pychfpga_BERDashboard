#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: C0301

"""
iceboard.py module.
Provides access to the basic functions of an ICEBoard (Model MGK7MB)

 History:
        2014-03-04 JFC: Created
        2014-03-18 JM: Added get_temperature and init_temp_sensors
"""

import logging

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, backref, reconstructor

# Force reloading of the hardware map module to allow this module
# reloads to succeed We need to make sure we use a freshly created
# hardware_map module because HWMResource uses with a new dynamically
# created Base class that statically remembers the current schema.
# Therefore, SQLAlchemy will complain that the table already exist) if
# we reloan this module and try to create an instrumented class that
# already exists in the schema.
from .. import hardware_map
reload(hardware_map)

import fpga
import arm

# import hardware handlers
import tmp100
import pca9575
import tca9548a

# Temporary lookup table used to determine the ARM address based on the
# FPGA serial number since we don't have a way to find which ARM
# processor is out there.  Eventually the ARMs will have a discovery
# protocol that will allow us to get this information on the fly.  We
# use the ARM's MAC address as its unique serial number, but it could be
# anything.
ARM_TABLE = {
    # ARM IP address : (ARM Serial (MAC address), FPGA serial , board_number, locked)
    '10.10.10.57': ('84:7E:40:6F:4A:F2', '10.10.10.37', 0x2069c2107eb05c,  7 , False),
    '10.10.10.18': ('84:7E:40:6F:CC:CA', '10.10.10.48', 0x24d046483e301c, 18 , True),
    '10.10.10.5' : ('84:7E:40:6F:63:18', '10.10.10.35', 0,                 5 , False),
    '10.10.10.9' : ('84:7E:40:6F:D4:CA', '10.10.10.39', 0,                 9 , False),
    '10.10.10.8' : ('84:7E:40:6F:41:E8', '10.10.10.38', 0x6869c2107eb05c,  8 , False),
    '10.10.10.14': ('84:7E:40:6F:CC:BE', '10.10.10.44', 0x3829c2107eb05c, 14 , False),
    '10.10.10.17': ('84:7E:40:6F:CC:9C', '10.10.10.47', 0,                17 , False),
    '10.10.10.19': ('84:7E:40:6F:CC:82', '10.10.10.49', 0x1829c2107eb05c, 19 , False),
    '10.10.10.16': ('84:7E:40:70:01:CA', '10.10.10.46', 0,                16 , False),
}

class IceBoard(hardware_map.HWMResource):
    """
    Provides access to the basic functions of an IceBoard Rev2/Rev3.

    This object inherits from a generic Hardware Manager resource,
    which allows the iceboard objects to be added to the hardware
    map database.

    The methods and properties have access to the hardware or firmware
    in one of the the following ways:
        - The low-level hardware access is made directly in python
          through the ARM or FPGA I2C links to the board.
        - The low-level hardware access is implemented in the ARM<
          software, and all methods and properties are imported
          through tuber.

    Project-specific classes are meant to be derived from this class.
    """

    # Hardware Map attributes

    __tablename__ = 'iceboards'
    __table_args__ = (
        # {'extend_existing':True},
        # UniqueConstraint('serial_number'),
        # UniqueConstraint('tuber_uri')
    )
    __mapper_args__ = {
            'polymorphic_identity': 'iceboard',
            'polymorphic_on': 'cls'
    }

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    serial_number = Column(Integer) # serial number of the board
    arm_ip_addr = Column(String)

    def _interface_ip_address_error(self):
        logger = logging.getLogger(__name__)
        logger.error('Currently do not support opening FPGA links with Iceboards objects created from the database because the interface address in unknown for UDP binding')

    interface_ip_address = property(_interface_ip_address_error) # This will be overriden

    @classmethod
    def discover(cls, timeout, interface_ip_addr):
        """
        Populate the resource database with the list of available
        Iceboards found on the network. 'timout' indicates the time we
        wait for an answer before we decide that there is no board.

        For now, this function finds the ARMs by probing all addresses
        from a static tables. The Iceboards are identified by
        verifying if their ARM processors offer a tuber interface.
        Once we have a broadcast discovery protocol in the ARM the
        table will not be necessary.
        """
        logger = logging.getLogger(__name__)

        iceboard_list = []
        for arm_ip_addr in ARM_TABLE.keys():
            if arm.Arm.ping_tuber(arm_ip_addr):
                logger.debug('Found an ARM board with tuber at %s!' % (arm_ip_addr))
                res = cls(arm_ip_addr = arm_ip_addr, interface_ip_addr = interface_ip_addr)
                logger.debug('Created IceBoard object %s' % res)
                iceboard_list.append(res)

        return iceboard_list

    class IceBoardException(Exception):
        pass

    NUMBER_OF_FMC_SLOTS = 2 # Indicates the number of FMC slots supported by this platform

    FPGA_I2C_SWITCH_ADDR = 0b1110100
    ARM_I2C_SWITCH_ADDR = None # need to look this one up

    GPIO_POWER_I2C_ADDR = 0b0100000
    GPIO_SFP_QSFP_I2C_ADDR = 0b0100001
    GPIO_SW_LEDS_ADDR = 0b0100010
    GPIO_ARM_PHY_LEDS_ADDR = 0b0100011

    TMP_ARM_I2C_ADDR = 0b1001010
    TMP_PHY_I2C_ADDR = 0b1001100
    TMP_FPGA_I2C_ADDR = 0b1001011
    TMP_POWER_I2C_ADDR = 0b1001000

    class I2CInterface(object):
        """
        This class wraps all that is needed to access an I2C device in
        a standardized way, whether the access is done through the
        FPGA or through the ARM.
        """
        def __init__(self, write_read_fn, port_select_fn, bus_table, switch_addr, verbose = None):
            self.write_read_fn = write_read_fn
            self.set_port_fn = port_select_fn
            self.I2C_BUS_LIST = bus_table

            self.i2c_switch = tca9548a.tca9548a(self, switch_addr)
            self.logger = logging.getLogger(__name__)

        def select_bus(self, bus_names):
            """
            Configure the I2C port and I2C switch so the following
            communications will access the desired I2C bus. 'bus_id'
            can be a bus name or bus number, or a list of those if
            multiple buses are to be accessed at the same time. An
            error will be provided if all the buses are not accessible
            through the same FPGA I2C port. This function assumes that
            each FPGA I2C port has an identical I2C switch.
            """
            if isinstance(bus_names, (str, int)):
                bus_names = [bus_names]
            selected_fpga_port_number = None
            selected_switch_port_numbers = []
            for bus_name in bus_names:
                if bus_name not in self.I2C_BUS_LIST:
                    self.logger.error("I2C bus '%s' is not part of the available buses. Valid values are %s" % (bus_name, ','.join(str(self.I2C_BUS_LIST.keys()))) )
                (fpga_port_number, switch_port_number) = self.I2C_BUS_LIST[bus_name]
                if selected_fpga_port_number is None:
                    selected_fpga_port_number = fpga_port_number
                elif selected_fpga_port_number != fpga_port_number:
                    self.logger.error("I2C bus '%s' is not on the same FPGA port as the other buses" % (bus_name) )
                selected_switch_port_numbers.append(switch_port_number)
                self.logger.debug("Enabling I2C bus %s" % bus_name)

            self.set_port_fn(selected_fpga_port_number)

            self.i2c_switch.set_port(selected_switch_port_numbers)

        def write_read(self, *args, **kwargs):
            """
            Writes up to 3 bytes to the addressed I2C device and/or
            reads up to 4 bytes from that device after a restart. See
            the FPGA I2C module for detailed method description.
            """
            self.logger.debug("Accessing I2C bus...")
            return self.write_read_fn(*args, **kwargs)

    def __init__(self, arm_ip_addr, interface_ip_addr=None):
        """
        Creates an Iceboard that is accessed through the specified IP address.
        """

        # For now we lookup a bunch of iceboard parameters from a table
        # because we don't have access to this info yet.  Normally we
        # would query the hardware to get this information
        (arm_serial_number, fpga_ip_addr, fpga_serial_number, board_serial_number, lock_flag) = ARM_TABLE[arm_ip_addr]

        # Initialize database columns. Those can be pre-initialized or
        # preserved
        self.serial_number = board_serial_number
        self.arm_ip_addr = arm_ip_addr

        # Initialize local variables. These are rebuilt every time.

        self.interface_ip_addr = interface_ip_addr # this is necessary evil for now... This would not be recreated if the object is reconstructed from the database

        self.logger = logging.getLogger(__name__)
        self.logger.debug('Initializing Iceboard object S/N %03i' % (self.serial_number))
        self.open()

    @reconstructor # SQLAlchemy decorator indicating that this method is to be called when the object is recreated from the database
    def _init_from_database(self):
        """
        Reconstructs the Iceboard basic information from the database
        entry and open the link to the Iceboard.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Reconstructing Iceboard object S/N %03i from database entry' % (self.serial_number))

        self.open()

    def open(self):

        # For now we lookup a bunch of iceboard parameters from a table
        # because we don't have access to this info yet.  Normally we
        # would query the hardware to get this information
        (arm_serial_number, fpga_ip_addr, fpga_serial_number, board_serial_number, lock_flag) = ARM_TABLE[self.arm_ip_addr]

        self.arm_serial_number = arm_serial_number
        self.fpga_ip_addr = fpga_ip_addr
        self.fpga_serial_number = fpga_serial_number
        self.fpga_port = 41000 + 4*(board_serial_number)
        self.fpga_subarray = 0 # another thing we probably won't need

        self.lock_flag = lock_flag

        self.arm = arm.Arm(self.arm_ip_addr)
        self.i2c = None # For now the i2c handler is not yet accessible as we need the FPGA firmware for this
        self.fpga = None # the fpga object will be created once we configure the FPGA

        # self.self_reference = self # circular reference that ensures that the object will persist in memory until explicitely closed with close(). Adding the object to the database is not sufficient to prevent this as this uses a weak reference.

    def configure_fpga(self, bitfile):
        """
        Configure the FPGAs on the ICEboard(s)

        We need the interface IP address in self.interface_ip_address
        to determine on which interface to listen for UDP replies. We
        won't need this parameter once we access the FPGA through the
        ARM using TCP.
        """
        # For now we do this the worst possible way: by programming each FPGA one aftet the other.
        # This should be rewritten to allow concurrent programming of all FPGAs, maybe using zeroMQ.

        interfaces = self.interface_ip_addr

        # First, we check if the desired FPGA already replies to broadcasts.
        # If so, we know it is programmed with *some* firmware and we can do further checks
        # and potentially could avoid reprogramming the FPGA

        self.logger.info('Checking if the FPGAs can be found on the network')
        fpga_serials = fpga.Fpga.discover_fpgas(interfaces)

        if self.fpga_serial_number not in fpga_serials: # if the FPGA has not replied, we program it
            self.logger.info('Configuring FPGA on board #%i through ARM at address %s' % (self.serial_number, self.arm_ip_addr))
            if self.locked:
                self.IceBoardException('Iceboard with serial %016X is locked and its FPGA cannot be configured' % self.serial_number)
            # arm_ = arm.Arm(ice.arm_ip_addr)
            self.arm.configure_fpga(bitfile)
        else:
            self.logger.info('FPGA on board #%i,  ARM address %s is already configured. Skipping configuration' % (self.serial_number, self.arm_ip_addr))

        self.logger.info('Checking again what FPGAs are on the network')
        fpga_serials = fpga.Fpga.discover_fpgas(interfaces)

        self.logger.info('Instantiating FPGAs and IceBoards')

        if self.fpga_serial_number not in fpga_serials:
            self.logger.error('Failed to find FPGA on board #%i' % (self.serial_number))
        else:
            self.logger.info('Creating FPGA firmware and Iceboard hardware resource handlers for board #%i' % (self.serial_number))
            if self.fpga:
                self.fpga.close()
            self.fpga = fpga.Fpga(self.interface_ip_addr, self.fpga_ip_addr, self.fpga_port, serial_number = self.fpga_serial_number) # here we need the serial number because we use the FPGA Ethernet interface.
            self.open_i2c()

    def __repr__(self):
        return 'Iceboard S/N %03i' % self.serial_number

    def open_i2c(self):
        """
        Establishes the connection with the hardware. This essentially
        creates all the I2C objects needed to interface the hardware.
        For now, we can only do this when the FPGA is configured
        because access is done through the FPGA
        """

        # Defines a standardized I2C interface object to be used to communicate with the board's hardware.
        # The functions underlying this interface varies depending on whether the ARM or FPGA is used to talk to the board:
        #   - With the FPGA we need to know the FPGA port associated with each I2C bus.
        #   - The I2C switch address is different for the ARM compared to the FPGA
        self.logger.info(' Instantiating motherboard I2C manager')
        if self.fpga:
            i2c_bus_list = {
                "FMC": (0, 0), # equivalent to FMCA. Included for backwards compatibility with single-FMC code
                "FMCA": (0, 0),
                "FMCB": (0, 1),
                "QSFPA": (0, 2),
                "QSFPB": (0, 3),
                "SFP": (0, 4),
                "SMPS": (0, 5),
                "BP": (0, 6),
                "GPIO": (0, 7)
                }
            self.i2c = self.I2CInterface(self.fpga.i2c_write_read, self.fpga.i2c_set_port, i2c_bus_list, self.FPGA_I2C_SWITCH_ADDR)

        self.logger.info(' Instantiating I2C GPIO manager')
        self.gpio_power = pca9575.pca9575(self.i2c, self.GPIO_POWER_I2C_ADDR, 'GPIO')
        self.gpio_sw_leds = pca9575.pca9575(self.i2c, self.GPIO_SW_LEDS_ADDR, 'GPIO')
        self.gpio_arm_phy_leds = pca9575.pca9575(self.i2c, self.GPIO_ARM_PHY_LEDS_ADDR, 'GPIO')
        self.gpio_sfp_qsfp = pca9575.pca9575(self.i2c, self.GPIO_SFP_QSFP_I2C_ADDR, 'GPIO')

        self.logger.info(' Instantiating I2C temperature sensors')
        self.tmp_power = tmp100.tmp100(self.i2c, self.TMP_POWER_I2C_ADDR, 'GPIO')
        self.tmp_phy = tmp100.tmp100(self.i2c, self.TMP_PHY_I2C_ADDR, 'GPIO')
        self.tmp_fpga = tmp100.tmp100(self.i2c, self.TMP_FPGA_I2C_ADDR, 'GPIO')
        self.tmp_arm = tmp100.tmp100(self.i2c, self.TMP_ARM_I2C_ADDR, 'GPIO')

        self.GPIO_EXPANDER_MAP = {
            # name : (expander object, byte, bit number (width))
            'GP_SW1': (self.gpio_sw_leds, 0, 0),
            'GP_SW2': (self.gpio_sw_leds, 0, 1),
            'GP_SW3': (self.gpio_sw_leds, 0, 2),
            'GP_SW4': (self.gpio_sw_leds, 0, 3),
            'GP_SW5': (self.gpio_sw_leds, 0, 4),
            'GP_SW6': (self.gpio_sw_leds, 0, 5),
            'GP_SW7': (self.gpio_sw_leds, 0, 6),
            'GP_SW8': (self.gpio_sw_leds, 0, 7),
            'GP_LED1': (self.gpio_sw_leds, 1, 7),
            'GP_LED2': (self.gpio_sw_leds, 1, 6),
            'GP_LED3': (self.gpio_sw_leds, 1, 5),
            'GP_LED4': (self.gpio_sw_leds, 1, 4),
            'GP_LED5': (self.gpio_sw_leds, 1, 3),
            'GP_LED6': (self.gpio_sw_leds, 1, 2),
            'GP_LED7': (self.gpio_sw_leds, 1, 1),
            'GP_LED8': (self.gpio_sw_leds, 1, 0),
            'GP_LED9': (self.gpio_arm_phy_leds, 0, 0),
            'GP_LED10': (self.gpio_arm_phy_leds, 0, 1),
            'GP_LED11': (self.gpio_arm_phy_leds, 0, 2),
            'GP_LED12': (self.gpio_arm_phy_leds, 0, 3),
            'GTX1V8PowerFault': (self.gpio_arm_phy_leds, 0, 4),
            'PHYAPowerFault': (self.gpio_arm_phy_leds, 0, 5),
            'PHYBPowerFault': (self.gpio_arm_phy_leds, 0, 6),
            'ArmPowerFault': (self.gpio_arm_phy_leds, 0, 7)
        }

        self.TEMPERATURE_SENSOR_TABLE = {
            # name: tmp object
            'TEMP_POWER': self.tmp_power,
            'TEMP_PHY': self.tmp_phy,
            'TEMP_FPGA': self.tmp_fpga,
            'TEMP_ARM': self.tmp_arm
        }

    def close(self):
        self.logger.info('Closing FPGA and Iceboard handlers for board #%i' % (self.serial_number))
        if self.i2c:
            self.i2c = None
        if self.fpga:
            self.fpga.close()
            self.fpga = None
        if self.arm:
            self.arm.close()
            self.arm = None
        #self.self_reference = None # Now the object can be garbage collected if no one else uses it

    def init(self):
        """Initializes the motherboard hardware to a known state"""
        self.init_gpio_expanders()
        self.init_temp_sensors()
        self.init_eeprom()
        self.set_fmc_power()

    def init_gpio_expanders(self):
        """
        Initializes GPIO expanders

        History
        140304 JM: created. todo: make more flexible for I/O pin configuration of each expander. Need to confirm I/O pin config with JF
        """
        self.gpio_power.init(cfg0_def=0b10101000, cfg1_def=0b10101000)
        self.gpio_sw_leds.init(cfg1_def=0b00000000)
        self.gpio_arm_phy_leds.init(cfg0_def=0b11110000)
        #self.gpio_sfp_qsfp.init(cfg0_def=0b00000000)

    def init_temperature_sensors(self, temperature_sensor_name, bit_resolution=12):
        """
        initializes temperature expanders
        'temperature_sensor_name' can be a list of temperature sensor names found in TEMPERATURE_SENSOR_TABLE
        'bit_resolution' is the number of bits of resolution of the temperature register. It can take values 9, 10, 11, 12

        History:
        140318 JM: created
        """
        if bit_resolution<9 or bit_resolution>12:
            raise self.IceBoardException('bit_resolution is out of range')
        else:
            if isinstance(temperature_sensor_name, str):
                temperature_sensor_name = [temperature_sensor_name]

            for temp_sensor in temperature_sensor_name:
                if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                    raise IceBoardException('Invalid temperature sensor name')
                else:
                    tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
                    tmp_object.init(bit_resolution)

    def init_eeprom(self):
        """initializes EEPROM"""
        pass

    def get_number_of_fmc_slots(self):
        return self.NUMBER_OF_FMC_SLOTS

    def set_fmc_power(self, fmc_number=range(NUMBER_OF_FMC_SLOTS), state=[True]*NUMBER_OF_FMC_SLOTS):
        """
        Enables or disables power of the specified FMC slot.
        Proper power sequencing is done to prevent the FMC board switchers to create too much a current spike when enabled.

        History:
            140223 JFC: Modified to use register names.
            140304 JM: Modified it so a state for every fmc can be specified. For now, state is either a boolean or a list of booleans with the same length as 'fmc_number'
        Todo:
            140223 JFC: used masked writes to avoid side effects.
        """
        if isinstance(fmc_number, int):
            fmc_number = [fmc_number]

        if isinstance(state, (bool, int)):
            state = [state] * len(fmc_number)

        for (fmc,fmc_state) in zip(fmc_number,state):
            if fmc not in range(self.NUMBER_OF_FMC_SLOTS):
                raise self.IceBoardException('FMC number %i is not a valid value' % fmc)
            else:
                out_reg = 'OUT%i' % fmc # sets the register name to access based on the FMC number
                #cfg_reg = 'CFG%i' % fmc
                self.gpio_power.write(out_reg, 0b00000000) # Turn off all power signals before we enable the GPIO outputs
                #self.gpio_power.write(cfg_reg, 0b10101000)
                self.gpio_power.write(out_reg, 0b00000111*bool(fmc_state)) # Turn on power to board
                self.gpio_power.write(out_reg, 0b01010111*bool(fmc_state)) # Set Power Good and CLKDIR to 1

    def set_led(self, led_name, state):
        """
        Set the LED(s) specified in 'led_name' to the the 'state'.
        'led_name' can be a list of LED names found in
        GPIO_EXPANDER_MAP.  'state' can be a single boolean value, or
        an array with the same length as 'led_name'
        """
        if isinstance(led_name, str):
            led_name = [led_name]

        if isinstance(state, (bool, int)):
            state = [state] * len(led_name)

        for (led, led_state) in zip(led_name,state):
            if led not in self.GPIO_EXPANDER_MAP:
                raise IceBoardException('Invalid LED name')
            else:
                led_info = self.GPIO_EXPANDER_MAP[led]
                io_expander = led_info[0]
                led_byte = led_info[1]
                led_bit = led_info[2]

                io_expander.write('CFG%i' % led_byte, 0b00000000 , mask = 1<<led_bit) # Configuring pin corresponding to led as output
                io_expander.write('OUT%i' % led_byte, (1<<led_bit) * bool(led_state) , mask = 1<<led_bit)

    def get_led(self, led_name):
        """
        Returns the status of specified LED(s) in a dictionary
        led_status where each key is a led_name and the respective value
        is the led status.
        """
        led_status = {}
        if isinstance(led_name, str):
            led_name = [led_name]

        for led in led_name:
            if led not in self.GPIO_EXPANDER_MAP:
                raise IceBoardException('Invalid LED name')
            else:
                led_info = self.GPIO_EXPANDER_MAP[led]
                io_expander = led_info[0]
                led_byte = led_info[1]
                led_bit = led_info[2]

                led_status[led]=bool(io_expander.read('IN%i' % led_byte) & (1<<led_bit))

        return led_status

    def get_temperature(self, temperature_sensor_name):
        """
        Returns the current temperature measured on the specified
        sensor(s).  NOTE: some temperatures are taken from the FPGA
        inetrnal SYSTEM monitor.

        initializes temperature expanders
        'temperature_sensor_name' can be a list of temperature sensor
        names found in TEMPERATURE_SENSOR_TABLE

        History:
        140318 JM: created
        """
        temperature_dict = {}
        if isinstance(temperature_sensor_name, str):
            temperature_sensor_name = [temperature_sensor_name]

        for temp_sensor in temperature_sensor_name:
            if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                raise IceBoardException('Invalid temperature sensor name')
            else:
                tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
                temperature_dict[temp_sensor]=tmp_object.get_temperature()

        return temperature_dict

    def get_power(self, target):
        """
        Returns the voltage and current of the power monitoring system.
        Includes power measured internally from  the FPGA's system
        monitor.  Multiple targets can be specified.  The power is
        returned as a (voltage, current) tuple.
        """
        pass

    def get_serial_number(self):
        """
        Returns the board's serial number. which is actually the FPGA's
        serial number.
        """
        self.fpga.get_serial_number(); # tentative code

    def get_info(self):
        """Loads the info data on the motherboard"""
        pass

    def status(self):
        """Displays the status of the motherboard"""

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
