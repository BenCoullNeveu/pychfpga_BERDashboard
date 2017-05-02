#!/usr/bin/env python
from __future__ import absolute_import, division, print_function

import os
import sys
import argparse

from Queue import Queue
import SocketServer
import threading
# import logging
# import os
import struct
import numpy as np
import h5py
import datetime


from rest import AsyncRESTServer, endpoint, AsyncRESTClient, coroutine, coroutine_return, IOLoop
from pychfpga import NameSpace



class RawAcqUDPServer(SocketServer.ThreadingUDPServer):
    class UDPHandler(SocketServer.BaseRequestHandler):
        '''
        Puts the data in the queue. Another process will pull the data from the queue and write it
        to a hdf5 file.
        '''
        def handle(self):
            data, socket = self.request
            port = self.server.server_address[1]
            (probe_id, stream_id, word_length,
                timestamp) = struct.unpack_from('>BHHL', data)
            chan = probe_id & 0x0F
            adc_data = np.fromstring(data[9:2057], dtype=np.int8)
            self.server.data_queue.put((timestamp, port, chan, adc_data))

    def __init__(self, server_address, data_queue):
        self.data_queue = data_queue
        SocketServer.UDPServer.__init__(self, server_address, self.UDPHandler)  # cannot use super(...): this is an old-style class

class hdf5TimestreamData(object):
    def __init__(self, filestring):
        self.N_SAMP = 2048
        #self.N_ANT = 1
        self.f = h5py.File(filestring, 'w')
        self.timestampDataset = self.f.create_dataset('timestamp',
                    (1, 1), dtype=np.uint32, maxshape=(None, 1))
        self.slotDataset = self.f.create_dataset('slot', (1, 1),
                                            dtype=np.int32, maxshape=(None, 1))
        self.crateDataset = self.f.create_dataset('crate', (1, 1),
                                            dtype=np.int32, maxshape=(None, 1))
        self.antDataset = self.f.create_dataset('ant', (1, 1),
                                            dtype=np.int32, maxshape=(None, 1))
        self.timestreamDataset = self.f.create_dataset('timestream',
                        (1, self.N_SAMP), dtype=np.int8,
                        maxshape=(None, self.N_SAMP))
        self.n_times = 1
        self.n = 0

    def write_singletime(self, timestamp, port, ant, timestream):
        if self.n == self.n_times:
            self.n_times = self.n + 1
            self.timestampDataset.resize((self.n_times, 1))
            self.slotDataset.resize((self.n_times, 1))
            self.crateDataset.resize((self.n_times, 1))
            self.antDataset.resize((self.n_times, 1))
            self.timestreamDataset.resize((self.n_times, self.N_SAMP))
        elif self.n < self.n_times:
            pass
        else:
            print("ut oh...")
        print(self.n_times)
        self.timestampDataset[self.n] = timestamp
        self.antDataset[self.n] = ant
        self.slotDataset[self.n] = port % 100  # assume port gives slot
        self.crateDataset[self.n] = ((port/100) % 10) - 1
        self.timestreamDataset[self.n] = timestream
        self.n += 1

    def close(self):
        self.f.close()

# class hdf5LiveTimestreamData(object):
#     def __init__(self, filestring):
#         self.N_SAMP = 2048
#         self.N_ANT = 16
#         self.f = h5py.File(filestring, 'a')
#         self.timestampDataset = self.f.require_dataset('timestamp',
#                   (16, self.N_ANT), dtype=np.int32, maxshape=(None, self.N_ANT))
#         self.portDataset = self.f.require_dataset('slot', (16, 1),
#                                             dtype=np.int32, maxshape=(None, 1))
#         self.timestreamDataset = self.f.require_dataset('timestream',
#                         (16, self.N_ANT, self.N_SAMP), dtype=np.int8,
#                         maxshape=(None, self.N_ANT, self.N_SAMP))


#     def init(self, n_times, n):
#         self.n_times = n_times
#         self.n = n


#     def write_singletime(self, timestamp, port, timestream):
#         if self.n == self.n_times:
#             self.n_times = self.n+1
#             #self.timestampDataset.resize((self.n_times, self.N_ANT))
#             #self.portDataset.resize((self.n_times, 1))
#             #self.timestreamDataset.resize((self.n_times, self.N_ANT, self.N_SAMP))
#         elif self.n < self.n_times:
#             pass
#         else:
#             print "ut oh..."
#         print self.n_times
#         self.timestampDataset[self.n] = timestamp
#         self.portDataset[self.n] = port % 100  # assume port gives slot
#         self.timestreamDataset[self.n] = timestream
#         self.n += 1

