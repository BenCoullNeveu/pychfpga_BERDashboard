from numpy import *
from math import *
import pylab as plt
import time as tm
import os

print "**********************************************"
print "|I C E B O A R D  T E S T I N G  S C R I P T  |"
print "|A. Tang (qing.tang@mail.mcgill.ca)			 |"
print "|Version 1.0 								 |"
print "**********************************************"
tm.sleep(2)

print "Welcome fellow CHIME member to the Iceboard testing script!"
tm.sleep(1)
print "We'll need a few information from you... Please enter everything prompted below correctly."
tm.sleep(1)
print "What is your name?"
username = raw_input("Enter:	")
print "What is the serial number of the board? (e.g. 0009)"
board_sn = raw_input("Enter:	")
print "What is the version of this board? (e.g. V1)"
board vn = raw_input("Enter:	")
print "What is the model of this board?"
board_md = raw_input("Enter:	")


print "Thank you for entering the above! Is this your first time doing Iceboard QC testing?"
firsttime = raw_input("Enter (Y or N):	")
if (firsttime == Y) or (firsttime == y):
	print "To do the QC test, please ensure you have the following:	"
	notimportant = raw_input("Press Enter to continue:		")
	print "A multimeter\n A power supply\n Twisted pair cable with banana plugs on one side and probes on other (for power supply)\n JTAG cable\n "
	print "If you have any questions regarding the items above, please consult the website at 'https://' "
	notimportant = raw_input("Press Enter to continue:		")
	print "Please ensure this script is located under the file directory 'Boardtests'.\n"
	print "Please also ensure the template.txt file is located in this directory as well.\n"
	notimportant = raw_input("Press Enter to continue:		")
	print "This testing script consists of several tests listed below:\n"
	print "Inspection Test\n Resistance Test\n DC test\n Programming PLL\n Programming ARM\n Programming FPGA\n FMC Test \n GTX Test\n"
	print "It is highly suggested for you to perform the test in this order. Please begin performing a test by entering 'iceboardtest.TEST()' on ipython command line."
	print "Happy testing!"

def date_format(date):
    
    #finds the date, converts to string and adds 0 if <10 for day, month
    #day
    day=str(date[2])
    if int(day)<10:
        day ='0' + day
    #month
    month=str(date[1])
    if int(month)<10:
        month ='0' + month
    #year
    year=str(date[0])
    #hour
    hour=str(date[3])
    if int(hour)<10:
       hour ='0' + hour
    #minutes
    minute=str(date[4])
    if int(minute)<10:
        minute ='0' + minute
    
    #returns 'dd/mm/yyyy, hh:mm'
    return day + '/' + month + '/' + year + ', ' + hour + ':' + minute
