#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 
# pylint: disable=C0321 

"""
chFPGA.py module 
 Implements interface to the CHIME chFPGA Proof of Concept board
 

History:
    2011-01-10 : JFC : First version
    2011-04-30 JFC : Modified UDP.py into chFPGA.py to implement higher level communication system
    2011-04 - 2011-08 JFC : Major modifications & cleanup
    2011-08-29 JFC: Moved hex to util to solve circular import reference.
    2012-03-27 JFC: Modified the read and write commands to support the new format following AXI4-Streaming implementation of the command bus
    2012-05-29 JFC: Cleanup init. Support FMC board detection. Extracted test functions.
    2012-07-xx JFC: Implemented Thread-based frame buffering. Updated frame reading and plotting functions accordingly.
    2012-07-16 KMB: Started moving plotting/saving functions out to plot_utils.py, and removing redundant programs
    2012-07-25 JFC: Splitted the init() from __init() to make sure the controller object creation does not change the state of the FPGA.
        Added LCD initialization and firmware version display on the LCD
        Implemented default channel managements
    2012-08-27 JFC : Fixed reference to common.util as pychfpga.common.util         
    2012-09-18 JFC: Added set_global_trig()
    2012-10-17 JFC: Added an exception if wring function name is used in set_funcgen_function()
    2012-11-28 JM: Added function set_gain()
"""

import logging
import numpy as np
#import pdb
import time

from pychfpga.common import util

import Shared_variables # Note: do not reload this module or we will lose acces to the data in it
import Module
import SocketIO

# FPGA subsystems handlers
import SPI
import I2C
import GPIO
import SYSMON
import FreqCtr
import REFCLK
import MGT

# FPGA Antenna processor handlers
import ANT
import ADCDAQ # Included only so it can be reloaded
import SRCSEL # Included only so it can be reloaded
import INJECT # Included only so it can be reloaded
import FUNCGEN # Included only so it can be reloaded
import FFT # Included only so it can be reloaded
import SCALER # Included only so it can be reloaded
import PROBER # Included only so it can be reloaded

# FPGA Correlator handlers
import CORR_BLOCK
import CH_DIST    # Included only so it can be reloaded
import ACC # Included only so it can be reloaded


# ML605 FPGA board specific device handlers

from pychfpga.motherboards import ML605_LCD
from pychfpga.motherboards import ML605_PMBus
from pychfpga.motherboards import mgk7mb # McGill ICEBoard hardware ressources wrapper

# MGADC08 FMC ADC board device handlers
from pychfpga.MGADC08 import MGADC08 

# -- Module reloader -- 
# Reload modules if we are debugging in case the source code has changed

MODULE_LIST = (
        util, 
        SocketIO, 
        Module, 
        SPI, 
        I2C, 
        GPIO, 
        SYSMON, 
        REFCLK, 
        MGADC08,
        ML605_LCD,
        FreqCtr,
        ML605_PMBus,
        ANT,
        ADCDAQ,
        SRCSEL, 
        INJECT,
        FUNCGEN,
        FFT, 
        SCALER, 
        PROBER, 
        CORR_BLOCK, 
        CH_DIST, 
        ACC,
        MGT,
        mgk7mb,
        MGADC08
        )

util.reload_modules(MODULE_LIST)


# -- chFPGA -- 
class chFPGA_config(object):
    def __str__(self):
        return '\n'.join(['%s = %s' % (key, repr(value)) for (key,value) in sorted(vars(self).items())])    


class chFPGAException(Exception):
    def __init__(self, message):
        super(self.__class__,self).__init__(message)
        logging.error(message)


