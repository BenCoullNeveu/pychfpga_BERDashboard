#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import argparse
import collections
import getpass
import logging
import numpy
import os
import signal
import socket
import struct
import subprocess
import sys
import pickle
import time
import traceback

import tornado
import tornado.tcpclient
import tornado.web

import chrx
import kotekan
import pychfpga
import pychfpga.fpga_array
import pychfpga.core.icecore


# Should put somewhere else. Flatten arbitrarily deep nested lists
# from stack overflow
def flatten(x):
    result = []
    for el in x:
        if hasattr(el, "__iter__") and not isinstance(el, basestring):
            result.extend(flatten(el))
        else:
            result.append(el)
    return result

def convert_types(val):
    # Do the annoying conversion of numpy types to native Python types. Sigh.
    found_complex = False
    if isinstance(val, (list, tuple)):
        if len(val) == 0:
            val = [0]
        #if isinstance(val[0], (list, tuple)):
        val = flatten(val)
        if not isinstance(val[0], str):
            try:
                if val[0].dtype.kind in ('i', 'u', 'f'):
                    val = list(numpy.asscalar(x) for x in val)
            except:
                if type(val[0]) == bool:
                    val = list(int(x) for x in val)
                else:
                    val = list(x for x in val)
            for i, val_element in enumerate(val):
                #print val_element
                if isinstance(val_element, complex):
                        val[i] = [val_element.real, val_element.imag]
                        found_complex = True
                if isinstance(val_element, (int,numpy.uint8)):
                        val[i] = float(val_element)
            if found_complex:
                val = flatten(val)
            else:
                val = list(int(x) for x in val)
    else:
        if isinstance(val, long):
            val = int(val)
        elif isinstance(val, bool):
            val = int(val)
        elif isinstance(val, unicode):
            val = str(val)
        if not isinstance(val, str):
            try:
                if val.dtype.kind in ('i', 'u', 'f', 'b'):
                    val = numpy.asscalar(val)
            except:
                    # Hopefully already a int/float
                    pass
    return val


## Setup logging ##

LOG_FORMATTER = logging.Formatter(
    "%(asctime)s %(levelname)s %(filename)s:%(lineno)d >> %(message)s",
    "%b %d %H:%M:%S")
log = logging.getLogger()
log.handlers = []  # clear all existing handlers
log.setLevel(logging.DEBUG) # pass all messages to the handlers
h = logging.StreamHandler(sys.stdout)
h.setFormatter(LOG_FORMATTER)
log.addHandler(h)


## Constants ##

# Current archive format version. Prefixed by "NT_" to signify that
# these data do not have the time-transpose completed.
ARCHIVE_VERSION = "NT_2.2.0"

# Backplane serial number---eventually this should be queried directly
# from the hardware!
CRATE_SN = "K7BP16-0004"

# FPGA housekeeping.
FPGA_HK_FIELDS = { "core_temp": "deg C" }

# Full path to this file.
PROGRAM = os.path.realpath(__file__)

# Git version.
GIT_VERSION = subprocess.check_output(
    'git describe --all --dirty --long'.split(),
    cwd=os.path.dirname(PROGRAM)).strip()

SECONDS_PER_FRAME = 2.56e-6


def load_gains(ib, bank=0):
    gains = {}
    for cc in ib:
        slot = cc.slot
        filename = '/home/chime/ch_acq/gains_slot'+str(slot)+'.pkl'
        try:
            g_array = pickle.load(open(filename, 'rb'))
            log.info('Setting gains on IceBoard SN%s, slot %i' % (cc.serial, slot))
            cc.set_gain(g_array, bank=bank)  # *** should this be bank=all_bank
            gains[slot] = cc.get_gain(bank=bank)
        except IOError:
            log = logging.getLogger()
            log.warn('Could not load gain file %s. Gains are not set.' % filename)
    return gains


