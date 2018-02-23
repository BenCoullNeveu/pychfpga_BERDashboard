#-------------------------------------------------------------------------------
#-----------------------Packages------------------------------------------------
#-------------------------------------------------------------------------------
import os
import glob
import argparse
import subprocess
import csv
import random

import numpy as np
import h5py
import datetime as dt
import time as tm

#import matplotlib
#matplotlib.use('Agg')
import matplotlib.pyplot as plt

from scipy import signal
from scipy import stats
from scipy.stats import kurtosis
from scipy.stats import skew
from skimage import filters

import log
ilog = log.get_logger(__name__)

FMT = 'FCC{:02d}{:02d}{:02d}'


#-------------------------------------------------------------------------------
#-------------------Reading CHIME data------------------------------------------
#---if one does not want timestream then simply give value to tm other than None
class chime_rawadc_reader():
    def __init__(self,files):
        self.Nfiles = len(files)
        self.h5pyfile = [h5py.File(f, 'r') for f in files]
        self.crate = [f['crate'].value.reshape(-1) for f in self.h5pyfile]
        self.slot = [f['slot'].value.reshape(-1) for f in self.h5pyfile]
        self.adc_channel = [f['adc_input'].value.reshape(-1)  for f in self.h5pyfile]
        self.timestamp = [f['timestamp'].value['ctime'].reshape(-1)  for f in self.h5pyfile]
        self.timestream = [f['timestream'] for f in self.h5pyfile]
        self.adc_channel_index = [12, 13, 14, 15, 8, 9, 10, 11, 4, 5, 6 ,7, 0, 1, 2, 3]
        self.DATA = self.get_data()

    def get_data(self):
        DATA = dict()
        ID = [FMT.format(a,b,c) for a in range(8) for b in range(16) for c in range(16)]
        for ig in ID:
            DATA[ig] = []
        for ff in range(self.Nfiles):
            Ninputs = len(self.crate[ff])
            for ii in range(Ninputs):
                DATA[FMT.format(self.crate[ff][ii], self.slot[ff][ii], self.adc_channel[ff][ii])].append([self.timestamp[ff][ii], self.timestream[ff][ii]])
        return DATA

    def get_adc_input(self,crate,slot,adc_input,tm=None):
        adc = self.adc_channel_index[adc_input]
        data =  self.DATA[FMT.format(crate,slot,adc)]
        T = []
        V = []
        for s,d in data:
            T.append(s)
            V.append(d)
        if tm == None:
            return V
        else:
            return V,T
#-------------------------------------------------------------------------------
#-------------------Function for deciding Thresholds----------------------------
def threshold(dictionary):
    A = []
    a = []
    for value in dictionary.values():
        A.append(value)
    A = np.array(A)
    val = filters.threshold_otsu(A)
    for i in A:
        if i > val:
            a.append(i)
    q75, q25 = np.percentile(a, [75 ,25])
    IQR = q75 - q25
    Threshold = q25 - IQR*3
    return Threshold
#------------------------------------------------------------------------------
#-------------------Saving Images of the Bad channels--------------------------
def save_images(obj, obj1, obj2, inputs, path, var_name, data, align=False):
    k = 0
    plot_dir = os.path.join(path, var_name)
    mkdir(plot_dir)
    for I,J,K in inputs:
        HIST = []
        k = k+1
        ch,t = obj.get_adc_input(I,J,K,0)
        mu = data.mean[FMT.format(I,J,K)]
        for e in ch:
            hist,bins=np.histogram(e - mu,bins=np.arange(-129,128,1))
            HIST.append(hist)
        HIST = np.array(HIST)
        Hist = np.median(HIST,axis=0)
        FFt = []
        for i in range(len(ch)):
            FFT = abs(np.fft.fft(ch[i])[:1024])**2
            FFt.append(FFT)
        FFt = np.array(FFt)
        data_FFT = np.median(FFt,axis=0)
        fig = plt.figure(num=k,figsize=(10,8),dpi=400)
        sub1 = fig.add_subplot(2,1,1)
        sub2 = fig.add_subplot(2,1,2)
        if align:
            data_FFT = (((data_FFT)/(np.median(data_FFT)))*np.median(obj2.Temp_fft)) #Data normalized to FFT Template level
        sub1.semilogy(np.linspace(800, 400, 1024, endpoint=False), data_FFT,'b',linewidth=1,label='FFT channel')
        sub1.semilogy(np.linspace(800, 400, 1024, endpoint=False),obj2.Temp_fft,'r',linewidth=1,label='FFT Template')
        sub2.plot(np.arange(-128,128,1),Hist,'b',linewidth=1,label='Averaged channel histogram')
        sub2.plot(np.arange(-128,128,1),obj1.Temp_Hist,'r',linewidth=1,label='Histogram Template')
        sub1.grid()
        sub1.legend()
        sub2.legend()
        sub1.set_title('FFT plot normalized to align its continuum with that of FFT template')
        sub2.set_title('Averaged histogram')
        sub1.set_xlabel('Frequency (MHz)')
        sub2.set_xlabel('Bins')
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, FMT.format(I,J,K) + '.png'), dpi=400)
        plt.gcf().clear()
        plt.close()

