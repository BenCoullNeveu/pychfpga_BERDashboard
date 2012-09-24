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

import time
import numpy as np
import matplotlib.pyplot as plt

class REFCLK_base(Module_base):

    sync_delay=16

    CONTROL=BitField.CONTROL
    STATUS=BitField.STATUS
    DRP=BitField.DRP

    # CONTROL bytes
    ADC_SYNC = BitField(CONTROL, 0x00, 7, doc='Force a SYNC to the ADC, synchronized on the FMC Reference clock, but bypasses the SYNC state machine that resets the IOSERDES and BUFR')
    DCI_RESET = BitField(CONTROL, 0x00, 6, doc='Resets the DCI')
    FORCE_SYNC = BitField(CONTROL, 0x00, 5, doc='Force the generation of a local SYNC sequence on the local board only. Has the same effect as a SYNC signed received on the 10 MHz clock.  The SYNC is synchronized to the 10 MHz output (transitions on its falling edge)')
    ENCODE_SYNC = BitField(CONTROL, 0x00, 4, doc='Generate a SYNC signal encoded on the 10 MHz clock output. Will SYNC the local FMC board only if the 10 MHz output is connected to the 10 MHz input of the local FMC board')
    SLAVE = BitField(CONTROL, 0x00, 3, doc='0=board is MASTER: SYNC SMA is an output, 1= board is SLAVE: SYNC SMA is an input')

    SYNC_DELAY_RST = BitField(CONTROL, 0x01, 7, doc='Resets the SYNC line IODELAY and loads the delay value specified in SYNC_DELAY.')
    ENABLE_SYNC_GENERATION = BitField(CONTROL, 0x01, 6, doc='Allows the internal state machine to generate the SYNC sequence (generate the ADC SYNC and resets the ADCDAQ SERDES and BUFG)')
    ENABLE_SYNC_DETECT = BitField(CONTROL, 0x01, 5, doc='When 1, enable SYNC detection based on the Refecence clock pulse length. Disable if the FMC board is not present to prevent spurious resets of the data path.')
    SYNC_DELAY = BitField(CONTROL, 0x01, 0, width=5, doc='Delay between the FMC Reference clock and the SYNC edge (0-31). Must pulse SYNC_DELAY_RST to load.')

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


    def __init__(self, fpga):
        self.fpga = fpga
        super(self.__class__, self).__init__(fpga, fpga.SYSTEM_PORT, fpga.SYSTEM_REFCLK_MODULE)

    def init(self):
        # Sets the REFCLK delay to zero by default.
        self.set_refclk_delay(0)

        # If the board is not present, disable SYNC detection on REFCLK to prevent noise on the floating REFCLK lien to generate spurioys resets. 
        if self.fpga.FMC_present:
            self.ENABLE_SYNC_DETECT = 1
            self.ENABLE_SYNC_GENERATION = 1
        else:
            self.ENABLE_SYNC_DETECT = 0
            self.ENABLE_SYNC_GENERATION = 0
            

    def sync(self, delay=None):
        if delay is not None:
            self.set_sync_delay(delay)
        self.set_refclk_delay(self.sync_delay)
        self.pulse_bit('ENCODE_SYNC')
        self.wait_for_bit('SYNC_DONE')
        #time.sleep(10e-3) # make sure the SYNC sequence is completed and that the ADC clock is running 

    def local_sync(self, delay=None):
        """
        Locally generates a SYNC pulse on the current board's ADCs and reset the data acquisition logic. This is the same as receiving a SYNC signal encoded on the 10 MHz reference clock. The timing of the sync pulse relative to the received 10 MHz clock can optionally be specified.
        """ 
        if delay is not None:
            self.set_sync_delay(delay)
            self.set_refclk_delay(delay)
        self.set_refclk_delay(self.sync_delay)

        #print 'Setting delay to',    self.sync_delay
        self.pulse_bit('FORCE_SYNC')
        self.wait_for_bit('SYNC_DONE')
        #time.sleep(10e-3) # make sure the SYNC sequence is completed and that the ADC clock is running 

    def inc_phase(self, inc_amount):
        if inc_amount > 0:
            self.PS_INCDEC = 1
        else:
            self.PS_INCDEC = 0
        for i in range(abs(inc_amount)):
            self.pulse_bit('PS_EN')
            #while not self.PS_DONE: pass

    def set_sync_delay(self, delay):
        """
        Sets the delay of the SYNC pulse relative to the Reference Clock. Valid range is 0-31.
        """
        #self.SYNC_DELAY=delay
        #self.pulse_bit('SYNC_DELAY_RST')
        self.sync_delay = delay # Save the current delay value
        self.set_refclk_delay(delay)

