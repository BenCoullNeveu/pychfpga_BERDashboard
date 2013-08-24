#!/usr/bin/python

"""
util.py module 
 Provides utility functions 
 
#
# History:
# 2011-08-29 : JFC : Created with hex() from chFPGA to eliminate circular imports
"""

import __builtin__
import numpy as np
import logging

def hex(arg):
	""" Wrapper around the built-in hex function to allow hex conversion of arrays """ 
	if isinstance(arg, np.ndarray) or isinstance(arg,list) or isinstance(arg,tuple):
		return '[%s]' % (' '.join(__builtin__.hex(a) for a in arg))
	else:
		return __builtin__.hex(arg)

def reload_modules(module_list):
    """ Reload modules specified in the list."""
    log = logging.getLogger(__name__)
    for module in module_list: 
        log.debug('Reloading module %s' % (module.__name__))
        reload(module)

def reverse_dict(d):
    """ Returns a reverse-lookup dictionnary of 'd'"""
    return {v:k for (k, v) in d.items()}
