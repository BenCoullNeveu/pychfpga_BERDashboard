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

import matplotlib
if os.name == 'posix' and "DISPLAY" not in os.environ: matplotlib.use('Agg')
import matplotlib.pyplot as plt

from scipy import signal
from scipy import stats
from scipy.stats import kurtosis
from scipy.stats import skew

import log
logger = log.get_logger(__name__)

SCALE_FACTOR = (1.0 / 100.0) * (0.500 / 256.0)**2 * 1000.0       # Converts from LSB^2 --> mW

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
def threshold_otsu(image, nbins=256):
    """Return threshold value based on Otsu's method.

    Parameters
    ----------
    image : (N, M) ndarray
        Grayscale input image.
    nbins : int, optional
        Number of bins used to calculate histogram. This value is ignored for
        integer arrays.

    Returns
    -------
    threshold : float
        Upper threshold value. All pixels with an intensity higher than
        this value are assumed to be foreground.

    Raises
    ------
    ValueError
         If `image` only contains a single grayscale value.

    References
    ----------
    .. [1] Wikipedia, http://en.wikipedia.org/wiki/Otsu's_Method

    Notes
    -----
    The input image must be grayscale.
    Adapted from skimage.filters.threshold_otsu.
    """
    if len(image.shape) > 2 and image.shape[-1] in (3, 4):
        msg = "threshold_otsu is expected to work correctly only for " \
              "grayscale images; image shape {0} looks like an RGB image"
        warn(msg.format(image.shape))

    # Check if the image is multi-colored or not
    if image.min() == image.max():
        raise ValueError("threshold_otsu is expected to work with images "
                         "having more than one color. The input image seems "
                         "to have just one color {0}.".format(image.min()))

    hist, bin_edges = np.histogram(image.ravel(), bins=nbins)
    bin_centers = bin_edges[0:-1] + 0.5 * np.diff(bin_edges)
    hist = hist.astype(float)

    # class probabilities for all possible thresholds
    weight1 = np.cumsum(hist)
    weight2 = np.cumsum(hist[::-1])[::-1]
    # class means for all possible thresholds
    mean1 = np.cumsum(hist * bin_centers) / weight1
    mean2 = (np.cumsum((hist * bin_centers)[::-1]) / weight2[::-1])[::-1]

    # Clip ends to align class 1 and class 2 variables:
    # The last value of `weight1`/`mean1` should pair with zero values in
    # `weight2`/`mean2`, which do not exist.
    variance12 = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2

    idx = np.argmax(variance12)
    threshold = bin_centers[:-1][idx]
    return threshold

def threshold(dictionary):

    meas = np.array(dictionary.values())

    init_th = threshold_otsu(meas)

    q75, q25 = np.percentile(meas[meas > init_th], [75, 25])

    final_th = q25 - 3.0 * (q75 - q25)

    return final_th

#------------------------------------------------------------------------------
#-------------------Saving Images of the Bad channels--------------------------
def save_images(obj, obj1, obj2, inputs, path, var_name, data, align=False):
    k = 0
    plot_dir = os.path.join(path, var_name)
    mkdir(plot_dir)
    for key in inputs:
        I, J, K = parse_serial_number(key)
        HIST = []
        k = k+1
        ch,t = obj.get_adc_input(I, J, K, 0)
        mu = data.mean[key]
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
        plt.savefig(os.path.join(plot_dir,  key + '.png'), dpi=400)
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

# Implementation that does not read entire dataset into memory
def create_templates_from_file(filename, obj1, obj2):

    hd = h5py.File(filename[0],'r')
    data = hd['timestream']

    index, klist = [], []

    for ind, frame in enumerate(data):

        rms = np.std(frame)

        if (rms >= 9) and (rms <= 20):

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
            y = np.array(data[ind], dtype=np.float32)
            y -= np.mean(y)

            hist += np.histogram(y, bins=obj1._nbins, range=obj1._range)[0]
            spec += np.abs(np.fft.rfft(y * obj2._window)[0:obj2._nfreq])**2
            count += 1

    hist /= float(count)
    spec /= float(count)

    obj1.Temp_Hist = hist
    obj2.Temp_fft = 2.0 * SCALE_FACTOR * obj2._window_norm * spec / (2.0 * obj2._nfreq)**2

    hd.close()


