# Standard Python packages
import logging
import socket

from .bsb_mmi import BSB_MMI

class TCPipe:
    """ Interface to the TCP-based command and control protocol to the FPGA board.

    This interface is meant to be very simple and lightweight. It provides :
        - FPGA bitstream programming
        - Access to the ARM and FPGA firmware via AXI memory-mapped read/writes
        - Access to the FPGA firmware using a lightweight Byte-serial Bus protocol
        - Basic I2C read-write commands to access the board's hardware
    """

    RPC_PREFIX = 0xCC
    RPC_BSB_WRITE_READ = 0x00
    RPC_IIC_WRITE = 0x01
    RPC_IIC_WRITE_READ = 0x02
    RPC_IIC_READ = 0x03

    def __init__(self, hostname, port=7, timeout=2):
        self.hostname = hostname
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect((hostname, self.port))
        self.tx_buf = bytearray(1024)
        self.tx_view = memoryview(self.tx_buf)
        self.rx_buf = bytearray(1024)
        self.rx_view = memoryview(self.rx_buf)
        self.firmware_crc = None

    def close(self):
        self.sock.close()
        self.sock = None

    def i2c_read(self, addr, read_length, no_error=False):
        tx_len = 6  # prefix, cmd, len_lsb, len_msb, addr, read_length
        self.tx_view[:tx_len] = bytes((self.RPC_PREFIX, self.RPC_IIC_READ, 2, 0, addr, read_length))
        self.sock.send(self.tx_view[:tx_len])
        rx_len = self.sock.recv_into(self.rx_buf)
        if self.rx_buf[0]:
            if no_error:
                return b''
            else:
                raise IOError(f'Reply has {rx_len} bytes but has error code {self.rx_buf[0]}')
        if rx_len < 1+read_length:
            raise IOError(f'did not receive enough bytes {rx_len} instead of {1+read_length}')
        return self.rx_buf[1:read_length + 1]


    # def rpc_call(self, command, length, reply_length=0):
    #     txv = self.tx_view
    #     txv[0] = self.RPC_PREFIX
    #     txv[1] = command
    #     txv[2] = len(header) + len(data)
    #     txv[3] = 0
    #     txv[4:4+len(header)] = header
    #     txv[4+len(header):4+len(header)+len(data)] = data

    def i2c_write_read(self, addr, data, read_length):
        """ Writes `data` to I2C address `addr`, perform a restart, and read `read_length` from the same device.

        Used for accessing devices such as EEPROMs that require a command or addres be sent in the same transaction before reading from the device.

        Parameters:

            addr (int): bits 6:0 is the I2C address. Bit 7 indiates whether we access IIC bus 0 or 1.

            data (bytes): data to write prior to the read operation

            read_length (int): number of bytes to read (1-255)

        """
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        cmd = bytes((self.RPC_PREFIX, self.RPC_IIC_WRITE_READ, 2 + len(data), 0, addr, read_length))
        tx_len = 6 # excluding data
        tx_len_data = tx_len + len(data)
        self.tx_view[:tx_len] = cmd
        self.tx_view[tx_len:tx_len_data] = data

        # print(f'Sending {self.tx_view[:tx_len_data]}')
        self.sock.sendall(self.tx_view[:tx_len_data])
        rx_len = self.sock.recv_into(self.rx_buf)
        if self.rx_buf[0]:
            raise IOError(f'Reply has error code {self.rx_buf[0]}')
        if rx_len != 1+read_length:
            raise IOError(f'Receive {rx_len} bytes instead of {1+read_length} bytes')
        return self.rx_buf[1:read_length+1]

    def i2c_write(self, addr, data):
        """ Writes `data` to I2C address `addr`.

        Used for accessing devices such as EEPROMs that require a command or addres be sent in the same transaction before reading from the device.

        Parameters:

            addr (int): bits 6:0 is the I2C address. Bit 7 indiates whether we access IIC bus 0 or 1.

            data (bytes): data to write prior to the read operation


        """
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)
        tx_len = 5 # excluding data
        tx_len_data = tx_len + len(data)
        self.tx_view[:tx_len] = bytes((self.RPC_PREFIX, self.RPC_IIC_WRITE, 1 + len(data), 0, addr))
        self.tx_view[tx_len:tx_len_data] = data
        self.sock.sendall(self.tx_view[:tx_len_data])
        rx_len = self.sock.recv_into(self.rx_buf)
        if self.rx_buf[0]:
            raise IOError(f'Reply has error code {self.rx_buf[0]}')
        if rx_len != 1:
            raise IOError(f'Receive {rx_len} bytes instead of 1 byte')

    def bsb_write_read(self, data):
        """ Writes `data` to the FPGA firmware Byte-serial bus and return reply.

        Used for accessing devices such as EEPROMs that require a command or addres be sent in the same transaction before reading from the device.

        Parameters:

            addr (int): bits 6:0 is the I2C address. Bit 7 indiates whether we access IIC bus 0 or 1.

            data (bytes): data to write prior to the read operation


        """
        tx_len = 4 # excluding data
        tx_len_data = tx_len + len(data)
        self.tx_view[:tx_len] = bytes((self.RPC_PREFIX, self.RPC_BSB_WRITE_READ, len(data) & 0xFF, len(data) >> 8))
        self.tx_view[tx_len:tx_len_data] = data
        self.sock.sendall(self.tx_view[:tx_len_data])
        rx_len = self.sock.recv_into(self.rx_buf)
        return self.rx_buf[:rx_len]

    def set_fpga_bitstream(self, data, crc=0, timeout=20):
        """ Programs the FPGA with the provided bitstream.

        Parameters:

            data (bytes): bitstream, without header, uncompressed. Sould be 34437356 bytes long for the ZU28.
        """

        print(f'TCPipe: Programming FPGA with {len(data)} bytes')

        assert len(data) == 34437356, "ZU28 bitstream should be 34437356 bytes long"

        old_timeout = self.sock.gettimeout()
        try:
            if timeout:
                self.sock.settimeout(timeout)  # Set a longer timeout since we are sending a lot of data
            self.sock.sendall(data)  # sendall will block if there s back pressure on the socket
            self.firmware_crc = crc
        except:
            self.firmware_crc = None
            raise
        finally:
            self.sock.settimeout(old_timeout)
        return

    def get_fpga_bitstream_crc(self):
        return self.firmware_crc

    def is_fpga_programmed(self):
        return True