def configure_fpgas(conf):

    fpga_array_params = conf.fpga.pop('fpga_array_params')

    log.info("Sampling frequency is %0.3f MHz." %
        float(fpga_array_params.samp_freq))

    # Create the FPGA controller object.
    # Will now create an array of controller objects indexed by serial number
    # And program board firmware if needed/requested currently will always reprogram
    ca = pychfpga.fpga_array.FPGAArray(**fpga_array_params)
    sync_board = ca.ib.get(serial=conf.fpga.master_sync_board) if conf.fpga.master_sync_board else None
    ca.set_sync_method(conf.fpga.sync_method, source=conf.fpga.sync_source, master=sync_board, master_time_source=conf.fpga.master_sync_source if sync_board else None)
    ca.ib.set_adc_mask(0) # null the ADC data before it gets to the channelizers to reduce power consumption

    try:
        delays = pickle.load(open(conf.fpga.adc_delay_table))
        #sync_delays = pickle.load(open(conf.fpga.sync_delay_table))
        for ib in ca.ib:
            #ib.REFCLK.set_sync_delay(sync_delays[int(ib.serial)])
            ib.REFCLK.compute_sync_delay() # XXX: is this ok?
            time.sleep(0.2)
            ib.set_adc_delays_with_check(delays[int(ib.serial)])
            log.info("set delays on SN%s, SLOT%s" % (ib.serial, ib.slot))
    except IOError:
        #log.warn("Error loading/setting delay tables. Using default delays from config file for all boards")
        raise RuntimeError('Error loading/setting delay tables')
    if not ca.ib:
        raise RuntimeError('No IceBoard could be found. Are the boards powered up? Is the networking functional?')

    ca.ib.set_corr_reset(1)
    time.sleep(0.1)
    ca.ib.set_corr_reset(0)

    # Set FPGA controller parameters.
    # Calculate new gains if necessary
    # Get config here to be able to create receiver object
    # Gains will need to be able to handle multiple boards, currently file
    # Will be overwritten when used for more than one board.
    # Make compute gains smarter -> write to db? need boards to actually be different

    # Get noise injection parameters
    ni_board = conf.fpga.ni_board
    ni_enable = conf.fpga.ni_enable
    ni_offset = conf.fpga.ni_offset
    ni_high_time = conf.fpga.ni_high_time - 1 # the -1 is due to the convention in function set_frame_pwm()
    ni_period = conf.fpga.ni_period - 1
    ni_board_26m = conf.fpga.ni_board_26m
    ni_enable_26m = conf.fpga.ni_enable_26m
    ni_offset_26m = conf.fpga.ni_offset_26m
    ni_high_time_26m = conf.fpga.ni_high_time_26m - 1 # the -1 is due to the convention in function set_frame_pwm()
    ni_period_26m = conf.fpga.ni_period_26m - 1

    if (int(conf.compute_gain) > 0):
        # Shouldn't need for loop here, but initial testing failed in parallel.
        if ni_enable:
            ca.set_noise_injection(ni_board, ni_enable, 0, 3, 4)
            ni_board.sync()
        if ni_enable_26m:
            ca.set_noise_injection(ni_board_26m, ni_enable_26m, 0, 3, 4)
            ni_board_26m.sync()
        calculate_gain_slots = conf.fpga.calculate_gain_slots
        for ib in ca,ib:
            if ib.slot in calculate_gain_slots:
                fpga_config = ib.get_config()
                pychfpga.calculate_gains.calculate_gains(ib, str(ib.fpga_port_number + 1))
    all_chan = range(16)  # range(conf["n_antenna"])
    ca.ib.set_data_source("adc")  # This should come first.
    ca.ib.set_FFT_bypass(False, channels=all_chan)
    ca.ib.set_FFT_shift(conf.fpga.fft_shift, channels=all_chan)

    ca.ib.set_synchronized_gain_switching(enable=0)
    ca.ib.set_next_gain_bank(bank=0)
    all_banks = ca.ib.get_current_gain_bank()

    # Load and set the gains
    log.info("Loading initial gains")
    load_gains(ca.ib, bank=0)

    for bankset in ca.ib.get_current_gain_bank():
        log.info('Using gain banks %s' % (', '.join([str(i) for i in bankset])))

    enable_gain_switching = conf.acq.enable_gain_switching
    gain_switch_frame = conf.fpga.gain_switch_frame
    if enable_gain_switching > 0:
        # set frame number to switch gains at.
        ca.ib.set_gain_switch_frame_number(frame=0) # XXX:???
        # set to only change when at configured frame number
        ca.ib.set_synchronized_gain_switching(enable=1)
        # set to use bank 1 next, change in loop below.
        # have to do this after config to wait for frame number

    for bankset in ca.ib.get_current_gain_bank():
        log.info('Using gain banks %s' % (', '.join([str(i) for i in bankset])))

    for enabled_sync in ca.ib.get_synchronized_gain_switching():
        log.info('Gain sync status is %s' % (', '.join([str(i) for i in enabled_sync])))

    for frames_set in ca.ib.get_gain_switch_frame_number():
        log.info('Gain sync frame is %s' % (', '.join([str(i) for i in frames_set])))

    log.info("Sending local sync to each board")
    ca.ib.sync()
    ca.ib.set_offset_binary_encoding(True)
    for ib in ca.ib:
        ib.set_local_data_port_number((ib.slot or 1) + 41100)
        ib.start_data_capture(period=30, source='adc', offset=(ib.slot or 1) - 1)
    # Setup noise injection enable PWM signals
    if ni_board:
        ca.set_noise_injection(ni_board, ni_enable, ni_offset, ni_high_time, ni_period)
    if ni_board_26m:
        ca.set_noise_injection(ni_board_26m, ni_enable_26m, ni_offset_26m, ni_high_time_26m, ni_period_26m)
    # Initialize data shufling and transmission to the GPU
    log.info("Setting FPGA operational mode")
    ca.set_operational_mode(conf.fpga.operational_mode, frames_per_packet=fpga_array_params.group_frames)
    log.info("Synchronizing the array...")

    ca.sync()  # synchronize all the boards in the array

    log.info("Unmasking the ADC data")
    ca.ib.set_adc_mask(0xFF) # restore normal ADC data

    log.info("Waiting for 2 seconds")
    time.sleep(2)

    return ca

