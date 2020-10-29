#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
Shared Variables.py module 
  Used to store variables that persist during the lifetime of a Python session (or until the module is reloaded). 

As with any other modules, this module is loaded by Python when the first import Shared_variables is encountered. 
It is not reloaded on any other occurences of the import statement since it is already in memory.
We use this feature to store variables that represent global hardware resources (like a socket listening to a specific IP address) that cannot be shared by multiple instances of another module.
This allows a module to free the ressource before creating another one, 
even if the reference to the object that originally allocated the ressource is no longer accessible, 
such as when 1) the variable containing the original objest is overridden, 2) the original object had an error after the ressource was allocated andtherefore failed to return a reference to itself.

The variables are lost when the python shell is closed and the pyhton process is terminated, which should also deallocate the allocated ressources.

 History:
    2012-11-09 JFC : Created 
"""

controller_sock = {} # Dictionnary containing the socket pointer for a specific IP address used by a controller