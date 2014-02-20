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
import socket #needed for inet_aton
import struct

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
import CROSSBAR
import CH_DIST    # Included only so it can be reloaded
import ACC # Included only so it can be reloaded

import GPU

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
        CROSSBAR,
        GPU,
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
    logger = logging.getLogger('chFPGAException')
    def __init__(self, message):
        super(self.__class__, self).__init__(message)
        self.logger.exception(message)


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
    IMPLEMENT_CORR = False
    ADC_CLK_SELECT = 1 # Antenna number from which the antenna processing will be clocked. This is hardwired in the firmware (need to use an ADCDAQ with a PLL)    
    #SAMPLING_FREQUENCY = 800e6 # in Hz
    #REFERENCE_FREQUENCY = 10e6 # in Hz
    SYSTEM_CLOCK_FREQUENCY = 200e6 # in Hz
    FRAME_HEADER_LENGTH = 9
    #FRAME_PERIOD = float(FRAME_LENGTH)/SAMPLING_FREQUENCY

    # Set the basic paramaters used to compute the address of each module
    SYSTEM_BASE_ADDR   = 0x00000 # This is always at zero so we can gather info from the FPGA before we know the number of antennas etc.
    CHAN_BASE_ADDR     = 0x20000 # Channelizer top address
    CROSSBAR_BASE_ADDR  = 0x40000 # CROSSBAR top address
    GPU_LINK_BASE_ADDR = 0x60000 # GPU Link top address
    CORR_BASE_ADDR     = 0x80000 # Correlator ports are determined dynamically based on the info from the firmware
    #MGT_PORT = NUMBER_OF_ANTENNAS+2 -- for future use, if needed

    CHAN_ADDR_INCREMENT           = 0x02000 # Address increment between each channelizer address spaces
    CROSSBAR_ADDR_INCREMENT        = 0x02000
    GPU_LINK_ADDR_INCREMENT       = 0x02000 # Address increment between each subsystem of the GPU links
    CORR_ADDR_INCREMENT           = 0x02000 # Address increment between each correlator

    # Build the memory map for every module of the system ( work in progress)
    MEMORY_MAP = {}
    MEMORY_MAP.update( ('SYSTEM/%s' % (module_name)                , 0x00000 + i * 0x02000                           ) for (i, module_name) in enumerate(['GPIO', 'SYSMON', 'FREQ_CTR', 'SPI', 'REFCLK', 'I2C']))
    MEMORY_MAP.update( ('CHAN%i/%s' % (channel_number, module_name), 0x20000 + channel_number * 0x02000 + module_number * 0x00400) for (module_number, module_name) in enumerate(['ADCDAQ','SRCSEL','FFT', 'SCALER', 'PROBER', 'FUNCGEN', 'INJECT']) for channel_number in range(16))


    # SYSTEM Modules addresses
    SYSTEM_GPIO_BASE_ADDR     = SYSTEM_BASE_ADDR + 0x00000
    SYSTEM_SYSMON_BASE_ADDR   = SYSTEM_BASE_ADDR + 0x02000
    SYSTEM_FREQ_CTR_BASE_ADDR = SYSTEM_BASE_ADDR + 0x04000
    SYSTEM_SPI_BASE_ADDR      = SYSTEM_BASE_ADDR + 0x06000
    SYSTEM_REFCLK_BASE_ADDR   = SYSTEM_BASE_ADDR + 0x08000
    SYSTEM_I2C_BASE_ADDR      = SYSTEM_BASE_ADDR + 0x0A000

    GPIO_COOKIE_REG = 0x080 # Register address of the firmware cookie
    GPIO_IPCONFIG_REG = 0x08D # Register address of the first byte of the IP config word
    CHFPGA_COOKIE = 0x42 # Expected cookie value for chFPGA

    PLATFORM_ID_ML605 = 0
    PLATFORM_ID_KC705 = 1
    PLATFORM_ID_MGK7MB_REV0 = 2
    PLATFORM_ID_MGK7MB_REV2 = 3

    PLATFORM_ID_LIST = {
        # ID: ( Board name, class to instantiate)
        PLATFORM_ID_ML605: ('Virtex 6 (XC6V240T-1 FFG1156) on Xilinx ML605 Evaluation board', None),
        PLATFORM_ID_KC705: ('Kintex 7 (XC7K325T-2 FFG900C) on Xilinx KC705 Evaluation board', None),
        PLATFORM_ID_MGK7MB_REV0: ('Kintex 7 (XC7K420T-2 FFG901) on McGill MGK7MB / ICEBoard Rev0', mgk7mb.MGK7MB),
        PLATFORM_ID_MGK7MB_REV2: ('Kintex 7 (XC7K420T-2 FFG901) on McGill MGK7MB / ICEBoard Rev2', mgk7mb.MGK7MB),
    }

    def __init__(self, ip_address='10.10.10.11', port_number=41000, init=1, verbose=0, host_ip=None, **kwargs):
        """
        Opens communication with the specified chFPGA. This does not affect the state and operations of chFPGA.
        """
        # Initialize instance attributes
        # For now, we do not know their values unless the system is initialized. 
        # We may want to fix that by reading the FPGA states and determining those values. 
        self.sampling_frequency = None
        self.reference_frequency = None
        self.FRAME_PERIOD = None
        self.FMC_present = []  # indicates if the FMC board is present. If not, the modules will act accordingly.
        self.ip_address = ip_address # store the IP address so we can use it to delete the shared_variable
        self.port_number = port_number

        self.log = logging.getLogger(__name__)

        self.motherboard = None
        self.adc_board = []
        self.fpga = None
        self.last_init_time = None
        # self.log.info("Creating chfpga_controller object ")

        self.log.info("=== Opening control communication sockets to FPGA at %s:%i." % (ip_address, port_number))

        # Close the socket open by a previous instance
        if ip_address in Shared_variables.controller_sock:
            self.log.info('   Closing the socket open in a previous instance ' +
                          'for IP address %s' % ip_address)
            Shared_variables.controller_sock[ip_address].close()
            del Shared_variables.controller_sock[ip_address]

        # # Set the IP address and port
        # self.fpga = SocketIO.ControlSocket_base('10.10.10.11', 41000)
        # ip_bytes = socket.inet_aton(ip_address) # converts the IP address as a string of 4 bytes
        # ip_word = struct.unpack('>L', ip_bytes)[0] # convert IP into a 32 bit word
        # ipconfig_word = np.uint32( ((ip_word & 0xFFFF) << 16) | (port_number & 0xFFFF) )
        # self.log.info('Setting IPCONFIG word to 0x%08X' % ipconfig_word)
        # self.write(self.SYSTEM_PORT, self.SYSTEM_GPIO_MODULE, self.GPIO_IPCONFIG_REG, ipconfig_word)
        # self.fpga.close()



        # Create socket handled and open socket communications to the chFPGA board
        self.fpga = SocketIO.ControlSocket_base(ip_address, port_number, host_ip=host_ip)
        Shared_variables.controller_sock[ip_address] = self.fpga # Save the socket in a persistent storage so it can be closed if needed  

        # provide access to the FPGA read/write methods directly from this chFPGA object 
        self.read = self.fpga.read
        self.write = self.fpga.write

        if init < 0: # If init<0, we do not perform any communication with the FPGA, so we don't read the firmware configuration
            self.log.info('Upon user request (init < 0), communication with the FPGA are inhibited. Initialization sequence stops here. Use this for debug only.')
            return

        self.log.info("   Attempting to communicate with the FPGA")

        #self.fpga.open(fpga_serial_number, ) # Open communication socket with the fpga with specified serial number and assign it the specified ip

        self.fpga.open() # Open communication socket with the fpga

        try:
            cookie = self.read(self.SYSTEM_GPIO_BASE_ADDR + self.GPIO_COOKIE_REG) # Read anything from the GPIO subsystem (which is always present on all versions of the FPGA)
        except Exception as e:
            error_message = "   Unable to communicate with the FPGA at address %s:%i due to the following exception: %s" % (ip_address, port_number, repr(e))
            self.close()
            raise chFPGAException(error_message)

        self.log.info("   Contact with the FPGA established")

        if cookie != self.CHFPGA_COOKIE:
            error_message = '   The firmware at %s:%i is not chFPGA. The magic cookie returned by the FPGA is 0x%02X, whereas we expected 0x%02X' % (ip_address, port_number, cookie, self.CHFPGA_COOKIE)
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

            if verbose >= 2: self.log.debug('=== Instantiating GPIO')
            self.GPIO = GPIO.GPIO_base(self, self.SYSTEM_GPIO_BASE_ADDR)
            # get system constants from the FPGA

            self.log.info('=== Getting board info information')

            self.PLATFORM_ID = self.GPIO.PLATFORM_ID
            if self.PLATFORM_ID not in self.PLATFORM_ID_LIST:
                raise chFPGAException('Platform ID 0x%02X is not recognized' % self.PLATFORM_ID)
            self.NUMBER_OF_FMC_SLOTS = None

            # Get frame size info
            self.LOG2_FRAME_LENGTH = self.GPIO.LOG2_FRAME_LENGTH
            self.FRAME_LENGTH = 2**self.LOG2_FRAME_LENGTH # 2**11 = 2048 time samples per frame
            self.NUMBER_OF_FREQUENCY_BINS = self.FRAME_LENGTH/2 # 1024 frequency bins per frame

            # Identify the number of channelizers and their properties
            self.CHANNELIZERS_CLOCK_SOURCE = self.GPIO.CHANNELIZERS_CLOCK_SOURCE 
            self.NUMBER_OF_ANTENNAS = self.GPIO.NUMBER_OF_CHANNELIZERS
            self.NUMBER_OF_ANTENNAS_WITH_FFT = self.GPIO.NUMBER_OF_CHANNELIZERS_WITH_FFT
            self.LIST_OF_ANTENNAS_WITH_FFT = range(self.NUMBER_OF_ANTENNAS_WITH_FFT)

            # if self.NUMBER_OF_ANTENNAS == 0:
            #     self.NUMBER_OF_ANTENNAS = 16

            # Get crossbar configuration
            self.NUMBER_OF_CROSSBAR_INPUTS = self.GPIO.NUMBER_OF_CROSSBAR_INPUTS
            self.NUMBER_OF_CROSSBAR_OUTPUTS = self.GPIO.NUMBER_OF_CROSSBAR_OUTPUTS

            # Get GPU link configuration
            self.NUMBER_OF_GPU_LINKS = self.GPIO.NUMBER_OF_GPU_LINKS

            # Get correlator info and their properties
            self.NUMBER_OF_CORRELATORS_MAX = self.GPIO.NUMBER_OF_CORRELATORS
            self.NUMBER_OF_CORRELATORS = self.GPIO.NUMBER_OF_CORRELATORS
            #self.LIST_OF_IMPLEMENTED_CORRELATORS = [i for i in range(8) if bool(self.GPIO.IMPLEMENT_CORR & 2**i) and i<self.NUMBER_OF_CORRELATORS_MAX]
            self.LIST_OF_IMPLEMENTED_CORRELATORS = range(self.NUMBER_OF_CORRELATORS)
