import memtest_rs232
import pyftdi.serialext
import re
import serial

memtest = memtest_rs232.MemTestRS232(ftdi_url='ftdi://ftdi:232h:FTXQYGNU/1')

#memtest.setup_serial('ftdi://ftdi:232h:FTXQYGNU/1')
memtest.interupt_boot()

memtest.ser.write(b"dtc --version")
while True:
    response = memtest.ser.readline()
    numOfLines = numOfLines +1
    #Print anything that has visible characters
    m = re.search(b'[0-9A-Fa-f]', response)
    if m:
       print(response.decode('ascii', errors='ignore').strip())