class TCPipe_I2C:
    """
    Provides an I2C-over-TCPIPE interface using the standardized I2C object API.

    An instance of this object is passed to the I2C drivers to provide them the methods to access their hardware.
    """

    I2CException = IOError  # Exception object to expect from I2C communication errors

    def __init__(self, tcpipe, verbose=None):
        super().__init__()
        self.tcpipe = tcpipe
        self._logger = logging.getLogger(__name__)
        self.current_port = None;  # I2C port currently in use
        self.current_switch_params = {}  # keep track of switch params so we don't set the switch needlessly

    def select_bus(self, bus_info, retry=1):
        """
        Configure the I2C port and I2C switches so the following
        communications will access the desired I2C bus. 'bus_id'
        can be a bus name or bus number, or a list of those if
        multiple buses are to be accessed at the same time. An
        error will be provided if all the buses are not accessible
        through the same FPGA I2C port. This function assumes that
        each FPGA I2C port has an identical I2C switch.

        Parameters:

            bus_info (dict): Describes the port, switch and switch parameter
                - port (int): I2C port to use
                - switch (instance): switch instance
                - switch_params (int or dict): arguments to pass to the switch instance

            args, kwargs: passed to the bus select function

        Exceptions:

            IOError: Raised by an FPGA-based I2C controller in case of transaction errors

        """
        self.current_port = bus_info['port']
        switch = bus_info['switch']
        if not switch:
            return
        switch_params = bus_info['switch_params']
        if self.current_switch_params.setdefault(switch, None) == switch_params:
            return
        if isinstance(switch_params, dict):
            switch.set_port(**switch_params)
        else:
            switch.set_port(switch_params)
        self.current_switch_params[switch] = switch_params

    # def write_read(self, *args, **kwargs):
    def write_read(self, addr=0, data=[0], read_length=0, verbose=1, noerror=False, retry=1):
        """
        Writes and read to/from I2C device at address `addr`.


        Parameters:

            addr (int): I2C address

            data (list of int): list of bytes to write before the read operation. If ``None``, no write is performed.

            read_length (int): Number of bytes to read. Can be 0-4 after the a
                preceding write operation, or 0-3 without a write operation.

            verbose (int): verbosity level

            noerror (bool): if True, no exception will be raised

            retry (int): Number of times to retry a transfer before raising an exception

        Returns:
            bytearray containing the read bytes

        Exceptions:

            IOError: Raised by an FPGA-based I2C controller in case of transaction errors
            ValueError: Is raised when `addr`, `read>_length` or `write_length` are out of range.

        """
        # self._logger.debug("Accessing I2C bus...")

        addr |= 0x80 if self.current_port else 0

        if not data:  # if we have no data to write, just read
            return list(self.tcpipe.i2c_read(addr,read_length)) # list for backwards compatibility
        elif not read_length:  # if we have data to write but nothing to read
            return self.tcpipe.i2c_write(addr, data)
        else:  # if we both write and read
            return list(self.tcpipe.i2c_write_read(addr, data, read_length))

    def is_present(self, addr, bus_name=None):
        """ Test the presence of an I2C device at the specified address.

        Parameters:

            addr (int): I2C address of the device to query

            bus_name (str, int, or list of str or int): I2C bus(es) to activate

        """
        if bus_name:
            self.select_bus(bus_name, retry=3)
        try:
            self.write_read(addr, data=[], read_length=0, retry=0)  # dummy I2C acces
        except IOError:
            return False
        return True


class TCPipe_BSB_MMI(BSB_MMI):
    """
    Provides read/write functions for accessing the FPGA's memory-map registers through a
    Byte-serial Bus interface through the TCPipe interface.

    """
    # Maximum packet lengths, limited by the size of the FIFOs
    MAX_BSB_COMMAND_PACKET_LENGTH = 4096
    MAX_BSB_REPLY_PACKET_LENGTH = 16384
    def __init__(self, tcpipe):

        super().__init__()
        self.tcpipe = tcpipe
        self.send_counter = 0
        self.recv_counter = 0

    def _send_command(self, cmd, expected_reply_length, retry=1, resync=False, **kwargs):
        reply = self.tcpipe.bsb_write_read(cmd)
        if len(reply) != expected_reply_length + 1:
            raise IOError('Unexpected number of reply bytes')
        return reply[1:]

    def close(self):
        # self.tcpipe.close()
        pass