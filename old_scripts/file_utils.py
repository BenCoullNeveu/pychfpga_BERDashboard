#!/usr/bin/python

"""
file_utils.py script 
 Functions for writing to disk
#
History:
    2012-09-28 KMB: First attempt 
"""
import numpy as np
import struct, time

def write_header(datafile, est_clk, acc_len):
    ## Read gains from a file
    #f=open('gains.txt', 'r')
    gainA= np.ones(1024,dtype=np.int32)
    gainB= np.ones(1024,dtype=np.int32)
    gainC= np.ones(1024,dtype=np.int32)
    gainD= np.ones(1024,dtype=np.int32)
    #for i in range(1024):
    #    gainA[i] = int(f.readline())
    #for i in range(1024):
    #    gainB[i] = int(f.readline())
    #for i in range(1024):
    #    gainC[i] = int(f.readline())
    #for i in range(1024):
    #    gainD[i] = int(f.readline())
    #f.close()
    header_version=14  #we start at 1.2 as 1.0 was complex128, 1.1 was int32/int32 and 1.2 adds a header
    datafile.write(struct.pack('i', header_version))
    datafile.write(struct.pack('d', time.time()))
    datafile.write(struct.pack('f', est_clk))
    datafile.write(struct.pack('i', acc_len))
    datafile.write(gainA)
    datafile.write(gainB)
    datafile.write(gainC)
    datafile.write(gainD)


def convert_format(accumulator):
    #want 1024 int32 real, int32 imag
    interleave_a = np.empty([10,2048],dtype=np.int32)
    gain = 32
    acc_real = (gain*accumulator).real.astype(np.int32)
    acc_imag = (gain*accumulator).imag.astype(np.int32)
    #interleave_a[:,::2] = acc_real
    #interleave_a[:,1::2] = acc_imag
    for i in range(1024):
        interleave_a[:,i * 2]     = acc_real[:,i]
        interleave_a[:,i * 2 + 1] = acc_imag[:,i]
    #print interleave_a
    return interleave_a

    