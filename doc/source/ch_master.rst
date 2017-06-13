:mod:`ch_master` module: CHIME telescope array master controller
================================================================

.. automodule:: ch_master


Class summary
-------------

.. autosummary::

   ch_master.ChimeMaster
   ch_master.Metric
   ch_master.DummyChimeMaster
   ch_master.ChimeMasterAsyncRESTServer
   ch_master.ChimeMasterRESTClient





Command-line interface
----------------------

The `ch_master` module can be used a a script to perform interactive operations.

   - start the REST server, with an optional configuration to be pre-loaded
   - start a REST client for use in an  Ipython to operate a server interactively
   - send a command to a already-running local or remote ch_master REST server
   - create a ChimeMaster object for direct use in a ipython session

The configuration file
----------------------

`ChimeMaster` operates and initializes the telescope hardware described in a Python dictionary that is is passed to its :meth:`ChimeMaster.start` method, wither directly or through the REST interface. The configuration ultimately comes from a YAML file that contains multiple array configurations, one of which  is selected and passed th `ChimeMaster`. The default configuration file is found in ``conf.py``.

A configuration describes:
	- Correlator name
	- Logging set-up
	- power supplies
	- F-engine and corner-turn engine configurations (FPGAs)
	- X-engine configuration (kotekan)
	- Raw data acquisition node (raw_acq)
	- Correlated data acquisition nodes (chrx)

Classes
-------


.. .. automethod:: chFPGA_controller.__init__(*see below*)
