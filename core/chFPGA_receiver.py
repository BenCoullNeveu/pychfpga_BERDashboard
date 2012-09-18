#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
chFPGA_reader.py module 
 Implements the classes that read the data streams coming from chFPGA.

 History:
    2012-07-19 JFC: Created
"""


import Queue
import threading
import struct
import time

import numpy as np

import SocketIO



class ReceiverThread(threading.Thread):        
    BUF_SIZE=32768
    data = bytearray(BUF_SIZE)
    data_buf = buffer(data)
    data_block = np.zeros((8,2048+9), dtype=np.uint8)
    #Number of frequency bin pairs, Number of antennas, Number of bytes per word, header
    corr_data_length = 128*4*13+11 #in bytes
    corr_data_block = np.zeros((5,corr_data_length), dtype=np.int8)
#        frame_block = {'timestamp' :0, 'data':frame_data}        
    queue_overflow = 0
    queue_corr_overflow = 0
    n_frames = 0
    
    def __init__(self, sock, queue, queue_corr, verbose = 1):
        self.sock = sock
        self.queue = queue
        self.queue_corr = queue_corr
        self._stop = threading.Event()
        self._flush = threading.Event()
        self.verbose = verbose
        self.print_delay = 1
        self._send_every_frame = threading.Event()
        super(type(self), self).__init__()
    
    def stop(self):
        self._stop.set()

    ###Currently the flush is unused...  Remove?
    def flush(self,state):
        if state:
            self._flush.set()
        else:
            self._flush.clear()

    def send_every_frame(self,state):
        if state:
            self._send_every_frame.set()
        else:
            self._send_every_frame.clear()
            
    def is_stopped(self):
        return self._stop.is_set()

    def run(self):
    #    timeout=1
    #    frame_array=[]
        last_timestamp = 0
    #    last_delta = 0
        n = 0
        n_corr = 0
        #t0 = time.time()
        #last_display_time = t0
#            expected_delta=self.ANT[0].PROBER.get_burst_period()
#            missing_frames = 0
#            bad_delta = 0
    #    data2 = bytearray(buf_size)        
        self.sock.settimeout(0.1)
        print 'Frame acquisition thread is running'
        while not self._stop.is_set():
            #data = self.sock.read_data(timeout_delay=timeout)
            # Read data from the UDP listening port
            if self._flush.is_set():
                try:
                    nbytes = self.sock.recv_into(self.data)
                except SocketIO.timeout:
                    pass
            else:
                try:
                    nbytes = self.sock.recv_into(self.data)
                except SocketIO.timeout:
                    nbytes = 0
                if nbytes:
                    #print 'Received a frame!!!'
                    self.n_frames += 1

                    #probe_id = struct.unpack_from('>B', self.data_buf)
                    (probe_id, stream_id, word_length, timestamp) = struct.unpack_from('>BHHL', self.data_buf)
                    #Correlator input                    
                    if (probe_id == 0xFB):
                        #Correlator unpack first try very simple.  
                        if (stream_id < 5 ) :
                            if (stream_id == 4):
                                self.corr_data_block[stream_id,:] = self.data[:self.corr_data_length]
                                try:
                                    self.queue_corr.put_nowait(self.corr_data_block.copy())
                                except Queue.Full:
                                    self.queue_corr_overflow += 1
                            else:
                                self.corr_data_block[stream_id,:] = self.data[:self.corr_data_length]
                        else:
                            print "BAD STREAM ID?"
                            #Clear stuff? ERROR HANDLE
                    
                    else:
                        #Spectrum/timestream unpack (maybe break this up as well?)    
                        if self._send_every_frame.is_set():
                            self.data_block[0,:] = self.data[:2048+9]
                            try:
                                self.queue.put_nowait((timestamp, self.data_block[0:1,:].copy()))
                                #print 'Stored a frame!!!'
                            except Queue.Full:
                                self.queue_overflow += 1
                        else:
                            if (timestamp != last_timestamp):
                                #print 'trying to store a frame!!!'
                                if n:
                                    try:
                                        #print 'Storing a frame!!!'
                                        self.queue.put_nowait((timestamp, self.data_block[0:n,:].copy()))
                                    except Queue.Full:
                                        self.queue_overflow += 1
                                last_timestamp = timestamp
                                n = 0
                            # Copy the new vector into the block memory buffer
                            self.data_block[n,:] = self.data[:2048+9]                    
                            n += 1
        print 'Frame acquisition thread is stopped'

    def status(self, print_delay=1):
        last_display_time = 0
        try:
            while True:
                t = time.time()                        
                dt = t-last_display_time
                if dt > print_delay:
                    print 'Received %i frames at %f frames/s (%f Mb/s), buffer size = %i, overflows= %i' % (self.n_frames, self.n_frames/dt, self.n_frames/dt*(2048+9)*8/1e6,  self.queue.qsize(), self.queue_overflow)
                    last_display_time = t
                    self.n_frames = 0
        except KeyboardInterrupt:
            pass

class chFPGA_receiver(object):
    # define constants
    FRAME_BUFFER_LENGTH = 10
    FRAME_HEADER_LENGTH = 9
    CORR_FRAME_HEADER_LENGTH = 11
    LOG2_FRAME_LENGTH = 11
    FRAME_LENGTH = 2**LOG2_FRAME_LENGTH

    def __init__(self, ip_address='10.10.10.11', port=41001, verbose=2):

        print '*** Opening receiver sockets ***'
        # Create socket handled and open socket communications to the chFPGA board
        self.sock=SocketIO.DataSocket_base(ip_address, port)
        #self.sock.open()

        # Create a frame a queue and a thread that will fill it
        self.frame_queue = Queue.Queue(maxsize=self.FRAME_BUFFER_LENGTH)
        self.frame_queue_corr = Queue.Queue(maxsize=self.FRAME_BUFFER_LENGTH)
        #self.frame_queue = multiprocessing.Queue(maxsize=1000)
        self.frame_receiver = ReceiverThread(self.sock.sock, self.frame_queue, self.frame_queue_corr, verbose=0)
        self.frame_receiver.start()

    def __del__(self):

        self.close()
        print '__del__: Closed FPGA at IP address'# %s' % self.SocketIO.OUT_IP

    def close(self):
        """ 
        Close object, which releases the socket bindings
        """
        self.frame_receiver.stop()
        self.frame_receiver.join()
        self.sock.close()


    def flush(self):
        """ Empties the frame buffer.
        It is suggested to call this function when no data is being transmitted if the first frame to be received is generated by a specific user-controlled event (frame injection, single trigger etc.)
        """
        #self.sock.flush_data_socket() # This cause conflict with the background socket operations
        #self.frame_receiver.flush(1)
        #self.frame_receiver.flush(0)
        with self.frame_queue.mutex:
            self.frame_queue.queue.clear()

    def send_every_frame(self, state):
        """ 
        If state=True, tells the receiver Thread to put in the FIFO every data frame as it comes in.
        If state=False, the receiver will put all the data with the same timestamp in the FIFO. This means this is not done until another timestanp is received.
        """        
        self.frame_receiver.send_every_frame(state)
        
    def length(self):
        """ Returns the number of entries in the receiver FIFO """
        
        return self.frame_queue.qsize()        
            
    def read_frames(self, frames=1, verbose=0, raw=0, flush=0, timeout=3):
        """
        Get frames that were captured by the capture thread.

        Parameters:
            frames: Number of frames to acquire per channel. Limited by the buffer lengths in the FPGA
            raw: when true, returns the unsigned raw data from the ADC (bit 7 is not inverted)
        History:
            110916 JFC: Added comments. 
                Changed output format to dictionnary of arrays instead of bidimentional array.
                Now use global trigger to support multi-channel
            120713 JFC: Changed name to from read_ADC_frames to get_frames. Rewritten for new frame acquisition architecture 
        """

        # Acquire the data
        data={}
        if flush:
            self.flush_frame_buffer()
            
        for j in range(frames):
        #j=0
        #while 1:
            #j+=1
            if verbose>1 or (verbose==1 and (j % 100 ==99 or j==frames-1)):
                print 'Acquiring Frame %i (%.0f%%)' % ((j+1),(100*(j+1)/frames))
            #try:
            data_block = self.frame_queue.get(timeout=timeout)
            #except Queue.`:
            #    return None
                
            block_timestamp = data_block[0]
            in_frames =  data_block[1]
            
            data['timestamp'] = block_timestamp
            
            for in_frame in in_frames[:]:
                

                if(len(in_frame) < self.FRAME_HEADER_LENGTH):
                    print 'Bad header'
                    break
                else:    
                    (probe_id, stream_id, word_length, timestamp) = struct.unpack_from('>BHHL', in_frame)
                    channel = probe_id & 0x0F
                    flags = word_length >> 12
                    word_length &= (2**12 - 1)
                
                if(len(in_frame) != self.FRAME_LENGTH+self.FRAME_HEADER_LENGTH):
                    print 'Frame too short'
                    break
        
                # Process the frame data
    
                raw_data=in_frame[self.FRAME_HEADER_LENGTH:]
                raw_data.dtype=np.int8 # ADC output are signed values
    
                if raw:
                    raw_data.dtype=np.uint8
                    raw_data^=0x80
    
                if verbose >=2:
                    print 'Packet received from port %i. Frame header information:  probe_id #=%i, stream_id #=%i, Word length=%i words, timestamp=%i, flags=%i' % (channel, probe_id, stream_id, word_length, timestamp, flags)
                    print data
                    #pass
                # Make sure there is an empty vector on the first storage so we can concatenate to it the new data
                
                if channel not in data:
                    data[channel]=raw_data
                else:
                    data[channel]=np.hstack((data[channel],raw_data));
        return data        
            
    def read_corr_frames(self, frames=1, verbose=0, flush=0, timeout=3):
        """
        Get corr frames that were captured by the capture thread.

        ##FIX THIS
        Parameters:
            frames: Number of frames to acquire per channel. Limited by the buffer lengths in the FPGA
        History:
            120913 KMB: Created from read_frames to read corr buffer
        """

        # Acquire the data
        data={}
        #need to change flush to take a queue object
        if flush:
            self.flush_frame_buffer()
            
        for j in range(frames):
        #j=0
        #while 1:
            #j+=1
            if verbose>1 or (verbose==1 and (j % 100 ==99 or j==frames-1)):
                print 'Acquiring Frame %i (%.0f%%)' % ((j+1),(100*(j+1)/frames))
            #try:
            data_block = self.frame_queue_corr.get(timeout=timeout)
            #except Queue.`:
            #    return None
                
            in_frames =  data_block
            block_timestamp = 0
            data['timestamp'] = block_timestamp
            
            for in_frame in in_frames[:]:
                

                if(len(in_frame) < self.CORR_FRAME_HEADER_LENGTH):
                    print 'Bad header'
                    break
                else:    
                    (probe_id, mult_id, word_length, timestamp) = struct.unpack_from('>BHLL', in_frame)
                    data['mult_id'] = mult_id

                #Return numpy complex128's  Check if this shifting is correct
                #not shifting through correctly yet.
                #not sure if the word thing will work, might need indexes or something
                raw_data = []
                #in_frame[11+13*i:24+13*i] i from 0 to 512
                for word in in_frame[11:].reshape(512,13):
                    (flags, r1, r2, i1, i2) = struct.unpack_from('>BHLHL',word)
                    raw_data.append(( r1 << 32 | r2 ) + 1.0j*(i1<<32 | i2))
                raw_data = np.array(raw_data)
        
                # Process the frame data Need to use Mult_ID to sort out what is what.
                # include in data flags etc?
    
                #Format data from frame
    
                if verbose >=2:
                    print 'Frame header information:  probe_id #=%i, mult_id #=%i, Word length=%i words, timestamp=%i ' % ( probe_id, mult_id, word_length, timestamp )
                    print data
                    #pass
                # Make sure there is an empty vector on the first storage so we can concatenate to it the new data
                
                if mult_id not in data:
                    data[mult_id]=raw_data
                else:
                    data[mult_id]=np.hstack((data[mult_id],raw_data));
        return data     




