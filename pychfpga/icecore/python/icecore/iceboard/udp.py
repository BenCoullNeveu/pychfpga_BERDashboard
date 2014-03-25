#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
udp.py module 
Provides a class that represents a UDP socket 

 History:
        2014-03-04 JFC: Created
"""
import logging
import socket
import __main__ as main # used to store a list of all opened sockets

class Udp(object):
    """
    Implements basic UDP socket handling. 
    """

    BROADCAST = '255.255.255.255'
    BUFFER_LENGTH = 32768

    timeout = socket.timeout
    TimeoutException = socket.timeout

    def __init__(self):
        self.logger = logging.getLogger(__name__)


    def open(self, if_ip_addr, ip_addr, port_number):
        """
        Opens a UDP socket at specified IP address and port over the specified interface.
        If ip_addr is Udp.BROADCAST, a broadcast socket will be opened.
        """
        self.port_number = port_number
        self.ip_addr = ip_addr
        self.if_ip_addr = if_ip_addr
        self.address = (ip_addr, port_number)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # store the socket in the mail module so it will live persistently until the session is closed. Is used to close all sockets when debugging.
        if hasattr(main, '__opened_sockets__'):
            main.__opened_sockets__.add(self.sock)
        else:
            main.__opened_sockets__= set([self.sock])

        if ip_addr == self.BROADCAST:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
        # sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # don't use REUSEADDR: many sockets get open and we then fail to receive replies
        self.sock.bind((if_ip_addr, port_number))
        self.logger.debug('   Opened control UDP Socket')
        self.logger.debug('   Opened socket on interface  %s:%i ' % (if_ip_addr, port_number))
        return self.sock;

    def close(self):
        """Closes the socket"""
        if self.sock:
            self.sock.close()
            if hasattr(main, '__opened_sockets__'):
                main.__opened_sockets__.discard(self.sock)
            self.sock=None
        self.logger.debug('   Closed UDP control socket')

    def send(self, data):
        """
        Sends a string to the socket.
        """
        # print 'writing', data, 'to', self.address
        self.sock.sendto(data, self.address)

    def recv(self):
        """
        Reads a string from the socket.
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

    def is_broadcast(self):
        """
        Returns true if the current socket is set-up in broadcast mode.
        """
        return self.ip_addr == self.BROADCAST