#-------------------------------------------------------------------------------
#-------------------Saving Data as a cvs file-----------------------------------
def csv_file(first_row,data,path,name_file):
    with open('{}/{}.csv'.format(path,name_file), 'wb') as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',',quotechar='|', quoting=csv.QUOTE_MINIMAL)
        filewriter.writerow(first_row)
        filewriter.writerows(data)

def mkdir(path):
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise

#-------------------------------------------------------------------------------
#-------------------LATEX file and PDF generation codes-------------------------
"""
Created on Thurday November 2 5:29 pm 2017
@author: Mohit Bhardwaj
Code is meant to produce a latex file which contains list of doubtful channels and a table containing their credentials
and statistical parameters, and finally plots of the non-zero Bad channels
"""
class latex():
    def __init__(self, filename_no_extension):
        self._filename = filename_no_extension.rsplit('.')[0]
        self._file = open(filename_no_extension + '.tex', 'w')
        self._eqn_counter = 0
        self._fig_counter = 0
        self._table_counter = 0
        self._section_counter = 0

    def add_file_start(self):
        self._file.write('\\documentclass[12pt,a4paper]{article}\n'+ \
                         '\\usepackage[utf8]{inputenc}\n'+ \
                         '\\usepackage{amsmath,amsfonts,amsthm} % Math packages\n'+ \
                         '\\usepackage{graphicx}\n'+ \
                         '\\usepackage[left=2cm,right=2cm,top=2cm,bottom=2cm,headheight=15pt]{geometry}\n'+ \
                         '\\author{Mohit Bhardwaj}\n'+ \
                         '\\maxdeadcycles=1000\n'+ \
                         '\\title{CHIME Channel Classification Using ADC Raw-Data }\n'+ \
                         '\\usepackage{booktabs} % Horizontal rules in tables\n'+ \
                         '\\usepackage{float}\n'+\
                         '\\usepackage{longtable}\n'+\
                         '\\usepackage{titlesec} % Allows customization of titles\n\n')

        self._file.write('\\renewcommand'+\
                         '\\thesection{\Roman{section}} % Roman numerals for the sections\n'+ \
                         '\\renewcommand'+\
                         '\\thesubsection{\Roman{subsection}} % Roman numerals for subsections\n'+ \
                         '\\titleformat{\section}[block]{\large\scshape\centering}{'+\
                         '\\thesection.}{1em}{} % Change the look of the section titles\n'+ \
                         '\\titleformat{\subsection}[block]{\large}{'+\
                         '\\thesubsection.}{1em}{} % Change the look of the section titles\n'+ \
                         '\\usepackage{fancyhdr} % Headers and footers\n'+ \
                         '\\pagestyle{fancy} % All pages have headers and footers\n'+ \
                         '\\fancyhead{} % Blank out the default header\n'+ \
                         '\\fancyfoot{} % Blank out the default footer\n'+ \
                         '\\fancyfoot[R]{'+\
                         '\\thepage} % Custom footer text\n'+ \
                         '\\fancyhead[C]{channel classification based on Raw-ADC data} % Custom header text\n'+ \
                         '\\begin{document}\n'+ \
                         '\\maketitle % Insert title\n'+ \
                         '\\thispagestyle{fancy} % All pages have headers and footers\n')


    def summary_table(self,No_good,No_Bad_zero_rms,No_Bad_nonzero_rms,No_missing,No_doubtful,label=None):
        self._table_counter += 1
        if label==None:
            label = 'S:summary'
        self._file.write('\\begin{table}[!h]\n'+ \
                         '\\label{{{}}}\n'.format(label)+ \
                         '\\begin{center}\n'+ \
                         '\\begin{tabular}{|c|c|}\n'+ \
                         '\\hline\n'+ \
                         'Good channels & {}\\\ \n'.format(No_good) + \
                         '\\hline\n'+ \
                         'Bad channels with with RMS (LSB) $<$ 1 LSB & {}\\\ \n'.format(No_Bad_zero_rms) +\
                         '\\hline\n'+ \
                         'Bad channels with with RMS (LSB) $>$ 1 LSB & {} \\\ \n'.format(No_Bad_nonzero_rms) +\
                         '\\hline\n'+ \
                         'Missing channels (No data stored in chunk files) & {}\\\ \n'.format(No_missing) +\
                         '\\hline\n'+ \
                         'Doubtful Channels & {}\\\ \n'.format(No_doubtful) +\
                         '\\hline \n'+ \
                         '\\end{tabular}\n'+ \
                         '\\end{center}\n'+ \
                         '\\end{table}\n\n')
        return label


    def add_figure(self, fig_filename, caption, frac_textwidth=0.7, label=None, angle=None):
        self._fig_counter += 1
        angletext = ' '
        if angle is not None:
            angletext = ', angle=' + str(angle)
        if label is None:
            label = 'f_'+ str(self._fig_counter)
        self._file.write('\\begin{figure}[!h] \\begin{center} \n' + \
                         '\\includegraphics[width=' + str(frac_textwidth) + '\\textwidth'  + \
                         angletext + ']{' + fig_filename + '}' + \
                         '\\caption{\\label{' + label + '} ' + caption + '}' + \
                         '\\end{center} \\end{figure} \n\n')
        return label

    def section(self,title,sec_label=None):
        self._section_counter += 1
        if sec_label==None:
            sec_label = 'S:'+str(self._section_counter)
        self._file.write('\section{{{0}}} \label{{{1}}}\n'.format(title,sec_label))


    def format_tabular_from_array(self, top_labels, side_labels, array,caption, label=None ):
        # formats an N+1 x M+1 element table from an N rows x M columns array
        #     top_labels is an M+1 element list of labels for the first row
        #     side_labels is an N element list of labels for the first column of each subsequent row
        #
        # Error check on array sizes:
        self.add_table_start()
        if ( len(top_labels) != array.shape[1]+1 ) or ( len(side_labels) != array.shape[0] ):
            print "format_tabular_from_array: array shape error"
            print len(top_labels)
            print len(side_labels)
            print array.shape
        if label is None:
            label = 't_'+str(self._table_counter)
        col_def = '|l'
        for i in range(0,array.shape[1]): col_def += '|c'
        col_def += '|'
        self._file.write('\\begin{longtable}{' + col_def + '}')
        self._file.write('\n\\caption{\\label{' + label + '} ' + caption + '}\\\ \n\hline')
        row_text = '\n '
        for col in range(0,len(top_labels)):
            if col != 0: row_text += ' & '
            row_text += str(top_labels[col])
        row_text += '\\\\ \\hline\n'
        self._file.write( row_text )

        self._file.write('\endfirsthead \n\multicolumn{}{{c}}% \n'.format('{'+str(len(top_labels))+'}'))
        self._file.write('\n' + r'{\tablename\ \thetable\ -- \textit{Continued from previous page}} \\ \hline')
        row_text = '\n'
        for col in range(0,len(top_labels)):
            if col != 0: row_text += ' & '
            row_text += str(top_labels[col])
        row_text += '\\\\ \\hline\n'
        self._file.write( row_text )

        self._file.write(r'\endhead'+'\n')
        self._file.write(r'\hline \multicolumn{}{{r}}{{\textit{{Continued on next page}}}} \\'.format('{'+str(len(top_labels))+'}')+'\n')
        self._file.write(r'\endfoot'+'\n')
        self._file.write(r'\hline'+'\n')
        self._file.write(r'\endlastfoot'+'\n')
        for row in range( 0, array.shape[0] ):
            row_text = str( side_labels[row] )
            for col in range(0,array.shape[1]): row_text += ' & ' + str(array[row,col])
            row_text += ' \\\\ \n'
            self._file.write( row_text )

        self.add_table_end()

    def add_table_start(self):
        self._table_counter += 1
        self._file.write('\\begin{center} \n') #+ \

    def add_table_end(self):
        self._file.write('\\hline \n\\end{longtable}\n\\end{center} \n\n')
        #return label

    def add_file_end(self):
        # write end of file stuff
        self._file.write('\\end{document} \n')
        self._file.close()

    def tex_it(self):
        k = 'pdflatex ' + str(self._filename) + '.tex'
        subprocess.call(k, shell=True)
        subprocess.call(k, shell=True)
        subprocess.call('rm ' + str(self._filename.rsplit('/')[-1]) + '.log ' + str(self._filename.rsplit('/')[-1]) + '.aux', shell=True)
        subprocess.call('mv {}.pdf {}.pdf'.format(str(self._filename.rsplit('/')[-1]),str(self._filename)),shell=True)
    def add_text(self,text):
        self._file.write(text)