#            self.NUMBER_OF_CORRELATORS = len(self.LIST_OF_IMPLEMENTED_CORRELATORS)
            self.NUMBER_OF_ANTENNAS_TO_CORRELATE = self.GPIO.NUMBER_OF_CHANNELIZERS_TO_CORRELATE

            # ANT_BASE_PORT = 1
            # CORR_BASE_PORT = ANT_BASE_PORT + self.NUMBER_OF_ANTENNAS
            # GPU_BASE_PORT = CORR_BASE_PORT + self.NUMBER_OF_CORRELATORS

            # self.ANT_PORT =  range(ANT_BASE_PORT, ANT_BASE_PORT + self.NUMBER_OF_ANTENNAS) # Antennas are ports 0-7
            # self.CORR_PORT = range(CORR_BASE_PORT, CORR_BASE_PORT +  self.NUMBER_OF_CORRELATORS)
            # self.GPU_PORT = range(GPU_BASE_PORT, GPU_BASE_PORT +  1)
            self.default_channels = range(self.NUMBER_OF_ANTENNAS)
            #self.LIST_OF_ANTENNAS_WITH_FFT = [i for i in range(8) if bool(self.GPIO.IMPLEMENT_FFT & 2**i)]


            self.log.info('   Hardware platform: %s' % self.PLATFORM_ID_LIST[self.PLATFORM_ID][0])
            self.log.info('   Firmware timestamp: %s' % self.get_version())
            self.log.info('   Number of channelizers: %i' %  self.NUMBER_OF_ANTENNAS)
            self.log.info('   Number of channelizers with FFT: %i (antennas %s)' % (len(self.LIST_OF_ANTENNAS_WITH_FFT), str(self.LIST_OF_ANTENNAS_WITH_FFT)))
            self.log.info('   Crossbar configuration: %i inputs x %i outputs' % (self.NUMBER_OF_CROSSBAR_INPUTS, self.NUMBER_OF_CROSSBAR_OUTPUTS))
            self.log.info('   Number of correlators: %i (correlators %s)' % (len(self.LIST_OF_IMPLEMENTED_CORRELATORS),str(self.LIST_OF_IMPLEMENTED_CORRELATORS)))
            self.log.info('   Number of channelizers supported by the correlators: %i ' % (self.NUMBER_OF_ANTENNAS_TO_CORRELATE))
 
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
                       
            self.log.info('=== Instantiating FPGA ressources')

            self.log.debug('=== Instantiating I2C')
            self.fpga_I2C = I2C.I2C_base(self, self.SYSTEM_I2C_BASE_ADDR)

            self.log.debug('=== Instantiating SYSMON')
            self.SYSMON = SYSMON.SYSMON_base(self, self.SYSTEM_SYSMON_BASE_ADDR)

            self.log.debug('=== Instantiating SPI')
            self.SPI = SPI.SPI_base(self, self.SYSTEM_SPI_BASE_ADDR)

            self.log.debug('=== Instantiating FreqCtr')
            self.FreqCtr = FreqCtr.FreqCtr_base(self, self.SYSTEM_FREQ_CTR_BASE_ADDR)

            self.log.debug('=== Instantiating REFCLK')
            self.REFCLK = REFCLK.REFCLK_base(self, self.SYSTEM_REFCLK_BASE_ADDR)
            
            self.log.debug('=== Instantiating CHAN')
            self.ANT = ANT.ANT_base(self, self.CHAN_BASE_ADDR, self.CHAN_ADDR_INCREMENT) # Antenna processors (ADCDAQ, SRCSEL, FFT, SCALER) for each input
            self.ANT_FMC_NUMBER = [i//8 for i in range(self.NUMBER_OF_ANTENNAS)]

            self.log.debug('=== Instantiating CROSSBAR')
            self.CROSSBAR = CROSSBAR.CROSSBAR_base(self, self.CROSSBAR_BASE_ADDR, self.CROSSBAR_ADDR_INCREMENT) # CROSSBAR block
    
            self.log.debug('=== Instantiating CORR')
            self.CORR = CORR_BLOCK.CORR_BLOCK_base(self, self.CORR_BASE_ADDR, self.CORR_ADDR_INCREMENT) # Correlator (XMUL, ACC) for each correlator

            self.log.debug('=== Instantiating GPU LINKS')
            self.GPU = GPU.GPU_base(self, self.GPU_LINK_BASE_ADDR, self.GPU_LINK_ADDR_INCREMENT) 

            # Now that the firmware ressources are initialized, print more configuration info that requires access to these ressources
            self.log.debug('      Data width is currently (Re+Im) = (%i+%i) bits (it might change later during initialization)' % (self.get_data_width(),self.get_data_width()))

            # ---------------------------------------------------------------------
            # -- Create motherboard ressource handlers objects
            # ---------------------------------------------------------------------

            self.log.info('=== Instantiating motherboard ressources handlers')
            motherboard_cls = self.PLATFORM_ID_LIST[self.PLATFORM_ID][1]
            self.motherboard = motherboard_cls(self) # Creates the motherboard handler

            self.NUMBER_OF_FMC_SLOTS = self.motherboard.get_number_of_fmc_slots()
            self.log.info('   This motherboard has %i FMC slots' % self.NUMBER_OF_FMC_SLOTS)
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
            self.log.info('=== Instantiating FMC ressource handlers')
            for fmc_number in range(self.NUMBER_OF_FMC_SLOTS):
                fmc_name = ['FMCA', 'FMCB'][fmc_number]
                self.log.debug('   Instantiating FMC #%i (%s)' % (fmc_number, fmc_name))
                self.adc_board.append(MGADC08.MGADC08_base(self, fmc_number, fmc_name, verbose = verbose))
                # Determine if the ADC board is present
                # The 3.3V supply powering the EEPROM is always on, so we can determing what FMC board is present before we power the board
                self.FMC_present.append(self.adc_board[fmc_number].is_present()) 
                if self.FMC_present[fmc_number]:
                    self.log.info('   An MGADC08 ADC Board is present on FMC slot %i' % (fmc_number))
                else:
                    self.log.warning('   An MGADC08 ADC Board is *not* present of FMC slot %i' % fmc_number)

            # Determine if the FMC board corresponding to each channelizer is present
            self.ANT_FMC_IS_PRESENT = [self.adc_board[self.ANT_FMC_NUMBER[i]].is_present() for i in range(self.NUMBER_OF_ANTENNAS)]

        except Exception as e:
            self.close()
            raise chFPGAException('An exception has occured during module instantiation. Sockets will be closed. The exception is %s' % repr(e))

            # Initialize subsystems. This has to be done only once all subsystems are created because some subsystems depend on each other.
        if init > 0:
            try:
                self.init(**kwargs)
            except Exception as e:
                self.close()
                raise chFPGAException('An exception has occured during module initialization. Sockets will be closed. The exception is %s' % repr(e))

    def __del__(self):

        self.close()
        self.log.debug('__del__: Closed FPGA at IP address %s' % \
                       self.fpga.ip_address)

    def init(self, sampling_frequency=800e6, reference_frequency=10e6, adc_delay_table=None, data_width=8, group_frames = 4, enable_gpu_link =0, verbose=0, **kwargs):
        """
        Resets the chFPGA to a known state with specified parameters.
        """

        for (key,value) in kwargs.items():
            self.log.warning('Unknown arguments %s=%s. Ignoring.' % (key, repr(value)))

        self.sampling_frequency = sampling_frequency
        self.reference_frequency = reference_frequency
        self.FRAME_PERIOD = float(self.FRAME_LENGTH)/self.sampling_frequency

        self.log.info('--- Initializing FPGA ressources')

        self.log.debug('--- Initializing GPIO')
        self.GPIO.init() # This stops the antenna procesors from sending data. Neeeded if the FPGA is flooding the buffers which prevent subsequent reads to come through
        self.GPIO.BUCK_PHASE=0xfedcba9876543210 # debug
        #self.fpga.flush_data_socket() # Now the the data stops coming, flush the buffers
        self.fpga.flush()
        if verbose >= 2: 
            self.GPIO.status()


        self.log.debug('--- Initializing I2C')
        self.fpga_I2C.init()

        # if verbose >= 2: self.log.debug('--- Initializing ML605 LCD')
        # self.LCD.init()
        # self.LCD.write('CHIME FW Version', col=0, row=0)
        # self.LCD.write('%s' % self.GPIO.get_bitstream_date(), col=0, row=1)

        # if verbose >= 2: self.log.debug('--- Initializing ML605 PMBus')
        # self.ML605_PMBus.init()
        # if verbose >= 2: self.ML605_PMBus.status()



         # Module depend on the FMC_present flag after this point

        self.log.debug('--- Initializing REFCLK')
        self.REFCLK.init()
        self.REFCLK.status()

        #Only do for ML605, not KC705 board
        self.log.debug('--- Initializing SYSMON')
        self.SYSMON.init()
        self.SYSMON.status()

        self.log.debug('--- Initializing SPI')
        self.SPI.init()
        self.SPI.status()

        self.log.info('--- Initializing FMC slots')

        for fmc in self.adc_board:
            if fmc.is_present():
                self.log.debug('   Powering up FMC%i', fmc.fmc_number)
                fmc.set_power(True)
                time.sleep(0.2) # Give it some time for the power to stabilize
                # We need to initialize the ADC board befor we initialize ANT (and its data acquisition) because the delay blocks need a clock
                self.log.debug('   Initializing FMC%i', fmc.fmc_number)
                fmc.init(sampling_frequency = sampling_frequency, reference_frequency=reference_frequency)
                fmc.status()
            else:
                self.log.debug('   Skipping FMC%i initialization since no board is present in that slot', fmc.fmc_number)

        self.sync() # might be needed  to make sure that the clock is running to set delays


#        self.FMC_present = self.adc_board[0].is_present()
        self.log.debug('=== Initializing Channelizers')
        self.ANT.init(delay_table=adc_delay_table, fmc_present = self.ANT_FMC_IS_PRESENT)
        self.ANT.status()

        self.log.debug('=== Initializing Crossbar')
        if self.NUMBER_OF_CROSSBAR_OUTPUTS>0:
            self.log.debug('  - CROSSBAR')
            self.CROSSBAR.init()
            self.CROSSBAR.status()
        else:
            self.log.warning("There are no CROSSBAR blocks in this firmware build (so there can't be data streamed to the correlators or GPU links!)");

        self.log.debug('=== Initializing FPGA correlators')
        if self.NUMBER_OF_CORRELATORS>0:
            self.log.debug('  - CORR')
            self.CORR.init()
            self.CORR.status()
        else:
            self.log.info('There are no FPGA correlators in this firmware build');

        self.set_data_width(data_width)  #sets the data width of both the SCALER and CROSSBAR
        self.log.info('Data width set to (Re+Im) = (%i+%i) bits' % (self.get_data_width(), self.get_data_width()))

        self.CROSSBAR.set_frame_grouping(group_frames)
        self.log.info('%i frames will be grouped to form the GPU/FPGA correlator streams' % (group_frames))

        self.GPU.set_enable(enable_gpu_link)

        self.CROSSBAR.configure()
        self.log.info('GPU link is currently %s' % (['Disabled','Enabled'][bool(enable_gpu_link)]))

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
        
        # self.log.info("Setting default data source")
        # self.set_funcgen_function('ramp')
        # self.set_data_source('funcgen')
        # self.set_ADC_mode('data') # This implies a self.sync(), which will reset the antenna processors again to ensure data alignment
        # self.set_data_source('adc')

        self.log.info("End of chFPGA initialization.")

        self.last_init_time = time.time()

    def get_fpga_cookie(self):
        """
        Reads the FPGA and returns the cookie that identifies the firmware.
        This method can be called before any FPGA modules are instatiated. 
        """
        return self.read(self.SYSTEM_GPIO_BASE_ADDR + self.GPIO_COOKIE_REG) & 0x7F

    def get_config(self):
        config = chFPGA_config() # Create empty config container
        # Add configuration parameters

        config.config_protocol_version = (1,0)
        config.config_capture_time = time.time()
        config.system_firmware_version = self.get_version()
        config.system_platform_id = self.PLATFORM_ID
        config.system_ip_address = self.ip_address
        config.system_base_port_number = self.port_number
        config.system_data_port_number = self.port_number + self.GPIO.DATA_IP_PORT_OFFSET
        config.system_corr_port_number = self.port_number + self.GPIO.CORR_IP_PORT_OFFSET


        config.number_of_antennas = self.NUMBER_OF_ANTENNAS
        config.system_list_of_antennas_with_channelizers = self.LIST_OF_ANTENNAS_WITH_FFT

        config.number_of_correlators_max = self.NUMBER_OF_CORRELATORS_MAX
        config.number_of_correlators = self.NUMBER_OF_CORRELATORS
        config.number_of_antennas_to_correlate = self.NUMBER_OF_ANTENNAS_TO_CORRELATE
        config.system_list_of_implemented_correlators = self.LIST_OF_IMPLEMENTED_CORRELATORS

        config.system_frame_length = self.FRAME_LENGTH
        config.system_sampling_frequency = self.sampling_frequency
        config.system_reference_frequency = self.reference_frequency
        config.system_frame_period = self.FRAME_PERIOD

        config.adc_board_is_present = self.adc_board[0].is_present()
        if self.adc_board[0].is_present():
            config.adc_board_temperature = self.adc_board[0].AmbTemp.temperature
            config.adc_board_adc_chip_temperature = [adc.get_temperature() for adc in self.adc_board[0].ADC]
        config.antenna_data_source = self.get_data_source()
        config.antenna_fft_bypass = self.get_FFT_bypass()
        config.antenna_fft_shift_schedule = self.get_FFT_shift()
        config.antenna_scaler_log2_gain = self.get_gain()
        config.antenna_adc_data_acquisition_delay_tables  = self.ANT.get_delays()
        config.FPGA_board_frequency = self.FreqCtr.read_frequency('CLK200', gate_time=0.05)
        config.CTRL_clock_frequency = self.FreqCtr.read_frequency('CTRL_CLK', gate_time=0.05)
        config.ant_clock = self.FreqCtr.read_frequency('ANT_CLK', gate_time=0.05)
        if self.IMPLEMENT_CORR:
            config.correlator_clock = self.FreqCtr.read_frequency('CORR_CLK', gate_time=0.05)
            config.correlator_capture_period_in_frames = [corr.ACC.CAPTURE_PERIOD for corr in self.CORR]
            config.correlator_integration_period_in_frames = [corr.ACC.INTEGRATION_PERIOD for corr in self.CORR]
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
        self.fpga.close()
        if self.ip_address in Shared_variables.controller_sock:
            del Shared_variables.controller_sock[self.ip_address]

    # Define Read and Write for legacy compatibility
    # Read = read
    # Write = write

    def read_bit(self, addr, bit):
        return (self.read(addr) & (1 << bit)) != 0

    def write_bit(self, addr, bit, data):
        old_data = self.read(addr)
        mask = 1 << bit
        self.write(addr, (old_data & (~mask)) | (mask if data else 0))

    def write_mask(self, addr, mask, data):
        old_data = self.read(addr)
        self.write(addr, (old_data & (~mask)) | (mask & data))

    def pulse_bit(self, addr, bit):
        old_data = self.read(addr)
        mask = 1 << bit
        self.write(addr, (old_data | mask))
        self.write(addr, (old_data & (~mask)))

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

    
    def set_channelizer_config(self, data_source=None, function=None, a=1, b=0, adc_mode='data', adcdaq_mode='data', fft_bypass=None, fft_shift=None, scaler_bypass=None, gain=None, postscaler=None, channels=None):
        """
            Single command used to set multiple channelizer settings. The data processing chain is:
            ADC --> ADCDAQ --> |        |
                   FUNCGEN --> | SRCSEL | --> FFT --> SCALER
                    INJECT --> |        |
        """
        if data_source is not None:
            self.set_data_source(data_source, channels=channels)

        if function is not None:
            self.set_funcgen_function(function=function, a=a, b=b, channels=channels)

        if adcdaq_mode is not None:
            self.set_adcdaq_mode(mode=adcdaq_mode, channels=channels)

        if fft_bypass is not None:
            self.set_fft_bypass(bypass_mode=fft_bypass, channels=channels)

        if fft_shift is not None:
            self.set_fft_shift(fft_shift, channels=channels)

        if gain is not None:
            self.set_gain(gain = gain, postscaler = postscaler, channels=channels)

        if adc_mode is not None:
            self.set_adc_mode(mode=adc_mode)

    set_data_path = set_channelizer_config # for legacy compatibility

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
        return [ant.SRCSEL.get_data_source() for ant in self.ANT.values()]        


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

    def get_adc_board(self, channel):
        """
        Returns the ADC board object that is associated with the specified antenna channel.
        If channel is a list, returns a list of unique board objects associated with the specified channels.
        """

        if isinstance(channel, int):
            channel = [channel]
            board_number = channel // 8
            return self.adc_board[board_number]
        else:
            board_list=[]
            for ch in channel:
                board_number = ch // 8
                board_list.append(self.adc_board[board_number]) 
            return list(set(board_list))


    ADC_MODE_NAMES = {
        # name, mode number, period (in 4-bytes words)
        'data' : (0, 64), # ADC sends analog data
        'ramp' : (1, 64), # ADC sends ramp from 0 to 255
        'pulse': (2, 11), # ADC sends ten 0x00 followed by one 0xff
        }    

    # ADC_MODE_NAMES_REVERSED = util.reverse_dict(ADC_MODE_NAMES)

    def set_adc_mode(self, mode='data', channels=None):
        """
        Sets the operating mode of the all the ADCs, sets the proper CAPTURE period, and sends a SYNC to actuate the change.
        By default, all ADCs on any board handling the specified channels are set to the desired mode. 
        If no channels are specified, the default channel list is used.
        Again: both ADCs on every target board are set, even if we specify channels handled by only one adc chip. 
            mode:
                'data': Normal mode (ADC output contains analog samples)
                'ramp': Ramp mode (ADC output contains repeating 0-255 pattern. Note that ADCDAQ inverts bit 7 during acquisition to convert offset binary to 2's complement binary)
                'pulse': Strobe mode (ADC output contains one 0xFF followed by ten 0x00. It repeats with a pariod of 11. Same comment as above)
        111212 JFC: Added this high-level function with string mode.
        131024 JFC: Implemented multi-board.
        """
        if mode.lower() not in self.ADC_MODE_NAMES:
            raise chFPGAException('Invalid ADC mode %s. Valid modes are %s' % (mode, ', '.join(self.ADC_MODE_NAMES.keys())))
        (mode_value, capture_period) = self.ADC_MODE_NAMES[mode.lower()]

            

        if channels is None:
            channels = self.default_channels

        # Set the mode on all affected ADC boards
        adc_boards = self.get_adc_board(channels)
        for adc_board in adc_boards:
            if not adc_board.is_present():
                self.log.warning('ADC Board of FMC slot #%i (%s) is not present. Ignoring set_ADC_mode() command for this board' % (adc_board.fmc_number, adc_board.fmc_name))
            else:
                adc_board.ADC.set_test_mode(test_mode=mode_value)


        # Set the capture period for all specified channels
        for ch in channels:
            ant = self.ANT[ch]
            ant.ADCDAQ.CAPTURE2_PERIOD = capture_period # set the period so we are ready to capture data correctly after the SYNC resets the CAPTURE logic

        # self.current_ADC_mode = mode_value
        self.sync() # make sure the ADC mode is set and that capture  restarts properly with the right period

    set_ADC_mode = set_adc_mode # For legacy code compatibility

    def get_adc_mode(self):
        """
        Gets the current operating mode of all the ADCs as a string. This assumes all the ADCs are operating in the same mode. If not, an error message will be returned.
        """

        mode_value = []
        # get the ADC mode number for every ADC board
        for adc_board in self.adc_board:
            if adc_board.is_present():
                mode_value.append(adc_board.ADC.get_test_mode())
        mode_value = list(set(mode_value)) # eliminate all duplicates. We should be left with only one mode number.
        if len(mode_value) != 1:
            raise chFPGAException('The ADC chips on the ADC boards are not ALL in the same mode')
        mode_string = [key for (key, info) in self.ADC_MODE_NAMES.items() if info[0]==mode_value[0]][0] # get the name of the first ADC mode that matches the provided number
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
        for ant in self.ANT.values():
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
            
        for ant in self.ANT.values():
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
        Sets the BYPASS flag on both the FFT modules.
        If the list of channels is specified, only these channels will be set.
        All antenna processors are reset to force the FFT to resynchronize to the frame boundaries.

        History:
            2012-08-31 JFC: Added this function
            2012-10-02 JFC: Added antenna reset after bypass change to ensure the FFT is synced.
            2013-12-05 JFC: Changed behavior so only the specified channels are changed.
            2014-02-09 JFC: Removed scaler bypass setting
        """

        if channels is None:
            channels = self.default_channels

        configured_channels = set()
        for ch in channels:
            if ch not in self.ANT:
                self.log.warning('FFT bypass mode on antena channel %i are not set because that channel is not available' % ch)
            elif ch not in self.LIST_OF_ANTENNAS_WITH_FFT:
                self.log.warning('FFT bypass mode on antena channel %i are not set because that channel does not have an FFT module' % ch)
            else:
                self.ANT[ch].FFT.BYPASS = bypass_mode
                configured_channels.add(ch) 
        self.log.info('Setting FFT bypass mode to %s for Antenna %s' % (str(bool(bypass_mode)), ', '.join([str(i) for i in configured_channels])))
        self.reset();
        #self.sync()

    set_FFT_bypass = set_fft_bypass # for legacy code compatibility

    def get_fft_bypass(self):
        """
        Returns a list indicating if the FFT is bypassed or not for each antenna. 
        """
        return [bool(ant.FFT.BYPASS) for ant in self.ANT.values()]

    get_FFT_bypass = get_fft_bypass # for legacy code compatiblity    

    def set_scaler_bypass(self, bypass_mode, channels=None):
        """
        Sets the BYPASS flag on the SCALER modules.
        If the list of channels is specified, only these channels will be set.

        History:
            2013-12-05 JFC: Added this function
        """

        if channels is None:
            channels = self.default_channels

        self.log.info('Setting SCALER bypass mode for Antenna %s' % ', '.join([str(i) for i in channels]))
        for ant in self.ANT.values():
            if ant.ant_number in channels:
                ant.SCALER.BYPASS = bypass_mode
            # else:
            #     self.log.warning('Attemnpting to set SCALER bypass mode for antenna channel %i which is not present on this card' % ch)


    def get_scaler_bypass(self):
        """
        Returns a list indicating if the SCALER is bypassed or not for each antenna. 
        """
        return [bool(ant.SCALER.BYPASS) for ant in self.ANT.values()]


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

        if not self.last_init_time:
            self.log.warning('The system is not initialized. This might not work.')

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
            self.log.info('Disabling correlator %i' %  (corr.instance_number))
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

    def compute_adc_delays(self, channels=[0], offset=[2,3,3,3,3,3,3,3, 4,3,3,3,3,3,3,3]):
        """
        Measures the eye diagram of the ADC digital data lines and computes the optimum delays to ensure reliable data acquisition.
        """

        current_delay = self.get_adc_delays()
        data = self.read_eye_diagram(channels, offset=offset)
        n = np.zeros((16, 3), dtype=np.uint8)
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
        self.log.info(' Controller IP address: %s, port: %i ' % (self.fpga.ip_address, self.fpga.port_number))
        self.log.info(' Firmware version: %s' % self.get_version())
        self.log.info(' Number of antenna inputs: %i' %  self.NUMBER_OF_ANTENNAS)
        self.log.info(' Number of antennas with channelizers: %i (antennas %s)' % (len(self.LIST_OF_ANTENNAS_WITH_FFT), str(self.LIST_OF_ANTENNAS_WITH_FFT)))
        self.log.info(' Number of correlators: %i (correlators %s)' % (len(self.LIST_OF_IMPLEMENTED_CORRELATORS),str(self.LIST_OF_IMPLEMENTED_CORRELATORS)))

        self.FreqCtr.status()

    def set_data_width(self, width):
        """
        Set the number of bits used to represent the values computed by the channelizers and used by the GPU link and FPGA correlators.
        All channelizers, crossbars and correlators are set to the new setting.
        width=4: data is 4 bits Real + 4 bits Imaginary
        width=8: data is 8 bits Real + 8 bits Imaginary
        """

        if width not in (4,8):
            raise chFPGAException('Number of bits %i is invalid. Only 4 or 8 is allowed' % width)

        # Set the channelizer data width
        self.ANT.set_data_width(width)

        # Set the crossbar data width
        self.CROSSBAR.set_data_width(width)

    def get_data_width(self):
        """
        Returns number of bits used to represent the values computed by the channelizers and used by the GPU link and FPGA correlators.
        If all the hardware modules are not set in the same mode, an error is raised.
        """

        # get the channelizer and crossbar data width
        chan_data_width = self.ANT.get_data_width()
        xbar_data_width = self.CROSSBAR.get_data_width()

        if chan_data_width == 8 and xbar_data_width ==8:
            return 8
        elif chan_data_width == 4 and xbar_data_width ==4:
            return 4
        else:
            raise chFPGAException("The channelizers and crossbar are not set to the same data width (chan=%i bits, xbar=%i bits). The data stream won't make much sense" % (chan_data_width, xbar_data_width))

    def configure_crossbar(self):
        self.CROSSBAR.configure()

    def set_gain(self, gain = None, postscaler = None, channels=None, use_fixed_gain = False):
        """
        Sets the gain between the (18+18) bits input of the scaler module (from the FFT) to its 4- or 8- bit scaler output. 
        The gain can be set individually for every frequency bins and every ADC channel.

        A gain consist of a tuple G=(Glin, Glog):
            1) Glin is a linear complex gain which can be unique to each bin.  
               It can be a scalar applied to every bin, or a 1024-point vector to specify a gain for evey bin.
               The real and imaginary part of the linear gain are integer values ranging from -32768 to 32767. 
 
            2) Glog is a binary scaling factor, which is an integer between 0 and 31 representing a power of two that multiplies the linear gain. 
               This is a scalar common to every bin.

        The actual gain between the scaler input and output for bin 'b' is:
           4-bit mode: out/in = Glin(b) * 2**(Glog-31)
           8-bit output: out/in = Glin(b) * 2**(Glog-27)

        G can be specified in the following manner:
           G = Glin              : Sets only the linear gain. Same as (Glin, None)
           G = (Glin, None)      : Same as above
           G = (None, Glog)      : Sets only the postscaler
           G = (Glin, Glog)      : Sets both the linear gain and the postscaler

        The 'gain' parameters can be specified as:
            gain = G: the specified gain is applied only to the ADC channels specified in the list 'channels'. 
            gain = {ch1: G1, ch2: G2 ...} : The gain is applied to specified channels, but only if they are included in 'channels'
            gain = [ (ch1, G1),  (ch2, G2), ...]: Same thing, but in a list format
            gain = [ (ch_list , G1), (ch_list2, G2), ...]: Same thing, but we can apply the gains to lists of channels

        If 'channels' is None, it is applied to the default (active) channels (see set_default_channels()).

        If 'postscaler' is specified, it will be used as default value when Glog = None.

        'use_fixed_gain': if True, enables the use of fixed gain mode of the scaler module. In this case, 'gain' can only be a scalar. Is False by default. This is normally used 

        Notes: 
            1) The PFB/FFT has an intrisic gain of 512 (a constant FFT input of '1' will yield the value 512 in bin 0 at the input of the scaler.
            2) If the FFT is bypassed, the 8-bit values from the ADC or the function generator are applied directly to the scaler input.
            3) In 4-bit mode, the output value is taken from bits 31 to 34 of the postscaled-value. In 8-bit mode, bits 27 to 31 are used. 
            4) A smaller postscaler value allows a larger gain to be used to acheive the same overall gain while providing more gain resolution. 
            A gain of (1, 31) allows the function generator values to appear on the scaler output with an overall gain of 1 in 4-bit mode. This is equivalent to (2, 30), (4,29) ... (16384, 8), except that the latter offers more gain resolution.
            A gain of (1, 27) dies the same in 8-bit mode.