#    def set_refclk200_phase(self, phase):
#        """
#        Sets DIVCLK phase on MCMM in inrements of 1/8 VCO cycles. Valid range is 0-512.
#        """
#        self.MMCM_RST = 1
#        self.MMCM_POWER = 0xFFFF
#        self.MMCM_REFCLK200_PHASE = phase & 0x07
#        self.MMCM_REFCLK200_DELAY = phase>>3
#        self.MMCM_RST = 0


    #def scan_refclk200_phase(self,sleep=0.3):
    #    samples=[];
    #    for phase in range(24): # FB=60, DIVOUT=3. Cycle = 8* DIVOUT
    #        self.set_refclk200_phase(phase)
    #        time.sleep(sleep)
    #        samples.append(self.ADC_CLK_SAMPLE)
    #    print ''.join(('0','1')[sample] for sample in samples)
    #    #return samples

    def set_refclk_delay(self, delay):
        """
        Sets the delay in the Reference clock received into the FPGA. Valid range is 0-31.
        """
        self.REFCLK_DELAY = delay
        self.pulse_bit('REFCLK_DELAY_RST')

    def scan_refclk_delay(self, sleep=0.005, average=1, continuous=0, verbose=0):
        tap_delay = 1/200e6/32/2
        #N=0
        #sum_edges=0.0
        #max_edges=-np.inf
        #min_edges=np.inf
        try:
            while True:
                samples = np.zeros(32, np.int8);
                for delay in range(32): 
                    self.set_refclk_delay(delay)
                    time.sleep(sleep)
                    #for i in range(40):
                        #s=self.ADC_CLK_SAMPLE
                        #print ('0','1')[s],
                    #print
                    #samples.append(self.ADC_CLK_SAMPLE)
                    #samples[delay]=self.ADC_CLK_SAMPLE
                    samples[delay] = self.fpga.ANT[0].ADCDAQ.ADC_CLK_SAMPLE | self.fpga.ANT[7].ADCDAQ.ADC_CLK_SAMPLE<<1

                #edges=np.where(np.diff(np.array(samples)))
                #first_edge=np.min(edges)
                #last_edge=np.max(edges)
                #uncertainty=float(last_edge-first_edge)*tap_delay
                #edge=float(last_edge+first_edge)/2*tap_delay
                #N+=1;
                #sum_edges+=edge
                #max_edges=max(max_edges,edge)
                #min_edges=min(min_edges,edge)

                #sum_uncertainty+=uncertainty

                if verbose:
                    print '%s (edge %.0f ps, uncertaunty= %.0f)' % (self.bit_vector_to_string(samples), edge*1e12,uncertainty*1e12)
                average -= 1
                if (not continuous) and (not average): break
        except KeyboardInterrupt:
            pass
        self.set_refclk_delay(0)
        #if verbose:
        #    print 'Edge statistigs: Average=%.0f ps, min=%.0f, max=%.0f, spread=%.0f ' % (sum_edges/N*1e12,min_edges*1e12,max_edges*1e12, (max_edges-min_edges)*1e12)
        return samples

    def print_bit_vector(self, samples):
        print self.bit_vector_to_string(samples)

    def bit_vector_to_string(self,samples):

        r = ''
        for bit in range(2):
            r += ''.join(('0','1')[bool(s & (1<<bit))] for s in samples)+' '
        return r

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
            print 'Warning: bad signal to noise in determining phase of ADC_CLK'
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


    def scan_sync_delay(self, sleep=0.001, repeat=1, delays=range(32), plot=False):
        samples = [];
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
        phase = np.ones(len(delays))*np.inf

        try:
            for delay in delays: 
                for n in range(repeat):
                    self.local_sync(delay)
                    s = self.scan_refclk_delay(sleep=sleep)
                    ss = (s&1!=0, s&2!=0)
                    dd = self.compute_phase(ss[0])
                    print 'Delay %2i: %s, phase =%.0f' % (delay, self.bit_vector_to_string(s), dd)
                    if plot:
                        plt.subplot(1,2,1)
                        plt.plot([0, 128],[-.25+delay]*2, 'r-')
                        plt.plot((np.hstack((ss[0], ss[0], ss[0], ss[0]))-.5)*.5+delay, 'r-')
                        plt.plot([dd],[delay], 'go')
                        #plt.plot([rise],[delay],'yo')
                        #plt.plot([np.mod(dd,8)],[delay],'ro')
                        plt.subplot(1,2,2)
                        plt.plot([0,128],[-.25+delay]*2, 'r-')
                        plt.plot((np.hstack((ss[1], ss[1], ss[1], ss[1]))-.5)*.5+delay, 'r-')
                phase[delay] = min(phase[delay],dd)
                if plot:
                    plt.draw()
            print 'Phases: ',phase
            phase = self.unwrap(phase, 32) # removes jumps greater than 32
            edges = self.find_edges(phase, min_step=3, window=4)
        
            if len(edges)<2:
                print 'Insufficient number of ADC_CLK phase jumps edges to determine optimal SYNC timing'
            else:
                e = int(edges[0]+np.average(np.diff(edges*1.0))*0.40) # place sync at a fraction of the average distance between phase jumps
                print 'Recommended SYNC delay: %i taps' % e
                if plot:
                    plt.subplot(1, 2, 1)
                    plt.plot(phase, range(len(phase)), 'bo-')
                    plt.plot(phase[np.mod(edges, 64)], edges, 'ro')
                    plt.plot([0, 31], [e]*2, 'yo-')
                    plt.draw()
                self.set_sync_delay(e)

        except KeyboardInterrupt:
            pass

            #self.print_bit_vector(s)
        #print ''.join(('0','1')[sample] for sample in samples)

    def status(self):
        print '---------------------FMC REF CLK  ------------------------------------'
        print 'SYNC Detection Enabled: %s' % (bool(self.ENABLE_SYNC_DETECT))
        print '----------------------------------------------------------------------'