#-------------------------------------------------------------------------------
#-----------------------Creating templates--------------------------------------
# def create_Htemp(filename,obj1,obj2):
#     hd = h5py.File(filename[0],'r')
#     data = hd['timestream']
#     filtered_data = []
#     for e in data:
#         if np.std(e) <=16 and np.std(e) >=8:
#             filtered_data.append(e)
#     DATA =[]
#     k = []
#     Da = []
#     filtered_data = np.array(filtered_data)
#     for e in filtered_data:
#         k1,p = stats.normaltest(e)
#         if p > 0.05:
#             k.append(k1)
#             Da.append(e)
#     q75, q25 = np.percentile(k, [75 ,25])
#     k_lower = q75 + 1.5*(q75 - q25)
#     for i,j in enumerate(k):
#         if j < k_lower:
#             DATA.append(Da[i])
#
#     DATA = np.array(DATA)
#     obj1.Temp_Hist = np.histogram(DATA, bins=obj1._nbins, range=obj1._range)[0] / float(len(DATA))
#     obj2.Temp_fft = np.mean(np.abs(np.fft.rfft(DATA, axis=-1))**2, axis=0)[:-1]

# Implementation that does not read entire dataset into memory
def create_templates_from_file(filename, obj1, obj2):

    hd = h5py.File(filename[0],'r')
    data = hd['timestream']

    index, klist = [], []

    for ind, frame in enumerate(data):

        rms = np.std(frame)

        if (rms >= 8) and (rms <= 16):

            kval, pval = stats.normaltest(frame)

            if pval > 0.05:

                index.append(ind)
                klist.append(kval)

    kperc = np.percentile(klist, [25, 75])
    k_upper = kperc[1] + 1.5 * np.diff(kperc)

    hist = np.zeros(obj1._nbins, dtype=np.float64)
    spec = np.zeros(obj2._nfreq, dtype=np.float64)
    count = 0

    for ind, kval in zip(index, klist):
        if kval < k_upper:
            hist += np.histogram(data[ind], bins=obj1._nbins, range=obj1._range)[0]
            spec += np.abs(np.fft.rfft(data[ind])[0:obj2._nfreq])**2
            count += 1

    hist /= float(count)
    spec /= float(count)

    obj1.Temp_Hist = hist
    obj2.Temp_fft = spec

    hd.close()


