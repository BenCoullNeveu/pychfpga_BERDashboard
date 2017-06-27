===============================================
:mod:`ch_acq`:  CHIME telescope control package
===============================================

The `ch_acq` package provides the Python modules that are used to initialize and operate the CHIME telescope hardware and make it produce and store correlated data. The data processing pipeline, which is not within the scope of this package, then process the data to generate usable scientific data.

The main module, :mod:`ch_master`, is used to connect with the various remote processes and hardware that operate the array, configure them into the desired configuration, and runs in the background to provide monitoring information and receiver further commands.

.. toctree::
   :maxdepth: 1
   :caption: Table of Contents

   installation
   quick_start
   usage



Main Modules
============

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
   :caption: Support modules

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
