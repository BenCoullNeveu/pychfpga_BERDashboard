"""
This module provide methods to access the functionnalities provided by the ARM processor on the McGill ICEBoard (MGK7MB) 
"""
import json, requests
import base64
import hashlib
import logging
import argparse
import os.path
import struct

class FpgaMmi:
    """
    Base class that defines the memory-mapped interface to the FPGA.
    This is used by Python code that handles the FPGA hardware directly (as opposed to handlers implemented into the ARM software)
    This is a virtual class. All methods hereis are meand to be overrided by implementation-specific derived class.

    Notes:
       - 140223 JFC: Maybe should define __enter__ and __exit__ so we can use with 'with'
       - 140223 JFC: Maybe add methods to allow packing multiple commands in a single packet. By default, the command queue is flushed at every write command.
    """

    def open():
        pass

    def close():
        pass

    def flush():
        """
        Sends any remaining read/write command that are pending in the command queue.
        """
        pass:

    def read(addr, type=np.uint32, length=1):
        """
        Reads 'length' values of type 'type' starting from address 'addr'
        """
        pass

    def write(addr, data, flush = True):
        """
        Writes data to the FPGA Memory-mapped space starting from address 'addr'.
        The command is immediately sent if 'flush' is true. Otherwise the command is simply queued.
        """
        pass
    def write_mask(addr, data, mask):
        """
        Writes data to the FPGA Memory-mapped space starting from address 'addr', but only affect bits that are set in mask.
        This function assumes that the memory location can be read back.
        """
        pass

class ArmFpgaMmi(FpgaMmi):
    """
    Provides access to the FPGA memory-mapped registers through the ARM processor.
    Two implementations are possible:
        Access is provided directly through the MMI socket (fastest)
        Access is provided through the JSON interface (safer?)
    """
    pass

class DirectFpgaMmi(FpgaMmi):
    """
    Provides access to the FPGA memory-mapped registers directly through the FPGA Ethernet link.
    """


class ARM(object):


    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.logger = logging.getLogger(__name__)
        self.fpga_mmi = DirectFpgaMmi()
        self.fpga_mmi.open()


    def configure_fpga(self, filename):
        """
        Configures the FPGA with the specified BIT or BIN file.
        """
        # filename='chFPGA_MGK7MB_Rev2_1channel_works.bit'
        # filename='chFPGA_MGK7MB.bin'
        # filename='chFPGA_MGK7MB_Rev2_GbEv14.bin'
        # IP='10.10.10.108'
        url = 'http://%s/tuber' % self.ip_address
        extension = os.path.splitext(filename)[1].split('.')[-1]
        extension = extension.lower()
        self.logger.debug('File type: %s' % extension)
        print extension
        self.logger.info('Reading file %s ...' % filename)
        with open(filename, mode='rb') as file: # b is important -> binary
            data = file.read()
        self.logger.info('Read %0.3f Mbytes' % (len(data)/1e6))

        if extension == 'bin':
            pass
        elif extension == 'bit':
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
            data = data[pos:]
        else:
            self.logger.error('unknown file extension "%s"' % extension)
            return

        # Compute the base64-encoded string
        base64_string = base64.b64encode(data)
        # compute MD5 sub as a hex string
        md5_sum = hashlib.md5(data).hexdigest()

        self.logger.debug('Encoded data starts with: %s' % base64_string[:32])
        self.logger.debug('Encoded data is %0.3f Mbytes long' % (len(base64_string)/1e6))
        self.logger.debug('MD5 sum is: %s' % md5_sum)

        json_command = '{"method":"load_fpga_bitstream","object":"iceboard","args":["%s","%s"]}' % (base64_string, md5_sum)

        self.logger.info('Sending configuration command data...')
        resp = requests.post(url=url, data = json_command)
        # print 'Response is: %s' % resp
        resp_dict = json.loads(resp.content)
        #print resp_dict
        # for (key,value) in resp_dict.items():
        #   print '%s = %s' % (key, repr(value))
        if resp_dict['error'] is None:
            self.logger.info('Programming successful')
        else:
            self.logger.error('Programming failed')
            self.logger.error('Error message: %s' % resp_dict['error']['message'])


    """
    ARM I2C access methods.
    Accesses the I2C busses controlled by the ARM directly.
    The methods are implemented by JSON commands and may be imported by Tuber.
    """
    i2c_ports = {'port':0
    }

    # Maybe the methods below should be part of a I2C class
    def i2c_set_port(port_id):
        """
        Sets the I2C interface to enable access to the specified port(s).
        Multiple ports cans be enabled simultaneously.
        """

    def i2c_write_read(i2c_addr, data=None, length=None):
        """
        Basic I2C access function. Can perform a single read command, write command, or a SMBUS-compatible write followed by a restart and a read. 
        """



if __name__ == '__main__':        

    log_levels = {'info': logging.INFO, 'debug': logging.DEBUG}
    
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('--ip', action = 'store', type=str, default='10.10.10.108', help='IP address of the ARM processor')
    parser.add_argument('-l', '--log_level', action = 'store', type=str, choices=log_levels.keys(), default='info', help='Logging level')
    parser.add_argument('-f','--filename', action = 'store', type=str, default=None, help='Program the FPGA with the specified bit/bin file ')
    args = parser.parse_args()


    logger = logging.getLogger(__name__)
    # logging.basicConfig(level=log_levels[args.log_level], format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')
    logging.basicConfig(level=log_levels[args.log_level], format='%(asctime)s %(name)-32s %(levelname)-10s : %(message)s')
    logger.info('------------------------')
    logger.info('ARM processor method')
    logger.info('J.-F. Cliche')
    logger.info('------------------------')
    logger.info('Using IP address %s' % args.ip)
    a = ARM(args.ip)
    logging.basicConfig(level=log_levels[args.log_level])

    if args.filename:
        a.configure_fpga(args.filename)
