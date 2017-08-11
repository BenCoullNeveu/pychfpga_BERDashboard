#!/usr/bin/env python
"""
REST Server and clients for the CHIME receiver hut power supplies.

"""

import logging
import sys
import argparse
import time
import socket

# import tornado

# from pychfpga.Agilent_N5764A import AgilentN5764AHandler
from pychfpga import Metrics, NameSpace, load_yaml_config
from rest import AsyncRESTClient, AsyncRESTServer, endpoint, coroutine, coroutine_return, sleep, IOLoop, RunSyncWrapper, SocketContext  # generic REST servers and clients
import log  # logging helper functions

class AgilentN5700(SocketContext):
    """
    A class to communicate with an Agilent N5700- or N8700-type power supply
    """


    SUPPORTED_PS = {
        # model : (name, IDN substring, Vmax, Imax)
        'N5764A': ('Agilent Power Supply', 'Agilent Technologies,N5764A', 21, 79.8 ),
        'N8731' : ('Agilent Power Supply', 'Agilent Technologies,N5781', 8, 400)
    }


    def __init__(self,  hostname, port=5025, timeout=0.5, verbose=1):

        super(AgilentN5700, self).__init__(hostname=hostname, port=port, timeout=timeout)
        self.log = log.get_logger(self)
        print "Initializing direct LAN Connection at %s:%i" % (hostname, port)
        self.locked = True
        self.verbose = verbose
        self.instrument_name = None
        self.instrument_model = None
        self.log.debug('Initializing instrument')

        # self.device_clear()


    def __repr__(self):
        if self.instrument_model:
            return '%s %s @%s:%i' % (self.instrument_name, self.instrument_model, self.ip_addr, self.ip_port)
        else:
            return 'Unknown Instrument @%s:%i' % (self.ip_addr, self.ip_port)

    ###################################
    # Basic read/write commands
    ###################################


    def command(self, comstr, flush=False):
        """
        Sends a command to the instrument. The terminator is added automatically.
        """
        with self.socket(flush=True):
            self._check_instrument_type()
            self.send(comstr + "\n")

    def query(self, command, flush=False, **kwargs):
        """
        Sends a command to the instrument and returns the reply string without the terminator or trailing spaces.
        """
        with self.socket(flush=flush):
            self._check_instrument_type()
            self.send(command + '\n')
            # self.command('*WAI')
            try:
                reply_string = self.recv(16384)
            except IOError:
                raise IOError('%r: timout while waiting for reply for command %s' % (self, command))
            return reply_string.rstrip() # remove trailing spaces or CR or LF

    def _check_instrument_type(self):
        """
        Make sure the instrument type and model is known and supported.
        """
        if self.instrument_model and self.instrument_name:
            return
        with self.socket(flush=True):
            self.send('*IDN?\n')
            id_string = self.recv(timeout=min(1, self.timeout))
            self.log.debug('Instrument Identification string: %s' % id_string)
            for (instrument_code, (instrument_name, instrument_id_string, vmax, imax)) in self.SUPPORTED_PS.items():
                if instrument_id_string in id_string:
                    self.log.debug('Connected to: %s' % instrument_name)
                    self.send('STATus:OPERation:ENABle %i\n' % 0x0500)  # We wish to know is in constant current or constant voltage mode
                    self.instrument_model = instrument_code
                    self.instrument_name = instrument_name
                    self.instrument_vmax = vmax
                    self.instrument_imax = imax
                    break

            if instrument_code is None:
                raise RuntimeError('The identification command did not return the expected instrument ID string')

    def open(self):
        with self.socket():
            self._check_instrument_type()

    def query_float(self, *args,  **kwargs):
        return float(self.query(*args, **kwargs))

    def query_int(self, *args,  **kwargs):
        return int(self.query_float(*args, **kwargs))

    def waituntilready(self):
        while not(self.query_float('*OPC?')):
            time.sleep(0.01)

    def lock(self):
        self.locked = True

    def unlock(self):
        self.locked = False

    def _check_lock(self):
        if self.locked:
            raise RuntimeError('Instrument is locked: cannot change its state. Call unlock() to allow changes to the instrument state')


    def set_output(self, state=None):

        """
        Turns on and off the output and measures current output state input
        state can be varius spellings of 'on'/ 'off', None, 0, or 1   (default
        is None)

        Returns status dictionary
        """
        self._check_lock()
        outstate = []
        if state is None:
            pass
        if state in ['on', 'On', 'ON', 1, True]:
            state = 1
        elif state in ['off', 'Off', 'OFF', 0, False]:
            state = 0
        else:
            raise ValueError('Unknown desired output power state')
        with self.socket(flush=True):
            self.command('OUTP:STAT %s' % state, flush=True)
            self.waituntilready()
            # self.command('*WAI')

        return {'PowerEnabled': self.get_output_state()}


    def get_output_state(self):
        return bool(self.query_float('OUTP:STAT?'))

    def set_power_on_state(self, state):
        if state.upper() not in ('RST','AUTO'):
            raise ValueError('%r: Power on state is either RST or AUTO' % self)
        self.command('OUTPut:PON:STATe %s' % state)

    def get_power_on_state(self):
        return self.query('OUTPut:PON:STATe?')

    def is_enabled(self):
        return self.get_output_state()

    def power_on(self):
        self.set_output(state=True)

    def power_off(self):
        self.set_output(state=False)

    def power_enable(self, state):
        self.set_output(state=state)

    def power_cycle(self, delay=4):
        with self.socket():
            self.set_output(state=False)
            time.sleep(delay)
            self.set_output(state=True)


    def get_state(self):
        """ Return the power supply operational state of the power supply.

        Returns:

            'OK': power supply is turned on and operates normally
            'OFF': power supply is turned off
            'ILIMIT': power supply is in current limit mode
            'FAULT': A fault has occured
        """
        with self.socket():
            failmode = int(self.query_float('STAT:QUES:COND?'))
            if failmode != 0:
                state = 'FAULT'
            else:
                op_state = int(self.query_float('STATus:OPERation:CONDition?'))
                if bool((op_state & (1 << 8)) >> 8):  # Voltage regulating
                    state = 'OK'
                elif bool((op_state & (1 << 10)) >> 10):  # Current limiting
                    state = 'ILIMIT'
                else:
                    state = 'OFF'
            return state


    def is_ok(self):
        """ Return the operational state of the power supply.
        """
        return self.get_state() == "OK"



    def status(self):

        """
        Returns a dictionary containting the output voltage and current
        """
        with self.socket(flush=True):
            meas = {'current': 0, 'voltage': 0}
            current = self.query_float('MEAS:CURR?', timeout=2)
            voltage = self.query_float('MEAS:VOLT?', timeout=2)
            power = round(current * voltage, 3)
            meas['current'] = current
            meas['voltage'] = voltage
            meas['power'] = power
            meas['status'] = self.get_state()
            return meas

    def set_voltage(self, voltage):
        """
        Sets the output voltage - Valid range is 0 to 21V - default is None
        Returns the power supply setpoint voltage
        """
        self._check_lock()
        if voltage > self.instrument_vmax or voltage < 0:
            raise ValueError('Invalid voltage - must be in range [0..21] - no action performed')
        with self.socket():
            self.command('VOLT %s' % voltage)
            # self.command('*WAI')
            self.waituntilready()

    def get_voltage_setting(self):
        """
        Returns the power supply setpoint voltage
        """
        return self.query_float('VOLT?')

    def set_current_limit(self, current=None, ocp=None):
        """
        Sets the current limit and can enable disable ocp  - Valid range is 0
        to 76A - by default current is None and ocp is None

        Returns the power supply current limit
        """
        self._check_lock()

        if ocp is not None:
            self.protection(ocp=ocp, readonly=False)
        if current > self.instrument_imax or current < 0:
            raise ValueError('Invalid current limit - must be in range [0..76] - no action performed')
        with self.socket():
            self.command('CURR %s' % current)
            # self.command('*WAI')
            self.waituntilready()

    def get_current_limit(self):
         """
         Returns the power supply current limit
         """
         return self.query_float('CURR?')

    def clear(self):
        """
        If any of the protection has triggered will need to clear it. Will
        return a False if everything is good
        """
        self._check_lock()
        with self.socket():
            self.protection(clear=True, readonly=False)[0]
            problem = self.protection()[0]
            return problem


    def set_protection(self, uvl=None, ovp=None, ocp=None,ilim=None, clear=None):
        """
        Adjusts power supply protection settings
        Returns two dictionaries the first with the current protection settings, the second with the fail modes
        Warning - when clearing - return status is 'dont trust anything' - run protection another time
        """
        self._check_lock()
        with self.socket(flush=True):
            if clear == 1:
                self.command('OUTPut:PROT:CLEar')
                #self.command('*WAI')
                self.waituntilready()

            if uvl != None:
                self.command('VOLT:LIM:LOW %s' % uvl)
            if ovp != None:
                self.command('VOLT:PROT %s' % ovp)
            if ocp != None:
                self.command('CURR:PROT:STAT %s' % ocp)
                #Note that OCP is not the current limit, only behaviour on current limit (can be 0 or 1)
                #With OCP active current switches to triggered current (by default and not changed by this program so far 0A)
            if ilim != None:
                self.command('CURR %s' % ilim)

    def get_protection(self, history=False):

        with self.socket():
            uvlmeas=self.query_float('VOLT:LIM:LOW?')
            ovpmeas= self.query_float('VOLT:PROT?')
            ocpmeas=self.query_float('CURR:PROT:STAT?')
            ilimmeas=self.query_float('CURR?')

            if not(history):  #By default just read the main status register not the register that clears itself after reading
                failmode=int(self.query_float('STAT:QUES:COND?'))
            else: #If you really want the register that clears itself set History=True
                failmode=int(self.query_float('STAT:QUES?'))  #Will spot if previously things went wrong or if currently things are wrong
                print "Not that reliable and it clears itself after!"

            problem = False
            if failmode != 0:
                print 'A power supply problem is present'
                problem = True

            UNR = bool( ( failmode & ( 1 << 10 ) ) >> 10 )  #True if Unregulated output
            if UNR == 1:
                UNRMes = 'Unregulated output'
            else:
                UNRMes = 'Output is regulated'

            INH = bool( ( failmode & ( 1 << 9 ) ) >> 9 )  #True if output turned off by J1 inhibit signal
            if INH == 1:
                INHMes = 'Inhibt signal on J1 turned off output'
            else:
                INHMes = 'No Inhibt signal on J1 has been detected'

            OT = bool( ( failmode & ( 1 << 4 ) ) >> 4 ) #True if output turned off by power supply temperature monitor
            if OT == 1:
                OTMes = 'Power supply got too hot and turned off output'
            else:
                OTMes = 'Power supply temperature okay'

            PF = bool( ( failmode & ( 1 << 2 ) ) >> 2 ) #True if output turned off because AC power failed
            if PF == 1:
                PFMes = 'Input Power faliure and output turned off '
            else:
                PFMes = 'Input power okay'

            OC = bool( ( failmode & ( 1 << 1 ) ) >> 1 ) #True if output turned off because of Over current
            if OC == 1:
                OCMes = 'OCP triggered, output off '
            else:
                OCMes = 'OCP did not trigger'

            OV = bool( ( failmode & ( 1 << 0 ) ) >> 0 ) #True if output turned off because of Over voltage
            if OV == 1:
                OVMes = 'Over voltage protection triggered, output turned off '
            else:
                OVMes = 'No over voltage detected'
            failmode = {'UNR': [UNR,UNRMes], 'INH': [INH, INHMes], 'OT': [OT, OTMes], 'PF': [PF, PFMes], 'OC':[OC, OCMes], 'OV':[OV, OVMes]}


            protectionstatus={'uvl':uvlmeas, 'ovp':ovpmeas, 'ocp':ocpmeas, 'ilim':ilimmeas}
            if clear == 1 and problem == 0:
                problem = 'dont trust anything'

            return problem, protectionstatus, failmode

    def configure_power_on_state(self, voltage, current):
        """
        Configure the power supply so it will automatically power up at the specified voltage and current limit.

        The power supply is turned off before the new settings are applied.
        """
        with self.socket():
            self.power_off()
            self.set_voltage(voltage)
            self.set_current_limit(current)
            self.set_power_on_state('AUTO')


