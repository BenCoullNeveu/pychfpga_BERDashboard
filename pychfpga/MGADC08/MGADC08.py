#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
MGADC08.py module 
 Wrapper object for MGADC08 FMC ADC board 

 History:
 2011-07-25 : JFC : Created 
"""
# MGADC08 FMC ADC board device handlers
import ADC
import IOExpander
import ADC_PLL
import AmbTemp
import BiasADC
import MGT_PLL
import FMC_EEPROM

MODULE_LIST = (
        AmbTemp,
        ADC,
        IOExpander,
        ADC_PLL,
        BiasADC,
        MGT_PLL,
        FMC_EEPROM,
        )

def reload_modules(module_list=MODULE_LIST):
    """ Reload modules specified in the list."""
    for module in module_list: 
        print 'Reloading module %s' % (module.__name__)
        reload(module)


class MGADC08_base(object):
    """ Implements wrapper object for MGADC08 FMC ADC board"""

    def __init__(self, fpga_instance, verbose=0):
        self.fpga = fpga_instance
        self._board_is_present = False # Will be checked later
        self.sampling_frequency = None
        self.reference_frequency = None
        self._board_info = {}
        
        if verbose >= 2: print '  - FMC EEPROM'
        self.FMC_EEPROM = FMC_EEPROM.FMC_EEPROM_base(self.fpga)
        self.FMC_EEPROM.init()

        self.check_FMC_presence()

        if self.is_present():
            self.load_board_info()
            if verbose >= 2: print '  - ADC'
            self.ADC = ADC.ADC_base(self.fpga)
            if verbose >= 2: print '  - IOExpander'
            self.IOExpander = IOExpander.IOExpander_base(self.fpga)
            if verbose >= 2: print '  - ADC_PLL'
            self.ADC_PLL = ADC_PLL.ADC_PLL_base(self.fpga)
            if verbose >= 2: print '  - AmbTemp'
            self.AmbTemp = AmbTemp.AmbTemp_base(self.fpga)
            if verbose >= 2: print '  - MGT_PLL'
            self.MGT_PLL = MGT_PLL.MGT_PLL_base(self.fpga)
            if verbose >= 2: print '  - BiasADC'
            self.BiasADC = BiasADC.BiasADC_base(self.fpga)
        

    def check_FMC_presence(self, verbose=False):
        """ Checks if the FMC is present"""
        data = self.FMC_EEPROM.read(0,length=1,noerror=True, verbose=verbose)
        self._board_is_present = (data[0] == 13) 

    def is_present(self):
        """ returns a boolean indicating whether the ADC board is present"""
        return self._board_is_present

    def load_board_info(self):
        """ loads the info data block from the ADC board EEPROM into memory for future access. """
        self._board_info = {
        'Model': 'MGADC08',
        'Revision' : 'Unknown',
        'SYNC delay': 0,
        'ADC delays': []
        }
         

    def init(self, sampling_frequency=800e6, reference_frequency=10e6, verbose=0):
        """ Initializes the FMC board modules""" 


        if self.is_present():
            self.sampling_frequency = sampling_frequency
            self.reference_frequency = reference_frequency

            if verbose >= 2: print '  - AmbTemp'
            self.AmbTemp.init()
    
            if verbose >= 2: print '  - IOExpander'
            self.IOExpander.init()
    
            if verbose >= 2: print '  - ADC_PLL'
            self.ADC_PLL.init(fout=2*self.sampling_frequency/1e6, fref=self.reference_frequency/1e6, verbose=0)
    
            if verbose >= 2: print '  - ADC'
            self.ADC.init()

    def status(self):
        """ Displays the status of the ADC board""" 
        print '======= MGADC FMC ADC BOARD  ============='
        print 'FMC board is present:', self.is_present()
        if self.is_present():
            self.FMC_EEPROM.status()
            self.AmbTemp.status()
            self.IOExpander.status()
            self.ADC_PLL.status()
            self.ADC.status()
        else:
            print ' *** Board is not present'
