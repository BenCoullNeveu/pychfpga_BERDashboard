# -*- coding: utf-8 -*-

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor

# Here's a UDP version of the simplest possible protocol
class receiveUDP(DatagramProtocol):
	n_frames = 0
	t0 = time.time()
	def datagramReceived(self, datagram, address):
		verbose = 1
		frame_array=[]
		last_timestamp = 0
		last_delta = 0
		n = 0
		#expected_delta=self.ANT[0].PROBER.get_burst_period()
		#data = self.sock.read_data(timeout_delay=timeout)
		frame=Frame(datagram)
		self.n_frames += 1
		if verbose >= 1 and (not self.n_frames % 500):
			dt = (time.time()-self.t0)
			print 'Received %i frames at %f frames/s (%f Mb/s), ' % (self.n_frames, self.n_frames/dt, self.n_frames/dt*2048*8/1e6)
			self.t0 = time.time()
			self.n_frames = 0
#		if frame.timestamp != last_timestamp:
#			delta = frame.timestamp - last_timestamp
#			last_timestamp = frame.timestamp
#				
#			if verbose >= 2:
#				print 'Received %i frames with timestamp=%i (%f s), ' % (n+1, frame.timestamp, frame.timestamp*self.FRAME_PERIOD)
##					if delta != last_delta:
##						print 'Timestamp increased by %i frames instead of %i frames' % (delta, last_delta)
#			if delta != expected_delta:
#				print 'Timestamp increased by %i frames instead of %i frames' % (delta, expected_delta)
#			if n != 8-1:
#				print 'Received only %i frames on the same timestamp' % (n+1)
#			n = 0
#			last_delta = delta
#		else:
#			n += 1

def main():
    reactor.listenUDP(41001, receiveUDP())
    reactor.run()
		
