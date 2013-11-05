#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
FUNCGEN.py module 
 Implements interface to the internal function generator

History:
    2012-10-01 JFC : Created from SRCSEL.py
    2012-10-17 JFC: Sets ramp as default function
"""

import logging

from Module import Module_base, BitField
   
class FUNCGEN_base(Module_base):
    """ Implements interface to the function generator within a procecessor pipeline"""
    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    FUNCTION_NAMES = {
        'zero' : 0, # All bytes are zero
        'a' : 1, # All bytes are Byte A
        'b' : 2, # All bytes are Byte B
        'ab' : 3, # Bytes alternate between A and B. 
        'ramp' : 4, # Successive bytes generate a repeating ramp from 0 to 255. 
        'real_ramp' : 5, # Generates a complex ramp from 0+0i to 255+0i on each successive (8+8) bits complex values (the imaginary part is always zero). 
        }    
    
    # Memory-mapped register definition
    RESET    = BitField(CONTROL, 0x00, 7, doc='Resets this module')
    FUNCTION = BitField(CONTROL, 0x00, 0, width=3, doc="Selects the waveform to be generated")
    BYTE_A   = BitField(CONTROL, 0x01, 0, width=8, doc="Byte A to be used by the function generator")
    BYTE_B   = BitField(CONTROL, 0x02, 0, width=8, doc="Byte B to be used by the function generator")
    
    RAMP_CTR = BitField(STATUS, 0x01, 0, width=8, doc="Last 8 bits of the ramp counter (for debuging)")


    def __init__(self, ant_ch_instance, port, module):
        self.ant = ant_ch_instance
        fpga = ant_ch_instance.fpga
        super(self.__class__, self).__init__(fpga, port, module)

        self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)
    # Specialized functions

    def reset(self):
        """ Resets the function generator"""
        self.pulse_bit('RESET')

    def set_function(self, function_name, a=None, b=None):
        """
        Sets the function to be generated  by the the function generator.
        The bytes 'a' and 'b' can optionnally be specified, otherwise their current value is used. 
        """
        if function_name not in self.FUNCTION_NAMES:
            raise Exception('Invalid function name')
        else:
            if a is not None:
                self.BYTE_A = a
            if b is not None:
                self.BYTE_B = b
            self.FUNCTION = self.FUNCTION_NAMES[function_name]

    def init(self):
        """ Initializes the function generator """
        self.set_function('ramp')
        pass
    
    def status(self):
        """ Displays the status of the function generator module """
        print '-------------- ANT[%i].FUNCGEN STATUS --------------' % self.port_number 
        print ' Function number: %i' % self.FUNCTION
        print ' Ramp counter status:'
        print '    RAMP_CTR: %i' % self.RAMP_CTR
 

