#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
CORR_BLOCK.py module 
 Implements interface to the correlator blocks

 History:
 2012-06-21 : JFC : Created 
"""
import CH_DIST
import ACC


class CORR_BLOCK_channel(object):
    """ Implements interface to one of the correlator"""

    # Antenna processor module addresses
    CH_DIST_MODULE = 0
    CORR_MODULE = 1
    ACC_MODULE = 2

    def __init__(self, parent, instance_number):
        #super(ADC_chip,self).__init__(fpga)
        self.parent = parent # store current ADC number for this instance
        self.instance_number = instance_number # store current correlator number for this instance
        self.fpga = self.parent.fpga
        self.CH_DIST = CH_DIST.CH_DIST_base(self, self.fpga, self.fpga.CORR_PORT[instance_number], self.CH_DIST_MODULE)
        self.ACC = ACC.ACC_base(self, self.fpga, self.fpga.CORR_PORT[instance_number], self.ACC_MODULE)
        

    def init(self):
        """ Inisializes all modules of a correlator block.""" 
        self.CH_DIST.init()
        self.ACC.init()


    def status(self):
        """Displays the status of al the correlator blocks"""
        print '======= CORR_BLOCK[%i] =============' % self.instance_number
        self.CH_DIST.status()
        self.ACC.status()



class CORR_BLOCK_base(object):
    """ Instantiates a container for all correlators blocks"""

    def __init__(self, fpga, verbose=0):
        self.fpga = fpga
        self.verbose = verbose
        # Create an instance of ADC_chip for each chip of the FMC board
        self.CORR_BLOCKS = []
        for i in range(fpga.NUMBER_OF_CORRELATORS):
            self.CORR_BLOCKS.append(CORR_BLOCK_channel(self, i))

    def __getitem__(self, key):
        """    Returns the correlator instance specified by the index"""
        return self.CORR_BLOCKS[key]



    def init(self):
        """ Initializes all correlators"""
        for corr in self.CORR_BLOCKS:
            corr.init()

    def status(self):
        """ Displays the status of all correlators"""
        for corr in self.CORR_BLOCKS:
            corr.status()
