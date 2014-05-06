#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301

"""
fpga_firmware.py module
ORM object that describes the firmware that is associated with the FPGA.

 History:
        2014-03-07 JFC: Created
"""
import logging
import hashlib
import zlib
import logging
import os.path
import struct
import urllib2
import datetime

from hardware_map import HWMResource, Integer, Column, String, Binary, LargeBinary, DateTime, ForeignKey, UniqueConstraint, reconstructor, inspect
from fpga_core import FpgaCoreFirmware

class FpgaBitstream(HWMResource):
    """ Represents the firmware that is running or to be run on the IceBoard FPGA.

    The firmware is represented by a URL in the database, and is cached in
    memory when the object is created by the user or when the get_data()
    method is called if it not already loaded.

    If store_in_database is true, the bistream will also be stored in the
    database for future use.
    """

    __tablename__ = 'fpga_bitstream'
    # __mapper_args__ = {
    #         'polymorphic_on': 'firmware_class',
    #         'polymorphic_identity': 'fpgafirmware'
    # }

    pk = Column(Integer, primary_key=True)
    polymorphic_class_name = Column(String, nullable=False) # String that identifies the polymorphic_identity of the class needed to handle the firmware
    class_name = Column(String, nullable=False) # String that identifies the class of this object
    crc32 = Column(Integer)
    md5_string = Column(String)
    timestamp = Column(DateTime)
    url = Column(String) # URL where the binary can be found if not stored locally in the database
    bitstream = Column(LargeBinary)

    bitstream_cache = None
    _active_instances = {} # class attributes indicating which instances have been created

    def __init__(self, url, firmware_class):
        """ Creates a bitstream object from the file specified by
        """
        self.logger = logging.getLogger(__name__)

        polymorphic_identity = inspect(firmware_class).polymorphic_identity
        self.polymorphic_class_name = polymorphic_identity
        self.class_name = firmware_class.__name__
        self.url = url
        # If we manually create this bitstream object, we always fetch the
        # data immediately so we can get its CRC32 and other info and have a
        # cached version of it in memory.
        self.logger.info('Creating bitstream object explicitely')
        self._load_bitstream()

    @reconstructor
    def _init_from_database(self):
        """
        Re-create the firmware object from the database data.
        """
        #try to reload the bitstream
        self.logger = logging.getLogger(__name__)
        self.logger.info('Creating bitstream object from database')
        # we leave the local self.bistream set to None.
        # bitstream = FpgaBitFile(self.filename)
        # if bitstream.crc32 != self.bitstream.crc32:
        #     self.logger.warning('Bitstream does not have the expected CRC')
        # self.firmware_class = pickle.loads(self.firmware_class_pickle)

    def get_bitstream(self):
        """
        """
        if self.bitstream_cache:
            return self.bitstream_cache
        if self.bitstream:
            return self.bitstream
        self.logger.info('Reloading during get_bitstream')
        self._load_bitstream()
        return self.bitstream_cache

    def persist_bitstream(self):
        """ Copy the cashed bitstream to the database"""

        self.logger.info('Persisting bitstream')
        if not self.bitstream_cache:
            self._load_bitstream()
        self.bitstream = self.bitstream_cache

    def get_firmware_class(self):
        """ Return the class object that should be used to access the firmware
        functionnalities corresponding to this bistream.
        """
        return inspect(FpgaCoreFirmware).polymorphic_map[self.polymorphic_class_name].class_

    def update(self, bitstream_object):
        """ Update the current object with the data contained with the provided one."""
        if bitstream_object.bitstream_cache:
            self.bitstream_cache = bitstream_object.bitstream_cache

    BIN_PREFIX = 0xffffffffaa995566

    def _load_bitstream(self):
        """
        Loads the bitstream contained by the URL into the cache memory and fill the corresponding info fields.

        TODO:
           - check for 0xffffffffaa995566 prefix on the data.

        Notes:
            BIT file format described in http://www.fpga-faq.com/FAQ_Pages/0026_Tell_me_about_bit_files.htm
        """
        # self.filename = filename
        self.timestamp = None
        self.md5 = None
        self.valid = False
        self.logger.info('Reading file from URL %s ...' % self.url)
        if '://' in self.url:
            with urllib2.urlopen(self.url) as res:
                data = res.read()
        else:
             # Open as a file with relative path. mode='rb': b is important -> binary
             with open(self.url, 'rb') as file:
                data = file.read()
        self.logger.info('Read %0.3f Mbytes' % (len(data)/1e6))

        is_bin = struct.unpack('>Q',data[0:8])[0] == self.BIN_PREFIX

        if not is_bin:
            pos = 0
            # Field 1 - ignore
            length = struct.unpack('>H',data[pos:pos+2])[0]
            self.logger.debug('Field 1: 0x%s' % ''.join(['%0X' % ord(c) for c in data[pos+2:pos+2+length]]))
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
            fpga_model = data[pos+2+1:pos+2+1+length]
            self.logger.debug('Field 4 (tag=%s, length = %i bytes): %s' % (tag, length, fpga_model))
            pos += length + 2 + 1
            # Field 5
            tag = data[pos]
            length = struct.unpack('>H',data[pos+1:pos+2+1])[0]
            firmware_date = data[pos+2+1:pos+2+1+length]
            self.logger.debug('Field 5 (tag=%s, length = %i bytes): %s' % (tag, length, firmware_date))
            pos += length + 2 + 1
            # Field 6
            tag = data[pos]
            length = struct.unpack('>H',data[pos+1:pos+2+1])[0]
            firmware_time = data[pos+2+1:pos+2+1+length]
            self.logger.debug('Field 6 (tag=%s, length = %i bytes): %s' % (tag, length, data[pos+2+1:pos+2+1+length]))
            pos += length + 2 + 1
            # Field 7
            tag = data[pos]
            length = struct.unpack('>L',data[pos+1:pos+4+1])[0]
            self.logger.debug('Field 7 (tag=%s, length= %i bytes): [configuration data]' % (tag, length))
            pos += 4 + 1 # skip the header. Now points to cofiguration data
            self.bitstream_cache = data[pos:]

            self.timestamp_string = firmware_date + ' ' + firmware_time
            self.timestamp = datetime.datetime.strptime(firmware_date[:-1] + ' ' + firmware_time[:-1], '%Y/%m/%d %H:%M:%S')
            self.valid = True


        # compute MD5 sum as a hex string
        self.md5_string = hashlib.md5(self.bitstream_cache).hexdigest()
        # compute CRC32 of the data
        self.crc32 = zlib.crc32(self.bitstream_cache)

        return
