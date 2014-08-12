'''
Set of functions used in iceboard qc script to program and test the FPGA.
'''

def programFpga(ch_acq_path, ip, bitfile_path = "fpga_bitfile.bit"):
    import logging
    import sys
    # Append ch_acq to PATH
    sys.path.append(ch_acq_path)
    from pychfpga.arm import ARM

    # Bitfile path from chFPGA. Left here for reference, now that a bitfile is included in iceboard-qc.
    # filename = "../../chFPGA/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit"
    
    # Set log
    log_level = logging.INFO
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')
    logger.info('------------------------')
    logger.info('ARM processor method')
    logger.info('J.-F. Cliche')
    logger.info('------------------------')
    logger.info('Using IP address %s' % ip)
    a = ARM(ip)
    logging.basicConfig(level=log_level)
    # Program FPGA
    a.configure_fpga(filename)
    
def top_test(ch_acq_path, host_ip): # adpated from pychfpga/top_test
    '''
    Creates fpga_controller and fpga_receiver instances and returns them as [c,r].
    '''
    import logging
    import sys
    import time
    # Append ch_acq to PATH
    sys.path.append(ch_acq_path)
    from pychfpga.core import chFPGA_controller
    from pychfpga.core import chFPGA_receiver
    
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
        
    try:
        c.close() # close sockets from previous objects to free them for the new one
        r.close() # close sockets from previous objects to free them for the new one
        del c
        del r
    except NameError:
        pass
    
    # parameters: --init 1 -f 800 -l debug -w 4 -g 2 --enable_gpu_link 1  --host_ip 
    ip = '10.10.10.11'
    init = 1
    sampling_frequency = 800
    log_level = logging.INFO
    data_width = 8
    group_frames = 1
    enable_gpu_link = 0
    ADC_DELAY_TABLE = ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2
    
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')
    logger.info('------------------------')
    logger.info('top_test.py: chFGPA test script')
    logger.info('J.-F. Cliche')
    logger.info('------------------------')
    
    # get FPGA_controller
    c = chFPGA_controller.chFPGA_controller(ip_address=ip, port_number=41000, adc_delay_table=ADC_DELAY_TABLE, init=init, sampling_frequency=sampling_frequency * 1e6, reference_frequency=10e6, data_width=data_width, group_frames=group_frames, enable_gpu_link = enable_gpu_link, host_ip = host_ip)
    time.sleep(0.5)
    
    # Check if at least one FMC board present
    adc_present = c.FMC_present[0] or c.FMC_present[1]
    if not adc_present:
        logger.warning("No ADC boards are present, will not initialize a receiver.")
        r = None
        logger.warning("Returning receiver ('r') as None.")
    else:
        logger.info('Getting chFPGA configuration')
        chFPGA_config = c.get_config()
        logger.info('Starting data/correlator receiver threads')
        r = chFPGA_receiver.chFPGA_receiver(chFPGA_config, ip_address=ip, port=41001, host_ip = host_ip)
    
    return [c,r]

def rampTest(ch_acq_path, directory, host_ip, board_ip):
    '''
    Run the ramp test on a single board connected to host_ip.
    '''
    # Import necessary pychfpga modules
    import sys
    sys.path.append(ch_acq_path)
    from pychfpga.common.tests.ramp_test import test_adc_ramp_histogram
    from pychfpga import save_raw_frames
    from pychfpga.core.chFPGA_controller import chFPGA_controller as ChimeFpgaFirmware
    from pychfpga.core import chFPGA_receiver
    
    # Timing for ADCs
    ADC_DELAY_TABLE= (
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
    
    print "\nProgramming FPGA:"
    programFpga(ch_acq_path, board_ip)
    
    print "\nRunning top_test:"
    [c,r] = top_test(ch_acq_path, host_ip)
    
    # Begin Ramp test
    print "\nBegin ramp test:"
    test = test_adc_ramp_histogram(c, r)
    test.execute(directory)
    r.close()
    
    
