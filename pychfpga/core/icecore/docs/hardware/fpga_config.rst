FPGA Configuration
------------------

This section describes how the FPGA is configured, and which DIP switches can
be used to alter this configuration.

.. figure:: ../images/banner.jpg
   :align:  center

.. contents:: Table of Contents
   :local:

The FPGA configuration mode is set by the SW9 DIP switches
(:ref:`FigFPGAConfigSwitches`, :ref:`SWnTable`).  The 'ON' position corresponds
to a binary '1'. The modes are listed in :ref:`TableFPGAConfModes`.
See [UG470]_ for more details on FPGA configuration modes.

The FPGA is normally programmed by the ARM processor using the Slave Serial
mode (The ARM generates the programming clock, and the data is sent serially
one bit at a time). Programming a non-compressed bitstream takes approximately
15 seconds.  JTAG programming is also possible using the Xilinx programming pod
using P14 JTAG connector next to the FPGA.

.. note:: JTAG access is always enabled in any mode, so external development
        tools (such as the Xilinx IBERT core) can be used to communicate with
        the FPGA even of the switch is left in slave serial mode. In other
        words, a user can program the IBERT core in the FPGA through the ARM
        and run the JTAG-based IBERT application without having to change the
        configuration switches.

The board has a serial flash memory that could be used to program the FPGA.
This feature was meant as an alternate programming solution in case the ARM
processor is not available, but this mode of programming has not been tested
and is therefore not recommended.

.. _FigFPGAConfigSwitches:
.. figure:: ../images/fpga_config_switches.jpg
    :align: center
    :width: 600 px

    FPGA configuration mode switches

.. _SWnTable:
.. table:: SW9 FPGA Configuration mode switches

    +---------------+-------------+------------------------------------------------------+
    | Switch number | Switch name | Function                                             |
    +===============+=============+======================================================+
    | 1             | M0          | FPGA Configuration mode                              |
    +---------------+-------------+ (see :ref:`TableFPGAConfModes`)                      |
    | 2             | M1          |                                                      |
    +---------------+-------------+                                                      |
    | 3             | M2          |                                                      |
    +---------------+-------------+------------------------------------------------------+
    | 4             | NC          | Not connected                                        |
    +---------------+-------------+------------------------------------------------------+

.. _TableFPGAConfModes:
.. table:: FPGA Configuration modes

    +--------+--------------------+
    | M[2:0] | Configuration Mode |
    +========+====================+
    | 000    | Master Serial      |
    +--------+--------------------+
    | 001    | Master SPI         |
    +--------+--------------------+
    | 010    | Master BPI         |
    +--------+--------------------+
    | 100    | Master SelectMAP   |
    +--------+--------------------+
    | 101    | JTAG               |
    +--------+--------------------+
    | 110    | Slave SelectMAP    |
    +--------+--------------------+
    | 111    | Slave Serial       |
    +--------+--------------------+

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
