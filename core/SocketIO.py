#!/usr/bin/python

"""
socketIO.py module. Implements socket communications to chFPGA 


History:
	2011-08-14 JFC : Created from the code in chFPGA.py
	2011-09-18 JFC: Added socket timout variable
	2012-03-31 JFC: Removed manual ARP entry now that the firmware supports ARP protocol. Was a problem with Win 7 (running non-admin) and with a router.
	2012-05-18 JFC: Let the code automatically determine the host computer IP address on which to open a listening port
"""

import socket
import os
import numpy as np

timeout=socket.timeout #110918 JFC

class SocketIO_base(object):
	def __init__(self):

		# Defines basic variables
		self.netmask='255.255.0.0' # network mask used to find the host address that is on the same subnet as the target IP. This does not affect the network adapter settings.
		self.OUT_IP="10.10.10.11"
		#self.OUT_IP="192.168.0.103" # if accessing from the WAN side of the router. Address is dynamic and may change over time.
		self.OUT_PORT=41000 # Control port on the FPGA
		self.OUT_ADDR=(self.OUT_IP, self.OUT_PORT)
		#self.OUT_MAC_ADDR='12-34-56-78-9a-bc' # Not needed anymore now that we have ARP
		
		self.IN_IP=None; # When None, the host address is automatically determined 
		self.IN_PORT=41000; # Control port on the host to receive command replies
		self.IN_PORT_DATA=self.IN_PORT+1; # Data port on the host (Control port +1), to receive frame data

	def open(self):
		"""
		Open Socket communications to chFPGA. Two sockets are open: one for control and one for data.
		"""
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM);
		self.sock.settimeout(2);

		self.sock_data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM);
		self.sock_data.settimeout(2);
		#		print self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
		err = self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768);
		err = self.sock_data.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768);
#		print self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
		if self.IN_IP is None:
			host_addr=self.get_host_addr(dest_addr=self.OUT_IP, netmask=self.netmask)
		else:
			host_name=self.IN_IP
		self.sock.bind((host_addr, self.IN_PORT));
		self.sock_data.bind((host_addr, self.IN_PORT_DATA));
		print 'Opened UDP Socket communications.'
		print '    Control port: listening on %s:%i ' % (host_addr, self.IN_PORT)
		print '    Data port:    listening on %s:%i ' % (host_addr, self.IN_PORT_DATA)


	def close(self):
		self.sock.close();
		self.sock_data.close();
		print 'Closed UDP Socket communications'

	def write_control(self,s):
		"""
		Writes a string to the control socket.
		"""
		self.sock.sendto(s,self.OUT_ADDR);

	def read_control(self):
		"""
		Reads a string from the control socket.
		"""
		data,client=self.sock.recvfrom(16384)
		return data

	def read_data(self,timeout_delay=0.1): #110918 JFC: Added timeout_delay
		self.sock_data.settimeout(timeout_delay);
		data,client=self.sock_data.recvfrom(16384);
		return data;


	def flush_control_socket(self):
#		print('Flushing socket buffer...');
		self.sock.settimeout(0.1);
		try:
			while True:
				data,client=self.sock.recvfrom ( 16384 );
				if len(data)==0:
					break;
		except:
			pass; # do nothing
			#print('Buffer is empty');
		self.sock.settimeout(1);

	def flush_data_socket(self):
#		print('Flushing socket buffer...');
		self.sock_data.settimeout(0.1);
		try:
			while True:
				data,client=self.sock_data.recvfrom ( 16384 );
				if len(data)==0:
					break;
		except:
			pass; # do nothing
			#print('Buffer is empty');
		self.sock_data.settimeout(1);

	def get_host_addr(self,dest_addr,netmask='255.255.0.0', only_one=True):
		"""
		Returns the IP of the host adapter that is on the same subnet as the specified destination IP given the net mask
		"""
		host_data=socket.gethostbyname_ex(socket.gethostname()) # get the list of IP addresses associated with this computer
		host_addr_list=host_data[2] # get the list of IP addresses associated with this computer
		dest_addr_vect=np.array(map(ord,socket.inet_aton(dest_addr))) # convert the target IP into a vector
		netmask_vect=np.array(map(ord,socket.inet_aton(netmask))) # convert the net mask into a vector
		
		matched_addr=[];
		for host_addr in host_addr_list:
			host_addr_vect=np.array(map(ord,socket.inet_aton(host_addr))) # convert the host address into a vector
			if all((host_addr_vect & netmask_vect)==(dest_addr_vect & netmask_vect)):
				matched_addr.append(host_addr)
		if only_one and len(matched_addr)!=1:
			raise SystemError('Could not determine the host address. Found %i possible matches for %s/%s on the following adapters for %s : %s' % (len(matched_addr),dest_addr,netmask, host_data[0], ', '.join(host_addr_list)))
		return matched_addr[0]
		
