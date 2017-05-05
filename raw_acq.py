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


#Should be in gain.py or something.
class GainCalc(object):
    def __init__(self, gain=None, zero=False):
        self.zero = zero
        self.mask = None
        self.idealRMS = 1.5 * np.sqrt(2)
        self.default_log2_gain = 22
        if gain:
            self.g = np.zeros((16,1024))
            for i in range(16):
                inb = np.array(gain[i][1][0])*2**(gain[i][1][1])
                self.g[i,:] = inb
        else:
           self.g = None

    def update(self, signal):
        self.signal = np.array(signal)
        mask = np.ma.make_mask_none((len(signal),))
        #The first bin is always bad for some reason
        mask[0] = True
        self.masked = np.ma.array(np.log(signal), mask=mask)

    def convert_gain_format(self):
        '''
        Expects array in. returns (glin, glog)
        '''
        #2**14 is max for linear gain
        #ignore dc component
        #check for nans
        #print g
        bad_values = (self.g > 2**31) | ~np.isfinite(self.g)
        g = np.ma.array(self.g,mask=bad_values)
        glog = (np.ceil(np.log2(np.ma.median(np.abs(g)/2**13,axis=1)))).astype(np.int)
        glin = np.zeros(g.shape, dtype=np.float)
        for i, glog_single in enumerate(glog):
            glin[i] = g[i]/2**glog[i]
        glog.data[glog.mask == True] = np.ma.median(glog)
        glog.mask[glog.mask] = False
        glin[bad_values] = 2**14
        return glin, glog.data

    def noisy_gain_estimate(self, data ):
        outrms = data[:,:,:].std(axis=0)
        outrms[outrms < 0.8] = 0.8
        #rmss.append(outrms.mean())
        print outrms.mean(axis=1)
        if self.g is not None:
            #not sure about format of previous gain yet...
            #needs to be a post of current gain setting I think...
            #glin, glog = self.convert_gain_format(previous_gain):
            glin, glog = self.convert_gain_format()
            # Not sure what g should be here.
            #g = self.idealRMS*2**(self.default_log2_gain)/outrms
            for j, glog1 in enumerate(glog):
                self.g[j] = self.idealRMS * glin[j] * (2**(glog[j]))/outrms[j] #idealRMS*glin*(2**(glog-4))/outrms
                self.g[j] = (20.0 * self.g[j] + 80.0 * glin[j] * (2**(glog[j])))/100.0
        else:
            #Assumes was set to something simple (glin=1), glog is something.
            self.g = self.idealRMS*2**(self.default_log2_gain)/outrms#idealRMS*2**(default_log2_gain-4)/outrms
        self.glin, self.glog = self.convert_gain_format()
        print self.glog
        bad_gains = self.glin > 2**14
        self.glin[bad_gains] = 2**14
        self.glin = self.glin.astype(np.int).astype(np.float)
        gain = []
        for channel in range(16):
            gain.append([channel,[self.glin[channel].tolist(), self.glog[channel]]])
        return gain

    def fourier_filter(self, signal, num_components):
        '''
        Filters signal with top-hat in fourier space.  Padded with itself on either     side to improve edge behavior.
        Should extend to other windows.
        not assured to maintain signal size
        '''
        signal = np.array(signal)
        signal_length = signal.size
        f_signal = np.fft.fft(np.r_[signal[signal_length/2:0:-1],signal,signal[-1:-signal_length/2:-1]])
        f_signal[num_components:-num_components] = 0
        filtered = np.fft.ifft(f_signal)[signal_length/2:-signal_length/2+1]
        filtered = (filtered.real).astype(np.int).astype(np.float)
        return filtered

    def flag_rfi(self, in_arr, fit, threshold):
        '''
        Identifies RFI in the signal spectrum by finding larger than expected jumps in the signal.
        Returns array of flags for each bin
        '''
        rfmask = abs(in_arr) < abs(fit/threshold)
        in_arr.mask = rfmask|in_arr.mask

    def poly_filter(self, signal, threshold, degree):
        '''
        Filters signal using a polynomial fit. Ignores RFI in calculating the polynomial.
        '''
        x = np.ma.array(np.arange(len(signal)), mask=signal.mask)
        fit = np.polyfit(np.ma.compressed(x), np.ma.compressed(signal), degree)
        #fit = np.polyfit(flagged, x, degree)
        fitarr = np.poly1d(fit)(np.arange(len(signal)))
        self.flag_rfi(signal, fitarr, threshold)
        return fitarr

    def iterative_poly_filter(self, signal):
        mask = np.ma.make_mask_none((len(signal),))
        #The first bin is always bad for some reason
        mask[0] = True
        degree = 1
        threshold = 1.2
        masked = np.ma.array(np.log(signal), mask=mask)
        while threshold > 1.01:
            fitarr = self.poly_filter(masked, threshold, degree)
            threshold = 1 + (threshold - 1)*0.8
            if degree < 15:
                degree += 2
        filtered = np.exp(fitarr)
        filtered = (filtered.real).astype(np.int).astype(np.float)
        return filtered, masked.mask

    def run(self, filtertype='hybrid', num_components = 50):
        if filtertype == 'fourier':
            output = self.fourier_filter(self.signal, num_components)
        elif filtertype == 'poly' or filtertype == 'hybrid':
            output, mask = self.iterative_poly_filter(self.signal)
            self.mask = mask
            if filtertype == 'hybrid':
                in_arr = self.signal.copy()
                in_arr[mask] = output[mask]
                output = self.fourier_filter(in_arr, num_components)
            if self.zero:
                output[mask] = 0
            else:
                output[mask] = self.signal[mask]
        else:
            raise ValueError
        output = (output.real).astype(np.int).astype(np.float)
        return output

