Benchtop Setup
==============

These instructions describe how to operate the IceBoard in a stand-alone
manner (without a backplane) on a bench.

.. figure:: ../images/banner.jpg
   :align:  center

.. warning:: Always use Electro-Static Discharge (ESD) protection when handling the
             IceBoard

.. warning:: The surface on which the IceBoard is laid out must be non-conductive
             and free of debris. If the board is to be used on the bench for
             some period of time, it is suggested to install standoffs on the
             non-plated mounting holes.

.. contents:: Table of Contents
   :local:

Before using the board, configure the switches and jumpers and make the
connections as follows:

Jumpers and Switch Configuration
--------------------------------

   - SW9 FPGA configuration mode set to 'Slave Serial' (M2:0 = 0b000, 'ON' means '1') to allow programming by the ARM
     (See :ref:`SectionFpgaConfigModeSwitches`)
   - SW1 ARM boot configuration:  Switch 1-8 = 0b01101000 ('ON means '1')
   - SW2 ARM boot configuration:  Switch 1-8 = 0b01010000 ('ON means '1')
   - SW6 GP Switches: any setting is ok
   - SW7 FPGA Dip Switches: Set all to '0' (ON means '1')
   - J1: Install jumper (powers FPGA flash memory even if not used so it
     does not affect SPI communications betweent he ARM and FPGA)

PLL Programming
---------------

   - The PLL is already programmed at the factory with typical operational frequencies.

Fan Connection
--------------

   - If there is no forced air cooling and if the FPGA firmware is going
     to generate any significant amount of dynamic power, the FPGA fan should
     be installed and connected to the fan power supply. Regularly monitor the
     FPGA core temperature via the Python interface to make sure the FPGA does
     not overheat (temp < 85 degC).

Clock Selection
---------------

   - Install jumper on J2, J4 or J7 to select clock source. Use J2
     (Crystal) for stand-alone operation.
   - If 'front panel SMA' clock is used, connect 10 MHz clock to front
     panel SMA.

ARM Firmware
------------

   - Insert SD Cart=d in SD card slot on the front panel

Network
-------

Connect Ethernet cable on P3: Ethernet A (the lower RJ-45 connector). The
cable should connect to a network providing DHCP services to allocate a IP
address to the Iceboard. The DHCP server could optionally be configured to
provide a fixed IP address based on the ARM MAC address.

Power
-----

If using the board without backplane, connect 14-20VDC supply on the P18
terminal block. Typical voltageis 16V. Polarity is indicated on the silk (+V,
Gnd, -V). A negative supply (V-) is *not* needed.  Board uses about 1A @ 16V
when FPGA is not programmed, and can use about 5A @ 16V when a very large FPGA
firmware is operating.
     
.. warning:: The input has a reverse diode and a fuse, and the non-resettable
   fuses (F1 and F2) shall blow if the power if applied with the wrong
   polarity.

Once the board is set-up, double check the power connections on the board and at the power supply.

Then turn power on. You should observe the following. If not, *turn off power
immediately* and investigate.

   #. The Fan (if installed) should immediately start spinning.
   #. All the power LEDS (DS1, DS2 and DS3 on the back) should light up (the color of the LED has no special meaning). This confirms proper voltages on the 12V, 3.3V, 2.5V, Vadj, 1.8V, 1.0V (FPGA Core), 1.5V, 1.2V and 1.0V (FPGA GTX) rails.
   #. Led D5V (on the top side, next to the other power LEDs) should light up to indicate presence of the 5V rail.
   #. The two PLL LEDs on DS10 (green and yellow LEDs on the lower LED stack on the front panel) should turn on to indicate that the PLL has locked to the 10 MHz reference clocks
   #. The LED on the Ethernet port with the cable should be blinking indicating that the processor sees traffic
   #. After about 10 seconds, on-board and front leds (except those mentionned above) will briefly flash and turn off, and the green led on the top front LED block (GPIO LED3, on DS12) will turn on to indicate that the ARM processor has finished its boot sequence.

Communicating with the Board
----------------------------

Once the ARM is running, you can confirm proper operation of the board by
checking its service advertisements via the mDNS / DNS-SD protocols.

On Linux, try the following::

        $ avahi-browse _tuber-jsonrpc._tcp
        +   eth0 IPv4 iceboard004                                   _tuber-jsonrpc._tcp  local
        +   eth0 IPv6 iceboard004                                   _tuber-jsonrpc._tcp  local

On Mac OS X, try the following::

        # GMS: confirm with someone
        $ dns-sd -B _tuber-jsonrpc._tcp

The ``iceboard004.local`` response is advertised by the IceBoards themselves; a
response here indicates a board is up and communicating.

You may now communicate with the board in a number of ways:

**Using SSH**
   If your IceBoard has serial 004, you can contact it via SSH as follows::

      $ ssh root@iceboard004.local

**Using a Web Browser**
   The board provides a web interface at http://iceboard004.local/; again,
   replace 004 with the serial number of your board.

If this works, you can compile the FPGA example firmware that is provided with
the IceCore repository and run the example Python program that will program
the FPGA, access FPGA resources and blink the FPGA LEDs.

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
