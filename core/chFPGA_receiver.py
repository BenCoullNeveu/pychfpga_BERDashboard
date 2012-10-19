#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
chFPGA_reader.py module 
 Implements the classes that read the data streams coming from chFPGA.

 History:
    2012-07-19 JFC: Created
    2012-10-17 JFC: Modified behavior of receiver for:
        a) If send_every_frame=False, discard the first block of frames after flush() avoid sending partial frame blocks
        b) if the Queue is full, automatically pop an element before pushing a new one. Old data will be automatically flushed over time.
"""


import Queue
import threading
import struct
import time

import numpy as np

import SocketIO



class ReceiverThread(threading.Thread):        
    BUF_SIZE=65536
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
    store_data = 0 # do not store frame blocks if False
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
        nc=0
        total_queue_entries = 0
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
                self.store_data = 0 # do not store data
                self.queue.queue.clear();
                self.queue_corr.queue.clear();
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
                    if (probe_id & 0xF0 == 0xF0): # If correlator data
                        #Correlator unpack first try very simple. 
                        if (stream_id < 5 ) :
                            if (stream_id == 0) and (probe_id & 0x0F == 0) and (nc>0):
                                try:
                                    self.queue_corr.put_nowait(self.corr_data_block.copy())
                                except Queue.Full:
                                    self.queue_corr_overflow += 1
                                self.corr_data_block[stream_id,:] = self.data[:self.corr_data_length]
                                nc=1
                            else:
                                self.corr_data_block[stream_id,:] = self.data[:self.corr_data_length]
                                nc+=1

                        else:
                            print "BAD STREAM ID?"
                            #Clear stuff? ERROR HANDLE
                    
                    elif (probe_id & 0xF0 == 0xA0): # if timestream or spectrum data
                        # If we don't want to wait for all frames with the same timestanp to be grouped, put the frame immediately on the queue
                        if self._send_every_frame.is_set():
                            self.data_block[0,:] = self.data[:2048+9]
                            # If the queue is full, make room by poping the oldest element
                            if self.queue.full():
                                self.queue.get()
                            # Now try to write the data into the Queue. 
                            try:
                                self.queue.put_nowait((timestamp, self.data_block[0:1,:].copy()))
                                #print 'Stored a frame!!!'
                            except Queue.Full:
                                self.queue_overflow += 1
                        else: # otherwise store the data only when a new timestanp is received and the numbe of frames is not zero
                            if (timestamp != last_timestamp) and (n != 0):
                                #print 'trying to store a frame!!!'
                                if self.store_data: # False if this is the first block to be stored. In this case, do not store the data in case we got partial block after a flush()
                                # If the queue is full, make room by poping the oldest element
                                    if self.queue.full():
                                        self.queue.get()
                                    # Now write the block of frames to the queue
                                    try:
                                        #print 'Storing a frame!!!'
                                        self.queue.put_nowait((timestamp, self.data_block[0:n,:].copy()))
                                        total_queue_entries += 1                        
                                        #if not (total_queue_entries % 10):
                                            #print '.',
                                    except Queue.Full:
                                        self.queue_overflow += 1
                                        print 'Receiver Queue overflow... Should not happen...'
                                else:
                                    self.store_data = 1 # next time store the block
                                last_timestamp = timestamp
                                n = 0
                            # Copy the new vector into the block memory buffer
                            if n < 0 or n >= 8:
                                print 'Receiver: received %i Timestrem/Spectrum frames with the same timestamp.' % n   
                            elif nbytes != 2048 + 9:
                                print 'Receiver: Timestrem/Spectrum frame has %i bytes instead of 2048+9=2057 bytes. First bytes are: 0x%s' % (nbytes, ' '.join('%02X' % c for c in self.data[:32]))                              
                            else:
                                self.data_block[n, :] = self.data[: 2048 + 9]                    
                                n += 1
                    else: # unknown frame format
                        print 'Receiver: Frame of %i bytes with unknown identifier 0x%Xx has been received. It was discarded. First bytes are 0x%s' % (nbytes, (probe_id & 0xF0) >> 4, ' '.join('%02X' % c for c in self.data[:32]))                              
                        
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

    CHANNELS_PER_CORR = 204
    CHANNELS_PER_CORR_MAX = 204
    NUMBER_OF_ANTENNAS_TO_CORRELATE = 5
    NUMBER_OF_CORRELATORS = NUMBER_OF_ANTENNAS_TO_CORRELATE
    FREQ_CHANNELS = 1024
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
        self.frame_receiver.flush(1)
        while (not self.frame_queue.empty()) or (not self.frame_queue_corr.empty()):
            pass
        self.frame_receiver.flush(0)
        #with self.frame_queue.mutex:
        #    self.frame_queue.queue.clear()

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
            self.flush()
            
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
            
    def read_corr_frames(self, frames=1, verbose=0, flush=0, timeout=3, raw=False):
        """
        Get corr frames that were captured by the capture thread.

        ##FIX THIS
        Parameters:
            frames: Number of frames to acquire per channel. Limited by the buffer lengths in the FPGA
        History:
            120913 KMB: Created from read_frames to read corr buffer
        """
        Nant = self.NUMBER_OF_ANTENNAS_TO_CORRELATE # Number of correlated antennas c.GPIO.
        Nproducts = (Nant*(Nant+1))/2 # Total number of correlation products
        Nchannels_max = self.CHANNELS_PER_CORR_MAX # Maximum number of frequency channels that can be contained in a frame CHANNELS_PER_CORR_MAX*NUMBER_OF_CORRELATORS
        linear_map = lambda i, j : (Nant * (Nant + 1) - (Nant - i) * (Nant - i + 1)) / 2 + (j - i) # Maps (i,j) (for j>=i) matrix coordinates into a linear array indexed from 0 to Nant*(Nant-1)/2-1: x0x0, x0x1, x0x2, x0x3, x1x1, x1x2, x1x3, x2x2, x2x3, x3x3
        corr_data=np.zeros((Nproducts, self.FREQ_CHANNELS), dtype=complex)  # Dimensions are: (Number_of_products, number_of_frequency_channels)          

        # Acquire the data
        data={}
        #need to change flush to take a queue object
        if flush:
            self.flush()
            
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
                    #data['mult_id'] = mult_id

                #Return numpy complex128's  Check if this shifting is correct
                #not shifting through correctly yet.
                #not sure if the word thing will work, might need indexes or something
                raw_data = []
                #in_frame[11+13*i:24+13*i] i from 0 to 512
                corr_number = probe_id & 0x0F
                word_number = 0
                num_channels = len(in_frame[11:])/13
                for word in in_frame[11:].reshape(num_channels,13):
                    (flags, r1, r2, i1, i2) = struct.unpack_from('>BHLHL',word)
                    product = ((r1 << 32) | r2 ) + 1.0j * ((i1 << 32) | i2)
                    raw_data.append(product)
                    
                    product_number = word_number %  Nant
                    freq_channel = (word_number // Nant) *2 + corr_number*self.CHANNELS_PER_CORR
                    # Compute the (i,j) index of each product
                    if mult_id == 0:
                        i_index = Nant - 1 - product_number
                        j_index = Nant - 1 - product_number
                        freq_channel_offset = 1
                    elif mult_id == Nant:
                        i_index = product_number
                        j_index = product_number
                        freq_channel_offset = 0
                    elif product_number < mult_id: # if we have the 'A' peoducts
                        i_index = Nant - 1 - mult_id
                        j_index = Nant - mult_id + product_number
                        freq_channel_offset = 0
                    else:
                        i_index = mult_id - 1
                        j_index = mult_id + Nant - product_number - 1
                        freq_channel_offset = 1
                    linear_index = linear_map(i_index, j_index)       
                    #print 'Multiplier #%i, word #%i, bin #%i, product #%i, (i,j)=(%i,%i), k=%i' %( mult_id, word_number, freq_channel+freq_channel_offset, product_number, i_index, j_index, linear_index )
                    corr_data[linear_index, freq_channel+freq_channel_offset] = product
                    word_number += 1   
                raw_data = np.array(raw_data)
        
                

                    
        
                # Process the frame data Need to use Mult_ID to sort out what is what.
                # include in data flags etc?
    
                #Format data from frame
    
                if verbose >=2:
                    print 'Frame header information:  probe_id #=%i, mult_id #=%i, Word length=%i words, timestamp=%i ' % ( probe_id, mult_id, word_length, timestamp )
                    print data
                    #pass
                # Make sure there is an empty vector on the first storage so we can concatenate to it the new data
                
                if mult_id in data:
                    print 'Warning: correlator data is received multiple times from the same multiplier'
 
                data[mult_id]=raw_data

                #if mult_id not in data:
                #    data[mult_id]=raw_data
                #else:
                #    data[mult_id]=np.hstack((data[mult_id],raw_data));
        if raw:
            return data
        else:
            return corr_data




