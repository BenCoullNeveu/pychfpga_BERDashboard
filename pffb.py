import numpy
import math

def pfb_fir(x):
    N = len(x)    # x is the incoming data time stream.
    taps = 4
    L = 512   # Points in subsequent FFT.
    bin_width_scale = 1.0
    dx = math.pi/L
    X = numpy.array([n*dx-taps*math.pi/2 for n in range(taps*L)])
    coeff = numpy.sinc(bin_width_scale*X/math.pi)*numpy.hanning(taps*L)

    y = numpy.array([0+0j]*(N-taps*L))
    for n in range((taps-1)*L, N):
        m = n%L
        coeff_sub = coeff[L*taps-m::-L]
        y[n-taps*L] = (x[n-(taps-1)*L:n+L:L]*coeff_sub).sum()

    return y