def create_templates_from_data(data, obj1, obj2):

    index, klist = [], []

    for key, stream in data.iteritems():

        for ind, (timestamp, frame) in enumerate(stream):

            rms = np.std(frame)

            if (rms >= 8) and (rms <= 16):

                kval, pval = stats.normaltest(frame)

                if pval > 0.05:

                    index.append((key, ind))
                    klist.append(kval)

    kperc = np.percentile(klist, [25, 75])
    k_upper = kperc[1] + 1.5 * np.diff(kperc)

    hist = np.zeros(obj1._nbins, dtype=np.float64)
    spec = np.zeros(obj2._nfreq, dtype=np.float64)
    count = 0

    for ind, kval in zip(index, klist):
        if kval < k_upper:
            hist += np.histogram(data[ind[0]][ind[1]][1], bins=obj1._nbins, range=obj1._range)[0]
            spec += np.abs(np.fft.rfft(data[ind[0]][ind[1]][1])[0:obj2._nfreq])**2
            count += 1

    hist /= float(count)
    spec /= float(count)

    obj1.Temp_Hist = hist
    obj2.Temp_fft = spec


def create_templates(data, obj1, obj2):

    if isinstance(data, dict):

        create_templates_from_data(data, obj1, obj2)

    elif isinstance(data, basestring):

        create_templates_from_file(data, obj1, obj2)

    else:
        ValueError(" Cannot construct template from %s." % type(data))

#-------------------------------------------------------------------------------
#-----------------------FFT-Test class------------------------------------------
class FFT_template_test():

    _nfreq = 1024

    def __init__(self):
        self.spectrum = dict()
        self.corr = dict()

    def load_FFT_Template(self):
        dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
        Temp_fft = []
        with open(os.path.join(dirname, 'template_spectrum.txt'), 'r') as f:
            for line in f:
                Temp_fft.append(float(line.rstrip()))
        self.Temp_fft = np.array(Temp_fft)

    def corr_coeff_fft(self, data, crate, slot, channel):
        if len(data) == 0:
            self.spectrum[FMT.format(crate,slot,channel)] = None
            self.corr[FMT.format(crate,slot,channel)] = None

        else:
            spec = np.median(np.abs(np.fft.rfft(np.array(data), axis=-1))**2, axis=0)[0:self._nfreq]
            spec *= (np.median(self.Temp_fft) / np.median(spec))  #This makes continuum part aligned

            self.spectrum[FMT.format(crate,slot,channel)] = spec

            specm = np.power( signal.medfilt(spec, kernel_size=7), 0.2)
            tempm = np.power(self.Temp_fft, 0.2)
            corr = np.correlate(specm, tempm)[0] / (np.linalg.norm(specm) * np.linalg.norm(tempm))
            self.corr[FMT.format(crate,slot,channel)] = corr

#-------------------------------------------------------------------------------
#-----------------------Histogram Test------------------------------------------
class Normality_test():
    '''This class test the dataframes for its normality by comparing ( or correlating) it with the good channel
    histogram template. if the correlation is more than 0.9 then those dataframes are considered good else bad
    channel candidates.

    It is possible that for a given channel, we have few dataframes detected as bad one and others good one
    (don't know exactly why but possible might be due to adc or random increment in stocastic noise)
    So to avoid wrong channel classification, I used the criteria that if there are more than 25% dataframes
    in a given channel classified as bad channels, then I consider it bad channel according to this test'''

    _nbins = 256
    _range = (-128.5, 127.5)

    def __init__(self):
        self.histogram = dict()
        self.corr = dict()

    def load_Histogram_template(self):
        dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
        with open(os.path.join(dirname, 'template_histogram.txt'), 'r') as t:
            str1 = t.read()
            self.Temp_Hist = np.array([int(i) for i in str1.strip().rsplit('\n')])

    def corr_coeff_hist(self, data, crate, slot, channel, mu):
        if len(data) == 0:
            self.histogram[FMT.format(crate,slot,channel)] = None
            self.corr[FMT.format(crate,slot,channel)] = None

        else:
            hist = np.zeros((len(data), self._nbins), dtype=np.float32)
            for ff, frame in enumerate(data):
                hist[ff, :] = np.histogram(frame - mu, bins=self._nbins, range=self._range)[0]

            hist = np.median(hist, axis=0)
            self.histogram[FMT.format(crate,slot,channel)] = hist

            corr = np.correlate(hist, self.Temp_Hist)[0] / (np.linalg.norm(hist) * np.linalg.norm(self.Temp_Hist))
            self.corr[FMT.format(crate,slot,channel)] = corr

