#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
INJECT.py module 
 Implements interface to the antenna data injector module
#
# History:
# 2012-10-01 JFC : Created from SRCSEL.py
"""

import numpy as np
from Module import Module_base, BitField


    
class INJECT_base(Module_base):
    """ Implements interface to the data injector module within a procecessor pipeline"""
    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    
    # Memory-mapped register definition
    RESET = BitField(CONTROL, 0x00, 7, doc='Resets this module')

    RST = BitField(STATUS, 0x00, 7, doc="debug")
    SOFT_RESET = BitField(STATUS, 0x00, 5, doc="debug")
    ANT_RESET = BitField(STATUS, 0x00, 4, doc="debug")
    FIFO_EMPTY = BitField(STATUS, 0x00, 1, doc="Active high  when the data FIFO is empty")
    FIFO_OVERFLOW = BitField(STATUS, 0x00, 0, doc="Active high if the data FIFO is overflowing")
    FIFO_LENGTH = BitField(STATUS, 0x01, 0, width=8, doc="Number of samples currently in the data FIFO (last 8 bits only)")


    def __init__(self, ant_ch_instance, port, module):
        self.ant = ant_ch_instance
        fpga = ant_ch_instance.fpga
        super(self.__class__, self).__init__(fpga, port, module)
        self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)
    # Specialized functions

    def reset(self):
        """Resets the data injection FIFO."""
        self.pulse_bit('RESET')


    def inject_frame(self, data=None, length=None):
        """ Inject a frame of data in the antenna processing pipeline"""

        #self.DSP_DATA_SRC = 1 # Data source = Data Injection FIFO
        #self.pulse_bit('FIFO_RESET') # clear FIFO to make sure we do not sent data that was previously lingering in the FIFO

        if data == None: # Send ramp
            if length == None:
                length = self.ant.frame_length
            frame = [(i % 256) for i in range(length)] #(i % 256)
        else:
            if length == None:
                length = self.ant.frame_length #len(data)
            
            if type(data) == str :
                data_length = len(data)
                frame = [ord(data[i % data_length]) for i in range(length)]
                #print 'Sending string:',s
            elif isinstance(data, np.ndarray) or isinstance(data, list):
                data_length = len(data)
                data = np.uint8(data)
                frame = [data[i % data_length] for i in range(length)]
                #print 'Sending string:',s
            elif type(data) == int:
                frame = [data]*length
            else:
                print 'Data should be an integer, a list, or numpy array'
                
        self.write_ram(0x00, frame, incr=0) # Write to FIFO


    def init(self):
        """ Initializes the data injector"""
        pass
    
    def status(self):
        """ Displays the status of the data injector module """
        print '-------------- ANT[%i].INJECT STATUS --------------' % self.port_number 
        print ' Reset states:'
        print '    RST: %s' % bool(self.RST)
        print '    ANT_RESET: %s' % bool(self.ANT_RESET)
        print ' Inject FIFO status:'
        print '    EMPTY: %s' % bool(self.FIFO_EMPTY)
        print '    OVERFLOW: %s' % bool(self.FIFO_OVERFLOW)
        print '    LENGTH: %i' % self.FIFO_LENGTH
 

