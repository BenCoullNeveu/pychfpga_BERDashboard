#!/usr/bin/env python
"""
REST Server and clients for the CHIME receiver hut GPS units Spectrum Instruments TM-4D, which are
accessed through the StarTech NETRS232 serial-to-ethernet adapters.

"""

import logging
import sys
import argparse
import time
import datetime
import calendar
import Queue

# import tornado

# from pychfpga.Agilent_N5764A import AgilentN5764AHandler
from pychfpga import Metrics, NameSpace, load_yaml_config
from rest import AsyncRESTClient, AsyncRESTServer, endpoint, coroutine, coroutine_return, sleep, IOLoop, RunSyncWrapper, SocketContext  # generic REST servers and clients
import log  # logging helper functions

class SpectrumInstrumentsTM4D(SocketContext):
    """
    A class to communicate with SpectrumInstruments TM4D GPS receiver
    """

    def __init__(self,  hostname, port=1001, timeout=0.5, verbose=1):

        super(SpectrumInstrumentsTM4D, self).__init__(hostname=hostname, port=port, timeout=timeout)
        self.log = log.get_logger(self)
        print "Initializing direct LAN Connection at %s:%i" % (hostname, port)
        self.verbose = verbose
        self.log.debug('Initializing instrument')
        self.polling_mode = None
        self.last_time = None
        self.buffer = '' # used in broadcast processing only
        self.get_methods = {
            '50': None, # Acknowledge
            '51': self.get_date_time,
            '52': self.get_position,
            '53': self.get_altitude,
            '55': self.get_mask_angle,
            '56': self.get_user_time_bias,
            '57': self.get_timing_mode,
            '59': self.get_geometric_quality_and_almanac_status,
            '60': self.get_mux1_output_source,
            '61': self.get_timing_status,
            '62': None, # Event Time Tag
            '63': None, # POP/ETT Status
            '64': self.get_oscillator_tuning_mode,
            '65': self.get_alarm_status,
            '66': None, # Reserved, #66,T28F2A.OBJ,NEWEPPSD10A.HEX   ,312102035321F,28F2,031816
            '68': self.get_mux2_output_source,
            '69': self.get_tracking_channel_status,
            '70': None, # Serial time message format
            '71': None, # Serial time code format
            '72': None, # Reserved
            '73': None, # ETT Parameters
            '74': None, # POP Parameters
            '75': self.get_speed_and_heading,
            '76': self.get_nmea_info,
            '74': None, # Phase lock status, old units (see #80)
            '78': self.get_user_options,
            '79': self.get_coast_timer,
            '80': self.get_phase_lock_status,
            '81': self.get_leap_seconds,
            '82': None, # Undocumented, #82,0,1,8,8,F,F
            '84': None, # Undocumented, #84,1,0,5,3,2,1,F
            }

    # def __repr__(self):
    #     if self.instrument_model:
    #         return '%s %s @%s:%i' % (self.instrument_name, self.instrument_model, self.ip_addr, self.ip_port)
    #     else:
    #         return 'Unknown Instrument @%s:%i' % (self.ip_addr, self.ip_port)

    ###################################
    # Basic read/write commands
    ###################################


    def command(self, *args, **kwargs):
        """
        Sends a command to the instrument. The terminator is added automatically.
        """
        flush = kwargs.get('flush', False)
        with self.socket(flush=flush):
            self.send('#%s\r\n' % ','.join(str(s) for s in args))

    def query(self, command, reply=None, flush=False):
        """
        Sends a command to the instrument and returns the reply string without the terminator or trailing spaces.
        """
        if reply is None:
            with self.socket(flush=flush):
                self.send('#13,%s\r\n' % command)
                try:
                    reply = ''
                    while True:
                        s = self.recv(16384)
                        print('received %r (%s)' % (s, '\r\n' in s))
                        reply += s
                        if '\r\n' in s:
                            break
                except IOError:
                    raise IOError('%r: timout while waiting for reply for command %s' % (self, command))
        args = reply.rstrip().split(',') # remove trailing spaces or CR or LF
        assert args[0] == '#' + command, 'Reply is not for command %s' % command
        return args[1:]


    ###################################
    # GPS commands
    ###################################

    # Set commands

    def set_mask_angle(self, angle_code):
        """ Sets mask angle of the GPS.

        Parameters:
            angle_code (int): 0=5 deg, 1=15 deg, 2=20 deg
        """
        if angle_code not in [0,1,2]:
            raise ValueError('%r: mask angle argument is 0 (5 deg), 1 (15 deg) or 2 (20 deg)' % self)

        self.command('05', angle_code)

    def set_user_time_bias(self, bias):
        """ Sets the user time bias.

        Parameters:
            bias (int): time bias in ns (-99999 to 99999). Negative values cause the timing functions to occur later
                in absolute time while positive values cause them to occur earlier.
        """
        if not  -999999 <= bias <= 999999:
            raise ValueError('%r: bias must be between -999999 and 99999 ns' % self)

        self.command('06', '%+05i' % bias)

    def set_timing_mode(self, mode):
        """ Sets the timing mode of the GPS.

        Parameters:
            mode (int): 0=Dynamic, 1=Static, 2=Auto survey
        """
        if mode not in [0,1,2]:
            raise ValueError('%r: timing modeargument is 0 (Dynamic), 1 (Static) or 2 (Survey)' % self)

        self.command('07', mode)

    def master_reset(self):
        """ Resets the GPS.
        """
        self.command('08', 1)

    def set_multiplexer_output_source(self, mux1, mux2):
        """ Selects the output of the multiplexers.

        Parameters:
            mux1 (int): 0=Dynamic, 1=Static, 2=Auto survey
                0: 10 MHz output
                1: 5 MHz output
                2: 1 MHz output
                3: 100 kHz output
                4: 10 kHz output
                5: 1 kHz output
                6: baseband IRIG output (if installed)
                7: PPS output
                8: OFF (newer TM-4's only)

            mux2 (int):
                0: for 10 MHz output
                1: for Mux1 mirror output
                2: for PPS
                3: for optional output 1
                4: for optional output 2
                5: for optional output 3
                6: for baseband IRIG (if installed)
                7: for baseband NASA-36 (if installed)
                8: for OFF (newer TM-4's only)
        """
        if not 0 <= mux1 <= 8:
            raise ValueError('%r: Mux1 selector value must be between 0 and 8' % self)
        if not 0 <= mux2 <= 8:
            raise ValueError('%r: Mux2 selector value must be between 0 and 8' % self)

        self.command('09', mux1)
        self.command('14', mux1)

    def set_broadcast_output(self, mode):
        """ Sets the broadcast output mode.

        Parameters:
            mode (int): 0= output all messages, 1=Output events and acknowledges only.
        """
        if mode not in [0,1]:
            raise ValueError('%r: broadcast mode must be  0 (all messages) or 1 (events or acknowledge only)' % self)

        self.command('12', mode)

    def set_polling_mode(self, mode=1):
        """ Sets the polling mode.

        Parameters:
            mode (int): 0=automatic broadcast, 1=polling with acknowledge, 2=polling without acknowledge.
        """
        if mode not in [0,1,2]:
            raise ValueError('%r:polling mode must be 0=automatic broadcast, 1=polling with acknowledge, 2=polling without acknowledge' % self)

        self.command('17', mode)

        self.polling_mode = mode
        if mode: # if we are not in broadcase mode, flush any data in the buffers
            with self.socket(flush=True, flush_timeout=1):
                pass

    def set_position(self, lat, lon, alt):
        """ Sets the position to use in the static timing mode.

        Parameters:
            lat (float): latitide in fractional degrees, positive=north, negative=south
            lon (float): longitude in fractional degrees, positive=east, negative=west
            alt : altitude in meters
        """
        self.command('19', '%02i%5.2f' % (abs(lat), abs(lat) % 1 * 60),
                           'N' if lat>=0 else 'S',
                           '%03i%5.2f' % (abs(lon), abs(lon) % 1 * 60),
                           'E' if lon>=0 else 'W',
                           '%+05.0f' % alt)

    def set_antenna_alarm_enable(self, enable):
        """ Enables or disables the antenna alarm.

        Parameters:
            enable (bool)
        """
        self.command('23', int(bool(enable)))

    def set_pps_output_source(self, source):
        """ Sets the source of the Pulse-Per-Second (PPS) signal.

        Parameters:
            source (int): 0=LOW at power-on/GPSPPS on Time Valid/FILPPS on lock, 1= LOW at power-on/FILPPS on lock, 2= LOW on power-up/GPSPPS on valid time and Lock, 3=GPSPPS always
        """
        if source not in [0,1,2,3]:
            raise ValueError('%r: PPS source 0=LOW at power-on/GPSPPS on Time Valid/FILPPS on lock, 1= LOW at power-on/FILPPS on lock, 2= LOW on power-up/GPSPPS on valid time and Lock, 3=GPSPPS always' % self)

        self.command('24', source)

    # Get commands

    def get_method_for(self, reply):
        """Return the method that can process the specified reply string.
        """
        cmd = reply.rstrip().split(',')[0] # remove trailing spaces or CR or LF
        if not cmd.startswith('#'):
            raise IOError('%r: Invalid reply format %s' % (self, reply))
        cmd = cmd[1:]
        if cmd not in self.get_methods:
            raise IOError('%r: Unknown reply code %s' % (self, reply))
        else:
            return self.get_methods[cmd]

    def get_date_time(self, reply=None, metrics=None):
        """Return the current date and time.

        Returns:
            datetime: date and time as a Python datetime object
        """
        date, time = self.query('51', reply)

        t= datetime.datetime(
            int(date[4:]),  int(date[2:4]), int(date[:2]), # year, month, day
            int(time[:2]), int(time[2:4]), int(time[4:6])) # hours, minutes, seconds

        self.last_time = calendar.timegm(t.timetuple())
        return t

    def get_position(self, reply=None, metrics=None):
        """Return the current position, GPS availability and numer of satellites used.

        Returns:
            (lat, lon, avail, n_sat) tuple:
                lat (float): latitude in fractional degrees
                lon (float): longitude in fractional degrees
                avail (bool): GPS availability (0=unavailable, 1=available)
                n_sat (int): number_of_satellites (0-12)
        """
        lat, ns, lon, ew, avail, n_sat = self.query('52', reply)

        return (
            (float(lat[:2]) + float(lat[2:]) / 60) * (-1 if ns == 'S' else 1),
            (float(lon[:3]) + float(lon[3:]) / 60) * (-1 if ew == 'W' else 1),
            bool(int(avail)),
            int(n_sat, 16))

    def get_altitude(self, reply=None, metrics=None):
        """Return the current altitude.

        Returns:
            float: signed altitude in meters
        """
        alt, units = self.query('53', reply)
        assert units=='M', 'Units are not in meters'
        return float(alt)

    def get_mask_angle(self, reply=None, metrics=None):
        """Return the current mask_angle.

        Returns:
            int: mask angle code: 0 (5 deg), 1 (15 deg) or 2 (20 deg)
        """
        angle_code, datum = self.query('55', reply)
        assert datum == '47', 'datum is not WGS84'
        mask_angle = int(angle_code)
        if metrics is not None:
            metrics.add('gps_mask_angle', value=mask_angle, type='gauge')
        return mask_angle

    def get_user_time_bias(self, reply=None, metrics=None):
        """Return the current user time bias.

        Returns:
            int: time bias in ns
        """
        (bias, ) = self.query('56', reply)
        time_bias = int(bias)
        if metrics is not None:
            metrics.add('gps_time_bias', value=time_bias, type='gauge')
        return time_bias

    def get_timing_mode(self, reply=None, metrics=None):
        """Return the current timing mode.

        Returns:
            int: timing mode:
                0: Dynamic Timing Mode
                1: Static Timing Mode
                3: Auto Survey Mode
        """
        (mode, ) = self.query('57', reply)
        timing_mode = int(mode)
        if metrics is not None:
            metrics.add('gps_mask_angle', value=timing_mode, type='gauge')
        return timing_mode

    def get_geometric_quality_and_almanac_status(self, reply=None, metrics=None):
        """Return the geometric quality (GQ) and almanac status.

        Returns:
            (gq, almanac_status) tuple where:
                gq (int): geometric quality (0-9)
                almanac_status (int): 0: OK, 1: no almanac, 2: almanac is old
        """
        gq, almanac_status = self.query('59', reply)
        gq, almanac_status = int(gq), int(almanac_status)
        if metrics is not None:
            metrics.add('gps_geometric_quality', value=gq, type='gauge')
            metrics.add('gps_almanac_status', value=almanac_status, type='gauge')
        return gq, almanac_status

    def get_oscillator_tuning_mode(self, reply=None, metrics=None):
        """Return the oscillator tuning mode.

        Returns:
            osc_tuning_mode (int):
                1: oscillator warm-up
                2: course adjust
                3: course adjust standby
                4: fine adjust
                5: fine adjust hold)
        """
        (osc_tuning_mode, ) = self.query('64', reply)
        osc_tuning_mode = int(osc_tuning_mode)
        if metrics is not None:
            metrics.add('gps_osc_tuning_mode', value=osc_tuning_mode, type='gauge')
        return osc_tuning_mode

    def get_alarm_status(self, reply=None, metrics=None):
        """Return the coast, antenna and 10 MHz alarm status.

        Returns:
            (coast_alarm, antenna_alarm, clk_alarm) tuple where:
                coast_alarm (bool): coast alarm
                antenna_alarm (bool): antenna alarm
                clk_alarm (bool): 10 MHz output alarm
        """
        coast_alarm, antenna_alarm, clk_alarm = self.query('65', reply)
        coast_alarm, antenna_alarm, clk_alarm = bool(int(coast_alarm)), bool(int(antenna_alarm)), bool(int(clk_alarm))
        if metrics is not None:
            metrics.add('gps_coast_alarm', value=coast_alarm, type='gauge')
            metrics.add('gps_antenna_alarm', value=antenna_alarm, type='gauge')
            metrics.add('gps_10MHz_alarm', value=clk_alarm, type='gauge')
        return coast_alarm, antenna_alarm, clk_alarm

    def get_mux1_output_source(self, reply=None, metrics=None):
        """Return the mux output source.

        Returns:
                mux1 (int): Mux 1 source
        """
        time_port_baud_rate, mux1, unknown = self.query('60', reply) # undocumented 'unknown' parameter ('+00')
        mux1 = int(mux1)
        if metrics is not None:
            metrics.add('gps_mux1_source', value=mux1, type='gauge')
        return mux1

    def get_timing_status(self, reply=None, metrics=None):
        """Return the timing status.

        Returns:
                status (int): 0: time not valid; 1: time valid
        """
        (status, ) = self.query('61', reply)
        status = int(status)
        if metrics is not None:
            metrics.add('gps_timing_status', value=status, type='gauge')
        return status


    def get_mux2_output_source(self, reply=None, metrics=None):
        """Return the mux output source.

        Returns:
                mux2 (int): Mux 2 source
        """
        (mux2, ) = self.query('68', reply)
        mux2 = int(mux2)
        if metrics is not None:
            metrics.add('gps_mux2_source', value=mux2, type='gauge')
        return mux2

    def get_tracking_channel_status(self, reply=None, metrics=None):
        """Return the status of each satellite.

        Returns:
            (statellite_status_map ,  receiver_status) tuple where:
                satellite_status_map = {satellite_prn: {constellation_status: x, tracking_status: y, signal_quality:v, ephemeris_status: z},...}
                satellite_prn (int): satellite id
                constellation_status (int): constellation status ( 0/1 = not included/included in current constellation)
                tracking_status (str): tracking status (A = acquisition/reacquisition, S = searching, 0-9 = SQ)
                signal_quality (int): tracking status in numeric format: -2: searching, -1: acquisition/reaquisition, 0-9: signal quality
                ephemeris_status (int): 0/1 not collected/collected
                receiver_status (int):
                    2 = search the sky
                    3 = Almanac collect
                    4 = Ephemeris collect
                    5 = acquisition
                    6 = position
        """
        s = self.query('69', reply)
        satellite_status_map = NameSpace()
        while len(s) >= 4:
            prn, cs, ts, es = s[:4]
            satellite_status_map[int(prn)] = NameSpace(
                constellation_status = int(cs),
                tracking_status = ts,
                signal_quality = -2 if ts=='S' else -1 if ts=='A' else int(ts),
                ephemeris_status = int(es))
            s = s[4:]
        receiver_status = int(s[0])

        if metrics is not None:
            metrics.add('gps_receiver_status', value=receiver_status, type='gauge')
            for sat_number, sat_info in satellite_status_map.items():
                metrics.add('gps_constellation_status', satellite_number=sat_number, value=sat_info.constellation_status, type='gauge')
                metrics.add('gps_signal_quality', satellite_number=sat_number, value=sat_info.signal_quality, type='gauge')
                metrics.add('gps_ephemeris_status', satellite_number=sat_number, value=sat_info.ephemeris_status, type='gauge')

        return satellite_status_map, receiver_status

    def get_speed_and_heading(self, reply=None, metrics=None):
        """Return the current speed and heading

        Returns:
            (speed, heading) tuple:
                speed (float): speed in m/s
                heading (float): heading in decimal degrees
        """
        speed, heading = self.query('75', reply)
        return (float(speed), float(heading))


    def get_nmea_info(self, reply=None, metrics=None):
        """Return higher precision position, speed and course.

        Returns:
            NameSpace containing:
                lat (float): latitude in fractional degrees
                lon (float): longitude in fractional degrees
                alt (float): altitude in meters
                fix (bool): GPS fix validity (0=not valid, 1=valid)
                n_sat (int): number_of_satellites (0-12)
                h_dilution: horizontal dilution (0 - 99.9)
                speed (float): speed over ground in knots,
                course (float): course in degrees
        """
        lat, ns, lon, ew, alt, alt_units, fix, n_sat, h_dil, speed, course = self.query('76', reply)

        info = NameSpace(
            lat = (float(lat[:2]) + float(lat[2:]) / 60) * (-1 if ns == 'S' else 1),
            lon = (float(lon[:3]) + float(lon[3:]) / 60) * (-1 if ew == 'W' else 1),
            alt = float(alt),
            fix = bool(fix),
            n_sat = int(n_sat),
            h_dilution = float(h_dil),
            speed = float(speed),
            course = float(course))

        if metrics is not None:
            metrics.add('gps_latitude', value=info.lat, type='gauge')
            metrics.add('gps_longitude', value=info.lon, type='gauge')
            metrics.add('gps_altitude', value=info.alt, type='gauge')
            metrics.add('gps_fix_valid', value=info.fix, type='gauge')
            metrics.add('gps_number_of_satellites', value=info.n_sat, type='gauge')
            metrics.add('gps_horiz_dilution', value=info.h_dilution, type='gauge')
            metrics.add('gps_speed', value=info.speed, type='gauge')
            metrics.add('gps_course', value=info.course, type='gauge')
        return info

    def get_user_options(self, reply=None, metrics=None):
        """Return the current antenna alarm elable status and the PPS source

        Returns:
            (antenna_alarm_enable,pps_source) tuple:
                antenna_alarm_enable (bool): antenna alarm is enabled
                pps_source (int): PPS source
        """
        aa_enabled, pps_source, _, _, _, _ = self.query('78', reply)
        aa_enabled, pps_source = (bool(aa_enabled), int(pps_source))
        if metrics is not None:
            metrics.add('gps_antenna_alarm_detection_enabled', value=aa_enabled, type='gauge')
            metrics.add('gps_pps_source', value=pps_source, type='gauge')
        return aa_enabled, pps_source

    def get_coast_timer(self, reply=None, metrics=None):
        """Return the  Amount of time that the unit has been in Coast (Mode 3 or Mode 5)

        Returns:
            coast_time (float): in fractional hours
        """
        # actual reply is ['#79', '00000000', '05335027', '02902627', '00000000', '4']
        # _, time = self.query('79')
        # return float(time[:4]) + float(time[4:6])/60 + float(time[6:])/3600
        coast_timer_values = self.query('79', reply)
        coast_timer_values = [int(c) for c in coast_timer_values]
        if metrics is not None:
            # metrics.add('gps_coast_time', value=coast_time, type='gauge')
            for i, c in enumerate(coast_timer_values):
                metrics.add('gps_coast_time', field=i, value=c, type='gauge')
        return coast_timer_values

    def get_phase_lock_status(self, reply=None, metrics=None):
        """Return the current phase lock status.

        Returns:
            int: phase lock status:
                0: OCXO warm-up (OSC mode: 1, Phase lock state: NO)
                1: Coarse OCXO tuning (OSC mode:2, Phase lock state: NO)
                2: Entered Coast condition during Mode 2 tuning (OSC mode:3, Phase lock state: NO)
                3: Fine tuning OCXO, waiting for phase lock. (OSC mode:4, Phase lock state: NO)
                4: Fine tuning OCXO, approaching phase lock (OSC mode:4, Phase lock state: NO)
                5: Entered Coast condition during Mode 4 tuning (OSC mode:5, Phase lock state: NO)
                9: Phase Lock Achieved (OSC mode:4, Phase lock state: YES)
        """
        (status, ) = self.query('80', reply)
        phase_lock_status = int(status)
        if metrics is not None:
            metrics.add('gps_phase_lock_status', value=phase_lock_status, type='gauge')
        return phase_lock_status

    def get_leap_seconds(self, reply=None, metrics=None):
        """
        Return the number of Leap Seconds that have been introduced to UTC Time since the beginning
        of GPS Time

        Returns:
            valid (bool): leap seconds info is valid
            leap_seconds(int): number of leap seconds
        """
        time_mode, valid, leaps  = self.query('81', reply)
        valid, leap_seconds = bool(int(valid)), int(leaps)
        if metrics is not None and valid:
            metrics.add('gps_leap_seconds', value=leap_seconds, type='gauge')
        return valid, leap_seconds

    def poll_metrics(self):
        metrics = Metrics()
        with self.socket(flush=True):
            if self.polling_mode != 1:
                self.set_polling_mode(1)
            for command, get_method in self.get_methods.items():
                if get_method:
                    try:
                        get_method(metrics=metrics)
                    except IOError:
                        self.log.warning('%r: Could not get reply for command %s' % (self, command))
        return metrics

    def get_broadcast_metrics(self):
        metrics = Metrics()
        with self.socket():# don't flush, data is presumably constantly coming in
            if self.polling_mode != 0:
                self.set_polling_mode(0)
            while True:
                # process whatever replies are in the buffer until all is left are partial commands

                while True:
                    # Remove anything up to '#' in case we got a partial buffer
                    if not self.buffer.startswith('#'):
                        pos = self.buffer.find('#')
                        if pos >=0:
                            self.buffer = self.buffer[pos:]
                    # find a string up to \r\n
                    pos = self.buffer.find('\r\n')
                    if pos <=0: # if there is not complete string, give up for now
                        break
                    reply = self.buffer[:pos+1]
                    self.buffer = self.buffer[pos+1:]
                    print('Got broadcast string %r' % reply)
                    get_method = self.get_method_for(reply)
                    if get_method:
                        get_method(reply=reply, metrics=metrics)

                # try to get new replies to complete partials command. If there are none,
                try:
                    reply = self.recv(timeout = 0.8) # must be <1 s because new data is coming every second and we'll never get out of here
                    self.buffer = (self.buffer + reply).lstrip()
                except IOError: # there was no data, this must be the end
                    break
        return metrics

    def configure_gps(self,  lat=49.320683333333335, lon=-119.62329666666666, alt=562.0):
        """
        Configure the GPS for standard CHIME operations.

        The GPS is put in 'static' mode, where it tries only to get time information and not the
        position infromation. This requires less satellites and presumably provides for a more
        stable time signal. In this mode a static position is given to the GPS so it will know what
        satellites to search for. The default position is the center of the CHIME array at DRAO,
        Penticton, BC, Canada.

        """
        with self.socket(flush=True):
            self.set_polling_mode()
            self.set_mask_angle(0)
            self.set_timing_mode(1) # Static. Position is set below.
            self.set_position(lat, lon, alt)
            self.set_pps_output_source(1) # FILPPS only when fully locked
            self.set_multiplexer_output_source(6, 0) # Mux1=IRIGB, Mux2= 10 MHz
            self.set_user_time_bias(0)
            self.set_antenna_alarm_enable(True)
            pass

