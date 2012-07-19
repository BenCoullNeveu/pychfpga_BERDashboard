import numpy as np
import math

def pfb_fir(x):
    N = len(x)    # x is the incoming data time stream.
    taps = 4
    L = 1024   # Points in subsequent FFT.
    bin_width_scale = 1.0
    dx = math.pi/L
    X = np.array([n*dx-taps*math.pi/2 for n in range(taps*L)])
    coeff = np.sinc(bin_width_scale*X/math.pi)*np.hanning(taps*L)

    y = np.array([0+0j]*(N-taps*L))
    for n in range((taps-1)*L, N):
        m = n%L
        #print m
        coeff_sub = coeff[L*taps-m::-L]
        #print coeff_sub
        y[n-taps*L] = (x[n-(taps-1)*L:n+L:L]*coeff_sub).sum()

    return y

def pffb(x):
    N=len(x) #length of data stream
    taps=4 #number of fir taps
    L=1024 #points in fft
    coeff_length = np.pi*taps
    coeff_num_samples = taps*L
    X = np.arange(-coeff_length/2.0,coeff_length/2.0, coeff_length/coeff_num_samples) #sampling locations of sinc function
    #np.sinc function is sin(pi*x)/pi*x, not sin(x)/x, so use X/pi
    coeff = np.sinc(X/np.pi)
    slice_length = taps*L
    shift_size = L
    count = 0
    out_arr = []
    while (slice_length+count*shift_size <= N):
        weighted_x = x[count*shift_size:count*shift_size+slice_length]*coeff
        print slice_length+count*shift_size
        out = weighted_x[:L]
        for n in range(1,taps):
            out += weighted_x[n*L:(n+1)*L]
        out_arr.append(out)
        count += 1
        print count
    y = np.array(out_arr).flatten()
    return y