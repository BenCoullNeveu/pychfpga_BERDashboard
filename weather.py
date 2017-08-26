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
import sqlite3

from pychfpga import Metrics, NameSpace, load_yaml_config
from rest import AsyncRESTClient, AsyncRESTServer, endpoint
from rest import coroutine, coroutine_return, sleep, IOLoop
from rest import RunSyncWrapper, SocketContext, run_client  # generic REST servers and clients

import log  # logging helper functions

archive_version = "2.3.0"

dataset = {    "barometer": {"type": "pressure"},
                "pressure": {"type": "pressure"},
               "altimeter": {"type": "pressure"},
                  "inTemp": {"type": "temperature"},
                 "outTemp": {"type": "temperature"},
              "inHumidity": {"type": "percent"},
             "outHumidity": {"type": "percent"},
               "windSpeed": {"type": "speed"},
                 "windDir": {"type": "direction"},
                "windGust": {"type": "speed"},
             "windGustDir": {"type": "direction"},
                "rainRate": {"type": "rate"},
                    "rain": {"type": "amount"},
                "dewpoint": {"type": "temperature"},
               "windchill": {"type": "temperature"},
               "heatindex": {"type": "temperature"}}

units = {   "pressure": "hPa",
         "temperature": "deg C",
             "percent": "%",
               "speed": "km/h",
           "direction": "deg",
                "rate": "mm/hr",
              "amount": "mm"
          }

# Parse command line and get .conf information.
parser = argparse.ArgumentParser(description = __doc__.split("\n")[0])
parser.add_argument("date", metavar = "<YYYYMMDD>", type=str)
parser.add_argument("-c", "--conf-file", default = "ch_translate_weather.conf")
parser.add_argument("-g", "--git-tag", action = "store", \
                    help = "Current git tag, use: " + \
                                         "-g `git describe --tags` ")
arg = parser.parse_args()

def get_wview_metrics(db_path='/var/lib/wview/archive/wview-archive.sdb'):

    # Figure out the starting UNIX time.
    # t_start = int(datetime.datetime.strptime(arg.date, "%Y%m%d").strftime("%s"))
    t_start = time.time()
    t_end = t_start + 600
    # Get the data.
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    # cur.execute("SELECT dateTime FROM archive ORDER BY dateTime LIMIT 1;")
    # t_first = cur.fetchone()[0]
    col_names = dataset.keys()
    col_string = ",".join(["dateTime", "usUnits"] + col_names)
    # cur.execute("SELECT %s FROM archive WHERE dateTime BETWEEN %d AND %d " \
    #             "ORDER BY dateTime;" % (col, t_start, t_end))
    cur.execute("SELECT %s FROM archive ORDER BY dateTime DESC LIMIT 1;" % (col_string))
    data = np.asarray(cur.fetchall(), dtype=float)
    db.close()

    metrics = Metrics(type='GAUGE')
    # Check if "usUnits" is true; if so, convert from Imperial to metric units.
    for i in range(data.shape[0]):
        time_ = data[i, 0]
        us_units = data[i, 1]
        for j in range(2, data.shape[1]):
            value = data[i, j]
            if not value:
              continue
            if us_units: # if US units, convert to metric
                type_ = dataset[col_names[j - 2]]["type"]
                if type_ == "pressure":
                  value = value * 33.86389 # inHg to hPa
                elif type_ == "temperature":
                  value = (value - 32.0) * 5.0 / 9.0 # F to C
                elif type_ == "speed":
                  value = value * 1.60934 # mi/h to km/ha
                elif type_ == "amount" or type_ == "rate":
                  value = value * 25.4 # inch to mm
            metrics.add('weather_%s' % type_, value=value)
    return metrics




