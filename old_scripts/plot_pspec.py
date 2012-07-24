from numpy import *
import pylab, sys

pspecs = []
ii=1
slength = 1024
sig = 0.2
freq = fft.fftfreq(slength,1/800.0)

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
   #fd = open(filename, 'rb')
   #data = fromfile(file=fd, dtype=int8)
   data = load(filename)*0.5/256.0
   #data = data[:2097152]*0.5/256.0
   #data = data[:524288]#*0.5/256.0
   nsamples = data.size/slength
   print data.size
   data = data.reshape((nsamples,slength))
   for j in arange(data.shape[0]):
      #data[j] = gauss_window(data[j], sig)
	  #data[j] = hann_window(data[j])
	  data[j] = data[j]
   fft1 = fft.fft(data)
   #convert to Vrms units
   fft1 = fft1[:,:slength/2]*sqrt(2)/slength
   freq = freq[:slength/2]
   #convert to dbm assumes 50 ohms in.
   pspec = 10*log10((fft1*fft1.conjugate()).mean(axis=0)/50.0) + 30.0
   pspec[0] = 0
   print pspec.max()
   pspecs.append(pspec)
   #fd.close()
   ii+=1
   pylab.plot(freq,pspec, label=filename[:-4])

pylab.legend(loc=0)
pylab.xlabel('freq (MHz)')
pylab.ylabel('Power (dB)')
#pylab.savefig('neighboring_channels.pdf')
#pylab.ylim(-15,5)
#pylab.xlim(370,380)
#pylab.savefig(filename[:-4]+str(nfiles)+'_zoom.png')
pylab.savefig(filename[:-4]+str(nfiles)+'.png')
pylab.show()
