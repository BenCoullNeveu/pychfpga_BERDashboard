#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
SCALER.py module 
 Implements interface to the SCALER

 History:
        2012-07-13 JFC: Created
"""
#import time
from Module import Module_base, BitField

class SCALER_base(Module_base):
    """ Implements interface to the SCALER module within a procecessor pipeline"""
    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # Define Control registers
    RESET = BitField(CONTROL, 0x00, 7, doc="Reset the SCALER.")
    BYPASS = BitField(CONTROL, 0x00, 6, doc="Bypass the SCALER")
    SHIFT_LEFT = BitField(CONTROL, 0x00, 0, width=4, doc="Number of bits to shift left the incoming data")

    # Define Status registers

    def __init__(self, ant_ch_instance):
         self.fpga = ant_ch_instance.fpga
         super(self.__class__, self).__init__(self.fpga, ant_ch_instance.ant_number, ant_ch_instance.SCALER_MODULE)
        
    def reset(self):
        """ Resets the SCALER module """
        self.pulse_bit('RESET')

    def init(self):
        """ Initialize the SCALER module"""
        # Bypass the scaler by default if the FFT is not present
        if (self.fpga.GPIO.IMPLEMENT_FFT & (1 << self.port_number)):
          self.BYPASS = 0
        else:
          self.BYPASS = 1
        #self.BYPASS = 1
        #self.SHIFT_LEFT = 10

    def status(self):
        """ Displays the status of the scaler module"""
        print '-------------- ANT[%i].SCALER STATUS --------------' % self.port_number 
        print ' SCALER Bypass: %s' % (bool(self.BYPASS))
        print ' Shift left: %i' % self.SHIFT_LEFT


