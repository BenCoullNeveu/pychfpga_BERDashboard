#!/usr/bin/python

'''
Fast python timestream receiver.  Simplified to just save timestreams fast!
'''

import struct, socket
import numpy as np

all_data = []
all_data_channels = []
timestamps = []

port = 41001

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('',port))
print "Receiving at port %d" % (port)

BUF_SIZE=65536
nframes = 2560
NUMBER_OF_CORRELATORS = 5
NUMBERS_OF_ANTENNAS_TO_CORRELATE = 5
#Nant = NUMBER_OF_ANTENNAS_TO_CORRELATE # Number of correlated antennas c.GPIO.
#Nproducts_max = (Nant*(Nant+1))/2 # Total number of correlation products
NUMBER_OF_MULTIPLIERS = NUMBERS_OF_ANTENNAS_TO_CORRELATE + 1
#MAX_NUMBER_OF_CHANNELS_PER_CORRELATOR = 128 
MAX_CORR_FRAME_LENGTH = 512*13+11 #in bytes. The accumulator size is always 512 words, each word being 13 bytes long. A 11 byte header is added. 
#corr_data_block = np.zeros((nframes, MAX_CORR_FRAME_LENGTH), dtype=np.int8)*np.nan
#        frame_block = {'timestamp' :0, 'data':frame_data}  
#RAW_DATA=2048+9
#FRAME_HEADER_LENGTH = 9
data = bytearray(BUF_SIZE)
data_buf = buffer(data)
#corr_data=np.zeros((256, Nproducts_max, FREQ_CHANNELS_MAX), dtype=complex)*np.nan
# product_numbers = np.zeros((256,Nproducts_max), dtype=np.int)
# timestamps = np.zeros((256), dtype=np.int)


Cont = True

fh = open('filename_testing', 'a+b')

while Cont:
    for frame in xrange(nframes):
        nbytes = sock.recv_into(data)
        #(probe_id, stream_id, word_length, timestamp) = struct.unpack_from('>BHHL', data_buf)
        #(corr_number, mult_number, stream_id, word_length, timestamp) = struct.unpack_from('>BHHHL', data_buf)
        #corr_data_block[frame,:nbytes] = data[:nbytes]
        fh.write(data)
    #corr_data_block.tofile(fh)
    Cont = False


