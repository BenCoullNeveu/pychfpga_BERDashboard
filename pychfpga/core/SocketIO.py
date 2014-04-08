#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
socketIO.py module. Implements socket communications to chFPGA 


History:
    2011-08-14 JFC : Created from the code in chFPGA.py
    2011-09-18 JFC: Added socket timout variable
    2012-03-31 JFC: Removed manual ARP entry now that the firmware supports ARP protocol. Was a problem with Win 7 (running non-admin) and with a router.
    2012-05-18 JFC: Let the code automatically determine the host computer IP address on which to open a listening port
"""

import socket
import logging
import numpy as np

timeout = socket.timeout #110918 JFC
TimeoutException = socket.timeout 

class FPGAException(Exception):
    logger = logging.getLogger('FPGAException')
    def __init__(self, message):
        super(self.__class__, self).__init__(message)
        self.logger.exception(message)


class ControlSocket_base(object):
    """Creates an object that represents the control socket communication link to the chFPGA.""" 
    BUFFER_LENGTH = 32768
    
    def __init__(self, ip_address, port_number=41000, netmask='255.255.0.0', host_ip=None):
        self.netmask = netmask # network mask used to find the host address that is on the same subnet as the target IP. This does not affect the network adapter settings.
        self.ip_address = ip_address
        self.port_number = port_number # Control port on the FPGA
        self.address = (self.ip_address, self.port_number)
        # self.host_ip = host_ip
        if host_ip:
            self.host_ip = host_ip
        else:
            self.host_ip = get_host_addr(dest_addr=self.ip_address, netmask=self.netmask)
        self.sock = None
        self.logger = logging.getLogger(__name__)

        # self.open()

    def open(self, broadcast = False):
        """
        Open control communication socket to chFPGA. 
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.BUFFER_LENGTH)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)

        if self.host_ip:
            host_addr = self.host_ip
        else:
            host_addr = get_host_addr(dest_addr=self.ip_address, netmask=self.netmask)
        self.sock.bind((host_addr, self.port_number))
        self.logger.info('   Opened control UDP Socket')
        self.logger.info('   Control port: listening on %s:%i ' % (host_addr, self.port_number))


    def close(self):
        """Closes the socket"""
        self.sock.close()
        self.logger.info('Closed UDP control socket')

    def sock_write(self, data):
        """
        Writes a string to the control socket.
        """
        self.sock.sendto(data, self.address)

    def sock_read(self):
        """
        Reads a string from the control socket.
        """
        data = self.sock.recv(self.BUFFER_LENGTH)
        return data


    def flush(self):
        """Flushes the socket receive buffer."""
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(0.1)
        try:
            while True:
                data = self.sock.recv(self.BUFFER_LENGTH)
                if len(data) == 0:
                    break
        except socket.timeout:
            pass # do nothing
            #print('Buffer is empty')
        self.sock.settimeout(old_timeout)

    def set_timeout(self, timeout):
        """
        Sets the socket timeout value in seconds.
        """
        self.sock.settimeout(timeout)

    def get_timeout(self):
        """
        Returns the current socket timeout value in seconds.
        """
        return self.sock.gettimeout()

    # def broadcast_open(self, interface_address):
    #     self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)



    def read(self, addr, type=np.dtype('>u1'), length=1, incr=1):
        """
        Reads memory-mapped byte(s) from the FPGA through the Ethernet interface.
        'length' values of type 'type' are read. The Reads will be done in the minimum number of requests in order to read all bytes.
        Returns a numpy array where the bytes are intrepreted as a series of 'length' elements of type 'type'.

        2014-02-06 JFC: Now reads multiple bytes at a time to improve efficiency by using the length field in the command word.
        """

        itemsize = np.dtype(type).itemsize # number of bytes contained in the destinaion vector type
        byte_length = length*itemsize ; # total number of bytes to read
        dout = np.zeros(byte_length, np.int8) # initialize result vector as a byte array
        offset = 0
        # Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))

        while offset < byte_length:
            log2_length = min((byte_length-offset).bit_length()-1,3) # compute the log2 of the number of bytes to read, limited to 3 (i.e. 8 bytes)
            read_length = 1<<log2_length # number of bytes to read in this iteration
            # print 'offset=', offset
            # print 'log2_length=', log2_length
            # print 'byte_length=', byte_length

            s = chr(0x00 + (0x40 if incr else 0) + (log2_length<<4) + ((addr >> 16) & 0x0F)) + chr((addr >> 8) & 0xFF) + chr(addr & 0xff)

            try:
                self.sock_write(s)
                data = self.sock_read()
            except Exception as e:
                raise FPGAException('FPGA read command failed because of the following exception: %s' % repr(e))
            #if data[0]!=s[0]:
            #    self.log.error("Read: ERROR: Returned ANT/SUB/ADDR (",   ata[0:2]," does not match request values (",   [0:2],")")
            if len(data) != read_length + 1:
                raise FPGAException("FPGA Read command returned %i bytes. %i were expected." % (len(data), read_length + 1))

            dout[offset:offset+read_length] = np.fromstring(data[1:], dtype=np.uint8) # store received byte

            if incr: 
                addr += read_length
            offset += read_length

        dout.dtype = np.dtype(type) # change interpretation of the byte array into a 'type' array

        #if we requested a single value (length=1), returns the object, otherwise return a numpy array of objects
        if len(dout) == 1:
            return dout[0]
        else:
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
        self.sock_write(string)
        return length



