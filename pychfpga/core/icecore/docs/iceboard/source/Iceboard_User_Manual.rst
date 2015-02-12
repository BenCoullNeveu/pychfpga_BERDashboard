------------
Introduction
------------

The IceBoard (Model MGK7MB) was designed at McGill University to provide a flexible and powerful real-time FPGA-based signal processing engine with very high bandwidth connectivity to allow efficient operations in large arrays.

This 9U motherboard is can accomodate two dual-width industry-standard FMC mezzanines that can be used with off-the-shelf ADC, DAC or other I/O modules. Up to 16 boards can be connected in a 19" subrack with a backplane allowing full-mesh 10Gbps links between every boards in addition to providing power, clocks and other trigger and synchronization signals.

The IceBoard is currently used for the CHIME telescope and the next geneation DFMUX.

Iceboard features
=================

- Form factor: 9U height able to accomodate two front-accessible double-width FMC mezzanines
- FPGA: Xilinx Kintex 7 7K420 (can also operate with a 7K325 and 7K480)
- Embedded processor: Texas Instrument AM3871 ARM processor
    - Software features:
        + Runs Linux
        + Allows remote FPGA programming
        + Provides high-level user interface to the hardware over IP
        + Allows application-specific user code to run locally
        + Runs a web server to visualize and control the core functions of the board

    + Hardware peripherals:
        + 1 GByte DDR3 memory
        + 2x Ethernet interfaces
        + SD-card-bootable
        + PCIe link to FPGA
        + Slave-serial interface to configure the FPGA

- Extensibility:
    + Two front-accessible dual-width FMC Mezzanine with High-Pin-Count (HPC)
      connectors connected to the FPGA (7K420 and 7k480 fully connect to all
      pins on both FPC-HPC connectors)

- External Connectivity
    + Back
        + 1 SFP+ cage connected to the FPGA (can accomodate 1 copper or optical 1Gb or 10 Gb Ethernet modules)
        + 2 QSFP+ cages connected to the FPGA (up to 4x10Gbps per connector) to connect to PCs, routers or  other boards
        + 3.3V UART connections to the ARM
        + 2 RJ-45 10/100/1000BASE-T Ethernet ports to the ARM
    + Front
        + SD card slot (ARM)
        + 3.3V UART  connection to the ARM
        + SMA clock input
    + On-board
        + FPGA fan power
        + Two SMAs connected to the FPGA (shared with LEDs and DIP switches)
- Backplane connectivity
    + 15x 10Gbps links to 15 other motherboards on the same backplane to allow full-mesh communication between every board in a crate
    + 4x 10Gbps links to backplane QSFP+ to allow inter-crate data shuffle.
    + 10 MHz reference clock input (LVPECL)
    + 2x LVDS SYNC inputs routed to the FMCs
    + TIME and TRIG LVDS signals
    + Three I2C backplane buses (one to FPGA and two to the ARM)
- Clocking
    + Reference clock sources (jumper-selectanble):
        + Embedded crystal oscillator,
        + Front panel SMA
        + Backplane
    + 2 low-jitter PLLs to generate all system clocks from 10 MHz reference clock
    + 10 MHz Reference clocks bypass the PLL and are fed to both FMCs for minimum jitter
- Power supply
    + 14-20VDC single-supply input voltage
    + Power provided by screw terminals or backplane connector
    + Fully FPGA-synchronized switchers allow noise control


Board description
=================

The following :ref:`figure <ImageIceBoardConnectors>` illustrates the localisation of the main connectors and LEDS of the IceBoard.

.. .........................
.. _ImageIceBoardConnectors:
.. figure:: images/Iceboard_top_view.png
    :align:  center

    IceBoard LED and connector localizations
.. .........................

.. _TableIceBoardConnectors:
.. table::  IceBoard Connectors (***to be completed***)

    +----------------------+---------------+--------------------------------+
    | Reference designator | Localisation  | Description                    |
    +======================+===============+================================+
    | P1                   | In ARM Shield | ARM UART0 connector            |
    +----------------------+---------------+--------------------------------+
    | P11                  | Back          | ARM UART1 connector            |
    +----------------------+---------------+--------------------------------+
    | P13                  | Front         | ARM UART2 connector            |
    +----------------------+---------------+--------------------------------+
    | SW9                  | Top           | FPGA Configuration mode switch |
    +----------------------+---------------+--------------------------------+
    | P18                  | Top           | Power terminal Block           |
    +----------------------+---------------+--------------------------------+

