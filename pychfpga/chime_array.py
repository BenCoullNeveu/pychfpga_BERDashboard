#!/usr/bin/python
"""
chime_array.py module. Defines the objects that represent and handles
operations one the whole array of CHIME ICE hardware.
"""
import argparse
import logging
import time
import __main__
import sys
import socket  # for gethostbyname()
import itertools
import numpy as np
import matplotlib.pyplot as plt

from tornado.netutil import Resolver
from tornado.ioloop import IOLoop
from tornado.gen import with_timeout, TimeoutError

from sqlalchemy import orm
from sqlalchemy import or_

# from pychfpga.core.icecore import async, async_return
from pychfpga.core.icecore import Ccoll
from pychfpga.core.icecore import IceBoardPlus, IceCrate
from pychfpga.core.icecore import HardwareMap, Session
from pychfpga.core.icecore import mdns_discover

from pychfpga.MGADC08 import MGADC08  # Import ti make sure this Mezzanine is registered  so it can be discovered
from pychfpga.core.chFPGA_controller import chFPGA_controller

# import logging.handlers


from pychfpga.core.icecore.session import load_session as load_yaml


# Configure Tornado objects
Resolver.configure('tornado.netutil.ThreadedResolver', num_threads=20)

#####################################

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
            try:
                self._load()
            except IOError:
                if not self.bitstream:
                    raise
        return self.bitstream

    def _load(self):
        with open(self.filename, 'rb') as file_:
            self.bitstream = file_.read()

# Default data and clock line delays for the two FMC boards/ML605 combination.
# First 8 values are the delays for bits 0 to 7, 8th value is the delay for the clock line.

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

