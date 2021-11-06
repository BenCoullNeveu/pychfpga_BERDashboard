
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

class FPGABitstream(object):
    """ Object used to fetch and store FPGA bit files.

    The firmware is represented by a URL ( a file or a remote location), and
    is loaded in memory when needed.
    """

    DEFAULT_BITSTREAM_FOLDER = '../../fpga_bitstreams'
    bitstream_cache = {} # {url:file_data}

    def __init__(self, url, bitstream_folder=None):
        """ Creates a bitstream object from the specified 'url', which can be
        a filename or a remote resource.

        """
        self.logger = logging.getLogger(__name__)
        self.url = url
        self.bitstream_folder = bitstream_folder or self.DEFAULT_BITSTREAM_FOLDER
        self.load_time = None  # time at which the file was loaded
        self.file_mtime = None # Modification date of the file. Used to quickly determine if it should be reloaded.
        self.load_bitstream()

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.url)

    def reload(self):
        """ Force the bitstream to be reloaded into the cache.

        This is useful to inform the system that the bitstream has changed.
        """
        self.load_bitstream()

    def load_bitstream(self):
        """
        Loads the bitstream contained by the URL into the cache memory and
        fill the corresponding info fields.



        The raw data starts with a variable amount of pre-synchronization data
        (many FFFFFFFF with some other data in it). The length of the
        pre-synchroniation data block is a multiple of 32 bytes. We then find
        the AA995566 synchronization sequence.

        .BIN files contain only raw data.

        BIT files has a tag-length-data format that wraps a number for fields and the raw data.

        BIT file format described in
             http://www.fpga-faq.com/FAQ_Pages/0026_Tell_me_about_bit_files.htm

        - Field 1/2:  0x0009 0ff0 0ff0 0ff0 0ff0 0000 01 (cookie)
        - Field 3:  tag "a", 2-byte length, null-terminated string: filename optionally followed by semicolon-separated fields: UserID=0xFFFFFFFF, Version=2021.1
        - Field 4:  tag "b", 2-byte length, null-terminated string: part number
        - Field 5:  tag "c", 2-byte length, null-terminated string: date
        - Field 6:  tag "d", 2-byte length, null-terminated string: time
        - Field 7:  tag "e", 4-byte length, raw bitstream data

        Length are stored as big-endian.

        """
        HEADER_COOKIE = bytes.fromhex('0009 0ff0 0ff0 0ff0 0ff0 00 0001') # we include everything before tag 'a' in the cookie
        BIN_PREFIX = 0xffffffffaa995566  # not used. Amount of FFFF's is variable.

        timestamp = None
        md5_string = None

        self.logger.info(f'{self!r}: Reading file from URL {self.url} ...')
        if '://' in self.url:
            with urllib.request.urlopen(self.url) as res:
                data = res.read()
        else:
            # Open as a file with relative path. mode='rb': b is important ->
            # binary
            filename = os.path.join(
                os.path.dirname(__file__),
                self.bitstream_folder,
                self.url)
            mtime = os.path.getmtime(filename)
            print(f'mtime={mtime}')
            print(f'and = {self.url} in {self.bitstream_cache.keys()}')
            if (mtime == self.file_mtime) and (self.url in self.bitstream_cache):
                data = self.bitstream_cache[self.url]
            else:
                with open(filename, 'rb') as file:
                    data = file.read()
                self.file_mtime = mtime
                self.bitstream_cache[self.url] = data  # store data in cache

        self.logger.info(f'{self!r}: Bitstream size is {len(data)/1e6:0.3f} MBytes')

        if len(data) < 1e6:
            raise(f'Bitstream at {self.url} is too small. Is it a git LFS pointer? If so, make sure LFS is installed and then pull the binaries.')

        # Process if the headers if we see the header prefix pattern
        if data.startswith(HEADER_COOKIE):
            pos = len(HEADER_COOKIE)  # skip the header cookie

            # decoding helper functions
            def read_tag(tag):
                nonlocal pos
                assert data[pos] == ord(tag), f"The header field does of file {self.url} not have the expected tag '{tag}' (got '{chr(data[pos])}' instead. This is not a valid bit file"
                pos += 1

            def read_word(length):
                nonlocal pos
                word = int.from_bytes(data[pos:pos + length], 'big')
                pos += length
                return word

            def read_field(tag):
                nonlocal pos
                read_tag(tag)
                length = read_word(length=2)
                field = data[pos: pos + length]
                pos += length
                return field

            def read_string_field(tag):
                field = read_field(tag)
                assert field[-1] == 0, f"String of field '{tag}' in file {self.url} does not end with a null character. This is not a valid bit file"
                return field[:-1].decode('ascii')

            # Field 3 - tag 'a': filename and other info
            field = read_field('a')
            assert field[-1] == 0, "This is not a valid bit file"
            filename = field[:-1].decode('ascii')
            self.logger.debug(f'{self!r}: Tag a: File info = {filename}')

            # Field 4 - tag 'b': part number
            part_number = read_string_field('b')
            self.logger.debug(f'{self!r}: Tag b: part number = {part_number}')

            # Field 5 - tag 'c': date
            firmware_date = read_string_field('c')
            self.logger.debug(f'{self!r}: Tag c: firmware_date = {firmware_date}')

            # Field 6 - tag 'd': time
            firmware_time = read_string_field('d')
            self.logger.debug(f'{self!r}: Tag d: firmware_time = {firmware_time}')

            # Field 7 - tag 'e': bitstream
            read_tag('e')
            length = read_word(length=4)
            self.logger.debug(f'{self!r}: Tag e: Bitstream, length={length}')

            bitfile = data[pos:]

            timestamp_string = firmware_date + ' ' + firmware_time
            timestamp = datetime.datetime.strptime(
                firmware_date + ' ' + firmware_time,
                '%Y/%m/%d %H:%M:%S')
        else:
            bitfile = data

        self.timestamp_string = timestamp_string  # string
        self.timestamp = timestamp  # datetime object
        self.file_info = filename  # string with semicolon-separated fields
        self.part_number = part_number  # string

        self.file_bytes = data  # All the data in the file in bytes,  with header (if any)
        self.bytes = bitfile  # raw bitfile bytes
        self.raw_bitstream = bitfile  # raw bitfile bytes
        self.base64 = base64.b64encode(bitfile)
        self.crc32 = zlib.crc32(bitfile)  # compute CRC32 of the data
        self.md5_string = hashlib.md5(bitfile).hexdigest() # MD5 sum as a hex string

        return


# Alternate simplified version
# class FPGABitstream(object):
#     """ Helper object used to load and store a FPGA bitstream. You don't have
#     to use it, but it makes the code look nicer"""
#     bitstream = None

#     def __init__(self, filename, auto_reload=True):
#         self.filename = filename
#         self.auto_reload = auto_reload
#         if not self.auto_reload:
#             self._load()

#     def __str__(self):
#         """ Return the bitstream as a string. """
#         if self.auto_reload:
#             try:
#                 self._load()
#             except IOError:
#                 if not self.bitstream:
#                     raise
#         return self.bitstream

#     def _load(self):
#         with open(self.filename, 'rb') as file_:
#             self.bitstream = file_.read()
#         self.crc32 = zlib.crc32(self.bitstream) & 0xFFFFFFFF  # compute CRC32 of the data
#         self.base64 = base64.b64encode(self.bitstream)



