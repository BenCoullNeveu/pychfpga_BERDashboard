#!/usr/bin/python

"""
socketIO.py module. Implements socket communications to chFPGA 


History:
	2011-08-14 JFC : Created from the code in chFPGA.py
	2011-09-18 JFC: Added socket timout variable
	2012-03-31 JFC: Removed manual ARP entry now that the firmware supports ARP protocol. Was a problem with Win 7 (running non-admin) and with a router.
"""

import socket
import os

timeout=socket.timeout #110918 JFC

class SocketIO_base(object):
	def __init__(self):

		# Defines basic variables
		
		self.OUT_IP="10.10.10.11"
		self.OUT_PORT=41000
		self.OUT_ADDR=(self.OUT_IP, self.OUT_PORT)
		self.OUT_MAC_ADDR='12-34-56-78-9a-bc'
		
		self.IN_IP="10.10.10.10";
		self.IN_PORT=41000;
		self.IN_PORT_DATA=self.IN_PORT+1;

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
		self.sock.bind((self.IN_IP, self.IN_PORT));
		self.sock_data.bind((self.IN_IP, self.IN_PORT_DATA));
		print 'Opened UDP Socket communications on %s:%i and %s:%i' % (self.IN_IP, self.IN_PORT, self.IN_IP, self.IN_PORT_DATA)


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

