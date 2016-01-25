#!/usr/bin/env python

import json
import struct

PORT = 12345

class KotekanMessage(object):

    def __init__(self, type, **kws):
        self.type = type
        self.kws = kws

    def __str__(self):
        return ' '.join([self.type, str(self.uid), str(self.kws)])

    @classmethod
    def deserialize(klass, s):
        d = json.loads(s)
        t = d.pop('msg_type')
        uid = d.pop('msg_uid')
        msg = klass(t, **d)
        msg.uid = int(uid)
        return msg

    def serialize(self, uid):
        d = { 'msg_type' : self.type,
              'msg_uid'  : int(uid) }
        d.update(self.kws)
        return json.dumps(d)

#
# fake Kotekan server, for testing
#
if __name__ == '__main__':

    from twisted.internet import reactor
    from twisted.internet.protocol import Factory
    from twisted.protocols.basic import Int32StringReceiver

    class KotekanProtocol(Int32StringReceiver):

        def __init__(self, factory):
            self.factory = factory

        def sendMessage(self, msg):
            uid = self.factory.new_uid()
            s = msg.serialize(uid)
            self.sendString(s)

        def stringReceived(self, s):
            msg = KotekanMessage.deserialize(s)
            self.factory.receive_message(self, msg)

    class KotekanServerFactory(Factory):

        def __init__(self):
            self.uid = 0

        def buildProtocol(self, addr):
            return KotekanProtocol(self)

        def receive_message(self, prot, msg):
            print 'got', msg
            prot.sendMessage(KotekanMessage('ack', msg_recv_uid=msg.uid))

        def new_uid(self):
            self.uid = self.uid + 1
            return self.uid

    print "Starting fake kotekan..."
    from twisted.internet import reactor
    reactor.listenTCP(PORT, KotekanServerFactory())
    reactor.run()

