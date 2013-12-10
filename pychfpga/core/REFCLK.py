#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
REFCLK.py module 
 Implements FMC Reference clock interface
#
# History:
    2011-09-22 JFC: Created
    2011-09-25 JFC: Modified to support new method on incrementing phase (pulse PS_EN unstead of PS_CLK) 
    2011-11-15 JFC: Lots of modifications done to debug SYNC clock alignment. 
    2012-05-xx JFC: Added disabling SYNC detect when the board is not there, because a floating input create spurious clocks and cause intermittent resets
    2012-09-05 JFC: Updated registers to match firmware. Includes a few status registers to debug SYNC generation mechanism. Added ENABLE_SYNC_GENERATION flag handling to fix spurious generation of SERDES_RST when FMC boar dis not present (the software FORCE_SYNC and REFCLK noise got the SYNC state machine started and left it in SERDES_RST=1 state) 
    2012-09-23 JFC: Removed MMCM status registers. Converted bitfield list to independent variables. Commented out set_refclk200_phase.
"""

from Module import Module_base, BitField

import logging
import time
import numpy as np
import matplotlib.pyplot as plt

class REFCLK_base(Module_base):

    sync_delay=9 # default value.

    CONTROL=BitField.CONTROL
    STATUS=BitField.STATUS
    DRP=BitField.DRP

    # CONTROL bytes
    ADC_SYNC = BitField(CONTROL, 0x00, 7, doc='Force a SYNC to the ADC, synchronized on the FMC Reference clock, but bypasses the SYNC state machine that resets the IOSERDES and BUFR')
    DCI_RESET = BitField(CONTROL, 0x00, 6, doc='Resets the DCI')
    FORCE_SYNC = BitField(CONTROL, 0x00, 5, doc='Force the generation of a local SYNC sequence on the local board only. Has the same effect as a SYNC signed received on the 10 MHz clock.  The SYNC is synchronized to the 10 MHz output (transitions on its falling edge)')
    ENCODE_SYNC = BitField(CONTROL, 0x00, 4, doc='Generate a SYNC signal encoded on the 10 MHz clock output. Will SYNC the local FMC board only if the 10 MHz output is connected to the 10 MHz input of the local FMC board')
    SLAVE = BitField(CONTROL, 0x00, 3, doc='0=board is MASTER: SYNC SMA is an output, 1= board is SLAVE: SYNC SMA is an input')

    REFCLK_SEL = BitField(CONTROL, 0x01, 7, doc='Selects the source of the REFCLK needed for SYNC generation. 0=FMC, 1=internal REFCLK generator.')
    ENABLE_SYNC_GENERATION = BitField(CONTROL, 0x01, 6, doc='Allows the internal state machine to generate the SYNC sequence (generate the ADC SYNC and resets the ADCDAQ SERDES and BUFG)')
    ENABLE_SYNC_DETECTION = BitField(CONTROL, 0x01, 5, doc='When 1, enable SYNC detection based on the Refecence clock pulse length. Disable if the FMC board is not present to prevent spurious resets of the data path.')

    REFCLK_DELAY_RST = BitField(CONTROL,0x02, 7, doc='Resets the REFCLK line IODELAY and loads the delay value specified in REFCLK_DELAY.')
    REFCLK_DELAY = BitField(CONTROL,0x02, 0, width=5, doc='Delay applied to the FMC Reference clock within the FPGA (0-31). Must pulse REFCLK_DELAY_RST to load.')

    # STATUS bytes
    SYNC_CTR = BitField(STATUS, 0x00, 4, width=4, doc='Counts the SYNC events')
    DCI_LOCKED = BitField(STATUS, 0x00, 3, doc='1 when DCI is locked')
    RECOVERED_SYNC = BitField(STATUS, 0x00, 2, doc='1 when a SYNC signal encoded on the 10 MHz is detected ')
    SYNC = BitField(STATUS, 0x00, 1, doc='Status on the internal SYNC signal, which is a combination of various sources (recovered from RefClk, from pin, from bit etc)')
    SERDES_RST = BitField(STATUS, 0x00, 0, doc='Status of the SERDER Reset output line')

    DIFF_COUNTER = BitField(STATUS, 0x01, 0, width=8, doc='DIfference between clocks')

    SYNC_DONE = BitField(STATUS, 0x02, 5, doc='1 when the local SYNC process is completed')
    SYNC_DELAY_READBACK = BitField(STATUS, 0x02, 0, width=5,doc='Reads back the delay set onthe SYNC IODELAY')


    def __init__(self, fpga, base_address):
        self.fpga = fpga
        self.logger = logging.getLogger(__name__)
        super(self.__class__, self).__init__(fpga, base_address)

    def init(self):
        # Sets the REFCLK delay to zero by default.
        self.set_refclk_delay(0)
        self.set_sync_delay(1)
        self.logger = logging.getLogger(__name__)
        # If the board is not present, disable SYNC detection on REFCLK to prevent noise on the floating REFCLK lien to generate spurioys resets. 
        if self.fpga.FMC_present[0]:
            self.logger.info('   REFCLK is using the 10 MHz reference clock from the ADC board')
            self.ENABLE_SYNC_DETECTION = 1
            self.ENABLE_SYNC_GENERATION = 1
            self.REFCLK_SEL = 0 # Use REFCLK coming from the FMC
        else:
            self.logger.info('   REFCLK is using the 10 MHz reference clock from FPGA since the ADC board is not prresent in FMC slot 0')
            self.ENABLE_SYNC_DETECTION = 0
            self.ENABLE_SYNC_GENERATION = 0
            self.REFCLK_SEL = 1 # Use internally generated REFCLK
 
        # self.REFCLK_SEL = 1 # Use internally generated REFCLK ** debug***
             

    def sync(self, delay=None):
        if delay is not None:
            self.set_sync_delay(delay)
        self.set_refclk_delay(self.sync_delay)
        self.pulse_bit('ENCODE_SYNC')
        #time.sleep(0.1) # see if that help packet loss
        self.wait_for_bit('SYNC_DONE')
        #time.sleep(10e-3) # make sure the SYNC sequence is completed and that the ADC clock is running 

    def local_sync(self, delay=None):
        """
        Locally generates a SYNC pulse on the current board's ADCs and reset the data acquisition logic. 
        This is the same as receiving a SYNC signal encoded on the 10 MHz reference clock. 
        The timing of the sync pulse (delay relative to FMC 10 MHz reference clock can optionally be specified).
            If delay=None or is omited, the previous SYNC timing will be used.
            If delay is an integer between 0 and 31, the timing delay is set to that value.
        """ 
        if delay is None:
            self.set_refclk_delay(self.sync_delay)
        else:
            self.set_sync_delay(delay)
            self.set_refclk_delay(delay)
 
        #print 'Setting delay to',    self.sync_delay
        self.pulse_bit('FORCE_SYNC') # Force the REFCLK state machine to initiate a SYNC event
        self.wait_for_bit('SYNC_DONE') # Wait until the SYNC process is completed
        #time.sleep(10e-3) # make sure the SYNC sequence is completed and that the ADC clock is running 

    def set_sync_delay(self, delay):
        """
        Sets the delay of the SYNC pulse relative to the Reference Clock. Valid range is 0-31.
        """
        #self.SYNC_DELAY=delay
        #self.pulse_bit('SYNC_DELAY_RST')
        self.sync_delay = delay # Save the current delay value
        self.set_refclk_delay(delay)


    def set_refclk_delay(self, delay):
        """
        Sets the delay in the Reference clock received into the FPGA. Valid range is 0-31.
        """
        self.REFCLK_DELAY = delay
        self.pulse_bit('REFCLK_DELAY_RST')

    def acquire_ADC_clock_waveform(self,  sleep=0.005, average=1, continuous=0, verbose=0):
        """
        Measures the waveform of the 400 MHz ADC input clock for all ADCs. 
        This is done by sweeping the delay on the 10 MHz reference clock and sampling the ADC clock signal in that delayed clock for every delay value. 
        32 samples are taken over total delay of 2.5 ns (78.125 ps/sample). The acquisition therefore spans the full period of a 400 MHz signal, and it is graranteed that a transition will be observed. 

        'ADC_list' specifies from which ADCs we want to measure the waveform.
        'sleep' indicates how much time to wait between samples are taken.

        The method returns a numpy array ox 8x32 integers. First dimension is the ADC number, second dimension is the delay.
        """
        tap_delay = 1/200e6/32/2
        samples = np.zeros((8,32), np.int8) # prepare an empty array that wil lcontain the clock sample values for all ADCs and all delay values. 
        for delay in range(32): 
            self.set_refclk_delay(delay)
            time.sleep(sleep)
            for i in range(8):
                samples[i][delay] = self.fpga.ANT[i].ADCDAQ.ADC_CLK_SAMPLE
 
        self.set_refclk_delay(0) # Return the reference clock delay to a known state
        return samples

    def print_bit_vector(self, samples, mark):
        print self.bit_vector_to_string(samples, mark)

#    def bit_vector_to_string(self,samples):
#
#        r = ''
#        for bit in range(2):
#            r += ''.join(('0','1')[bool(s & (1<<bit))] for s in samples)+' '
#        return r

    def bit_vector_to_string(self, samples, mark):

        bitstring = ''
        for i in range(len(samples)):
            if i == mark:
                bitstring += '!'
            else:
                bitstring += ('.','#')[bool(samples[i])]
        return bitstring

    def compute_phase(self, s, freq=400e6, dt=1/200e6/32/2):
        """
        Computes the phase of a periodic signal by providing a vector of samples of that clock.
        The vector 's' is a Boolean array.
        The returned value is the sample number corresponding if the estimated rising edge of the signal (assuming a 50% duty cycle)
        """
        rad_per_sample = dt/(1/freq)*2*np.pi;
        phi = np.arange(len(s))*rad_per_sample # phase corresponding to each sample 
        #s=2*s-1 # convert array into -1 or +1
        s *= 1.0    
        v = np.average(s*np.cos(s*phi)+1j*np.sin(s*phi))
        if abs(v) < 2/np.pi/4:
            self.logger.warning('Warning: bad signal to noise in determining phase of ADC_CLK')
        delay = np.mod((np.angle(v)/(2*np.pi))*32, 32) # substract a quarter of cycle to get the rising edge position assuming a 50% duty cycle

        return delay

    def find_edges(self, s, min_step=.5, window=4):
        """
        Finds the position of all positive or negative edges of amplitude 'min_step' followed by 'window' samples where such a transition does not occur.
            """
        ds = (np.abs(np.diff(s*1.0)) > min_step)*2-1
        w = np.hstack(([1], [-1] * window))
        p = np.correlate(ds,w,mode='valid')
        return np.where(p==len(w))[0]+1

    def unwrap(self, v, step, threshold=None):
        """
        Removes jumps of +/-step. If not specified, 'threshold' is 'step/2'.
        """
        if threshold == None:
            threshold = step/2.0
        ds = np.hstack(([0],np.diff(v*1.0)))
        vv = v-np.cumsum((np.abs(ds) >= threshold)*np.sign(ds)*step)
        return vv


    def compute_sync_delay(self, ADC_list = [0,7], sleep=0.001, repeat=1, delays=range(32), plot=False):
        """
        Computes and sets the recommended SYNC pulse timing to ensure that it will meet the ADC timing requirments. 

        This is done by sweeping the timing of the SYNC pulse over a range of 2.5 ns in 32 steps (78.125 ps steps) and for 
        each delay synchronize the ADC and measure the waveform of the 400 MHz ADC output clock. 
        Phase discontinuities will be seen where the timing requirments is not met 
        (i.e. the SYNC falling edge is too close to the 1600 MHz ADC input clock and the setup or hold requirements are not met).  

        The algorithm then look for those discontinuities, and compute the delay that will place the SYNC between the first two first ones. 
        This is done for all ADC simultaneously. The average SYNC timing for all ADCs is used as the optimal value.

        NOTE: This will work only of the ADC board is configured to SYNC the ADC directly from the SYNC signal coming from the FPGA.
        On REV2 boards, this means: 
            1) The FPGA SYNC is used as a source by setting the appropriate control bit on the SYNC mux. 
            2) The SYNC Flip Flop is bypassed by hardware, and the ADC SYNC selection mux control bit must also be set to use the bypassed input.
        """
        samples = [];
        # If plot=1, prepare the plots 
        if plot:
            plt.figure(1)
            plt.clf()
            plt.subplot(1,2,1)
            plt.hold(1)
            plt.axis([0, 128,min(delays)-1,max(delays)+1])
            plt.xlabel('Time (tap delays)');
            plt.ylabel('Sync delay (tap delays)');
            plt.title('ADC0 clock waveform as a function of ADC_SYNC timing delay');
            plt.subplot(1, 2, 2)
            plt.hold(1)
            plt.axis([0, 128,min(delays)-1, max(delays)+1])
            plt.xlabel('Time (tap delays)');
            plt.ylabel('Sync delay (tap delays)');
            plt.title('ADC1 clock waveform as a function of ADC_SYNC timing delay');

        if isinstance(delays,int):
            delays = [delays]
        phase = np.ones((8,len(delays)))*np.inf

        for sync_delay in delays: 
            print 'Sync delay %2i:' % (sync_delay),
            self.local_sync(sync_delay)
            samples = self.acquire_ADC_clock_waveform(sleep=sleep) # Measure the ADC clock waveform for all ADCs
            for ADC_number in range(len(samples)):
                phase[ADC_number][sync_delay] = self.compute_phase(samples[ADC_number])
                if ADC_number in ADC_list:
                    bitstring =  self.bit_vector_to_string(samples[ADC_number], np.mod(int(round(phase[ADC_number][sync_delay])),32))   
                    print 'ADC%2i: %s' % (ADC_number,bitstring), 
            print
#            if plot:
#                plt.subplot(1,2,1)
#                plt.plot([0, 128],[-.25+delay]*2, 'r-')
#                plt.plot((np.hstack((ss[0], ss[0], ss[0], ss[0]))-.5)*.5+delay, 'r-')
#                plt.plot([dd],[delay], 'go')
#                #plt.plot([rise],[delay],'yo')
#                #plt.plot([np.mod(dd,8)],[delay],'ro')
#                plt.subplot(1,2,2)
#                plt.plot([0,128],[-.25+delay]*2, 'r-')
#                plt.plot((np.hstack((ss[1], ss[1], ss[1], ss[1]))-.5)*.5+delay, 'r-')
#            phase[delay] = min(phase[delay],dd)
#            if plot:
#                plt.draw()
        print 'Recommended SYNC delays' 
        recommended_sync_delay = np.zeros(len(samples))
        for ADC_number in range(len(samples)):
            print 'ADC%2i:' % (ADC_number), 
            phase[ADC_number] = self.unwrap(phase[ADC_number], 32) # removes jumps greater than 16
            phase[ADC_number] -= min(phase[ADC_number])
            edges = self.find_edges(phase[ADC_number], min_step=3, window=4)
            print 'Edges found at delays (%s)' % str(edges),
            if len(edges)<2:
                print 'Insufficient number of ADC_CLK phase jumps edges to determine optimal SYNC timing'
            else:
                recommended_sync_delay[ADC_number] = edges[0]+np.average(np.diff(edges*1.0))*0.40 # place sync at a fraction of the average distance between phase jumps
                print ' Recommended sync_delay: %i' % int(round(recommended_sync_delay[ADC_number]))
        average_recommended_sync_delay = int(round(np.average(recommended_sync_delay))) # must be an integer
        print 'Recommended average sync delay: %i' % average_recommended_sync_delay
#            if plot:
#                plt.subplot(1, 2, 1)
#                plt.plot(phase, range(len(phase)), 'bo-')
#                plt.plot(phase[np.mod(edges, 64)], edges, 'ro')
#                plt.plot([0, 31], [e]*2, 'yo-')
#                plt.draw()

        self.set_sync_delay(average_recommended_sync_delay)


            #self.print_bit_vector(s)
        #print ''.join(('0','1')[sample] for sample in samples)

    def status(self):
        """
        Displays the status of the REFCLK module.
        """
        # self.logger.info('-----------------------REFCLK------------------------------------')
        # self.logger.info('SYNC Detection Enabled: %s' % (bool(self.ENABLE_SYNC_DETECTION)))


