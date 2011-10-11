from numpy import *
import pylab, sys

pspecs = []
flabels = []
ii=1
#size of sample block
slength = 1024
#number of channels
nchan=8
sig = 0.2
#800MSPS sampling rate
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
   freq = freq[:slength/2]
   freq = 800.0-freq
   #convert to dbm assumes 50 ohms in.
   pspec = 10*log10((fftall*fftall.conjugate()).mean(axis=0)/50.0) + 30.0
   pspec[:,0] = 0
   print pspec.max()
   pspecs.append(pspec)
   #fd.close()
   ii+=1
   #ch=1
   flabels.append(filename[:-4])
   #for ps in pspec:
   #   pylab.plot(freq,ps, label=(filename[:-4]+ ' ch' + str(ch)))
   #   pylab.xlabel=('freq (MHz)')
   #   pylab.ylabel=('Power (dbm)')
   #   pylab.legend(loc=0)
   #   pylab.savefig(filename[:-4]+'_ch'+str(ch)+'.png')
   #   pylab.clf()
   #   ch+=1

data_chan = 2

ps = pspecs[0][data_chan]

tone1s = 570
tone2s = 620

tone1zone = (freq > tone1s-5.0) & (freq < tone1s+5.0)
tone2zone = (freq > tone2s-5.0) & (freq < tone2s+5.0)


ps_t1 = max(ps[tone1zone])
ps_t2 = max(ps[tone2zone])
ti1 = where(ps == ps_t1)[0][0]
ti2 = where(ps == ps_t2)[0][0]
tone1 = freq[ti1]
tone2 = freq[ti2]

print tone1, tone2

ip3fa = 2*tone1-tone2
ip3fb = 2*tone2-tone1

print ip3fa, ip3fb

ip3fazone = (freq > ip3fa-1.0) & (freq < ip3fa+1.0)
ip3fbzone = (freq > ip3fb-1.0) & (freq < ip3fb+1.0)
ps_ip3a = max(ps[ip3fazone])
ps_ip3b = max(ps[ip3fbzone])
ip3fa = freq[where(ps==ps_ip3a)[0][0]]
ip3fb = freq[where(ps==ps_ip3b)[0][0]]
ps_ip3b = max(ps[ip3fbzone])

toi = ps_t1 + 0.5*(ps_t1 - ps_ip3b)
print ps_t1, ps_t2
print ps_ip3a, ps_ip3b
print toi

plot_fa = array([ip3fa,ip3fa])
plot_fay = array([min(ps),max(ps)])
plot_fb = array([ip3fb,ip3fb])
plot_fby = array([min(ps),max(ps)])

pylab.plot(plot_fa,plot_fay,'r-')
pylab.plot(plot_fb,plot_fby,'r-')
pylab.plot(freq,ps)
#pylab.legend(loc=0)
pylab.xlabel('freq (MHz)')
pylab.ylabel('Power (dB)')
pylab.savefig('IP3.pdf')
#pylab.ylim(-15,5)
#pylab.xlim(370,380)
#pylab.savefig(filename[:-4]+str(nfiles)+'_zoom.png')
#pylab.savefig(filename[:-4]+str(nfiles)+'.png')
pylab.show()