def configure_fpgas_post_acq(conf, ca):

    ca.ib.CROSSBAR.LANE_MONITOR_RESET = 1
    ca.ib.CROSSBAR.LANE_MONITOR_RESET = 0
    ca.ib.CROSSBAR2.LANE_MONITOR_RESET = 1
    ca.ib.CROSSBAR2.LANE_MONITOR_RESET = 0
    ca.ib.CROSSBAR.LANE_MONITOR_SEL = 6
    ca.ib.CROSSBAR2.LANE_MONITOR_SEL = 6

    if (conf.acq.enable_gain_switching > 0):
        ca.ib.set_next_gain_bank(bank=1)
    for bankset in ca.ib.get_next_gain_bank():
        log.info('Set next gain bank to %s' % ', '.join([str(i) for i in bankset]))
    for bankset in ca.ib.get_current_gain_bank():
        log.info('Currently using gain banks %s' % ', '.join([str(i) for i in bankset]))


def pass_gains_to_chrx(acq, fpga_gains):
    remap_adc_sma = [12, 13, 14, 15,  8, 9, 10, 11,  4,  5,  6,  7, 0, 1, 2, 3]
    remap_slot    = [ 5,  1,  4,  0, 13, 9, 12,  8, 15, 11, 14, 10, 7, 3, 6, 2]
    for fpga_slot, slot_gain in fpga_gains.items():
        for val in slot_gain:
            v = convert_types(val)
            inp = remap_slot[fpga_slot-1] * 16 + remap_adc_sma[int(val[0])]
            acq.pass_fpga_gain(inp, v)


def reap_cached_sockets():
    import __main__
    if hasattr(__main__, '__opened_sockets__'):
        for port,socket in __main__.__opened_sockets__.items():
            log.debug("closing cached socket on port %d" % port)
            socket.close()
        del __main__.__opened_sockets__


