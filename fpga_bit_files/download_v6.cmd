setmode -bscan
setCable -p auto
identify
assignfile -p 2 -file chfpga_v6.bit
program -p 2
quit
