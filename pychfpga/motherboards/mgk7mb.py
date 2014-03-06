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
from pychfpga.common import util

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

class pca9575(object):
    """
    Implements the interface to the I2C IO Extender.
    """

    def __init__(self, i2c_interface, address, verbose=0):
        self.i2c = i2c_interface
        self.address = address

    def write(self, register, value):
        """ 
        Writes a value to the specified register
        """
        self.i2c.select_bus('GPIO')
        self.i2c.write_read(self.address, data=[register, value])

    def read(self, register):
        """ 
        Read a value to the specified register
        """
        self.i2c.select_bus('GPIO')
        return self.i2c.write_read(self.address, data=[register], read_length=1)

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

    def read_DDR3_reg(self, addr):
        """ Reads from the EEPROM"""
        i2c = self.fpga_instance.I2C
        i2c_addr = 0x1b

        i2c.select_buses('DDR3')
        i2c.write_read(i2c_addr, [addr]) # sets the address
        data = i2c.write_read(i2c_addr, length=2) # reads a word
        return data


class MGK7MB(object):
    """ Implements wrapper object for MGADC08 FMC ADC board"""

    NUMBER_OF_FMC_SLOTS = 2 # Indicates the number of FMC slots supported by this platform
    GPIO_POWER_I2C_ADDR = 0b0100000
    GPIO_SFP_QSFP_I2C_ADDR = 0b0100001
    GPIO_SW_LEDS_ADDR = 0b0100010
    GPIO_ARM_PHY_LEDS_ADDR = 0b0100011

    def __init__(self, system_instance, verbose=0):
        self.sys = system_instance
        self.logger = logging.getLogger(__name__)

        if verbose >= 2: self.logger.info(' Instantiating motherboard I2C manager')
        self.i2c = I2CWrapper(self.sys.fpga_I2C)

        if verbose >= 2: self.logger.info(' Instantiating I2C GPIO manager')
        self.gpio_power = pca9575(self.i2c, self.GPIO_POWER_I2C_ADDR)



    def init(self):
        """ Initializes the motherboard hardware"""
        self.set_fmc_power(True)

    def get_number_of_fmc_slots(self):
        return self.NUMBER_OF_FMC_SLOTS

    def set_fmc_power(self, fmc_number, state):
        """
        Enables or disables power of the specified FMC slot.
        'state' is converted to a boolean value so 0/1 can be used as well as False/True.
        """

        if fmc_number == 0:
            self.gpio_power.write(0x0A, 0b00000000) # Turn off all power signals before we enable the GPIO outputs
            self.gpio_power.write(0x08, 0b10101000)
            self.gpio_power.write(0x0A, 0b00000111*bool(state)) # Turn on power to board
            self.gpio_power.write(0x0A, 0b01010111*bool(state)) # Set Power Good and CLKDIR to 1
        elif fmc_number == 1:
            self.gpio_power.write(0x0B, 0b00000000) # Turn off all power signals before we enable the GPIO outputs
            self.gpio_power.write(0x09, 0b10101000)
            self.gpio_power.write(0x0B, 0b00000111*bool(state))
            self.gpio_power.write(0x0B, 0b01010111*bool(state))
        else:
            raise self.sys.chFPGAException('FMC number %i is not a valid value' % fmc_number)

    LED_TABLE = {
        'LED1': (GPIO_SW_LEDS_ADDR, 1, 7), 
        'LED2': (GPIO_SW_LEDS_ADDR, 1, 6), 
        'LED3': (GPIO_SW_LEDS_ADDR, 1, 5), 
        'LED4': (GPIO_SW_LEDS_ADDR, 1, 4), 
        'LED5': (GPIO_SW_LEDS_ADDR, 1, 3), 
        'LED6': (GPIO_SW_LEDS_ADDR, 1, 2), 
        'LED7': (GPIO_SW_LEDS_ADDR, 1, 1), 
        'LED8': (GPIO_SW_LEDS_ADDR, 1, 0), 
        'LED9': (GPIO_ARM_PHY_LEDS_ADDR, 0, 0), 
        'LED10': (GPIO_ARM_PHY_LEDS_ADDR, 0, 1), 
        'LED11': (GPIO_ARM_PHY_LEDS_ADDR, 0, 2), 
        'LED12': (GPIO_ARM_PHY_LEDS_ADDR, 0, 3)
        }

    def set_led(self, led_name, state):
        old_value = 0


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
