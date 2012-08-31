#!/usr/bin/python

"""
FFT.py module 
 Implements interface to the FFT or PFB
#
# History:
# 2011-07-12 : JFC : Created from test code in chFPGA.py
# 2012-05-29 JFC: Extracted frm ANT.py
"""
#import time
#import numpy as np
from Module import Module_base, BitField
   

class FFT_base(Module_base):
    """ Implements interface to the FR_DIST within a procecessor pipeline"""
    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    # Define Control registers
    BYPASS =     BitField(CONTROL,0x00,0, doc="Bypass the FFT")
    DLY_RESET =     BitField(CONTROL,0x00,1, doc="Reset the computation of the CASPER block pipelining delay. When released, the block will re-learn the block latency once a CASPER SYNC has passed through the block.")
    FFT_SHIFT = BitField(CONTROL,0x02,0,10, doc="FFT shift enable bit for each of the FFT stage")
    SYNC_PERIOD = BitField(CONTROL, 0x04, 0, width=16, doc="Number of clock cycles between SYNC pulses. See CASPER documentation for minimum SYNC spacing.")
    PIPELINE_DELAY = BitField(STATUS,0x06, 0, width=16, doc="Latency (in number of clocks) of the CASPER PFB/FFT")
     
    # Define Status registers
    MEASURED_PIPELINE_DELAY = BitField(STATUS,0x01, 0, width=16, doc="Latency (in numbe rof clocks) of the CASPER PFB/FFT")
    OVERFLOW_COUNT = BitField(STATUS,0x02, 0, width=8, doc="Number of FFT overflows since reset (rolls back)")

    def __init__(self,ant_ch_instance):
        super(self.__class__,self).__init__(ant_ch_instance.fpga,ant_ch_instance.ant_number, ant_ch_instance.FFT_MODULE)
        
    def reset(self):
        self.pulse_bit('RESET')

    def init(self):
        """ Initialize the FFT module"""
        self.BYPASS=1

    def status(self):
        """ Displays the status of the data capture module"""
        print '-------------- ANT[%i].FFT STATUS --------------' % self.port_number 
        print ' FFT Bypass: %s' % (bool(self.BYPASS))
#        print ' FFT SHIFT schedule: 0x%X' % (self.FFT_SHIFT)
#        print ' CASPER block pipeling delay: %i clocks' % (self.PIPELINE_DELAY)
#        print ' Number of FFT overflows: %i' % (self.OVERFLOW_COUNT)


