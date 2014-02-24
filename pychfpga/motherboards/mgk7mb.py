#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
MGK7MB.py module
 Wrapper object to provide addess to the  McGill MGK7MB ICEBoard Hardware ressources

 History:
 2013-08-08 : JFC : Created
"""
# MGADC08 FMC ADC board device handlers
import logging

import pca9575
from common import util

util.reload_modules([])

class tca9548a(object):
    """
    Implements the interface to the TCA9548A I2C switch.
    """

    def __init__(self, i2c_interface, address, verbose=0):
        self.i2c = i2c_interface
        self.switch_address = address

    def set_port(self, ports=None, bitmask = None):
        """ 
        Activates selected I2C ports of the switch and disable the others.
        The ports can be either specified as a single port number (e.g. ports=1), a list of ports (e.g. ports=[1,2,3]) or a bitmask (bit_mask = 0x83)
        """
        bit_pattern = 0

        if (ports is not None) and (bitmask is None):
            if isinstance(ports, int):
                ports = [ports]
            for port in ports:
               bit_pattern |= (1 << port) 
        elif (ports is None) and (bitmask is not None):
            bit_pattern = bitmask
        else:
            raise chFPGAException('Must provide either port number(s) or a bit mask')

        self.i2c.write_read(self.switch_address, data=[bit_pattern])

I2C_SWITCH_ADDR = 0b1110100

class I2CWrapper(object):
    """
    Implements the I2C interface on the MGK7MB motherboard.
    I2C buses are selected by name (FMC0, FMC1, SMBUS etc.). This module takes care of selecting the proper I2C port and set the I2C switch to reach that bus.
    """

    I2C_BUS_LIST = {
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

    def __init__(self, i2c_handler, verbose = None):
        self.fpga_i2c = i2c_handler
        self.i2c_switch = tca9548a(self.fpga_i2c, I2C_SWITCH_ADDR)
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


        self.fpga_i2c.set_port(selected_fpga_port_number)

        self.i2c_switch.set_port(selected_switch_port_numbers)

    def write_read(self, *args, **kwargs):
        """
        Writes up to 3 bytes to the addressed I2C device and/or reads up to 4 bytes from that device after a restart.
        See the FPGA I2C module for detailed method description.
        """
        self.logger.debug("Accessing I2C bus...")
        return self.fpga_i2c.write_read(*args, **kwargs)

class ddr3_eeprom(object):
    """
    Provides access to the ML605 DDR3 memory embedded EEPROM.
    """

    def read_DDR3_reg(self, addr):
        """ Reads from the EEPROM"""
        i2c = self.fpga_instance.I2C
        i2c_addr = 0x1b

        i2c.select_buses('DDR3')
        i2c.write_read(i2c_addr, [addr]) # sets the address
        data = i2c.write_read(i2c_addr, length=2) # reads a word
        return data

class IceBoard(object):
    """
    Virtual class representing the IceBoard Rev2.
    The methods and properties are actually implemented by derived classes in the following way:
        - The low-level hardware access is made directly in python through the ARM or FPGA I2C links to the board.
        - The low-level hardware access is implemented in the ARM< software, and all methods and properties are imported through tuber.
    """
    class IceBoardException(Exception):
        pass

    def __init__(self, interface, arm_firmware=None, fpga_firmware = None):

        """
        Notes:
            'arm_if' used for i2c. and arm-specific fw support. 
            if arm_if: i2c_if = arm_if.i2c else: if fpga_if: i2c_if = fpga_if else raise IceBoardException('message')

            'interface' provides a object through which the ARM and FPGA firmare is accessed. 
        """

        # arm = ARM(interface)
        # fpga = FPGA(interface)

        # self.arm_fw = arm_firmware
        # self.fpga_fw = fpga_firmware
        # if arm_firmware:
        #     i2c_interface = arm_firmware.i2c
        # elif fpga_firmware:
        #     i2c_interface = fpga_firmware.i2c


class MGK7MB(IceBoard):
    """
    Implements the interfaces to the IceBoard functionnalities in Python through the specified I2C interface (ARM or FPGA).
    """

    NUMBER_OF_FMC_SLOTS = 2 # Indicates the number of FMC slots supported by this platform


    GPIO_POWER_I2C_ADDR = 0b0100000
    GPIO_SFP_QSFP_I2C_ADDR = 0b0100001
    GPIO_SW_LEDS_ADDR = 0b0100010
    GPIO_ARM_PHY_LEDS_ADDR = 0b0100011

    def __init__(self, i2c_interface, verbose=0):
        
        # self.sys = system_instance
        self.logger = logging.getLogger(__name__)
        self.i2c = i2c_interface

        if verbose >= 2: self.logger.info(' Instantiating motherboard I2C manager')
        self.i2c = I2CWrapper(self.i2c)

        if verbose >= 2: self.logger.info(' Instantiating I2C GPIO manager')
        self.gpio_power = pca9575.pca9575(self.i2c, self.GPIO_POWER_I2C_ADDR, 'GPIO')
        self.ioexpander_sw_leds = pca9575.pca9575(self.i2c, self.GPIO_SW_LEDS_ADDR, 'GPIO')

        self.LED_TABLE = {
            # name : (I2C address, byte, bit number (width))
            'LED1': (self.ioexpander_sw_leds, 1, 7), 
            'LED2': (self.ioexpander_sw_leds, 1, 6), 
            'LED3': (self.ioexpander_sw_leds, 1, 5), 
            'LED4': (self.ioexpander_sw_leds, 1, 4), 
            'LED5': (self.ioexpander_sw_leds, 1, 3), 
            'LED6': (self.ioexpander_sw_leds, 1, 2), 
            'LED7': (self.ioexpander_sw_leds, 1, 1), 
            'LED8': (self.ioexpander_sw_leds, 1, 0), 
            'LED9': (GPIO_ARM_PHY_LEDS_ADDR, 0, 0), 
            'LED10': (GPIO_ARM_PHY_LEDS_ADDR, 0, 1), 
            'LED11': (GPIO_ARM_PHY_LEDS_ADDR, 0, 2), 
            'LED12': (GPIO_ARM_PHY_LEDS_ADDR, 0, 3)
            }


    def init(self):
        """ Initializes the motherboard hardware"""
        self.set_fmc_power(True)

    def get_number_of_fmc_slots(self):
        return self.NUMBER_OF_FMC_SLOTS

    def set_fmc_power(self, fmc_number, state):
        """
        Enables or disables power of the specified FMC slot.
        'state' is converted to a boolean value so 0/1 can be used as well as False/True.
        Proper power sequencing is done to prevent the FMC board switchers to create too much a current spike when enabled.

        History:
            140223 JFC: Modified to use register names.
        Todo:
            140223 JFC: used masked writes to avoid side effects.
        """
        if isinstance(fmc_number, int):
            fmc_number = [fmc_number]

        for fmc in fmc_number:
            if fmc not in range(self.NUMBER_OF_FMC_SLOTS):
                raise self.IceBoardException('FMC number %i is not a valid value' % fmc)
            else:
                out_reg = 'OUT%i' % fmc # sets the register name to access based on the FMC number
                cfg_reg = 'CFG%i' % fmc
                self.gpio_power.write(out_reg, 0b00000000) # Turn off all power signals before we enable the GPIO outputs
                self.gpio_power.write(cfg_reg, 0b10101000)
                self.gpio_power.write(out_reg, 0b00000111*bool(state)) # Turn on power to board
                self.gpio_power.write(out_reg, 0b01010111*bool(state)) # Set Power Good and CLKDIR to 1


    # The following table defines the LEDS found on the board

    def set_led(self, led_name, state):
        """
        Set the LED(s) specified in 'led_name' to the the 'state'.
        'led_name' can be a list of LED names found in LED_TABLE.
        'state' can be a single boolean value, or an array with the same length as 'led_name'
        """
        if isinstance(led_name, str):
            led_name = [ led_name]

        for led in led_led_name:
            if led not in self.LED_TABLE:
                raise IceBoardException('Invalid LED name')
            led_info = self.LED_TABLE[led]
            io_expander = led_info[0]
            led_byte = led_info[1]
            led_bit = led_info[2]

            io_expander.write('OUT%i' % led_byte, (1<<led_bit) * bool(state) , mask = 1<<led_bit)

        pass # code not implemented
    def get_led(self, led_name):
        """
        Returns the status of specified LED(s).
        """

    TEMP_SENSOR_TABLE = {}
    def get_temperature(self, temperature_sensor_name):
        """
        Returns the current temperature measured on the specified sensor(s).
        NOTE: some temperatures are taken from the FPGA inetrnal SYSTEM monitor.
        """
        pass # Not implemented yet

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
        self.fpga .get_serial_number(); # tentative code

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