(16384, 8), except that the latter offers more gain resolution.

        Examples:
            set_gain(1) # Sets all gains to 1, leaves the poscslaler unchanged fro all antennas.
            set_gain((1, None)) # Same thing
            set_gain(postscaler = 26) # Sets postscaler on all antennas
            set_gain((1,31)) # For all antennas, sets all gains to 1 and postscaler to 31
            set_gain(16384,8) # In 4-bit, FFT enabled mode, outputs a value of '1' on bin 0 when the input of the FFT is a constant '1'.
            set_gain(np.arange(1024), channels=[1,2,3])
            set_gain({1: 16384, 4: 1300+15000*j, 5: np.arange(1024)}) # sets ADC channels 1-3 to a real gain of 16384, channel 4 to complex gain of (1300+15000j), and channels 5-7 with a gain ramp from 0 to 1023.
        History:
            2012-11-28 JM: Added this function
            2014-02-08 JFC: Rewrote and documented this function for the new scaler supporting complex gain tables.
        """

        # if postscaler is not None:
        #     if postscaler<0 or postscaler>31:
        #         raise chFPGAException('Invalid postscaler value');

        #         if postscaler is not None


        if channels is None:
            channels = self.default_channels


        # Convert to a list of channel-gain tuples
        if isinstance(gain, list):
            pass
        elif isinstance(gain, dict):
            gain = gain.items()
        else: # if anything else including None, a scalar, a gain tuple etc.
            gain = [ (channels, gain) ]


        configured_channels = set()

        for (channel_list, gain_value) in gain:
            # Make sure channel_list is a list (in case we provide a single channel number)
            if isinstance(channel_list, int):
                channel_list = [channel_list]
            # Extratc Glin and Glog from the specified gain value
            if gain_value is None:
                Glin = None
                Glog = None
            elif isinstance(gain_value, tuple):
                Glin = gain_value(0)
                Glog = gain_value(1)
            else: # if a scalar or a vector
                Glin = gain_value
                Glog = None
            # Replace default postscaler value if one is provided
            if (Glog is None) and (postscaler is not None):
                Glog = postscaler


            for ch in channel_list: # process each channel
                if ch not in channels: 
                    continue
                if ch not in self.ANT.keys():
                    self.log.warning('Gains on antenna channel %i are not set because that channel is not available' % ch)
                    continue
                # Set the postscaler value
                if Glog is not None:
                    self.ANT[ch].SCALER.SHIFT_LEFT = Glog

                if use_fixed_gain:
                    if not np.isscalar(Glin):
                        self.chFPGAException('Only scalar gains are allowed when using set_fixed_gain=True.')
                    self.ANT[ch].SCALER.USE_GAIN_TABLE = 0
                    self.ANT[ch].SCALER.set_fixed_gain(Glin)
                else:
                    self.ANT[ch].SCALER.USE_GAIN_TABLE = 1
                    self.ANT[ch].SCALER.set_gain_table(Glin)
                configured_channels.add(ch)
        self.log.info('Setting scaler gains for Antenna %s' % ', '.join([str(i) for i in configured_channels]))

    def get_gain(self):
        """
        Returns the log2 SCALER gain each antenna. 
        """
        return [ant.SCALER.SHIFT_LEFT-1 for ant in self.ANT.values()]

    def set_fmc_power(self, state):
        """
        Enable or disables power on one or both FMCs. 
        If 'state' is an integer or a boolean, all FMCs are set to the target state. 
        If 'state' is a tuple, each element specifies the state of one FMC slot starting from slot 0.
        If 'state' is a dictionary, the FMC slot specified by the key is set to the corresponding value.

        History:
            2013-09-04 JFC: Added this function
        """

        if isinstance(state, (int, bool)):
            for fmc in self.adc_board:
                fmc.set_power(state)
        elif isinstance(state, (tuple, list)):
            for (fmc_number, fmc_state) in enumerate(state):
                self.adc_board[fmc_number].set_power(fmc_state)
        elif isinstance(state, dict):
            for (fmc_number, fmc_state) in state.items():
                self.adc_board[fmc_number].set_power(fmc_state)


    def set_fft_shift(self, fft_shift=0b11111111111, channels=None):
        """
        Sets the FFT shift schedule for the FFT.  Each bit represents a divide by 2 for that stage of the FFT.  Default is to shift every stage.  11 stage FFT, so default is 2**11-1.
        expects a number  in the range 0b11111111111 (2047) and 0b00000000000 (0).  

        History:
            2013-02-19 KMB: Added this function
        """

        if channels is None:
            channels = self.default_channels

        for ant in self.ANT.values():
            if ant.ant_number in channels:
                self.log.info('Setting FFT shift of antenna %i' % ant.ant_number)
                ant.FFT.FFT_SHIFT = fft_shift

    set_FFT_shift = set_fft_shift  # For legacy code compatibility

    def get_fft_shift(self):
        """
        Returns the FFT shift schedule for each antenna. 
        """
        return [ant.FFT.FFT_SHIFT for ant in self.ANT.values()]

    get_FFT_shift = get_fft_shift # for legacy compatibility

    def check_adc_data_acquisition(self, test_duration = 1):
        """
        Sets the ADC in ramp mode and compare the incoming ramp in real time with an internally generated ramp to combute the total number of words in error (and an error count for each bit)
        """
        old_adc_mode = self.get_adc_mode()
        self.set_adc_mode('ramp')
        self.sync() # sync the board to make sure that data acquisition starts on the right ramp sample

        # Clear the word and bit error counters
        for ant in self.ANT.values():
            print 'Clearing antenna', ant.ant_number
            ant.ADCDAQ.RAMP_ERR_CLEAR=0
            ant.ADCDAQ.RAMP_ERR_CLEAR=1
        self.log.info('Measuring the data acquisition error rate over %0.1f seconds...' % test_duration)
        t0 = time.time();
        word_error = np.zeros(len(self.ANT))
        bit_error = np.zeros((len(self.ANT), 8))
        try:
            while time.time() - t0 <= test_duration: 
                for (i, ant) in self.ANT.items():
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

    def test_speed(self, n=1000, timeout=0.1):
        old_timeout = self.fpga.get_timeout()
        self.fpga.set_timeout(timeout)
        t0 = time.time()
        errors = 0
        trials = 0
        for i in xrange(n):
            try:
                trials += 1
                self.get_fpga_cookie()
            except chFPGAException:
                errors += 1
                print 'error on transaction #%i' % i
            except KeyboardInterrupt:
                break
        t1 = time.time()
        self.fpga.set_timeout(old_timeout)
        print '%i read operations performed in %.2f s (%.0f read/s) with %i errors (%0.3f%% errors)' % (trials, t1 - t0, float(n)/(t1 - t0), errors, float(errors)/float(trials)*100)

    def print_memory_map(self):
        import operator
        # map = ['%-20s:0x%05X' % (module_name, addr) for (module_name, addr) in self.MEMORY_MAP.items()]
        sorted_map = sorted(self.MEMORY_MAP.items(), key=operator.itemgetter(1))
        for (module_name, addr) in sorted_map:
            print '0x%05X: %s%-20s' % (addr, '  '*module_name.count('/'), module_name)