class PowerSupplyAsyncRESTServer(AsyncRESTServer):
    """
    REST interface for receiver hut power supplies.
    """

    DEFAULT_PORT = 54324

    POWER_SUPPLY_CLASSES = {
        'AgilentN5764': AgilentN5700,
        'AgilentN8731': AgilentN5700
        }

    def __init__(self,  address='', port=DEFAULT_PORT, logging_params={}):
        """ power_supplies list of dict with entries 'type', 'name', and 'address'
        """
        self.power_supplies = {}
        # self.name = name
        # self.ps_port = 5025
        super(PowerSupplyAsyncRESTServer, self).__init__(address=address, port=port, heartbeat_string='Ps')

    def _parse_names(self, ps_names):
        if not ps_names:
            return []
        if isinstance(ps_names, (str, unicode)):
            ps_names = ps_names.replace(' ', ',').split(',')
        ps_names = [name.strip() for name in ps_names]
        if 'all' in ps_names or '*' in ps_names:
            ps_names = self.power_supplies.keys()
        unknown_supplies = [name for name in ps_names if name not in self.power_supplies]
        if unknown_supplies:
           raise RuntimeError("%.32r: Unknown power supply names %s" % (self, unknown_supplies))
        return ps_names


    @coroutine
    def _get_metrics(self):
        """ Return a Metrics object containing power supply monitoring data
        """
        self.log.info('%.32r: Received monitoring metrics request' % self)
        metrics = Metrics()
        for ps_name, ps in self.power_supplies.items():
            try:
                status = NameSpace(ps.status())
                metrics.add('fpga_power_supply_voltage', name=ps_name, value=status.voltage, type='gauge')
                metrics.add('fpga_power_supply_current', name=ps_name, value=status.current, type='gauge')
                metrics.add('fpga_power_supply_power', name=ps_name, value=status.power, type='gauge')
                metrics.add('fpga_power_supply_status', name=ps_name, value=int(status.status == 'OK'), type='gauge')
            except IOError:
                pass
        coroutine_return(metrics)

    def _set_is_ready_later(self, name):
        """ Sets the is_ready flag for power supply `name` to True after the power supply power-up delay has elapsed """
        def callback():
            self.is_ready[name] = True
        self.call_later( self.power_up_delay[name], callback)

    ##################
    # Server commands
    ##################

    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        """ Start the power sypply server with provided config
        """
        if self.power_supplies:
            raise RuntimeError('%.32r: Power Supply server is already started' % self)
        self.config = NameSpace(config)
        self.power_supplies = {}
        self.power_up_delay = {}
        self.is_ready = {}

        units = self.config.units or {}
        for name, ps in units.items():
            type_ = ps.pop('type')
            self.power_up_delay[name] = ps.pop('power_up_delay')
            cls = self.POWER_SUPPLY_CLASSES[type_]
            ps_instance = cls(**ps)
            self.power_supplies[name] = ps_instance
            # self.power_supplies[name].open()
            self.is_ready[name] = False

        # If a power supply is already up and running (for an unknown period of time),
        # schedule the `is_ready` flag to be true after the power-up delay
        for ps_name, ps in self.power_supplies.items():
            if ps.is_ok():
                self.is_ready[ps_name] = True
                #self._set_is_ready_later(ps_name)

        coroutine_return('Power supply server started')

    @coroutine
    @endpoint('stop')
    def stop(self, handler):
        if not self.power_supplies():
            self.log.warning('%.32r: Power Supply server is not started' % self)
        else:
            for ps_name, ps in self.power_supplies.items():
                ps.close()
            self.power_supplies = {}
        coroutine_return('Power supply server stopped')

    @coroutine
    @endpoint('status')
    def status(self, handler):
        # ps_names = self._parse_names(ps_names)
        # self.log.info('%.32r: Received status request for %r' % (self, ps_names))
        stati = dict(is_started=bool(self.power_supplies),
                     ps_names=self.power_supplies.keys())
        for ps_name, ps in self.power_supplies.items():
            stati[ps_name] = ps.status()
            self.log.info('%.32r: Status of %s is %s' % (self, ps_name, stati[ps_name]))
        coroutine_return(stati)


    @coroutine
    @endpoint('is-started')
    def is_started(self, handler):
        coroutine_return(bool(self.power_supplies))


    @coroutine
    @endpoint('list-names')
    def listNames(self, handler):
        self.log.info('%.32r: Received list names request' % self)
        coroutine_return(self.power_supplies.keys())

    @coroutine
    @endpoint('power-on')
    def powerOn(self, handler, ps_names=None):
        ps_names = self._parse_names(ps_names)
        self.log.info('%.32r: Received power on command for %r' % (self, ps_names))

        for ps_name in ps_names:
            ps = self.power_supplies[ps_name]
            # status = ps.status()  # todo: make async
            # if status['status'] == 'OK':
            if ps.is_enabled():
                self.log.info("%.32r: Power supply '%s' is already ON" % (self, ps_name))
            else:
                self.log.info("%.32r: Turning ON power supply '%s'" % (self, ps_name))
                ps.unlock()
                ps.power_on() # todo: make async
                ps.lock()
                self.is_ready[ps_name] = False
                self._set_is_ready_later(ps_name)
                self.log.info("%.32r: %s is powered ON" % (self, ps_name))

                # yield sleep(self.config.power_on.delay) # make this asynchronous so all the delay happen in parallel
        coroutine_return(True)

    @coroutine
    @endpoint('power-off')
    def powerOff(self, handler, ps_names=None):
        ps_names = self._parse_names(ps_names)
        self.log.info('%.32r: Received power off command for %r' % (self, ps_names))

        for ps_name in ps_names:
            ps = self.power_supplies[ps_name]
            self.is_ready[ps_name] = False
            if not ps.is_enabled():
                self.log.warning("Power ouput already disabled for {}".format(ps_name))
            else:
                ps.unlock()
                ps.power_off()
                ps.lock()
                self.log.info("%.32r: %s is powered OFF" % (self, ps_name))
        coroutine_return('%s powered off' % ps_names)


    @coroutine
    @endpoint('is-enabled')
    def is_enabled(self, handler):
        is_enabled = {name: ps.is_enabled()
                    for name, ps in self.power_supplies.items()}
        coroutine_return(is_enabled)

    @coroutine
    @endpoint('is-ready')
    def is_ready(self, handler):
        is_ready = {name: (ps.is_enabled() and ps.is_ok() ) #and self.is_ready[name]
                    for name, ps in self.power_supplies.items()}
        coroutine_return(self.is_ready)


    @coroutine
    @endpoint('get-metrics')
    def get_metrics(self, handler):
        metrics = yield self._get_metrics()
        coroutine_return(metrics.as_dict())

    @coroutine
    @endpoint('get-monitoring-data')
    def monitoringMetrics(self, handler):
        self.log.info('%.32r: Received monitoring metrics request' % self)
        metrics = yield self._get_metrics()
        handler.set_header('Content-Type', 'text/plain')
        handler.write(str(metrics))