class GPSAsyncRESTServer(AsyncRESTServer):
    """
    REST interface for receiver hut GPS.
    """

    DEFAULT_PORT = 54325

    def __init__(self,  address='', port=DEFAULT_PORT, logging_params={}):
        """ power_supplies list of dict with entries 'type', 'name', and 'address'
        """
        self.gps = {}
        super(GPSAsyncRESTServer, self).__init__(address=address, port=port, heartbeat_string='Gs')
        self.metrics_queue = Queue.Queue(1000)
        self.add_periodic_callback(self._get_metrics, 1000)


    @coroutine
    def _get_metrics(self):
        """ get the metrics from the GPS units and put them in the queue
        """
        metrics = Metrics()
        for gps_name, gps in self.gps.items():
            print('%.32r: Getting metrics for GPS %s' % (self, gps_name))
            metrics.add(gps.get_broadcast_metrics(), gps_name=gps_name)
        if self.metrics_queue.full():
            self.metrics_queue.get()
        self.metrics_queue.put(metrics)


    ##################
    # Server commands
    ##################

    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        """ Start the GPS server with provided config
        """
        if self.gps:
            raise RuntimeError('%.32r: Power Supply server is already started' % self)
        self.config = NameSpace(config)
        units = self.config.units or {}
        for name, params in units.items():
            gps = SpectrumInstrumentsTM4D(**params)
            self.gps[name] = gps
        coroutine_return('GPS server started')

    @coroutine
    @endpoint('stop')
    def stop(self, handler):
        if not self.gps:
            self.log.warning('%.32r: Power Supply server is not started' % self)
        else:
            self.gps = {}
        coroutine_return('GPS server stopped')

    # @coroutine
    # @endpoint('status')
    # def status(self, handler):
    #     # ps_names = self._parse_names(ps_names)
    #     # self.log.info('%.32r: Received status request for %r' % (self, ps_names))
    #     stati = dict(is_started=bool(self.power_supplies),
    #                  ps_names=self.power_supplies.keys())
    #     for ps_name, ps in self.power_supplies.items():
    #         stati[ps_name] = ps.status()
    #         self.log.info('%.32r: Status of %s is %s' % (self, ps_name, stati[ps_name]))
    #     coroutine_return(stati)


    @coroutine
    @endpoint('list-names')
    def listNames(self, handler):
        self.log.info('%.32r: Received list names request' % self)
        coroutine_return(self.gps.keys())



    @coroutine
    @endpoint('get-monitoring-data')
    def monitoringMetrics(self, handler):
        print('%.32r: Received monitoring metrics request' % self)
        metrics = Metrics()
        for i in range(self.metrics_queue.qsize()):
            m = self.metrics_queue.get()
            print m
            metrics.add(m)
        handler.set_header('Content-Type', 'text/plain')
        handler.write(str(metrics))

