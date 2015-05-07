""" Test launcher.

   - Gets command-line arguments like iceboard hostnames,  bitfile name,
     desired logging target and level and performs basic checks
   - Clears any previous logging handlers and set the SQLAlchemy logging to a
     known level.
"""

import argparse
import logging
import __main__
import datetime
import sys

from pychfpga.core.icecore import IceBoardPlus, IceBoardPlusHandler, IceCrate, HardwareMap, discover_iceboards
from pychfpga.MGADC08 import MGADC08
from pychfpga.core.chFPGA_controller import chFPGA_controller
from pychfpga.core.chFPGA_receiver import chFPGA_receiver
from pychfpga.core.icecore.session import load_session as load_yaml

# import all test modules
import scaler_tests

test_classes = {
    'scaler': scaler_tests.ScalerTests
    }

# Reload all modules in case they were changed
for m in {sys.modules[c.__module__] for c in test_classes.values()}:
    print 'Reloading module %s' % m.__name__
    reload(m)
for n,c in test_classes.items():
    test_classes[n] = getattr(sys.modules[c.__module__], c.__name__)

class FpgaBitstream(object):
    """ Helper object used to load and store a FPGA bitstream. You don't have
    to use it, but it makes the code look nicer"""
    bitstream = None

    def __init__(self, filename, auto_reload=True):
        self.filename = filename
        self.auto_reload = auto_reload
        if not self.auto_reload:
            self._load()
    def __str__(self):
        """ Return the bitstream as a string. """
        if self.auto_reload:
            self._load()
        return self.bitstream
    def _load(self):
        with open(self.filename, 'rb') as file_:
            self.bitstream = file_.read()

ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 = (
    ([16]*8,     [3]*8),  #CH0
    ([7]*8,      [3]*8),  #CH1
    ([22]*8,     [3]*8),  #CH2
    ([19]*8,     [3]*8),  #CH3
    ([15]*8,     [3]*8),  #CH4
    ([14, 13, 14, 14, 13, 14, 15, 14],    [3]*8),  #CH5
    ([18]*8,     [3]*8),  #CH6
    ([17]*8,     [4]*8),  #CH7
    ([15, 17, 15, 18, 17, 14, 17, 15],   [3]*8),  #CH8
    ([16]*8,     [4]*8),  #CH9
    ([20]*8,     [3]*8),  #CH10
    ([18]*8,     [3]*8),  #CH11
    ([15]*8,     [3]*8),  #CH12
    ([18]*8,     [3]*8),  #CH13
    ([18]*8,     [3]*8),  #CH14
    ([16]*8,     [3]*8)  #CH15
    )

ADC_DELAY_TABLE = ADC_DELAYS_MGK7MB_REV2_MGAC08_REV2 #ADC_DELAYS_REV2_SN0001 ## select the table corresponding to the FMC serial number


