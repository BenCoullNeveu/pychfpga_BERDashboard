from numpy import *
import pylab, sys
from scipy.optimize import leastsq

dataArray = load(sys.argv[1])
dataArray = dataArray.reshape(dataArray.shape[0]/8,8,1024)

phases0 = zeros(dataArray.shape[0])
phases4 = zeros(dataArray.shape[0])
amplitudes0 = zeros(phases0.size)
amplitudes4 = zeros(phases0.size)

freq1 = 12.5

x = arange(1024)*1/800.0

errors = ones(1024)

def residuals(p, y, x, errors):
     err = (y-peval(x,p))/errors
     return err

def peval(x, p):
     return p[1]*sin(2*pi*freq1*x + p[0])
	 
for i in arange(phases0.size):
     p0 = array([0.1,45.0])
     y0 = dataArray[i,0,:]
     y4 = dataArray[i,4,:]
     plsq = leastsq(residuals, p0, args=(y0, x, errors), maxfev=2000)
     phases0[i] = plsq[0][0]
     amplitudes0[i] = plsq[0][1]
     plsq = leastsq(residuals, p0, args=(y4, x, errors), maxfev=2000)
     phases4[i] = plsq[0][0]
     amplitudes4[i] = plsq[0][1]
	  
print phases0
print amplitudes0

diff = phases0-phases4
print diff.mean()
print diff.std()

pylab.plot(phases0)
pylab.plot(phases4)
pylab.plot(phases0 - phases4)
pylab.show()