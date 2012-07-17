#!/usr/bin/python
'''
   plot_utils.py
    Provides plotting utilities
    
    #
    # History:
    # 2012-07-16 : KMB : Created mostly moving functions from chFPGA
    
'''


import numpy as np
import pylab as plt
#from core import chFPGA

def plot_TIMESTREAM_frames(chFPGA, channel=0, hold=0, frames=1, continuous=0, raw=0, flush=0):
    """ Plots incoming frames """
    #if isinstance(channels,int): # make sure that channel is a list of channels
    #	channels=[channels]
    
    
    continuous |= (frames == 0) # plots continuously if frames=0 and continuous set to True
    
    
    plt.figure(5)
    plt.clf()
    plt.hold(hold)
    plt.show()
    
    number_of_frames = 0
    ymax = 1
    try:
        while (continuous == 1) or (number_of_frames < frames):
            try:
                print 'Reading data...'
                #sync_again=(number_of_frames==0) or bool(reset)
                a = chFPGA.read_frames(raw=raw, flush=flush) #(number_of_frames==0)
                flush = 0
                ch1_data = a[channel]
                number_of_frames += 1
                
                aamax = max(abs(ch1_data))
                ymax = max(ymax*.99, aamax)
                plt.plot(ch1_data, 'b.-')
                plt.draw()
            except:
                raise
    except KeyboardInterrupt:
        pass
    print 'Plotted %i frames' % number_of_frames

def plot_TIMESTREAM_frames_multichannel(chFPGA, channels=[0], hold=0, frames=1, raw=0, flush=0):
    """ Plots incoming frames, expected to be a timestream """
    if isinstance(channels,int): # make sure that channel is a array of channels
    	channels=np.array([channels])
    elif isinstance(channels,list):
        channels=np.array(channels)

    
    continuous = (frames == 0) # plots continuously if frames=0
    nchan = channels.size
    
    plt.figure(5, figsize=(6*nchan,6))
    plt.ion()  #not sure if necessary, sets to interactive mode
    plt.clf()
    plt.hold(hold)  #again, not sure if necessary or should be here
    plt.show()   #again, not sure if necessary or should be here
    
    chanIndex = np.arange(nchan)
    plotObject = np.arange(nchan)


    number_of_frames = 0
    ymax = 1
    try:
        while (continuous == 1) or (number_of_frames < frames):
            try:
                print 'Reading data...'
                #sync_again=(number_of_frames==0) or bool(reset)
                a = chFPGA.read_frames(raw=raw, flush=flush) #(number_of_frames==0)
                flush = 0  ### ? not sure about this
                
                aamax = max(abs(a[channels[0]]))
                ymax = max(ymax*.99, aamax)
                if ( number_of_frames == 0 )
                    for chanNum in chanIndex:
                        plt.subplot(2,nchan,chanNum)
                        plt.title('Timestream')
                        plt.xlabel('Sample')
                        plt.ylabel('Amplitude')
                        plotObject[chanNum], = plt.plot(a[channels[chanNum]] ,'b.-')
                        plt.draw()  #not sure if necessary
                else:
                    for chanNum in chanIndex:
                        plotObject[chanNum].set_ydata(a[channels[chanNum]])
                
                number_of_frames += 1
            except:
                raise
    except KeyboardInterrupt:
        pass
    print 'Plotted %i frames' % number_of_frames

