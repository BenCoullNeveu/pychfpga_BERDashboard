#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
fpga_mmi.py module
Provides access to the memory-mapped interface of the FPGA through a socket.

 History:
        2014-03-04 JFC: Created
"""
#import time
#import argparse
import logging
#import sys
#import struct
#import socket
#import re
import numpy as np
# from Module import Module_base, BitField
import udp

class FpgaMmiException(Exception):
    pass

class TimeoutException(Exception):
    pass

class FpgaMmi:
    """
    Base class that defines the memory-mapped interface to the FPGA either through a direct link to the FPGA or through the ARM direct-access socket.
    This is used by Python code that handles the FPGA firmware directly by toggling reading and writing to memopry-mapped registers.

    For now we implement only UDP sockets but TCP would work as well with minor changes. ZeroMQ sockets could probably be supported easily as well for efficient distribution of commands.
    TCP and ZeroMQ would work only through the ARM, through.

    Notes:
       - 140223 JFC: Maybe should define __enter__ and __exit__ so we can use with 'with'
       - 140223 JFC: Maybe add methods to allow packing multiple commands in a single packet. By default, the command queue is flushed at every write command.
    """
    BROADCAST = udp.Udp.BROADCAST
    PROTO_UDP = 'UDP'
    PROTO_TCP = 'TCP'
    PROTO_ZMQ = 'ZMQ'
    TimeoutException = TimeoutException

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.sock = None;

        if args or kwargs:
            self.open(*args, **kwargs)


    def __enter__(self):
            return self

    def __exit__(self, etype, einst, etraceback):
            self.close()


    def open(self, interface_ip_addr, ip_addr, port_number, send_only = False, netmask='255.255.0.0', timeout = 2):
        """
        Open control communication socket to FPGA
        """

        self.netmask = netmask # network mask used to find the host address that is on the same subnet as the target IP. This does not affect the network adapter settings.
        self.ip_addr = ip_addr
        self.port_number = port_number # Control port on the FPGA
        self.address = (self.ip_addr, self.port_number)
        self.interface_ip_addr = interface_ip_addr
        # if interface_ip_addr:
        #     self.interface_ip_addr = interface_ip_addr
        # else:
        #     self.interface_ip_addr = get_host_addr(dest_addr=self.ip_addr, netmask=self.netmask)

        self.sock = udp.Udp()
        self.sock.open(if_ip_addr=self.interface_ip_addr, ip_addr = self.ip_addr, port_number = self.port_number, send_only= send_only)
        self.sock.set_timeout(timeout)

        # self.logger.info('   Opened control socket on %s:%i through interface %s' % (self.ip_addr, self.port_number, self.interface_ip_addr))

    def close(self):
        """Closes the socket"""
        self.sock.close()
        # self.logger.info('Closed control socket')

    def flush(self):
        """Flushes the socket receive buffer."""
        old_timeout = self.sock.get_timeout()
        self.sock.set_timeout(0.1)
        try:
            while True:
                data = self.sock.recv()
                if len(data) == 0:
                    break
        except self.sock.TimeoutException:
            pass # do nothing
            #print('Buffer is empty')
        self.sock.set_timeout(old_timeout)

    def set_timeout(self, timeout):
        """
        Sets the socket timeout value in seconds.
        """
        self.sock.set_timeout(timeout)

    def get_timeout(self):
        """
        Returns the current socket timeout value in seconds.
        """
        return self.sock.get_timeout()


    def read(self, addr, type=np.dtype('>u1'), length=1, incr=1, timeout = None):
        """
        Reads memory-mapped byte(s) from the FPGA through the Ethernet interface.
        'length' values of type 'type' are read. The Reads will be done in the minimum number of requests in order to read all bytes.
        Returns a numpy array where the bytes are intrepreted as a series of 'length' elements of type 'type'.

        2014-02-06 JFC: Now reads multiple bytes at a time to improve efficiency by using the length field in the command word.
        """

        if self.sock.is_broadcast():
            raise Exception('standard read cannot be used in broadcast mode as there might be many returned values. Use broadcast_read() instead.')

        itemsize = np.dtype(type).itemsize # number of bytes contained in the destinaion vector type
        byte_length = length*itemsize ; # total number of bytes to read
        dout = np.zeros(byte_length, np.int8) # initialize result vector as a byte array
        offset = 0
        # Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))

        if timeout:
            old_timeout = self.get_timeout()
            self.set_timeout(timeout)

        while offset < byte_length:
            log2_length = min((byte_length-offset).bit_length()-1,3) # compute the log2 of the number of bytes to read, limited to 3 (i.e. 8 bytes)
            read_length = 1<<log2_length # number of bytes to read in this iteration
            # print 'offset=', offset
            # print 'log2_length=', log2_length
            # print 'byte_length=', byte_length

            s = chr(0x00 + (0x40 if incr else 0) + (log2_length<<4) + ((addr >> 16) & 0x0F)) + chr((addr >> 8) & 0xFF) + chr(addr & 0xff)

            try:
                self.sock.send(s)
                data = self.sock.recv()
            except self.sock.TimeoutException:
                raise self.TimeoutException
            except Exception as e:
                raise FpgaMmiException('FPGA read command failed because of the following exception: %s' % repr(e))
            #if data[0]!=s[0]:
            #    self.log.error("Read: ERROR: Returned ANT/SUB/ADDR (",   ata[0:2]," does not match request values (",   [0:2],")")
            if len(data) != read_length + 1:
                raise FpgaMmiException("FPGA Read command returned %i bytes. %i were expected." % (len(data), read_length + 1))

            dout[offset:offset+read_length] = np.fromstring(data[1:], dtype=np.uint8) # store received byte

            if incr:
                addr += read_length
            offset += read_length

        if timeout:
            self.set_timeout(old_timeout)

        dout.dtype = np.dtype(type) # change interpretation of the byte array into a 'type' array

        #if we requested a single value (length=1), returns the object, otherwise return a numpy array of objects
        if len(dout) == 1:
            return dout[0]
        else:
            return dout

    def broadcast_read(self, addr, type=np.dtype('>u8'), timeout=.5):
        """
        Reads memory-mapped object from multiple FPGAs through a broadcast request.
        Returns a array of type 'type' containing the values that were returned by all FPGAs.
        This command can read only a single object that is 1,2,4 or 8 bytes wide.
        """

        byte_length = np.dtype(type).itemsize # number of bytes contained in the destinaion vector type
        log2_length = byte_length.bit_length()-1 # compute the log2 of the number of bytes to read, limited to 3 (i.e. 8 bytes)
        read_length = 1<<log2_length # number of bytes to read in this iteration
        # dout = np.zeros(byte_length, np.int8) # initialize result vector as a byte array
        dout = []
        # Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))

        s = chr(0x40 + (log2_length<<4) + ((addr >> 16) & 0x0F)) + chr((addr >> 8) & 0xFF) + chr(addr & 0xff)

        self.sock.send(s)
        self.sock.set_timeout(timeout)
        while True:
            try:
                data = self.sock.recv()
                if data == s: # ignore the command packet that was broadcasted back to us
                    continue
            except self.sock.TimeoutException :
                break

            if len(data) != read_length + 1:
                raise FpgaMmiException("FPGA Read command returned %i bytes. %i were expected." % (len(data), read_length + 1))

            dout.append(np.fromstring(data[1:], dtype=type)[0]) # store received byte
        return dout

    def write(self, addr, data, incr=1):
        """
        Writes byte(s) to memory-mapped registers in the FPGA through the Ethernet interface.
        'data' can be:
            - String
            - list of integers between 0 and 255
            - numpy array of integers between 0 and 255
            - 4 bytes in a numpy uint32. MSB is transmitted first
            - 2 bytes in a numpy uint16. MSB is transmitted first
            - 1 byte in a numpy uint8.
        """
        # build command packet
        #s=chr(0x80+ant+(0x40 if incr else 0))+chr((module<<2)+(addr>>8))+chr(addr&0xFF)

        string = chr(0x80 + (0x40 if incr else 0) + ((addr >> 16) & 0x0F)) + chr((addr >> 8) & 0xFF) + chr(addr & 0xff)

        # Add the data to the string. The method depends on the data type
        if type(data) == str:
            string += data
            length = len(data)
        elif type(data) == list or type(data) == np.ndarray:
            string += ''.join([chr(data[i]) for i in range(len(data))])
            length = len(data)
        elif type(data) == np.uint32:
            length = 4
            a = np.array([data], np.dtype('>u4')) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            string += ''.join([chr(a[i]) for i in range(4)])
        elif type(data) == np.uint16:
            length = 2
            a = np.array([data], np.dtype('>u2')) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            string += ''.join([chr(a[i]) for i in range(2)])
        elif type([data]) == np.uint8:
            length = 1
            a = np.array([data]) # store as big endian (most significant byte first)
            a.dtype = np.uint8
            string += chr(a[i])
        else:
            string += chr(data)
            length = 1
        self.sock.send(string)
        return length

    def write_mask(addr, data, mask):
        """
        Writes data to the FPGA Memory-mapped space starting from address 'addr', but only affect bits that are set in mask.
        This function assumes that the memory location can be read back.
        """
        raise Exception('write_mask() is not supported by the current firmware')