class WeatherAsyncRESTServer(AsyncRESTServer):
    """
    REST interface for receiver hut GPS.
    """

    DEFAULT_PORT = 54325

    def __init__(self,  address='', port=DEFAULT_PORT, logging_params={}):
        """ power_supplies list of dict with entries 'type', 'name', and 'address'
        """
        self.gps = {}
        super(WeatherAsyncRESTServer, self).__init__(address=address, port=port, heartbeat_string='Gs')
        self.metrics_queue = Queue.Queue(1000)
        self.add_periodic_callback(self._get_metrics, 1000)


    @coroutine
    def _get_metrics(self):
        """ get the metrics from the GPS units and put them in the queue
        """
        metrics = Metrics()
        for gps_name, gps in self.gps.items():
            self.log.info('%.32r: Getting metrics for GPS %s' % (self, gps_name))
            try:
                m = gps.get_broadcast_metrics()
                metrics = Metrics()
                metrics.add(m, gps_name=gps_name)
                self.log.info('Got %i metrics' % len(metrics.metrics))
                if len(metrics.metrics):
                    if self.metrics_queue.full():
                        self.metrics_queue.get()
                    self.metrics_queue.put(metrics)
            except IOError as e:
                self.log.warning('%r: Error while trying to access metric from %s\nThe error is:\n%r' % (self, gps_name, e))
            except Exception as e:
                self.log.error(e)
                raise

        self.log.info('Queue has %i metrics blocks' % self.metrics_queue.qsize())

    ##################
    # Server commands
    ##################

    @coroutine
    @endpoint('start')
    def start(self, handler, **config):
        """ Start the GPS server with provided config
        """
        self.log.info('%r: Received start command' % self)
        if self.gps:
            raise RuntimeError('%.32r: Power Supply server is already started' % self)
        self.config = NameSpace(config)
        units = self.config.units or {}
        for name, params in units.items():
            self.log.debug('%r: Creating GPS handler %s' % (self, name))
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
        self.log.info('%.32r: Received monitoring metrics request' % self)
        metrics = Metrics()
        for i in range(self.metrics_queue.qsize()):
            m = self.metrics_queue.get()
            metrics.add(m)
        self.log.info('%r: sending %i metrics' % (self, len(metrics.metrics)))
        handler.set_header('Content-Type', 'text/plain')
        handler.write(str(metrics))

#########################################
# Power Supply REST client
#########################################

class WeatherAsyncRESTClient(AsyncRESTClient):
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
    DEFAULT_PORT = WeatherAsyncRESTServer.DEFAULT_PORT

    def __init__(self, hostname='localhost', port=DEFAULT_PORT):
        super(WeatherAsyncRESTClient, self).__init__(
            hostname=hostname, port=port,
            server_class= WeatherAsyncRESTServer,
            heartbeat_string='Gc')


    @coroutine
    def start(self, config):
        """ If the PowerSupply remote server is not started, start it with the specified configuration

        Parameters:

            config (str or dict): If a string, the configuration is loaded from the specified
                configuration file and name. if a dict, it is passed directly to the server.

        """
        #print('start!')
        self.log.info('%s: Starting remote PowerSupply server at %s:%i with config: %r' % (self, self.hostname, self.port, config))

        if isinstance(config, str):
            config = load_yaml_config(config)
        result = self.post('start', **config)
        coroutine_return('GPS server started')

    @coroutine
    def stop(self):
        result = yield self.get('stop')
        coroutine_return(result)

    # @coroutine
    # def status(self):
    #     result = yield self.get('status')
    #     coroutine_return(result)


    @coroutine
    def list_names(self):
        result = yield self.get('list-names')
        coroutine_return(result)


    # @coroutine
    # def get_metrics(self):
    #     result = yield self.get('get-metrics')
    #     coroutine_return(Metrics(result))



def main():
    """ Command-line interface to launch and operate the GPS server.
    """
    # Setup logging
    log.setup_basic_logging('DEBUG')
    client, server = run_client(sys.argv[1:], WeatherAsyncRESTServer, WeatherAsyncRESTClient, object_name ='GPS', server_config_path='gps.servers')
    return client, server

if __name__ == '__main__':
    client, server = main()
