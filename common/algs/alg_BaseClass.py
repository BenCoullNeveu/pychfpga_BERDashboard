#!/usr/bin/env python

'''
BaseClass for algs running on the board
'''

class alg_BaseClass:
    '''
     Base class for all  alg operations on chFPGA
    '''
    def __init__(self,fpga_ctrl, fpga_recv):
        '''
            The baseclass has one data member, called data. 
            It is meant to hold the results of executing the algorithm once.
            you must call alg_BaseClass.__init__(self) from your derived __init__
            method.
        '''
        self.fpga_ctrl = fpga_ctrl
        self.fpga_recv = fpga_recv

        
    def execute(self, channel ): 
        ''' This method must be declared in all derived classes 
        the derived class execute will override this one '''
        pass