if __name__=='__main__':

    # This is the bitfile that is generated if implementing the the Vivado
    # project located in
    # icecore/rtl/projects/iceboard_top_example/iceboard_top_example.xpr
    default_bitfile = (
        '../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/CHFPGA_MGK7MB_REV2.bit')

    # Configure the various loggers to provide adequate levels of details
    log_levels = {'info': logging.INFO, 'debug': logging.DEBUG}

    # -------------------------------
    # Process command line arguments
    # -------------------------------

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('test_names', nargs='*', type=str, help="Name of the test to run")

    parser.add_argument('-t', '--log_target', action='store', type=str, default='syslog', help="Logging target ('stream', 'syslog' or a filename)")
    parser.add_argument('-l', '--log_level', action='store', type=str, choices=log_levels, default='debug', help='Logging level')
    parser.add_argument('--if_ip', action='store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. This is used solely for direct UDP communications with the FPGA. If not specified, the system will use the same interface that communicates with the ARM processor.')

    parser.add_argument('-i', '--iceboards', action='store', nargs='+', type=str, help="Space-separated list of the iceboard hostnames (e.g. 10.10.10.7 or iceboard0007.local if the mDNS system is operational")
    parser.add_argument('-d', '--discover', action='store_true', help="Discover all boards and crates on the network using mDNS and add them to the hardware map")
    parser.add_argument('-c', '--crate', action='store', type=str, help="Select only boards in the specified crate serial number")
    parser.add_argument('-s', '--slot', action='store', type=str, help="Select only boards in the specified slot(s)")
    parser.add_argument('--force', action='store', type=int, default=0, help='Force FPGA programming even if the firmware is already programmed. If -1, the FPGA is not configured.')
    parser.add_argument('--bitfile', action='store', type=str, default= default_bitfile,  help='Filename of the bitfile used to to program the FPGAs')


    # parser.add_argument('-s', '--subarray', action='store', nargs='+', type=int, help='Space-separated list of subarrays to include')
    parser.add_argument('--init', action='store', type=int, default=-1, help='Initialization level: -1: Just create sockets, 0: connect and read only. 1: initialize hardware')
    parser.add_argument('-f', '--sampling_frequency', action='store', type=float, default=800, help='Sampling frequency of the ADC in MHz')
    parser.add_argument('-w', '--data_width', action='store', type=int, choices=[4,8], default=4, help='Data width of each Re and Im component of the channelizer output')
    parser.add_argument('-g', '--frames_per_packet', action='store', type=int, default=4, help='Number of frames to group before sending to the GPU or FPGA correlator. The total size of the frame, including the header and ethernet obverhead, cannot exceed 8 kibytes.')
    parser.add_argument('--enable_gpu_link', action='store', type=int, default=0, help='Enables the GPU link transmission')
    # parser.add_argument('--sn', action='store', type=int, default=7, help='Serial number of the Iceboard')

    args = parser.parse_args()

    __main__._host_interface_ip_addr = args.if_ip


    # -------------------------------
    # Set-up logging
    # -------------------------------


    # Make sure SQLAlchemy does not log too much
    sql_logger = logging.getLogger('sqlalchemy.engine.base.Engine')
    sql_logger.setLevel(logging.INFO)

    # Set-up chFPGA loggers
    if args.log_target == 'stream':
        log_handler = logging.StreamHandler()
    elif args.log_target == 'syslog':
        log_handler = logging.handlers.SysLogHandler()
    else:
        log_handler = logging.FileHandler(args.log_target)

    logger = logging.getLogger('')
    logger.handlers = []  # Clear all existing handlers
    log_level = log_levels[args.log_level]

   # Set-up log for this test run
    logger.setLevel(log_levels[args.log_level])
    logger.addHandler(log_handler)


    # Associate the bitstream with the target Handler
    fpga_bitstream = FpgaBitstream(args.bitfile)
    # chFPGA_controller.register_fpga_bitstream(fpga_bitstream)

    # -------------------------------
    # Create a hardware map
    # -------------------------------
    hwm = HardwareMap()  # Create empty hardware map

    # First, Add iceboards that are explicitely listed. For now, we know only their hostname
    if args.iceboards:
        for hostname in args.iceboards:
            i = IceBoardPlus(hostname=hostname)
            hwm.add(i)
            hwm.flush()
            if not i.ping():
                raise RuntimeError("%r could not be found at '%s'"
                                   % (i, i.tuber_uri))
            i.discover_serial()
            i.discover_crate()

    # Discover additional boards and crates on the network using mDNS
    if args.discover:
        if not args.crate:
            raise NameError('Must specify a crate number when using auto-discovery')
        discover_iceboards(hwm)

    ib = hwm.query(IceBoardPlus)
    print 'The following boards were specified and/or discovered:'
    for i in ib:
        print 'Crate SN%s, slot %2i: Iceboard SN%s at %s (ping =%s)' % (i.crate.serial, i.slot, i.serial, i.hostname, i.ping())

    if args.crate:
        ic = hwm.query(IceCrate).filter_by(serial=args.crate).one()
    else:
        ic = hwm.query(IceCrate)
        if ic.count():
            ic = ic.one()
        else:
            ic = None

    # Filter by crate and slot number
    if ic:
        ib = ib.filter_by(crate=ic)
    if args.slot:
        ib = ib.filter_by(slot=args.slot)

    # -------------------------------
    # Check if specified iceboards are on-line before going any further
    # -------------------------------

    if ib.count():
        ib.set_handler(chFPGA_controller, fpga_bitstream)
        # ib.set_handler(IceBoardPlusHandler, fpga_bitstream)

        # Configure the FPGA with the bitstream associated with the handler
        if args.force > -1:
            ib.set_fpga_bitstream(force=args.force)

        ib.discover_mezzanines() # auto-discover mezzanines and add them to the hardware map (requires chFPGA_controller handler to read McGill MGADC08 EEPROMs)

        print 'The following boards were selected:'
        for i in ib:
            mezz = ['%s SN%s' % (m.__ipmi_part_number__, m.serial) if m else 'None' for m in [i.mezzanine.get(1,None), i.mezzanine.get(2,None)]]
            print 'Crate SN%s, slot %2i: Iceboard SN%s at %s (ping =%s), Mezz1=%s, Mezz2=%s' % (i.crate.serial, i.slot, i.serial, i.hostname, i.ping(), mezz[0], mezz[1])

        if args.init > -1:
            ib.open(adc_delay_table=ADC_DELAY_TABLE,
                    init=args.init,
                    sampling_frequency=args.sampling_frequency * 1e6,
                    reference_frequency=10e6,
                    data_width=args.data_width,
                    group_frames=args.frames_per_packet,
                    enable_gpu_link=args.enable_gpu_link)

        # logger.info('Getting chFPGA configuration')
        # chFPGA_config = c.get_config()
        # logger.info('Starting data/correlator receiver threads')

        # r = chFPGA_receiver(chFPGA_config)

    for test_name in args.test_names:
        test_module = test_classes[test_name]
        for i in ib:
            test_filename = 'results/%s_IceBoard_SN%s' % (test_name, i.serial)
            te = test_module(context={
                "Date": datetime.datetime.now(),
                "Bitstream filename": args.bitfile,
                "Bitstream CRC32": '0x%08X' % i.get_fpga_bitstream_crc(),
                "Master Iceboard hostname": i.hostname,
                "Iceboard handler name": type(i.handler).__handler_name__,
                })
            try:
                te.run(i)
            except Exception:
                raise
            finally:
                te.write_xml(test_filename + '.xml')
                # te.write_html(test_filename + '.html')
                print '\n'.join(te.synopsis_as_strings())
# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
