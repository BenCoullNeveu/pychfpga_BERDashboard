import numpy as np
#from multiprocessing import Process

def gauss_window(data,sigma):
    npoints = data.size
    x = arange(npoints)
    return data*exp(-0.5*((x-(npoints-1)/2.0)/(sigma*(npoints-1)/2.0))**2)

def hann_window(data):
    npoints = data.size
    x = arange(npoints)
    return data*0.5*(1-cos(2*pi*x/(npoints-1)))

def sim_data(sigma=12, dataLength=1024, nchan = 4):
    return (sigma*np.random.randn(nchan,dataLength)).round().astype(np.int8)

def fourier_transform(data):
    out = np.fft.fft(data)[:,:data.shape[1]/2]
    return out

def corr(nchan, fdata, accumulator):
    for j in np.arange(nchan):
        for k in np.arange(j,nchan):
            accumulator = fdata[j]*fdata[k].conjugate() + accumulator
    return accumulator
    
if __name__ == "__main__":
    #import sys
    import pp, time
    intLoops = 5048 #sys.argv[1]
    nchan = 4
    length = 1024
    accumulator = np.zeros(((nchan*(nchan+1))/2,length/2))
    #pdata = 
    st = time.time()
    for i in np.arange(intLoops):
        data = sim_data(dataLength=length, nchan=nchan)
        fdata = fourier_transform(data)
        accumulator = corr(nchan, fdata, accumulator)
    accumulator = accumulator/intLoops
    et = time.time()
    print "took " + str(et - st ) + ' seconds'