class chFPGA_controller(object):
    """
    Creates an object that connects to the specified chFPGA board and provides the methods to configure it and control its operations.

    Arguments:
        ip_address : string indicating the IP address of the chFPGA board, e.g. "10.10.10.11"
        port: control port number
        sampling_frequency: sampling frequency of the ADC in Hz, from 150 to 2500 MHz
        reference_frequency: frequency in Hz of the reference signal provided to the chFPGA. Typically 10 MHz.        
    """
    
    # Basic system constants
    IMPLEMENT_CORR = True
    ADC_CLK_SELECT = 1 # Antenna number from which the antenna processing will be clocked. This is hardwired in the firmware (need to use an ADCDAQ with a PLL)    
    #SAMPLING_FREQUENCY = 800e6 # in Hz
    #REFERENCE_FREQUENCY = 10e6 # in Hz
    SYSTEM_CLOCK_FREQUENCY = 200e6 # in Hz
    FRAME_HEADER_LENGTH = 9
    #FRAME_PERIOD = float(FRAME_LENGTH)/SAMPLING_FREQUENCY

    # Port numbers
    SYSTEM_PORT = 0 # This is always at zero so we can gather info from the FPGA before we know the number of antennas etc.
    ANT_PORT = None # Antennas ports are determined dynamically based on the info from the firmware
    CORR_PORT = None # Correlator ports are determined dynamically based on the info from the firmware
    #MGT_PORT = NUMBER_OF_ANTENNAS+2 -- for future use, if needed


    # SYSTEM Modules addresses
    SYSTEM_GPIO_MODULE = 0
    SYSTEM_SYSMON_MODULE = 1
    SYSTEM_FREQ_CTR_MODULE = 2
    SYSTEM_SPI_MODULE = 3
    SYSTEM_REFCLK_MODULE = 4
    SYSTEM_I2C_MODULE = 5

    GPIO_COOKIE_REG = 0x080 # Register address of the firmware cookie
    CHFPGA_COOKIE = 0x42 # Expected cookie value for chFPGA
    PLATFORM_ID_ML605 = 0
    PLATFORM_ID_KC705 = 1
    PLATFORM_ID_MGK7MB = 2

    PLATFORM_ID_LIST = {
        # ID: ( Board name, class to instantiate)
        0: ('Virtex 6 (XC6V240T-1 FFG1156) on Xilinx ML605 Evaluation board', None),
        1: ('Kintex 7 (XC7K325T-2 FFG900C) on Xilinx KC705 Evaluation board', None),
        2: ('Kintex 7 (XC7K420T-2 FFG901) on McGill MGK7MG / ICEBoard Rev0', mgk7mb.MGK7MB),
    }

    def __init__(self, ip_address='10.10.10.11', port_number=41000, init=1, verbose=2, **kwargs):
        """
        Opens communication with the specified chFPGA. This does not affect the state and operations of chFPGA.
        """
        # Initialize instance attributes
        # For now, we do not know their values unless the system is initialized. 
        # We may want to fix that by reading the FPGA states and determining those values. 
        self.sampling_frequency = None
        self.reference_frequency = None
        self.FRAME_PERIOD = None
        self.FMC_present = None  # indicates if the FMC board is present. If not, the modules will act accordingly.
        self.ip_address = ip_address # store the IP address so we can use it to delete the shared_variable
        self.log = logging.getLogger(__name__)

        self.motherboard = None
        self.adc_board = []
        self.fpga = None

        self.log.info("Creating chfpga_controller object ")

        # Close the socket open by a previous instance
        if ip_address in Shared_variables.controller_sock:
            self.log.info('Closing the socket open in a previous instance ' +
                          'for IP address %s' % ip_address)
            Shared_variables.controller_sock[ip_address].close()
            del Shared_variables.controller_sock[ip_address]

        self.log.info("Opening control communication sockets to FPGA at %s:%i." % (ip_address, port_number))

        # Create socket handled and open socket communications to the chFPGA board
        self.sock = SocketIO.ControlSocket_base(ip_address, port_number)
        Shared_variables.controller_sock[ip_address] = self.sock # Save the socket in a persistent storage so it can be closed if needed  

        if init < 0: # If init<0, we do not perform any communication with the FPGA, so we don't read the firmware configuration
            self.log.info('Upon user request (init < 0), communication with the FPGA are inhibited. Initialization sequence stops here. Use this for debug only.')
            return

        self.log.info("Attempting to communicate with the FPGA")

        try:
            cookie = self.read(self.SYSTEM_PORT, self.SYSTEM_GPIO_MODULE, self.GPIO_COOKIE_REG) # Read anything from the GPIO subsystem (which is always present on all versions of the FPGA)
        except Exception as e:
            error_message = "Unable to communicate with the FPGA at address %s:%i due to the following exception: %s" % (ip_address, port_number, repr(e))
            self.log.error(error_message)
            self.close()
            raise chFPGAException(error_message)

        self.log.info("Contact with the FPGA established")

        if cookie != self.CHFPGA_COOKIE:
            error_message = 'The firmware at %s:%i is not chFPGA. The magic cookie returned by the FPGA is 0x%02X, whereas we expected 0x%02X' % (ip_address, port_number, cookie, self.CHFPGA_COOKIE)
            self.log.error(error_message)
            self.close()
            raise chFPGAException(error_message)

        self.log.info('   ---> Hello! This is chFPGA! <---')



        try: # catch initialization errors so we can free the socket for future instantiation

            # Create handware handling objects 
            #  NOTE: Does not initialize them yet because some modules are interdependent - we need to wait until all of them are instantiated.
            #  NOTE: The instantiation does not initiate communicattion with the hardware yet. this is done in the INIT phase.
    
            # ---------------------------------------------------------------------
            # -- Create basic FPGA ressource handlers objects
            # ---------------------------------------------------------------------

            if verbose >= 2: self.log.debug('  - GPIO')
            self.GPIO = GPIO.GPIO_base(self)
            # get system constants from the FPGA

            self.log.info('Getting board info information')

            self.PLATFORM_ID = self.GPIO.PLATFORM_ID
            if self.PLATFORM_ID not in self.PLATFORM_ID_LIST:
                raise chFPGAException('Platform ID 0x%02X is not recognized' % self.PLATFORM_ID)
            self.NUMBER_OF_FMC_SLOTS = None
            self.NUMBER_OF_ANTENNAS = self.GPIO.NUMBER_OF_ANTENNAS
            if self.NUMBER_OF_ANTENNAS == 0:
                self.NUMBER_OF_ANTENNAS = 16
            self.NUMBER_OF_CORRELATORS_MAX = self.GPIO.NUMBER_OF_CORRELATORS
            self.LIST_OF_IMPLEMENTED_CORRELATORS = [i for i in range(8) if bool(self.GPIO.IMPLEMENT_CORR & 2**i) and i<self.NUMBER_OF_CORRELATORS_MAX]
            #self.LIST_OF_IMPLEMENTED_CORRELATORS = range(self.NUMBER_OF_CORRELATORS)
            self.NUMBER_OF_CORRELATORS = len(self.LIST_OF_IMPLEMENTED_CORRELATORS)
            self.NUMBER_OF_ANTENNAS_TO_CORRELATE = self.GPIO.NUMBER_OF_ANTENNAS_TO_CORRELATE
            self.LOG2_FRAME_LENGTH = self.GPIO.LOG2_FRAME_LENGTH
            self.FRAME_LENGTH = 2**self.LOG2_FRAME_LENGTH # 2**11 = 2048 time samples per frame
            self.ANT_PORT =  range(self.SYSTEM_PORT + 1, self.SYSTEM_PORT + 1 + self.NUMBER_OF_ANTENNAS) # Antennas are ports 0-7
            self.CORR_PORT = range(self.SYSTEM_PORT + 1 + self.NUMBER_OF_ANTENNAS, self.SYSTEM_PORT + 1 + self.NUMBER_OF_ANTENNAS + self.NUMBER_OF_CORRELATORS)
            self.default_channels = range(self.NUMBER_OF_ANTENNAS)
            self.LIST_OF_ANTENNAS_WITH_FFT = [i for i in range(8) if bool(self.GPIO.IMPLEMENT_FFT & 2**i)]

            self.log.info('System configuration')
            self.log.info('   Hardware platform: %s' % self.PLATFORM_ID_LIST[self.PLATFORM_ID][0])
            self.log.info('   Firmware timestamp: %s' % self.get_version())
            self.log.info('   Number of antenna inputs: %i' %  self.NUMBER_OF_ANTENNAS)
            self.log.info('   Number of antennas with channelizers: %i (antennas %s)' % (len(self.LIST_OF_ANTENNAS_WITH_FFT), str(self.LIST_OF_ANTENNAS_WITH_FFT)))
            self.log.info('   Number of correlators: %i (correlators %s)' % (len(self.LIST_OF_IMPLEMENTED_CORRELATORS),str(self.LIST_OF_IMPLEMENTED_CORRELATORS)))
 
        # version = self.fpga.read(BASE_REGISTERS_BASE_ADDR + BASE_VERSION_REG)
        # firmware_timestamp = self.get_bitstream_timestamp()
        # config_reg1 = self.fpga.read(BASE_REGISTERS_BASE_ADDR + BASE_CONFIG1_REG)
        # config_reg2 = self.fpga.read(BASE_REGISTERS_BASE_ADDR + BASE_CONFIG2_REG)

        # self.NUMBER_OF_MEZZANINES                           = (config_reg1 >> 0) & 0xFF
        # self.NUMBER_OF_SQUID_CHANNELS_PER_MEZZANINE         = (config_reg1 >> 8) & 0xFF
        # self.NUMBER_OF_FREQUENCY_CHANNELS_PER_SQUID_CHANNEL = (config_reg1 >> 16) & 0xFF
        # self.NUMBER_OF_SQUID_CONTROLLERS                    = (config_reg1 >> 24) & 0xFF
        # self.PLATFORM_ID                                    = (config_reg2 >> 24) & 0xFF
        # self.PLATFORM_DESCRIPTION = PLATFORM_DESCRIPTION_LIST[self.PLATFORM_ID];

        # print '   Hardware platform:', self.PLATFORM_DESCRIPTION
        # print '   Firmware timestamp:', firmware_timestamp
        # print '   Firmware Magic Cookie: 0x%08X' % cookie
        # print '   Firmware version number: %i' % version
        # print '   Number of mezzanines supported: %i' % self.NUMBER_OF_MEZZANINES;
        # print '   Number of SQUID Channels/mezzanine: %i' % self.NUMBER_OF_SQUID_CHANNELS_PER_MEZZANINE
        # print '   Number of frequency channels per SQUID channel: %i' % self.NUMBER_OF_FREQUENCY_CHANNELS_PER_SQUID_CHANNEL
        # print '   Number of SQUID controllers supported: %i' % self.NUMBER_OF_SQUID_CONTROLLERS
                       
            self.log.debug('Instantiating chFPGA modules.')

            self.log.debug('  - I2C')
            self.fpga_I2C = I2C.I2C_base(self)

            self.log.debug('  - SYSMON')
            self.SYSMON = SYSMON.SYSMON_base(self)

            self.log.debug('  - SPI')
            self.SPI = SPI.SPI_base(self)

            self.log.debug('  - FreqCtr')
            self.FreqCtr = FreqCtr.FreqCtr_base(self)

            self.log.debug('  - REFCLK')
            self.REFCLK = REFCLK.REFCLK_base(self)
            
            self.log.debug('  - ANT')
            self.ANT = ANT.ANT_base(self) # Antenna processors (ADCDAQ, SRCSEL, FFT, SCALER) for each input
    
            self.log.debug('  - CORR')
            self.CORR = CORR_BLOCK.CORR_BLOCK_base(self) # Correlator (CH_DIST, CORR, ACC) for each correlator

    
            # ---------------------------------------------------------------------
            # -- Create motherboard ressource handlers objects
            # ---------------------------------------------------------------------

            self.log.debug('  - Loading motherboard ressources')
            motherboard_cls = self.PLATFORM_ID_LIST[self.PLATFORM_ID][1]
            self.motherboard = motherboard_cls(self) # Creates the motherboard handler

            self.NUMBER_OF_FMC_SLOTS = self.motherboard.get_number_of_fmc_slots()
            self.log.info('This motherboard has %i FMC slots' % self.NUMBER_OF_FMC_SLOTS)
            #return
            # self.log.debug('  - ML605 PMBus')
            # self.ML605_PMBus = ML605_PMBus.ML605_PMBus_base(self)

            # self.log.debug('  - ML605 PMBus')
            # self.LCD = ML605_LCD.LCD_base(self.GPIO)

            #if verbose>=2: self.log.debug('  - MGT')
            #self.MGT=MGT.MGT_base(self)
    
    
            # ---------------------------------------------------------------------
            # -- Create ADC board hardware ressource handlers objects
            # ---------------------------------------------------------------------
            for fmc_number in range(self.NUMBER_OF_FMC_SLOTS):
                    fmc_name = ['FMCA', 'FMCB'][fmc_number]
                    self.adc_board.append(MGADC08.MGADC08_base(self, fmc_number, fmc_name, verbose = verbose))

            self.FMC_present = self.adc_board[0].is_present() # The 3.3V supply powering the EEPROM is always on, so we can determing what FMC board is present before we power the board
            if not self.FMC_present:
                self.log.warning('The FMC ADC Board is not present')
 
        except Exception as e:
            self.log.error('An exception has occured during module instantiation. Sockets will be closed. The exception is %s' % repr(e))
            self.close()
            raise

            # Initialize subsystems. This has to be done only once all subsystems are created because some subsystems depend on each other.
        if init > 0:
            self.init(**kwargs)


    def __del__(self):

        self.close()
        self.log.debug('__del__: Closed FPGA at IP address %s' % \
                       self.sock.ip_address)

    def init(self, sampling_frequency=800e6, reference_frequency=10e6, adc_delay_table=None, verbose=0):
        """
        Resets the chFPGA to a known state with specified parameters.
        """
        
        self.sampling_frequency = sampling_frequency
        self.reference_frequency = reference_frequency
        self.FRAME_PERIOD = float(self.FRAME_LENGTH)/self.sampling_frequency

        self.log.info('Initializing FPGA modules.')

        self.log.debug('  - GPIO')
        self.GPIO.init() # This stops the antenna procesors from sending data. Neeeded if the FPGA is flooding the buffers which prevent subsequent reads to come through
        #self.sock.flush_data_socket() # Now the the data stops coming, flush the buffers
        self.sock.flush()
        if verbose >= 2: self.GPIO.status()


        self.log.debug('  - I2C')
        self.fpga_I2C.init()

        # if verbose >= 2: self.log.debug('  - ML605 LCD')
        # self.LCD.init()
        # self.LCD.write('CHIME FW Version', col=0, row=0)
        # self.LCD.write('%s' % self.GPIO.get_bitstream_date(), col=0, row=1)

        # if verbose >= 2: self.log.debug('  - ML605 PMBus')
        # self.ML605_PMBus.init()
        # if verbose >= 2: self.ML605_PMBus.status()



         # Module depend on the FMC_present flag after this point

        self.log.debug('  - REFCLK')
        self.REFCLK.init()
        self.REFCLK.status()

        #Only do for ML605, not KC705 board
        self.log.debug('  - SYSMON')
        self.SYSMON.init()
        self.SYSMON.status()

        self.log.debug('  - SPI')
        self.SPI.init()
        self.SPI.status()

        self.log.debug('  - ADC BOARD')

        for fmc_number in range(self.NUMBER_OF_FMC_SLOTS):
            self.log.debug('   Powering up ADC board #%i', fmc_number)
            self.motherboard.set_fmc_power(fmc_number, False)
            # We need to initialize the ADC board befor we initialize ANT (and its data acquisition) because the delay blocks need a clock
            self.log.debug('   Initializing ADC board #%i', fmc_number)
            self.adc_board[fmc_number].init(sampling_frequency = sampling_frequency, reference_frequency=reference_frequency)
            self.adc_board[fmc_number].status()
        self.sync() # might be needed  to make sure that the clock is running to set delays

        self.FMC_present = self.adc_board[0].is_present()

        self.log.debug('  - ANT')
        self.ANT.init(delay_table=adc_delay_table)
        self.ANT.status()

        if self.IMPLEMENT_CORR and self.NUMBER_OF_CORRELATORS>0:
            self.log.debug('  - CORR')
            self.CORR.init()
            self.CORR.status()

        # MGT is disabled    
        #self.log.debug('  - MGT_PLL')
        #self.MGT_PLL.init(fref=fref)
        #self.log.debug('  - MGT')
        #self.MGT.init() # MGT_PLL must be initialized first
        
            self.log.info("Done with initializations.")


        #self.log.info("Setting ADCDAQ delays.")

        #if adc_delay_table:
        #    self.ANT.set_delays(adc_delay_table)

 
        self.set_ant_reset(0) # disable antenna reset
        
        self.log.info("Setting FPGA ADC mode")
        self.set_funcgen_function('ramp')
        self.set_data_source('funcgen')
        self.set_ADC_mode('data') # This implies a self.sync(), which will reset the antenna processors again to ensure data alignment
        self.set_data_source('adc')

        self.log.info("End of chFPGA initialization.")

    def get_fpga_cookie(self):
        """
        Reads the FPGA and returns the cookie that identifies the firmware.
        This method can be called before any FPGA modules are instatiated. 
        """
        return self.read(self.SYSTEM_PORT, self.SYSTEM_GPIO_MODULE, self.GPIO_COOKIE_REG) & 0x7F

    def get_config(self):
        config = chFPGA_config() # Create empty config container
        # Add configuration parameters

        config.config_protocol_version = (1,0)
        config.config_capture_time = time.time()
        config.system_firmware_version = self.get_version()
        config.system_platform_id = self.PLATFORM_ID
        config.number_of_antennas_to_correlate = self.NUMBER_OF_ANTENNAS_TO_CORRELATE
        config.number_of_correlators = self.NUMBER_OF_CORRELATORS
        config.number_of_antennas = self.NUMBER_OF_ANTENNAS
        config.number_of_correlators_max = self.NUMBER_OF_CORRELATORS_MAX
        config.system_list_of_implemented_correlators = self.LIST_OF_IMPLEMENTED_CORRELATORS
        config.system_list_of_antennas_with_channelizers = self.LIST_OF_ANTENNAS_WITH_FFT
        config.system_frame_length = self.FRAME_LENGTH
        config.system_sampling_frequency = self.sampling_frequency
        config.system_reference_frequency = self.reference_frequency
        config.system_frame_period = self.FRAME_PERIOD

        config.adc_board_is_present = self.adc_board[0].is_present()
        if self.adc_board[0].is_present():
            config.adc_board_temperature = self.adc_board[0].AmbTemp.temperature
            config.adc_board_adc_chip_temperature = [adc.temperature for adc in self.adc_board[0].ADC]
        config.antenna_data_source = self.get_data_source()
        config.antenna_fft_bypass = self.get_FFT_bypass()
        config.antenna_fft_shift_schedule = self.get_FFT_shift()
        config.antenna_scaler_log2_gain = self.get_gain()
        config.correlator_capture_period_in_frames = [corr.ACC.CAPTURE_PERIOD for corr in self.CORR]
        config.correlator_integration_period_in_frames = [corr.ACC.INTEGRATION_PERIOD for corr in self.CORR]
        config.antenna_adc_data_acquisition_delay_tables  = self.ANT.get_delays()
        config.FPGA_board_frequency = self.FreqCtr.read_frequency('CLK200', gate_time=0.05)
        config.CTRL_clock_frequency = self.FreqCtr.read_frequency('CTRL_CLK', gate_time=0.05)
        config.ant_clock = self.FreqCtr.read_frequency('ANT_CLK', gate_time=0.05)
        config.correlator_clock = self.FreqCtr.read_frequency('CORR_CLK', gate_time=0.05)
        config.fmc_ref_clock = self.FreqCtr.read_frequency('FMC_REFCLK', gate_time=0.05)
        config.mgt_ref_clock = self.FreqCtr.read_frequency('MGT_REFCLK', gate_time=0.05)
        config.mgt_word_clock = self.FreqCtr.read_frequency('MGT_USRCLK2', gate_time=0.05)
        config.adc_clocks = [self.FreqCtr.read_frequency(('ADC_CLK'+str(i)), gate_time=0.05) for i in range(8)]
        # Add FFT shift, scaler gain, corr integration/capture period etc.
        return config

        
    def update_config(self):
        pass
    
    def close(self):
        """ 
        Close chFPGA object, which releases the socket bindings
        """
        self.sock.close()
        if self.ip_address in Shared_variables.controller_sock:
            del Shared_variables.controller_sock[self.ip_address]

    def read(self, ant, module, addr, type=np.dtype('>u1'), length=1, incr=1):
        """ Reads memory-mapped byte(s) from the FPGA through the Ethernet interface.
        Returns a numpy array where the bytes are intrepreted as a series of 'length' elements of type 'type'.
        """

        itemsize = np.dtype(type).itemsize # number of bytes contained in the destinaion vector type
        dout = np.zeros(length*itemsize, np.int8) # initialize result vector as a byte array
        NBYTES = 0
        # Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))
        for i in range(length*itemsize): 
            s = chr(0x00+(NBYTES<<3)+(ant>>3))+chr(((ant&0x07)<<5)+(module<<2)+(addr>>8))+chr(addr&0xff)
            self.sock.write(s)
            data = self.sock.read()
            #if data[0]!=s[0]:
            #    self.log.error("Read: ERROR: Returned ANT/SUB/ADDR (",   ata[0:2]," does not match request values (",   [0:2],")")
            if len(data) != 2:
                self.log.error("Read: ERROR: %i bytes were returned" % len(data))
            dout[i] = ord(data[1]) # store received byte
            if incr: addr += 1
        dout.dtype = np.dtype(type) # change interpretation of the byte array into a 'type' array

        #if we requested a single value (length=1), returns the object, otherwise return a numpy array of objects
        if len(dout) == 1:
            return dout[0]
        else:
            return dout
        
    
    def write(self, ant, module, addr, data, incr=1):
        """ 
        Writes byte(s) to memory-mapped registers in the FPGA through the Ethernet interface.
        'data' can be:
            - String
            - list of integers between 0 and 255
            - numpy array of integers between 0 and 255
            - 4 bytes in a numpy uint32. MSB is transmitted first
            - 2 bytes in a numpy uint16. MSB is transmitted first
            - 1 byte in a numpy uint8. 
        """
        # build command packet
        #s=chr(0x80+ant+(0x40 if incr else 0))+chr((module<<2)+(addr>>8))+chr(addr&0xFF) 
        NBYTES = 0
        string = chr(0x80 + (0x40 if incr else 0) + (NBYTES << 3) + (ant >> 3)) + chr(((ant & 0x07) << 5) + (module << 2) + (addr >> 8)) + chr(addr & 0xff)

        # Add the data to the string. The method depends on the data type
        if type(data) == str:
            string += data
            length = len(data)
        elif type(data) == list or type(data) == np.ndarray:
            string += ''.join([chr(data[i]) for i in range(len(data))])
            length = len(data)
        elif type(data) == np.uint32:
            length = 4
            a = np.array([data], np.dtype('>u4')) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            string += ''.join([chr(a[i]) for i in range(4)])
        elif type(data) == np.uint16:
            length = 2
            a = np.array([data], np.dtype('>u2')) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            string += ''.join([chr(a[i]) for i in range(2)])
        elif type([data]) == np.uint8:
            length = 1
            a = np.array([data]) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            string += chr(a[i])
        else:
            string += chr(data)
            length = 1
        self.sock.write(string)
        return length
        

    # Define Read and Write for legacy compatibility
    Read = read
    Write = write

    def read_bit(self, port, module, addr, bit):
        return (self.read(port, module, addr) & (1<<bit))!=0

    def write_bit(self, port, module, addr, bit, data):
        old_data = self.read(port,module,addr)
        mask = 1<<bit
        self.write(port, module, addr, (old_data & (~mask)) | (mask if data else 0))

    def write_mask(self, port, module, addr, mask, data):
        old_data = self.read(port, module, addr)
        self.write(port, module, addr, (old_data & (~mask)) | (mask & data))

    def pulse_bit(self, port, module, addr, bit):
        old_data = self.read(port, module, addr)
        mask = 1 << bit
        self.write(port, module, addr, (old_data | mask))
        self.write(port, module, addr, (old_data & (~mask)))

    def sync(self, local=1, verbose=0):
        if verbose:
            self.log.info("Sync...")
        if local:
            self.REFCLK.local_sync()
        else:
            self.REFCLK.sync()

    def pulse_ant_reset(self):
        """ Resets the stats of all antenna processor modules and clear the processing pipeline.
        Memory-mapped registers are not affected.
        """
        self.GPIO.pulse_ant_reset() # resets all 

    def reset(self):
        """ Resets the antenna processor modules and collelators.
        Memory-mapped registers are not affected.
        """
        self.set_ant_reset(1)            
        self.set_corr_reset(1)            
        self.set_corr_reset(0)
        self.set_ant_reset(0)            

    def set_default_channels(self, channels):
        """
            Sets the default channels to use in other functions when not specifically specified.
        """
        if isinstance(channels,int):
            channels = [channels]
        self.default_channels = channels

    def get_default_channels(self):
        """
            Returns the default channels that are used in other functions when not specifically specified.
        """
        return self.default_channels

    def set_data_path(self, source=None, function=None, a=1, b=0, adc_mode='data', adcdaq_mode='data', fft_bypass=None, scaler_gain=None, channels=None):
        """
            Single command used to set multiple data path settings. The data processing chain is:
            ADC --> ADCDAQ --> |        |
                   FUNCGEN --> | SRCSEL | --> FFT --> SCALER
                    INJECT --> |        |
        """
        if function is not None:
            self.set_funcgen_function(function=function, a=a, b=b, channels=channels)

        if adcdaq_mode is not None:
            self.set_adcdaq_mode(mode=adcdaq_mode, channels=channels)

        if fft_bypass is not None:
            self.set_fft_bypass(bypass_mode=fft_bypass, channels=channels)

        if scaler_gain is not None:
            self.set_gain(log2_gain=scaler_gain, channels=channels)
        if adc_mode is not None:
            self.set_adc_mode(mode=adc_mode, channels=channels)

    def set_data_source(self, source=None,  channels=None):
        '''
            Sets the data source on specified channels (or default channels if the channels are not specified).
        '''
        if (source is None) or (source.lower() not in self.ANT[0].SRCSEL.DATA_SOURCE_NAMES):
            self.log.info('Valid data sources are %s:' % ', '.join(self.ANT[0].SRCSEL.DATA_SOURCE_NAMES.keys()))
            return
            
        if channels is None:
            channels = self.default_channels

        
        self.set_ant_reset(1) # Reset is needed to resyncronize the system with the new data 
        for ch in channels:
            ant = self.ANT[ch]
            ant.SRCSEL.set_data_source(source.lower())
        self.set_ant_reset(0) # Reset is needed to resyncronize the system with the new data 
        #self.sync() # SYNCs the ADC, and resets (again) the antenna processor to align the data with the ADC


    def get_data_source(self):
        '''
            Returns a list of data source for all channels.
        '''
        return [ant.SRCSEL.get_data_source() for ant in self.ANT]        


    def set_funcgen_function(self, function=None, a=1, b=0, channels=None):
        '''
        Sets the waveform generated by the function generator on specified channels (or default channels if the channels are not specified).
        This may cause one frame to partially contain the new waveform.
        '''
        if (function is None) or (function.lower() not in self.ANT[0].FUNCGEN.FUNCTION_NAMES):
            self.log.info('Valid functions are %s:' % ', '.join(self.ANT[0].FUNCGEN.FUNCTION_NAMES.keys()))
            raise Exception('Invalid function generator function string')

        if channels is None:
            channels = self.default_channels
     
        for ch in channels:
            ant = self.ANT[ch]
            ant.FUNCGEN.set_function(function.lower(), a=a, b=b)

    ADC_MODE_NAMES = {
        # name, mode number, period (in 4-bytes words)
        'data' : (0, 64), # ADC sends analog data
        'ramp' : (1, 64), # ADC sends ramp from 0 to 255
        'pulse': (2, 11), # ADC sends ten 0x00 followed by one 0xff
        }    

    # ADC_MODE_NAMES_REVERSED = util.reverse_dict(ADC_MODE_NAMES)

    def set_adc_mode(self, mode='data', channels=None):
        """
        Sets the test mode of both ADCs, sets the proper CAPTURE period, and sends a SYNC.
            mode:
                'data': Normal mode (ADC output contains analog samples)
                'ramp': Ramp mode (ADC output contains repeating 0-255 pattern. Note that ADCDAQ inverts bit 7 during acquisition to convert offset binary to 2's complement binary)
                'pulse': Strobe mode (ADC output contains one 0xFF followed by ten 0x00. It repeats with a pariod of 11. Same comment as above)
        111212 JFC: Added this high-level function with string mode.
        """
        if not self.adc_board[0].is_present():
            self.log.warning('ADC Board not present. Ignoring set_ADC_mode() command')
            return
            

        if channels is None:
            channels = self.default_channels

        # if isinstance(mode, int):
        #     mode_info = 'Unknown'

        mode_info = self.ADC_MODE_NAMES[mode.lower()]
        mode_value = mode_info[0]
        capture_period = mode_info[1]

        self.adc_board[0].ADC.set_test_mode(test_mode=mode_value)
        self.current_ADC_mode = mode_value

        for ant in self.ANT:
            ant.ADCDAQ.CAPTURE2_PERIOD = capture_period # set the period so we are ready to capture data correctly after the SYNC resets the CAPTURE logic

        self.sync() # make sure the ADC mode is set and that capture  restarts properly with the right period

    set_ADC_mode = set_adc_mode # For legacy code compatibility

    def get_adc_mode(self):
        """
        Gets the current operating mode of the ADCs as a string.
        """
        if not self.adc_board[0].is_present():
            self.log.warning('ADC Board not present. Ignoring get_adc_mode() command')
            return None
            
        mode_value = self.adc_board[0].ADC.get_test_mode()
        mode_string = [key for (key, info) in self.ADC_MODE_NAMES.items() if info[0]==mode_value][0] # get the name of the first ADC mode that matches the provided number
        return mode_string

    def set_adcdaq_mode(self, mode='data', channels=None):
        """
        Sets the source of the data acquisition module.
            test_mode:
                'data': the ADCDAAQ module sends data from the ADC
                'ramp': The ADCDAQ sens an internally generated ramp
        """

        if channels is None:
            channels = self.default_channels

        for ch in channels:
            ant = self.ANT[ch]
            ant.ADCDAQ.set_ADCDAQ_mode(mode) # set the period so we are ready to capture data correctly after the SYNC resets the CAPTURE logic

    set_ADCDAQ_mode = set_adcdaq_mode


    def set_ant_reset(self, state):
        self.GPIO.ANT_RESET = state

    def set_corr_reset(self, state):
        self.GPIO.CORR_RESET = state

    def set_trig(self, state):
        self.GPIO.GLOBAL_TRIG = state
        
    def stop_data_capture(self):
        """
        Stops the transmission of data.
        """
        self.GPIO.GLOBAL_TRIG = 0 # disable data transmission if continuous mode is currentlly selected
        for ant in self.ANT:
            ant.PROBER.RESET = 1

    def start_data_capture(self,  burst_period_in_seconds=None, burst_period_in_frames=None, frames_per_burst=1,  number_of_bursts=0,  channels=None, sync=1, verbose=1):
        """
        Triggers the capture of the specified number of frames in the FPGA for transmission over the Ethernet port. 
        This function does not receive the frames from the ethernet port. This has to be done separately.
        History:
            2012-08-31 JFC: Fixed bandwidth computation
        """
        if channels is None:
            channels = self.default_channels

        if ( (burst_period_in_frames is None) and (burst_period_in_seconds is None)) or ((burst_period_in_frames is not None) and (burst_period_in_seconds is not None)) :
            raise SystemError("You must specify either 'burst_period_in_frames' or bust_period_in_seconds'")

        if burst_period_in_seconds is not None:
            burst_period_in_frames = max(float(burst_period_in_seconds)/self.FRAME_PERIOD, 1)


        burst_period_in_frames = int(burst_period_in_frames)
        # print "%s" % channels.__repr__()
        # print "%i" frames_per_burst
        # print burst_period_in_frames
        # print burst_period_in_frames*self.FRAME_PERIOD*1000
        # print ('continuously when TRIG=1' if not number_of_bursts else ('for a total of %i bursts' % number_of_bursts) ) 
        if verbose:
            self.log.info("Configuring antennas %s to transmit %i-frame burst every %i frames (i.e .every %.3f ms) %s." %\
                          (channels.__repr__(),
                           frames_per_burst, 
                           burst_period_in_frames, 
                           burst_period_in_frames*self.FRAME_PERIOD*1000, 
                           ('continuously when TRIG=1' if not number_of_bursts else ('for a total of %i bursts' % number_of_bursts) ) )) 
            frames_per_second = len(channels)*frames_per_burst*1.0/self.FRAME_PERIOD/burst_period_in_frames
            bits_per_second = frames_per_second * 8 * self.FRAME_LENGTH
            self.log.info('Data rates are: %f kFrames/s, %f Mbits/s' % (frames_per_second/1e3, bits_per_second/1e6))

        self.set_trig(0) # disable data transmission if continuous mode is currentlly selected
