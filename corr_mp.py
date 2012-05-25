import numpy as np
from multiprocessing import Process, Queue

def gauss_window(data,sigma):
    npoints = data.size
    x = arange(npoints)
    return data*exp(-0.5*((x-(npoints-1)/2.0)/(sigma*(npoints-1)/2.0))**2)

def hann_window(data):
    npoints = data.size
    x = arange(npoints)
    return data*0.5*(1-cos(2*pi*x/(npoints-1)))

def sim_data(qdata, sigma=12, dataLength=1024, nchan = 4):
    qdata.put( (sigma*np.random.randn(nchan,dataLength)).round().astype(int8) )

def fourier_transform(qfdata, data):
    out = np.fft.fft(data)[:,:data.shape[1]/2]
    qfdata.put(out)

def corr(nchan, fdata, accumulator):
    for j in np.arange(nchan):
        for k in np.arange(j,nchan):
            accumulator = fdata[j]*fdata[k].conjugate() + accumulator
    return accumulator
    
if __name__ == "__main__":
    #import sys
    import pp
    intLoops = 10048 #sys.argv[1]
    nchan = 4
    length = 1024
    accumulator = zeros(((nchan*(nchan+1))/2,length/2))
    qdata = Queue()
    qfdata = Queue()
    pdata = Process(target=sim_data, args=(qdata, 12, length, nchan))
    pdata.start()
    pfdata = Process(target=fourier_transform, args=( qfdata, qdata.get() )  )
    pfdata.start()
    #pacc = Process(target=corr, args=(nchan, qfdata.get(), accumulator )
    accumulator = corr(nchan, qfdata.get(), accumulator)
    for i in np.arange(intLoops-1):
        pdata.run()
        #print qdata.get()
        pfdata.run()
        #print qfdata.get()
        #data = sim_data(dataLength=length, nchan=nchan)
        #fdata = fourier_transform(data)
        accumulator = corr(nchan, qfdata.get(), accumulator)
        #pdata.join()
        #pfdata.join()
    accumulator = accumulator/intLoops

