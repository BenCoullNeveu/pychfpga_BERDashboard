"""
Set of functions used in iceboard qc script to program and test the FPGA.
"""

def programFpga(board_sn, ch_acq_path = '../../ch_acq/', host_ip = None,  bitfile_path = "fpga_bitfile.bit", force = False):
    '''
    This method programs the FPGA of the specified board. It will force it to reprogram if it was already.
    :param ch_acq_path: will be added to PYTHONPATH. defaults to '../../ch_acq/'
    :param host_ip: IP address of adapter used by computer to communicate with FPGA
    :param board_sn: e.g. '0021'
    :param bitfile_path: defaults to "fpga_bitfile.bit" in BoardTests
    :return: 'c' instance of programmed chFPGA_controller
    '''

    import logging
    import sys
    # Append ch_acq to PATH
    sys.path.append(ch_acq_path)

    # Import icecore dependencies
    from pychfpga.icecore.icearray import IceArray, close_all_sockets
    from pychfpga.core.chFPGA_controller import chFPGA_controller

    # Bitfile path from chFPGA. Left here for reference, now that a bitfile is included in iceboard-qc.
    # filename = "../../chFPGA/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/chFPGA_MGK7MB_Rev2.bit"
    
    # Set log
    log_level = logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')
    logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.WARN)
    logger = logging.getLogger(__name__)
    logger.info('Using IP address %s' % host_ip)
    
    close_all_sockets() # close any previously opened sockets
    try:
        logger.info('Deleting previous chFPGA instances in current namespace')
        r.close() # close sockets from previous objects to free them for the new one
        del r
    except NameError:
        pass
    
    array = reload_list(host_ip=host_ip)

    # Load in memory the CHIME firmware to be used with the iceboards
    fpga_bitstream = array.get_fpga_bitstream(bitfile_path, chFPGA_controller)

    # Query the database for iceboard with given serial number
    c = array.get_iceboards(serial_number=int(board_sn)).one()

    # Program the iceboard with the specified firmware and assiciate it with the corresponding Python handler class
    # (if the FPGA  is already programmed, this will be instantaneous)
    c.set_fpga_firmware(fpga_bitstream, configure_fpga=True, force=force)
    return c

def discover_fpgas(host_ip):
    from pychfpga.icecore.fpga_core import FpgaCoreFirmware
    FpgaCoreFirmware.interface_ip_addr = host_ip
    return FpgaCoreFirmware.discover_fpgas()
    
def top_test(board_sn, ch_acq_path='../../ch_acq/', host_ip=None, force=False):
    '''
    Creates fpga_controller and fpga_receiver instances and returns them as [c,r].
    :param ch_acq_path: will be added to PYTHONPATH. defaults to '../../ch_acq/'
    :param host_ip: IP address of adapter used by computer to communicate with FPGA
    :param board_sn: e.g. '0021'
    :return: list [c,r] chfpga controller and receiver, respectively
    '''
    import logging
    import sys
    # Append ch_acq to PATH
    sys.path.append(ch_acq_path)
    from pychfpga.core import chFPGA_receiver
    from pychfpga.icecore.icearray import close_all_sockets
    
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
    
    # parameters: --init 1 -f 800 -l debug -w 4 -g 2 --enable_gpu_link 0  --host_ip
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
    logger.info('top_test for ICEboard QC')
    logger.info('------------------------')

    close_all_sockets()
    # get FPGA_controller
    c = programFpga(board_sn, ch_acq_path=ch_acq_path, host_ip=host_ip, force=force)
    c.open(\
        adc_delay_table=ADC_DELAY_TABLE, \
        init=init, \
        sampling_frequency=sampling_frequency * 1e6, \
        reference_frequency=10e6,\
        data_width=data_width, \
        group_frames=group_frames, \
        enable_gpu_link = enable_gpu_link)
    
    # Check if at least one FMC board present
    adc_present = c.fpga.is_fmc_present(0) or c.fpga.is_fmc_present(1)
    if not adc_present:
        logger.warning("No ADC boards are present, will not initialize a receiver.")
        r = None
        logger.warning("Returning receiver ('r') as None.")
    else:
        logger.info('Getting chFPGA configuration')
        chFPGA_config = c.fpga.get_config()
        logger.info('Starting data/correlator receiver threads')
        r = chFPGA_receiver.chFPGA_receiver(chFPGA_config, ip_address=c.fpga_ip_addr, port=c.fpga_port_number+1, host_ip = host_ip)

    return [c,r]