#########################################
# Power Supply REST client
#########################################

class GPSAsyncRESTClient(AsyncRESTClient):
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
    DEFAULT_PORT = GPSAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):

        super(GPSAsyncRESTClient, self).__init__(
            hostname=hostname, port=port,
            make_server_func= lambda address, port: GPSAsyncRESTServer(address=address, port=port),
            heartbeat_string='Gc')


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
        coroutine_return('GPS server started')

    @coroutine
    def stop(self):
        result = yield self.get('stop')
        coroutine_return(result)

    @coroutine
    def status(self):
        result = yield self.get('status')
        coroutine_return(result)


    @coroutine
    def list_names(self):
        result = yield self.get('list-names')
        coroutine_return(result)


    # @coroutine
    # def get_metrics(self):
    #     result = yield self.get('get-metrics')
    #     coroutine_return(Metrics(result))




def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="ps: Receiver hut power supply control server", epilog="""
        """)
    parser.add_argument('args', type=str, nargs='*', default='',  help='"server" or "client" ')
    parser.add_argument('-p', '--port', default=GPSAsyncRESTServer.DEFAULT_PORT, type=int, help="Server port")
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
    logging.getLogger().setLevel('DEBUG')

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
            all_config = NameSpace(load_yaml_config(args[0]))
            server_name = args[1]
            config = all_config.gps.servers[server_name]
            args = args[2:]
        else:
            raise RuntimeError('Please specify both a config root name and power supply name')

    if is_server:
        server_port = config.port if config else port
        server = RunSyncWrapper(GPSAsyncRESTServer(port=server_port))
        if config:
            server.start(None, name=server_name, **config)
        print("GPS REST Server started. Waiting for REST commands.")
        server.run()
        print("\nI'm done. Bye!")

    else:
        client_port = config.port if config else port
        client_host = config.hostname if config else host
        client = RunSyncWrapper(GPSAsyncRESTClient(hostname=client_host, port=client_port))
        if config:
            client.start(config)
        # If the client started a server, get it for the interactive session
        if hasattr(client,'server'):
            server = RunSyncWrapper(client.server)
        # If there are further arguments, assume they are commands
        if args:
            cmd = args[0]
            if cmd and hasattr(client, cmd):
                print('Sending command %s(%s) to CHIME Master server %s:%s' % (cmd, ', '.join(args[1:]), client_host, client_port))
                print getattr(client, cmd)(*args[1:])
    print()
    print("If this was run in an interactive session (ipython -i), the following variables are now accessible:")
    if server: print("   server: GPS REST server")
    if client: print("   client: GPS REST client")