#-------------------------------------------------------------------------------
#-----------------------Data storing class--------------------------------------
class DataAnalysis(object):
    def __init__(self,obj1,obj2):
        self.Bad_channel_Normal = []
        self.Bad_channel_Zero = []
        self.Good_channel = []
        self.Missing_channel = []
        self.Doubtful_channel = []
        self.Good_channel1 = []
	self.Bad_channel_Zero1 = []
	self.Bad_channel_Normal1 = []
	self.Doubtful_channel1 = []

        self.nframe = dict()
        self.mean = dict()
        self.kurtosis = dict()
        self.skew = dict()
        self.rms = dict()
        self.snr = dict()
        self.result = dict()

        self.freq = np.linspace(800, 400, 1024, endpoint=False)
        self.lsb = np.linspace(-128, 127, 256)

        self.histogram = dict()
        self.spectrum = dict()

        self.histogram_corr_coeff = dict()
        self.spectrum_corr_coeff = dict()

        self.histogram_fail = dict()
        self.spectrum_fail = dict()

        self.histogram_threshold = None
        self.spectrum_threshold = None

        self.histogram_template = None
        self.spectrum_template = None

    def feed(self, ch, crate, slot, channel):

        key = FMT.format(crate, slot, channel)
        if len(ch) == 0:
            self.nframe[key] = None
            self.mean[key] = None
            self.kurtosis[key] = None
            self.skew[key] = None
            self.rms[key] = None
            self.snr[key] = None
            self.result['{}-{}-{}'.format(crate,slot,channel)] ='MISSING'
            self.Missing_channel.append([crate,slot,channel])
        else:
            self.nframe[key] = len(ch)
            self.mean[key] = np.mean(np.array([np.mean(x) for x in ch]))
            self.kurtosis[key] = np.mean(np.array([kurtosis(x) for x in ch]))
            self.skew[key] = np.mean(np.array([skew(x) for x in ch]))
            self.rms[key] = np.mean((np.array([np.std(x) for x in ch])))
            rms = [(np.std(ch[i]))**2 for i in range(len(ch))]
            RMS = np.std(rms)
            RMS_Mean = np.mean(rms)
            self.snr[key] = (RMS_Mean/RMS)

    def channel_Analysis(self, obj1, obj2, Threshold_1, Threshold_2):

        self.histogram_template = obj1.Temp_Hist
        self.histogram_threshold = Threshold_1

        for key, value in obj1.corr.iteritems():

            self.histogram_corr_coeff[key] = value
            self.histogram_fail[key] = value <= Threshold_1
            self.histogram[key] = obj1.histogram[key]

        self.spectrum_template = obj2.Temp_fft
        self.spectrum_threshold = Threshold_2

        for key, value in obj2.corr.iteritems():

            self.spectrum_corr_coeff[key] = value
            self.spectrum_fail[key] = value <= Threshold_2
            self.spectrum[key] = obj2.spectrum[key]

    def analysis_data(self,obj1,threshold,w,q1,q2,q3):  #w=0.5 for test-2, w=1.5 for test-1
        rt = 1    		
        if w == 1.5:
            rt = 2
        Weight = dict()
        if q1 > 0: # the cutoff is either mean or 0 which ever is smaller.
            s = 0
        else:
            s = q1
        for i,j in obj1.corr.iteritems():
            if j == None:
                continue
            j = j - threshold
            if j > s or j==s:
                Weight[i] = 10
            elif j < s and j > q2 or j == q2:
                Weight[i] = 6.6*w
            elif j < q2 and j > q3 or j == q3:
                Weight[i] = 3.3*rt
            elif j < q3:
                Weight[i] = 0
        return Weight

    def re_analysis(self, obj1,obj2,Threshold_1,Threshold_2):
        Weight = dict()	
        q11,q12,q13 = self.find_divisions(obj1,Threshold_1)
        q21,q22,q23 = self.find_divisions(obj2,Threshold_2)
        wt1 = self.analysis_data(obj1,Threshold_1,1.5,q11,q12,q13)
        wt2 = self.analysis_data(obj2,Threshold_2,0.5,q21,q22,q23)
        for key in wt1.keys():
            Weight[key] = wt1[key]+wt2[key]
        print Weight
        for i,j in Weight.items():
            if wt1[i] == 0 or wt2[i]==0:
                j = 0
            if j > 14.0:
                self.result[i] = 'GOOD'
    	    elif j < 14.0 and j > 6.0:
                self.result[i] = 'DOUBTFUL'
    	    elif j<6.0:
                self.result[i] = 'BAD'

    def find_divisions(self,obj,threshold):
        data = []			
        for crate,slot,channel in self.Doubtful_channel1:
            data.append(obj.corr['{}-{}-{}'.format(crate,slot,channel)] - threshold)
            q75, q50, q25 = np.percentile(data, [75, 50, 25])
            k_lower = q25 - 1.5*(q75 - q25)
            return q50, q25, k_lower
		
    def results(self):
        TAGS = [[a,b,c] for a in range(8) for b in range(16) for c in range(16)]
        print 'Start'
        print '-------Results---------\n'
        for crate,slot,channel in TAGS:
            if self.result['{}-{}-{}'.format(crate,slot,channel)] == 'MISSING':
                continue
            if self.result['{}-{}-{}'.format(crate,slot,channel)] == 'GOOD':
                self.Good_channel.append([crate,slot,channel])
            elif self.result['{}-{}-{}'.format(crate,slot,channel)] == 'BAD':
                if self.RMS_ch['{}-{}-{}'.format(crate,slot,channel)] < 1:				
                    self.Bad_channel_Zero.append([crate,slot,channel])
                else:
                    self.Bad_channel_Normal.append([crate,slot,channel])
            elif self.result['{}-{}-{}'.format(crate,slot,channel)] == 'DOUBTFUL':
                    self.Doubtful_channel.append([crate,slot,channel])

    def Results(self):
        TAGS = [[a,b,c] for a in range(8) for b in range(16) for c in range(16)]
        for crate,slot,channel in TAGS:
            key = FMT.format(crate,slot,channel)
            if not self.histogram_fail[key] and not self.spectrum_fail[key]:
                self.Good_channel1.append([crate,slot,channel])
            elif self.histogram_fail[key] and self.spectrum_fail[key]:
                if self.rms[key] < 1:
                    self.Bad_channel_Zero1.append([crate,slot,channel])
                else:
                    self.Bad_channel_Normal1.append([crate,slot,channel])
            else:
                self.Doubtful_channel1.append([crate,slot,channel])

    def display_stats(self):
        ilog.info('Total channels in the chunk : {}'.format(len(self.Bad_channel_Normal) + len(self.Missing_channel) +
                                                               len(self.Bad_channel_Zero) + len(self.Good_channel) + len(self.Doubtful_channel)))
        ilog.info('Good channels : {}'.format(len(self.Good_channel)))
        ilog.info('Missing Channels : {}'.format(len(self.Missing_channel)))
        ilog.info('Bad channels with near-zero RMS : {}'.format(len(self.Bad_channel_Zero)))
        ilog.info('Bad channels with non-zero RMS : {}'.format(len(self.Bad_channel_Normal)))
        ilog.info('Doubtful channels : {}'.format(len(self.Doubtful_channel)))
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

