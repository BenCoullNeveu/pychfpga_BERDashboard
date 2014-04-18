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
import logging
reload(logging) # needed to reset the logger config in case we change the formatting
import argparse
import time


# from pychfpga.icecore import hardware_map
# reload(hardware_map) #needed to make sure database-mapped classes are build into a fresh list

from icecore import hardware_map
# from icecore import tuber
reload(hardware_map)
# reload(tuber)

# from pychfpga.icecore.icearray import IceArray, close_all_sockets
# from pychfpga.icecore.fpgabitfile import FpgaBitFile


from icecore.icearray import IceArray, close_all_sockets
from icecore.fpgabitfile import FpgaBitFile
from icecore.iceboard import IceBoard

from core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware

# from pychfpga.core import chFPGA_controller
# from pychfpga.core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware
from pychfpga.core import chFPGA_receiver
import plot_utils.plot_utils as pu
from pychfpga.core import Inject_tools as inj

# from pychfpga.common.tests.test_adc_fft_bin import test_adc_fft_bin
# from pychfpga.common.tests.test_adc_fft_int_power import test_adc_fft_int_power
# from pychfpga.common.tests.test_adc_fft_level import test_adc_fft_level
# from pychfpga.common.tests.test_adc_dc import test_adc_dc
# from pychfpga.common.tests.test_adc_spectrum import test_adc_spectrum
# import pychfpga.common.tests.test_corr as tc
# from pychfpga import receiver_corr_fast

print 'Reloading modules'
# dreload(chFPGA_controller) # just to make sure that any changes to the code are reloaded
#dreload(chFPGA_receiver) # just to make sure that any changes to the code are reloaded
reload(pu)
reload(inj)
# reload(receiver_corr_fast)

# Default data and clock line delays for the two FMC boards/ML605 combination.
# First 8 values are the delays for bits 0 to 7, 8th value is the delay for the clock line.
#SN001_ADC_DELAYS = (
#    [13,19,19,19,19,19,19,19]+[13], # CH0
#    [18]*8+[0], #CH1
#    [10]*8+[13], #CH2
#    [19]*8+[13], #CH3
#    [18]*8+[0], #CH4
#    [16]*8+[0], #CH5
#    [18]*8+[0], #CH6
#    [14]*8+[0] #CH7
#    )
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

#SN002_ADC_DELAYS = (
#    [17,15,15,15,15,15,15,3]+[0], #CH0 (BUFR)
#    [15]*8, #CH1 (BUFR)
#    [27,14,29,29,29,29,29,15]+[0], #CH2 (PLL)
#    [15]*8+[0], #CH3 (PLL)
#    [17]*8, #CH4 (BUFR)
#    [17]*8, #CH5 (BUFR)
#    [18]*8, #CH6 (BUFR)
#    [14]*8, #CH7 (BUFR)
#    )


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

ADC_DELAYS_REV2_SN0001 = (
    [20,26,25,25,25,25,25,24], #CH0
    [22]*8, #CH1
    [22,22,20,20,20,20,20,19], #CH2
    [18]*8+[0], #CH3
    [17]*8, #CH4
    [17]*8, #CH5
    [19,19,19,18,17,16,20,20], #CH6
    [16]*8, #CH7
    )

ADC_DELAYS_REV2_SN0001_KC705_FMC700 = (
    [13,10,9,10,9,10,9,9], #CH0
    [7]*8, #CH1
    [11,11,8,9,7,8,8,7], #CH2
    [6]*8, #CH3
    [14]*8, #CH4
    [14]*8, #CH5
    [13]*8, #CH6
    [0]*8, #CH7
    )

