Root Filesystem
===============

**This document is a focal point for root-filesystem documentation on the
IceBoard.** For context on the root filesystem, consult the :doc:`index`
document for firmware.

.. figure:: ../images/banner.jpg
   :align: center

.. contents:: Table of Contents
   :local:

When to Read This Document
--------------------------

This document is useful in a few situations:

#. You want to build a cross-toolchain, so that you can compile C code to run
   on the board,
#. You want to rebuild the root filesystem, or
#. You want to add a new package to the root filesystem.

Introduction
------------

The root filesystem is managed by a tool called **Buildroot**. This tool does
several things:

#. Compiles a compiler (including libc),
#. Fetches and builds source code for a diverse set of tools, and
#. Combines these tools into a complete root filesystem.

You can think of buildroot as an easy way to put together a custom Linux
mini-distribution. For example, buildroot compiles the following tools
available on the IceBoard:

#. "Dropbear" ssh server,
#. Python,
#. libmicrohttpd (the embedded web server we use for our application stack),
#. the DHCP client and mDNS/DNS-SD tools (Avahi) used for networking,
#. ...and many others.

For detailed Buildroot documentation, please consult the Buildroot site
(linked below.)

References
----------

`IceBoard buildroot Git tree <https://bitbucket.org/winterlandcosmology/iceboard-buildroot.git>`_

   **This is where we keep the source code for our Buildroot branch.**

`Buildroot Homepage <http://buildroot.uclibc.org>`_

   **This is the homepage for the Buildroot project**. Our version split off
   at version 2013.11, so you should not expect any content newer than that
   (unless I've added it explicitly.)

Building Buildroot
------------------

.. code:: bash

   $ git clone bitbucket.org:winterlandcosmology/iceboard-buildroot.git
   $ cd iceboard-buildroot
   iceboard-buildroot$ make iceboard_defconfig

The build product is `output/images/rootfs.tar.bz2`.

Configuring Buildroot
---------------------

.. note:: You don't need to configure buildroot beyond the
   "iceboard_defconfig" step above, unless you want to *change* its
   configuration.

.. code:: bash

   $ make menuconfig

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
