Installation
============


Requirements
------------
   * system files
       * git (>1.8.2 for git-lfs)
       * git-lfs (needed to pull fpga firmware)
       * Python 2.7.X (Python 3 **not** supported)
       * python pip
       * python-devel (needed on some system to install ipython, matplotlib)
       * tkinter (needed on Centos for matplotlib)
       * mdns/avahi/bonjour services with development libraries

   * Python packages:

       - virtualenv (pip)
       - ipython
       - numpy
       - matplotlib
       - sqlalchemy
       - pyyaml
       - tornado
       - lxml
       - h5py
       - nose
       - docutils
       - futures
       - requests
       - netifaces
       - pybonjour (requires avahi/mdns/bonjour system files to be installed)::

            wget https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/pybonjour/pybonjour-1.1.1.tar.gz
            tar zxf pybonjour-1.1.1.tar.gz
            cd pybonjour-1.1.1
            python setup.py install


Centos 7 installation
---------------------

OS version check
****************
::

    cat /etc/*-release


Git
***

Check the Git and git-lfs version with::

    git --version
    git-lfs --version

If git is lower than 1.8.2, we need to update it for git-lfs. Git and git-lfs are installed following the instructions from https://github.com/git-lfs/git-lfs/wiki/Installation::

    sudo yum install epel-release
    sudo yum install git # if needed
    curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.rpm.sh | sudo bash
    sudo yum install git-lfs
    git lfs version


Activate the git-lfs install (needs to be done only once by this specific user)::

    git lfs install


Python
******

Check version::

    python --version

Hopefully this will will be one of the 2.7 releases. Any one should do (we operated successfully with 2.7.5 - 2.7.11). We cannot operate with python 3. It is not trivial to install another python version: Centos uses it for its system and is very picky on which verison is installed, and it is hard to get and compile all the dependencies. We tried to install 2.7.13 instead of 2.7.5 and fai;led because we could not find tkinter libraries for that specific version.

Pip
***
If there is no pip,  install with::

    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    sudo python get-pip.py



Virtualenv
**********

If the virtualenv package is not installed::

    sudo pip install virtualenv

We don't want to mess up Centos or other user Python install, so we'll install our packages in out own local user environment.
We create a virtualenv with the default system python version with:

    virtualenv ~/py275

And we activate the environment with::

    source ~/py275/bin/activate

.. Note:: The virtualenv environemnt needs to be activated on every new session

Python packages
***************

Some packages have system library dependencies. Let's install them first:

ipython and matplotlib need python development libs::

    sudo yum install python-devel
    sudo yum install tkinter


We will use pybonjour, which requires avahi system libraries::

    sudo yum install avahi avahi-compat-libdns_sd avahi-compat-libdns_sd-devel
    sudo yum install avahi-tools avahi-ui-tools # to get the command-line tools like avahi-browse, avahi-discover

Now, install python packages::

    pip install ipython
    pip install numpy matplotlib sqlalchemy pyyaml tornado lxml h5py
    pip install nose docutils futures requests netifaces
    pip install -e git+https://github.com/Eichhoernchen/pybonjour.git#egg=pybonjour


.. note:: Pybonjour can also be installed manually with::

    wget https://storage.googleapis.com/google-code-archive-downloads/v2/code.google.com/pybonjour/pybonjour-1.1.1.tar.gz
    tar zxf pybonjour-1.1.1.tar.gz
    cd pybonjour-1.1.1
    python setup.py install


Getting the source code
***********************

We need ch_acq (python code) and chfpgalite (FPGA firmware) repositories, which are located on bitbucket.

if you use ssh keys to access these repos, setup ssh keys in .ssh/config or start ssh-agent and provide it with your keys::

    eval `ssh-agent`
    ssh-add path_to_bitbucket_key

Create a you own user folder to put the repos::

    mkdir ~/git
    cd ~/git

Get the repos::

    git clone  git@bitbucket.org:chime/ch_acq.git ch_acq
    git-lfs clone  git@bitbucket.org:winterlandcosmology/chfpgalite.git chfpga

Checkout the proper branches. In this example, we use jfc_dev for ch_acq and jfc/dev for chfpgalite::

    cd ch_acq
    checkout jfc_dev
    cd ../chfpga
    checkout jfc/dev



Networking
**********

To make the system work, we need to
    1) allow mDNS and UDP packets from the FPGA to be allowed in, and
    2) accept jumbo frames for raw data acquisition.


To temorarily allow avahi to work and accept all UDP packets for the FPGA commands and raw data (which might also allow mDNS)

    sudo iptables -I INPUT -p udp -j ACCEPT

Opeen port to allow clients to connect to servers

    sudo iptables -I INPUT 1 -p tcp  --dport 54321 -j ACCEPT  # ch_master server
    sudo iptables -I INPUT 1 -p tcp  --dport 54324 -j ACCEPT  # power supply server

Raw data packets are large and require the interface to accept JUMBO frames. Enable JUMBO frames with::

    sudo ifconfig enp0s31f6 mtu 9000

Tip: you can check incoming trafic with::

    ip -s  link show enp0s31f6


to check if avahi works:
    avahi-browse _tuber-jsonrpc._tcp --resolve

If resolve timeouts after 10 seconds, there is a problem. Sould restart the avahi server:

    sudo avahi-daemon -k; sudo avahi-daemon -D

Testing
*******

Make sure the virtualenv is enabled and launch ipython::

    cd ~/git/ch_acq
    source ~/py275/bin/activate
    ipython

in ipython, create a fpga_array with no boards in it, just to see if there are no missing packages::

    run -i pychfpga/fpga_array.py

Tips
****


Checking crates visible to mDNS:

sudo avahi-daemon -k
avahi-browse  _tuber-jsonrpc._tcp --resolve -t | grep -o 'backplane-serial=[0-9]*' | sort -u

Dynamic DHCP entries on carillon::

    cat /var/lib/dhcpd/dhcpd.leases


Static DHCP entries::
    sudo cat /etc/dhcp/dhcpd.conf



Search for OUI in static or dynamic addresses::

    cat /var/lib/dhcpd/dhcpd.leases | grep -B 7 '00:18'
    sudo cat /etc/dhcp/dhcpd.conf | grep '00:18'

Restart the DHCP server::


