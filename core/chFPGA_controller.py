#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 
# pylint: disable=C0321 

"""
chFPGA.py module 
 Implements interface to the CHIME chFPGA Proof of Concept board
 
 Provided methods:


#
# History:
# 2011-01-10 : JFC : First version
# 2011-04-30 JFC : Modified UDP.py into chFPGA.py to implement higher level communication system
# 2011-04 - 2011-08 JFC : Major modifications & cleanup
# 2011-08-29 JFC: Moved hex to util to solve circular import reference.
# 2012-03-27 JFC: Modified the read and write commands to support the new format following AXI4-Streaming implementation of the command bus
# 2012-05-29 JFC: Cleanup init. Support FMC board detection. Extracted test functions.
    2012-07-xx JFC: Implemented Thread-based frame buffering. Updated frame reading and plotting functions accordingly.
    #2012-07-16 KMB: Started moving plotting/saving functions out to plot_utils.py, and removing redundant programs
"""

import time
#import datetime
#import random
#import sys
#import select
#import struct
#import multiprocessing

import numpy as np
import matplotlib.pyplot as plt
#import pdb

import util
 
import Module

import SocketIO
# hardware subsystems handlers
import SPI
import I2C
import SYSMON
import SYSMOD
import FreqCtr
import REFCLK
import MGT

# SPI device handlers
import ADC
import IOExpander
import ADC_PLL
import AmbTemp
import BiasADC
import MGT_PLL

# I2C device handlers
import FMC_EEPROM
import ML605_PMBus


# Antenna processor handlers
import ANT
import ADCDAQ # Included only so it can be reloaded
import FRAMER # Included only so it can be reloaded
import FFT # Included only so it can be reloaded
import SCALER # Included only so it can be reloaded
import PROBER # Included only so it can be reloaded


# Correlator handlers
import CORR_BLOCK
import CH_DIST    # Included only so it can be reloaded


# -- Module reloader -- 
# Reload modules if we are debugging in case the source code has changed

reload_modules = (util, 
        SocketIO, 
        Module, 
        SPI, 
        I2C, 
        SYSMOD, 
        SYSMON, 
        REFCLK, 
        AmbTemp,
        FreqCtr,
        ADC,
        IOExpander,
        ADC_PLL,
        BiasADC,
        MGT_PLL,
        FMC_EEPROM,
        ML605_PMBus,
        ANT,
        ADCDAQ,
        FRAMER, 
        FFT, 
        SCALER, 
        PROBER, 
        CORR_BLOCK, 
        CH_DIST, 
        MGT
        )
    

for m in reload_modules: 
    print 'Reloading module %s' % (m.__name__)
    reload(m)



