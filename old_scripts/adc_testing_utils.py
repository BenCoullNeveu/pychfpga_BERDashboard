#!/usr/bin/python

import numpy as np
import pylab as plt

def plot_ADC_eye_diagram(chFPGA, channel=0):
    '''
        Used to figure out ADC delays, may not work currently, might need to be updated
    '''
    ant=chFPGA.ANT[channel]
    m=np.zeros((32,1024),np.uint8)
    old_delays=ant.ADCDAQ.read_delay()
    plt.figure(2)
    plt.clf()
    plt.plot(old_delays,np.arange(8),'ro')
    plt.hold(1)
    plt.draw()
    for dly in range(32):
        ant.ADCDAQ.set_delay([dly]*8,reset=0)
        a=chFPGA.read_ADC_frame(channels=[channel],length=1024);
        #m[dly,:]=[ 1 if a[i]&(1<<bit) else 0 for i in xrange(len(a))]
        m[dly,:]=a[channel]
    #print ' Delay %2i : %s' % (dly, ''.join([ '|' if a[i]&(1<<bit) else '.' for i in xrange(160)])) 
    ant.ADCDAQ.set_delay(old_delays); # restore original delays
    for b in range(8):
        mm=np.array(m & (1<<b),dtype=bool) # select desired bit
        ix=np.where(np.diff(mm,axis=0)) # find indexes of all transitions (dly ix,sample ix)
        
        xx=np.row_stack((ix[0],ix[0]+1))
        yy=np.row_stack((mm[ix],mm[ix[0]+1,ix[1]]))*0.4-0.2 +b
        plt.plot(np.arange(0,32),(m[:,:(2**b)*4] & (1<<b)!=0 )*0.4-0.2 +b,'r.-')
        #plt.plot(xx,yy,'b.-')
        print('Bit %i, %i points' % (b,len(ix[0])))
        #plt.plot(np.arange(0,32),(m[:,:(2**b)*4] & (1<<b)!=0 )*0.4-0.2 +b,'r.-')
        plt.draw()
    plt.xlabel('Tap delay #');
    plt.ylabel('Bit #');
#plt.figure(1)
#plt.clf()
#plt.imshow((m & (1<<bit))!=0,aspect='auto', interpolation='nearest', cmap=plt.gray(), filternorm=1)
#plt.draw()