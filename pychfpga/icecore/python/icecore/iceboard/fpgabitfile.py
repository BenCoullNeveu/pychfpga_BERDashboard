"""
This module provides the FpgaBitFile class that represents a FPGA bitstream.

"""
import hashlib
import zlib
import logging
import os.path
import struct


class FpgaBitFile(object):
    """
    Represents an FPGA bit file.

    TODO:
       - check for 0xffffffffaa995566 prefix on the data.
       - store metadata in accessible atttributes.
    Notes:
        BIT file format described in http://www.fpga-faq.com/FAQ_Pages/0026_Tell_me_about_bit_files.htm
    """
    # __metaclass__ = _add_class_logger # intercept the default class creator (type(...)) with one that adds a 'logger' atttribute with a 'module.class' name (why this? The name of this class is not accessible in __name__ until the class creation is completed)

    def __init__(self, filename, loglevel = None):
        """
        Initializes the objects and loads the bit file into memory.
        """
        self.logger = logging.getLogger('%s.%s' % (type(self).__module__, type(self).__name__))
        if loglevel:
            self.logger.setLevel(loglevel)
        self.filename = None
        self.valid = False
        self.timestamp = None
        self.load(filename)
        self.md5 = None

    def load(self, filename):
        self.filename = filename
        self.valid = False
        extension = os.path.splitext(filename)[1].split('.')[-1]
        extension = extension.lower()
        self.logger.debug('File type: %s' % extension)
        # print extension
        self.logger.info('Reading file %s ...' % filename)
        with open(filename, mode='rb') as file: # b is important -> binary
            data = file.read()
        self.logger.info('Read %0.3f Mbytes' % (len(data)/1e6))

        if extension not in ['bit', 'bin']:
            self.logger.error('Unknown file extension "%s"' % extension)
            raise Exception('Unknown file extension')

        if extension == 'bit':
            pos = 0
            # Field 1 - ignore
            length = struct.unpack('>H',data[pos:pos+2])[0]
            self.logger.debug('Field 1: %s' % data[pos+2:pos+2+length])
            pos += length + 2
            # Field 2 - always 'a'
            length = struct.unpack('>H',data[pos:pos+2])[0]
            field = data[pos+2:pos+2+length]
            self.logger.debug('Field 2 (%i bytes): %s' % (length,field))
            if field != 'a':
                self.logger.error('This is not a valid bit file')
                return
            pos += length + 2
            # Field 3
            length = struct.unpack('>H',data[pos:pos+2])[0]
            self.logger.debug('Field 3: %s' % data[pos+2:pos+2+length])
            pos += length + 2
            # Field 4
            tag = data[pos]
            length = struct.unpack('>H',data[pos+1:pos+2+1])[0]
            self.logger.debug('Field 4 (tag=%s, length = %i bytes): %s' % (tag, length, data[pos+2+1:pos+2+1+length]))
            pos += length + 2 + 1
            # Field 5
            tag = data[pos]
            length = struct.unpack('>H',data[pos+1:pos+2+1])[0]
            self.logger.debug('Field 5 (tag=%s, length = %i bytes): %s' % (tag, length, data[pos+2+1:pos+2+1+length]))
            pos += length + 2 + 1
            # Field 6
            tag = data[pos]
            length = struct.unpack('>H',data[pos+1:pos+2+1])[0]
            self.logger.debug('Field 6 (tag=%s, length = %i bytes): %s' % (tag, length, data[pos+2+1:pos+2+1+length]))
            pos += length + 2 + 1
            # Field 7
            tag = data[pos]
            length = struct.unpack('>L',data[pos+1:pos+4+1])[0]
            self.logger.debug('Field 7 (tag=%s, length= %i bytes): [configuration data]' % (tag, length))
            pos += 4 + 1 # skip the header. Now points to cofiguration data
            self.data = data[pos:]
            self.valid = True

        # compute MD5 sum as a hex string
        self.md5_string = hashlib.md5(self.data).hexdigest()
        # compute CRC32 of the data
        self.crc32 = zlib.crc32(self.data)

        return