def adc_to_fla(crate, slot, inp):

    bulkhead = adc_to_fla_bulkhead(crate)
    col = adc_to_fla_col(slot)
    row = adc_to_fla_row(crate, inp)

    return bulkhead, col, row

def adc_to_fla_bulkhead(crate):

    return chr(65 + (crate / 2))

def adc_to_fla_col(slot):

    all_cols = [chr(65 + ii) for ii in np.arange(18)]
    all_cols.remove('I')
    all_cols.remove('O')

    return all_cols[slot]

def adc_to_fla_row(crate, inp):

    return 16 * ((crate + 1) % 2) + inp


def array_const(obj, CH, wtest=False):
    K = []
    for i,j,k in CH:
        bulkhead, col, row = adc_to_fla(i, j, k)

        K1 = ['${}-{}-{}$'.format(i,j,k),r'${}\_{}{}$'.format(bulkhead,col,row),round(obj.mean[FMT.format(i,j,k)],3),
              round(obj.rms[FMT.format(i,j,k)],3),round(obj.kurtosis[FMT.format(i,j,k)],3),round(obj.skew[FMT.format(i,j,k)],3)]

        if wtest:
            K1 += [round(obj.histogram_fail[FMT.format(i,j,k)], 3), round(obj.spectrum_fail[FMT.format(i,j,k)], 3)]

        K.append(K1)

    return K