def rampTest(board_sn, directory, ch_acq_path='../../ch_acq/', host_ip=None):
    '''
    Run the ramp test on a single board.
    :param ch_acq_path: will be added to PYTHONPATH. defaults to '../../ch_acq/'
    :param host_ip: IP address of adapter used by computer to communicate with FPGA
    :param board_sn: e.g. '0021'
    :param directory: directory to save ramp_test results in (e.g. histogram PDFs and data)
    '''

    # Import necessary pychfpga modules
    import sys
    sys.path.append(ch_acq_path)
    from pychfpga.common.tests.ramp_test import test_adc_ramp_histogram
    
    print "\nRunning top_test:"
    [c,r] = top_test(board_sn, ch_acq_path=ch_acq_path, host_ip=host_ip)
    
    # Timing for ADCs. Calculate proper offsets for this board.
    ADC_DELAY_TABLE, stuck_bits, bitposgood = c.fpga.compute_adc_delay_offsets(channels=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15])
    print "Computed delay table:"
    print repr(ADC_DELAY_TABLE)
    print "Stuck bit flags (0 indicates a stuck bit):"
    print repr(bitposgood)
    #ADC_DELAY_TABLE= (
    #([16]*8,     [3]*8), #CH0
    #([7]*8,                       [3]*8), #CH1
    #([22]*8,    [3]*8), #CH2
    #([19]*8,                       [3]*8), #CH3
    #([15]*8,                        [3]*8), #CH4
    #([14, 13, 14, 14, 13, 14, 15, 14],    [3]*8), #CH5
    #([18]*8,     [3]*8), #CH6
    #([17]*8,                       [4]*8), #CH7
    #
    #([15, 17, 15, 18, 17, 14, 17, 15],   [3]*8), #CH8
    #([16]*8,                       [4]*8), #CH9
    #([20]*8,                       [3]*8), #CH10
    #([18]*8,                     [3]*8), #CH11
    #([15]*8,                       [3]*8), #CH12
    #([18]*8,                       [3]*8), #CH13
    #([18]*8,                       [3]*8), #CH14
    #([16]*8,                       [3]*8)  #CH15
    #)
    
    # Set ADC delays
    c.fpga.set_adc_delays(ADC_DELAY_TABLE)

    # Record serials of mezzanines

    # Begin Ramp test
    print "\nBegin ramp test:"
    test = test_adc_ramp_histogram(c.fpga, r)
    test.execute(directory)
    r.close()

def reload_list(fname="iceboard_list.txt", host_ip=None):
    from pychfpga.icecore.icearray import IceArray, close_all_sockets
    # Close all previous sessions with the layout/hardware map database
    IceArray.close_all_sessions()

    # Create the array object and update the hardware database from a file and from auto-discovery
    array = IceArray(uri='sqlite:///test.db', interface_ip_addr=host_ip)
    array.load_iceboards('iceboard_list.txt') # update iceboard definitions in database with the data in this CSV file so we can start with an empty database if needed
    array.discover() # automatically update the hardware map database with discovered resources. This will probe the boards and will update the 'present' field.
    return array

def read_list(fname="iceboard_list.txt"):
    '''
    Reads file iceboard_list.txt and returns a 2D list with contents of table.
    :param fname: File name of board list. defaults to "iceboard_list.txt"
    :return: 2D list of ARM and FPGA addresses. If file not found, returns empty list.
    '''
    import os

    # Check file exists
    if not os.path.isfile(fname):
        print "\nFile " + fname + " doesn't exist."
        return []
    # Read file as list
    f = open(fname, 'r')
    content = f.readlines()
    f.close()

    # Convert content of file to 2D list and strip whitespace
    content_grid = [i.split(',') for i in content]
    content_grid = [[j.strip() for j in i] for i in content_grid]
    return content_grid
    
def edit_list(board_sn, arm_ip=None, arm_mac=None, fpga_ip=None, fpga_sn=None, locked=None, subarray=None):
    '''
    Edit the line from iceboard_list.txt corresponding to some board.
    :param board_sn: e.g. '0012'
    :param arm_ip: e.g. '10.10.10.12'
    :param arm_mac: e.g. '84:7E:40:6F:CC:A0'
    :param fpga_ip: e.g. '10.10.3.12'
    :param fpga_sn: e.g. '0x14e1c452263014'
    :param locked: e.g. '0'
    :param subarray: e.g. '1'
    '''
    import os

    # Read file and create if doesn't exist
    fname = "iceboard_list.txt"
    content = read_list(fname)
    if len(content) == 0 and (not os.path.isfile(fname)):
        header = "# sn,                      ARM/tuber_uri,      ARM MAC address,      fpga_ip_addr, fpga_serial_number, locked, subarray"
        file = open(fname, 'w')
        file.write(header)
        file.close()
        print "Created new file " + fname + " ."
        content[0] = header.split(',')
        content[0] = [i.strip() for i in content[0]]

    # Check that list is not empty
    if len(content) < 2:
        empty = True
    else:
        empty = False

    # Find line for this board
    line_index = None
    line = None
    if not empty:
        for i, val in enumerate(content[1:len(content)]):
            if int(val[0]) == int(board_sn):
                line_index = i + 1
                line = val
                break
    if line_index is None:
            line_index = len(content)
            line = [str(int(board_sn))]
            line[1:7] = ["0"] * 6

    # Edit line and add to content
    for index, val in enumerate([arm_ip, arm_mac, fpga_ip, fpga_sn, locked, subarray]):
        if val is not None:
            line[index+1] = val
    if line_index < len(content):
        content[line_index] = line
    else:
        content.append(line)

    # Format table with fixed column width
    COLUMN_WIDTHS = (4, 35, 21, 18, 18, 6, 9)
    for i, lin in enumerate(content):
        for j, val in enumerate(lin):
            if COLUMN_WIDTHS[j] - len(val) < 0:
                print "Supplied argument '" + val + "' in row " + str(i) + ", column " + str(j) + "  is longer than the allowed column width of the table."
                print "Formatting will be off. Please check your values and try again."
            while COLUMN_WIDTHS[j] - len(content[i][j]) > 0: # Have to use content[i][j] to actually modify value, val is not in scope
                content[i][j] = " " + content[i][j]
    # Add '\n' to every line except last
    for i, lin in enumerate(content[0:len(content)-1]):
        content[i][-1] = lin[-1] + '\n'
    content = [','.join(l) for l in content]

    # Write formatted table to file
    file = open(fname, 'w')
    file.writelines(content)
    file.close()

