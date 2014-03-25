"""
This module provide methods to access the functionnalities provided by the ARM processor on the McGill ICEBoard (MGK7MB) 
"""
import json, requests
import base64
import logging
import argparse
import os.path
import struct
import socket

# def _add_class_logger(future_class_name, future_class_parents, future_class_attr):
#     """
#     Intercepts the class definition process in all class of this module to automatically add a logger attribute with the name of the module/class.
#     """

#     future_class_attr['logger'] = logging.getLogger('%s.%s' % (__name__, future_class_name))
#     return type(future_class_name, future_class_parents, future_class_attr)



class ArmException(Exception):
    pass


class Arm(object):


    @staticmethod
    def ping_tuber(ip_address, port=80, timeout = 0.1):

        url = 'http://%s:%i/tuber' % (ip_address, port)

        result = False
        try:
            r=requests.post(url,'{}', headers={'Connection':'close'}, timeout=timeout)
            r.connection.close()
            result =  r.ok
        except requests.Timeout:
            pass
        return result

    @staticmethod
    def ping_tcp(ip_address, port=80, timeout = 0.1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        result = False
        try:
            s.connect((ip_address, port))
            s.close()
            result = True
        except socket.timeout:
            pass
        return result

    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.logger = logging.getLogger(__name__)
        # self.fpga_mmi = DirectFpgaMmi()
        # self.fpga_mmi.open()


    def configure_fpga(self, filename):
        """
        Configures the FPGA with the specified BIT or BIN file.
        """
        # filename='chFPGA_MGK7MB_Rev2_1channel_works.bit'
        # filename='chFPGA_MGK7MB.bin'
        # filename='chFPGA_MGK7MB_Rev2_GbEv14.bin'
        # IP='10.10.10.108'

        if isinstance(filename, str):
            bitfile = FpgaBitFile(filename)
        elif isinstance(filename, FpgaBitFile):
            bitfile = filename
        else:
            raise ArmException('Invalid argument. Pass either a FpgaBitFile object or a filename')

        url = 'http://%s/tuber' % self.ip_address

        # compute MD5 sub as a hex string
        md5_sum = bitfile.md5_string

        # Compute the base64-encoded string
        base64_string = base64.b64encode(bitfile.data)

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

    def hello(self, arg):
        print'Hello world with argument', arg, 'on ip ', self.ip_address
        return self.ip_address

    toto = 15
    def close(self):
        pass


    # """
    # ARM I2C access methods.
    # Accesses the I2C busses controlled by the ARM directly.
    # The methods are implemented by JSON commands and may be imported by Tuber.
    # """
    # i2c_ports = {'port':0
    # }

    # # Maybe the methods below should be part of a I2C class
    # def i2c_set_port(port_id):
    #     """
    #     Sets the I2C interface to enable access to the specified port(s).
    #     Multiple ports cans be enabled simultaneously.
    #     """
    #     pass

    # def i2c_write_read(i2c_addr, data=None, length=None):
    #     """
    #     Basic I2C access function. Can perform a single read command, write command, or a SMBUS-compatible write followed by a restart and a read. 
    #     """
    #     pass




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
