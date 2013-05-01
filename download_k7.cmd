setmode -bscan
setCable -p auto
identify
assignfile -p 2 -file chFPGA_KC705.bit
program -p 2
quit