class GainEstimator(object):

    def __init__(self, read_data_func, number_of_ports, number_of_frames=2):
        self.previousGain = None
        self.read_data_func = read_data_func  # function to call to get packets
        self.number_of_ports = number_of_ports
        self.number_of_frames = number_of_frames

    def estimateGains(self):
        ''' Assume setup to send spectrum data.  average a number of
            frames together, and get estimate of new gain settings.'''
        # gain_estimates = []
        frame_number = 0
        spectrum = np.zeros(self.number_of_ports, self.number_of_frames, 16, 1024), dtype=np.complex)  # port (board), timestanp, channel, bin
        while frame_number < self.number_of_frames:
            timestamps, ports, all_data = self.read_data_func()
            data_unpacked = (np.array(all_data).astype(np.int8) ^ np.int8(128)) >> 4
            spectrum[:,frame_number,:,:] = data_unpacked[:,:,::2] + 1.0j*data_unpacked[:,:,1::2]
            frame_number += 1

        for i, port in enumerate(ports):
            if self.previousGain:
                gain_calc = GainCalc(self.previousGain[i])
                first_run = False
            else:
                gain_calc = GainCalc()
                self.previousGain = []
                first_run = True
            gain = gain_calc.noisy_gain_estimate(spectrum[i])
            for j in range(16):
                gain_calc.update(gain[j][1][0])
                glin_update = gain_calc.run()
                gain[j][1][0] = glin_update.tolist()
            if first_run:
                self.previousGain.append(gain)
            else:
                self.previousGain[i] = gain
        return self.previousGain



class RawAcqUDPReceiver(SocketServer.ThreadingUDPServer):
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
            print( "{0} {1} {2}".format(port, chan, adc_data.std()) )
            self.server.data_queue.put((timestamp, port, chan, adc_data))

    def __init__(self, server_address, data_queue):
        self.data_queue = data_queue
        SocketServer.UDPServer.__init__(self, server_address, self.UDPHandler)  # cannot use super(...): this is an old-style class