#     def close(self):
#         self.f.close()



class dataWriter(object):
    def __init__(self, data_queue):
        if not isinstance(data_queue, (list, tuple)):
            self.data_queue = [data_queue]
        else:
            self.data_queue = data_queue
        self.n_file = 0
        self.N_ELEMENT_PER_FILE = 2048*64
        self.time_name = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        self.base_dir = './'+ self.time_name + '_CHIME_pfFirmwareC0_rawadc/'
        #self.live_base_dir = '/mnt/agogo/livedata/'
        try:
            os.mkdir(self.base_dir)
        except:
            print("couldn't make directory... using current one.")
            self.base_dir = './'
        self.h5name = self.base_dir + "{0:06d}.h5".format(self.n_file)
        self.h5file = hdf5TimestreamData(self.h5name)
        self.run = True
        #self.live_name = self.live_base_dir + "live_adc_data.h5"
        #self.live_h5file = hdf5LiveTimestreamData(self.live_name)
        #self.live_h5file.init()
        #self.live_h5file.close()

    def write(self):
        while self.run:
            n_elements = 0
            while n_elements < self.N_ELEMENT_PER_FILE:
                for j, out_q in enumerate(self.data_queue):
                    if not out_q.empty():
                        self.all_ts, self.port, self.ant, self.all_data = out_q.get()
                        self.h5file.write_singletime(self.all_ts, self.port, self.ant, self.all_data)
                        n_elements += 1
                        #self.live_h5file = hdf5LiveTimestreamData(self.live_name)
                        #self.live_h5file.init(n_times=j+1, n=j)
                        #self.live_h5file.write_singletime(self.all_ts, self.port, self.all_data)
                        #self.live_h5file.close()
            self.h5file.close()
            #self.live_h5file.close()
            self.n_file += 1
            self.h5name = self.base_dir + "{0:06d}.h5".format(self.n_file)
            self.h5file = hdf5TimestreamData(self.h5name)
            #self.live_h5file.init(n_times=1, n=0)
            #self.live_h5file.close()

class RawAcqReceiver(object):
    '''
    Interactive receiver object.  To create port threads, and get data out
    from those ports.
    Should probably fix the 'serve forever bits'
    '''
    def __init__(self, ports=[41101], host='127.0.0.1'):
        self.HOST = host
        self.PORTS = ports
        self.dataWriter = None
        self.servers = []
        self.data_queues = []


    def start(self):
        self.data_queues = []
        self.servers = []
        self.server_threads = []
        self.N_ANT = 16
        self.old_timestamp = 0
        self.n_ant_rec = 0
        self.all_data = []
        self.all_ts = []
        for port in self.PORTS:
            self.data_queues.append(Queue())
            server = RawAcqUDPServer((self.HOST, port), self.data_queues[-1])
            self.servers.append(server)
            self.server_threads.append(threading.Thread(target=server.serve_forever))
            self.server_threads[-1].setDaemon(True)
            self.server_threads[-1].start()
            print('server thread started')
            self.all_data.append(np.zeros((16, 2048), dtype=np.int8))
            self.all_ts.append(np.zeros(16, dtype=np.int32))
        self.all_data = np.array(self.all_data)
        self.all_ts = np.array(self.all_ts)

    def startHdf5Disk(self):
        self.dataWriter = dataWriter(self.data_queues)
        self.data_writer_thread = threading.Thread(target=self.dataWriter.write)
        self.data_writer_thread.setDaemon(True)
        self.data_writer_thread.start()



    def read_data(self):
        for j, out_q in enumerate(self.data_queues):
            trying_to_receive = True
            while trying_to_receive:
                self.timestamp, self.port, self.ant, self.adc_data = out_q.get()
                if (self.timestamp == self.old_timestamp) and (self.n_ant_rec < self.N_ANT - 1):
                    self.all_ts[j][self.ant] = self.timestamp
                    self.all_data[j][self.ant, :] = self.adc_data
                    self.n_ant_rec += 1
                elif (self.timestamp == self.old_timestamp) and (self.n_ant_rec == self.N_ANT - 1):
                    self.all_ts[j][self.ant] = self.timestamp
                    self.all_data[j][self.ant, :] = self.adc_data
                    self.n_ant_rec = 0
                    self.old_timestamp = 0
                    trying_to_receive = False
                elif (self.timestamp != self.old_timestamp) and (self.n_ant_rec < self.N_ANT):
                    # Start over, would be new set start as well.
                    #print "didn't get full set, only received {0} ant. restarting.".format(self.n_ant_rec)
                    self.old_timestamp = self.timestamp
                    self.all_ts[j][self.ant] = self.timestamp
                    self.all_data[j][self.ant, :] = self.adc_data
                    self.n_ant_rec = 1
        #SHould use the returned port.  cheating here.
        return self.all_ts, self.PORTS, self.all_data

    def stop(self):
        while self.servers:
            server = self.servers.pop()
            server.shutdown()
            server.server_close()
            server.socket.close()  # free the socket so we can restart the server later
            print("shutdown servers")
        while self.data_queues:
            data_queue = self.data_queues.pop()
            if not data_queue.empty():
                data_queue.queue.clear()
        if self.dataWriter:
            self.dataWriter.run = False
            self.dataWriter = None
        print("done shutting down")

    def is_running(self):
        return bool(self.servers)

