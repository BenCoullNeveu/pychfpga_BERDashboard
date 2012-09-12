import numpy as np

import pylab

def pfb_fir(x, taps=4, L=512):
    '''
    PFB copyied directly from web.  
    '''
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

def sinc_window(taps, L):
    coeff_length = np.pi*taps
    coeff_num_samples = taps*L
    X = np.arange(-coeff_length/2.0,coeff_length/2.0, coeff_length/coeff_num_samples) #sampling locations of sinc function
    #np.sinc function is sin(pi*x)/pi*x, not sin(x)/x, so use X/pi
    coeff = np.sinc(X/np.pi)
    return coeff
    
def hanning_window(taps,L):
    return(np.hanning(taps*L))
    
def sinc_hanning_window(taps,L):
    return(sinc_window(taps,L)*hanning_window(taps,L))

def kaiser_window(taps,L):
    return(np.kaiser(taps*L, np.pi*3))

def sinc_kaiser_window(taps,L):
    return(sinc_window(taps,L)*kaiser_window(taps,L))
    
def boxcar(taps,L):
    return(np.ones(taps*L))
    
def pffb(x, taps=4, L=2048, window_function=sinc_kaiser_window):
    '''
    Polyphase filter bank FFT with hanning/sinc window rewritten to be more 
    clear.  Takes arbitrary length of timestream data and ouputs complex 
    spectra y of length L.  Taps is the number of taps for the poly-phase filter.
    '''
    N=len(x) #length of data stream
    #taps = number of fir taps
    #L = points in fft
    coeff = window_function(taps, L)    
    #*np.hanning(taps*L)
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


###Finish to simulate fft of same bin
def sim_pfb(taps=4, L = 2048, window_function=sinc_hanning_window, bin_number=30, resolution=2**20):
    x=np.sin(np.arange(taps*L)*np.pi*2.0*bin_number*1.0/L)
    y, coeff =  pffb(x, taps, L, window_function)
    #fy = np.fft.fft(y[:L])
    #fy2 = np.fft.fft(y[L:2*L])
    #fyo = np.fft.fft(x[:L*taps])
    lz = np.zeros(resolution)
    if window_function == boxcar:
        lz[lz.size/2:lz.size/2+L] = 1.0*x[:L]
    else:
        lz[lz.size/2:lz.size/2+taps*L] = coeff*x
    coeff_ft = np.fft.fft(lz)
    #lz2 = np.zeros(resolution)
    #lz2[lz2.size/2:lz2.size/2+L] = 1*x[:L]
    #flat_ft = np.fft.fft(lz2)
    xs = np.arange(lz.size)*L*1.0/lz.size
    return xs, coeff_ft

if __name__ == '__main__':
    taps = 4
    L = 2048
    bin_numbers = [1,6,7]
    for bin_number in bin_numbers:
        x=np.sin(np.arange(8192)*np.pi*2.0*bin_number/2048.0)
        y, coeff =  pffb(x, taps, L)
        fy = np.fft.fft(y[:L])
        #fy2 = np.fft.fft(y[L:2*L])
        fyo = np.fft.fft(x[:L*taps])
        #pylab.plot(abs(fyo[:fyo.size/2]))
        #pylab.plot(4*np.arange(L/2),abs(fy[:L/2]))
        #pylab.plot(4*np.arange(L/2),abs(fy2[:L/2]))
        lz = np.zeros(2**20)
        lz[lz.size/2:lz.size/2+4*2048] = coeff*x
        coeff_ft = np.fft.fft(lz)
        lz2 = np.zeros(2**20)
        lz2[lz2.size/2:lz2.size/2+2048] = 1*x[:2048]
        flat_ft = np.fft.fft(lz2)
        #pylab.plot(np.arange(65536)/(1.0*L),10*np.log10(abs(flat_ft)))
        #pylab.plot(np.arange(65536)/(1.0*L),10*np.log10(abs(coeff_ft)))
        pylab.plot(np.arange(lz2.size)*2048.0/lz2.size, 20*np.log10(np.abs(coeff_ft)/np.abs(coeff_ft).max()))
        pylab.plot(np.arange(lz2.size)*2048.0/lz2.size, 20*np.log10(np.abs(flat_ft)/np.abs(flat_ft).max()))
    pylab.xlim(0,8)
    pylab.ylim(-120,0)
    pylab.savefig('pffb_comp_flat_vs_pfb_sinc_kaiser_window_bins1_6_7.pdf')
    pylab.show()