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

class ControlSocket_base(object):
	"""Creates an object that represents the control socket communication link to the chFPGA.""" 
	BUFFER_LENGTH = 32768
	
	def __init__(self, ip_address, port_number, netmask='255.255.0.0'):
		self.netmask = netmask # network mask used to find the host address that is on the same subnet as the target IP. This does not affect the network adapter settings.
		self.ip_address = ip_address
		self.port_number = port_number # Control port on the FPGA
		self.address = (self.ip_address, self.port_number)
		self.sock = None
		self.logger = logging.getLogger(__name__)

		self.open()
	def open(self):
		"""
		Open control communication socket to chFPGA. 
		"""
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.settimeout(2)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.BUFFER_LENGTH)
		host_addr = get_host_addr(dest_addr=self.ip_address, netmask=self.netmask)
		self.sock.bind((host_addr, self.port_number))
		self.logger.info('   Opened control UDP Socket')
		self.logger.info('   Control port: listening on %s:%i ' % (host_addr, self.port_number))


	def close(self):
		"""Closes the socket"""
		self.sock.close()
		self.logger.info('Closed UDP control socket')

	def write(self, data):
		"""
		Writes a string to the control socket.
		"""
		self.sock.sendto(data, self.address)

	def read(self):
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




class DataSocket_base(object):
	"""Creates an object that represents the control socket communication link to the chFPGA.""" 

	BUFFER_LENGTH = 32768

	def __init__(self, ip_address, port_number, netmask='255.255.0.0'):

		# Defines basic variables
		self.netmask = netmask # network mask used to find the host address that is on the same subnet as the target IP. This does not affect the network adapter settings.
		self.ip_address = ip_address # IP of the chFPGA board. Used to determine the host address 
		self.port_number = port_number # Data port on the host (Control port +1), to receive frame data
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
		host_addr = get_host_addr(dest_addr=self.ip_address, netmask=self.netmask)
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
		
