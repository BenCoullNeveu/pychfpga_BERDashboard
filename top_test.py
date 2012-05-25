#!/usr/bin/python

"""
top_test.py script 
 Instantiates a chFPGA object 'c' for interactive testing. Import in ipython using "r -i top_test" so the created chFPGA object "c" is accessible in the ipython interactive workspace.


#
History:
	2011-08-14 JFC: Created from chFPGA, which now only contains top test code.
	2011-09-09 JFC: Added global FREF 
	2011-10-11 JFC: Updated delay tables
"""

import chFPGA
reload(chFPGA) # just to make sure that any changes to the code are reloaded

# Default data and clock line delays for the two FMC boards/ML605 combination.
# First 8 values are the delays for bits 0 to 7, 8th value is the delay for the clock line.
SN001_adc_delays=(
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

SN002_adc_delays=(
	[16,22,22,22,22,22,22,22]+[0], #CH0 (BUFR)
	[21]*8, #CH1 (BUFR)
	[22]*8+[0], #CH2 (PLL)
	[18]*8+[0], #CH3 (PLL)
	[17]*8, #CH4 (BUFR)
	[17]*8, #CH5 (BUFR)
	[18]*8, #CH6 (BUFR)
	[14]*8, #CH7 (BUFR)
	)


if __name__=='__main__':		
	print '------------------------'
	print 'top_test.py: chFGPA test script'
	print 'J.-F. Cliche'
	print '------------------------'

	# Delete previous instances of 'c' to make sure the sockets are closed. If not, the new object will not be able to open the socket.
	try:
		print 'Deleting previous chFPGA instances in current namespace'
		c.close() # close sockets from previous objects to free them for the new one
		del c
	except:
		pass

	ADC_TEST_MODE=0 	#  0= normal, 1= ramp, 2=pulse (1 high, 10 low)
	ADC_DELAY_TABLE=SN002_adc_delays # select the table corresponding to the FMC serial number
	FREF=10 # FMC Reference clock frequency 

	# Create the new chFPGA object.
	c=chFPGA.chFPGA(adc_test_mode=ADC_TEST_MODE, adc_delay_table=ADC_DELAY_TABLE,fref=FREF);
	c.sync()
	print
	
	# Displays the system frequencies
	c.FreqCtr.status()
	# Continuously plot the ADC output
	#c.plot_ADC_frame(channels=[1], frames=512)

