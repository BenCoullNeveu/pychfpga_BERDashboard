#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301

"""
MGK7MB.py module
 Wrapper object to provide addess to the  McGill MGK7MB ICEBoard Hardware ressources

 History:
 2013-08-08 : JFC : Created
 2014-03-04 JM: modified set_led(), init() and set_fmc_power(), added get_led() for MGK7MB
"""
# MGADC08 FMC ADC board device handlers
import logging

import tca9548a
import pca9575
import tmp100

from common import util
from icearray import iceboard

util.reload_modules([iceboard])



class I2CWrapper(object):
    """
    Implements the I2C interface on the MGK7MB motherboard through the FPGA.
    I2C buses are selected by name (FMC0, FMC1, SMBUS etc.). This module takes care of selecting the proper I2C port and set the I2C switch to reach that bus.
    """

    I2C_SWITCH_ADDR = 0b1110100
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
        self.i2c_switch = tca9548a.tca9548a(self.fpga_i2c, self.I2C_SWITCH_ADDR)
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


class MGK7MB(iceboard.IceBoard):
    """
    Implements the interfaces to the IceBoard functionnalities in Python through the specified I2C interface (ARM or FPGA).
    """

    def __init__(self, i2c_interface, verbose=0):
        super().__init__(i2c_interface = i2c_interface, verbose= verbose)
