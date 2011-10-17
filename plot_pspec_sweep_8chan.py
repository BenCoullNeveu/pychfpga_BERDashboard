from numpy import *
import pylab, sys

pspecs = []
ii=1
slength = 1024
sig = 0.2
freq = fft.fftfreq(slength,1/800.0)
cut=14
nchan=8
sweepChan = 2

nfiles = len(sys.argv) - 1

def gauss_window(data,sigma):
   npoints = data.size
   x = arange(npoints)
   return data*exp(-0.5*((x-(npoints-1)/2.0)/(sigma*(npoints-1)/2.0))**2)
      
def hann_window(data):
   npoints = data.size
   x = arange(npoints)
   return data*0.5*(1-cos(2*pi*x/(npoints-1)))

for filenum in range(nfiles):
   filename = sys.argv[filenum+1]
   fd = open(filename, 'rb')
   #data = fromfile(file=fd, dtype=int8)
   data = load(filename)*0.5/256.0
   #data = data[:2097152]*0.5/256.0
   #data = data[:524288]*0.5/256.0
   nsamples = data.size/slength/nchan
   print data.size
   data = data.reshape((nsamples,nchan,slength))
   for j in arange(data.shape[0]):
      for k in arange(nchan):
         #data[j,k,:] = gauss_window(data[j,k,:], sig)
	     data[j,k,:] = hann_window(data[j,k,:])
	     #data[j,k,:] = data[j,k,:]
   fft1 = fft.fft(data)
   fft1 = fft1[:,:,:slength/2]*sqrt(2)/slength
   freq = freq[:slength/2]
   pspec = 10*log10((fft1*fft1.conjugate()).max(axis=0)/50.0)  + 30.0
   pspec[:,0] = 0
   print pspec.max()
   pspecs.append(pspec)
   fd.close()
   ii+=1
   if (filenum == 0):
      pylab.plot(freq[cut:-cut],pspec[sweepChan,cut:-cut], label=filename[:-4])
   elif (filenum ==1):
      pylab.plot((800-freq)[cut:-cut], pspec[sweepChan,cut:-cut], label=filename[:-4])
   else:
      pylab.plot((800+freq)[cut:-cut], pspec[sweepChan,cut:-cut], label=filename[:-4])

#pylab.legend(loc=4)
pylab.xlabel('freq (MHz)')
pylab.ylabel('Power (dBm)')
pylab.savefig('adc_spectrum_chan3-5dbm_sweep_max.pdf')
pylab.show()
