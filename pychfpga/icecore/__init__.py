""" Provide direct access to the Python modules located in the /python subfolder

We redefine the __path__ variable of this module so the user can access the
icecore Python modules without having to specify the whole path. For example, if the user named the icecore folder 'myicecore', we can do:

    >>> import myicecore.iceboard

instead of

    >>> import myicecore.python.iceboard
"""
__path__= [__path__[0] + '/python'] # __path__[0] is the name given by the user to this folder.
#__path__= ['icecore/python'] # __path__[0] is the name given by the user to this folder.

