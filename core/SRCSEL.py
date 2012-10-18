#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
SRCSEL.py module 
 Implements interface to the antenna Source Selector module
#
# History:
    2011-07-12 JFC : Created from test code in chFPGA.py
    2012-05-29 JFC: Extracted from ANT.py
    2012-08-28 JFC: Moved SYNC_PERIOD to the FFT block
    2012-10-01 JFC: Moved INJECT and FUNCGEN out of here
    2012-10-17 JFC: Fixed default source setting when there is no FMC
"""

from Module import Module_base, BitField
    
class SRCSEL_base(Module_base):
    """ Implements interface to the FR_DIST within a procecessor pipeline"""
    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    DATA_SOURCE_NAMES = {
        'adc' : 0, # Data comes from the ADC
        'funcgen' : 1, # Data comes from the function generator
        'inject' : 2, # Data is injected by the user  
        }    
    
    # Memory-mapped register definition
    RESET = BitField(CONTROL, 0x00, 7, doc='Resets this module')
    CAPTURE_FLAG = BitField(CONTROL, 0x00, 5, doc="When '1', forces the CAPURE flag of the outgoing frames to be '1'. Could be used downstream.")
    DATA_SOURCE = BitField(CONTROL, 0x00, 0, width=3, doc="Selects the Antenna processing block data source")

    RST = BitField(STATUS, 0x00, 7, doc="debug")
    SOFT_RESET = BitField(STATUS, 0x00, 5, doc="debug")
    ANT_RESET = BitField(STATUS, 0x00, 4, doc="debug")
    WORD_CTR = BitField(STATUS, 0x01, 0, width=8, doc="Number of samples samples sent into the antenna processing pipeline (last 8 bits only)")
    FRAME_CTR = BitField(STATUS, 2, 0, width=8, doc="Number of frames sent into the antenna processing pipeline (last 8 bits only)")


    def __init__(self, ant_ch_instance):
        self.ant = ant_ch_instance
        fpga = ant_ch_instance.fpga
        super(self.__class__, self).__init__(fpga, fpga.ANT_PORT[ant_ch_instance.ant_number], ant_ch_instance.SRCSEL_MODULE)
        self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)
    # Specialized functions

    def reset(self):
        """ Resets the Source selector module"""
        self.pulse_bit('RESET')

    def set_data_source(self, source_name):
        """
        Sets the data source to be selected by the the SOURCE selector.
        """
        if source_name not in self.DATA_SOURCE_NAMES:
            raise Exception('Invalid data source name')
        else:
            self.DATA_SOURCE = self.DATA_SOURCE_NAMES[source_name]
        

    def init(self):
        """ Initializes the antenna processing chain data source module """
        # Do nothing if the FMC is not present
        if not self.fpga.FMC_present:
            self.set_data_source('funcgen') # use the dunction generator if the ADC is not present
        else:
            self.set_data_source('adc') # use the ADC data

    def status(self):
        """ Displays the status of the antenna processing chain data source module """
        print '-------------- ANT[%i].SRCSEL STATUS --------------' % self.port_number 
        print ' Data source number: %i' % self.DATA_SOURCE
        print ' Reset states:'
        print '    RST: %s' % bool(self.RST)
        print '    SOFT_RESET: %s' % bool(self.SOFT_RESET)
        print '    ANT_RESET: %s' % bool(self.ANT_RESET)
        print ' Counter status:'
        print '    WORD_CTR: %i' % self.WORD_CTR
        print '    FRAME_CTR: %i' % self.FRAME_CTR
