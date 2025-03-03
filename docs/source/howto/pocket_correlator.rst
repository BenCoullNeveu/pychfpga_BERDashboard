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
First, create a BitBucket account if you don't have one. Then, contact Jean-Francois Cliche at jfcliche@jfcliche.com to
request access to the repository and other winterland dependencies and include the email for which your
BitBucket account is registered. After getting access, it is necessary to add your ssh key to your BitBucket account.

Create a new ssh key by typing in a terminal:

.. code-block:: bash

    cd
    mkdir .ssh
    ssh-keygen -t ed25519 -b 4096 .ssh/bitbucket_key

Leave the passphrase field empty (press Enter twice). Type:

.. code-block:: bash

    cat .ssh/bitbucket_key_test.pub

and copy the output. Now you need to add the copied key to BitBucket. To do that, on BitBucket go `Gear icon -> Personal
BitBuket settings -> Security -> SSH keys -> Add key`. You can put any label in the respective field. Paste the key copied
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

    mkdir icecorr
    cd icecorr

Inside the directory, create a Python 3.8 virtual environment by running

.. code-block:: bash

    sudo apt install python3.8-venv
    python3.8 -m venv .venv_pychfpga

Now, anytime you are runing the ICE board, you should activate the created environment by running

.. code-block:: bash

    source .venv_pychfpga/bin/activate

from the directory where the environment is located. In our case it is `~/icecorr`.


Installing :bash:`pychfpga`
+++++++++++++++++++++++++++
First, download the software by running the following in terminal:

.. code-block:: bash

    git clone git@bitbucket.org:winterlandcosmology/pychfpga.git -b deploy

If you had issues with this step, you probably don't have access to the repository. Check if you properly set up your
BitBucket key an if you have permissions. If the command succeded, go to the cloned repo:

.. code-block:: bash

    cd pychfpga

Make sure the large files were cloned too:

.. code-block:: bash

    sudo apt install git-lfs
    git-lfs fetch


Now you need to find the latest version tested for a single board correlator. To do it, see the tags in the
:bash:`pychfpga` repository. The correct tag format for a single ICE board correlator would be
:code:`x.y.z-ice+co`, where :code:`x`, :code:`y` and :code:`z` are version numbers. To list all relevant tags run:

.. code-block:: bash

    git tag --list '*.*.*-ice+co'

Then choose the latest available version. At the moment of writing, this version is :code:`1.3.1-ice+co`. Now you need
to switch to the selected version of the code by running the following command. You need to replace the
:code:`[selected_tag]` with the version you selected in previous step.

.. code-block:: bash

    git checkout [selected_tag]

While doing checkout, git may download additional files.

Now, it's time to install the software. While in :bash:`pychfpga` directory, run

.. code-block:: bash

    pip install -e .

If you had problems during installation - check if you're using Python 3.8 and if you have access to all the winterland
dependencies needed to install the software. For dependency access requests contact Jean-Francois Cliche
at jfcliche@jfcliche.com.

After installation, you can run an :bash:`fpga_master` command to see if installation is complete
(it will throw an error for now).


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

