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

Installation
============

``kotekan`` and ``carillon``  can both run ch_master. All the system files and python packages required to run ch_master have been installed as root user and are available to all users. However, if the machine has been rebooted, you will need to tdo the following::

    sudo iptables -A INPUT -p udp -j ACCEPT  # allow FPGA command packet replies and mdns packets in
    sudo iptables -A INPUT -p tcp  --dport 54320:54329 -j ACCEPT # allow the external (housekeeping) computer to query metrics
    sudo ifconfig interface_name mtu 9000 # allow jumbo frames (replace interface name with the proper name: enp0s31f6 on klaxon)


Quick start
===========
Here is how  you can start an experiment with `ch_master` in the configuration ``jfc.erh3``::

   sudo avahi-daemon -k  # kill the avahi daemon. Apparently it restarts by itself when needed...
   ./ch_master.py server jfc.erh3


Here, ``jfc.erh3`` is the config defined in ``config.yaml``, which in this case powers-up crate 3, initialize all boards, and start capturing raw data for 5 minutes. After that, it will stop storing data but will continue to operate the power supply and ch_acq servers (which could be queried and operated by the user with REST commands), and will serve metrics to Prometheus.


Note that if ch_master fails  to connect to raw_acq and power_supply servers (as defined in the config file), it will create temporary servers that will run as long as ch_master is running.

To stop ch_master, just press :kbd:`ctrl-C`.


Main Modules
============

The :mod:`ch_acq` package provides the following main modules, each corresponding to a CHIME subsystem:

.. toctree::
   :maxdepth: 1
   :caption: Main modules

   ch_master
   ps
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
