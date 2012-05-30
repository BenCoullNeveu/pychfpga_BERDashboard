import numpy as np
import struct, chFPGA
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

def write_header(datafile, est_clk, acc_len):
    ## Read gains from a file
    #f=open('gains.txt', 'r')
    gainA= numpy.empty([1024],dtype=numpy.int32)
    gainB= numpy.empty([1024],dtype=numpy.int32)
    gainC= numpy.empty([1024],dtype=numpy.int32)
    gainD= numpy.empty([1024],dtype=numpy.int32)
    #for i in range(1024):
    #    gainA[i] = int(f.readline())
    #for i in range(1024):
    #    gainB[i] = int(f.readline())
    #for i in range(1024):
    #    gainC[i] = int(f.readline())
    #for i in range(1024):
    #    gainD[i] = int(f.readline())
    #f.close()
    header_version=14  #we start at 1.2 as 1.0 was complex128, 1.1 was int32/int32 and 1.2 adds a header
    datafile.write(struct.pack('i', header_version))
    datafile.write(struct.pack('d', time.time()))
    datafile.write(struct.pack('f', est_clk))
    datafile.write(struct.pack('i', acc_len))
    datafile.write(gainA)
    datafile.write(gainB)
    datafile.write(gainC)
    datafile.write(gainD)

def convert_format(accumulator):
    #want 1024 int32 real, int32 imag
    interleave_a = numpy.empty([10,2048],dtype=np.int32)
    acc_real = accumulator.real.astype(np.int32)
    acc_imag = accumulator.imag.astype(np.int32)
    for i in range(1024):
        interleave_a[:,i * 2]     = acc_real[:,i]
        interleave_a[:,i * 2 + 1] = acc_imag[:,i]
    return interleave_a

def get_ADC_frames(c, channels, length=1024, frames=2):
    number_of_frames=0
    data_list=[]
    nchan = len(channels)
    chanIndex = range(nchan)
    contiguousFrames=2
    while (frames==0) or (frames!=0 and number_of_frames<frames):
        try:
            a=c.read_ADC_frame_simple(channels,length=length, frames=contiguousFrames) #(number_of_frames==0)
            #print a
            number_of_frames+=1					
            if filename:
                for chanNum in chanIndex:
                    data_list.append(a[channels[chanNum]])
        #file.write(np.int8(a[ch1,:]))
        except:
            raise
    data_list = np.array(data_list)
    return data_list


SN002_adc_delays=(
                  [16,22,22,22,22,22,22,22]+[0], #CH0 (BUFR)
                  [21]*8, #CH1 (BUFR)
                  [22]*8+[0], #CH2 (PLL)
                  [18]*8+[0], #CH3 (PLL)
                  [17]*8, #CH4 (BUFR)
                  [17]*8, #CH5 (BUFR)
                  [18]*8, #CH6 (BUFR)
                  [14]*8, #CH7 (BUFR)
                  )
    

if __name__ == "__main__":
  #import sys
  import time, os
  try:
          print 'Deleting previous chFPGA instances in current namespace'
          c.close() # close sockets from previous objects to free them for the new one
          del c
  except:
          pass
      
  ADC_TEST_MODE=0 	#  0= normal, 1= ramp, 2=pulse (1 high, 10 low)
  ADC_DELAY_TABLE=SN002_adc_delays # select the table corresponding to the FMC serial number
  FREF=10 # FMC Reference clock frequency 
  
  # Create the new chFPGA object.
  c=chFPGA.chFPGA(adc_test_mode=ADC_TEST_MODE, adc_delay_table=ADC_DELAY_TABLE,fref=FREF);
  c.sync()
  print
  
  # Displays the system frequencies
  c.FreqCtr.status()
  # save some number of frames to disk.
  channels = [1,2,3,4]
  c.setup_ADC(channels, length=1024, frames=2)
  #c.save_ADC_frames(channels=[0,1,2,3,4,5,6,7], frames=2048, contiguousFrames=4, filename='testing_600MHz.npy')
    
  try:
    #setup_adc
    intLoops = 2048 #sys.argv[1]
    nchan = 4
    length = 2048
    filename = 'out'
    nowtime=time.time()
    #nowtime = 1338143259.2
    basename = '\\Users\\chime\\workspace\\kevin\\data\\'+filename + '_'+ str(nowtime)+'\\'
    print basename
    os.mkdir(basename)
    fname=basename+filename+str(time.time())+'.'
    fcount = 0
    fout = open(fname+'%04i'%fcount, 'w+')
    est_clk = 65
    acc_len = 2*11
    write_header(fout, est_clk, acc_len)
    accumulator = np.zeros(((nchan*(nchan+1))/2,length/2))
    #pdata = 
    #tsdata = np.load('testing_600MHz.npy')
    #tsdata = tsdata.reshape((2048,8,4096))
    icount = 0
    fcount = 0
    cont = True
    while (cont):
        st = time.time()
        for i in np.arange(intLoops):
            #data = sim_data(dataLength=length, nchan=nchan)
            #data = tsdata[i,:nchan,:length]
            intLoopsMod = intLoops
            try:
                data = get_ADC_frames(c, channels, length=1024, frames=2)
            except:
                intLoopsMod = intLoopsMod - 1
                print "Lost one integration"
            fdata = fourier_transform(data)
            accumulator = corr(nchan, fdata, accumulator)
        accumulator = accumulator/intLoopsMod
        interleave_a = convert_format(accumulator)
        fout.write(interleave_a)
        et = time.time()
        icount = icount + 1
        if ( icount > 120):
            fout.close()
            icount = 0
            fcount=fcount+1
            if (fcount > 48):
                cont = False
            fname=basename+filename+str(time.time())+'.'+'%04i'%fcount
            fout=open(fname,'w+')
            #f_osc=open(fname+'.osc','w+')
            write_header(fout, est_clk, acc_len)
            #start_time = time.time()
        print "took " + str(et - st ) + ' seconds'
  except KeyboardInterrupt:
    fout.close()
  except:
    print "something bad happend"  
    raise