#        self.set_ant_reset(1) # resets all 
#        if clear_buffer:
#            self.flush_frame_buffer()
            
        for ant in self.ANT:
            ant.PROBER.RESET = 1
            ant.PROBER.PROBE_ID = 0xA0 + ant.ant_number
            ant.PROBER.config_capture(frames_per_burst=frames_per_burst, burst_period=burst_period_in_frames, number_of_bursts=number_of_bursts)
            if ant.ant_number in channels:
                self.log.info('Enabling Capture for Antenna %i' % ant.ant_number)
                ant.PROBER.RESET = 0

        self.set_trig(1) # enables data transmission if continuous mode is selected
#       self.set_ant_reset(0) # disable reset all 

    def set_fft_bypass(self, bypass_mode, channels=None):
        """
        Determines in the FFT is bypassed or not. Sets the BYPASS flag on both the FFT and the SCALER modules.
        All antenna processors are reset to force the FFT to resynchronize to the frame boundaries.

        History:
            2012-08-31 JFC: Added this function
            2012-10-02 JFC: Added antenna reset after bypass change to ensure the FFT is synced.
        """

        if channels is None:
            channels = self.default_channels

        for ant in self.ANT:
            if ant.ant_number in channels:
                self.log.info('Setting FFT and SCALER bypass mode for Antenna %i' % ant.ant_number)
                if (self.GPIO.IMPLEMENT_FFT & (1 << ant.ant_number)):
                    ant.FFT.BYPASS = bypass_mode
                    ant.SCALER.BYPASS = bypass_mode
                else:
                    ant.FFT.BYPASS = 1
                    ant.SCALER.BYPASS = 1
        self.reset();
        #self.sync()

    set_FFT_bypass = set_fft_bypass # for legacy code compatibility

    def get_fft_bypass(self):
        """
        Returns a list indicating if the FFT is bypassed or not for each antenna. 
        """
        return [bool(ant.FFT.BYPASS) for ant in self.ANT]

    get_FFT_bypass = get_fft_bypass # for legacy code compatiblity    

    def set_global_trigger(self, trigger_state):
        """
        Sets the global trigger to the specified value.
        
        In injection mode, the injection buffers are read only when trigger=True. This allows the buffers from all the antennas to be read simultaneously. In this case, the CAPTURE flag if the injected frames is always set.
        In other modes, the trigger status is passed to the CAPTURE flag of the data frames on a frame-by-frame basis (the CAPTURE flag is set at the begining of the frame ans syats constant until the end of the frame so no partial frames will be captured downstream.)

        History:
            120918 JFC: Added this function
        """
        self.GPIO.set_global_trig(trigger_state)

    def inject_frame(self,  data=None, length=None, channels=None):
        """ Inject a frame of data in the specified antenna processing pipeline"""
        if channels is None:
            channels = self.default_channels
        if isinstance(channels, int):
            channels = [channels]
        for ch in channels:            
            if isinstance(data, dict):
                self.ANT[ch].INJECT.inject_frame(data[ch])
            else:
                self.ANT[ch].INJECT.inject_frame(data)

    def start_corr_capture(self,  integration_period=1.0, capture_period=None, corr_to_use=None, verbose=1):
        """
        Instructs chFPGA to starts integrating and capturing the correlator outputs at the specified period. The captures data is sent over the Ethernet interface.
        The capture period can be optionnaly specified independently from the integration period. If not specified, it is equal to the integration period.
        This function does not receive the frames from the ethernet port. This has to be done separately.

        corr_to_use -> if not None, is a list specifying which to correlators to use
        History:
            2012-10-02 JFC: Created
            2013-03-25 KMB
        """

        if capture_period is None:
            capture_period = integration_period

        capture_period_in_frames = int(capture_period*1.0/self.FRAME_PERIOD)
        integration_period_in_frames = int(integration_period*1.0/self.FRAME_PERIOD)

        self.set_ant_reset(1)            
        self.set_corr_reset(1)
        if corr_to_use is None:     
            corrs = self.LIST_OF_IMPLEMENTED_CORRELATORS
            corrs_not_used = []
        else:
            corrs = corr_to_use
            corrs_not_used = list(set(self.LIST_OF_IMPLEMENTED_CORRELATORS).difference(corr_to_use))
        for corr_num in corrs:
            corr = self.CORR[corr_num]
            self.log.info('Configuring correlator %i to integrate over %f seconds (over %i frames) and transmit data every %f seconds (over %i frames)' %  (corr.instance_number, integration_period, integration_period_in_frames, capture_period , capture_period_in_frames))
            corr.ACC.RESET = 0
            corr.ACC.config(integration_period=integration_period_in_frames, capture_period=capture_period_in_frames)
        for corr_num in corrs_not_used:
            corr = self.CORR[corr_num]
            corr.ACC.RESET = 1
        self.set_corr_reset(0)
        self.set_ant_reset(0)            
        #self.sync()

    def get_version(self):
        """
        Returns the firmware revion currenting running on the FPGA (which si the date and time of bitstream generation)
        """
        return self.GPIO.get_bitstream_date()

    def get_adc_delays(self):
            return self.ANT.get_delays();

    def set_adc_delays(self, delay_table):
            return self.ANT.set_delays(delay_table);

    def read_eye_diagram(self, channels=[0], offset=5):
        """
        Measures the eye diagram of the ADC digital data lines using the ADCDAQ capture feature.
        """
        old_delays = self.get_adc_delays()
        old_adc_mode = self.get_adc_mode()
        # self.set_adc_delays((None, 0)); # Set all sampling delays to zero
        self.set_adc_mode('pulse') # generate pulse pattern

        data={}
        for ch in channels:
            d = np.zeros((32, 3), dtype=np.uint8)
            self.log.info('Reading channel %i.' % (ch))
            adcdaq = self.ANT[ch].ADCDAQ

            for dly in range(32):
                adcdaq.set_delay((dly, None))
                d[dly, :] = self.ANT[ch].ADCDAQ.get_pattern(period=11)[offset[ch]:offset[ch] + 3];
            data[ch] = d
        self.set_adc_delays(old_delays) # restore original delays before the function was called
        self.set_adc_mode(old_adc_mode)
        return data

    def compute_adc_delays(self, channels=[0], offset=[2,3,3,3,3,3,3,3]):
        """
        Measures the eye diagram of the ADC digital data lines and computes the optimum delays to ensure reliable data acquisition.
        """

        current_delay = self.get_adc_delays()
        data = self.read_eye_diagram(channels, offset=offset)
        n = np.zeros((8, 3), dtype=np.uint8)
        delays={}

        for ch in channels:
            for bit in range(8):
                mask = 1 << bit
                n[bit, :] = np.sum((data[ch] & mask) / mask, axis=0)
            #self.log.info('n is ', n)

            n_min = np.min(n, axis=0) # minimum number of delay values that allowed the pulse in each slot
            N = np.argmax(n_min) # slot with the maximum number of possible delays for all bits
            N = 1
            self.log.info('Aligning bits on sample #%i' % N)

            self.log.info('CHANNEL %i' % ch)
            computed_delay = np.zeros(8, dtype=np.uint8)
            for bit_number in range(8):
                mask = 1 << bit_number
                d = (data[ch][:, 0] & mask) / mask
                computed_delay[bit_number] = np.sum(d*range(32)) / np.sum(d)
                bit_string = ''
                for delay in range(len(d)):
                    if delay == current_delay[bit_number]:
                        bit_string += 'X'
                    elif delay == computed_delay[bit_number]:
                        bit_string += '!O'[d[delay]]
                    else:
                        bit_string += '.#'[d[delay]]

                self.log.info('Bit %i: %s Delay = %2i' % (bit_number, bit_string, computed_delay[bit_number]))

            delays[ch]=computed_delay
        return delays

    compute_delays = compute_adc_delays # For legacy software compatibility

    def status(self):
        self.log.info('----------- chFPGA status ---------------')
        self.log.info(' Controller IP address: %s, port: %i ' % (self.sock.ip_address, self.sock.port_number))
        self.log.info(' Firmware version: %s' % self.get_version())
        self.log.info(' Number of antenna inputs: %i' %  self.NUMBER_OF_ANTENNAS)
        self.log.info(' Number of antennas with channelizers: %i (antennas %s)' % (len(self.LIST_OF_ANTENNAS_WITH_FFT), str(self.LIST_OF_ANTENNAS_WITH_FFT)))
        self.log.info(' Number of correlators: %i (correlators %s)' % (len(self.LIST_OF_IMPLEMENTED_CORRELATORS),str(self.LIST_OF_IMPLEMENTED_CORRELATORS)))

        self.FreqCtr.status()


    def set_gain(self, log2_gain=0, channels=None):
        """
        Sets that gain of the scalar module. The convention for log2gain is that if log2gain=0 the FFT of 1 gives 1 at DC. The range of log2gain is -1 to 14

        History:
            2012-11-28 JM: Added this function
        """

        if channels is None:
            channels = self.default_channels

        for ant in self.ANT:
            if ant.ant_number in channels:
                self.log.info('Setting gain of Antenna %i' % ant.ant_number)
                ant.SCALER.SHIFT_LEFT = 1 + log2_gain

    def get_gain(self):
        """
        Returns the log2 SCALER gain each antenna. 
        """
        return [ant.SCALER.SHIFT_LEFT-1 for ant in self.ANT]


    def set_fft_shift(self, fft_shift=0b11111111111, channels=None):
        """
        Sets the FFT shift schedule for the FFT.  Each bit represents a divide by 2 for that stage of the FFT.  Default is to shift every stage.  11 stage FFT, so default is 2**11-1.
        expects a number  in the range 0b11111111111 (2047) and 0b00000000000 (0).  

        History:
            2013-02-19 KMB: Added this function
        """

        if channels is None:
            channels = self.default_channels

        for ant in self.ANT:
            if ant.ant_number in channels:
                self.log.info('Setting FFT shift of antenna %i' % ant.ant_number)
                ant.FFT.FFT_SHIFT = fft_shift

    set_FFT_shift = set_fft_shift  # For legacy code compatibility

    def get_fft_shift(self):
        """
        Returns the FFT shift schedule for each antenna. 
        """
        return [ant.FFT.FFT_SHIFT for ant in self.ANT]

    get_FFT_shift = get_fft_shift # for legacy compatibility

    def check_adc_data_acquisition(self, test_duration = 1):
        """
        Sets the ADC in ramp mode and compare the incoming ramp in real time with an internally generated ramp to combute the total number of words in error (and an error count for each bit)
        """
        old_adc_mode = self.get_adc_mode()
        self.set_adc_mode('ramp')
        self.sync() # sync the board to make sure that data acquisition starts on the right ramp sample

        # Clear the word and bit error counters
        for ant in self.ANT:
            print 'Clearing antenna', ant.ant_number
            ant.ADCDAQ.RAMP_ERR_CLEAR=0
            ant.ADCDAQ.RAMP_ERR_CLEAR=1
        self.log.info('Measuring the data acquisition error rate over %0.1f seconds...' % test_duration)
        t0 = time.time();
        word_error = np.zeros(len(self.ANT))
        bit_error = np.zeros((len(self.ANT), 8))
        try:
            while time.time() - t0 <= test_duration: 
                for (i, ant) in enumerate(self.ANT):
                    print  self.ANT[i].ADCDAQ.RAMP_ERR_CTR,
                    word_error[i] += ant.ADCDAQ.RAMP_ERR_CTR
                    for bit_number in range(8):
                        bit_error[i, bit_number] += ((ant.ADCDAQ.BIT_ERR_CTR >> (bit_number*4)) & 0x0F)
                    ant.ADCDAQ.RAMP_ERR_CLEAR = 0
                    ant.ADCDAQ.RAMP_ERR_CLEAR = 1
                    # self.log.info('CH%i: %3i (%08X)' % (ant.ant_number, ant.ADCDAQ.RAMP_ERR_CTR, ant.ADCDAQ.BIT_ERR_CTR))
        except KeyboardInterrupt:
            pass

        for (i, ant) in enumerate(self.ANT):
            self.log.info('CH%i: %5i word errors, bit errors (7:0) = (%s)' % (ant.ant_number, word_error[i], ','.join('%3i' % e for e in bit_error[i,::-1])))
        total_word_errors = np.sum(word_error)
        self.log.info('There were %i word errors in total' % total_word_errors)
#        self.set_adc_mode(old_adc_mode)
        return total_word_errors

    def test_speed(self, n=1000):
        t0 = time.time()
        for i in xrange(n):
            try:
                self.get_fpga_cookie()
            except:
                print 'error on transaction #%i' % i
        t1 = time.time()
        print '%i read operations performed in %.2f s (%.0f read/s)' % (n, t1 - t0, float(n)/(t1 - t0))
