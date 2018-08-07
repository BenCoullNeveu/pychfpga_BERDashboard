Spectrum Instruments TM-4 GPS receiver configuration
====================================================

This HowTo describes how to configure the Spectrum Instruments TM-4 Irig-B GPS receiver to use it as a source for the IceBoard.


GPS receiver Configuration
--------------------------

Output Configuration
    + Out A: Mux1
    + Out B: 10 MHz
    + Out C: 10 MHz
    + Mux 1: IRIG-B

We set both Out A and Out B to the 10MHz output so we can drive two crates.

PPS Mode:
	Set PPS mode to FILPPS when Time Valid, and GPSPPS otherwise. This applies to the PPS signal on the Muxes. We don't use PPS, but Spectrum Instruments have changes their firmware for us so the IRIG_B signal would also switch to the filtered version when the PPS signal switches. This is important to have the IRIG-B timing be stable relative to the 10 MHz reference clock, and therefore allow us to specify triggers that safely occur between two 10 MHz edges and allow all boards to trig on the same 10 MHz edge.

Time format
	IRIGB207 is needed if we want the year.

Timing Mode:
	Static is the easiest to make work. It just measures time, assuming the location has been properly entered by the user. It works with only one visible satellite. It is easy to get a Tive Valid and reference Lock  in a short delay, even if the antenna is indoors next to a window in front of buildings that block most of the sky. You might need to set the current position manually by using the GUI or sending a command to the GPS.

	On a good location with good sky visibility, use Survey mode to figure out the position automatically.

	NOTE: For some reason , the Windows GUI does not accept Western longitudes. The GUI can be used to send a command to set it.

Connection to the IceCrate
--------------------------

Use a 6dB attenuator before conecting to the IceCrate because the output level of the TM4 CMOS output exceeds the IceCrate input range.

Failure to use the attenuator will likely destroy the clock/data distributor chip that receives the signal.

Spectrum Instruments TM-4D GPS receiver configuration
=====================================================

The TM-4D is a TM-4 board connected to a distribution board. The unit can provide 10 MHz and IRIG-B signal for up to 8 Icecrates.

GPS receiver Configuration
--------------------------

Output Configuration
    + Out A: Mux1
    + Out B: 10 MHz
    + Mux 1: IRIG-B

Time format: See TM-4

Timing mode: See TM-4

Distribution board Configuration
--------------------------------

Remove the cover of the unit and select the following digital sources:
	+ Bank 1: Out A
	+ Bank 2: Out A
	+ Bank 3: Out B
	+ Bank 4: Out B

Banks 1 & 2 (8 BNCs) provide IRIG-B, and banks 2 & 3 (8 BNCs) provide the 10 MHz clock.

Connection to the IceCrate
--------------------------

The outputs of the TM-4D are 2.5Vpp in 50 ohms and are compatible with the backplane clock input.

.. Voltage output confirmed on Slack by a masurement from Seth, Dec 7th 2017

The antenna required a TNC connector, so an adapter might be needed.

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