``*`` 'Top' side is the side with the FPGA and ARM processor

Board Set-up and power-up
=========================

These instructions describe how to operate the IceBoard in a stand-alone
manner (without a backplane) on a bench.

.. warning:: Always use Electro-Static Discharge (ESD) protection when handling the
             IceBoard

.. warning:: The surface on which the IceBoard is laid out must be non-conductive
             and free of debris. If the board is to be used on the bench for
             some period of time, it is suggested to install standoffs on the
             non-plated mounting holes.

Before using the board, configure the switches and jumpers and make the
connections as follows:

    #. Jumpers and switch configuration

       + SW9 FPGA configuration mode set to 'Slave Serial' (M2:0 = 0b000, 'ON' means '1') to allow programming by the ARM
         (See :ref:`SectionFpgaCOnfigModeSwitches`)
       + SW1 ARM boot configuration:  Switch 1-8 = 0b01101000 ('ON means '1')
       + SW2 ARM boot configuration:  Switch 1-8 = 0b01010000 ('ON means '1')
       + SW6 GP Switches: any setting is ok
       + SW7 FPGA Dip Switches: Set all to '0' (ON means '1')
       + J1: Install jumper (powers FPGA flash memory even if not used so it
         does not affect SPI communications betweent he ARM and FPGA)

    #. PLL Programming

        + PLL is already programmed at the factory with typical operational frequencies.

    #. Fan connection

        + If there is no forced air cooling and if the FPGA firmware is going
          to generate any significant amount of dynamic power, the FPGA fan should
          be installed and connected to the fan power supply. Regularly
          monitor the FPGA core temperature via the Python interface to make
          sure the FPGA does not overheat (temp < 85 degC).

    #. Clock selection

        + Install jumper on J2, J4 or J7 to select clock source. Use J2
          (Crystal) for stand-alone operation.
        + If 'front panel SMA' clock is used, connect 10 MHz clock to front
          panel SMA.

    #. ARM Firmware

        + Insert SD Cart=d in SD card slot on the front panel

    #. ARM Ethernet

        + Connect Ethernet cable on P3: Ethernet A (the lower RJ-45
          connector). The cable should connect to a network providing DHCP
          services to allocate a IP address to the Iceboard. The DHCP server
          could optionnally be configured to provide a fixed IP address based
          on the ARM MAC address.

    #. Power connection

        + If using the board without backplane, connect 14-20VDC supply on the
          P18 terminal block. Typical voltageis 16V. Polarity is indicated on
          the silk (+V, Gnd, -V). A negative supply (V-) is *not* needed.
          Board uses about 1A @ 16V when FPGA is not programmed, and can use
          about 5A @ 16V when a very large FPGA firmware is operating. The
          input has a reverse diode and a fuse, and the non-resettable fuses
          (F1 and F2) shall blow if the power if applied with the wrong
          polarity.

Once the board is set-up, double check the power connections on the board and at the power supply.

Then turn power on. You should observe the following. If not. turn off power immediatly and investigate.

        #. The Fan (if installed) should immediately start spinning.
        #. All the power LEDS (DS1, DS2 and DS3 on the back) should light up (the color of the LED has no special meaning). This confirms proper voltages on the 12V, 3.3V, 2.5V, Vadj, 1.8V, 1.0V (FPGA Core), 1.5V, 1.2V and 1.0V (FPGA GTX) rails.
        #. Led D5V (on the top side, next to the other power LEDs) should light up to indicate presence of the 5V rail.
        #. The two PLL LEDs on DS10 (green and yellow LEDs on the lower LED stack on the front panel) should turn on to indicate that the PLL has locked to the 10 MHz reference clocks
        #. The LED on the Ethernet port with the cable should be blinking indicating that the processor sees traffic
        #. After about 10 seconds, on-board and front leds (except those mentionned above) will briefly flash and turn off, and the green led on the top front LED block (GPIO LED3, on DS12) will turn on to indicate that the ARM processor has finished its boot sequence.

Once the ARM is running, you can confirm proper operation of the board by
logging into the ARM. To do this, determine the IP address  that the DHCP gave
to the ARM by logging into the DHCP server and looking for devices with MAC
addresses starting with .

Alternatively, if the board has a ARM firmware version that is recent enough
(V2.0 and up), it will advertise its presence through the mDNS protocol. If
your host computer has a mDNS client (often implemented by Avahi on Linux and
Apple Bonjour on Macs and PC), you can list the hostname of the IceBoard by
issuing the command  ``dns-sd -B _ssh._tcp``. The names ``iceboard`` or
``iceboardNNNN`` will normally show in the list, meaning that the boards can
be accessed throught the names  ``iceboard.local`` or ``iceboardNNNN.local``
instead of its IP address.

You can then log into the board by starting a ssh session at that address under the root username. There is no password.

If this works, you can compile the FPGA example firmware that is provided with
the IceCore repository and run the example Python program that will program
the FPGA , access FPGA resources and blink the FPGA leds.



Hardware Description
====================

Clock source
------------
All of the IceBoard hardware is operated on clocks derived from a single 10MHz reference. The clocks provided to the FMC mezzanines also come from this clock. The clock can come from the following sources:

- On-board crystal: This option allows the board to be used quickly on a bench without requiring an external source, but offers limited frequency accuracy or phase noise performance ( We use an Abracon ASFL1-10.000 MHz oscillator, +/- 100 ppm, 1 ps rms phase jitter 12 KHz-20MHz). In an array of boards, having each board using its own independent oscillator is not recommended as this will create relative drifts in data acquired/generated by the mezzanine and may put protocol constraints on high speed links between boards. When the on-board clock is not selected, the clock chip is disabled to ensure it will not cause noise in the system.
- Front panel SMA
- Backplane: A high precision LVPECL clock can be provided to the board by the backplane. The IceBoard has a proper LVPECL termination, so each board on the backplane must be driven by an independent LVPECL driver (e.g. driven by a LVPECL clock fanout chip). In other words, the clock lines cannot be bussed or daisy chained. The backplane is responsible from converting its clock input (typically from a SMA or BNC connector) to a proper LVPECL format. The IceBoard can optionnally be fed an LVDS clock from the backplane by removing the LVPECL termination resistors (R10, R70, R72, R305).


.. note:: If multiple boards are communicating together over the FPGA's gigabit links (GTXes), all the boards should be driven from a common clocks unless you have confirmed that the GTX can cope with the worst case frequency difference between boards and that the GTX and communication protocol has been designed explicitely to drop words to compensate for the frequency differences. Also note that in loopback mode, the GTX still derive the receive clock from the remote source and may not be at the same freuency as the transmit clock if independent clocks are used.

The source of the 10 MHz reference clock is selected by installing the jumper in the locations listed in
:ref:`the following table <TableClockSelection>`. The settings of the jumpers can be read out from the ARM processor to allow the control software to detect improper clock source selection.

.. _TableClockSelection:
.. table::  Clock source jumper positions

    +------------------+-----------------+
    | Clock source     | Jumper position |
    +==================+=================+
    | On-board crystal | J2              |
    +------------------+-----------------+
    | Front SMA        | J4              |
    +------------------+-----------------+
    | Backplane        | J7 or no jumper |
    +------------------+-----------------+

The selected 10 MHz clock source is fed to a ultra-low jitter clock MUX/fanout
chip (U17, a LMK00304SQ). The clock source is selected by the MUX section
based on the jumper settings and is outputted as 4 LVDS signals, two of which
drive the internal PLLs, and with the other two connecting directly to the FMC
mezzanines. The later connections ensure there is a direct PLL-free path
between the reference clock and the mezzanines for applications where jitter
performace has to be tightly controlled.  A fifth single-ended reference
output is fed to the FPGA directly (FPGA_CLK_RAW) to provide a copy of the
clock that is always present (independet of the PLL configuration) and that
has a well defined phase relative to the high quality FMC reference clocks.

Two PLL chips are used to generate the various clocks required by the ARM and FPGA. The
.. _TableDefaultPLLConfig:
.. table::  PLL Default Configuration Information

    +------+--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    | PLL  | Output | Frequency  | Destination                                    | Typical Usage                                                         |
    +======+========+============+================================================+=======================================================================+
    | PLL1 | Out 0  | 20 MHz     | ARM                                            | Main ARM clock                                                        |
    | U16A +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 1  | 100 MHz    | FPGA MGTCLKREF1_114 and ARM PCI                | FPGA and ARM PCI Express reference clock                              |
    |      +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 2  | 25 MHz     | ARM PHY (two single-ended outputs)             | Used by the ARM to generate the PHY clocks                            |
    |      +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 3  | 125 MHz    | FPGA MGTCLKREF1_116                            | SFP reference clock for 1G Ethernet                                   |
    |      +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 4  | 200 MHz    | FPGA MGTCLKREF1_112                            |                                                                       |
    +------+--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    | PLL2 | Out 0  | 156.25 MHz | FPGA MGTCLKREF0_112                            | 10G Ethernet or 10G links on SHUFFLE/QUAD/QSFP+                       |
    | U16B +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 1  | 156.25 MHz | FPGA MGTCLKREF0_114                            | 10G Ethernet or 10G links on SHUFFLE/QUAD/QSFP+                       |
    |      +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 2  | 156.25 MHz | FPGA MGTCLKREF0_116                            | 10G Ethernet or 10G links on SHUFFLE/QUAD/QSFP+                       |
    |      +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 3  | 125 MHz    | FPGA MGTCLKREF0_115                            | Alternate 1G Ethernet reference                                       |
    |      +--------+------------+------------------------------------------------+-----------------------------------------------------------------------+
    |      | Out 4  | 10 MHz     | FPGA MGTCLKREF1_115                            | Feedback bypass, for access to original 10 MHz reference, AC coupled  |
    +------+--------+------------+------------------------------------------------+-----------------------------------------------------------------------+




.. note::  The PLLs are factory-programmed and do not need to be programmed by the user.


.. _SectionFpgaCOnfigModeSwitches:

FPGA Configuration Mode switches
--------------------------------


The FPGA configuration mode is set by the SW9 DIP switches
(:ref:`image<FigFPGAConfigSwitches>`, :ref:`switch definition <SWnTable>`).
The 'ON' position corresponds to a binary '1'. The modes are listed in :ref:`TableFPGAConfModes`.

The FPGA is normally programmed by the ARM processor using the Slave Serial
mode (The ARM generates the programming clock, and the data is sent serially
one bit at a time). Programming a non-compressed bitstream takes approximately 15 seconds.
JTAG programming is also possible using the Xilinx programming pod using P14 JTAG connector next to the FPGA.

Note that JTAG access is always enabled in any mode, so external developemnt
tools (such as the Xilinx IBERT core) can be used to communicate with the FPGA
even of the switch is left in slave serial mode. In other words, a user can
program the IBERT core in the FPGA through the ARM and run the JTAG-based
IBERT application without having to change the configuration switches.

The board has a serial flash memory that could be used to program the FPGA.
This feature was meant as an alternate programming solution in case the ARM
processor is not available, but this mode of programming has not been tested
and is therefore not recommended.

.. _FigFPGAConfigSwitches:
.. figure:: images/FPGAConfigSwitches.jpg
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


* see [UG470]_ for more details

.. _SectionGTXselection:

GTX connection selection resistors
----------------------------------

GTX Banks 111,112,113 and 114 each contain 4 multi-gigabit transceivers (MGT)
that can be connected either to the FMC DP lines or to the backplane high speed (shuffle)
lines. Each link can operate at speeds up to 12.5 Gbps. The routing of the
link is set by soldering resistors to the proper pads. The
:ref:`figure below<FigGTXSelectionResistors>`
shows which block of resistors control the
routing of which GTX signals.

.. _FigGTXSelectionResistors:
.. figure:: images/GTX_selection_resistors.png
    :align: center
    :width: 800 px


.. [UG470] Xilinx 7 Series FPGAs Configuration





                              --- End of document ---