#########################################
# Power Supply REST client
#########################################

class PowerSupplyAsyncRESTClient(AsyncRESTClient):
    """
    Implements an asynchronous client that exposes the functions of the specified remote RawAcq server.

    This client is used by ch_master to start, configue and operate all the RawAcq servers in the array.

    The client is implemented using a Tornado AsyncHTTPClient. It exposes the RawAcq server methods
    (i.e REST endpoints) as local methods. The local methods are Tornado coroutines so requests to
    multiple clients can be made in parallel. This is especially beneficial since the data requests
    from the server are slow IO operations which benefit the mist from co-execution.

    The client will operate only if the IOloop in which is was created is running.

    Parameters:

        name (str): Name of the client, to be used in logging etc.

        hostname (str): The hostname of the RawAcq REST server. If `host` is None, an (experimental,
             Python-based) RawAcq REST server will be created locally.

        port (int): The port number to which the RawAcq REST server is listening. Default is port 80.

        ps_names (list of str): list of power supply names on which this client will operate. Other
            supplies will not be affected.
    """
    DEFAULT_PORT = PowerSupplyAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):

        def make_server(self, address, port):
            """ Called to create a server if hostname is None or empty or the server does not respond"""
            return PowerSupplyAsyncRESTServer(address=address, port=port)

        super(PowerSupplyAsyncRESTClient, self).__init__(
            hostname=hostname,
            port=port,
            make_server_func=make_server,
            heartbeat_string='Pc')


    # @coroutine
    # def ping(self):
    #     try:
    #         yield self.get('status')
    #         self.log.info("Successfully pinged power_supply server at %s:%i" % (self.hostname, self.port))
    #     except Exception as e:
    #         self.log.debug(repr(e))
    #         self.log.error("Can't ping power_supply server at %s:%i" % (self.hostname, self.port))
    #         coroutine_return(False)
    #     coroutine_return(True) # coroutine_return raises an exception: we don't want it in the try block

    @coroutine
    def start(self, config):
        """ If the PowerSupply remote server is not started, start it with the specified configuration

        Parameters:

            config (str or dict): If a string, the configuration is loaded from the specified
                configuration file and name. if a dict, it is passed directly to the server.

        """
        self.log.info('%s: Starting remote PowerSupply server at %s:%i with config: %r' % (self, self.hostname, self.port, config))

        if isinstance(config, str):
            config = load_yaml_config(config)

        server_info = NameSpace((yield self.status()))
        ps_names = config['units'].keys()


        if not server_info.is_started:
            self.log.info('%.32r: Server not started. Starting it with the provided configuration' % self)
            start_results = yield self.post('start', **config)  # start the server if not already started
        else:
            self.log.info('%.32r: Server is already started' % self)
            if set(server_info.ps_names) != set(ps_names):
                self.log.warning('%.32r: The server does not support the same supplies as the current config (%s instead of %s)' % (self, server_info.ps_names, ps_names))
            start_results = 'Already started'

        # result = yield self.post('start', **config)

        # if server_info.name != name:
        #     raise RuntimeError('%.32r: The remote server does not have the expected name (%s instead of %s)' % (self, server_info.name, name))


        coroutine_return(start_results)

    @coroutine
    def is_started(self):
        coroutine_return((yield self.get('is-started')))

    @coroutine
    def stop(self):
        result = yield self.get('stop')
        coroutine_return(result)

    @coroutine
    def status(self):
        result = yield self.get('status')
        coroutine_return(result)

    @coroutine
    def is_enabled(self):
        """ Indicates if the power supplies are enabled (but do not necessarily produce a valid output) """
        result = yield self.get('is-enabled')
        coroutine_return(result)

    @coroutine
    def is_ready(self):
        """ Indicates if the power supplies are enabled, have a valid output and the power up delay has elapsed.
        """
        result = yield self.get('is-ready')
        coroutine_return(result)

    @coroutine
    def list_names(self):
        result = yield self.get('list-names')
        coroutine_return(result)

    @coroutine
    def power_on(self, ps_names=None):
        result = yield self.post('power-on', ps_names=ps_names)
        coroutine_return(result)

    @coroutine
    def power_off(self, ps_names=None):
        result = yield self.post('power-off', ps_names=ps_names)
        coroutine_return(result)

    @coroutine
    def get_metrics(self):
        result = yield self.get('get-metrics')
        coroutine_return(Metrics(result))



