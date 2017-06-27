===============================================
:mod:`ch_acq`:  CHIME telescope control package
===============================================

The `ch_acq` package provides a number of Python modules that are used to initialize and operate the CHIME telescope hardware. The main module, :mod:`ch_master`, provides the classes to connect with the various remote processes and hardware that operate the array, configure them into the desired configuration, and runs in the background to provide monitoring information and receiver further commands.

The :mod:`ch_acq` package provides the following main modules, each corresponding to a CHIME subsystem:

.. toctree::
   :maxdepth: 1
   :caption: Main modules

   ch_master
   fpga_array
   kotekan
   raw_acq
   chrx

Additional support modules are also provided:

.. toctree::

   rest

The CHIME telescope subsystems
==============================

The following figure illustrates the main subsystems of the CHIME telescope Front-End.

.. image:: images/chime_processes_interactions.svg
	:width: 100 %


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
