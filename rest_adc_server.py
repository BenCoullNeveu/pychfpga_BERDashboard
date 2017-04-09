#from tornado import httpserver
from tornado import gen
from tornado.ioloop import IOLoop
import tornado.web
'''
Raw timestream receiver and hdf5 writer.
Define array of 'ports' assumed to have last 2 digits be the slot number,
third digit the crate, 
and the current host ip to listen to.  Will then listen for and write from all
boards into hdf5 file.  
'''

from Queue import Queue
import SocketServer
import threading
# import logging
# import os
import struct
import numpy as np
import h5py
import time
import datetime
import os



class TimestreamUdpHandler(SocketServer.BaseRequestHandler):
    '''
    Runs the basic receiver part.  Puts data in Queue to be parsed
    and written to hdf5 file.
    '''
    # def __init__(self, request, client_address, server):
    #     #self.logger = logging.getLogger('TimestreamUdpHandler')
    #     #self.logger.debug('__init__')
    #     SocketServer.BaseRequestHandler.__init__(self, request,
    #                                                client_address, server)
    def handle(self):
        self.data = self.request[0] # .strip()
        self.socket = self.request[1]
        self.port = self.server.server_address[1]
        (probe_id, stream_id, word_length,
            self.timestamp) = struct.unpack_from('>BHHL', self.data)
        self.ant_channel = probe_id & 0x0F
        self.adc_data = np.fromstring(self.data[9:2057], dtype=np.int8)
        #if (self.adc_data.shape[0] != 2048):
        #    print "bad data?"
        #    print self.adc_data
        #    print '#######################'
        #    print len(self.data)
        #    print '#######################'
        #    print len(self.request[0])
        self.server.data_queue.put((self.timestamp, self.port,
                                    self.ant_channel, self.adc_data))


class ThreadedUdpServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
    def __init__(self, server_address, handler_class, data_queue):
        self.data_queue = data_queue
        SocketServer.UDPServer.__init__(self, server_address, handler_class)


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
            self.n_times = self.n+1
            self.timestampDataset.resize((self.n_times, 1))
            self.slotDataset.resize((self.n_times, 1))
            self.crateDataset.resize((self.n_times, 1))
            self.antDataset.resize((self.n_times, 1))
            self.timestreamDataset.resize((self.n_times, self.N_SAMP))
        elif self.n < self.n_times:
            pass
        else:
            print "ut oh..."
        print self.n_times
        self.timestampDataset[self.n] = timestamp
        self.antDataset[self.n] = ant
        self.slotDataset[self.n] = port % 100  # assume port gives slot
        self.crateDataset[self.n] = ((port/100) % 10) - 1
        self.timestreamDataset[self.n] = timestream
        self.n += 1

    def close(self):
        self.f.close()

class hdf5LiveTimestreamData(object):
    def __init__(self, filestring):
        self.N_SAMP = 2048
        self.N_ANT = 16
        self.f = h5py.File(filestring, 'a')
        self.timestampDataset = self.f.require_dataset('timestamp',
                  (16, self.N_ANT), dtype=np.int32, maxshape=(None, self.N_ANT))
        self.portDataset = self.f.require_dataset('slot', (16, 1),
                                            dtype=np.int32, maxshape=(None, 1))
        self.timestreamDataset = self.f.require_dataset('timestream',
                        (16, self.N_ANT, self.N_SAMP), dtype=np.int8,
                        maxshape=(None, self.N_ANT, self.N_SAMP))


    def init(self, n_times, n):
        self.n_times = n_times
        self.n = n
    

    def write_singletime(self, timestamp, port, timestream):
        if self.n == self.n_times:
            self.n_times = self.n+1
            #self.timestampDataset.resize((self.n_times, self.N_ANT))
            #self.portDataset.resize((self.n_times, 1))
            #self.timestreamDataset.resize((self.n_times, self.N_ANT, self.N_SAMP))
        elif self.n < self.n_times:
            pass
        else:
            print "ut oh..."
        print self.n_times
        self.timestampDataset[self.n] = timestamp
        self.portDataset[self.n] = port % 100  # assume port gives slot
        self.timestreamDataset[self.n] = timestream
        self.n += 1 

    def close(self):
        self.f.close()



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
            print "couldn't make directory... using current one."
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

class Receiver(object):
    '''
    Interactive receiver object.  To create port threads, and get data out
    from those ports.  
    Should probably fix the 'serve forever bits'
    '''
    def __init__(self, ports=[41101], host='10.10.10.25'):
        self.HOST = host
        self.PORTS = ports
        self.dataWriter = None


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
            self.servers.append(ThreadedUdpServer((self.HOST, port), TimestreamUdpHandler, self.data_queues[-1]))
            self.server_threads.append(threading.Thread(target=self.servers[-1].serve_forever))
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
        for i, port in enumerate(self.PORTS):
            self.servers[i].shutdown()
            self.servers[i].server_close()
            print("shutdown servers")
            if not self.data_queues[i].empty():
                self.data_queues[i].queue.clear()
        if self.dataWriter:
            self.dataWriter.run = False
        print("done shutting down")

class StartHandler(tornado.web.RequestHandler):
    def initialize(self, rec):
        self.rec = rec

    def get(self):
        self.rec.start()
        self.write("started receiver")

class StartHdf5Handler(tornado.web.RequestHandler):
    def initialize(self, rec):
        self.rec = rec

    def get(self):
        self.rec.startHdf5Disk()
        self.write("started hdf5 writing to disk.")

class StopHandler(tornado.web.RequestHandler):
    def initialize(self, rec):
        self.rec = rec

    def get(self):
        self.rec.stop()
        self.write("stopped receiver")

class PacketHandler(tornado.web.RequestHandler):
    def initialize(self, rec):
        self.rec = rec

    def get(self):
        ts, ports, data = self.rec.read_data()
        print(ts)
        print(ports)
        print(data)
        self.write(dict(ts=ts.tolist(), ports=ports, data=data.tolist()))

class Application(tornado.web.Application):
    def __init__(self, rec):
        handlers = [
            (r"/start/?", StartHandler, dict(rec=rec)),
            (r"/start_hdf5/?", StartHdf5Handler, dict(rec=rec)),
            (r"/stop/?", StopHandler, dict(rec=rec)),
            (r"/get_packets/?", PacketHandler, dict(rec=rec))
        ]
        tornado.web.Application.__init__(self, handlers)

def main():
    rec = Receiver()
    app = Application(rec)
    app.listen(33221)
    print("starting up!, tell me to do something!")
    IOLoop.instance().start()

if __name__ == '__main__':
    main()
