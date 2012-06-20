import numpy as np
import pylab, time

def corr(nchan, fdata, accumulator):
    i=0
    for j in np.arange(nchan):
        for k in np.arange(j,nchan):
            accumulator[i] = fdata[j]*fdata[k].conjugate() + accumulator[i]
            i=i+1
    return accumulator

nchan=2560
ncyl = 5
antenna_locations_ns = [i*80.0/(nchan/ncyl) for i in range(nchan/ncyl)]
antenna_locations_ew = [i*20 for i in range(ncyl)]
xs,ys = np.meshgrid(antenna_locations_ew, antenna_locations_ns)

#n-s direction * some step set for each 
#phaseshifts = arange(-pi/2.0-phase_ns_offset,pi/2-phase_ns_offset,0.01)

theta_source = 15*np.pi/180.0
lam = 300.0/550.0
earth_rate = 7.2921159e-5  # radians/second
zenithDEC = 0.0

tstep=1/800e6*2056
#t = [x*tstep for x in range(2<<18)]
nsteps = 2<<10 #2<<12
print "number of time steps", str(nsteps)
t = np.arange(0,nsteps*tstep,tstep)

u = xs/lam
v = ys/lam
l=np.sin(t*np.cos(zenithDEC+theta_source)*earth_rate)
m=np.sin(theta_source)

signal = np.empty((len(l),xs.shape[0],xs.shape[1]), dtype=complex)
for i, ti in enumerate(t):
    l1=np.sin(ti*np.cos(zenithDEC+theta_source)*earth_rate)
    signal[i] = np.exp(1.0j*2*np.pi*(u*l1+v*m))

print signal.shape
#Is opposite of what I put in the document, where would each column be a single 
#time, so the matrix version is now A^dagger A instead of A A^dagger
signal.shape = (nsteps,nchan)

signal.real = (signal.real*7).round()
signal.imag = (signal.imag * 7).round()

#change to match the document
signal= signal.T

st1=time.time()
signalDagger = signal.conj().T
nloops = 1
st = time.time()
#for loops in range(nloops):
accumulator1 = np.dot(signal,signalDagger)
et=time.time()
dt =  et - st
print " matrix method took " + str( dt ) + ' seconds'

# call it 8 operations per complex MAC, N chan squared macs being wasteful, so
# actually computing twice the number needed
nops = nsteps*nloops*8*nchan**2 + nsteps*nchan
print str(nops) + " operations in " + str( dt ) + ' seconds'  
print str(nops/dt/1e9) + " Gflops"
#st=time.time()
#accumulator = np.zeros(((nchan*(nchan+1))/2),dtype=complex)

#for fdata in signal:
#    accumulator = corr(nchan, fdata, accumulator)
#et=time.time()
#print " python method took " + str(et - st ) + ' seconds'
#pylab.plot(signal[0,:])
#pylab.show()