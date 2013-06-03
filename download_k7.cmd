setmode -bscan
setCable -p auto
identify
assignfile -p 1 -file chFPGA_KC705.bit
program -p 1
quit
