Kernel
======

**This document is a focal point for kernel documentation on the IceBoard.**
For context on firmware, consult the :doc:`index` document for firmware.

.. figure:: ../images/banner.jpg
   :align:  center

.. contents:: Table of Contents
   :local:

When to Read This Document
--------------------------

This documentation is useful in a few situations:

#. You want to understand how the kernel works on the IceBoard,
#. You want a "clean" re-build of the kernel without changes,
#. You want to add new driver, hardware, or protocol support to the IceBoard.

References
----------

`IceBoard kernel Git Tree <https://bitbucket.org/winterlandcosmology/iceboard-linux.git>`_

   **This is where we keep the source code for our Linux tree. Other Linux
   sources (below) are useful for reference only.** Our Linux distribution
   differs from TI's source code (below) in the following ways:

   #. The "ti81xx" board support package (BSP) is adapted the IceBoard;
   #. DDR3 caching changed to always use write allocation. This is a
      workaround for UDM/LDM swap in rev0 IceBoards, and should no longer be
      relevant;
   #. Bugfixes for compiler variations (e.g. 758c866442)
   #. PHY, DDR3, and GPIO initialization
   #. Board-specific configuration for GPIO, I2C, flash, Ethernet/PHYs.

`Arago u-boot-omap3.git Sources <http://arago-project.org/git/projects/?p=linux-omap3.git;a=summary>`_

   **This git tree is where our Linux snapshot started from.**

`Kernel Homepage <http://www.kernel.org>`_

   **This is the kernel's "official" home on the web.** TI's snapshot of the
   kernel diverged back at version 2.6.37. This link is useful because it's
   the "official" kernel source.

`TI's AM3874 Documentation <http://processors.wiki.ti.com/index.php/DM814x_AM387x_PSP_User_Guide#Linux_Kernel>`_

   **This link contains TI-specific information for using Linux on our
   processor.** The documentation here is useful for our board and Linux
   version, except that it's targeted at the TI8148 evaluation board (which
   differs from our hardware.)

Prerequisites
-------------

**Compiler**:

   The kernel compiler comes from the Vivado toolchain. You must download and
   install Vivado, and run `source /path/to/Vivado/2014.4/settings64.sh` prior
   to proceeding. This will place the compiler toolchain in your `$PATH`.

Building Linux
--------------

.. code:: bash

   $ git clone bitbucket.org:winterlandcosmology/iceboard-linux.git
   $ cd iceboard-linux
   iceboard-linux$ . /path/to/Vivado/2014.4/settings64.sh
   iceboard-linux$ make ARCH=arm iceboard_defconfig
   iceboard-linux$ make ARCH=arm CROSS_COMPILE=arm-xilinx-linux-gnueabi- uImage

The build product is `arch/arm/boot/uImage`.

Configuring Linux
-----------------

.. note:: You don't need to configure Linux beyond the "iceboard_defconfig"
   step above, unless you want to *change* its configuration.

.. code:: bash

   $ make menuconfig

Useful Hints
------------

I2C Devices, GPIO device names:
   The IceBoard's I2C buses are largely managed by the kernel. The kernel's
   description of what hardware is attached via I2C lives in
   `iceboard-linux/arch/arm/mach-omap2/board-ti8148evm.c
   <https://bitbucket.org/winterlandcosmology/iceboard-linux/src/HEAD/arch/arm/mach-omap2/board-ti8148evm.c?at=master>`_.
   (Exception: The mezzanines' I2C buses are managed entirely in userspace
   software, since we don't know what mezzanine might be attached, and because
   the mezzanine isn't powered on when the board is first booted.)

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
