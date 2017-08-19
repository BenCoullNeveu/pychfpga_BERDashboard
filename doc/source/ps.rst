:mod:`ps` module: Power supply server and client
================================================

.. automodule:: ps

.. autosummary::

	ps.AgilentN5700
	ps.PowerSupplyAsyncRESTServer
	ps.PowerSupplyAsyncRESTClient

Power Supply REST Server
************************

.. autoclass:: ps.PowerSupplyAsyncRESTServer
	:members:



Power Supply REST Client
************************

.. autoclass:: ps.PowerSupplyAsyncRESTClient
	:members:


Power Supply interface object
*****************************
.. autoclass:: ps.PowerSupplyAsyncRESTServer
	:members:


Design
******

`ps` follows the same REST client/server model as the other modules, with a similar command line interface.

The client instantiates a collection of `AgilentN5700` objects, which is a front end to access one power supply. The `AgilentN5700` maintains its own socket connection to the power supply. It uses the `SocketContext` class as a base, which allows it to differ socket connection to the moment where it is needed, and which will attempt to reopen a broken connection if needed. This allows the server to be initialized and run even if units (or the networking) randomly go online and offline, which is sometimes the case during comissioning, testing, or when a container shuts down as a precautionary measure.

In the case of the `AgilentN5700` object, `SocketContext` will open and close the TCP connection for each series of command grouped under a ``with socket()`` block, since the units do not like multiple simulataneous connections.

The `AgilentN5700` and underlying socket access methods are **not** implemented as coroutines. This would probably be very beneficial to the response time if the gode that uses it is designed to take advantage of that. Since we have a small number of supplies, this was not a priority.


Command-line interface
**********************
The first line the python module ``ps.py`` contains a shebang that allows Linux to automatically recognize it as a python script and run it with the python interpreter. So the script can be invoked as ``./ps.py`` as well as `python ps.py`, or within ipython, `run -i ps`.

./ps.py [config] [server_name] [command {args}] {--host hostname} {--port portnumber} {--no-server} {--no-start} {--no-run}

where:
	config: reference to a config file element, in the form [[filename]:]name{.name}. Default filename is config.yaml.
		    For example:
				my_config:some.object
				:some.object
				some.object

			The config element points to the whole run config (the one passed to ch_master). The script will automatically fetch the 'ps' section within it.

			If a config is specified, it is used to obtain the address of the server, unless overriden by the --host and --port options. The config will also be used to initialize the server if no command is specified.


	server_name: name of the specific server config to use. A config can supports multiple power supply servers.
		If server is not specified, and there is only one power supply server defined, then the configuration for this server. Otherwise an error will be raised.

	command: name of a client method to be invoked with the following arguments as parameters. The command is
		identified as the first string that is found amongst the client class method names. Some commands might fail if the server is not initialized. Once the command is executed, the script returns.

		If no command is specified, and a new local server was created, the script will continue to run the server continuously until :kbd:`Ctrl-C` is pressed so the server can do its job (provide metrics, respond to client requests etc) . If no server was created, a warning will be

	args: any remaining arguments are passed to the client method as strings as positional arguments. The client method is responsible for validating and converting the strings to numeric format if needed.

If there is no server runing at the target address specified in the config file or through the --host and --port options, then a server object will be created locally at the same port. If a config file was specified, the server will be initialized with it unless the --no-start flag is specified. Attempt to initialized an already-initialized server will raise an error.

Examples::

	./ps.py jfc.drao #  Connect to an existing server or start a new server if there is none, and initialize it. If a local server was created, run continuously until Ctrl-C.

	./ps.py jfc.drao pss0  # same, buy by specifying a specific power supply server configuration. Needed only if there are multiple servers defined in the config.

	./ps.py status # invked the status command on the server located at the default port on the localhost

	./ps.py jfc.drao status # same, but run the command on the server specified in the only server specified in the config.

	./ps.py power_off ps_crate0

Commands:

	- power_on ps_names | all
	- power_off ps_names | all
	- status

FAQ, troubleshooting and known issues
*************************************

- The N5700/8700 do not seem to handle multiple TCP connections well. Sometimes it works, but sometimes you can establish a conneciton but the Python code fails with a broken pipe or some other errors.

  If you have such problems, make sure that only one server (or an ipython session that has crated a power supply object) is running.


