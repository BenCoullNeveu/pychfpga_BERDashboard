#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
ANT.py module 
    Implements interface to the Antenna processors

History:
    2011-07-12 : JFC : Created from test code in chFPGA.py
    2012-08-31 JFC: Swapped addresses of PROBER and SCALER to match the same change in firmware
    2012-09-25 JFC: Renamed to FRAMER and FR_DIST to SRCSEL
"""
import logging

import ADCDAQ
import SRCSEL
import FFT
import SCALER
import PROBER    
import FUNCGEN
import INJECT

class ANT_channel(object):
    """ Implements interface to one of the antenna processor pipeline"""

    # Antenna processor module addresses
    ADCDAQ_MODULE  = 0
    SRCSEL_MODULE  = 1
    FFT_MODULE     = 2
    SCALER_MODULE  = 3
    PROBER_MODULE  = 4
    FUNCGEN_MODULE = 5
    INJECT_MODULE  = 6

    def __init__(self, ant_instance, ant_number):
        #super(ADC_chip,self).__init__(fpga)
        self.ant = ant_instance # store current ADC number for this instance
        self.ant_number = ant_number # store current ADC number for this instance
        self.fpga = self.ant.fpga
        self.logger = logging.getLogger(__name__)

        port = self.fpga.ANT_PORT[self.ant_number]

        self.ADCDAQ  = ADCDAQ.ADCDAQ_base(self, port, self.ADCDAQ_MODULE)
        self.SRCSEL  = SRCSEL.SRCSEL_base(self, port, self.SRCSEL_MODULE)
        self.FFT     = FFT.FFT_base(self, port, self.FFT_MODULE)
        self.SCALER  = SCALER.SCALER_base(self, port, self.SCALER_MODULE)
        self.PROBER  = PROBER.PROBER_base(self, port, self.PROBER_MODULE)
        self.FUNCGEN = FUNCGEN.FUNCGEN_base(self, port, self.FUNCGEN_MODULE)
        self.INJECT  = INJECT.INJECT_base(self, port, self.INJECT_MODULE)
        self.frame_length = self.ant.frame_length

        
    def read(self, module, addr, *args, **kwargs): 
        """ Reads data from the specified module at the specified address""" 
        return self.ant.read(self.ant_number, module, addr, *args, **kwargs)

    def write(self, module, addr, data, *args, **kwargs): 
        """ Writes data to the specified module at the specified address""" 
        return self.ant.write(self.ant_number, module, addr, data, *args, **kwargs)



    def init(self):
        """ Initializes the antenna modules""" 
        self.logger.info('Initializing modules for antenna #%i' % self.ant_number)
        self.logger.debug('  - ADCDAQ')
        self.ADCDAQ.init()
        self.logger.debug('  - SRCSEL')
        self.SRCSEL.init()
        self.logger.debug('  - FFT')
        self.FFT.init()
        self.logger.debug('  - SCALER')
        self.SCALER.init()
        self.logger.debug('  - PROBER')
        self.PROBER.init()
        self.logger.debug('  - FUNCGEN')
        self.FUNCGEN.init()
        self.logger.debug('  - INJECT')
        self.INJECT.init()


    def status(self):
        """ Displays the status of the antenna modules""" 
        self.logger.info('======= ANTENNA NUMBER %i =============' % self.ant_number)
        # self.ADCDAQ.status()
        # self.SRCSEL.status()
        # self.FFT.status()
        # self.SCALER.status()
        # self.PROBER.status()
        # self.FUNCGEN.status()
        # self.INJECT.status()

class ANT_base(object):
    """ Instantiates a container for all antenna processors available on the FPGA """

    def __init__(self, fpga, verbose=0):
        self.fpga = fpga
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        # Create an instance of ADC_chip for each chip of the FMC board
        self.frame_length = fpga.FRAME_LENGTH
        self.ANT = []
        for i in range(fpga.NUMBER_OF_ANTENNAS):
            self.ANT.append(ANT_channel(self, i))

    def __getitem__(self, key):
        """If the user indexes this object (ANT[n] instead of ANT) then return the antenna processor instance"""
        return self.ANT[key]

    def __len__(self):
        """Returns the number of antennas"""
        return len(self.ANT)

    # Low-level access functions

    def read(self, ant_number, module_number, addr, *args, **kwargs):
        """ Reads from the register of a module of a specified antenna processor"""
        fpga = self.fpga
        data = fpga.read(fpga.ANT_PORT[ant_number], module_number, addr, *args, **kwargs)
        return data

    def write(self, ant_number, module_number, addr, data, *args, **kwargs):
        """ Writes to the register of a module of a specified antenna processor"""
        fpga = self.fpga
        fpga.write(fpga.ANT_PORT[ant_number], module_number, addr, data, *args, **kwargs)

    def init(self, delay_table=None):
        """ Initializes all antennas""" 
        for ant in self.ANT:
            self.logger.debug('Initializing Antenna #%i' % ant.ant_number)
            ant.init()

        if delay_table is not None:
            self.set_delays(delay_table)

    def status(self):
        """ Displays the status of all antennas""" 
        for ant in self.ANT:
            ant.status()

        #self.ANT[1].ADCDAQ.set_divclk_phase(1) # Adjust phase of the DIVCLK signal to allow proper sampling of the deserialized words

    def set_delays(self, adc_delay_table):
        """
        Sets the delays for all ADC data lines using the provided array.
        'adc_delay-table'  consists of a list of 8 arrays comprising 8 delay values each.
        """
        for i, ant in enumerate(self.ANT):    
            ant.ADCDAQ.set_delay(adc_delay_table[i]) 

    def get_delays(self):
        """
        Return the delays currently in use for all ADC data lines.
        """
        return [ant.ADCDAQ.get_delay() for ant in self.ANT]

    def print_ramp_errors(self):
        try:
            while 1:
                for ant in self.ANT:
                    print 'CH%i: %3i' % (ant.ant_number, ant.ADCDAQ.RAMP_ERR_CTR),
                print
        except KeyboardInterrupt:
            pass
        