# class PowerSupplyEasyRESTClient(object):
#     def __init__(self, hostname='localhost', port=PowerSupplyAsyncRESTServer.DEFAULT_PORT):
#         self.port = port
#         self.host = hostname
#         self.url = "http://{}:{:d}/".format(self.host, self.port)
#         print "Connected to server at {}".format(self.url)

#     def check_code(self, code):
#         if not code == 200:
#             raise RuntimeError("Got code {:d} from server at {}:{:d}".format(code, self.host, self.port))

#     def listNames(self):
#         print "Requesting list of power supply names..."
#         response = requests.get(self.url + "listNames")
#         self.check_code(response.status_code)
#         return response.json()

#     def powerOn(self, ps_names=None):
#         print "Sending power on command..."
#         response = requests.post(self.url + "powerOn", data={'ps_names': ps_names})
#         self.check_code(response.status_code)
#         print "Successfully sent power on!"

#     def powerOff(self, ps_names=None):
#         print "Sending power off command..."
#         response = requests.post(self.url + "powerOff", data={'ps_names': ps_names})
#         self.check_code(response.status_code)
#         print "Successfully sent power off!"

#     def status(self, ps_names=None):
#         print "Requesting status..."
#         response = requests.post(self.url + "status", data={'ps_names': ps_names})
#         self.check_code(response.status_code)
#         print "Status: {}".format(response.json())
#         return response.json()

