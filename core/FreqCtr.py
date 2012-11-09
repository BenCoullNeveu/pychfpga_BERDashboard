#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
FreqCtr.py module 
 Implements the Frequency Counter interface

History:
    2011-07-13 : JFC : Created from test code in chFPGA.py
    2011-09-08 JFC: Added FMC_REFCLK
    2011-09-25 JFC: Added fan RPM readout
    2012-05-31 JFC: Added data processing frequency readout. Cleanup status() display.
    2012-10-17 JFC: Added correlator frequency
    2012-11-09 JFC: Modified to use Module. Uses fpga SYSTEM_CLOCK_FREQUENCY variable.
"""
from Module import Module_base, BitField

class FreqCtr_base(Module_base):
    """
    Implements the Frequency Counter Interface.
    """

    # Frequency counter port definitions
    PORTS = {
    'ADC_CLK0': 0,
    'ADC_CLK1': 1,
    'ADC_CLK2': 2,
    'ADC_CLK3': 3,
    'ADC_CLK4': 4,
    'ADC_CLK5': 5,
    'ADC_CLK6': 6,
    'ADC_CLK7': 7,
    'MGT_REFCLK': 8,
    'MGT_USRCLK2': 9,
    'FMC_REFCLK': 10,
    'CLK200': 11,
    'CTRL_CLK': 12,
    'FAN': 13,
    'ANT_CLK': 14,
    'CORR_CLK': 15,
    'SYSMON_CLK': 16,
    }

    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    GATE_COUNT = BitField(CONTROL, 3, 0, width=32, doc='Gate time, set in 200 MHz clocks')
    SOURCE = BitField(CONTROL, 4, 4, width= 4, doc='Select signal to be measured')
    START = BitField(CONTROL, 4, 0, doc='When 0, resets the frequency counter.  When high, counts the uncoming clock edges until the gate time is elapsed.')

    FREQ_COUNT = BitField(STATUS, 3, 0, width=32, doc='Frequency count (number of rising edges seen on the source signal during the gate time)')
    DONE = BitField(STATUS, 4, 0, doc='Frequency counting is complete (gate time has been reached).')


    # Registers

    def __init__(self, fpga, verbose=1):
        self.fpga = fpga
        self.verbose = verbose
        super(self.__class__, self).__init__(fpga, fpga.SYSTEM_PORT, fpga.SYSTEM_FREQ_CTR_MODULE)
        self._lock() # prevent further property creation to avoid creating attrubutes by mistake

#    def read(self, addr, type=np.uint8):
#        """ Reads from the register of the frequency counter"""
#        fpga = self.fpga
#        data = fpga.Read(fpga.SYSTEM_PORT, fpga.SYSTEM_FREQ_CTR_MODULE, addr, type)
#        return data
#
#    def write(self, addr, data):
#        """ Writes to the register of the frequency counter"""
#        fpga = self.fpga
#        fpga.Write(fpga.SYSTEM_PORT, fpga.SYSTEM_FREQ_CTR_MODULE, addr, data)

    def init(self):
        """
        Initializes the frequency counter module.
        """
        pass


    def read_frequency(self, port, gate_time=0.01):
        """ Reads the frequency (in Hz) of the specified frequency counter input port 
        """
        ref_freq = self.fpga.SYSTEM_CLOCK_FREQUENCY
        #gate_ctr = np.array([ref_freq*gate_time], np.dtype('>u4'))
        #gate_ctr.dtype = np.uint8
        gate_ctr = int(ref_freq*gate_time)
        #print gate_ctr
        #self.write(0x00, gate_ctr)
        self.GATE_COUNT = gate_ctr

        if type(port) is str:
            port = self.PORTS[port]
        self.SOURCE = port # Sets the signal source to be measured
        self.START = 0 # Clears the counter       
        self.START = 1 # starts the frequncy counter       
        #self.write(0x04, (port << 4) + 0x00) # Reset frequency counter
        #self.write(0x04, (port << 4) + 0x01) # Start frequency counter
        while not self.DONE: 
            pass
        freq = self.FREQ_COUNT
        return freq * 2.0 / gate_time

    def status(self):
        """
        Prints the Frequency Counter status.
        """
        fpga = self.fpga

        gate_time = 0.05
        resolution = 2.0 / gate_time

        fan_gate_time = 0.2
        fan_resolution = 2.0 / fan_gate_time

        if fpga.FMC_present:
            fmc_present_string = ''
        else:
            fmc_present_string = ' (ADC board not present)'

        ant_clock_source_string = ('ADC','SYSTEM CLOCK')[fpga.ANT[fpga.ADC_CLK_SELECT].ADCDAQ.PLL_CLK_SRC]        

        print 'System Frequencies:'
        print '   FPGA Board frequency:      %7.3f MHz' % (self.read_frequency('CLK200', gate_time=gate_time) / 1e6) 
        print '   CTRL_CLK frequency:        %7.3f MHz' % (self.read_frequency('CTRL_CLK', gate_time=gate_time) / 1e6) 
        #print '   SYSMON_CLK frequency:      %7.3f MHz' % (self.read_frequency('SYSMON_CLK', gate_time=gate_time) / 1e6) 
        print '   ANT_CLK frequency:         %7.3f MHz (Source=%s)' % (self.read_frequency('ANT_CLK', gate_time=gate_time) / 1e6, ant_clock_source_string) 
        print '   Correlator frequency:      %7.3f MHz' % (self.read_frequency('CORR_CLK', gate_time=gate_time) / 1e6) 
        print '   FMC Reference frequency:   %7.3f MHz%s' % (self.read_frequency('FMC_REFCLK', gate_time=gate_time) / 1e6, fmc_present_string) 
        print '   MGT Ref clock frequency:   %7.3f MHz' % (self.read_frequency('MGT_REFCLK', gate_time=gate_time) / 1e6) 
        print '   MGT word frequency:        %7.3f MHz' % (self.read_frequency('MGT_USRCLK2', gate_time=gate_time) / 1e6) 
        for i in range(8):
            print '   ADC%i clock frequency:      %7.3f MHz%s' % (i, self.read_frequency('ADC_CLK%i' % i, gate_time=gate_time) / 1e6, fmc_present_string) 
        print '   Resolution          :    %10.6f MHz' % (resolution / 1e6) 
        print '   Gate time           :    %.3f s' % (gate_time) 
        print '   Fan speed:               %7.0f RPM (resolution %.0f RPM)' % (self.read_frequency('FAN', gate_time=fan_gate_time)*60. / 2, fan_resolution*60. / 2) # 1 Hz=60 RPM, divide by 2 because there is 2 pulses per fan turn  