ADC_DELAYS_MGK7MB_REV0_MGAC08_REV2 = (
    ([6,25,25,25,25,25,25,25],     [4]*8), #CH0
    ([21]*8,                       [3]*8), #CH1
    ([18,17,16,16,13,15,14,13],    [3]*8), #CH2
    ([13]*8,                       [3]*8), #CH3
    ([9]*8,                        [3]*8), #CH4
    ([14,12,12,12,12,12,12,12],    [3]*8), #CH5
    ([11,11,13,10,10,8,12,13],     [3]*8), #CH6
    ([12]*8,                       [4]*8), #CH7

    ([15, 14, 16, 14, 13, 18, 15, 15],   [4]*8), #CH8
    ([15, 19, 21, 18, 15, 18, 19, 20],                       [3]*8), #CH9
    ([18, 18, 21, 20, 20, 20, 20, 16],                       [3]*8), #CH10
    ([15, 15, 15, 14, 15, 13, 14, 15],                     [3]*8), #CH11
    ([13, 15, 16, 12, 11, 16, 16, 15],                       [3]*8), #CH12
    ([12, 12, 10, 11, 10, 11, 13, 10],                       [3]*8), #CH13
    ([13, 15, 15, 14, 12, 11, 16, 14],                       [3]*8), #CH14
    ([13, 15, 15, 17, 17, 18, 18, 14],                       [3]*8)  #CH15
    )

ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 = (
    ([16]*8,     [3]*8), #CH0
    ([7]*8,                       [3]*8), #CH1
    ([22]*8,    [3]*8), #CH2
    ([19]*8,                       [3]*8), #CH3
    ([15]*8,                        [3]*8), #CH4
    ([14, 13, 14, 14, 13, 14, 15, 14],    [3]*8), #CH5
    ([18]*8,     [3]*8), #CH6
    ([17]*8,                       [4]*8), #CH7

    ([15, 17, 15, 18, 17, 14, 17, 15],   [3]*8), #CH8
    ([16]*8,                       [4]*8), #CH9
    ([20]*8,                       [3]*8), #CH10
    ([18]*8,                     [3]*8), #CH11
    ([15]*8,                       [3]*8), #CH12
    ([18]*8,                       [3]*8), #CH13
    ([18]*8,                       [3]*8), #CH14
    ([16]*8,                       [3]*8)  #CH15
    )

