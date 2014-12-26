###################################################################
# Define clock timing constraints
###################################################################

create_clock -period 8.000 -name sfp_clk -waveform {0.000 4.000} [get_ports sfp_clk125_p]