def create_templates_from_data(data, obj1, obj2):

    index, klist = [], []

    for key, stream in data.iteritems():

        for ind, (timestamp, frame) in enumerate(stream):

            rms = np.std(frame)

            if (rms >= 9) and (rms <= 20):

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
            y = np.array(data[ind[0]][ind[1]][1], dtype=np.float32)
            y -= np.mean(y)

            hist += np.histogram(y, bins=obj1._nbins, range=obj1._range)[0]
            spec += np.abs(np.fft.rfft(y * obj2._window)[0:obj2._nfreq])**2
            count += 1

    hist /= float(count)
    spec /= float(count)

    obj1.Temp_Hist = hist
    obj2.Temp_fft = 2.0 * SCALE_FACTOR * obj2._window_norm * spec / (2.0 * obj2._nfreq)**2


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
    _beta = 2

    def __init__(self):
        self.spectrum = dict()
        self.corr = dict()

        self._window = np.kaiser(2 * self._nfreq, self._beta)
        self._window_norm = float(self._window.size) / np.sum(self._window**2)

    def load_FFT_Template(self):
        dirname = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
        Temp_fft = []
        with open(os.path.join(dirname, 'template_spectrum.txt'), 'r') as f:
            for line in f:
                Temp_fft.append(float(line.rstrip()))
        self.Temp_fft = np.array(Temp_fft)

    def corr_coeff_fft(self, data, crate, slot, channel, mu):
        if len(data) == 0:
            self.spectrum[FMT.format(crate,slot,channel)] = None
            self.corr[FMT.format(crate,slot,channel)] = None

        else:
            windowed_data = (np.array(data, dtype=np.float32) - mu) * self._window[np.newaxis, :]
            spec = self._window_norm * np.median(np.abs(np.fft.rfft(windowed_data, axis=-1))**2, axis=0)[0:self._nfreq]

            # Save in units of mW at ADC input
            self.spectrum[FMT.format(crate,slot,channel)] = 2.0 * SCALE_FACTOR * spec / (2.0 * self._nfreq)**2

            # Align continuum with the template
            spec = spec * (np.median(self.Temp_fft) / np.median(spec))  #This makes continuum part aligned

            specm = np.power( signal.medfilt(spec, kernel_size=7), 0.2)[1:]
            tempm = np.power(self.Temp_fft, 0.2)[1:]
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
                hist[ff, :] = np.histogram(np.array(frame, dtype=np.float32) - mu, bins=self._nbins, range=self._range)[0]

            hist = np.median(hist, axis=0)
            self.histogram[FMT.format(crate,slot,channel)] = hist

            corr = np.correlate(hist, self.Temp_Hist)[0] / (np.linalg.norm(hist) * np.linalg.norm(self.Temp_Hist))
            self.corr[FMT.format(crate,slot,channel)] = corr