# -- chFPGA -- 

    

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
    NUMBER_OF_CORRELATORS = 1
    NUMBER_OF_ANTENNAS = 8
    LOG2_FRAME_LENGTH = 11
    FRAME_LENGTH = 2**LOG2_FRAME_LENGTH # 2**11 = 2048 time samples per frame
    ADC_CLK_SELECT = 1 # Antenna number from which the antenna processing will be clocked. This is hardwired in the firmware (need to use an ADCDAQ with a PLL)    
    #SAMPLING_FREQUENCY = 800e6 # in Hz
    #REFERENCE_FREQUENCY = 10e6 # in Hz
    SYSTEM_CLOCK_FREQUENCY = 200e6 # in Hz
    FRAME_HEADER_LENGTH = 9
    #FRAME_PERIOD = float(FRAME_LENGTH)/SAMPLING_FREQUENCY

    # Port numbers
    ANT_PORT = range(NUMBER_OF_ANTENNAS) # Antennas are ports 0-7
    SYSTEM_PORT = NUMBER_OF_ANTENNAS
    CORR_PORT = range(NUMBER_OF_ANTENNAS+1, NUMBER_OF_ANTENNAS+1+ NUMBER_OF_CORRELATORS)
    #MGT_PORT = NUMBER_OF_ANTENNAS+2 -- for future use, if needed


    # SYSTEM Modules addresses
    SYSTEM_SPI_MODULE = 0
    SYSTEM_SYSMON_MODULE = 1
    SYSTEM_FREQ_CTR_MODULE = 2
    SYSTEM_SYSMOD_MODULE = 3
    SYSTEM_REFCLK_MODULE = 4
    SYSTEM_I2C_MODULE = 5

    def __init__(self, ip_address='10.10.10.11', port_number=41000, sampling_frequency=800e6, reference_frequency=10e6, init=1, adc_delay_table=None, verbose=2):

        self.sampling_frequency = sampling_frequency
        self.reference_frequency = reference_frequency
        self.FRAME_PERIOD = float(self.FRAME_LENGTH)/self.sampling_frequency
        self.FMC_present = False # indicates if the FMC board is present. If not, the modules will act accordingly.

        print '*** Opening control communication sockets ***'
        # Create socket handled and open socket communications to the chFPGA board
        self.sock = SocketIO.ControlSocket_base(ip_address, port_number)

        try: # catch initialization errors so we can free the socket for future instantiation
            print '*** Instantiating modules ***'
            # Create handware handling objects 
            #  NOTE: Does not initialize them yet because some modules are interdependent - we need to wait until all of them are instantiated.
            #  NOTE: The instantiation does not initiate communicattion with the hardware yet. this is done in the INIT phase.
    
    
            if verbose >= 2: print '  - SYSMOD'
            self.SYSMOD = SYSMOD.SYSMOD_base(self)
            if verbose >= 2: print '  - I2C'
            self.I2C = I2C.I2C_base(self)
            if verbose >= 2: print '  - SYSMON'
            self.SYSMON = SYSMON.SYSMON_base(self)
            if verbose >= 2: print '  - SPI'
            self.SPI = SPI.SPI_base(self)
            if verbose >= 2: print '  - FreqCtr'
            self.FreqCtr = FreqCtr.FreqCtr_base(self)
            if verbose >= 2: print '  - REFCLK'
            self.REFCLK = REFCLK.REFCLK_base(self)
    
            #if verbose>=2: print '  - MGT'
            #self.MGT=MGT.MGT_base(self)
    
            if verbose >= 2: print '  - ADC'
            self.ADC = ADC.ADC_base(self)
            if verbose >= 2: print '  - IOExpander'
            self.IOExpander = IOExpander.IOExpander_base(self)
            if verbose >= 2: print '  - ADC_PLL'
            self.ADC_PLL = ADC_PLL.ADC_PLL_base(self)
            if verbose >= 2: print '  - AmbTemp'
            self.AmbTemp = AmbTemp.AmbTemp_base(self)
            if verbose >= 2: print '  - MGT_PLL'
            self.MGT_PLL = MGT_PLL.MGT_PLL_base(self)
            if verbose >= 2: print '  - BiasADC'
            self.BiasADC = BiasADC.BiasADC_base(self)
            if verbose >= 2: print '  - FMC EEPROM'
            self.FMC_EEPROM = FMC_EEPROM.FMC_EEPROM_base(self)
            if verbose >= 2: print '  - ML605 PMBus'
            self.ML605_PMBus = ML605_PMBus.ML605_PMBus_base(self)
    
            if verbose >= 2: print '  - ANT'
            self.ANT = ANT.ANT_base(self)
    
            if verbose >= 2: print '  - CORR'
            self.CORR_BLOCK = CORR_BLOCK.CORR_BLOCK_base(self)
    
            # Initialize subsystems. This has to be done only once all subsystems are created because some subsystems depend on each other.
            if init:
                print '*** Initializing modules ***'
        
                if verbose >= 2: print '  - SYSMOD'
                self.SYSMOD.init() # This stops the antenna procesors from sending data. Neeeded if the FPGA is flooding the buffers which prevent subsequent reads to come through
                #self.sock.flush_data_socket() # Now the the data stops coming, flush the buffers
                self.sock.flush()
                self.SYSMOD.status()
        
                if verbose >= 2: print '  - I2C'
                self.I2C.init()
        
        
                if verbose >= 2: print '  - ML605 PMBus'
                self.ML605_PMBus.init()
                self.ML605_PMBus.status()
        
        
                if verbose >= 2: print '  - EEPROM'
                self.FMC_EEPROM.init()
                self.FMC_EEPROM.status()
        
                self.FMC_present = self.FMC_EEPROM.FMC_present(verbose=True)
        
                 # Module depend on the FMC_present flag after this point
        
                if verbose >= 2: print '  - REFCLK'
                self.REFCLK.init()
                self.REFCLK.status()
        
                if verbose >= 2: print '  - SYSMON'
                self.SYSMON.init()
                self.SYSMON.status()
        
                if verbose >= 2: print '  - SPI'
                self.SPI.init()
                self.SPI.status()
        
                if verbose >= 2: print '  - AmbTemp'
                self.AmbTemp.init()
                self.AmbTemp.status()
        
        
                if verbose >= 2: print '  - IOExpander'
                self.IOExpander.init()
                self.IOExpander.status()
        
                if verbose >= 2: print '  - ADC_PLL'
                self.ADC_PLL.init(fout=2*self.sampling_frequency/1e6, fref=self.reference_frequency/1e6, verbose=1)
                self.ADC_PLL.status()
        
                if verbose >= 2: print '  - ADC'
                self.ADC.init()
                self.ADC.status()
        
                if verbose >= 2: print '  - ANT'
                self.ANT.init(delay_table=adc_delay_table)
                self.ANT.status()
        
                if verbose >= 2: print '  - CORR'
                self.CORR_BLOCK.init()
                self.CORR_BLOCK.status()
        
                # MGT is disabled    
                #print '  - MGT_PLL'
                #self.MGT_PLL.init(fref=fref)
                #print '  - MGT'
                #self.MGT.init() # MGT_PLL must be initialized first
                if verbose >= 2: 
                    print '  - Done with initializations'
    
                #print '*** Setting ADCDAQ delays ***'
        
                #if adc_delay_table:
                #    self.ANT.set_delays(adc_delay_table)
        
                print '*** Set ADC mode ***'
        
                self.set_ADC_mode('data')
                print '*** End of chFPGA initialization ***'
    
        except SocketIO.timeout:
            self.close()
            raise
    

    def __del__(self):

        self.close()
        print '__del__: Closed FPGA at IP address %s' % self.sock.ip_address

    def close(self):
        """ 
        Close chFPGA object, which releases the socket bindings
        """
        self.sock.close()

    def read(self, ant, module, addr, type=np.dtype('>u1'), length=1, incr=1):
        """ Reads memory-mapped byte(s) from the FPGA through the Ethernet interface.
        Returns a numpy array where the bytes are intrepreted as a series of 'length' elements of type 'type'.
        """

        itemsize = np.dtype(type).itemsize # number of bytes contained in the destinaion vector type
        dout = np.zeros(length*itemsize, np.int8) # initialize result vector as a byte array
        NBYTES = 0
        # Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))
        for i in range(length*itemsize): 
            s = chr(0x00+(NBYTES<<3)+(ant>>2))+chr(((ant&0x03)<<6)+(module<<2)+(addr>>8))+chr(addr&0xff)
            self.sock.write(s)
            data = self.sock.read()
            #if data[0]!=s[0]:
            #    print "Read: ERROR: Returned ANT/SUB/ADDR (",   ata[0:2]," does not match request values (",   [0:2],")"
            if len(data) != 2:
                print "Read: ERROR: %i bytes were returned" % len(data)
            dout[i] = ord(data[1]) # store received byte
            if incr: addr += 1
        dout.dtype = np.dtype(type) # change interpretation of the byte array into a 'type' array

        #if we requested a single value (length=1), returns the object, otherwise return a numpy array of objects
        if len(dout) == 1:
            return dout[0]
        else:
            return dout
        
    
    def write(self, ant, module, addr, data, incr=1, mask=0xff):
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
        s = chr(0x80+(0x40 if incr else 0)+(NBYTES<<3)+(ant>>2))+chr(((ant&0x03)<<6)+(module<<2)+(addr>>8))+chr(addr&0xff)

        # Add the data to the string. The method depends on the data type
        if type(data) == str:
            s += data
            length = len(data)
        elif type(data) == list or type(data) == np.ndarray:
            s += ''.join([chr(data[i]) for i in range(len(data))])
            length = len(data)
        elif type(data) == np.uint32:
            length = 4
            a = np.array([data], np.dtype('>u4')) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            s += ''.join([chr(a[i]) for i in range(4)])
        elif type(data) == np.uint16:
            length = 2
            a = np.array([data], np.dtype('>u2')) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            s += ''.join([chr(a[i]) for i in range(2)])
        elif type([data]) == np.uint8:
            length = 1
            a = np.array([data]) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            s += chr(a[i])
        else:
            s = s + chr(data)
            length = 1
        self.sock.write(s)
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

    def sync(self, continuous=0, sleep=0, phase=None, delay=None, plot=0, verbose=0, local=1):
        if phase is not None:
            self.ADC_PLL.init(phase=phase, verbose=verbose)
        if plot:
            plt.figure(1)
            plt.clf()
            plt.hold(1)
            plt.axis([0, 32, -1, 2])
            
        try:
            while 1:
                if verbose:
                    print 'Sync...'
                if local:
                    self.REFCLK.local_sync(delay=delay)
                else:
                    self.REFCLK.sync(delay=delay)

                s = self.REFCLK.scan_refclk_delay()
                if verbose:
                    self.REFCLK.print_bit_vector(s)
                if plot:
                    plt.plot(s)
                    plt.draw()
                if not continuous: break
                time.sleep(sleep)
        except KeyboardInterrupt:
            pass

    DATA_SOURCE_NAMES = {
        # name, source_sel, adcdaq_ramp, adc
        'func_zero' : (0, None), # All bytes are zero
        'func_one' : (1, None), # All bytes are one
        'func_ramp': (2, None), # Successive bytes generate a repeating ramp from 0 to 255
        'func_real_ramp' : (3, None), # Generates a complex ramp from 0+0i to 255+0i on each successive (8+8) bits complex values (the imaginary part is always zero). 
        'inject' : (6, None), # Takes the data from the data injection FIFO
        'adcdaq_data' : (7, False),  # takes the data from the ADC. Use set_adc_mode() to choose whether the ADC sends data, a ramp or pulses.
        'adcdaq_ramp' : (7, True), # takes a ramp generated by the ADCDAQ
        }    


    def set_data_source(self, source="adcdaq_data", channels=range(8)):
        '''
            Sets the data source.  Options are:
            'func_zero' : (0, None), # All bytes are zero
            'func_one' : (1, None), # All bytes are one
            'func_ramp': (2, None), # Successive bytes generate a repeating ramp from 0 to 255
            'func_real_ramp' : (3, None), # Generates a complex ramp from 0+0i to 255+0i on each successive (8+8) bits complex values (the imaginary part is always zero). 
            'inject' : (6, None), # Takes the data from the data injection FIFO
            'adcdaq_data' : (7, False),  # takes the data from the ADC. Use set_adc_mode() to choose whether the ADC sends data, a ramp or pulses.
            'adcdaq_ramp' : (7, True), # takes a ramp generated by the ADCDAQ
            '''
        if source in self.DATA_SOURCE_NAMES:
            source_info = self.DATA_SOURCE_NAMES[source.lower()]
            source_sel = source_info[0]            
            adcdaq_ramp = source_info[1]
            
        else:
            raise Exception('Invalid data source')
            
        for ch in channels:
            ant = self.ANT[ch]
            ant.FR_DIST.DATA_SOURCE = source_sel
            ant.FR_DIST.reset_fifo() # if this automatically reset by SYNC now?
            if adcdaq_ramp is not None:
                ant.ADCDAQ.ENABLE_RAMP = adcdaq_ramp

    ADC_MODE_NAMES = {
        # name, mode number, period
        'data' : (0, 64), # All bytes are zero
        'ramp' : (1, 64), # All bytes are one
        'pulse': (2, 11), # Successive bytes generate a repeating ramp from 0 to 255
        }    

    def set_ADC_mode(self, channels=range(8), mode='data', sync=1):
        """
        Sets the test mode of both ADCs, sets the proper CAPTURE period, and sends a SYNC.
            test_mode:
                'data': Normal mode (ADC output contains analog samples)
                'ramp': Ramp mode (ADC output contains repeating 0-255 pattern. Note that ADCDAQ inverts bit 7 during acquisition to convert offset binary to 2's complement binary)
                'pulse': Strobe mode (ADC output contains one 0xFF followed by ten 0x00. It repeats with a pariod of 11. Same comment as above)
        111212 JFC: Added this high-level function with string mode.
        """

        mode_info = self.ADC_MODE_NAMES[mode.lower()]
        mode_value = mode_info[0]
        capture_period = mode_info[1]

        self.ADC.set_test_mode(test_mode=mode_value)
        self.current_ADC_mode = mode_value

        for ant in self.ANT:
            ant.ADCDAQ.CAPTURE2_PERIOD = capture_period # set the period so we are ready to capture data correctly after the SYNC resets the CAPTURE logic

        self.sync() # make sure the ADC mode is set and that capture  restarts properly with the right period

    def stop_data_capture(self):
        """
        Stops the transmission of data.
        """
        self.SYSMOD.GLOBAL_TRIG = 0 # disable data transmission if continuous mode is currentlly selected
        for ant in self.ANT:
            ant.PROBER.RESET = 1

    def start_data_capture(self,  burst_period_in_seconds=None, burst_period_in_frames=None, frames_per_burst=1,  number_of_bursts=0,  channels=range(NUMBER_OF_ANTENNAS), sync=1, verbose=1):
        """
        Triggers the capture of the specified number of frames in the FPGA for transmission over the Ethernet port. 
        This function does not receive the frames from the ethernet port. This has to be done separately.
        """

        if ( (burst_period_in_frames is None) and (burst_period_in_seconds is None)) or ((burst_period_in_frames is not None) and (burst_period_in_seconds is not None)) :
            raise SystemError("You must specify either 'burst_period_in_frames' or bust_period_in_seconds'")

        if burst_period_in_seconds is not None:
            burst_period_in_frames = max(float(burst_period_in_seconds)/self.FRAME_PERIOD, 1)


        burst_period_in_frames = int(burst_period_in_frames)

        if verbose:
            print 'Configuring antennas %s to transmit %i-frame burst every %i frames (i.e .every %.3f ms) %s' %  (
                channels.__repr__(),
                frames_per_burst, 
                burst_period_in_frames, 
                burst_period_in_frames*self.FRAME_PERIOD*1000, 
                ('continuously when TRIG=1' if not number_of_bursts else 'for a total of %i bursts' % number_of_bursts ) ) 
            frames_per_second = len(channels)*frames_per_burst*1.0/self.FRAME_PERIOD
            bits_per_second = frames_per_second * 8 * self.FRAME_LENGTH
            print 'Data rates are: %f kFrames/s, %f Mbits/s' % (frames_per_second/1e3, bits_per_second/1e6)

        self.SYSMOD.GLOBAL_TRIG = 0 # disable data transmission if continuous mode is currentlly selected
        self.SYSMOD.ANT_RESET = 1 # resets all 
#        if clear_buffer:
#            self.flush_frame_buffer()
            
        for ant in self.ANT:
            ant.PROBER.RESET = 1
            ant.PROBER.PROBE_ID = 0xA0 + ant.ant_number
            ant.PROBER.config_capture(frames_per_burst=frames_per_burst, burst_period=burst_period_in_frames, number_of_bursts=number_of_bursts)
            if ant.ant_number in channels:
                print 'Enabling Capture for Antenna %i' % ant.ant_number
                ant.PROBER.RESET = 0

        self.SYSMOD.GLOBAL_TRIG = 1 # enables data transmission if continuous mode is selected
        self.SYSMOD.ANT_RESET = 0 # disable reset all 