class ChimeMaster(object):
    """
    """

    def __init__(self):
        self.state = 'off'

    def start(self, **kvs):
        self.state = 'starting'
        self.config = kvs
        conf = pychfpga.core.icecore.NameSpace(kvs)

        time_str = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        acq_name = "%s_%s_corr" % (time_str, conf.corr_name)
        acq_base_dir = os.path.join(conf.acq.base_path, acq_name)

        try:
            os.makedirs(acq_base_dir)
        except:
            errmsg = "Could not create directory '%s'!" % acq_base_dir
            log.critical(errmsg)
            return {'error':errmsg}

        # Create a symbolic link to the output directory.
        if conf.acq.curfile:
            if os.path.islink(conf.acq.curfile):
                os.unlink(conf.acq.curfile)
            os.symlink(acq_base_dir, conf.acq.curfile)

        # Start writing to a log file in this directory.
        acq_log_path = "%s/ch_master.log" % acq_base_dir
        self.logfile = logging.FileHandler(acq_log_path)
        self.logfile.setFormatter(LOG_FORMATTER)
        log.addHandler(self.logfile)
        log.info("now logging to \"%s\"." % acq_log_path)

        # FPGAs
        log.info("initializing FPGAs...")
        self.fpgas = configure_fpgas(conf)
        log.info("finished initializing FPGAs")

        # Read the FPGA setting back from the FPGA
        log.info("getting configuration data from all FPGAs")
        fpga_conf = {ib.slot:vars(ib.get_config()) for ib in self.fpgas.ib}

        # Add some acquisition information to the header, for kicks.
        headers = {
            'acquisition_name': acq_name,
            'acquisition_type': 'corr',
            'archive_version': ARCHIVE_VERSION,
            'collection_server': socket.gethostname(),
            'instrument_name': conf.corr_name,
            'git_version_tag': GIT_VERSION,
            'system_user': getpass.getuser(),
        }

        for k in ['notes']:
            if k in conf:
                headers[k] = conf[k]

        # Pass FPGA configuration variables to header.
        for fpga_slot, slot_conf in fpga_conf.items():
            for name in slot_conf:
                if name != 'antenna_scaler_gain':
                    val = convert_types(slot_conf[name])
                    name = 'Slot_'+ str(fpga_slot) + '_' + name
                    headers[name] = val

        # CHRX
        log.info("starting CHRX...")

        self.acq = chrx.acq(conf, log, 16, FPGA_HK_FIELDS)

        for k,v in headers.items():
            self.acq.add_header_item(k, v)

        self.acq.start(acq_base_dir, CRATE_SN, int(conf.fpga.subarray))
        log.info("finished starting CHRX")

        configure_fpgas_post_acq(conf, self.fpgas)
        self.current_bank = 0

        # print board info every 60s
        self.iceboard_cb = tornado.ioloop.PeriodicCallback(
            self.fpgas.print_iceboard_info, 60e3)
        self.iceboard_cb.start()

        self.state = 'on'
        return {}

    def status(self):
        status = dict(state=self.state)
        if self.state == 'on':
            status['config'] = self.config
        return status

    def stop(self):
        if self.state == 'on':
            self.state = 'stopping'
            log.info("stopping acquisition")
            self.iceboard_cb.stop()
            self.acq.stop()
            log.removeHandler(self.logfile)
            reap_cached_sockets()
            self.state = 'off'
        return {}

    def load_gains(self):
        current_bank = self.current_bank
        next_bank = (current_bank + 1) % 2
        iceboards = self.fpgas.ib

        # log current gains
        for bankset in iceboards.get_current_gain_bank():
            log.info('Using gain banks ' + ', '.join(map(str,bankset)))

        # load gains into next bank
        fpga_gains = load_gains(iceboards, bank=next_bank)
        log.info("Loaded gains into bank %d" % next_bank)

        return fpga_gains

    def set_gain_switch_frame(self):
        iceboards = self.fpgas.ib
        gain_switch_delay = self.config['fpga']['gain_switch_delay']
        gpu_integration_period = self.config['gpu']['gpu_integration_period']

        # set gain switch time
        frame_number = iceboards[0].get_frame_number()
        new_gain_switch_frame = (1 + (frame_number + gain_switch_delay)//gpu_integration_period)*gpu_integration_period
        iceboards.set_gain_switch_frame_number(frame=new_gain_switch_frame)

        sleep = (new_gain_switch_frame - frame_number)*SECONDS_PER_FRAME
        return sleep

    def switch_gain_banks(self):
        current_bank = self.current_bank
        next_bank = (current_bank + 1) % 2
        iceboards = self.fpgas.ib

        iceboards.set_next_gain_bank(bank=current_bank)
        self.current_bank = next_bank
        log.debug("changed which gain bank will be written to over to %d"
            % current_bank)

        # log current gains
        for bankset in iceboards.get_current_gain_bank():
            log.info('Using gain banks ' + ', '.join(map(str,bankset)))


class DummyChimeMaster(ChimeMaster):
    """
    A variant of ChimeMaster that doesn't do anything hardware related.
    """

    def start(self, **kvs):
        self.config = kvs
        return kvs

    def status(self):
        return self.config

    def stop(self):
        return {}


class JsonRequestHandler(tornado.web.RequestHandler):
    """
    Accept and return JSON instead of HTML.
    """

    def prepare(self):
        if not self.request.body: return
        content_type = self.request.headers['Content-Type']
        if content_type == 'application/json':
            try:
                args = tornado.escape.json_decode(self.request.body)
                self.request.arguments.update(args)
            except ValueError:
                self.send_error(400, error="can't parse JSON")
        elif content_type == 'application/x-www-form-urlencoded':
            args = { k:v[-1] for k,v in self.request.arguments.items() }
            self.request.arguments.update(args)

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')

    def write_error(self, status_code, **kvs):
        if 'exc_info' in kvs:
            exc_info = kvs.pop('exc_info')
            kvs['error'] = ''.join(traceback.format_exception(*exc_info))
        self.write(kvs)


class EchoHandler(JsonRequestHandler):
    """
    /echo REST endpoint handler. Echoes back POSTed arguments, for debugging.
    """
    def post(self):
        a = self.request.arguments
        self.write(a)


class StartHandler(JsonRequestHandler):
    """
    /start REST endpoint handler.
    """
    def initialize(self, cm):
        self.cm = cm

    def post(self):
        def encode_utf8(x):
            "convert unicode to utf-8 strings"
            if type(x) is unicode:
                return x.encode('utf8')
            elif type(x) is dict:
                return {encode_utf8(k):encode_utf8(v) for k,v in x.items()}
            elif type(x) is list:
                return map(encode_utf8, x)
            else:
                return x
        config = encode_utf8(self.request.arguments)
        self.write(self.cm.start(**config))


class StatusHandler(JsonRequestHandler):
    """
    /status REST endpoint handler.
    """
    def initialize(self, cm):
        self.cm = cm

    def get(self):
        self.write(self.cm.status())


class StopHandler(JsonRequestHandler):
    """
    /stop REST endpoint handler.
    """
    def initialize(self, cm):
        self.cm = cm

    def get(self):
        self.write(self.cm.stop())


class SwitchGainsHandler(JsonRequestHandler):
    """
    /switchgains REST endpoint handler.
    """
    def initialize(self, cm):
        self.cm = cm

    @tornado.gen.coroutine
    def post(self):
        if self.cm.state != 'on':
            self.write(dict(error='not started'))
            return

        fpga_gains = self.cm.load_gains()
        sleep = self.cm.set_gain_switch_frame()

        # wait for switch
        yield tornado.gen.sleep(sleep)
        pass_gains_to_chrx(self.cm.acq, fpga_gains)

        # wait for 10 secs, then switch banks
        yield tornado.gen.sleep(10)
        self.cm.switch_gain_banks()

        self.write({})


class KotekanHandler(JsonRequestHandler):
    """
    /kotekan REST endpoint handler. Just passes messages through.
    """
    def initialize(self, kotekan):
        self.kotekan = kotekan

    @tornado.gen.coroutine
    def post(self):
        args = self.request.arguments.copy()
        type = args.pop('msg_type')
        msg = kotekan.KotekanMessage(type, **args)
        yield self.kotekan.send(msg)


class KotekanConnection(object):

    def __init__(self, host, port, callback):
        self.host = host
        self.port = port
        self.on_msg = callback
        self.msg_uid = 0

    @tornado.gen.coroutine
    def start(self):
        client = tornado.tcpclient.TCPClient()
        while True:
            try:
                self.stream = yield client.connect(self.host, self.port)
                log.info("connected to kotekan")
                while True:
                    msg = yield self.receive()
                    self.on_msg(msg) # yield?
            except tornado.iostream.StreamClosedError:
                #log.debug("can't connect to kotekan")
                yield tornado.gen.sleep(10)

    @tornado.gen.coroutine
    def send(self, msg):
        self.msg_uid += 1
        s = msg.serialize(self.msg_uid)
        b = struct.pack('!I', len(s))
        yield self.stream.write(b + s)

    @tornado.gen.coroutine
    def receive(self):
        b = yield self.stream.read_bytes(4)
        n,= struct.unpack('!I', b)
        s = yield self.stream.read_bytes(n)
        msg = kotekan.KotekanMessage.deserialize(s)
        raise tornado.gen.Return(msg)


def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="Chime Master")
    parser.add_argument('--debug', action='store_true',
                        help="debug mode")
    parser.add_argument('-p', '--port', default=54321, type=int)
    return parser.parse_args(argv)


def main(args):

    log.info("program %s" % PROGRAM)
    log.info("version %s" % GIT_VERSION)

    # create event loop
    loop = tornado.ioloop.IOLoop.instance()

    if args.debug:
        cm = DummyChimeMaster()
    else:
        cm = ChimeMaster()

    # kotekan
    k = KotekanConnection('localhost', kotekan.PORT,
            lambda msg: print('received', msg))
    loop.add_callback(k.start)

    # setup REST endpoints
    url = tornado.web.url
    app = tornado.web.Application([
        url(r'/echo', EchoHandler),
        url(r'/kotekan', KotekanHandler, dict(kotekan=k)),
        url(r'/start', StartHandler, dict(cm=cm)),
        url(r'/status', StatusHandler, dict(cm=cm)),
        url(r'/stop', StopHandler, dict(cm=cm)),
        url(r'/switchgains', SwitchGainsHandler, dict(cm=cm)),
    ])
    app.listen(args.port)

    def shutdown():
        cm.stop()
        loop.stop()
    handler = lambda sig,frame: loop.add_callback_from_signal(shutdown)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    # start event loop
    log.info("ready")
    loop.start()


if __name__ == '__main__':
    args = parse_cmdline_args(sys.argv[1:])
    main(args)