#-------------------------------------------------------------------------------
#-----------------------Data storing class--------------------------------------
class DataAnalysis(object):
    def __init__(self,obj1,obj2):

        self.missing_channel = []
        self.initial_good_channel = []
        self.initial_bad_channel_zero = []
        self.initial_bad_channel_normal = []
        self.initial_doubtful_channel = []
        self.good_channel = []
        self.bad_channel_normal = []
        self.bad_channel_zero = []
        self.doubtful_channel = []

        self.nframe = dict()
        self.mean = dict()
        self.kurtosis = dict()
        self.skew = dict()
        self.rms = dict()
        self.snr = dict()
        self.weight = dict()
        self.classification = dict()

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

    def analyze_adc_input(self, ch, crate, slot, channel):

        key = FMT.format(crate, slot, channel)
        if len(ch) == 0:
            self.missing_channel.append(key)
            self.nframe[key] = 0
            self.mean[key] = None
            self.kurtosis[key] = None
            self.skew[key] = None
            self.rms[key] = None
            self.snr[key] = None
            self.weight[key] = None
            self.classification[key] = None
        else:
            self.nframe[key] = len(ch)
            self.mean[key] = np.mean(np.array([np.mean(x) for x in ch]))
            self.kurtosis[key] = np.mean(np.array([kurtosis(x) for x in ch]))
            self.skew[key] = np.mean(np.array([skew(x) for x in ch]))
            self.rms[key] = np.mean((np.array([np.std(x) for x in ch])))
            power = [(np.std(ch[i]))**2 for i in range(len(ch))]
            power_sig = np.std(power)
            power_mu = np.mean(power)
            self.snr[key] = (power_mu / power_sig) if power_sig > 0.0 else 0.0

    def make_initial_classification(self, obj1, obj2, Threshold_1, Threshold_2):

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

    def compute_weight(self, obj1, threshold, w, q1, q2, q3):  #w=0.5 for test-2, w=1.5 for test-1
        rt = 1
        if w == 1.5:
            rt = 2
        Weight = dict()
        if q1 > 0: # the cutoff is either mean or 0 which ever is smaller.
            s = 0
        else:
            s = q1
        for i, j in obj1.corr.iteritems():
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

    def make_secondary_classification(self, obj1, obj2, Threshold_1, Threshold_2):

        q11, q12, q13 = self.find_divisions(obj1, Threshold_1)
        q21, q22, q23 = self.find_divisions(obj2, Threshold_2)

        wt1 = self.compute_weight(obj1, Threshold_1, 1.5, q11, q12, q13)
        wt2 = self.compute_weight(obj2, Threshold_2, 0.5, q21, q22, q23)

        for key in wt1.keys():

            if (wt1[key] == 0) or (wt2[key] == 0):
                weight = 0.0
            else:
                weight = wt1[key] + wt2[key]

            if weight > 14.0:
                self.classification[key] = 1.0
                self.good_channel.append(key)

            elif (weight > 6.0) and (weight < 14.0):
                self.classification[key] = 0.5
                self.doubtful_channel.append(key)

            elif weight < 6.0:
                self.classification[key] = 0.0

                if self.rms[key] < 1.0:
                    self.bad_channel_zero.append(key)
                else:
                    self.bad_channel_normal.append(key)

            self.weight[key] = weight

    def find_divisions(self, obj, threshold):

        data = [obj.corr[key] - threshold for key in self.initial_doubtful_channel]

        q75, q50, q25 = np.percentile(data, [75, 50, 25])
        k_lower = q25 - 1.5*(q75 - q25)

        return q50, q25, k_lower

    def get_initial_results(self):

        for key in self.histogram_fail.keys():

            if not self.histogram_fail[key] and not self.spectrum_fail[key]:
                self.initial_good_channel.append(key)

            elif self.histogram_fail[key] and self.spectrum_fail[key]:
                if self.rms[key] < 1:
                    self.initial_bad_channel_zero.append(key)
                else:
                    self.initial_bad_channel_normal.append(key)

            else:
                self.initial_doubtful_channel.append(key)

    def display_stats(self):
        logger.info('Total channels in the chunk : {}'.format(len(self.bad_channel_normal) + len(self.missing_channel) +
                                                              len(self.bad_channel_zero) + len(self.good_channel) +
                                                              len(self.doubtful_channel)))
        logger.info('Good channels : {}'.format(len(self.good_channel)))
        logger.info('Missing Channels : {}'.format(len(self.missing_channel)))
        logger.info('Bad channels with near-zero RMS : {}'.format(len(self.bad_channel_zero)))
        logger.info('Bad channels with non-zero RMS : {}'.format(len(self.bad_channel_normal)))
        logger.info('Doubtful channels : {}'.format(len(self.doubtful_channel)))
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

