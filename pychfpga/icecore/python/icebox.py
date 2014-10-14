#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: C0301

"""iceboard_hardware.py module: Provides a class to access the hardware of IceBoard
(McGill Model MGK7MB).
"""

import logging

# Import IceBoard hardware handlers
from lib.fmc_eeprom import FMC_EEPROM
from lib import ina230 # I2C Voltage and current monitor
from lib import tmp421 # I2C temperature sensor
from lib import pca9698 # I2C 40-bit IO Expander

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

    _QSFP_CTRL_SETA_ADDR = 0b0100000
    _QSFP_CTRL_SETB_ADDR = 0b0100010
    _RESETS_CTRL_ADDR = 0b0100100

    _TMP_SLOT1_ADDR = 0x4E
    _TMP_SLOT16_ADDR = 0x4D

    _POWER_3V3_ADDR = 0x40

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

        self._logger.info(' Instantiating Backplane I2C temperature sensors')
        self._tmp_slot1 = tmp421.tmp421(self._i2c, self._TMP_SLOT1_ADDR, 'BP')
        self._tmp_slot16 = tmp421.tmp421(self._i2c, self._TMP_SLOT16_ADDR, 'BP')

        self._logger.info(' Instantiating Backplane I2C current/power monitor')
        self._power_3v3 = ina230.ina230(self._i2c, self._POWER_3V3_ADDR, 'BP')

        self._logger.info(' Instantiating Backplane I2C I/O expanders')
        self._QSFP_CTRLA = pca9698.pca9698(self._i2c, self._QSFP_CTRL_SETA_ADDR, 'BP')
        self._QSFP_CTRLB = pca9698.pca9698(self._i2c, self._QSFP_CTRL_SETB_ADDR, 'BP')
        self._RESET_CTRL = pca9698.pca9698(self._i2c, self._RESETS_CTRL_ADDR, 'BP')

        self.QSFP_CTRL_MAP = {
             # Slot num : (expander object, Register, bit number ModPrs, bit number Reset, bit number IntL, bit number ModSel)
             1: (self._QSFP_CTRLA, 2,    0,1,2,3 ),
             2: (self._QSFP_CTRLA, 2,    4,5,6,7 ),
             3: (self._QSFP_CTRLA, 1,    0,1,2,3 ),
             4: (self._QSFP_CTRLA, 1,    4,5,6,7 ),
             5: (self._QSFP_CTRLA, 0,    0,1,2,3 ),
             6: (self._QSFP_CTRLA, 0,    4,5,6,7 ),
             7: (self._QSFP_CTRLA, 3,    0,1,2,3 ),
             8: (self._QSFP_CTRLA, 3,    4,5,6,7 ),

             9: (self._QSFP_CTRLB, 2,    0,1,2,3 ),
             10: (self._QSFP_CTRLB, 2,   4,5,6,7 ),
             11: (self._QSFP_CTRLB, 1,   0,1,2,3 ),
             12: (self._QSFP_CTRLB, 1,   4,5,6,7 ),
             13: (self._QSFP_CTRLB, 0,   0,1,2,3 ),
             14: (self._QSFP_CTRLB, 0,   4,5,6,7 ),
             15: (self._QSFP_CTRLB, 3,   0,1,2,3 ),
             16: (self._QSFP_CTRLB, 3,   4,5,6,7 )
        }

        self.SLOT_RESETS_MAP = {
            # Slot num : (expander object, ARM Register, Power Down Register, Bit number)
            1: (self._RESET_CTRL, 1, 2, 0),
            2: (self._RESET_CTRL, 1, 2, 1),
            3: (self._RESET_CTRL, 1, 2, 2),
            4: (self._RESET_CTRL, 1, 2, 3),
            5: (self._RESET_CTRL, 1, 2, 4),
            6: (self._RESET_CTRL, 1, 2, 5),
            7: (self._RESET_CTRL, 1, 2, 6),
            8: (self._RESET_CTRL, 1, 2, 7),
            9: (self._RESET_CTRL,  3, 4, 0),
            10: (self._RESET_CTRL, 3, 4, 1),
            11: (self._RESET_CTRL, 3, 4, 2),
            12: (self._RESET_CTRL, 3, 4, 3),
            13: (self._RESET_CTRL, 3, 4, 4),
            14: (self._RESET_CTRL, 3, 4, 5),
            15: (self._RESET_CTRL, 3, 4, 6),
            16: (self._RESET_CTRL, 3, 4, 7)
        }

        self.FULLBP_RESETS_MAP = {
             # ResetType : (expander object, Register, mask, inactive, active)
             'ARM':       (self._RESET_CTRL, 0, 0b01000011, 0b00000001, 0b01000010),
             'POWER':     (self._RESET_CTRL, 0, 0b01001100, 0b00000100, 0b01001000),
             'LED':       (self._RESET_CTRL, 0, 0b10000000, 0b10000000, 0b00000000),

        }


        self.TEMPERATURE_SENSOR_TABLE = {
             # sensor name: tmp object
             'TEMP_SLOT1': self._tmp_slot1,
             'TEMP_SLOT16': self._tmp_slot16,
         }

        self.POWER_SENSOR_TABLE = {
             # sensor name : (ina230 object, output voltage(volts), rshunt(inductor) (mohm), typical current(amps), current tolerance (0<tol<1))
             'BP_3V3': (self._power_3v3, 3.3, 2.6, 2., 0.5),
        }

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

        self._init_QSFP_CTRL()


    def _init_QSFP_CTRL(self):
        """
        Initializes QSFP control IO expanders

        History
        141014 created:
        """




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

    def _init_temperature_sensors(self, temperature_sensor_name=None):
        """
        initializes temperature sensors
        'temperature_sensor_name' can be a list of temperature sensor names found in TEMPERATURE_SENSOR_TABLE.

        History:
        140318 JM: created
        """
        if temperature_sensor_name == None:
            temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
        elif isinstance(temperature_sensor_name, str):
            temperature_sensor_name = [temperature_sensor_name]

        for temp_sensor in temperature_sensor_name:
            if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                raise IceBoardHardwareException('Invalid temperature sensor name')
            else:
                tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
                tmp_object.init()

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
        return self.get_eeprom_serial_number(); # tentative code

    def get_info(self):
        """Loads the info data on the motherboard"""
        pass

    def status(self):
        """Displays the status of the motherboard"""

