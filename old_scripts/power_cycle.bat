:loop
"c:\Program Files\PowerUSB\PwrUsbCmd.exe" 0 0 0
TIMEOUT 15
"c:\Program Files\PowerUSB\PwrUsbCmd.exe" 1 0 0
TIMEOUT 15
PYTHON top_test_ramp.py
TIMEOUT 15
PYTHON top_test_ramp.py

goto loop