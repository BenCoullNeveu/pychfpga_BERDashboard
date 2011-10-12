from numpy import *
import pylab, sys

pspecs = []
timestreams = []
ii=1
#size of sample block
slength = 1024
#Vpeak in bits (0-128)
slevel = 50
#freq1 (MHz)
freq1 = 570.0
#freq1 = 170.0
#freq2 (MHZ)
freq2 = 620.0
#freq2 = 220.0
sig = 0.2
#800MSPS sampling rate
freq = fft.fftfreq(slength,1/800.0)
freq = freq[:slength/2]
t = arange(slength)/800.0

try:
   nsims = sys.argv[1]
except:
   nsims = 1024


def gauss_window(data,sigma):
   npoints = data.size
   x = arange(npoints)
   return data*exp(-0.5*((x-(npoints-1)/2.0)/(sigma*(npoints-1)/2.0))**2)
      
def hann_window(data):
   npoints = data.size
   x = arange(npoints)
   return data*0.5*(1-cos(2*pi*x/(npoints-1)))

for sim in range(nsims):
   phase = rand()*2.0*pi
   phase2 = rand()*2*pi
   data = slevel*sin(2*pi*freq1*t+phase2) + slevel*sin(2*pi*freq2*t + phase) + 0.7*randn(1024)
   #data = 0.7*randn(1024)
   dataint = data#.astype(int8)
   timestreams.append(dataint)
   #pylab.plot(data)
   #pylab.show()
   #convert data from int to Volts
   data = dataint*0.5/256.0
   #data = gauss_window(data, sig)
   #data = hann_window(data)
   fftall = fft.fft(data)
   #convert to Vrms units
   fftall = fftall[:slength/2]*sqrt(2)/slength
   #convert to dbm assumes 50 ohms in.
   pspec = 10*log10((fftall*fftall.conjugate())/50.0) + 30.0
   pspec[0] = 0
   #print pspec.max()
   pspecs.append(pspec)
   #fd.close()
   ii+=1

pspecs = array(pspecs)
timestreams = array(timestreams)
#pylab.legend(loc=0)
#pylab.xlabel('freq (MHz)')
#pylab.ylabel('Power (dB)')
#pylab.savefig('neighboring_channels.pdf')
#pylab.ylim(-15,5)
#pylab.xlim(370,380)
#pylab.savefig(filename[:-4]+str(nfiles)+'_zoom.png')
#pylab.savefig(filename[:-4]+str(nfiles)+'.png')
#pylab.show()