def plot_SPECTRUM_frames(chFPGA, channels=[0], hold=0, frames=1, raw=0, flush=0):
    """ Plots incoming frames, expected to be fourier transformed """
    if isinstance(channels,int): # make sure that channel is a array of channels
    	channels=np.array([channels])
    elif isinstance(channels,list):
        channels=np.array(channels)
    
    
    continuous = (frames == 0) # plots continuously if frames=0
    nchan = channels.size
    
    plt.figure(5, figsize=(6*nchan,6))
    plt.ion()  #not sure if necessary, sets to interactive mode
    plt.clf()
    plt.hold(hold)  #again, not sure if necessary or should be here
    plt.show()   #again, not sure if necessary or should be here
    
    chanIndex = np.arange(nchan)
    plotMagnitudeObject = np.arange(nchan)
    plotPhaseObject = np.arange(nchan)
    
    
    number_of_frames = 0
    ymax = 1
    try:
        while (continuous == 1) or (number_of_frames < frames):
            try:
                print 'Reading data...'
                #sync_again=(number_of_frames==0) or bool(reset)
                a = chFPGA.read_frames(raw=raw, flush=flush) #(number_of_frames==0)
                flush = 0  ### ? not sure about this
                
                aamax = max(abs(a[channels[0]]))
                ymax = max(ymax*.99, aamax)
                if ( number_of_frames == 0 ):
                    #Break up real and imaginary parts of a and put into numpy complex array
                    #fa = np.empty([chanIndex.size,(a[channels[0].size)/2],dtype=np.complex64)
                    fa = np.empty((a[channels[0].size)/2,dtype=np.complex64)
                    for chanNum in chanIndex:
                        fa.real = a[channels[chanNum]][::2]
                        fa.imaginary = a[channels[chanNum]][1::2]
                        plt.subplot(2,nchan,chanNum+1)
                        plt.title('Spectrum')
                        plt.xlabel('Frequency (arb)')
                        plt.ylabel('Amplitude')
                        plotMagnitudeObject[chanNum], = plt.plot(10*np.log10(np.abs(fa)**2), 'b.-')
                        plt.subplot(2,nchan,nchan+chanNum+1)
                        plt.title('Phase')
                        plt.xlabel('Frequency (arb)')
                        plt.ylabel('Phase (rad)')
                        plotPhaseObject[chanNum], = plt.plot(np.angle(fa) ,'b.-')
                else:
                    for chanNum in chanIndex:
                        fa.real = a[channels[chanNum]][::2]
                        fa.imaginary = a[channels[chanNum]][1::2]
                        plt.subplot(2,nchan,chanNum+1)
                        plotMagnetudeObject[chanNum].set_ydata(10*np.log10(np.abs(fa)**2))
                        plt.subplot(2,nchan,nchan+chanNum+1);
                        plotPhaseObject[chanNum].set_ydata(np.angle(fa))
                
                number_of_frames += 1
            except:
                raise
    except KeyboardInterrupt:
        pass
    print 'Plotted %i frames' % number_of_frames

def save_DATA_frames(chFPGA, channels=[0], frames=1, raw=0, flush=0, filename='data.npy'):	
    '''
     Saves data from Acquisition board to numpy array 
    '''
    data_list = []
    if isinstance(channels,int): # make sure that channel is a array of channels
        channels=np.array([channels])
    elif isinstance(channels,list):
        channels=np.array(channels)
    nchan = channels.size
    chanIndex = np.arange(nchan)
                                     
    number_of_frames=0
    try:
        while (frames==0) or (frames!=0 and number_of_frames<frames):
            try:
                a = chFPGA.read_frames(raw=raw, flush=flush)
                number_of_frames+=1
                if filename:
                    for chanNum in chanIndex:
                        data_list.append(a[channels[chanNum]])
                if (number_of_frames % 100) == 0:
                print 'Captured {0} frames'.format(number_of_frames) 
            except:
                raise
    except KeyboardInterrupt:
        pass
    np.array(data_list)
    np.save(filename,data_list)

    print 'Saved %i frames' % number_of_frames

                                     
                                     
#legacy version may not still work.  
#def save_frames(self, filename, channels=0, frames=1, raw=0):
#    """ Save incoming frames to disk """
#    if filename:
#        file=open(filename,'w')
#    else:
#        file=None
#    
#    if isinstance(channels,int): # make sure that channel is a list of channels
#        channels=[channels]
#    
#    number_of_frames=0
#    try:
#        while (continuous==1) or (number_of_frames<frames):
#            try:
#                print 'Reading data...'
#                #sync_again=(number_of_frames==0) or bool(reset)
#                a=self.read_frames(raw=raw) #(number_of_frames==0)
#                ch1_data=a[ch1][:length]
#                number_of_frames+=1
#                file.write(np.int8(ch1_data))
#            except:
#                raise
#    except KeyboardInterrupt:
#        pass
#    if file:
#        file.close()
#    print 'Saved %i frames' % number_of_frames
                                     
if __name__ == '__main__':
    from core import chFPGA
    ADC_TEST_MODE = 0 	#  0= normal, 1= ramp, 2=pulse (1 high, 10 low)
    ADC_DELAYS_REV2_SN0001 = (
                           [20,26,25,25,25,25,25,24], #CH0
                           [23]*8, #CH1 
                           [24,22,20,20,20,20,20,17], #CH2 
                           [19]*8+[0], #CH3
                           [17]*8, #CH4
                           [17]*8, #CH5 
                           [19,19,19,18,17,16,20,20], #CH6 
                           [16]*8, #CH7
                           )
    FREF = 10 # FMC Reference clock frequency
    # Create the new chFPGA object.
    c = chFPGA.chFPGA(adc_test_mode=ADC_TEST_MODE, adc_delay_table=ADC_DELAY_TABLE, fref=FREF) # pylint: disable=C0103
    c.sync()
    # source can be:  'func_zero', func_one, func_ramp, func_real_ramp, inject, adcdaq_data, adcdaq_ramp
    c.set_data_source('adcdaq_data')
    c.set_data_capture(burst_period=10000, number_of_bursts=0)
    plot_TIMESTREAM_frames_multichannel(c, channels=[0,1,2,3,4,5,6,7], hold=0, frames=0, raw=0, flush=0):
    #plot_SPECTRUM_frames(c, channels=[0,1,2,3,4,5,6,7], hold=0, frames=0, raw=0, flush=0):
    

                                     
                                     
                                     
                                     
                                     
                                     
                                     
                                     
                                     
                                     