if __name__ == '__main__':

    close_all_sockets() # close any previously opened sockets
    try:
        logger.info('Deleting previous chFPGA instances in current namespace')
        r.close() # close sockets from previous objects to free them for the new one
        del r
    except NameError:
        pass

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('--init', action = 'store', type=int, default=1, help='Initialization level: -1: Just create sockets, 0: connect and read only. 1: initialize hardware')
    parser.add_argument('-f', '--sampling_frequency', action = 'store', type=float, default=850, help='Sampling frequency of the ADC in MHz')
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=['info','debug'], default='info', help='Logging level')
    parser.add_argument('-w', '--data_width', action = 'store', type=int, choices=[4,8], default=8, help='Data width of each Re and Im component of the channelizer output')
    parser.add_argument('-g', '--group_frames', action = 'store', type=int, default=4, help='Number of frames to group before sending to the GPU or FPGA correlator. The total size of the frame, including the header and ethernet obverhead, cannot exceed 8 kibytes.')
    parser.add_argument('--enable_gpu_link', action = 'store', type=int, default=0, help='Enables the GPU link transmission')
    parser.add_argument('--sn', action = 'store', type=int, default=7, help='Serial number of the Iceboard')
    parser.add_argument('--subarray', action = 'store', type=int, default=0, help='Number of the Subarray in which the board will be searched')
    parser.add_argument('--host_ip', action = 'store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. If not specified, the controller will attempt to identify the proper host based on the FPGA IP address.')
    args = parser.parse_args()

    log_level = {'info': logging.INFO, 'debug': logging.DEBUG}[args.log_level]
    logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.WARN)

    logger = logging.getLogger(__name__)
    logger.info('------------------------')
    logger.info('top_test.py: chFGPA test script')
    logger.info('J.-F. Cliche')
    logger.info('------------------------')
    logger.info('This module is called with the follwing parameters:' )
    for (key,value) in args.__dict__.items():
        logger.info('   %s = %s' % (key, repr(value)))
    # logger.info('Using Sampling frequency of %0.3f MHz' % args.sampling_frequency)
    # Delete previous instances of 'c' to make sure the sockets are closed. If not, the new object will not be able to open the socket.
    # pylint: disable=E0601


    #ADC_TEST_MODE = 0     #  0= normal, 1= ramp, 2=pulse (1 high, 10 low)
    ADC_DELAY_TABLE = ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 #ADC_DELAYS_REV2_SN0001 ## select the table corresponding to the FMC serial number
    #FREF = 10 # FMC Reference clock frequency

    # Close all previous sessions with the layout/hardware map database
    IceArray.close_all_sessions() # close all previously opened sessions

    # Create the array object and update the hardware database from a file and from auto-discovery
    array = IceArray(uri='sqlite:///test.db', interface_ip_addr=args.host_ip)
    array.load_iceboards('iceboard_list.txt') # update iceboard definitions in database with the data in this CSV file so we can start with an empty database if needed
    array.discover() # automatically update the hardware map database with discovered resources. This will probe the baords and will update the 'present' field.

    # Load in memory the CHIME firmware to be used with the iceboards
    bitfile_filename = '../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit'
    fpga_bitstream = FpgaBitFile(bitfile_filename) # we have to create one bitstream object only.

    # Query the database for all available iceboards
    # To mimick the old top_test, select only one board
    c = array.get_iceboards(subarray=args.subarray, serial_number=args.sn).one()

    # Program the iceboard with the specified firmware and assiciate it with the corresponding Python handler class
    # (if the FPGA  is already programmed, this will be instantaneous)
    c.set_fpga_firmware(fpga_bitstream, ChimeFpgaFirmware, configure_fpga=True)

    # Establish communication with the board and initialize the firmware and software
    c.open( \
        adc_delay_table=ADC_DELAY_TABLE, \
        init=args.init, \
        sampling_frequency=args.sampling_frequency * 1e6, \
        reference_frequency=10e6, data_width=args.data_width, \
        group_frames=args.group_frames, \
        enable_gpu_link = args.enable_gpu_link)

    # c = chFPGA_controller.chFPGA_controller(ip_address=args.ip, port_number=41000, adc_delay_table=ADC_DELAY_TABLE, init=args.init, sampling_frequency=args.sampling_frequency * 1e6, reference_frequency=10e6, data_width=args.data_width, group_frames=args.group_frames, enable_gpu_link = args.enable_gpu_link, host_ip = args.host_ip) # pylint: disable=C0103

    time.sleep(0.5)
    logger.info('Getting chFPGA configuration')
    chFPGA_config = c.get_config()
    logger.info('Starting data/correlator receiver threads')
    r = chFPGA_receiver.chFPGA_receiver(chFPGA_config, ip_address=c.fpga_ip_addr, port=c.fpga_port_number + 1, host_ip = c.interface_ip_addr)
    #r = receiver_corr_fast.chFPGA_receiver(chFPGA_config, ip_address='10.10.10.11', port=41001)
    ##c.sync()
    #inj.set_inject_mode(c,r)
    #dcs = inj.check_fft_dc(c,r)
    ######adctest = test_adc_spectrum(c,r)
    ######stuff = adctest.execute()
    # Displays the system frequencies
#    c.status()
    #adctest = test_adc_fft_bin(c,r)
    #stuff = adctest.execute()
    #adctest = test_adc_fft_int_power(c,r)
    #stuff = adctest.execute()
    #import numpy as np
    #stuff = np.array(stuff)
    #np.save('convergance_of_pfb.npy', stuff)
    #c.set_data_source('adcdaq_data')
    #c.start_data_capture(burst_period_in_seconds=1.0, number_of_bursts=0)
    #c.set_data_capture(burst_period=10000, number_of_bursts=0)
    # Continuously plot the ADC output
    #c.plot_ADC_frame(channels=[1], frames=512)

    #

    #c.close()
    #r.close()

