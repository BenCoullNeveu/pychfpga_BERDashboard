setmode -bscan
setCable -p auto
identify
assignfile -p 5 -file chfpga_v6.bit
program -p 5
quit