def parse_serial_number(key):

    if key is None:
        return key
    else:
        return int(key[3:5]), int(key[5:7]), int(key[7:9])

def array_const(obj, channels, wtest=False):
    K = []
    for key in channels:

        crate, slot, inp = parse_serial_number(key)
        bulkhead, col, row = adc_to_fla(crate, slot, inp)

        K1 = ['${}-{}-{}$'.format(crate, slot, inp), r'${}\_{}{}$'.format(bulkhead, col, row),
              round(obj.mean[key], 3), round(obj.rms[key], 3), round(obj.kurtosis[key], 3), round(obj.skew[key], 3)]

        if wtest:
            K1 += [round(obj.histogram_fail[key], 3), round(obj.spectrum_fail[key], 3)]

        K.append(K1)

    return K
#-------------------------------------------------------------------------------
#-----------------------Main function-------------------------------------------
def main(input_files, output_dir=None, output_csv=True, output_plot=True, output_tex=True, compute_template=True, align=False):
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
        DATA.analyze_adc_input(ch,crate,slot,channel)
        mu = DATA.mean[FMT.format(crate,slot,channel)]
        Test_1.corr_coeff_hist(ch,crate,slot,channel,mu)
        Test_2.corr_coeff_fft(ch,crate,slot,channel,mu)

    Threshold_1 = threshold(Test_1.corr)
    Threshold_2 = threshold(Test_2.corr)

    DATA.make_initial_classification(Test_1, Test_2, Threshold_1, Threshold_2)
    DATA.get_initial_results()
    DATA.make_secondary_classification(Test_1, Test_2, Threshold_1, Threshold_2)

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
        for key in DATA.bad_channel_normal:
            crate, slot, channel = parse_serial_number(key)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            bad_nonzero.append([crate, slot, channel, fla_id,
                               DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                               DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, bad_nonzero, path, 'results_bad_nonzero_{}'.format(chunk))

        Doubtful = []
        for key in DATA.doubtful_channel:
            crate, slot, channel = parse_serial_number(key)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            Doubtful.append([crate, slot, channel, fla_id,
                            DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                            DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, Doubtful, path,'results_doubtful_{}'.format(chunk))

        Bad_Zero = []
        for key in DATA.bad_channel_zero:
            crate, slot, channel = parse_serial_number(key)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            Bad_Zero.append([crate, slot, channel, fla_id,
                            DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                            DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, Bad_Zero, path, 'results_bad_zero_{}'.format(chunk))

        Miss = []
        for key in DATA.missing_channel:
            crate, slot, channel = parse_serial_number(key)
            fla_id = '{}_{}{}'.format(*adc_to_fla(crate, slot, channel))
            Miss.append([crate, slot, channel, fla_id,
                        DATA.mean[key], DATA.rms[key], DATA.skew[key], DATA.kurtosis[key], DATA.snr[key],
                        DATA.histogram_corr_coeff[key], DATA.spectrum_corr_coeff[key], DATA.histogram_fail[key], DATA.spectrum_fail[key]])
        csv_file(first_row, Miss, path, 'results_missing_{}'.format(chunk))

    # If requested, output plots of bad channels
    if output_plot:

        plot_dir = os.path.join(path, 'plots')
        mkdir(plot_dir)

        save_images(data, Test_1, Test_2, DATA.bad_channel_normal, plot_dir, 'bad_nonzero', DATA, align=align)
        save_images(data, Test_1, Test_2, DATA.doubtful_channel, plot_dir, 'doubtful', DATA, align=align)

    # If requested, output .tex file with summary report
    if output_tex:

        file_tex  = latex(os.path.join(path, chunk))
        file_tex.add_file_start()
        file_tex.section('Summary table')
        file_tex.summary_table(len(DATA.good_channel), len(DATA.bad_channel_zero), len(DATA.bad_channel_normal),
                               len(DATA.missing_channel), len(DATA.doubtful_channel))
        file_tex.add_text('\n'+r'\clearpage'+'\n')

        if len(DATA.bad_channel_zero) != 0:

            file_tex.section('Zero Bad Channel Table')
            top_labels = ['S.No.','Crate-Slot-Channel','FLA-ID','Mean','RMS','Kurtosis','Skewness']
            side_labels = np.arange(1, len(DATA.bad_channel_zero)+1, 1)
            file_tex.format_tabular_from_array(top_labels, side_labels, np.array(array_const(DATA, DATA.bad_channel_zero)), 'Table of all Zero Bad channels')
            file_tex.add_text('\n'+r'\clearpage'+'\n')


        if len(DATA.bad_channel_normal) != 0:
            file_tex.section(r'Non-Zero Bad Channels')
            top_labels = ['S.No.','Crate-Slot-Channel','FLA-ID','Mean','RMS','Kurtosis','Skewness']
            side_labels = np.arange(1, len(DATA.bad_channel_normal)+1, 1)
            file_tex.format_tabular_from_array(top_labels, side_labels, np.array(array_const(DATA, DATA.bad_channel_normal)), 'Table of all Non-zero Bad channels')
            file_tex.add_text('\n'+r'\clearpage'+'\n')

            if output_plot:
                xyz = 0
                for i in np.arange(1, len(DATA.bad_channel_normal)+1, 1):
                    xyz += 1
                    key = DATA.bad_channel_normal[i-1]
                    fig_filename = os.path.join(plot_dir, 'bad_nonzero', key + '.png')

                    crate, slot, channel = parse_serial_number(key)
                    bulkhead, col, row = adc_to_fla(crate, slot, channel)
                    caption = 'Figure of BAD channel : ${}-{}-{}$ :${}\_{}{}$'.format(crate, slot, channel, bulkhead, col, row)
                    label = file_tex.add_figure(fig_filename, caption, frac_textwidth=0.7, label=None, angle=None)
                    if xyz == 2:
                        file_tex.add_text('\n'+r'\clearpage'+'\n')
                        xyz = 0

                file_tex.add_text('\n'+r'\clearpage'+'\n')


        if len(DATA.doubtful_channel) != 0:
            file_tex.section('Table of Doubtful channels')
            file_tex.add_text('\n\n' + r'In Test-1 (Histogram-Test) and Test-2(FFT-Test) column of the table shown below, 1.0 means that the channel failed the test and 0.0 means that the channel passed the test.')
            file_tex.add_text('\n\n')
            top_labels = ['S.No.','Crate-Slot-Channel','FLA-ID','Mean','RMS','Kurtosis','Skewness',r'Test-1',r'Test-2']
            side_labels = np.arange(1, len(DATA.doubtful_channel)+1, 1)
            file_tex.format_tabular_from_array(top_labels, side_labels, np.array(array_const(DATA, DATA.doubtful_channel, wtest=True)), 'Table of all Doubtful channels')
            file_tex.add_text('\n'+r'\clearpage'+'\n')

            if output_plot:
                xyz = 0
                for i in np.arange(1, len(DATA.doubtful_channel)+1, 1):
                    xyz += 1
                    key = DATA.doubtful_channel[i-1]
                    fig_filename = os.path.join(plot_dir, 'doubtful', key + '.png')

                    crate, slot, channel = parse_serial_number(key)
                    bulkhead, col, row = adc_to_fla(crate, slot, channel)
                    caption = 'Figure of Doubtful channel : ${}-{}-{}$ :${}\_{}{}$'.format(crate, slot, channel, bulkhead, col, row)
                    label = file_tex.add_figure(fig_filename, caption, frac_textwidth=0.7, label=None, angle=None)
                    if xyz == 2:
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
    parser.add_argument('--align', help='Align the FFT power spectrum baseline to that of the FFT template', action='store_true')

    args = parser.parse_args()

    log.setup_basic_logging('INFO')

    main(args.input_files, output_dir=args.output_dir, output_csv=args.output_csv, output_plot=args.output_plot, output_tex=args.output_tex,
                           compute_template=args.compute_template, align=args.align)