class DataSocket_base(object):
    """Creates an object that represents the control socket communication link to the chFPGA.""" 

    BUFFER_LENGTH = 32768

    def __init__(self, ip_address, port_number, netmask='255.255.0.0', host_ip=None):

        # Defines basic variables
        self.netmask = netmask # network mask used to find the host address that is on the same subnet as the target IP. This does not affect the network adapter settings.
        self.ip_address = ip_address # IP of the chFPGA board. Used to determine the host address 
        self.port_number = port_number # Data port on the host (Control port +1), to receive frame data
        self.host_ip = host_ip
        self.sock = None
        self.logger = logging.getLogger(__name__)

        self.open()

    def open(self):
        """
        Open data communication socket communications to chFPGA. This is a listen-only socket.
        """

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.BUFFER_LENGTH)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.host_ip:
            host_addr = self.host_ip
        else:
            host_addr = get_host_addr(dest_addr=self.ip_address, netmask=self.netmask)
        self.logger.debug('Using host address %s' % host_addr)
        self.sock.bind((host_addr, self.port_number))
        self.logger.info('Opened data UDP Socket')
        self.logger.info('    Data port:    listening on %s:%i ' % (host_addr, self.port_number))

    def close(self):
        """Closes the communication socket"""
        self.sock.close()
        self.logger.info('Closed UDP data socket')

    def flush(self):
        """Flushes the socket receive buffer."""
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(0.1)
        try:
            while True:
                data = self.sock.recv(self.BUFFER_LENGTH)
                if len(data) == 0:
                    break
        except socket.timeout:
            pass # do nothing
            #print('Buffer is empty')
        self.sock.settimeout(old_timeout)

    def read(self, timeout_delay=None): #110918 JFC: Added timeout_delay
        """
        Reads a string from the control socket.
        """
        if timeout_delay is not None:
            self.sock.settimeout(timeout_delay)
        else:
            self.sock.settimeout(0.1)
        
        data = self.sock.recv(self.BUFFER_LENGTH)
        return data


def get_host_addr(dest_addr, netmask='255.255.0.0', only_one=True):
    """
    Returns the IP of the host adapter that is on the same subnet as the specified destination IP given the net mask
    """
    host_data = socket.gethostbyname_ex(socket.gethostname()) # get the list of IP addresses associated with this computer
    host_addr_list = host_data[2] # get the list of IP addresses associated with this computer
    dest_addr_vect = np.array(map(ord, socket.inet_aton(dest_addr))) # convert the target IP into a vector
    netmask_vect = np.array(map(ord, socket.inet_aton(netmask))) # convert the net mask into a vector

    matched_addr = []
    for host_addr in host_addr_list:
        host_addr_vect = np.array(map(ord, socket.inet_aton(host_addr))) # convert the host address into a vector
        if all((host_addr_vect & netmask_vect) == (dest_addr_vect & netmask_vect)):
            matched_addr.append(host_addr)
    if only_one and len(matched_addr) != 1:
        raise SystemError('Could not determine the host address. Found %i possible matches for %s/%s on the following adapters for %s : %s' % (len(matched_addr), dest_addr, netmask, host_data[0], ', '.join(host_addr_list)))
    return matched_addr[0]
        

