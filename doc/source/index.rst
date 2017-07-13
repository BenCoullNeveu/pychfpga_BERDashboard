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

``kotekan`` and ``carillon``  can both run ch_master. All the system files required to run ch_master have been installed as root user and are available to all. Python, however, is run in a user-specific virtual environment that currently needs to be created and configured by each user. We might create a global install at some point, or use a common user to run ch_master, once ch_master gets out of development phase.

In a nutshell, to create the Python environment::

    virtualenv ~/py275  # Create the virtual environemnt with the current version of Python (2.7.5)
    source ~/py275/bin/activate # Activate the environment
    pip install ipython numpy matplotlib sqlalchemy pyyaml tornado lxml h5py  # install requires packages
    pip install nose docutils futures requests netifaces # more packages
    pip install -e git+https://github.com/Eichhoernchen/pybonjour.git#egg=pybonjour  # pybonjour is not in pip, so we get the resource directly


Also ``kotekan`` and ``carillon`` networking is not configured properly at power up. If the machine has been rebooted, you will need::

    sudo iptables -I INPUT -p udp -j ACCEPT  # allow FPGA command packets and mdns packats in
    sudo iptables -A INPUT 1 -p tcp  --dport 54321 -j ACCEPT # allow the external (housekeeping) computer to query metrics
    sudo ifconfig interface_name mtu 9000 # allow jumbo frames (replace interface name with the proper name)


Quick start
===========
Here is how  you can start an experiment with `ch_master`:

First, activate your Python virtual environment::

    cd ~/git/ch_acq
    source ~/py275/bin/activate

Second, you will often need to restart avahi because it stops refreshing every few minutes on Centos 7::

   sudo avahi-daemon -k  # kill the avahi daemon. Apparently it restarts by itself when needed...

Finally, start ch_master with the proper config::

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