class hdf5TimestreamData(object):
    def __init__(self, filestring):
        self.N_SAMP = 2048
        #self.N_ANT = 1
        self.f = h5py.File(filestring, 'w')
        self.f.attrs["file_name"] = filestring
        self.f.attrs["data_type"] = "ADC snapshot data"
        self.f.attrs["version"] = 0.1
        self.f.attrs["timestamping_warning"] = "Done on file write, may be significantly different from snapshot acquistion time"
        self.compound_dtype = np.dtype([('fpga_count', np.uint64), ('ctime', np.float64)])
        self.timestampDataset = self.f.create_dataset('timestamp',
                    (1, 1), dtype=self.compound_dtype, maxshape=(None, 1))
        self.timestampDataset.attrs['axis'] = ['snapshot', 'time']
        self.slotDataset = self.f.create_dataset('slot', (1, 1),
                                            dtype=np.uint8, maxshape=(None, 1))
        self.slotDataset.attrs['axis'] = ['snapshot', 'slot_number']
        self.crateDataset = self.f.create_dataset('crate', (1, 1),
                                            dtype=np.uint32, maxshape=(None, 1))
        self.crateDataset.attrs['axis'] = [ 'snapshot', 'crate_number']
        self.antDataset = self.f.create_dataset('adc_input', (1, 1),
                                            dtype=np.uint8, maxshape=(None, 1))
        self.antDataset.attrs['axis'] = ['snapshot', 'adc_input_number']
        self.timestreamDataset = self.f.create_dataset('timestream',
                        (1, self.N_SAMP), dtype=np.int8,
                        maxshape=(None, self.N_SAMP))
        self.timestreamDataset.attrs['axis'] = ['snapshot', 'timestream_data']
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
        current_time = time.time()
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
        self.gain_estimator = None


    def start(self):
        """ Start the raw data receivers.

        For each IP port we monitor, create a data queue and atart a multithreaded UDP receiver that
        will write data to the queue.
        """
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
            server = RawAcqUDPReceiver((self.HOST, port), self.data_queues[-1])
            self.servers.append(server)
            self.server_threads.append(threading.Thread(target=server.serve_forever))
            self.server_threads[-1].setDaemon(True)
            self.server_threads[-1].start()
            print('server thread started')
            self.all_data.append(np.zeros((16, 2048), dtype=np.int8))  # pre-allocate data (channels x bins) for this port,  for a single timestamp
            self.all_ts.append(np.zeros(16, dtype=np.int32)) # pre-allocate timestamps storage for the current data on this port (should all be the same)
        self.all_data = np.array(self.all_data)
        self.all_ts = np.array(self.all_ts)
        self.gain_estimator = GainEstimator(self.read_data, len(self.PORTS))

    def startHdf5Disk(self):
        self.dataWriter = dataWriter(self.data_queues)
        self.data_writer_thread = threading.Thread(target=self.dataWriter.write)
        self.data_writer_thread.setDaemon(True)
        self.data_writer_thread.start()




    def read_data(self):
        """
        """
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
        self.gain_estimator = None
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

    @coroutine
    def estimate_gains(self):
        coroutine_return(yield self.post('estimate_gains'))   # estimate-gains?

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

    @coroutine
    @endpoint
    def estimate_gains(self, handler):
        if self.gain_estimator:
            gains = self.gain_estimator.estimateGains()
            coroutine_return(gains=gains)
        else:
            raise RuntimeError('Gain estimator is not created (most probably because the server is not started)')

def parse_cmdline_args(argv):
    parser = argparse.ArgumentParser(description="Raw_acq: ADC Raw data acquisition server", epilog="""
        """)
    parser.add_argument('args', type=str, choices=['client', 'server'], default='',  help='"server" or "client" ')
    parser.add_argument('-p', '--port', default=33221, type=int, help="Server port")
    parser.add_argument('-n', '--host', default='localhost', type=str, help="Server hostname")
    return parser.parse_args(argv)

if __name__ == '__main__':
    """
    Command-line interface to the raw_acq engine.
        raw_acq server --port 33221 # starts the server on localhost.
        raw_acq client --port 33221 --host localhost # starts a client in variable 'rc'

    Default port is 33221 if not specified.
    """
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
        print('Use rc.run_sync(method_name, args...) to call and run asynchronous (coroutine) client methods in a ioloop. Alternativeny, one can use rc.sync_method_name(args, ...).')
