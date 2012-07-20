import numpy as np

import pylab

def pfb_fir(x, taps=4, L=512):
    N = len(x)    # x is the incoming data time stream.
    #taps = 4
    #L = 1024   # Points in subsequent FFT.
    bin_width_scale = 1.0
    dx = np.pi/L
    X = np.array([n*dx-taps*np.pi/2 for n in range(taps*L)])
    coeff = np.sinc(bin_width_scale*X/np.pi)#*np.hanning(taps*L)

    y = np.array([0+0j]*(N-taps*L))
    for n in range((taps-1)*L, N):
        m = n%L
        #print m
        coeff_sub = coeff[L*taps-m::-L]
        #print coeff_sub
        y[n-taps*L] = (x[n-(taps-1)*L:n+L:L]*coeff_sub).sum()

    return y,coeff



def pffb(x, taps=4, L=512):
    N=len(x) #length of data stream
    #taps = number of fir taps
    #L = points in fft
    coeff_length = np.pi*taps
    coeff_num_samples = taps*L
    X = np.arange(-coeff_length/2.0,coeff_length/2.0, coeff_length/coeff_num_samples) #sampling locations of sinc function
    #np.sinc function is sin(pi*x)/pi*x, not sin(x)/x, so use X/pi
    coeff = np.sinc(X/np.pi)*np.hanning(taps*L)
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
    return y, coeff


if __name__ == '__main__':
    taps = 4
    L = 512
    x=np.sin(np.arange(8192)/78.0)
    y, coeff =  pffb(x, taps, L)
    fy = np.fft.fft(y[:L])
    fy2 = np.fft.fft(y[L:2*L])
    fyo = np.fft.fft(x[:L*taps])
    #pylab.plot(abs(fyo[:fyo.size/2]))
    #pylab.plot(4*np.arange(L/2),abs(fy[:L/2]))
    #pylab.plot(4*np.arange(L/2),abs(fy2[:L/2]))
    lz = np.zeros(2**16)
    lz[65536/2:65536/2+taps*L]=coeff
    coeff_ft = np.fft.fft(lz)
    lz2 = np.zeros(2**16)
    lz2[65536/2:65536/2+taps*L]=1
    flat_ft = np.fft.fft(lz2)
    pylab.plot(np.arange(65536)/(1.0*L),10*np.log10(abs(flat_ft)))
    pylab.plot(np.arange(65536)/(1.0*L),10*np.log10(abs(coeff_ft)))
    pylab.show()