#!/usr/bin/python

"""
util.py module 
 Provides utility functions 
 
#
# History:
# 2011-08-29 : JFC : Chreated with hex() from chFPGA to eliminate circular imports
"""

import __builtin__


def hex(arg):
	""" Wrapper around the built-in hex function to allow hex conversion of arrays """ 
	if isinstance(arg, np.ndarray):
		return '[%s]' % (' '.join(__builtin__.hex(a) for a in arg))
	else:
		return __builtin__.hex(arg)
