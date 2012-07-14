"""a very simple UDP test

Usage:

%(name)s client <remotehost<message to send|length of message>
to continuously send messages to <remotehostuntil Ctrl-C

%(name)s server
to listen for messages until Ctrl-C

Uses port %(port)d. Once stopped, shows some statistics.
Creates udpstress-client.csv or udpstress-server.csv with
pairs (size,time)
    
taken from:http://bytes.com/topic/python/answers/855727-problem-writing-fast-udp-server
    reply by Gabriel Genellina
"""

import os, sys
import socket
import time

PORT = 41001
BUFSIZE = 32768
socket.setdefaulttimeout(10.0)

def server(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('',port))
    print "Receiving at port %d" % (port)
    history = []
    print "Waiting for first packet to arrive...",
    sock.recvfrom(BUFSIZE)
    print "ok"
    t0 = time.time()
    while 1:
        try:
            try:
                data, remoteaddr = sock.recvfrom(BUFSIZE)
            except socket.timeout:
                print "Timed out"
                break
            except KeyboardInterrupt: # #1755388 #926423
                raise
            t1 = time.time()
            if not data:
                break
            history.append((len(data), t1-t0))
            t0 = t1
        except KeyboardInterrupt:
            print "Stopped"
            break
    sock.close()
    return history

def client(remotehost, port, data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    history = []
    print "Sending %d-bytes packets to %s:%d" % (len(data), remotehost,
                                                 port)
    t0 = time.clock()
    while 1:
        try:
            nbytes = sock.sendto(data, (remotehost,port))
            t1 = time.clock()
            if not nbytes:
                break
            history.append((nbytes, t1-t0))
            t0 = t1
        except KeyboardInterrupt:
            print "Stopped"
            break
    sock.close()
    return history

def show_stats(history, which):
    npackets = len(history)
    bytes_total = sum([item[0] for item in history])
    bytes_avg = float(bytes_total) / npackets
    bytes_max = max([item[0] for item in history])
    time_total = sum([item[1] for item in history])
    time_max = max([item[1] for item in history])
    time_min = min([item[1] for item in history])
    time_avg = float(time_total) / npackets
    speed_max = max([item[0]/item[1] for item in history if item[1]>0])
    speed_min = min([item[0]/item[1] for item in history if item[1]>0])
    speed_avg = float(bytes_total) / time_total
    print "Packet count %8d" % npackets
    print "Total bytes %8d bytes" % bytes_total
    print "Total time %8.1f secs" % time_total
    print "Avg size / packet %8d bytes" % bytes_avg
    print "Max size / packet %8d bytes" % bytes_max
    print "Max time / packet %8.1f us" % (time_max*1e6)
    print "Min time / packet %8.1f us" % (time_min*1e6)
    print "Avg time / packet %8.1f us" % (time_avg*1e6)
    print "Max speed %8.1f Kbytes/sec" % (speed_max/1024)
    print "Min speed %8.1f Kbytes/sec" % (speed_min/1024)
    print "Avg speed %8.1f Kbytes/sec" % (speed_avg/1024)
    print "Avg speed %8.1f Kbits/sec" % (speed_avg/1024*8)
    print
#    open("udpstress-%s.csv" % which,"w").writelines(
#                                                        ["%d,%f\n" % item for item in history])

#if len(sys.argv)>1:
#    if "client".startswith(sys.argv[1].lower()):
#        remotehost = sys.argv[2]
#        data = sys.argv[3]
#        if data.isdigit(): # means length of message
#            data = "x" * int(data)
#            history = client(remotehost, PORT, data)
#            show_stats(history, "client")
#            sys.exit(0)
#    elif "server".startswith(sys.argv[1].lower()):
history = server(PORT)
show_stats(history, "server")
