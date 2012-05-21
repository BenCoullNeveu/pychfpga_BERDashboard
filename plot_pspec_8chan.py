from numpy import *
import pylab, sys

pspecs = []
ii=1
#size of sample block
slength = 1024
#number of channels
nchan=8
sig = 0.2
#800MSPS sampling rate
freq = fft.fftfreq(slength,1/800.0)
freq = 800.0 - freq[:slength/2]

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
   #convert data from int to Volts
   data = load(filename)*0.5/256.0
   #data = data[:2097152]*0.5/256.0
   #data = data[:524288]#*0.5/256.0
   nsamples = data.size/slength/nchan
   print data.size
   data = data.reshape((nsamples,nchan,slength))
   for j in arange(data.shape[0]):
      for k in arange(nchan):
         #data[j,k,:] = gauss_window(data[j,k,:], sig)
	     #data[j,k,:] = hann_window(data[j,k,:])
	     data[j,k,:] = data[j,k,:]
   fftall = fft.fft(data)
   #convert to Vrms units
   fftall = fftall[:,:,:slength/2]*sqrt(2)/slength
   #convert to dbm assumes 50 ohms in.
   pspec = 10*log10(1e-20+(fftall*fftall.conjugate()).mean(axis=0)/100.0) + 30.0  #changed from 50 to 100 since adc is actually 100 ohms might be wrong
   pspec[:,0] = 0
   print pspec.max()
   pspecs.append(pspec)
   #fd.close()
   ii+=1
   ch=1
   for ps in pspec:
      pylab.plot(freq,ps, label=(filename[:-4]+ ' ch' + str(ch)))
      pylab.xlabel=('freq (MHz)')
      pylab.ylabel=('Power (dbm)')
      pylab.legend(loc=0)
      pylab.savefig(filename[:-4]+'_ch'+str(ch)+'.png')
      pylab.clf()
      ch+=1
   ch=1
   for ps in pspec:
      pylab.plot(freq,ps, label=('ch' + str(ch)))
      pylab.xlabel=('freq (MHz)')
      pylab.ylabel=('Power (dbm)')
      pylab.legend(loc=0)
      #pylab.clf()
      ch+=1
   pylab.savefig(filename[:-4]+'_allch'+'.pdf')
   pylab.show()
   pylab.clf()

#pylab.legend(loc=0)
#pylab.xlabel('freq (MHz)')
#pylab.ylabel('Power (dB)')
#pylab.savefig('neighboring_channels.pdf')
#pylab.ylim(-15,5)
#pylab.xlim(370,380)
#pylab.savefig(filename[:-4]+str(nfiles)+'_zoom.png')
#pylab.savefig(filename[:-4]+str(nfiles)+'.png')
#pylab.show()