#-------------------------------------------------------------------------------
#-----------------------Main function-------------------------------------------
def main(input_files, output_dir=None, output_csv=True, output_plot=True, output_tex=True, compute_template=True):
    """
    Syntax : python /home/chime/Videos/Faster_code/Final_Code/Code.py /home/chime/Music/New_Data/000000.h5 /home/chime/Music/New_Data/ 20171123T141924Z_chime_rawadc
    """

    if not hasattr(input_files, '__iter__'):
        input_files = [input_files]

    if output_dir is None:
        output_dir = os.getcwd()

    acq = os.path.basename(os.path.dirname(input_files[0]))
    path_acq = os.path.join(output_dir, acq)

    chunk = os.path.splitext(os.path.basename(input_files[0]))[0]
    path = os.path.join(path_acq, chunk)

    # If necessary create an output directory
    if output_csv or output_plot or output_tex:
        mkdir(path_acq)
        mkdir(path)

    # Read in data
    data = chime_rawadc_reader(input_files)

    # Instantiate objects to hold test results
    Test_1 = Normality_test()
    Test_2 = FFT_template_test()
    DATA = DataAnalysis(Test_1, Test_2)

    # If requested, compute histogram and FFT templates.  Otherwise use packaged defaults.
    if compute_template:
        create_templates(data.DATA, Test_1, Test_2)
    else:
        Test_1.load_Histogram_template()
        Test_2.load_FFT_Template()

    x = [[a,b,c] for a in range(8) for b in range(16) for c in range(16)]
    for crate,slot,channel in x:
        ch = data.get_adc_input(crate,slot,channel)
        DATA.feed(ch,crate,slot,channel)
        mu = DATA.mean[FMT.format(crate,slot,channel)]
        Test_1.corr_coeff_hist(ch,crate,slot,channel,mu)
        Test_2.corr_coeff_fft(ch,crate,slot,channel)

    Threshold_1 = threshold(Test_1.corr)
    Threshold_2 = threshold(Test_2.corr)

    DATA.channel_Analysis(Test_1,Test_2,Threshold_1,Threshold_2)
    DATA.Results()
    DATA.re_analysis(Test_1,Test_2,Threshold_1,Threshold_2)
    print('Done')	
    DATA.results()	
    DATA.display_stats()

    # If requested, output csv files with results
    if output_csv:

        threshold_file = os.path.join(path, 'threshold_{}.txt'.format(chunk))

        with open(threshold_file, 'w') as hd:
            hd.write('Histogram Test Threshold: {}\n'.format(Threshold_1))
            hd.write('FFT Test Threshold:       {}'.format(Threshold_2))


        first_row = ['Crate','Slot','Channel','FLA-identifier','Mean','Standard_Deviation','Skew','Kurtosis','SNR',
                     'HISTOGRAM_Corr','FFT_Corr','Test_1_Result','Test_2_Result']
        CVS = []
        for crate, slot, channel in x:
            key = FMT.format(crate, slot, channel)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            CVS.append([crate, slot, channel, fla_id,
                        DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                        DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, CVS, path, 'results_{}'.format(chunk))

        bad_nonzero = []
        for crate, slot, channel in DATA.Bad_channel_Normal:
            key = FMT.format(crate, slot, channel)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            bad_nonzero.append([crate, slot, channel, fla_id,
                               DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                               DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, bad_nonzero, path, 'results_bad_nonzero_{}'.format(chunk))

        Doubtful = []
        for crate, slot, channel in DATA.Doubtful_channel:
            key = FMT.format(crate, slot, channel)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            Doubtful.append([crate, slot, channel, fla_id,
                            DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                            DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, Doubtful, path,'results_doubtful_{}'.format(chunk))

        Bad_Zero = []
        for crate, slot, channel in DATA.Bad_channel_Zero:
            key = FMT.format(crate, slot, channel)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            Bad_Zero.append([crate, slot, channel, fla_id,
                            DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                            DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, Bad_Zero, path, 'results_bad_zero_{}'.format(chunk))

        Miss = []
        for crate,slot,channel in DATA.Missing_channel:
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            Miss.append([crate, slot, channel, fla_id,
                        DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                        DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, Miss, path, 'results_missing_{}'.format(chunk))

    # If requested, output plots of bad channels
    if output_plot:

        plot_dir = os.path.join(path, 'plots')
        mkdir(plot_dir)

        save_images(data, Test_1, Test_2, DATA.Bad_channel_Normal, plot_dir, 'bad_nonzero', DATA, align=None)
        save_images(data, Test_1, Test_2, DATA.Doubtful_channel, plot_dir, 'doubtful', DATA, align=None)
        o,p,q = DATA.Good_channel[1]
        ch,t =data.get_adc_input(o,p,q,1)
        T1 = dt.datetime.fromtimestamp(t[-1])
        t1 = dt.datetime.strftime(T1,'%Y-%m-%d %H:%M:%S')
        T0 = dt.datetime.fromtimestamp(t[0])
        t0 = dt.datetime.strftime(T0,'%Y-%m-%d %H:%M:%S')

    # If requested, output .tex file with summary report
    if output_tex:

        file_tex  = latex(os.path.join(path, chunk))
        file_tex.add_file_start()
        file_tex.section('Summary table')
        file_tex.summary_table(len(DATA.Good_channel),len(DATA.Bad_channel_Zero),len(DATA.Bad_channel_Normal),len(DATA.Missing_channel),len(DATA.Doubtful_channel))
        file_tex.add_text('\n'+r'\clearpage'+'\n')

        if len(DATA.Bad_channel_Zero) != 0:

            file_tex.section('Zero Bad Channel Table')
            top_labels = ['S.No.','Crate-Slot-Channel','FLA-ID','Mean','RMS','Kurtosis','Skewness']
            side_labels = np.arange(1,len(DATA.Bad_channel_Zero)+1,1)
            file_tex.format_tabular_from_array(top_labels, side_labels, np.array(array_const(DATA,DATA.Bad_channel_Zero)),'Table of all Zero Bad channels')
            file_tex.add_text('\n'+r'\clearpage'+'\n')


        if len(DATA.Bad_channel_Normal) != 0:
            file_tex.section(r'Non-Zero Bad Channels')
            top_labels = ['S.No.','Crate-Slot-Channel','FLA-ID','Mean','RMS','Kurtosis','Skewness']
            side_labels = np.arange(1,len(DATA.Bad_channel_Normal)+1,1)
            file_tex.format_tabular_from_array(top_labels, side_labels, np.array(array_const(DATA,DATA.Bad_channel_Normal)),'Table of all Non-zero Bad channels')
            file_tex.add_text('\n'+r'\clearpage'+'\n')

            if output_plot:
                xyz = 0
                for i in np.arange(1,len(DATA.Bad_channel_Normal)+1,1):
                    xyz+=1
                    l,m,n = DATA.Bad_channel_Normal[i-1]
                    fig_filename = os.path.join(plot_dir, 'bad_nonzero', FMT.format(l,m,n) + '.png')

                    bulkhead, col, row = adc_to_fla(l,m,n)
                    caption = 'Figure of BAD channel : ${}-{}-{}$ :${}\_{}{}$'.format(l,m,n,bulkhead,col,row)
                    label = file_tex.add_figure(fig_filename, caption, frac_textwidth=0.7, label=None, angle=None)
                    if xyz ==2:
                        file_tex.add_text('\n'+r'\clearpage'+'\n')
                        xyz = 0

                file_tex.add_text('\n'+r'\clearpage'+'\n')


        if len(DATA.Doubtful_channel) != 0:
            file_tex.section('Table of Doubtful channels')
            file_tex.add_text('\n\n' + r'In Test-1 (Histogram-Test) and Test-2(FFT-Test) column of the table shown below, 1.0 means that the channel failed the test and 0.0 means that the channel passed the test.')
            file_tex.add_text('\n\n')
            top_labels = ['S.No.','Crate-Slot-Channel','FLA-ID','Mean','RMS','Kurtosis','Skewness',r'Test-1',r'Test-2']
            side_labels = np.arange(1,len(DATA.Doubtful_channel)+1,1)
            file_tex.format_tabular_from_array(top_labels, side_labels, np.array(array_const(DATA,DATA.Doubtful_channel,wtest=True)),'Table of all Doubtful channels')
            file_tex.add_text('\n'+r'\clearpage'+'\n')

            if output_plot:
                xyz = 0
                for i in np.arange(1,len(DATA.Doubtful_channel)+1,1):
                    xyz+=1
                    l,m,n = DATA.Doubtful_channel[i-1]
                    fig_filename = os.path.join(plot_dir, 'doubtful', FMT.format(l,m,n) + '.png')

                    bulkhead, col, row = adc_to_fla(l,m,n)
                    caption = 'Figure of Doubtful channel : ${}-{}-{}$ :${}\_{}{}$'.format(l,m,n,bulkhead,col,row)
                    label = file_tex.add_figure(fig_filename, caption, frac_textwidth=0.7, label=None, angle=None)
                    if xyz ==2:
                        file_tex.add_text('\n'+r'\clearpage'+'\n')
                        xyz = 0
                file_tex.add_text('\n'+r'\clearpage'+'\n')

        file_tex.add_file_end()
        #file_tex.tex_it()

    # Return results
    return DATA

#_______________________________________________________________________________
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('input_files', help='HDF5 file containing raw ADC data to be processed.', type=str, nargs='+')

    parser.add_argument('--output_dir', '-o', help='Output directory to save results.', type=str, default=None)
    parser.add_argument('--no_csv', dest='output_csv', help='Do not save the results to a .csv file.', action='store_false')
    parser.add_argument('--no_plot', dest='output_plot', help='Do not output plots to a .pdf file.', action='store_false')
    parser.add_argument('--no_tex', dest='output_tex', help='Do not output summary to a .tex file.', action='store_false')
    parser.add_argument('--default_template', dest='compute_template', help='Use the default histogram and FFT template.  ' +
                                             'Otherwise will compute template from the input data files.', action='store_false')
    parser.add_argument('--align', help='to align FFT power spectrum baseline to that of FFT template', action='store_true')

    args = parser.parse_args()

    log.setup_basic_logging('INFO')

    main(args.input_files, output_dir=args.output_dir, output_csv=args.output_csv, output_plot=args.output_plot, output_tex=args.output_tex,
                           compute_template=args.compute_template, align=args.align)

