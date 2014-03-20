#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
iceboard.py module 
Provides access to the basic functionnalities of an ICEBoard (Model MGK7MB)

 History:
        2014-03-04 JFC: Created
        2014-03-18 JM: Added get_temperature and init_temp_sensors
"""
#import time
import logging
#import struct
import numpy as np

import fpga
#import core.Module
# import core.GPIO

# import hardware handlers
import tmp100
import pca9575
import tca9548a
# from Module import Module_base, BitField

class IceBoard(fpga.Fpga):
    """
    Provides access to the basic functionnalitied of an IceBoard.
    Virtual class representing the IceBoard Rev2.
    The methods and properties have access to the hardware or firmware in one of the the following way:
        - The low-level hardware access is made directly in python through the ARM or FPGA I2C links to the board.
        - The low-level hardware access is implemented in the ARM< software, and all methods and properties are imported through tuber.


    Project-specific classes are meant to be derived from this class.
    """
    class IceBoardException(Exception):
        pass

    # def __init__(self, interface, arm_firmware=None, fpga_firmware = None):

        # """
        # Notes:
        #     'arm_if' used for i2c. and arm-specific fw support. 
        #     if arm_if: i2c_if = arm_if.i2c else: if fpga_if: i2c_if = fpga_if else raise IceBoardException('message')

        #     'interface' provides a object through which the ARM and FPGA firmare is accessed. 
        # """

        # arm = ARM(interface)
        # fpga = FPGA(interface)

        # self.arm_fw = arm_firmware
        # self.fpga_fw = fpga_firmware
        # if arm_firmware:
        #     i2c_interface = arm_firmware.i2c
        # elif fpga_firmware:
        #     i2c_interface = fpga_firmware.i2c

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


    class I2cInterface(object):
        def __init__(self, write_read_fn, port_select_fn, bus_table, switch_addr, verbose = None):
            self.write_read_fn = write_read_fn
            self.set_port_fn = port_select_fn
            self.I2C_BUS_LIST = bus_table

            self.i2c_switch = tca9548a.tca9548a(self, switch_addr)
            self.logger = logging.getLogger(__name__)

        def select_bus(self, bus_names):
            """
            Configure the I2C port and I2C switch so the folloging communications will access the desired I2C bus.
            'bus_id' can be a bus name or bus number, or a list of those if multiple buses are to be accessed at the same time.
            An error will be provided if all the buses are not accessible through the same FPGA I2C port.
            This function assumes that each FPGA I2C port has an identical I2C switch.
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
            Writes up to 3 bytes to the addressed I2C device and/or reads up to 4 bytes from that device after a restart.
            See the FPGA I2C module for detailed method description.
            """
            self.logger.debug("Accessing I2C bus...")
            return self.write_read_fn(*args, **kwargs)

    def __init__(self, arm, fpga, verbose=2):
        
        # self.sys = system_instance
        self.arm = arm
        self.fpga = fpga
        self.logger = logging.getLogger(__name__)


        self.logger.debug('Initializing Iceboard object with ARM=%s, FPGA=%s' % (arm, fpga))
        # Defines a standardized I2C interface object to be used to communicate with the board's hardware.
        # The functions underlying this interface varies depending on whether the ARM or FPGA is used to talk to the board:
        #   - With the FPGA we need to know the FPGA port associated with each I2C bus.
        #   - The I2C switch address is different for the ARM compared to the FPGA
        if verbose >= 2: self.logger.info(' Instantiating motherboard I2C manager')
        if fpga:
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
            self.i2c = self.I2cInterface(fpga.i2c_write_read, fpga.i2c_set_port, i2c_bus_list, self.FPGA_I2C_SWITCH_ADDR)


        if verbose >= 2: self.logger.info(' Instantiating I2C GPIO manager')
        self.gpio_power = pca9575.pca9575(self.i2c, self.GPIO_POWER_I2C_ADDR, 'GPIO')
        self.gpio_sw_leds = pca9575.pca9575(self.i2c, self.GPIO_SW_LEDS_ADDR, 'GPIO')
        self.gpio_arm_phy_leds = pca9575.pca9575(self.i2c, self.GPIO_ARM_PHY_LEDS_ADDR, 'GPIO')
        self.gpio_sfp_qsfp = pca9575.pca9575(self.i2c, self.GPIO_SFP_QSFP_I2C_ADDR, 'GPIO')

        if verbose >= 2: self.logger.info(' Instantiating I2C temperature sensors')
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



    def init(self):
        """ Initializes the motherboard hardware"""
        self.init_gpio_expanders()
        self.init_temp_sensors()
        self.init_eeprom()
        self.set_fmc_power()

    def close(self):
        pass

    def init_gpio_expanders(self):
        """
        initializes GPIO expanders
        
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


    # The following table defines the LEDS found on the board

    def set_led(self, led_name, state):
        """
        Set the LED(s) specified in 'led_name' to the the 'state'.
        'led_name' can be a list of LED names found in GPIO_EXPANDER_MAP.
        'state' can be a single boolean value, or an array with the same length as 'led_name'
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
        Returns the status of specified LED(s) in a dictionary led_status where each key is a led_name and the respective value is the led status.
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
        Returns the current temperature measured on the specified sensor(s).
        NOTE: some temperatures are taken from the FPGA inetrnal SYSTEM monitor.

        initializes temperature expanders
        'temperature_sensor_name' can be a list of temperature sensor names found in TEMPERATURE_SENSOR_TABLE
        
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

    
    POWER_SENSOR_TABLE = {
        # name : (i2c address, calibration)
        }
    def get_power(self, target):
        """
        Returns the voltage and current of the power monitoring system.
        Includes power measured internally from  the FPGA's system monitor.
        Multiple targets can be specified.
        The power is returned as a (voltage, current) tuple.
        """
    def get_serial_number(self):
        """
        Returns the board's serial number. which is actually the FPGA's serial number.
        """
        self.fpga.get_serial_number(); # tentative code

    def get_info(self):
        """ loads the info data on the motherboard """
        pass

    def status(self):
        """ Displays the status of the motherboard"""
        # print '======= MGADC FMC ADC BOARD  ============='
        # print 'FMC board is present:', self.is_present()
        # if self.is_present():
        #     self.FMC_EEPROM.status()
        #     self.AmbTemp.status()
        #     self.IOExpander.status()
        #     self.ADC_PLL.status()
        #     self.ADC.status()
        # else:
        #     print ' *** Board is not present'
        pass

