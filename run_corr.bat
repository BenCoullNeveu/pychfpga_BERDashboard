REM batch file to keep the correlator going after crashing
:LOOP
\Xilinx\14.1\ISE_DS\ISE\bin\nt64\impact.exe -batch download.cmd
python corr.py
goto LOOP