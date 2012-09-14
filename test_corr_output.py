#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
top_test.py script 
 Instantiates a chFPGA object 'c' for interactive testing. Import in ipython using "r -i top_test" so the created chFPGA object "c" is accessible in the ipython interactive workspace.


#
History:
    2011-08-14 JFC: Created from chFPGA, which now only contains top test code.
    2011-09-09 JFC: Added global FREF 
    2011-10-11 JFC: Updated delay tables
"""
import time
import numpy as np
from pychime.core import chFPGA_controller
from pychime.core import chFPGA_receiver
import pychime.plot_utils as pu
from pychime.core import Inject as inj
from pychime.common.algs.alg_test_adc import alg_test_adc
reload(chFPGA_controller) # just to make sure that any changes to the code are reloaded
reload(chFPGA_receiver) # just to make sure that any changes to the code are reloaded
reload(pu)
reload(inj)


# Default data and clock line delays for the two FMC boards/ML605 combination.
# First 8 values are the delays for bits 0 to 7, 8th value is the delay for the clock line.
SN001_ADC_DELAYS = (
    [13,19,19,19,19,19,19,19]+[13], # CH0
    [18]*8+[0], #CH1
    [10]*8+[13], #CH2
    [19]*8+[13], #CH3
    [18]*8+[0], #CH4
    [16]*8+[0], #CH5
    [18]*8+[0], #CH6
    [14]*8+[0] #CH7
    )
# SN001_adc_delays=(
    # [5+16,8+16,8+16,8+16,8+16,8+16,8+16,8+16]+[0], # CH0
    # [2+16]*8+[0], #CH1
    # [5+16]*8+[0], #CH2
    # [1+16]*8+[0], #CH3
    # [16]*8+[0], #CH4
    # [15]*8+[0], #CH5
    # [18]*8+[0], #CH6
    # [13]*8+[0] #CH7
    # )

# SN001_adc_delays=(
    # [5,12,12,12,12,12,12,12]+[0], # CH0
    # [8]*8+[0], #CH1
    # [8]*8+[0], #CH2
    # [6]*8+[0], #CH3
    # [5]*8+[0], #CH4
    # [4]*8+[0], #CH5
    # [4]*8+[0], #CH6
    # [4]*8+[0] #CH7
    # )

#SN002_adc_delays=(
#    [16,22,22,22,22,22,22,22]+[0], #CH0 (BUFR)
#    [21]*8, #CH1 (BUFR)
#    [22]*8+[0], #CH2 (PLL)
#    [18]*8+[0], #CH3 (PLL)
#    [17]*8, #CH4 (BUFR)
#    [17]*8, #CH5 (BUFR)
#    [18]*8, #CH6 (BUFR)
#    [14]*8, #CH7 (BUFR)
#    )
    
SN002_ADC_DELAYS = (
    [17,15,15,15,15,15,15,3]+[0], #CH0 (BUFR)
    [15]*8, #CH1 (BUFR)
    [27,14,29,29,29,29,29,15]+[0], #CH2 (PLL)
    [15]*8+[0], #CH3 (PLL)
    [17]*8, #CH4 (BUFR)
    [17]*8, #CH5 (BUFR)
    [18]*8, #CH6 (BUFR)
    [14]*8, #CH7 (BUFR)
    )

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

def unscramble(data):
    '''
    Assumes data is (5,512) in shape array
    writes to (10,256) shape, where the 10 
    are correlation pairs:  AA, AB,AC,AD,BB,BC,BD,CC,CD,DD
    and the 256 are frequency channels.  Will need to further combine output from 4
    Correlators to get all frequencies. Hopefully will see a pattern to put in for loop.  Also should change to 
    better support the actual data coming out
    '''
    corr_output = np.zeros((10,256), dtype=np.complex)
    corr_output[0,::2] = data[4,::4] #AA
    corr_output[0,1::2] = data[0,3::4] #AA
    corr_output[1,::2] = data[3,::4] #AB
    corr_output[1,1::2] = data[1,3::4] #AB
    corr_output[2,::2] = data[3,1::4] #AC
    corr_output[2,1::2] = data[1,2::4] #AC
    corr_output[3,::2] = data[3,2::4] #AD
    corr_output[3,1::2] = data[1,1::4] #AD
    corr_output[4,::2] = data[4,1::4] #BB
    corr_output[4,1::2] = data[0,2::4] #BB
    corr_output[5,::2] = data[2,::4] #BC
    corr_output[5,1::2] = data[2,3::4] #BC
    corr_output[6,::2] = data[2,1::4] #BD
    corr_output[6,1::2] = data[2,2::4] #BD
    corr_output[7,::2] = data[4,2::4] #CC
    corr_output[7,1::2] = data[0,1::4] #CC
    corr_output[8,::2] = data[1,::4] #CD
    corr_output[8,1::2] = data[3,3::4] #CD
    corr_output[9,::2] = data[4,3::4] #DD
    corr_output[9,1::2] = data[0,::4] #DD
    return corr_output      
    
if __name__ == '__main__':        
    print '------------------------'
    print 'top_test.py: chFGPA test script'
    print 'J.-F. Cliche'
    print '------------------------'

    # Delete previous instances of 'c' to make sure the sockets are closed. If not, the new object will not be able to open the socket.
    # pylint: disable=E0601    
    try:
        print 'Deleting previous chFPGA instances in current namespace'
        c.close() # close sockets from previous objects to free them for the new one
        r.close() # close sockets from previous objects to free them for the new one
        del c
        del r
    except NameError:
        pass

    #ADC_TEST_MODE = 0     #  0= normal, 1= ramp, 2=pulse (1 high, 10 low)
    ADC_DELAY_TABLE = ADC_DELAYS_REV2_SN0001 # select the table corresponding to the FMC serial number
    #FREF = 10 # FMC Reference clock frequency 

    # Create the new chFPGA object.
    c = chFPGA_controller.chFPGA_controller(adc_delay_table=ADC_DELAY_TABLE) # pylint: disable=C0103
    r = chFPGA_receiver.chFPGA_receiver()
    c.sync()
    #inj.set_inject_mode(c,r)
    #dcs = inj.check_fft_dc(c,r)
    # Displays the system frequencies
    c.FreqCtr.status()
    #adctest = alg_test_adc(c,r)
    #stuff = adctest.execute()
    #import numpy as np
    #stuff = np.array(stuff)
    #np.save('convergance_of_pfb.npy', stuff)
    c.set_FFT_bypass(True, channels=[0,1,2,3,4,5,6,7])
    c.set_data_source('func_zero')
    c.set_data_source('func_real_ramp', channels=[0,1,2,3])
    #c.CORR_BLOCK[0].CH_DIST.select_words(8)
    c.start_data_capture(burst_period_in_seconds=1.0, number_of_bursts=0)
    #c.set_data_capture(burst_period=10000, number_of_bursts=0)
    # Continuously plot the ADC output
    #c.plot_ADC_frame(channels=[1], frames=512)
    #c.close()
    #r.close()
    time.sleep(2)
    test = r.read_frames()
    test = r.read_frames()
    output = r.read_corr_frames()
    output = r.read_corr_frames()
    dout = np.array([output[0],output[1],output[2],output[3],output[4]])
    data = unscramble(dout)
    #### dout shouldn't need to do all these manipulations anymore
    # dout = dout.reshape(dout.shape[0],dout.shape[1]/13,13)
    # flags = dout[:,:,0]
    # data = dout[:,:,1:]
    # reals = data[:,:,:6].astype(np.uint8)
    # imags = data[:,:,6:].astype(np.uint8)
    # re2 = reals[:,:,0].astype(np.int8) *256**5 + reals[:,:,1] *256**4 + reals[:,:,2] *256**3 + \
    #     reals[:,:,3] *256**2 + reals[:,:,4] *256 + reals[:,:,5]
    # im2 = imags[:,:,0] *256**5 + imags[:,:,1] *256**4 + imags[:,:,2] *256**3 + \
    #     imags[:,:,3] *256**2 + imags[:,:,4] *256 + imags[:,:,5]
    # corr = re2 + 1.0j*im2
    

