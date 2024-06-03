ICE System Quality Control Handbook
=======================


.. role:: bash(code)
   :language: bash

.. role:: python(code)
   :language: python

This handbook is intended as a companion book, providing dia-
grams for easier identification of the steps in the QC process. Please
follow the instructions as written on screen, and refer to these pages
as needed

Authors:
    JF Cliche, Antoine Parise


MGADC08 - CHIME Mezzanine
-----------------
TODO

MGK7MB - ICE Motherboard
--------------
.. figure:: ../images/iceqc/IceBoardPhotos/main_view.jpg
    :width: 75%
    :alt: Motherboard
    :align: center

    Motherboard 

Inspection Test
^^^^^^^^^^^^^^^
**Step 1:** Is the FPGA heatsink securely attached?
**Step 2:** Are the FPGA heatsink pins cut near the stiffener?


.. figure:: ../images/iceqc/IceBoardPhotos/InspTest/inspection_step12.jpeg
    :width: 60%
    :alt: example
    :align: center

    Points of interest for Steps 1 and 2

**Step 3:** Is the board stiffener installed, and the board reasonably flat?
**Step 4:** Are the PLL heatsinks attached?
**Step 5:** Does the arm shield fence look straight?

.. figure:: ../images/iceqc/IceBoardPhotos/InspTest/inspection_step345.jpeg
    :width: 60%
    :alt: example
    :align: center

    Points of interest for Steps 3,4 and 5


**Step 6:** Are the dipswitches set correctly?
**Step 7:** Are the jumpers set correctly?

.. figure:: ../images/iceqc/IceBoardPhotos/InspTest/inspection_step67.jpeg
    :width: 60%
    :alt: example
    :align: center

    Front of the ICE board

**Step 8:** Are the 90 pin Molex backplane connectors screwed down? (back-
side)
**Step 9:** Are the QSFP and SFP connectors soldered in place? (backside)
**Step 10:** Do all the buck converters have the additional hand-soldered ca-
pacitor? (backside)

.. figure:: ../images/iceqc/IceBoardPhotos/InspTest/inspection_step8910.jpeg
    :width: 60%
    :alt: example
    :align: center


**Step 11:** Do all the FMC power switches look well soldered?
**Step 12:** Is the blue patch wire in place and secured?

.. figure:: ../images/iceqc/IceBoardPhotos/InspTest/inspection_step1112.jpeg
    :width: 60%
    :alt: example
    :align: center


Impedance test
^^^^^^^^^^^^^^^^
Before taking measurements, make sure that the board setup is as shown in
figure 16.

.. figure:: ../images/iceqc/IceBoardPhotos/ImpTest/CroppedIceboard.jpeg
    :width: 60%
    :alt: example
    :align: center

    Figure 16: Iceboard with ground connection and one-slot backplane


Apply the red test probe to the test points in the following order: +V
supply followed by the buck converters in a counter clockwise order - see
figure 17. Refer to probe location 10 in the diagram for instructions on
where to apply the test probe for all buck converters.

.. figure:: ../images/iceqc/IceBoardPhotos/ImpTest/ImpTest/Impedance_test-points.jpeg
    :width: 60%
    :alt: example
    :align: center

    Figure 17: Impedance measurement test locations



Power test
^^^^^^^^^^^^^^^^^
Connect the power cable to the backplane as shown in figure 18.

.. figure:: ../images/iceqc/IceBoardPhotos/PowerUpTest/power_cable.jpegg
    :width: 60%
    :alt: example
    :align: center

    Figure 18: Power cable attached to one-slot backplane with motherboard

Check that all 9 power LEDs are turned on as shown in figure 19.

.. figure:: ../images/iceqc/IceBoardPhotos/PowerUpTest/power_leds.jpeg
    :width: 60%
    :alt: example
    :align: center

    Figure 19: Motherboards 9 power LEDS

PLL programming
^^^^^^^^^^^^^^^^^^
Connect the PLL programming cable to the board, making sure that the
black marked side faces the SFP connectors - see figure 20.

.. figure:: ../images/iceqc/IceBoardPhotos/PLLTest/PLLDongle.jpeg
    :width: 60%
    :alt: example
    :align: center

    Figure 20: PLL Programming dongle

Check that both PLL lock lights are turned on (green & yellow on the right) see figure 21

.. figure:: ../images/iceqc/IceBoardPhotos/PLLTest/PLLLock.jpeg
    :width: 60%
    :alt: example
    :align: center

    Figure 21: PLL Lock LEDs



Memory test
^^^^^^^^^^^^^^^





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