#     def monitoringMetrics(self):
#         print "Requesting monitoring metrics..."
#         response = requests.get(self.url + "monitoringMetrics")
#         self.check_code(response.status_code)
#         return response.json()



def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="ps: Receiver hut power supply control server", epilog="""
        """)
    parser.add_argument('args', type=str, nargs='*', default='',  help='"server" or "client" ')
    parser.add_argument('-p', '--port', default=PowerSupplyAsyncRESTServer.DEFAULT_PORT, type=int, help="Server port")
    parser.add_argument('-n', '--host', default='localhost', type=str, help="Server hostname")
    parser.add_argument('-s', '--server', action='store_true', help='Start a server')
    return parser.parse_args(argv)

if __name__ == '__main__':
    """
    Command-line interface to start power supply REST server or client

    To start a server (on the local machine):
        ps.py [--port 54324] --server # creates and run an uninitialized local power supply server
        ps.py [config_file:]config_name server_name --server  # create and starts a local power supply server the port and with the configuration specified in the config file.

    To start a client:
        ps.py [--host localhost] [--port 54324] [command [arg1, arg2]] # starts a client that connect to the server located at the specified host and port. If the hostname is '' or does not respond, a temporary local server will be created. If a command and arguments are specified, that the command is sent to the server.
        ps.py [config_file:]config_name server_name [command [arg1, arg2, ...]]  # The ultimate command. Create client and local server if necessary. If a known command  is provided, it is sent to the server, otherwise the argument is assumed to be a configuration that is loaded and used to re(start) the server

    Port is 54324 used by defaut if not specified.

    Examples::

        ./ps.py  --server  # creates a local server on port 54324.
        ./ps.py jfc.drao pss0 --server # create, start and run local power supply server based on pss0 entry of jfc.drao config

        ./ps.py power_off all# power off all power supplies handled by the server on localhost (assuming the server is started)
        ./ps.py jfc.drao pss0 power_off all # power off all supplies managed py the server pss0 defined in config jfc.drao
        ./ps.py power_off ps_crate0 --host 10.0.0.192 --port 1234 # instruct power supply server at 10.0.0.192:1234 to power off supply named ps_crate0

    In interactive ipython sessions, server or client objects cna be used directly::

        [1] run -i ps server
        [2]
    """

    # Create our own IOLoop so we don't interfere with ipython's own ioloop.
    ioloop = IOLoop()
    ioloop.make_current()

    # Setup logging
    #log.setup_logger(__name__, stderr_log_level='warning', syslog_level='debug')
    logging.getLogger().setLevel('INFO')

    args = parse_cmdline_args(sys.argv[1:])
    port = args.port
    host = args.host
    is_server = args.server
    args = args.args
    first_arg = args[0].lower() if args else None
    pss_config = None
    pss = None  # PowerSupply server object
    psc = None  # PowerSupply client object
    # print(args.args[1:], first_arg)

    if args and (':' in args[0] or '.' in args[0]):
        if len(args) >= 2:
            print('Loading %s from config %s ' % (args[1], args[0]))
            config = NameSpace(load_yaml_config(args[0]))
            pss_name = args[1]
            pss_config = config.power_supplies.nodes[pss_name]
            args = args[2:]
        else:
            raise RuntimeError('Please specify both a config root name and power supply name')

    if is_server:
        pss_port = pss_config.port if pss_config else port
        pss = RunSyncWrapper(PowerSupplyAsyncRESTServer(port=pss_port))
        if pss_config:
            pss.start(None, name=pss_name, **pss_config)
        print("Power supply REST Server started. Waiting for REST commands.")
        pss.run()
        print("\nI'm done. Bye!")

    else:
        psc_port = pss_config.port if pss_config else port
        psc_host = pss_config.hostname if pss_config else host
        psc = RunSyncWrapper(PowerSupplyAsyncRESTClient(hostname=psc_host, port=psc_port))
        if pss_config:
            psc.start(pss_config)
        # If the client started a server, get it for the interactive session
        if hasattr(psc,'server'):
            pss = RunSyncWrapper(psc.server)
        # If there are further arguments, assume they are commands
        if args:
            cmd = args[0]
            if cmd and hasattr(psc, cmd):
                print('Sending command %s(%s) to CHIME Master server %s:%s' % (cmd, ', '.join(args[1:]), psc_host, psc_port))
                print getattr(psc, cmd)(*args[1:])


    print()
    print("If this was run in an interactive session (ipython -i), the following variables are now accessible:")
    if pss: print("   pss: PowerSupply REST server")
    if psc: print("   psc: PowerSupply REST client")
