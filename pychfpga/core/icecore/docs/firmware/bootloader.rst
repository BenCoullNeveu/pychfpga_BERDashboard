U-Boot
======

**This document is a focal point for u-boot documentation on the IceBoard.**
For context on firmware, consult the :doc:`index` document for firmware.

.. figure:: ../images/banner.jpg
   :align:  center

.. contents:: Table of Contents
   :local:

When to Read This Document
--------------------------

This documentation is useful in a few situations:

#. You want to understand how u-boot works on the IceBoard,
#. You want a "clean" re-build of u-boot without changes,
#. You want to change what happens in the first ~100ms of boot-up (u-boot
   stage 1), or
#. You want to change what happens in the first ~5s of boot-up (u-boot stage
   2).

References
----------

`IceBoard u-boot Git Tree <https://bitbucket.org/winterlandcosmology/iceboard-uboot.git>`_

   **This is where we keep the source code for our u-boot tree. Other u-boot
   sources (below) are useful for reference only.** Our u-boot distribution
   differs from TI's source code (below) in the following ways:

   #. The "ti8148_evm" board support package (BSP) is adapted the IceBoard;
   #. Data cache is enabled early in boot. This is a workaround for UDM/LDM
      swap in rev0 IceBoards, and should no longer be relevant; and
   #. PHY, DDR3, and GPIO initialization is adapted for the IceBoard

`Arago u-boot-omap3.git Sources <http://arago-project.org/git/projects/?p=u-boot-omap3.git;a=summary>`_

   **This git tree is where our u-boot snapshot started from.** At time of
   writing, the newest common commit was
   `d31a6e4f0f5e3c23a7041d98703218df4b15a6e1
   <http://arago-project.org/git/projects/?p=u-boot-omap3.git;a=commit;h=d31a6e4f0f5e3c23a7041d98703218df4b15a6e1>`_.

`U-Boot Homepage <http://www.denx.de/wiki/U-Boot>`_

   **This is u-boot's "official" home on the web.** Our snapshot of u-boot
   diverged from this tree way back at version 2010.06. This link is useful
   because it's the "official" distribution of u-boot.

`TI's U-Boot Documentation <http://processors.wiki.ti.com/index.php/DM814x_AM387x_PSP_U-Boot>`_

   **This link contains TI-specific information for using u-boot on our
   processor.** The documentation here is useful for our board and u-boot
   version, except that it's targeted at the TI8148 evaluation board (which
   differs from our hardware.)

Prerequisites
-------------

**Compiler**:

   You must `download and install Code Composer Studio (CCS)
   <http://processors.wiki.ti.com/index.php/Download_CCS#Code_Composer_Studio_Version_5_Downloads>`_.
   We use their compiler for u-boot. The compiler path used to compile u-boot
   is configured at
   `iceboard-uboot/board/ti/ti8148/config.mk
   <https://bitbucket.org/winterlandcosmology/iceboard-uboot/src/HEAD/board/ti/ti8148/config.mk?at=master>`_.

Building U-Boot
---------------

We use a 2-stage boot process:

**Stage 1** (MLO):
   In stage 1, the CPU has barely been initialized and we're limited to
   on-chip RAM. This RAM isn't big enough to comfortably run a fully-fledged
   u-boot, so we start with a stripped-down version just big enough to
   initialize hardware and chain-load a "real" u-boot build.

**Stage 2** (u-boot.bin):

   Stage 2 u-boot is "big enough" to do interesting things, like load and boot
   Linux from the SD card or across the network.

.. warning:: Keep stage-1 and stage-2 u-boot builds separate. They start from
   the same source code, but should be checked out into two different
   locations.

In the following sections, we describe how to build each stage from scratch.

Stage 1
~~~~~~~

.. code:: bash

   $ git clone https://bitbucket.org/winterlandcosmology/iceboard-uboot uboot1
   $ cd uboot1
   uboot1$ make distclean
   uboot1$ export PATH=$PATH:/opt/ti/ccsv6/tools/compiler/gcc-arm-none-eabi-4_7-2013q3/bin/
   uboot1$ make ARCH=arm CROSS_COMPILE=arm-none-eabi- ti8148_evm_min_sd
   uboot1$ make ARCH=arm CROSS_COMPILE=arm-none-eabi- u-boot.ti

The build output is `u-boot.min.sd`, and should be distributed as `MLO`.

Stage 2
~~~~~~~

.. code:: bash

   $ git clone https://bitbucket.org/winterlandcosmology/iceboard-uboot uboot2
   $ cd uboot2
   uboot2$ make distclean
   uboot2$ export PATH=$PATH:/opt/ti/ccsv6/tools/compiler/gcc-arm-none-eabi-4_7-2013q3/bin/
   uboot2$ make ARCH=arm CROSS_COMPILE=arm-none-eabi- ti8148_evm_config_sd
   uboot2$ make ARCH=arm CROSS_COMPILE=arm-none-eabi- u-boot.ti

The build output is `u-boot.bin`, and should keep that name.

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
