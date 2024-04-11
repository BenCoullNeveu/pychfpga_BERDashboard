.. pychfpga documentation master file, created by
   sphinx-quickstart on Wed Jan 20 12:29:25 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


.. role:: ul
    :class: underline

Welcome to pychfpga's documentation!
====================================

The ``pychfpga`` package is the Python framework that is used to operate the FPGA-based F-engine hardware, corner-turn and optional firmware-basd X-engine that is used for a number of big and small interferometer radio telescopes, including the Canadian Hydrogen Intensity Mapping Experiment (CHIME).

.. toctree::
   :maxdepth: 1

   installation
   howto/setup_python
   howto/takeData
   howto
   quick_start

.. toctree::
   :maxdepth: 1
   :caption: API Reference
   :hidden:

   _autosummaries/pychfpga

CHIME-specific modules:

.. toctree::
   :maxdepth: 1
   :caption: CHIME-specific modules

   chime/networking_configuration


External modules

.. toctree::
   :maxdepth: 1
   :caption: External modules

   external_packages/metrics
   external_packages/rest


.. include:: ../../README

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`



