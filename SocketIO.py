#!/usr/bin/python

"""
socketIO.py module. Implements socket communications to chFPGA 


History:
 2011-08-14 : JFC : Created from the code in chFPGA.py
"""

import socket
import os

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

		os.system('arp -s %s %s %s' % (self.OUT_IP,self.OUT_MAC_ADDR,self.IN_IP)) # set ARP table to let the computer know that this Ip request shpuld be sent to this MAC address. chFPGA does respond to ARP requests...


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

	def read_data(self):
		self.sock_data.settimeout(0.1);
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