class ChimeArray(object):
    def __init__(self, argv=[], **kwargs):
        """ Create a hardware map describing CHIME hardware and optionally
        initialize the hardware.

        The hardware map to use and initialization options are specified either by parsing a list of command line
        arguments specified in ``argv`` or by directly using keyword arguments.

        Example::
            ChimeArray(argv=['--iceboard', '10.10.10.7', '10.10.10.8', '--subarray', '3'])  is equivalent to:
            ChimeArray(iceboard=['10.10.10.7', '10.10.10.8'], subarray=3)

        The hardware map can be loaded from a YAML file, is created by
        ezlicitely listing IceBoard hostnames, or by mDNS network auto-
        discovery.


        Parameters
        ----------

        argv : List of strings representing command line arguments to be
            parsed by the python ``argparse`` parser as an alternative to the
            keyword arguments below. The argument list excludes the program
            name. For example, use ``argv=sys.argv[1:]`` to process all
            command line arguments. Use keywords arguments below instead if
            the class is to be created programmatically. Keywords arguments
            will override comand line arguments. Default is an empty list (no
            command line arguments)

        log_target : String indicating the logging target (default = 'syslog'). May be
            - 'stream' : logs on stdout (not recommended in interactive sessions)
            - 'syslog': logs on Syslog on localhost
            - any other string: logs to a file specified by the string

        log_level : String indicating the logging level. May be 'info',
            'error', 'warn' , 'debug'. default is 'debug'.

        sql_log_level : String indicating SQLAlchemy logging level. Same
            values as ``log_level``. Defaults to 'warn'.

        if_ip : string corresponding to the IP address of adapter through
            which the connection to the FPGA will be established. If not
            specified, the system will assume that the FPGA is reached trough
            the same interface that reaches the ARM processor.

        yamlfile : String containg the name of a YAML file to load in order to
            provide file-based configuration data accessible to the
            applicaton.

            If the YAML file contains a single hardware map or contains the
            hardware map specified by the ``hwm_name`` parameter, then the
            hardware map will be initialized with it. The crate, slot and
            serial number information will be automatically obtained from the
            hardware if not specified in the YAML file.


        iceboards : List of strings corresponding to the serial number, the IP
            address or the mDNS name of the iceboards to be added to the
            hardward map.

            If an IceBoard is specified by IP address (e.g. '10.10.10.7'),
            then the board can be added directly in the hardware map. This
            does *not* rely on the system mDNS client or the Python
            ``pybonjour`` package.

            If an IceBoard is specified by its mDNS name (e.g.
            'iceboard0007.local'), the operating system will automatically
            resolve the IP address using mDNS, assuming that a mDNS client
            (Bonjour on Windows or Mac, avahi on Linux) is running on this
            computer. The ``pybonjour`` Python package is not needed.

            In both cases, the crate, slot and serial number information will
            be automatically obtained directly through the IceBoard's ARM
            processor if that information not already present in the hardware
            map.

            If an IceBoard is specified by its serial number (e.g. '0007', or
            just a numeric 7 as a convenient shortcut), the board will use the
            ``pybonjour`` package to actively query mDNS and find boards that
            match the serial number.

        exclude_iceboards : Excludes the iceboards specified by serial number only.

        icecrates : Adds all the iceboards from the crates that have the
            serial numbers specified in the provided list of strings.

            This option *always* the ``pybonjour`` package and the system mDNS
            client to automatically probe the network and discover the
            specified Iceboards that advertised themseles along with their
            associated crate number.

            Examples:
                ``icecrates='003'`` or ``icecrates=['003']`` will discover and select all boards from crate SN003
                ``icecrates=['003', '004']`` will select boards from crates SN003 and SN004.
                ``icecrates=[]`` will select all boards on the network


        hwm_name : Name (string) of the hardware map to load from the YAML file (the
            YAML file must be structured as a dictionary)

        Default Iceboard set

        subarrays : List of integers describing the subarrays to include in
            the default IceBoard set. If not specified or an empty list, all
            Iceboards in the hardware map wil be selected. Affects only the
            boards loaded from the hardware map.


        force : (integer). If ``force=0``, the FPGAs in the default Iceboard set will be
            configured only if they are not already configured with the same
            firmware. If ``force=1``, they will always be reconfigured. If
            ``force=-1`` or is not specified, the boards are never configured.

        bitfile : String. Filename of the bitfile used to to program the FPGAs

        ping : Integer. If ``ping=1``, The connection to Iceboards is checked
            by sending a dummy Tuber request to their ARM processor. If a
            YAML-specified iceboards fails, it is simply removed from the
            hardware map, but an exception is raised if a board listed
            explicitely fails. If ``ping=0``, the presence of boards is not
            checked.


        init : Initialization level: -1: Just create sockets, 0: connect and read only. 1: initialize hardware

        open_boards : Establish communication with the boards and initialize the firmware and software

        sampling_frequency : Sampling frequency of the ADC in MHz

        data_width : Data width of each Re and Im component of the channelizer output

        frames_per_packet : Number of frames to group before sending to the GPU or FPGA correlator. The total size of the frame, including the header and ethernet obverhead, cannot exceed 8 kibytes.

        enable_gpu_link : Enables the GPU link transmission


        """

        # This is the bitfile that is generated if implementing the Vivado
        # project located in
        # icecore/rtl/projects/iceboard_top_example/iceboard_top_example.xpr
        default_bitfile = (
            '../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/CHFPGA_MGK7MB_REV2.bit')

        # Configure the various loggers to provide adequate levels of details
        log_levels = {'info': logging.INFO, 'debug': logging.DEBUG, 'warn': logging.WARNING, 'error': logging.ERROR}

        # -------------------------------
        # Process command line arguments
        # -------------------------------

        parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring

        parser.add_argument('-t', '--log_target', action='store', type=str, default='syslog', help="Logging target ('stream', 'syslog' or a filename)")
        parser.add_argument('-l', '--log_level', action='store', type=str, choices=log_levels, default='debug', help='Logging level')
        parser.add_argument('--sql_log_level', action='store', type=str, choices=log_levels, default='warn', help='SQLAlchemy Logging level')
        parser.add_argument('--stderr_log_level', action='store', type=str, choices=log_levels, default='warn', help='stderr (console) Logging level')
        parser.add_argument('--if_ip', action='store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. This is used solely for direct UDP communications with the FPGA. If not specified, the system will use the same interface that communicates with the ARM processor.')

        parser.add_argument('-y', '--yamlfile','--yaml_file', action = 'store', type=str, default=None,  help='Yaml file with list of boards and their respective IP addresses and handlers.')
        parser.add_argument('--hwm_name', action = 'store', type=str, default=None,  help='Name of the hardware map to load from the YAML file (the YAML file must be structured as a dictionary)')
        parser.add_argument('-i', '--iceboards', action='store', nargs='*', type=str, default=[], help="Space-separated list of iceboards, which can be specified byip address (e.g. 10.10.10.7), hostname (e.g. iceboard0007.local) if a mDNS client is running locally, or by serial number (e.g. 0007 or simply 7) in which case active mDNS discovery will be done")
        parser.add_argument('-c', '--icecrates', action='store', nargs='*', type=str, default=[], help="Space-separated list of icecrate serial numbers.  Discover and adds all boards in the specified serial number")
        parser.add_argument('--subarrays', action = 'store', type=int, nargs='*', help='Keep in the hardware map only the boards that are in the specified subarrays. This applies only to iceboards that are specified in a YAML file.')
        parser.add_argument('-x', '--exclude_iceboards', action='store', nargs='*', type=str, default=[], help="Space-separated list of iceboards serials to exclude ")
        # parser.add_argument('--slots', action='store', type=str, nargs='*', help="Select only boards in the specified slot(s)")
        parser.add_argument('--prog', action='store', type=int, nargs='?', const=0, default=-1, help='Programs the FPGA if not already programmed. --prog 1 forces the FPGA programming even if the firmware is already programmed')
        parser.add_argument('-b', '--bitfile', action='store', type=str, default=default_bitfile,  help='Filename of the bitfile used to to program the FPGAs')
        parser.add_argument('--ping', action='store', type=int, default=1, help="1: Check if Tuber is responding. 0: Check but ignore. ")
        parser.add_argument('--mdns_timeout', action='store', type=float, default=2, help="Time to wait for mDNS discovery replies")


        # parser.add_argument('-s', '--subarray', action='store', nargs='+', type=int, help='Space-separated list of subarrays to include')
        parser.add_argument('--no_mezz', action='store_true', help='Do not attempt to auto-detect the mezzanines')
        # parser.add_argument('-n', '--init', action='store', type=int, default=-1, help='Initialization level: -1: Just create sockets, 0: connect and read only. 1: initialize hardware')
        parser.add_argument('-o', '--open', action='store', type=int, nargs='?', const=1, default=-1, help='Opens communication with the FPGAs, create the Python objects reprenting the firmware, and initialize the firmware. --open 0 skips the firmware initialization phase')
        parser.add_argument('-f', '--sampling_frequency', action='store', type=float, default=800, help='Sampling frequency of the ADC in MHz')
        parser.add_argument('-w', '--data_width', action='store', type=int, choices=[4,8], default=4, help='Data width of each Re and Im component of the channelizer output')
        parser.add_argument('-g', '--frames_per_packet','--group_frames',  action='store', type=int, default=4, help='Number of frames to group before sending to the GPU or FPGA correlator. The total size of the frame, including the header and ethernet obverhead, cannot exceed 8 kibytes.')
        parser.add_argument('-e', '--enable_gpu_link', action='store', type=int, default=0, help='Enables the GPU link transmission')
        # parser.add_argument('--sn', action='store', type=int, default=7, help='Serial number of the Iceboard')

        args = parser.parse_args(argv)  # We always parse even if argv is not specified so we have default values

        # Bring all keywoards argument into the args namespace
        for k, v in kwargs.items():
            setattr(args, k, v)



        __main__._host_interface_ip_addr = args.if_ip


        # -------------------------------
        # Set-up logging
        # -------------------------------


        # Make sure SQLAlchemy does not log too much
        sql_logger = logging.getLogger('sqlalchemy.engine.base.Engine')
        sql_logger.setLevel(log_levels[args.sql_log_level])

        # Set-up chFPGA loggers
        if args.log_target == 'stream':
            log_handler = logging.StreamHandler()
        elif args.log_target == 'syslog':
            log_handler = logging.handlers.SysLogHandler()
        else:
            log_handler = logging.FileHandler(args.log_target)

        self.logger = logging.getLogger('')
        self.logger.handlers = []  # Clear all existing handlers
        self.logger.setLevel(logging.DEBUG)  # pass all messages to the handlers which will filter what they want
       # Set-up log for this test run
        log_handler.setLevel(log_levels[args.log_level])
        self.logger.addHandler(log_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(log_levels[args.stderr_log_level])
        self.logger.addHandler(stream_handler)

        self.logger.info('%r: ------------------------' % self)
        self.logger.info('%r: C H I M E A R R A Y' % self)
        self.logger.info('%r: ------------------------' % self)
        self.logger.info('%r: Called with: %s' % (self, ', '.join('%s=%s' % (key, repr(value)) for (key,value) in args.__dict__.items())))


        # -------------------------------
        # Load YAML file
        # -------------------------------
        # The YAML file may contain any configuration data that will be
        # accessible by the user, which includes hardware maps that will be
        # extracted below
        if args.yamlfile:
            self.logger.info('%.32r: Loading YAML file %s' % (self, args.yamlfile))
            print 'Loading YAML file %s' % args.yamlfile
            with open(args.yamlfile, 'rb') as yamlfile:
                self.yaml = load_yaml(yamlfile)
        else:
                self.yaml = None

        # If the YAML file contains contrictor arguments, add them to the argument list
        chimearray_params_dict_name = 'chimearray_params'
        if isinstance(self.yaml, dict) and chimearray_params_dict_name in self.yaml:
            for (k, v) in self.yaml[chimearray_params_dict_name].items():
                if not hasattr(args, k):
                    raise KeyError("YAML parameter '%s' does not exist" % k)
                setattr(args, k, v)

        # Fix up a few parameters for convenience
        if isinstance(args.iceboards, (str, int)):
            args.iceboards = [args.iceboards]
        args.iceboards = [self._to_integer(x) for x in args.iceboards]

        if isinstance(args.icecrates, (str, int)):
            args.icecrates = [args.icecrates]
        args.icecrates = [self._to_integer(x) for x in args.icecrates]

        # -------------------------------
        # Create a hardware map
        # -------------------------------
        # If a hardware map exists in the yaml file, use it, otherwise create a new blank one
        # If the yaml file is a single hardware map, get it
        self.hwm = None
        if isinstance(self.yaml, Session):
            self.hwm = self.yaml
            self.yaml = None
        elif isinstance(self.yaml, list):
            hwm = [obj for obj in self.yaml if isinstance(obj, Session)]
            if len(hwm) == 1:
                self.hwm = hwm[0]
                self.yaml.remove(self.hwm)
            elif len(hwm) > 1:
                raise RuntimeError("YAML file is a list containing multiple hardware map and I don't know which one to use")
        elif isinstance(self.yaml, dict) and args.hwm_name:
            if args.hwm_name in self.yaml:
                hwm = self.yaml.pop(args.hwm_name)
                if not isinstance(self.yaml, Session):
                    raise RuntimeError("YAML entry %s is not a hardware map" % args.hwm_name)
            else:
                raise RuntimeError("YAML does not contain a hardware map named %s" % args.hwm_name)

        # If no hardware map was found in the YAML file, create an empty one
        if not self.hwm:
            self.hwm = HardwareMap()  # Create empty hardware map


        # Remove boards that are not in the specified subarray
        if args.subarrays:
            ib_not_in_subarray = self.hwm.query(IceBoardPlus).filter(~IceBoardPlus.subarray.in_(args.subarrays))
            for ib in list(ib_not_in_subarray):  # make sure the list does not change during the loop
                print ("%r (subarray '%s') is not in the target subarray list %s. It is removed from the YAML hardware map."  # That comment should be if verbose=1
                                   % (ib, ib.subarray, args.subarrays))
                self.hwm.delete(ib)
            self.hwm.flush()

        # Check if the boards is the selected subarray actually exist on the
        # network. If not, delete them from the hardware map.
        if args.ping:
            self.logger.info('%.32r: Pinging IceBoards specified in YAML file' % (self))
            ib_to_ping = self.hwm.query(IceBoardPlus).as_dict()  # use as_dict so ib_to_ping does not change as we delete boards from the hwm
            if ib_to_ping:
                ping_results = ib_to_ping.ping()  # asynchronous parallel call to all boards
                self.logger.debug('%.32r: Ping results are %s' % (self, ping_results))
                for i, ping_successful in enumerate(ping_results):
                    ib = ib_to_ping[i]
                    if not ping_successful:
                        print ("%r could not be found at '%s'. It is removed from YAML hardware map."
                                           % (ib, ib.tuber_uri))
                        self.logger.debug('%.32r: Deleting %r from the YAML hardware map' % (self, ib))
                        self.hwm.delete(ib)
                self.hwm.flush()


        # Add iceboards that are explicitely listed as hostnames
        if args.iceboards:
            for hostname in [ib for ib in args.iceboards if '.' in str(ib)]:
                # ip_addr = socket.gethostbyname(hostname)  # convert hostname to IP address for faster Tuber access
                ip_addr = hostname
                ib = IceBoardPlus(hostname=ip_addr)
                self.hwm.add(ib)
                self.hwm.flush()
                # Explicitely listed boards must exist on the network
                if args.ping and not ib.ping():
                    raise RuntimeError("%r could not be found at '%s'"
                                       % (ib, ib.tuber_uri))


        # Complete serial, crate and slot information on IceBoard that miss
        # that information. All boards in the hardware map at this point have
        # a valid hostname, so this information is obtained through the ARM
        # (i.e without using mDNS and pybonjour).
        ib_without_serial = self.hwm.query(IceBoardPlus).filter(IceBoardPlus.serial==None)
        if ib_without_serial.count():
            ib_without_serial.discover_serial()

        ib_without_crate = self.hwm.query(IceBoardPlus).filter(or_(IceBoardPlus.crate==None, IceBoardPlus.slot==None))
        if ib_without_crate.count():
            ib_without_crate.discover_crate()

        # If requested, discover additional boards and crates on the network using mDNS and add those to the hardware map
        iceboards_to_discover = [ib for ib in args.iceboards if '.' not in str(ib)]
        if '*' in str(iceboards_to_discover):
            iceboards_to_discover = '*'
        icecrates_to_discover = args.icecrates
        if '*' in str(icecrates_to_discover):
            icecrates_to_discover = '*'

        if icecrates_to_discover or iceboards_to_discover:
            print 'Discovering IceBoards %s and IceCrates %s...' % (iceboards_to_discover, icecrates_to_discover)
            self.print_flush()
            mdns_discover(self.hwm,
                          icecrates=icecrates_to_discover,
                          iceboards=iceboards_to_discover,
                          timeout=args.mdns_timeout)

        # Remove iceboards to be excluded (by serial number)
        if args.exclude_iceboards:
            for ib in self.hwm.query(IceBoardPlus):
                try:
                    serial = str(int(ib.serial))
                except (TypeError, ValueError):
                    serial = ib.serial
                if serial in args.exclude_iceboards or ib.serial in args.exclude_iceboards:
                    self.hwm.delete(ib)
            self.hwm.flush()

        # Hardware map is complete

        # Query all iceboards
        ib = self.hwm.query(IceBoardPlus).order_by(IceBoardPlus.slot)
        ic = self.hwm.query(IceCrate).order_by(IceCrate.serial)

        if not ib.count():
            raise RuntimeError('No Iceboards matching the selection criteria were found')

        if not ic.count():
            print 'There are no IceCrates in the hardware map!'

        print 'The following IceBoards are in the hardware map:'
        for i in ib:
            crate_name = '%s SN%s' % (i.crate.part_number, i.crate.serial) if i.crate else 'No crate'
            print 'Crate %s, slot %2s: Iceboard SN%s at %s (ping =%s)' % (crate_name, i.slot, i.serial, i.hostname, i.ping())

        # Augment the arg Namespace with conveniently proprocessed elements
        self.ib = Ccoll(ib)
        self.ic = Ccoll(set(c for c in ib.crate if c))

        # chFPGA_controller.register_fpga_bitstream(fpga_bitstream)

        if self.ib:
            ib.check_tuber_version()  # Check if the board is running a compatible ARM firmware
            ib.set_handler(chFPGA_controller)
            ib.set_cache() # we have a new handler, so update its cached ORM object values
            # ib.set_handler(IceBoardPlusHandler, fpga_bitstream)

            # Configure the FPGA with the bitstream associated with the handler
            if args.prog > -1:
                print 'Configuring FPGAs...'
                # Associate the bitstream with the target Handler
                self.fpga_bitstream = FpgaBitstream(args.bitfile)
                ib.register_fpga_bitstream(self.fpga_bitstream)
                ib.set_fpga_bitstream(force=args.prog)
                print 'Done configuring FPGAs'

            # Auto-discover mezzanines and add them to the hardware map McGill
            # MGADC08 can only be discovered if the FPGA is programmed with the
            # chFPGA_controller firmware

            if not args.no_mezz:
                for ib in self.ib:
                    if ib.is_fpga_programmed():
                        print 'Discovering Mezzanines...'
                        ib.discover_mezzanines()
                self.hwm.flush()
                ib.set_cache()

        print
        print 'Updated hardware map, with mezzanine info:'
        for i in self.ib:
            mezz_name = ['%s SN%s' % (m.__ipmi_part_number__, m.serial) if m else 'None' for m in [i.mezzanine.get(1, None), i.mezzanine.get(2, None)]]
            crate_name = '%s SN%s' % (i.crate.part_number, i.crate.serial) if i.crate else 'No crate'
            print 'Crate %s, slot %2s: Iceboard SN%s at %s (ping =%s), Mezz1=%s, Mezz2=%s' % (crate_name, i.slot, i.serial, i.hostname, i.ping(), mezz_name[0], mezz_name[1])
        self.print_flush()

        print
        if self.ib and args.open > -1:
            print 'Initializing firmware (calling ib.open())'
            self.ib.open(adc_delay_table=ADC_DELAY_TABLE,
                         init=args.open,
                         sampling_frequency=args.sampling_frequency * 1e6,
                         reference_frequency=10e6,
                         data_width=args.data_width,
                         group_frames=args.frames_per_packet,
                         enable_gpu_link=args.enable_gpu_link)
            self.set_sync_method(method='distributed_time', source='bp_trig')

            if self.ic:
                self.ic.init()

        self.print_flush()


        # import all command line argument values into this object
        self.args = args
        for k, v in args._get_kwargs():
            setattr(self, k, v)

        print 'Done processing arguments'

    @staticmethod
    def _to_integer(x):
        try:
            return int(x)
        except ValueError:
            return x

    def print_flush(self):
        sys.stdout.flush()


    def dns_resolve(self, hostnames='iceboard0077.local', timeout=1):
        """ This is an experimental method to concurrently resolve the  IP
        address of boards without having to contend with the fixed timout of
        getaddrinfo(). This does not work yet, as requests seem to block
        anyway even with the Async resolver.
        """
        if isinstance(hostnames, str):
            hostnames = [hostnames]
        io_loop = IOLoop()
        resolver = Resolver()
        futures = [resolver.resolve(h, 9000) for h in hostnames]

        def stop_when_all_resolved(one_future):
            print [ff.done() for ff in futures]
            self.print_flush()
            return
            # if all(f.done() for f in futures):
            #     io_loop.stop()
            # print one_future.exception() or one_future.result()
        for f in futures:
            io_loop.add_future(f, stop_when_all_resolved)
        io_loop.add_timeout(io_loop.time() + timeout, lambda: io_loop.stop())
        io_loop.start()
        ip_addr = [None if not f.done() or f.exception() else dict(f.result())[socket.AF_INET][0] for f in futures]
        for f in futures:
            f.cancel()
        resolver.close()
        return (resolver, futures, ip_addr)

    def __getattr__(self, name):
        """
        Redirects all attributes access to the hardware map (Session) object.
        """
        return getattr(self.hwm, name)

    def __dir__(self):
        # return type(self).__dict__ + self.__dict__ + dir(self._hwmap)
        return dir(self.hwm) + self.__dict__.keys()

    def __repr__(self):
        """ Short string representing this object and suitable to use as a tag in a syslog entry"""
        return self.__class__.__name__

    def get_hwm_info(self):
        string = '%s object with the following hardware map:\n' % self.__class__.__name__
        for i in ib:
            mezz = ['%s SN%s' % (m.__ipmi_part_number__, m.serial) if m else 'None' for m in [i.mezzanine.get(1,None), i.mezzanine.get(2,None)]]
            string +='   Crate SN%s, slot %2i: Iceboard SN%s at %s (ping =%s), Mezz1=%s, Mezz2=%s\n' % (i.crate.serial if i.crate else None, i.slot, i.serial, i.hostname, i.ping(), mezz[0], mezz[1])
        return string

    def set_operational_mode(self, mode):
        """
        Set the operational mode of the array.

        'raw_time': Each boards stream raw 8-bit time samples from channels
                    0-7 to the corresponding GPU ports.
        """

        if mode == 'raw_time':
            self.ib.set_fft_bypass(True)
            self.ib.set_scaler_bypass(True)
            self.init_shuffle(cb1_bypass=True, bp_bypass = True, cb2_bypass = True)


    def set_sync_method(self, method='distributed_time', source='bp_time', master=None, master_time_source=None):
        """ Sets the global syncing method, and setup the boards accordingly.

        method: (string)
            - 'distributed_time': All boards receive and decode IRIG-B time
              signal and trigger a SYNC event at a target time sent to every
              board in the array.

              The IRIG-B time signal can come from either of the backplane
              SMAs TRIG (``source='bp_trig'``) or TIME (``source='bp_time'``).
              If ``source='bp_gpio_int'``, a master board must be specified
              and the internal GPIO_INT backplane line is used to send the
              master's board IRIG-B signal to all boards in the crate.


              If a master board ``master`` is specified, the master board is
              configured to output an IRIG-B signal on its SMA connector or on
              the backplane GPIO_INT line depending on the value of
              ``source``. ``master_time_source`` determines the source of the
              IRIG-B signal provided by the master board, which can come from one of
              the backplane SMAs or from its IRIG-B test signal generator.

              If no master board is specified, the IRIG_B must be generated by
              an external source (like a GPS receiver) and must be connected
              to the specified backplane SMA.


            - 'centralized_time_trigger': All boards receive a SYNC trigger
              from the master board when its IRIG-B decoder reaches the target
              time.

              Depending on ``source``, the trigger signal can be received from
              the backplane SMA connectors or the BP_GPIO_INT backplane line.

              A master board ``master`` must be specified and is configured to
              generate the time-based trigger signal on its BP_GPIO_INT line
              or on its SMA connector (in which case a cable must connect the
              master board and the backplane). The master board's IRIG-B
              signal source is set by ``master_time_source`` and can be set to
              come from the backplane or its internal test generator.

            - 'centralized_soft_trigger': All boards receive a SYNC trigger
              from the master when it receives a software command to do so.
              The trigger signal is received from the backplane SMA input
              connectors. The master board is configured to generate this
              trigger signal on its SMA connector.


        source: (string): source of the time or trigger signal for the slave boards.
            - 'bp_gpio_int': the signal comes from the internal backplane
              GPIO_INT line. The master board must be specified, and will be
              configured to generate this signal.
            - 'bp_time': the signal comes from the backplane TIME SMA.
            - 'bp_trig': the signal comes from the backplane TRIG SMA.

        master_time_source: (string): source of the time signal that the
            master board will send to its SMA or BP_GPIO_INT backplane line.
            Not applicable for soft trigger, must be specified for centralized
            time triggers, and may be specified for distributed time syncing.
            - 'bp_time': the time signal comes from the backplane TIME SMA.
            - 'bp_trig': the time signal comes from the backplane TRIG SMA.
            - 'irigb_gen': the time signal comes from the internal IRIG-B test signal generator.

        master: IceBoard that is to be configured to generate the time or trigger signals. Can be omitted only in distributed time if an external IRIG-B source is used.
            It is assumed that the SMA output
            is connected to the backplane TRIG or TIME input.


        The boards start their sync process on the next rising edge of the 10
        MHz refecence clock following when either the target irigb time is
        reached or the trigger signal is received. These events are configured
        to occur between two reference clock edges in order to guarantee
        detection on the same edge across the entire array.


          Sync Method                         source                           master     master_time_source
        ------------------------          -------------------------------   ------------  -----------------------------
        distributed_time (ext source)     bp_time | bp_trig                  Not needed           ---
        distributed_time (master source)  bp_time | bp_trig | bp_gpio_int      Needed     bp_time | bp_trig | irigb_gen
        centralized_time_trigger          bp_time | bp_trig | bp_gpio_int      Needed     bp_time | bp_trig | irigb_gen
        centralized_soft_trigger          bp_time | bp_trig | bp_gpio_int      Needed             ---

        """
        self.sync_master = master
        self.sync_method = method

        if method == 'distributed_time':
            self.ib.set_sync_source('irigb')
            self.ib.set_irigb_source(source)
            if source in ['bp_time', 'bp_trig']:
                if bool(master) != bool(master_time_source):
                    raise ValueError('The master board that generates the the time signal on its SMA connector and its time source must be specified')
                if master:
                    master.set_user_output_source(master_time_source)
            elif source in ['bp_gpio_int']:
                if not master or not master_time_source:
                    raise ValueError('With the bp_io_int source, the master board and its time source must be specified')
                if master_time_source not in ['irigb_gen']:
                    raise  NotImplementedError("The 'bp_gpio_int' source currently only supports the master_time_source=irigb_gen'")
                self.ib.set_bp_gpio_int_output_source(None)  # Make sure no other board is driving the backplane line
                master.set_bp_gpio_int_output_source(master_time_source)
        elif method == 'centralized_time_trigger':
            if not master or not master_time_source:
                raise ValueError('In the centralized time trigger mode, the master board and its time source must be specified')
            self.ib.set_sync_source(source)
            master.set_irigb_source(master_time_source)
            master.set_user_output_source('irigb_trig')
        elif method == 'centralized_soft_trigger':
            if not master:
                raise ValueError('In the centralized soft trigger mode, a master board must be specified')
            if master_time_source:
                raise ValueError('In the centralized soft trigger mode, no master_time_source must be specified')
            self.ib.set_sync_source(source)
            master.set_user_output_source('sync')
        else:
            raise ValueError("Unknown syncing method '%s'" % method)

    def sync(self, delay=2, check=True):
        """ Generate a SYNC event across the whole array based on the syncing method set by ``set_sync_method()``.

        If ``check`` is True, the method will read the SYNC counters on every
        board to confirm that the SYNC really happened everywhere.
        """

        if check:
            sync_ctr_before = self.ib.REFCLK.SYNC_CTR

        if self.sync_method == 'centralized_soft_trigger':
            self.sync_master.remote_sync()
        elif self.sync_method == 'centralized_time_trigger':
            dt = self.sync_master.get_irigb_time()
            print 'Triggering SYNC at ', dt.isoformat()
            self.sync_master.set_irigb_trigger_time(dt, delay=delay)
            t0 = time.time()
            while self.sync_master.is_irigb_before_trigger_time():
                if time.time() - t0 > delay+1:
                    raise RuntimeError('Timout while waiting for the IRIG-B-based SYNC to complete')
        elif self.sync_method == 'distributed_time':
            dt = self.ib[0].get_irigb_time()
            print 'Triggering SYNC in %i seconds at %s' % (delay,  dt.isoformat())
            self.print_flush()
            self.ib.set_irigb_trigger_time(dt, delay=delay)
            t0 = time.time()
            while any(self.ib.is_irigb_before_trigger_time()):
                if time.time() - t0 > delay+1:
                    raise RuntimeError('Timout while waiting for the IRIG-B-based SYNC to complete')
        else:
            raise ValueError("Unknown syncing method '%s'" % self.sync_method)

        if check:
            sync_ctr_after = self.ib.REFCLK.SYNC_CTR
            bad_ib = [ib for i,ib in enumerate(self.ib) if (sync_ctr_after[i] - sync_ctr_before[i]) & 0xf != 1]
            if bad_ib:
                raise RuntimeError('The following IceBoards did not SYNC properly: %s' % (','.join(repr(ib) for ib in bad_ib)))

    def set_noise_injection(self, ni_board, ni_enable=False, ni_offset=0, ni_high_time=8388608, ni_period=16777216):
        """ Configure noise injection gating signal"""
        if ni_enable:
            ni_board.set_user_output_source('pwm')
            ni_board.set_frame_pwm(ni_offset, ni_high_time, ni_period)

    def init_shuffle(self,
                     dsmap=range(16),
                     frames_per_packet=1,
                     cb1_lanes=4, cb1_bins=16, cb1_bypass=False,
                     bp_bypass=False,
                     cb2_lanes=2, cb2_bins=1, cb2_bypass=False,
                     remap=True,
                     ):
        """ Setup the crossbars and data shuffling in every board of the array.

        The GTX receivers that have no corresponding transmitter is put in
        reset so it won't generate random packets into the following crossbar.
        """

        tx_list = []

        crate_set = set(ib.crate for ib in self.ib)
        if len(crate_set) != 1:
            raise RuntimeError('All boards must be in the same crate. The provided set of Iceboards have the following crates: %r' % crate_set)
        crate = crate_set.pop()

        self.logger.info('%.32r: Configuring crate-wide data shuffling with frames_per_packet=%i, cb1_lanes=%i, cb1_bins=64, cb2_lanes=%i, cb2_bins=%i, cb2_bypass=%s, bp_bypass=%s' % (crate, cb1_lanes, cb1_bins, cb2_lanes, cb2_bins, bool(cb2_bypass), bool(bp_bypass)))

        # Set-up transmitters
        for i, ib in enumerate(self.ib):
            self.logger.info('%.32r: **** Initializing transmitters for Slot %02i (IceBoard SN%s) ****' % (crate, ib.slot, ib.serial))
            ib.set_corr_reset(0)

            tx_list.append((ib.slot, 0))  # Register Bypass lane (lane 0) as a transmitter in this slot
            for j, gtx in enumerate(ib.BP_SHUFFLE.gtx):
                gtx.TXINHIBIT = 0
                tx_list.append((ib.slot, j+1))

            if remap:
                ib.CROSSBAR2.set_lane_map(self.compute_lane_map(ib))

            # Initialize the crossbars to select and send data in a specific format
            ib.init_crossbars(dsmap, frames_per_packet=frames_per_packet, cb1_lanes=cb1_lanes, cb1_bins=cb1_bins, cb1_bypass=cb1_bypass, cb2_lanes=cb2_lanes, cb2_bins=cb2_bins, cb2_bypass=cb2_bypass, remap=remap, bp_bypass=bp_bypass)

        # set-up receivers
        for i, ib in enumerate(self.ib):
            # Disable all receivers for which there are no transmitters
            for j, gtx in enumerate(ib.BP_SHUFFLE.gtx):
                rx = (ib.slot, j+1)
                tx = ib.crate.get_matching_tx(rx)

                # disable receivers that have no corresponding transmitters
                if tx in tx_list:
                    gtx.USER_GTRXRESET = 0
                else:
                    gtx.USER_GTRXRESET = 1
                    # gtx.USER_RESET = 1

            # ib.CROSSBAR2.SOF_WINDOW_STOP = 25
            ib.BP_SHUFFLE.reset_rx_equalizers()
            ib.REFCLK.sync() # needed

        # Print links
        for ib in self.ib:
            for i in range(ib.NUMBER_OF_CROSSBAR_OUTPUTS):
                rx = (ib.slot, i)
                tx = ib.crate.get_matching_tx(rx)
                if tx in tx_list:
                    self.logger.info('%.32r: %s is receiving from %s' % (ib.crate, rx, tx))
                else:
                    self.logger.info('%.32r: %s has no corresponding transmitter' % (ib.crate, rx,))


        # sync boards
        #soft_sync(c, sync_board)
        self.sync(delay=2)


    @staticmethod
    def compute_lane_map(ib):
        """ Computes a lane mapping vector that will compensate for the
        backplane connectivity on the specified IceBoard to obtain data
        from slot 1 in lane 0, slot 2 in lane 1 etc.

        The IceBoard must be connected to an identified backplane in order to
        obtain the slot number and backplane connectivity information.
        """
        lane_map = np.zeros(16, dtype=np.int8)
        for i in range(16):
            rx = (ib.slot, i)
            tx = ib.crate.get_matching_tx(rx)
            # print '%s is receiving from %s' % (rx, tx)
            lane_map[tx[0]-1] = i
        return lane_map

    def test_sync(self):
        c = list(self.ib)
        sync_board = self.sync_master

        sync_ctr = np.zeros(len(c), dtype=int)
        for i,bb in enumerate(c):
            bb.REFCLK.set_sync_source('bp')#bb.REFCLK.SLAVE=1
            sync_ctr[i] = bb.REFCLK.SYNC_CTR

        fail=0
        for test_number in range(10):
            print 'Trial # %i: Sending SYNC pulse from Slot %02i (Iceboard SN%s)' % (test_number+1, sync_board.slot, sync_board.serial)
            sync_board.REFCLK.sync()
            for i,bb in enumerate(c):
                new_sync_ctr = bb.REFCLK.SYNC_CTR
                diff = (new_sync_ctr - sync_ctr[i]) & 0xF
                sync_ctr[i] = bb.REFCLK.SYNC_CTR
                fail += bool(diff!=1)
                print '    Slot %02i (Iceboard SN%s): Sync counter = %2i, diff = %2i => %s' % (bb.slot, bb.serial, new_sync_ctr, diff, ('FAILED!', 'PASS')[bool(diff==1)])
            time.sleep(0.2)
        if fail:
            print 'SYNC Test has FAILED!'
        else:
            print 'SYNC Test has PASSED!'

    def init_gains(self):
        import pickle
        for cc in self.ib:
            try:
                g_array = pickle.load(open('/home/chime/ch_acq/gains_'+str(cc.GPIO.FPGA_SERIAL_NUMBER)+'.pkl', 'rb'))
            except:
                g_array = pickle.load(open('/home/chime/ch_acq/gains.pkl', 'rb'))
                print 'Could not find gain settings for %r, sn %i. Using default gain settings.' % (cc, cc.get_fpga_serial_number())
            print 'Setting gains on IceBoard SN%s' % cc.serial
            cc.set_gain(g_array)

    def soft_sync(self, sync_board):
        """ Synchronize all boards"""
        boards = list(self.ib)
        print 'Masking ADC data before sync'
        for ib in boards:
            for ant in ib.ANT:
                ant.ADCDAQ.BYTE_MASK = 0

        print 'Initiating global sync'
        sync_board.REFCLK.sync()

        print 'Unmasking ADC data'
        for ib in boards:
            for ant in ib.ANT:
                ant.ADCDAQ.BYTE_MASK = 255

    # def time_soft_sync(self, sync_board, delay):
    #     """ Synchronize all boards"""

    #     boards = list(self.ib)
    #     print 'Masking ADC data before sync'
    #     for ib in boards:
    #         for ant in ib.ANT:
    #             ant.ADCDAQ.BYTE_MASK = 0

    #     # Get current time
    #     current_time = sync_board.get_irigb_time()
    #     print 'Setting IRIG-B sync after %d seconds' %delay
    #     # Send sync pulse delay seconds in the future
    #     sync_board.set_irigb_trigger_time(current_time, delay)

    #     print 'Unmasking ADC data'
    #     for ib in boards:
    #         for ant in ib.ANT:
    #             ant.ADCDAQ.BYTE_MASK = 255

    # def irigb_sync(self, delay):
    #     """ Synchronize all boards"""

    #     # Get current time
    #     current_time = self.ib[0].get_irigb_time()
    #     print 'Setting IRIG-B sync after %d seconds' %delay
    #     for ib in self.ib:
    #         ib.set_irigb_trigger_time(current_time, delay)


    def print_temperatures(self):
        t = [(b.slot, b.serial, b.SYSMON.temperature()) for b in self.ib]
        t.sort()
        for (slot, serial_number, fpga_temp) in t:
            print 'Slot %2i (SN%s): FPGA %2.1f C' % (slot, serial_number, fpga_temp)

    def set_adc_mask(self, value):
        for ib in self.ib:
            for ant in ib.ANT:
                ant.ADCDAQ.BYTE_MASK = value

    def print_fmc_power(self):
        sensor_list = ['FMCA_12V0', 'FMCA_3V3','FMCA_VADJ','FMCB_12V0','FMCB_3V3','FMCB_VADJ']

        for b in self.ib:
            for sensor in sensor_list:
                (voltage, current, power) = b.hw.get_power(sensor)[sensor]
                if voltage is not None:
                    print '%0.1fV@%0.2fA=%0.1fW ' % (voltage, current, power),
                else:
                    print 'None                 ',
            print


    def detect_backplane_links(self, tx_power=7, print_=True):
        """ Setup all boards on the array to send test pattern over the
        backplane link and detect  from which slot/lane every board is
        receiving data.

        The test is performed only on IceBoards that are installed in crates and whose FPGA has been programmed and initialized. Other boards are ignored.

        For now, this test works only if all boards are in a single crate.
        """
        # select only boards on crates and that are open
        array = Ccoll(ib for ib in self.ib if ib.is_open() and ib.crate and ib.slot)

        if not array:
            raise RuntimeError('There are no boards that are opened() AND connected in a crate')

        # Check if the board are all on a single crate
        if len(set(array.crate)) != 1:
            raise RuntimeError('Sorry, this method currently can work on only one crate. The currently active boards span multiple crates %s' % list(set(array.crate)))

        active_slots = [ib.slot for ib in array]
        if len(set(active_slots)) != len(active_slots):
            raise SystemError('Slot numbers are not unique!')

        print 'Setting Transmitted ID'
        for ib in array:
            ib.BP_SHUFFLE.TX_DATA_MSB = 0xFF00 + ib.slot
            for gtx_number, g in enumerate(ib.BP_SHUFFLE.gtx):
                g.SOURCE_SEL = 1 # 0:Send TXDATA , 1: SEND 10G Ethernet test packet
                g.LOOPBACK = 0
                g.TXPRBSSEL=0
                g.RXPRBSSEL=0
                g.TXDIFFCTRL = tx_power
                g.TX_DATA_LSB = gtx_number + 1
                g.TXHEADER=1
                g.CAPTURE_ENABLE = 1
                g.TXPRECURSOR = 0b00000 #DFE cannot compensate pre-cursor
                g.TXPOSTCURSOR = 0b00000
                g.RXLPMEN = 0 #Go to DFE mode instead of LPM
                # g.RXMONITORSEL = 1 # 1=AGC, 2=UL, 3=VP loop
                # g.RX_DEBUG_CFG = 0b1011 << 2
                #g.DMONITOR_CFG1 = 0
                #g.DMONITOR_CFG0 = (0b1<<15) | (0x0080 <<1) | 1
                # Configure DMONITOR to read the AGC gain
                # g.DMONITOR_SELECT = 1
                # g.PCS_RSVD_ATTR_BIT6 = 1
                #old=g.read_drp(0x6f)
                #g.write_drp(0x6f,old | 1<<6)
                #g.RXDFEOVRD=1
                #g.write_drp(0x1d, 0x00ea)

        print 'Resetting the GTXes'
        for ib in array:
            for g in ib.BP_SHUFFLE.gtx:
                g.RXDFELPMRESET = 1
                g.RXDFELPMRESET = 0
            time.sleep(0.1)

        print 'Checking received data'
        link_list = []
        link_matrix = [[None]*17 for x in range(17)]
        serial_number = ['N/A'] * 17
        for ib in array:
            #print 'Slot %i' % (ib.slot)
            dest_slot = ib.slot
            serial_number[dest_slot-1] = ib.serial
            for gtx_number, g in enumerate(ib.BP_SHUFFLE.gtx):
                dest_lane = gtx_number + 1
                dest = (dest_slot, dest_lane)
                expected_source = ib.crate.get_matching_tx(dest)
                source_present = expected_source[0] in active_slots
                for trial in range(3):
                    rxdata = g.get_rxdata()
                    #print '   Slot %i Lane %i received %08X' % (    ib.slot, lane+1,  rxdata)
                    source_slot = int((rxdata >> 8) & 0xFF)
                    source_lane = int((rxdata) & 0xFF)
                    source = (source_slot, source_lane)
                    source_valid = (rxdata >> 16) == 0xFFFF
                    maybe = (rxdata != 0x55555555) and (rxdata != 0xAAAAAAAA)
                    if source_valid:
                        break

                if source_valid:
                    print 'Slot %2i Lane %2i is receiving data from Slot %2i Lane %2i (received word = 0x%08X, RXMONITOROUT= %x, DMONITOROUT=%x)' % (dest_slot, dest_lane, source_slot, source_lane, rxdata, g.RXMONITOR, g.DMONITOROUT)
                    link_matrix[dest_slot][dest_lane] = 'S%02iL%02i' % (source_slot, source_lane)
                elif maybe:
                    print 'Slot %2i Lane %2i is receiving some data but cannot determine source (received word = 0x%08X, RXMONITOROUT= %x, DMONITOROUT=%x)' % (dest_slot, dest_lane, rxdata, g.RXMONITOR, g.DMONITOROUT)
                    link_matrix[dest_slot][dest_lane] = 'S??L??'
                else:
                    link_matrix[dest_slot][dest_lane]='  ()  '

                if not source_valid or not source_present or source != expected_source:
                    if source_present:
                        link_matrix[dest_slot][dest_lane] += '/S%sL%s  ' % expected_source
                    else:
                        link_matrix[dest_slot][dest_lane] += '/(S%sL%s)' % expected_source

                link_list.append((source, dest))
        if print_:
            # Print a slot map
            print 'Slot-> ' + ' '.join(['%-15i' % (slot+1) for slot in range(16)])
            print 'S/N -> ' + ' '.join(['%-15s' % (sn) for sn in serial_number])
            print 'Lane   ' + ' '.join(['%-15s' % '----------' for x in range(16)])

            for dest_lane in range(1,16):
                print '%6i ' % (dest_lane),
                for dest_slot in range(1,17):
                    print '%-15s' % link_matrix[dest_slot][dest_lane],
                print

        return link_list

    def get_backplane_links(self, print_=True):
        """ Return all backplane links that **should** be available given the currnet collection of crates.
        """

        # get all crates associated with the current set of iceboards
        crates = set(ib.crate for ib in self.ib if ib.crate)

        links = {}
        for cr in crates:
            links[cr.id] = list(itertools.chain(*(ib.BP_SHUFFLE.get_links() for ib in cr.slot.values())))
        return links



    def get_link_map(self):
        link_map = {}

        for ib in self.ib:

            # Get backplane links
            link_map.update(ib.BP_SHUFFLE.get_link_map())

            # Add GPU links
            crate_id = ib.get_crate_id()
            slot = ib.slot
            for tx_lane, gtx in enumerate(ib.GPU.gtx):
                rx_lane = (tx_lane + 4) % 8
                link = ('GPU', (crate_id, slot, tx_lane), (crate_id, slot, rx_lane))
                tx = ib.GPU.gtx[tx_lane]
                rx = ib.GPU.gtx[rx_lane]
                link_map[link] = (tx, rx)
        return link_map

    def get_ber(self, link_list=None, period=0.1, tx_power=None, print_=True):

        from threading import Thread

        link_map = self.get_link_map()

        if isinstance(link_list, str):
            link_list = [link for link in link_map.keys() if link[0] == link_list]

        link_list.sort(key=lambda (lt, (sc, ss, sl), (dc, ds, dl)): ss * 16 + ds)

        def one_link_ber(l_map, l, output):
            (link_type, (sc, ss, sl), (dc, ds, dl)) = l
            if l not in l_map:
                return
            (source_gtx, dest_gtx) = l_map[l]
            if source_gtx is None or dest_gtx is None:
                return

            if tx_power is not None:
                source_gtx.TXDIFFCTRL = tx_power

            source_gtx.TXPRBSSEL = 4
            if print_:
                print 'Measuring BER for link %s' % (l,),

            # First, make sure we can get errors by setting the wrong RX PRBS Sequence
            dest_gtx.RXPRBSCNTRESET = 1
            dest_gtx.RXPRBSSEL = 3
            dest_gtx.RXPRBSCNTRESET = 0
            t0 = time.time()
            while True:
                if dest_gtx.ERR_CTR:
                    break
                if time.time() - t0 > 1:
                    raise SystemError('Cannot detect errors even with the wrong sequence! Are the links connected as expected?')

            # dest_gtx.RXPRBSCNTRESET=1
            # dest_gtx.RXPRBSCNTRESET=0
            # dest_gtx.RXPRBSCNTRESET=1
            # dest_gtx.RXPRBSCNTRESET=0
            # t0=time.time()
            # while time.time()-t0 < 13:
            #    print  dest_gtx.ERR_CTR, 'from', dest_gtx
            #    #dest_gtx.RXPRBSCNTRESET=1
            #    #dest_gtx.RXPRBSCNTRESET=0
            #    time.sleep(0.5)
            #    #if not dest_gtx.ERR_CTR:
            #    #    print 'locked',
            #    #    break
            #dest_gtx.RXPRBSCNTRESET=1
            dest_gtx.RXDFELPMRESET = 1
            time.sleep(0.005)
            dest_gtx.RXDFELPMRESET = 0
            time.sleep(0.005)
            dest_gtx.RXPRBSCNTRESET = 1
            dest_gtx.RXPRBSSEL = 4
            dest_gtx.RXDFELPMRESET = 1
            time.sleep(0.005)
            dest_gtx.RXDFELPMRESET = 0
            time.sleep(0.005)
            dest_gtx.RXPRBSCNTRESET = 0
            time.sleep(period)
            cnt = dest_gtx.ERR_CTR
            err = (float(cnt) * 16) / (period * 10e9)
            err_max = (float(cnt) * 16 + 1) / (period * 10e9)

            print 'BER = %1.1e (%i errors, BER<%1.1e)' % (err, cnt, err_max)
            self.print_flush()
            output[l] = err

        #  ib_map = {ib.slot: ib for ib in self.ib}
        ber_table = {}
        ts = []
        for link in link_list:
            t = Thread(target=one_link_ber, args=(link_map, link, ber_table))
            ts.append(t)
            t.start()
        for t in ts:
            t.join()
        return ber_table


    def get_ber_vs_power(self, max_power, period=0.1):

        array = self.ib
        links = self.scan_links(array, tx_power = max_power)
        power = range(0, max_power+1)
        data = {}
        for tx_power in power:
            e = self.get_ber(array, links, period=period, tx_power = tx_power)
            for (link, ber) in e.items():
                if link in data:
                    data[link][0].append(tx_power)
                    data[link][1].append(ber)
                else:
                    data[link] = [[tx_power], [ber]]
        return data

    def plot_ber_vs_power(self, data):
        for ((ss, sl), (ds, dl)), (tx_power, ber) in data.items():
            print '%10s' % (((ss, sl), (ds, dl)), ), ','.join(['%6.1g' % b for b in ber])
        plt.figure(1)
        plt.clf()

        for ((ss, sl), (ds, dl)), (tx_power, ber) in data.items():
            plt.plot(tx_power, np.log10(np.array(ber)+1e-12), label='Slot (%i,%i)=>(%i,%i)' % (ss, sl, ds, dl))
        plt.legend()

    def get_eye_matrix(self, h_step=10, v_step=40):
        link_map = self.detect_backplane_links()
        eye_matrix = {}

        for link in link_map:
            ((from_slot, from_lane), (to_slot, to_lane)) = link
            print  "###### running from slot %i lane %i to slot %i lane %i #######" % ( from_slot, from_lane, to_slot, to_lane)
            gtx = self.ib.get(slot=to_slot).BP_SHUFFLE.gtx[to_lane-1]
            e = gtx.get_eye_diagram(range(-32, 32, h_step), range(-127, 128, v_step))
            eye_matrix[link] = e
        return eye_matrix

    @staticmethod
    def plot_eye_matrix(eye_matrix):
        plt.figure(1)
        plt.clf()

        source_slots = [ss for ((ss, sl), (ds, dl)) in eye_matrix.keys()]
        dest_slots = [ds for ((ss, sl), (ds, dl)) in eye_matrix.keys()]
        slots = sorted(set(source_slots + dest_slots))

        # slot_map = {slot: ix for (ix, slot) in enumerate(slots)}
        slot_map = {x+1: x for x in range(16)}

        (fig, ax) = plt.subplots(len(slot_map), len(slot_map), sharex=True, sharey=True, subplot_kw={'axis_bgcolor': 'black'})
        fig.subplots_adjust(wspace=0, hspace=0)
        fig.suptitle('Backplane 10Gbps mesh eye diagrams\n TX slot #: left, Rx slot #: bottom')

        for (slot, ix) in slot_map.items():
            # Bottom images
            a = ax[ix, 0]
            a.tick_params(labelsize=6)
            a.set_ylabel("TX S%02i" % (slot), fontsize=10)
            # Left images
            a = ax[len(slot_map)-1, ix]
            a.tick_params(labelsize=6)
            a.set_xlabel("RX S%02i" % (slot))
            plt.setp(a.xaxis.get_majorticklabels(), rotation=70)
            # Diagonal images
            a = ax[ix, ix]
            a.patch.set_color('black')

        for (((ss, sl), (ds, dl)), eye) in eye_matrix.items():
            a = ax[slot_map[ss], slot_map[ds]]
            a.imshow(np.log10(eye.ber_map+1e-12), origin='lower', extent=(-32, 32, -128, 128), aspect='auto', vmin=-12, vmax=1)
        plt.draw()

    def print_crossbar2_frame_info(self, reset_stats=False, grid=True, width=180):
        slots = Ccoll(self.ib, self.ib.slot) # Get iceboards indexed by slot number

        crate = set(slots.crate)
        if len(crate) == 1:
            crate = crate.pop()
        else:
            raise RuntimeError('Sorry, this method currently can work on one and only one crate. The currently active boards either have no crates or span multiple crates %s' % list(set(slots.crate)))

        slot_range = range(1,17)
        lane_range = range(16)
        slot_labels = [slots[s].serial if s in slots.keys() else 'N/A' for s in slot_range]

        captured_source = {}
        computed_source = {}
        valid_source = {}
        info = {}
        expected_bp_frame_size = 37
        for dest_slot in slot_range:
            if dest_slot in slots.keys():
                cb = slots[dest_slot].CROSSBAR2
                bp = slots[dest_slot].BP_SHUFFLE
                bin_sel = cb.BIN_SEL[0]
                shuffle_to_bin_sel_lane_map = cb.get_reverse_lane_map()
                remapped_direct_lane = shuffle_to_bin_sel_lane_map[0]
                if reset_stats:
                    bp.reset_stats()
                stream_ids = bin_sel.capture_stream_id()
                frame_number = bin_sel.capture_frame_number()
                frame_number = [f- frame_number[remapped_direct_lane] for f in frame_number]
                captured_source = {remapped_dest_lane: (((s >> 4) & 0xF) + 1 , (s & 0xF)) for remapped_dest_lane, s in enumerate(stream_ids)}
                computed_source = {shuffle_to_bin_sel_lane_map[dest_lane]: crate.get_matching_tx((dest_slot, dest_lane)) for dest_lane in lane_range}
                valid_source = {shuffle_to_bin_sel_lane_map[dest_lane]: v for dest_lane, v in enumerate(cb.get_lane_monitor('INPUT_DETECT'))}
                missing_frame = {shuffle_to_bin_sel_lane_map[dest_lane]: v for dest_lane, v in enumerate(cb.get_lane_monitor('MISSING_FRAME'))}
                align_fifo_overflow = {shuffle_to_bin_sel_lane_map[dest_lane]: v for dest_lane, v in enumerate(cb.get_lane_monitor('ALIGN_FIFO_OVERFLOW'))}
                rx_errors = {shuffle_to_bin_sel_lane_map[dest_lane]: v for dest_lane, v in enumerate(bp.get_rx_lane_monitor('ERROR_CTR'))}
                rx_fifo_overflow = {shuffle_to_bin_sel_lane_map[dest_lane]: v for dest_lane, v in enumerate(bp.get_rx_lane_monitor('FIFO_OVERFLOW'))}
                rx_max_frame_length = {shuffle_to_bin_sel_lane_map[dest_lane]: v for dest_lane, v in enumerate(bp.get_rx_lane_monitor('MAX_FRAME_LENGTH'))}

            else:
                captured_source = {dest_lane: None for dest_lane in lane_range}
                computed_source = {dest_lane: crate.get_matching_tx((dest_slot, dest_lane)) for dest_lane in lane_range}
                valid_source = {dest_lane: False for dest_lane in lane_range}
                missing_frame = {dest_lane: False for dest_lane in lane_range}
                align_fifo_overflow = {dest_lane: False for dest_lane in lane_range}
                rx_fifo_overflow = {dest_lane: False for dest_lane in lane_range}
                rx_errors = {dest_lane: 0 for dest_lane in lane_range}
                rx_max_frame_length = {dest_lane: expected_bp_frame_size for dest_lane in lane_range}
                frame_number = None


            info[dest_slot] = {}
            for remapped_dest_lane in lane_range:
                cap_src = captured_source[remapped_dest_lane]
                comp_src = computed_source[remapped_dest_lane]
                valid_src = valid_source[remapped_dest_lane]
                data_expected = not ((comp_src[0] not in slots.keys()) or (dest_slot not in slots.keys()))
                cell = ' ' if (cap_src and cap_src==comp_src and valid_src) or not data_expected else '!'
                cell += '------' if not cap_src or not data_expected else '--??--' if not valid_src else 'S%02iL%02i' % cap_src
                cell +='/S%02iL%02i' %  comp_src # if not cap_src or data_not_expected or not valid_src else ''
                if frame_number is not None and data_expected and any(frame_number):
                    cell += ' F=%02x' % frame_number[remapped_dest_lane]
                if data_expected:
                    if missing_frame[remapped_dest_lane]:
                        cell += '\n  MISSING FRAMES'
                    if align_fifo_overflow[remapped_dest_lane]:
                        cell += '\n  ALIGN FIFO OVERFLOW'
                    if rx_fifo_overflow[remapped_dest_lane]:
                        cell += '\n  RX FIFO OVERFLOW'
                    if rx_errors[remapped_dest_lane]:
                        cell += '\n  RX ERR = %i' % rx_errors[remapped_dest_lane]
                    if rx_max_frame_length[remapped_dest_lane] != expected_bp_frame_size:
                        cell += '\n  RX FRAME = %i Words' % rx_max_frame_length[remapped_dest_lane]
                info[dest_slot][remapped_dest_lane] = cell


        print 'Post-remap, crossbar2 bin selector input lane indentification'

        corner_label = 'Slot->\nS/N ->\n\\|/Lane'
        col_labels = ['%i\n%s' % (slot_range[i], slot_labels[i]) for i in range(len(slot_range))]
        row_labels = lane_range
        self.print_table(info,
                         row_labels=row_labels, col_labels=col_labels, corner_label=corner_label,
                         line_sep=grid, max_width=width)

    def print_bp_shuffle_info(self, reset_stats=False, grid=True):
        slots = Ccoll(self.ib, self.ib.slot) # Get iceboards indexed by slot number

        crate = set(slots.crate)
        if len(crate) == 1:
            crate = crate.pop()
        else:
            raise RuntimeError('Sorry, this method currently can work on one and only one crate. The currently active boards either have no crates or span multiple crates %s' % list(set(slots.crate)))

        slot_range = range(1,17)
        lane_range = range(16)

        info = {}
        for dest_slot in slot_range:
            if dest_slot in slots.keys():
                bp = slots[dest_slot].BP_SHUFFLE
                if reset_stats:
                    bp.reset_stats()
                computed_source = {dest_lane: crate.get_matching_tx((dest_slot, dest_lane)) for dest_lane in lane_range}
                rx_errors = {dest_lane: v for dest_lane, v in enumerate(bp.get_rx_lane_monitor('ERROR_CTR'))}
                rx_fifo_overflow = {dest_lane: v for dest_lane, v in enumerate(bp.get_rx_lane_monitor('FIFO_OVERFLOW'))}
                rx_max_frame_length = {dest_lane: v for dest_lane, v in enumerate(bp.get_rx_lane_monitor('MAX_FRAME_LENGTH'))}
                info[dest_slot] = {}
                for dest_lane in lane_range:
                    data_expected = computed_source[dest_lane][0] in slots.keys()
                    cell = ('S%02iL%02i\n' if data_expected else '(S%02iL%02i)\n') % computed_source[dest_lane]# if not cap_src or data_not_expected or not valid_src else ''
                    cell += '%s\n' % bool(rx_fifo_overflow[dest_lane])
                    cell += '%05i\n' % rx_errors[dest_lane]
                    cell += '%i' % rx_max_frame_length[dest_lane]
                    info[dest_slot][dest_lane] = cell
            else:
                info[dest_slot] = {dest_lane: '---' for dest_lane in lane_range}

        print 'Backplane shuffle RX status'

        corner_label = 'Slot->\nS/N ->\n\\|/Lane'
        slot_labels = ['SN%s'% slots[s].serial if s in slots.keys() else 'N/A' for s in slot_range]
        col_labels = ['%i\n%s' % (slot_range[i], slot_labels[i]) for i in range(len(slot_range))]
        row_labels = ['L%02i From\n    FIVO_OVF\n    ERR_CTR\n    FRAME_MAX\n' % lane for lane in lane_range]
        self.print_table(info, row_labels=row_labels, col_labels=col_labels, corner_label=corner_label, line_sep=grid)

    def print_table(self, data=None,
                    row_labels=None, col_labels=None, corner_label=None,
                    row_keys=None, col_keys=None,
                    max_width=180, line_sep=False):


        # If we provide no row/col keys, and labels are dict, use the label keys as the row/col keys
        if col_keys is None:
            if isinstance(col_labels, dict):
                col_keys = col_labels.keys()
            elif isinstance(data, dict): #columns are dicts
                col_keys = data.keys()
            else:
                col_keys = range(len(data))

        data = [data[key] for key in col_keys]

        if row_keys is None:
            if isinstance(row_labels, dict):
                row_keys = row_labels.keys()
            else:
                for col_data in data:
                    keys = col_data.keys() if isinstance(col_data, dict) else range(len(col_data))
                    if row_keys is None:
                        row_keys = keys
                    elif keys != row_keys:
                        raise ValueError('Row keys are not identical for every row')

        data = [[col_data[row_key] for row_key in row_keys] for col_data in data]

        if col_labels is None:
            col_labels = [str(key) for key in col_keys]
        else:
            col_labels = [str(label) for label in col_labels]
        if row_labels is None:
            row_labels = [str(key) for key in row_keys]
        else:
            row_labels = [str(label) for label in row_labels]

        if corner_label is None:
            corner_label = ''

        col_keys = range(len(data))
        row_keys = range(len(data[0]))
        col_width = [max([len(line) for cell_data in [col_labels[col]] + data[col] for line in str(cell_data).splitlines() ]) for col in col_keys]
        row_labels_width = max([len(line) for row_label in [corner_label] + row_labels for line in row_label.splitlines() ])
        col_labels_height = max([len(label.splitlines()) for label in [corner_label] + col_labels])


        remaining_col_keys = list(col_keys)
        while remaining_col_keys:
            block_col_keys = []
            block_col_width = []
            while remaining_col_keys:
                col_key = remaining_col_keys[0]
                width = col_width[col_key]
                block_width = row_labels_width +3 + sum(block_col_width + [width]) + len(block_col_width)*3 + 3 + 1
                # print block_col_keys, col_key, block_col_width, width, block_width, max_width
                if block_width <= max_width:
                    block_col_keys.append(remaining_col_keys.pop(0))
                    block_col_width.append(width)
                else:
                    break

            line_format = '| %%-%is' % row_labels_width +' | ' + ' | '.join('%%-%is' % width for width in block_col_width) + ' |'
            line_sep_str = '+' + '+'.join(['-' * (width+2) for width in [row_labels_width] + block_col_width])+'+'

            print line_sep_str

            for i in range(col_labels_height):
                line_data = [cell.splitlines()[i] if i < len(cell.splitlines()) else '' for cell in [corner_label] + [col_labels[col_key] for col_key in block_col_keys]]
                print line_format % tuple(line_data)

            print line_sep_str

            for row_key in row_keys:
                row_data = [str(cell) for cell in [row_labels[row_key]] + [data[col_key][row_key] for col_key in block_col_keys]]
                row_height = max([len(cell.splitlines()) for cell in row_data])
                for i in range(row_height):
                    line_data = [cell.splitlines()[i] if i < len(cell.splitlines()) else '' for cell in row_data]
                    print line_format % tuple(line_data)
                if line_sep:
                    print line_sep_str

            if not line_sep: # Make sure we have a bottom line if we didn't already printed one
                    print line_sep_str

    def print_frame_info(self):
        ts = []
        sid = []

        # get 8 bits of stream ID
        self.HEADER_CAPTURE_DATA_SEL = 0
        self.HEADER_CAPTURE_EN = 1
        self.HEADER_CAPTURE_EN = 0
        for i in range(16):
            self.HEADER_CAPTURE_LANE_SEL = i
            sid.append(self.HEADER_CAPTURE_DATA)

        # get lsb of timestamp
        self.HEADER_CAPTURE_DATA_SEL = 1
        self.HEADER_CAPTURE_EN = 1
        self.HEADER_CAPTURE_EN = 0
        for i in range(16):
            self.HEADER_CAPTURE_LANE_SEL = i
            ts.append(self.HEADER_CAPTURE_DATA)

        for i in range(len(ts)):
            print 'Lane %02i: Stream ID=0x%02x, Frame = 0x%02x (delta = %i)' % (i, sid[i], ts[i], ts[i]-ts[0])


if __name__ == '__main__':

    ca = ChimeArray(argv=sys.argv[1:])
    hwm = ca.hwm
    ib = ca.ib
    c = ca.ib
    ic = ca.ic

    # Open boards
