CLOCK, TRIG and TIME and SYNC inputs
====================================

The backplane offers 4 SMA connectors whose signals are distributed signals to all slots using high speed fanout chips. The signal on the SMA is single-ended, and the fanout buffer chip converts those signals to 16 differential signals that are sent to each slot, thus ensuring maximum signal integrity. To ensure this, the boards must implement proper routing techniques and adequate terminations. If boards are not installed, the line is obviously unterminated, but the clock buffers were chosen to allow this without affecting the quality of the signal on the other boards.


SYNC is internally distributed as LVPECL, but is plit in two and is sent to the connector as two LVDS signals.
TIME and TRIG and distributed and appear on the slot conector as LVDS.
CLOCK is internally distributed as LVPECL.

TRIG and TIME input levels
--------------------------

`` Text from Adam
In all cases a logic 1 is when the input to the fanout IC is 100mV
higher than 1.1V, and low when its 100mV lower than 1.1V.
For Time and Trig the IC is powered from 2.5V so you absolutely must
not have a signal stronger than this (at the IC input)
For Clock and Sync the IC is powered from 3.3V so you absolutely must
not have a signal stronger than this (at this IC input)

Your clock source must not be AC coupled (since we do not want
negative voltages at the input to our fan out IC)

If you do not have a terminator on the backplane loaded. Stick your
clock source into a oscilloscope (with the input impedance on very
high, can just use some probes) and measure the maximum and minimum
voltages. The maximum must not exceed the 2.5/3.3 and the minimum must
not be negative.

If you do have a terminator on the backplane. Stick your clock source
into the oscilloscope again but this time with the oscilloscope input
impedance set to 50 Ohms. Measure the maximum and minimum voltages and
ensure that they do not exceed the 2.5/3.3V and do not go negative.

In any case (except for the signals going negative one) if you measure
something thats too big, you can use some inline terminators to reduce
the voltage. In the worst case scenario, you'd have a 5V clock source,
with no output impedance and no terminator on the backplane. In this
case 11dB of attenuation ensures that everything is happy.
```

Measured by JF on June 9th, 2016
Measured with multimeter
SN003 (Rev0): all inputs 55 ohms
SN011 (Rev2): Clock/Sync: 55 ohms, Trig/Time: 65 ohms

Rev 2 - Clock/Sync inputs
	Input impedance: 56 ohms at dc, 50 ohms above 10 kHz  (fc at 1 kHz)
	Limits (50 ohms source output impedance, all frequencies):
		Vin_high: 1.25 - 3.5V in 50 ohm load
		Vin_low: 0 - 0.8V in 50 ohm load
	Limits (low source output impedance, all frequencies):
		Vin_high: 1.25 - 3.6V
		Vin_low: 0 - 1.0V

Rev 2 - Trig/Time inputs
	Input impedance: 65 ohms at dc, 50 ohms above 10 kHz  (fc at 4 kHz)

	Limits (50 ohms source output impedance, all frequencies):
		Vin_high: 1.48 - 2.85V in 50 ohm load
		Vin_low: 0 - 1.05V in 50 ohm load
	Limits (low source output impedance, all frequencies):
		Vin_high: 1.5 - 3.2V
		Vin_low: 0 - 1.1V

Spice simulations:
	Vmax = 3.3V
	DC: < 100 Hz, AC: > 10 kHz
	Vref= 1.0V, V_high > 1.1V, Vlow < 0.9V

	Rev2 Clock/Sync
	1.9V, 50 ohms (0.8V in 50 ohms) => DC: 0.9V, AC: 0.85V
	2.5V, 50 ohms (1.25V in 50 ohms) => DC: 1.18V, AC: 1.11V
	7.0V, 50 ohms (3.5V in 50 ohms) => DC: 3.31V, AC: 3.11V

	1.0V, 0 ohms (1.0V in 50 ohms) => DC: 0.9V, AC: 0.85V
	1.25V 0 ohms (1.25V in 50 ohms) => DC: 1.12V , AC: 1.11V
	3.65V 0 ohms(3.65V in 50 ohms) => DC: 3.27V, AC: 3.25V

	Rev2 Trig/time
	Vmax = 2.5V
	2.1V 50 ohms (1.05V in 50 ohms)=> DC: 0.91V, AC: 0.79V (Vlow_max, limited by DC)
	2.95V 50 ohms (1.48V in 50 ohms)=> DC: 1.28V, AC: 1.10V (Vhi_min, limited by AC) (2.3V + 50 ohms (1.75V in 50 ohms) : DC: 1.00V)
	5.7V 50 ohms (2.85V in 50 ohms) => DC: 2.48V, AC: 2.12V
	1.1V 0 ohms (1.1V in 50 ohms)=> DC: 0.85V, AC: 0.82V
	1.5V 0 ohms (1.5V in 50 ohms) => DC: 1.16, AC: 1.12V
	3.2V 0 ohms (3.2V in 50 ohms) => DC 2.47V, AC: 2.40V

Rev2 clock/sync Examples:
	5V source with 50 ohms output impedance = 2.5V in 50 ohms = ok
	5V source with 50 ohms output impedance and dB attenuator or 1:2 splitter = 1.76V in 50 ohms = ok
	5V source with low output impedance = 5V in 50 ohms = might damage input!
	5V source with low output impedance and 3 dB attenuator = The source is not 50 ohms, so the attenuator might not attenuate 3dB! might damage input!
	3.3V/2.5V source, 50 ohms impedance = 1.65V/1.25V in 50 ohms = ok
	3.3V/2.5V source, low impedance= 3.3V/2.5V in 50 ohms
