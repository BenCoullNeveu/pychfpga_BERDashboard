#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: disable=C0301 

"""
ML605_LCD.py module 
 Implements  interface to the ML605 LCD display
#
# History:
    2012-07-25 JFC: Created from code in SYSMOD.py. 
        Modified to accept a gpio_instance at initialization and made DELAY global to the class. 
"""

import time

class LCD_base(object):
    """
    Provides a basic interface to the ML605 on-board LCD display.
    """
    DELAY = 2e-3 # Minimum delay (in seconds) to wait to ensure the LCD had time to process the command after a clock edge

    def __init__(self, gpio_instance):
        self.gpio = gpio_instance
        
    def status(self):
        """ Displays the status of the LCD."""
        print '-------------------------LCD--------------------------------------'
        print 'No status info'
        print '----------------------------------------------------------------------'


#    def lcd_read_write(self,dir=0, command=1, data=0):
#        self.LCD_RW=0 # Always write for now
#        self.LCD_RS=not command # 0 when a command

    def write_command(self, data):
        """ Writes a command byte to the LCD."""
        delay = self.DELAY # Minimum delay to wait to ensure the LCD had time to process the command 
        gpio = self.gpio

        gpio.LCD_RW = 0 # Always write for now
        gpio.LCD_RS = 0 # 0 when a command
        gpio.LCD_DATA = (data >> 4) & 0x0F # Send High nibble
        gpio.pulse_bit('LCD_E')
        time.sleep(delay)
        gpio.LCD_DATA = (data & 0x0F) # Send Low nibble
        gpio.pulse_bit('LCD_E')
        time.sleep(delay)

    def write_data(self, data):
        """ Writes a data byte to the LCD."""
        delay = self.DELAY # Minimum delay to wait to ensure the LCD had time to process the command 
        gpio = self.gpio
        gpio.LCD_RW = 0 # Always write for now
        gpio.LCD_RS = 1 # 1 for data
        gpio.LCD_DATA = (data >> 4) & 0x0F # Send High nibble
        gpio.pulse_bit('LCD_E')
        time.sleep(delay)
        gpio.LCD_DATA = (data & 0x0F) # Send Low nibble
        gpio.pulse_bit('LCD_E')
        time.sleep(delay)

    def write(self, string, col=None, row=None):
        """ Prints a string on the lcd. The column and row can optionally be specified. 
        If not, writing starts at last current position.
        """
        pos = 0x00
        if col is not None:
            pos += col
        if row is not None:
            pos += 0x40 * row
        if col is not None or row is not None:
            self.set_addr(pos)
        for char in string:
            print '.',
            self.write_data(ord(char))


    def clear(self):
        """ Clears the LCD display and set position to zero."""
        self.write_command(0b00000001) # Clear display, set address to zero

    def set_addr(self, addr):
        """ Sets the position to write data to the LCD."""
        self.write_command(0x80 + (addr & 0x7F)) # set address

    def define_char(self, char_number, bitmap):
        """ Defines the character 'char_number' with the provided 'bitmap'. Bitmap is an list of 8 bytes."""
        self.write_command(0x40 + (char_number << 3)) # set CG address
        for byte in bitmap:
            self.write_data(byte)

    def init(self):
        """ Initializes tle LCD and prints the default message."""
        # At this point we do not know which nibble we are writing if the device is in 4 bit mode. We switch back to 8 bits to reset the nibble counter. Tis might take 2 commands in the worst case.
        self.write_command(0b00110011)

        # Now we are in 8 bit interface, and we know that the next nibble will be the MSB. 
        # We send a last 8 bit interface command followed by a 4-bit  4 bit interface command.
        self.write_command(0b00110010)

        # We configure the LCD 

        self.write_command(0b00101100) # 4 bit mode, 2 lines, large font
        self.write_command(0b00001101) # Display on, cursor off, blinking on
        self.write_command(0b00000001) # Clear display, set address to zero
        #self.write_command(0b00000010) # Move cursor to 1st digit
        self.write_command(0b00000110) # Cursor move = increase, Shift=off

        # defines character 0, which is supposed to look like a little radiotelescope (just add a healthy dose of imagination)
        #self.define_char(0, (
        #    0b00010000 ,
        #    0b00011010 ,
        #    0b00011100 ,
        #    0b00011100 ,
        #    0b00000111 ,
        #    0b00000000 ,
        #    0b00000000 ,
        #    0b00000000 ) )

        #self.write('\000CHIME Pathfinder', col=0, row=0)
