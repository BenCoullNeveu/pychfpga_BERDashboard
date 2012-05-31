import numpy as np
import struct

ft_bins = 1024

#read header copied for greg davies code
def read_header_v140(fpath):
    """Read header version 14"""
    global fs
    global acc_len
    global hdr_len
    hdr_len = 4 * (4 + ft_bins*4) + 4
    f = open(fpath, 'r')
    f.seek(4)
    hdr_time = struct.unpack('d', f.read(8))[0]
    hdr_clkf = struct.unpack('f', f.read(4))[0]
    hdr_acclen = struct.unpack('i', f.read(4))[0]
    acc_len = hdr_acclen
    print acc_len
    #fs = 4.0 * hdr_clkf
    gainA = np.array(struct.unpack(ft_bins*'i', f.read(4*ft_bins)))
    gainB = np.array(struct.unpack(ft_bins*'i', f.read(4*ft_bins)))
    gainC = np.array(struct.unpack(ft_bins*'i', f.read(4*ft_bins)))
    gainD = np.array(struct.unpack(ft_bins*'i', f.read(4*ft_bins)))
    f.close()
    return hdr_time, gainA, gainB, gainC, gainD
	
	
def read_raw_data(fpath):
    """Read the full raw data (not including header) of a CHIME data file"""
    f = open(fpath, 'r')
    #f.seek(hdr_len, 0)
    #data = f.read()
    data = np.fromfile(file=f, dtype='i') 
    f.close()
    raw_data = data[hdr_len/4:]
    #raw_data = data
    #raw_data = numpy.array(struct.unpack(len(data)/4*'i', data))
    return raw_data

if __name__ == '__main__':
    import sys
    #fname = sys.argv[1]
    fpath = '\\Users\\chime\\workspace\\kevin\\data\\out_1338445645.75\\out1338445645.75.0000'
    hdr_time, gainA, gainB, gainC, gainD = read_header_v140(fpath)
    print hdr_len
    raw_data = read_raw_data(fpath)