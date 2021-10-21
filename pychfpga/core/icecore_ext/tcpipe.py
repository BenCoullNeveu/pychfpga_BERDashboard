# Standard Python packages
import logging
import socket

class TCPipe:
    """ Interface to the TCP-based command and control protocol to the FPGA board.

    This interface is meant to be very simple and lightweight. It provides :
        - FPGA bitstream programming
        - Access to the ARM and FPGA firmware via AXI memory-mapped read/writes
        - Access to the FPGA firmware using a lightweight Byte-serial Bus protocol
        - Basic I2C read-write commands to access the board's hardware
    """

    CMD_PORT = 7

    RPC_PREFIX = 0xCC
    RPC_BSB_WRITE_READ = 0x00
    RPC_IIC_WRITE = 0x01
    RPC_IIC_WRITE_READ = 0x02
    RPC_IIC_READ = 0x03

    def __init__(self, hostname):
        self.hostname = hostname
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((hostname, self.CMD_PORT))
        self.tx_buf = bytearray(1024)
        self.tx_view = memoryview(self.tx_buf)
        self.rx_buf = bytearray(1024)
        self.rx_view = memoryview(self.rx_buf)

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
        self.sock.send(self.tx_view[:tx_len_data])
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
        self.sock.send(self.tx_view[:tx_len_data])
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
        self.tx_view[:tx_len] = bytes((self.RPC_PREFIX, self.RPC_BSB_WRITE_READ, len(data), 0))
        self.tx_view[tx_len:tx_len_data] = data
        self.sock.send(self.tx_view[:tx_len_data])
        rx_len = self.sock.recv_into(self.rx_buf)
        return self.rx_buf[:rx_len]

