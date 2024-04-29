Pocket correlator guide
=======================


.. role:: bash(code)
   :language: bash

.. role:: python(code)
   :language: python

This guide includes all essential info and tips about running a single ICE board in a correlator mode.

Authors:
    Vadym Bidula, Kit Gerodias


Board overview
-----------------
TODO

Hardware setup
--------------
.. figure:: ../images/pocket_corr/example1.jpg
    :width: 75%
    :alt: example1
    :align: center

    Example of the ICE board setup

.. figure:: ../images/pocket_corr/example2.jpg
    :width: 60%
    :alt: example2
    :align: center

    Example of the ethernet wiring. You'll need at least four cables and a gigabit switch

.. figure:: ../images/pocket_corr/example3.jpg
    :width: 60%
    :alt: example3
    :align: center

    Connection ethernet cables to the ICE board

.. figure:: ../images/pocket_corr/example4.jpg
    :width: 60%
    :alt: example4
    :align: center

    Front of the ICE board


Software installation
---------------------

:bash:`pychfpga` is developed and tested on Ubuntu OS, so it is recommended to run this on Ubuntu. This guide was tested
on Ubuntu 22.04.

Getting access to :bash:`pychfpga`
++++++++++++++++++++++++++++++++++
First, create a BitBucket account if you don't have one. Then, contact jfcliche@jfcliche.com to request
access to the :bash:`pychfpga` repository and other winterland dependencies and include the email for which your
BitBucket account is registered. After getting access, it is necessary to add your ssh key to your BitBucket account.

Create a new ssh key by typing in a terminal:

.. code-block:: bash

    mkdir .ssh
    ssh-keygen -t ed25519 -b 4096 .ssh/bitbucket_key

Leave the passphrase field empty (press Enter twice). Type:

.. code-block:: bash

    cat .ssh/bitbucket_key_test.pub

and copy the output. Now you need to add the copied key to BitBucket. To do that, on BitBucket go `Gear icon -> Personal
BitBuket settings -> Security -> SSH keys -> Add key`. You can label the key whatever you prefer. Paste the key copied
from the terminal in the "Key" field.

Finally, add a created key to the ssh client. Run in terminal window:

.. code-block:: bash

    eval `ssh-agent`
    ssh-add .ssh/bitbucket_key

Creating an environment
+++++++++++++++++++++++

The recommended version of Python to use is `3.8`. You can install the older version of Python by
typing in the terminal:

.. code-block:: bash

    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt update
    sudo apt install python3.8

To check that the Python is properly installed run. This should output the installed Python version:

.. code-block:: bash

    python3.8 --version

It is recommended to create a separate directory for the :bash:`pychfpga` environment, for example:

.. code-block:: bash

    mkdir iceboard
    cd iceboard

Inside the directory, create a Python 3.8 virtual environment by running

.. code-block:: bash

    sudo apt install python3.8-venv
    python3.8 -m venv venv_pychfpga

Now, anytime you are runing the ICE board, you should activate the created environment by running

.. code-block:: bash

    source venv_pychfpga/bin/activate

from the directory where the environment is located. In our case it is `~/iceboard`.


Installing :bash:`pychfpga`
+++++++++++++++++++++++++++

To find the latest stale version of the software, see the tags in the :bash:`pychfpga` repository or contact
jfcliche@jfcliche.com. At the moment of writing this tutorial, the latest (temporary) confirmed version is defined by
the commit :bash:`13e33984d8e3acc4eb36b5bbfa960ac1b4aabe9f`. To download it run in terminal:

.. code-block:: bash

    git clone git@bitbucket.org:winterlandcosmology/pychfpga.git -b vb/stable_corr

Go to the cloned repo

.. code-block:: bash

    cd pychfpga

Make sure the large files were cloned too

.. code-block:: bash

    sudo apt install git-lfs
    git-lfs fetch

..
    Finally, checkout to the mentioned commit

    .. code-block:: bash

        git checkout 13e33984d8e3acc4eb36b5bbfa960ac1b4aabe9f

    While doing checkout, the git should download additional files for about 54 MB.

Now, it's time to install the software. While in :bash:`pychfpga` directory, run

.. code-block:: bash

    pip install -e .

You can then run an :bash:`fpga_master` command to see if installation is complete (it will throw an error for now).


Correlator configuration
------------------------
TODO


Running the correlator
----------------------
TODO
To check network connection
	~$ ifconfig
	Make sure that the connection you have is set to mtu 9000
	For linux:
Ethernet Connection >> Edit Connections >> Ethernet >> name_of_the_wired_connection >> Ethernet >> MTU
	set MTU 9000

Then, do
~$ sudo ifconfig name_of_connection mtu 9000

Do ifconfig to check


Reading the data
----------------
TODO