class RawAcqAsyncRESTClient(AsyncRESTClient):
    """Implements a RawAcq REST client using a Tornado AsyncHTTPClient .

    All methods are Tornado coroutines so that operations can be performed concurrently on multiple nodes.
    The client will operate only if the IOloop is running.
    """
    def __init__(self, name='RawAcq', host='localhost', port=80, **kwargs):

        super(RawAcqAsyncRESTClient, self).__init__(host=host, port=port)
        self.name = name
        self.config = kwargs

    @coroutine
    def ping(self):
        try:
            yield self.get('status')
            self.log.info("Successfully pinged raw_acq server at %s:%i" % (self.host, self.port))
        except Exception as e:
            self.log.debug(repr(e))
            self.log.error("Can't ping raw_acq server at %s:%i" % (self.host, self.port))

    @coroutine
    def start(self, **config):
        print('starting with config=', config)
        result = yield self.post('start', **config)
        coroutine_return(result)

    @coroutine
    def stop(self):
        try:
            result = yield self.get('stop')
        except Exception as e:
            result = dict(error=repr(e))
        print('result=', result)
        coroutine_return(result)

class RawAcqAsyncRESTServer(AsyncRESTServer):

    DEFAULT_PORT = 33221

    def __init__(self, port=DEFAULT_PORT):
        self.receiver = RawAcqReceiver()
        super(RawAcqAsyncRESTServer, self).__init__(port=port)

    @coroutine
    def shutdown(self):
        self.receiver.stop()

    @coroutine
    @endpoint
    def start(self, handler, **config):
        print('Received start command with', config)
        if self.receiver.is_running():
            raise RuntimeError('Server is already started')
        self.receiver.start()
        coroutine_return("started receiver")

    @coroutine
    @endpoint
    def start_hdf5(self, handler):
        self.receiver.startHdf5Disk()
        coroutine_return("started hdf5 writing to disk.")

    @coroutine
    @endpoint
    def stop(self, handler):
        self.receiver.stop()
        coroutine_return("stopped receiver")

    @coroutine
    @endpoint
    def get_packets(self, handler):
        ts, ports, data = self.receiver.read_data()
        print(ts)
        print(ports)
        print(data)
        coroutine_return(ts=ts.tolist(), ports=ports, data=data.tolist())

def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="Raw_acq: ADC Raw data acquisition server", epilog="""
        """)
    parser.add_argument('args', type=str, choices=['client', 'server'], default='',  help='"server" or "client" ')
    parser.add_argument('-p', '--port', default=33221, type=int, help="Server port")
    parser.add_argument('-n', '--host', default='localhost', type=str, help="Server hostname")
    return parser.parse_args(argv)

if __name__ == '__main__':
    #
    # Run Python-based raw_acq server, for testing.
    #
    ioloop = IOLoop()
    ioloop.make_current()
    args = parse_cmdline_args(sys.argv[1:])
    print(args)
    first_arg = args.args.lower()
    if first_arg == 'server':
        rs = RawAcqAsyncRESTServer(port=args.port)
        print("Raw Acq REST Server started. Waiting for REST commands.")
        ioloop.start()
        print("\nI'm done. Bye!")
    elif first_arg == 'client':
        rc = RawAcqAsyncRESTClient(name='UserRawAcqClient0', host=args.host, port=args.port)
        print('Use rc.run_sync(method_name, args...) to call and run a client method in a ioloop')
