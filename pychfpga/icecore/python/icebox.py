#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: C0301

"""iceboard_hardware.py module: Provides a class to access the hardware of IceBoard
(McGill Model MGK7MB).
"""

import logging

# Import IceBoard hardware handlers
from lib import tmp100 # I2C Temperature sensor
from lib.fmc_eeprom import FMC_EEPROM
# import pca9575 # I2C 16-bit IO Expander
# import tca9548a # I2C switch
# import ina230 # I2C Voltage and current monitor

class IceBoxException(Exception):
    pass
class IceBox(object):
    """
    Provides access to the IceBox (IceBoard backplane):
    """

    #------------------------------------
    # Define hardware-specific constants
    #------------------------------------
    NUMBER_OF_SLOTS = 16 #
    BACKPLANE_EEPROM_DATA_ADDRESS = 0x54 # covers 0x54 - 0x57
    BACKPLANE_EEPROM_SERIAL_ADDRESS = 0x5C # 16 byte serial number starting at address 0
    BACKPLANE_EEPROM_ADDRESS_WIDTH = 10
    # _FPGA_I2C_SWITCH_ADDR = 0b1110100
    # _ARM0_I2C_SWITCH_ADDR = 0b1110000
    # _ARM1_I2C_SWITCH_ADDR = 0b1110001
    # _ARM2_I2C_SWITCH_ADDR = 0b1110010
    # _ARM3_I2C_SWITCH_ADDR = 0b1110011

    # _GPIO_POWER_I2C_ADDR = 0b0100000
    # _GPIO_SFP_QSFP_I2C_ADDR = 0b0100001
    # _GPIO_SW_LEDS_ADDR = 0b0100010
    # _GPIO_ARM_PHY_LEDS_ADDR = 0b0100011

    # _TMP_ARM_I2C_ADDR = 0b1001010
    # _TMP_PHY_I2C_ADDR = 0b1001100
    # _TMP_FPGA_I2C_ADDR = 0b1001011
    # _TMP_POWER_I2C_ADDR = 0b1001000

    # _POWER_ICEVADJ_I2C_ADDR = 0b1000011
    # _POWER_ICE12V0_I2C_ADDR = 0b1000111
    # _POWER_ICE5V0_I2C_ADDR = 0b1001000
    # _POWER_ICE3V3_I2C_ADDR = 0b1001001
    # _POWER_ICE1V5_I2C_ADDR = 0b1001100
    # _POWER_ICE1V2_I2C_ADDR = 0b1001101
    # _POWER_ICE1V0_I2C_ADDR = 0b1001110
    # _POWER_ICE1V8_I2C_ADDR = 0b1001011
    # _POWER_ICE1V0GTX_I2C_ADDR = 0b1001111

    @classmethod
    def get_backplane_info(cls, iceboard):
        logger = logging.getLogger(__name__)
        logger.debug("Attempting to read backplane eeprom to determine board presence")
        eeprom = FMC_EEPROM(iceboard.i2c, 'BP', address=cls.BACKPLANE_EEPROM_DATA_ADDRESS, address_width=cls.BACKPLANE_EEPROM_ADDRESS_WIDTH)
        data = eeprom.read(0, length=1, noerror=True, verbose=1)
        logger.debug("Backplane EEPROM returned the value: %i", data[0])
        return (data[0], None)


    def __init__(self, iceboard):
        """
        Creates all the I2C objects needed to interface the hardware.
        For now, we can only do this when the FPGA is configured
        because access is done through the FPGA.

        For FPGA-based I2C:
            - fpga_core is not Null
            - fpga_core provides the following methods
                - i2c_set_port(...) # Port number 0 (connected to the FPGA I2C switch) is used for all accesses
                - i2c_write_read(...) # FPGA I2C engine
        """
        self._I2C_BACKPLANE_BUS_NAME = 'BP'
        self._logger = logging.getLogger(__name__)
        self._logger.debug('Initializing Iceboard hardware')
        self._i2c = iceboard.i2c
        self._iceboard_hw = iceboard.hw
        self._iceboard = iceboard

        self._logger.info(' Instantiating Backplane I2C resource managers')
        self._eeprom = FMC_EEPROM(iceboard.i2c, 'BP', address=self.BACKPLANE_EEPROM_DATA_ADDRESS, address_width=self.BACKPLANE_EEPROM_ADDRESS_WIDTH)
        self._serial = FMC_EEPROM(iceboard.i2c, 'BP', address=self.BACKPLANE_EEPROM_SERIAL_ADDRESS, address_width=self.BACKPLANE_EEPROM_ADDRESS_WIDTH)

        # self._gpio_power = pca9575.pca9575(self._i2c, self._GPIO_POWER_I2C_ADDR, 'GPIO')
        # self._gpio_sw_leds = pca9575.pca9575(self._i2c, self._GPIO_SW_LEDS_ADDR, 'GPIO')
        # self._gpio_arm_phy_leds = pca9575.pca9575(self._i2c, self._GPIO_ARM_PHY_LEDS_ADDR, 'GPIO')
        # self._gpio_sfp_qsfp = pca9575.pca9575(self._i2c, self._GPIO_SFP_QSFP_I2C_ADDR, 'GPIO')

        # self._logger.info(' Instantiating I2C temperature sensors')
        # self._tmp_power = tmp100.tmp100(self._i2c, self._TMP_POWER_I2C_ADDR, 'GPIO')
        # self._tmp_phy = tmp100.tmp100(self._i2c, self._TMP_PHY_I2C_ADDR, 'GPIO')
        # self._tmp_fpga = tmp100.tmp100(self._i2c, self._TMP_FPGA_I2C_ADDR, 'GPIO')
        # self._tmp_arm = tmp100.tmp100(self._i2c, self._TMP_ARM_I2C_ADDR, 'GPIO')

        # self._logger.info(' Instantiating I2C current/power monitors')
        # self._power_ice_3v3 = ina230.ina230(self._i2c, self._POWER_ICE3V3_I2C_ADDR, 'SMPS')
        # self._power_ice_12v0 = ina230.ina230(self._i2c, self._POWER_ICE12V0_I2C_ADDR, 'SMPS')
        # self._power_ice_5v0 = ina230.ina230(self._i2c, self._POWER_ICE5V0_I2C_ADDR, 'SMPS')
        # self._power_ice_1v0_gtx = ina230.ina230(self._i2c, self._POWER_ICE1V0GTX_I2C_ADDR, 'SMPS')
        # self._power_ice_vadj = ina230.ina230(self._i2c, self._POWER_ICEVADJ_I2C_ADDR, 'SMPS')
        # self._power_ice_1v2 = ina230.ina230(self._i2c, self._POWER_ICE1V2_I2C_ADDR, 'SMPS')
        # self._power_ice_1v5 = ina230.ina230(self._i2c, self._POWER_ICE1V5_I2C_ADDR, 'SMPS')
        # self._power_ice_1v0 = ina230.ina230(self._i2c, self._POWER_ICE1V0_I2C_ADDR, 'SMPS')
        # self._power_ice_1v8 = ina230.ina230(self._i2c, self._POWER_ICE1V8_I2C_ADDR, 'SMPS')

        # self.GPIO_EXPANDER_MAP = {
        #     # name : (expander object, byte, bit number (width))
        #     'GP_SW1': (self._gpio_sw_leds, 0, 0),
        #     'GP_SW2': (self._gpio_sw_leds, 0, 1),
        #     'GP_SW3': (self._gpio_sw_leds, 0, 2),
        #     'GP_SW4': (self._gpio_sw_leds, 0, 3),
        #     'GP_SW5': (self._gpio_sw_leds, 0, 4),
        #     'GP_SW6': (self._gpio_sw_leds, 0, 5),
        #     'GP_SW7': (self._gpio_sw_leds, 0, 6),
        #     'GP_SW8': (self._gpio_sw_leds, 0, 7),
        #     'GP_LED1': (self._gpio_sw_leds, 1, 7),
        #     'GP_LED2': (self._gpio_sw_leds, 1, 6),
        #     'GP_LED3': (self._gpio_sw_leds, 1, 5),
        #     'GP_LED4': (self._gpio_sw_leds, 1, 4),
        #     'GP_LED5': (self._gpio_sw_leds, 1, 3),
        #     'GP_LED6': (self._gpio_sw_leds, 1, 2),
        #     'GP_LED7': (self._gpio_sw_leds, 1, 1),
        #     'GP_LED8': (self._gpio_sw_leds, 1, 0),
        #     'GP_LED9': (self._gpio_arm_phy_leds, 0, 0),
        #     'GP_LED10': (self._gpio_arm_phy_leds, 0, 1),
        #     'GP_LED11': (self._gpio_arm_phy_leds, 0, 2),
        #     'GP_LED12': (self._gpio_arm_phy_leds, 0, 3),
        #     'GTX1V8PowerFault': (self._gpio_arm_phy_leds, 0, 4),
        #     'PHYAPowerFault': (self._gpio_arm_phy_leds, 0, 5),
        #     'PHYBPowerFault': (self._gpio_arm_phy_leds, 0, 6),
        #     'ArmPowerFault': (self._gpio_arm_phy_leds, 0, 7)
        # }

        # self.TEMPERATURE_SENSOR_TABLE = {
        #     # sensor name: tmp object
        #     'TEMP_POWER': self._tmp_power,
        #     'TEMP_PHY': self._tmp_phy,
        #     'TEMP_FPGA': self._tmp_fpga,
        #     'TEMP_ARM': self._tmp_arm
        # }

        # self.POWER_SENSOR_TABLE = {
        #     # sensor name : (ina230 object, output voltage(volts), rshunt(inductor) (mohm), typical current(amps), current tolerance (0<tol<1))
        #     'ICE_3V3': (self._power_ice_3v3, 3., 2.36, 8., 0.5),
        #     'ICE_12V0': (self._power_ice_12v0, 12., 5.5, 3., 0.5),
        #     'ICE_5V0': (self._power_ice_5v0, 5., 2.36, 11., 0.5),
        #     'ICE_1V0_GTX': (self._power_ice_1v0_gtx, 1., 0.77, 16., 0.5),
        #     'ICE_1V2': (self._power_ice_1v2, 1.2, 0.77, 8., 0.5),
        #     'ICE_1V5': (self._power_ice_1v5, 1.5, 2.36, 3., 0.5),
        #     'ICE_1V0': (self._power_ice_1v0, 1., 0.77, 16., 0.5),
        #     'ICE_1V8': (self._power_ice_1v8, 1.8, 5.5, 1., 0.5),
        #     'ICE_VADJ': (self._power_ice_vadj, 2.5, 2.36, 8., 0.5)
        # }

    def open(self):
        """
        """
        pass


    def close(self):
        self._logger.info('Closing Icebox hardware')


    # def get_backplane_info(self, iceboard):
    #     # logger = logging.getLogger(__name__)
    #     self._logger.debug("Attempting to read backplane eeprom to determine board presence")
    #     # eeprom = FMC_EEPROM(iceboard.i2c, 'BP', address=cls.BACKPLANE_EEPROM_ADDRESS)
    #     eeprom_data = self._eeprom.read(0, length=1, noerror=True, verbose=1)
    #     self._logger.debug("Backplane EEPROM returned the value: %i", data[0])
    #     slot_number = self._iceboard.get_slot_number()
    #     return (eeprom_data[0], slot_number)


    def init(self):
        """Initializes the motherboard hardware to a known state"""
        # self._init_gpio_expanders()
        # self._init_temperature_sensors()
        # self._init_eeprom()
        # self.set_fmc_power()

    def _init_gpio_expanders(self):
        """
        Initializes GPIO expanders

        History
        140304 JM: created. todo: make more flexible for I/O pin configuration of each expander. Need to confirm I/O pin config with JF
        """
        self._gpio_power.init(cfg0_def=0b10101000, cfg1_def=0b10101000)
        self._gpio_sw_leds.init(cfg1_def=0b00000000)
        self._gpio_arm_phy_leds.init(cfg0_def=0b11110000)
        #self._gpio_sfp_qsfp.init(cfg0_def=0b00000000)

    def _init_temperature_sensors(self, temperature_sensor_name=None, bit_resolution=12):
        """
        initializes temperature sensors
        'temperature_sensor_name' can be a list of temperature sensor names found in TEMPERATURE_SENSOR_TABLE. If temperature_sensor_name=None, all sensors in
        'bit_resolution' is the number of bits of resolution of the temperature register. It can take values 9, 10, 11, 12

        History:
        140318 JM: created
        """
        if bit_resolution<9 or bit_resolution>12:
            raise self.IceBoardHardwareException('bit_resolution is out of range')
        else:
            if temperature_sensor_name == None:
                temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
            elif isinstance(temperature_sensor_name, str):
                temperature_sensor_name = [temperature_sensor_name]

            for temp_sensor in temperature_sensor_name:
                if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                    raise IceBoardHardwareException('Invalid temperature sensor name')
                else:
                    tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
                    tmp_object.init(bit_resolution)

    def _init_power_sensors(self, power_sensor_name=None):
        """
        initializes current/power monitors
        'power_sensor_name' can be a list of current/power monitor names found in POWER_SENSOR_TABLE. If power_sensor_name=None, all sensors in
        POWER_SENSOR_TABLE are initialized.

        History:
        140320 JM: created
        """
        if power_sensor_name == None:
            power_sensor_name = self.POWER_SENSOR_TABLE.keys()
        elif isinstance(power_sensor_name, str):
            power_sensor_name = [power_sensor_name]

        for power_sensor in power_sensor_name:
            if power_sensor not in self.POWER_SENSOR_TABLE:
                raise IceBoardHardwareException('Invalid current/power monitor name')
            else:
                power_sensor_list = self.POWER_SENSOR_TABLE[power_sensor]
                power_sensor_object = power_sensor_list[0]
                power_sensor_object.init(v_out=power_sensor_list[1], r_shunt=power_sensor_list[2], i_typ=power_sensor_list[3], tol_i=power_sensor_list[4])


    def _init_eeprom(self):
        """initializes EEPROM"""
        pass

    def get_number_of_slots(self):
        return self.NUMBER_OF_SLOTS

    def read_eeprom(self, addr, length=1):
        return self._eeprom.read(addr, length = length)

    def get_eeprom_serial_number(self):
        """ return the 128-bit hardware-coded EEPROM serial number as a hex string. """
        return ''.join(['%02X' % v for v in self._serial.read(0x80, length=16)])

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
                raise IceBoardHardwareException('Invalid LED name')
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
                raise IceBoardHardwareException('Invalid LED name')
            else:
                led_info = self.GPIO_EXPANDER_MAP[led]
                io_expander = led_info[0]
                led_byte = led_info[1]
                led_bit = led_info[2]

                led_status[led]=bool(io_expander.read('IN%i' % led_byte) & (1<<led_bit))

        return led_status

    def get_temperature(self, temperature_sensor_name=None):
        """
        Returns the current temperature measured on the specified
        sensor(s).  NOTE: some temperatures are taken from the FPGA
        inetrnal SYSTEM monitor.

        initializes temperature expanders
        'temperature_sensor_name' can be a list of temperature sensor
        names found in TEMPERATURE_SENSOR_TABLE

        Returns a dictionary with keys corresponding to the temperature_sensor_name names.

        History:
        140318 JM: created
        """
        temperature_dict = {}
        if temperature_sensor_name == None:
            temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
        elif isinstance(temperature_sensor_name, str):
            temperature_sensor_name = [temperature_sensor_name]

        for temp_sensor in temperature_sensor_name:
            if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                raise IceBoardHardwareException('Invalid temperature sensor name')
            else:
                tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
                temperature_dict[temp_sensor]=tmp_object.get_temperature()

        return temperature_dict

    def get_power(self, power_sensor_name=None):
        """
        Returns the voltage, current and power of the power monitoring system.
        Includes power measured internally from  the FPGA's system monitor.
        Multiple targets can be specified.

        Arguments:

           'power_sensor_name' can be a list of temperature sensor
            names found in POWER_SENSOR_TABLE. If
            power_sensor_name=None, measurements of all sensors in
            TEMPERATURE_SENSOR_TABLE are returned.

        Returns dictionary with keys corresponding to the
        power_sensor_name names. The respective value is a (bus
        voltage (V), shunt voltage (V), current (A), power (W)) tuple.

        History:
        140320 JM: created
        """
        power_dict = {}
        if power_sensor_name == None:
            power_sensor_name = self.POWER_SENSOR_TABLE.keys()
        elif isinstance(power_sensor_name, str):
            power_sensor_name = [power_sensor_name]

        for power_sensor in power_sensor_name:
            if power_sensor not in self.POWER_SENSOR_TABLE:
                raise IceBoardHardwareException('Invalid power sensor name')
            else:
                power_sensor_list = self.POWER_SENSOR_TABLE[power_sensor]
                power_object = power_sensor_list[0]
                power_dict[power_sensor]=(power_object.get_bus_voltage(), power_object.get_shunt_voltage(), power_object.get_current(), power_object.get_power())

        return power_dict


    def get_serial_number(self):
        """
        Returns the board's serial number. which is actually the FPGA's
        serial number.
        """
        return self._fpga.get_serial_number(); # tentative code

    def get_info(self):
        """Loads the info data on the motherboard"""
        pass

    def status(self):
        """Displays the status of the motherboard"""

