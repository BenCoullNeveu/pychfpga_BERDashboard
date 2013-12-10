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
    """ Implements the interface to one of the channelizer"""

    CHAN_MODULE_ADDR_INCREMENT = 0x00400
    # Antenna processor module addresses
    ADCDAQ_OFFSET_ADDR  = 0 * CHAN_MODULE_ADDR_INCREMENT
    SRCSEL_OFFSET_ADDR  = 1 * CHAN_MODULE_ADDR_INCREMENT
    FFT_OFFSET_ADDR     = 2 * CHAN_MODULE_ADDR_INCREMENT
    SCALER_OFFSET_ADDR  = 3 * CHAN_MODULE_ADDR_INCREMENT
    PROBER_OFFSET_ADDR  = 4 * CHAN_MODULE_ADDR_INCREMENT
    FUNCGEN_OFFSET_ADDR = 5 * CHAN_MODULE_ADDR_INCREMENT
    INJECT_OFFSET_ADDR  = 6 * CHAN_MODULE_ADDR_INCREMENT

    def __init__(self, fpga_instance, base_address, instance_number):
        #super(ADC_chip,self).__init__(fpga)
        # self.ant = ant_instance # store current ADC number for this instance
        self.ant_number = instance_number # store current ADC number for this instance
        self.fpga = fpga_instance
        self.logger = logging.getLogger(__name__)

        # port = self.fpga.ANT_PORT[self.ant_number]

        self.ADCDAQ  = ADCDAQ.ADCDAQ_base( fpga_instance,   base_address + self.ADCDAQ_OFFSET_ADDR,  instance_number)
        self.SRCSEL  = SRCSEL.SRCSEL_base( fpga_instance,   base_address + self.SRCSEL_OFFSET_ADDR,  instance_number)
        self.FFT     = FFT.FFT_base( fpga_instance,         base_address + self.FFT_OFFSET_ADDR,     instance_number)
        self.SCALER  = SCALER.SCALER_base( fpga_instance,   base_address + self.SCALER_OFFSET_ADDR,  instance_number)
        self.PROBER  = PROBER.PROBER_base( fpga_instance,   base_address + self.PROBER_OFFSET_ADDR,  instance_number)
        self.FUNCGEN = FUNCGEN.FUNCGEN_base( fpga_instance, base_address + self.FUNCGEN_OFFSET_ADDR, instance_number)
        self.INJECT  = INJECT.INJECT_base( fpga_instance,   base_address + self.INJECT_OFFSET_ADDR,  instance_number)
        self.frame_length = self.fpga.FRAME_LENGTH

        
    # def read(self, module, addr, *args, **kwargs): 
    #     """ Reads data from the specified module at the specified address""" 
    #     return self.fpga.read(self.ant_number, module, addr, *args, **kwargs)

    # def write(self, module, addr, data, *args, **kwargs): 
    #     """ Writes data to the specified module at the specified address""" 
    #     return self.ant.write(self.ant_number, module, addr, data, *args, **kwargs)



    def init(self, fmc_present):

        self.fmc_present = fmc_present

        """ Initializes the antenna modules""" 
        self.logger.debug('Initializing modules for antenna #%i' % self.ant_number)
        self.logger.debug('  - ADCDAQ')
        self.ADCDAQ.init(fmc_present)
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
        #self.logger.info('=== ANTENNA NUMBER %i ' % self.ant_number)
        # self.ADCDAQ.status()
        # self.SRCSEL.status()
        # self.FFT.status()
        # self.SCALER.status()
        # self.PROBER.status()
        # self.FUNCGEN.status()
        # self.INJECT.status()

class ANT_base(object):
    """ Instantiates a container for all channelizers available on the FPGA. 
    """

    def __init__(self, fpga, base_address, address_increment, verbose=0):
        self.fpga = fpga
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        # Create an instance of ADC_chip for each chip of the FMC board
        self.frame_length = fpga.FRAME_LENGTH
        self.ANT = []
        for i in range(fpga.NUMBER_OF_ANTENNAS):
            self.ANT.append(ANT_channel(self.fpga, base_address + i * address_increment, i))

    def __getitem__(self, key):
        """If the user indexes this object (ANT[n] instead of ANT) then return the antenna processor instance"""
        return self.ANT[key]

    def __len__(self):
        """Returns the number of antennas"""
        return len(self.ANT)

    # Low-level access functions

    # def read(self, ant_number, module_number, addr, *args, **kwargs):
    #     """ Reads from the register of a module of a specified antenna processor"""
    #     fpga = self.fpga
    #     data = fpga.read(fpga.ANT_PORT[ant_number], module_number, addr, *args, **kwargs)
    #     return data

    # def write(self, ant_number, module_number, addr, data, *args, **kwargs):
    #     """ Writes to the register of a module of a specified antenna processor"""
    #     fpga = self.fpga
    #     fpga.write(fpga.ANT_PORT[ant_number], module_number, addr, data, *args, **kwargs)

    def init(self, delay_table=None, fmc_present=None):
        """ Initializes all antennas""" 

        # Selects which clock is used to clock the channelizes based on whether the ADC card that normally provides the clock is present or not.
        if fmc_present[self.fpga.CHANNELIZERS_CLOCK_SOURCE]:
            self.logger.info('Using the ADC to generate the channelizer clock')
            self.fpga.GPIO.CHAN_CLK_SRC = 0 # uses the ADC clock to clock the channelizers
        else:
            self.logger.info('Using the internal clock to generate the channelizer clock since the ADC is not available')
            self.fpga.GPIO.CHAN_CLK_SRC = 1 # uses the internal 200 MHz clock to clock the channelizer

        for (i, ant) in enumerate(self.ANT):
            self.logger.debug('Initializing Antenna #%i %s' % (ant.ant_number, '' if fmc_present[i] else '(No ADC board)'))
            ant.init(fmc_present[i])

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

    def set_data_width(self, width):
        """
        Set the number of bits used to represent the values computed by the channelizers.
        All channelizers are set to the new setting.
            width=4: data is 4 bits Real + 4 bits Imaginary
            width=8: data is 8 bits Real + 8 bits Imaginary
        """

        if width==4:
            is_four_bits = 1
        elif width == 8:
            is_four_bits = 0
        else:
            raise self.fpga.chFPGAException('Number of bits %i is invalid for the channelizers. Only 4 or 8 is allowed' % width)

        # Set the channelizer data width
        for ch in self.ANT:
            ch.SCALER.FOUR_BITS = is_four_bits

    def get_data_width(self):
        """
        Returns number of bits used to represent the values computed by the channelizers.
        If all the channelizer are not set in the same mode, an error is raised.
        """

        four_bits = set() # use a set to uniquely record all the possible encountered states

        for ch in self.ANT:
            four_bits.add(ch.SCALER.FOUR_BITS)

        if four_bits == set([0]):
            return 8
        elif four_bits == set([1]):
            return 4
        else:
            raise self.fpga.chFPGAException("The channelizers are not set to the same data width.")


    def print_ramp_errors(self):
        try:
            while 1:
                for ant in self.ANT:
                    print 'CH%i: %3i' % (ant.ant_number, ant.ADCDAQ.RAMP_ERR_CTR),
                print
        except KeyboardInterrupt:
            pass
        
