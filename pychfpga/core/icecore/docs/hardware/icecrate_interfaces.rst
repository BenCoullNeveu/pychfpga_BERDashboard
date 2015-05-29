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

