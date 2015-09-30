------------
Introduction
------------

The IceBoard (Model MGK7MB) was designed at McGill University to provide a
flexible and powerful real-time FPGA-based signal processing engine with
high-bandwidth connectivity to allow efficient operations in large arrays.

This 9U motherboard is can accomodate two dual-width industry-standard FMC
mezzanines that can be used with off-the-shelf ADC, DAC or other I/O modules.
Up to 16 boards can be connected in a 19" subrack with a backplane allowing
full-mesh 10Gbps links between every boards in addition to providing power,
clocks and other trigger and synchronization signals.

The IceBoard is currently used for the CHIME telescope and the next generation
DFMUX.

.. figure:: ../images/banner.jpg
   :align:  center

.. contents:: Table of Contents
   :local:

Key Features
============

**9U Form Factor**
   - Able to accomodate two front-accessible double-width FMC mezzanines

**Kintex-7 '420t FPGA**
   - Board is also compatible with '325t and '480t

**Texas Instruments AM3874 CPU**
   - Hardware

     - Cortex-A8 with FPU
     - 1 GByte DDR3 memory
     - 2x Gigabit Ethernet interfaces
     - Boots from removable SD/MMC card
     - PCIe link to FPGA
     - Slave-serial interface to configure the FPGA

   - Software

     - Runs Linux
     - Allows remote FPGA programming
     - Provides high-level user interface to the hardware over IP
     - Allows application-specific user code to run locally
     - Runs a web server to visualize and control the core functions of the board

**FMC-Compliant Mezzanines**
   - Two dual-width mezzanines with High-Pin-Count (HPC) connectors
   - Full HPC FMC connectivity when using 'k420t or '480t FPGAs
   - On-board, per-mezzanine power switches with current and voltage
     monitoring

**High-Speed, Full-Mesh Backplane**
   - 15 x 10Gb links (per slot) to every other slot in the crate
   - 4 x 10Gbps links (per slot) to backplane QSFP+
   - 10 MHz reference clock input (LVPECL) with high-speed fanout buffer
   - (Optional) 2x LVDS SYNC inputs routed directly to FMCs
   - Dedicated TIME and TRIG LVDS signals with high-speed fanouts
   - Three I2C backplane buses

     - One to shared FPGA/ARM I2C fabric
     - Two direct I2C links to the ARM

**Rich Connectivity**
   - Rear Edge:

     - 1 SFP+ cage connected to the FPGA (can accomodate 1 copper or optical 1Gb or 10 Gb Ethernet modules)
     - 2 QSFP+ cages connected to the FPGA (up to 4x10Gbps per connector) to connect to PCs, routers or  other boards
     - 2 RJ-45 10/100/1000BASE-T Ethernet ports to the ARM
     - 3.3V UART connections to the ARM
   - Front Edge:

     - SD card slot (ARM)
     - 3.3V UART  connection to the ARM
     - SMA clock input

   - On-board

     - FPGA fan power
     - Two SMAs connected to the FPGA (shared with LEDs and DIP switches)

**Flexible Clocking**
   - Reference clock sources (jumper-selectable):

     - Embedded crystal oscillator
     - Front panel SMA
     - Backplane

   - 2 low-jitter PLLs to synthesize system clocks from 10 MHz reference clock
   - 10 MHz Reference clocks bypass the PLL and are fed to FMCs for minimum jitter

**Single, 14-20V Power Supply**
   - Power provided by screw terminals or backplane connector
   - Fully FPGA-synchronized switchers for noise control

Map of LEDs, Switches, and Sockets
==================================

.. figure:: ../images/iceboard_top_view.svg
    :align:  center

    IceBoard LED and Connector Locations

Table of Connectors
===================

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

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
