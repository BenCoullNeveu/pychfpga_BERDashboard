
""" Object that describes the firmware that is associated with the FPGA.
"""

import logging
import hashlib
import zlib
import struct
import urllib.request
import urllib.error
import urllib.parse
import datetime
import os
import base64

class FpgaBitstream(object):
    """ Object used to fetch and store FPGA bit files.

    The firmware is represented by a URL ( a file or a remote location), and
    is loaded in memory when needed.
    """

    crc32 = None
    md5_string = None
    timestamp = None
    timestamp_string = None
    url = None  # URL where the binary can be found
    bitstream_cache = None

    def __init__(self, url, load=True):
        """ Creates a bitstream object from the specified 'url', which can be
        a filename or a remote resource.

        If 'load' is true, the bitsream will be loaded in memory immediately,
        otherwise it will be loaded only when needed.
        """
        self.logger = logging.getLogger(__name__)

        self.url = url
        self.filename = os.path.split(self.url)[1]
        if load:
            self.load_bitstream()

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.filename)

    def __str__(self):
        """ Fetch and return the bitstream as a string.
        """
        if self.bitstream_cache:
            return self.bitstream_cache  # return from the cache
        self.logger.info('%r: Reloading during get_bitstream' % self)
        self.load_bitstream()
        return self.bitstream_cache

    def reload(self):
        """ Force the bitstream to be reloaded into the cache.

        This is useful to inform the system that the bitstream has changed.
        """
        self.load_bitstream()

    def load_bitstream(self):
        """
        Loads the bitstream contained by the URL into the cache memory and
        fill the corresponding info fields.

        Notes: BIT file format described in
             http://www.fpga-faq.com/FAQ_Pages/0026_Tell_me_about_bit_files.htm
        """
        BIN_PREFIX = 0xffffffffaa995566

        timestamp = None
        md5_string = None

        self.logger.info('%r: Reading file from URL %s ...' %
                         (self, self.url))
        if '://' in self.url:
            with urllib.request.urlopen(self.url) as res:
                data = res.read()
        else:
            # Open as a file with relative path. mode='rb': b is important ->
            # binary
            with open(self.url, 'rb') as file:
                data = file.read()
        self.logger.info('%r: Read %0.3f MBytes' % (self, len(data) / 1e6))

        is_bin = struct.unpack('>Q', data[0:8])[0] == BIN_PREFIX

        if not is_bin:
            pos = 0
            # Field 1 - ignore
            length = struct.unpack('>H', data[pos:pos+2])[0]
            self.logger.debug(
                '%r: Field 1: 0x%s' % (self, ''.join(
                    ['%0X' % c for c in data[pos+2: pos+2+length]]))
                )
            pos += length + 2
            # Field 2 - always 'a'
            length = struct.unpack('>H', data[pos:pos+2])[0]
            field = data[pos + 2: pos + 2 + length]
            self.logger.debug(
                '%r: Field 2 (%i bytes): %s' % (self, length, field))
            if field != b'a':
                self.logger.error('This is not a valid bit file')
                return
            pos += length + 2
            # Field 3
            length = struct.unpack('>H', data[pos:pos+2])[0]
            self.logger.debug(
                '%r: Field 3: %s' % (self, data[pos+2:pos+2+length]))
            pos += length + 2
            # Field 4
            tag = data[pos]
            length = struct.unpack('>H', data[pos+1: pos+2+1])[0]
            fpga_model = data[pos+2+1: pos+2+1+length]
            self.logger.debug(
                '%r: Field 4 (tag=%s, length = %i bytes): %s' %
                (self, tag, length, fpga_model))
            pos += length + 2 + 1
            # Field 5
            tag = data[pos]
            length = struct.unpack('>H', data[pos+1: pos+2+1])[0]
            firmware_date = data[pos+2+1: pos+2+1+length]
            self.logger.debug(
                '%r: Field 5 (tag=%s, length = %i bytes): %s' %
                (self, tag, length, firmware_date))
            pos += length + 2 + 1
            # Field 6
            tag = data[pos]
            length = struct.unpack('>H', data[pos+1: pos+2+1])[0]
            firmware_time = data[pos+2+1: pos+2+1+length]
            self.logger.debug(
                '%r: Field 6 (tag=%s, length = %i bytes): %s' %
                (self, tag, length, data[pos+2+1: pos+2+1+length]))
            pos += length + 2 + 1
            # Field 7
            tag = data[pos]
            length = struct.unpack('>L', data[pos+1: pos+4+1])[0]
            self.logger.debug(
                '%r: Field 7 (tag=%s, length= %i bytes): [data]' %
                (self, tag, length))
            pos += 4 + 1  # skip the header. Now points to cofiguration data
            bitstream = data[pos:]

            timestamp_string = firmware_date + b' ' + firmware_time
            timestamp = datetime.datetime.strptime(
                (firmware_date[:-1] + b' ' + firmware_time[:-1]).decode(),
                '%Y/%m/%d %H:%M:%S')

            # I thought the the remaining bitstream should start with the
            # proper cookie but there seems to be additional bytes before it.
            # So we disable the test.
            # prefix = struct.unpack('>Q', bitstream[0:8])[0]
            # if prefix != BIN_PREFIX:
            #     self.logger.error(
            #    '%r: This is not a valid bit file. Header is 0x%016X' %
            #     (self, prefix))

        else:
            bitstream = data

        self.bitstream_cache = bitstream
        self.bytes = bitstream
        self.base64 = base64.b64encode(bitstream)
        self.crc32 = zlib.crc32(bitstream)  # compute CRC32 of the data
        # Compute MD5 sum as a hex string
        self.md5_string = hashlib.md5(bitstream).hexdigest()
        self.timestamp_string = timestamp_string
        self.timestamp = timestamp
        return
