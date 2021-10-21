"""
Generate read/write command to access the FPGA's memory-mapped registers through its byte-serial bus (BSB) protocol.

"""

import logging
import numpy as np
from . import udp as udp


class FpgaMmiException(IOError):
    pass


class BSB_MMI:
    """
    Base class that defines the memory-mapped interface to the FPGA.

    Read/write commands are transmitted as a sequence of bytes, where the
    first 3 bytes contain the 3-bit command type, 2-bit read length and 19-bit
    target address. The command is then followed by the data to be written, if
    applicable.

    Read/writes operations can be performed in 3 different targets that share the same address space:
        Control registers (read/write)
        Status registers (read only)
        RAM or DRP (read/write)

    The read/write methods determine the target and select the appropriate operation code based on the upper bits of the address.
    """

    # Define address ranges of various targets. That will be used to map to the proper command.
    _CONTROL_BASE_ADDR = 0x000000  # Read/write control registers
    _STATUS_BASE_ADDR = 0x080000  # read-only status registers
    _RAM_BASE_ADDR = 0x100000  # RAM or DRP access (depends on firmware implementation)

    # MMI operations codes
    OPCODE_READ_CONTROL       = 0b000
    OPCODE_READ_NOP           = 0b001
    OPCODE_READ_STATUS        = 0b010
    OPCODE_READ_RAM           = 0b011
    OPCODE_WRITE_CONTROL      = 0b100
    OPCODE_WRITE_CONTROL_MASK = 0b101
    OPCODE_WRITE_NOP          = 0b110
    OPCODE_WRITE_RAM          = 0b111

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    def _send_command(self, cmd, expected_reply_length, **kwargs):
        """ Send a read or write command to the FPGA and check the reply for the correct
        sequence number and packet length. If unsuccessful, the command will
        be resent ``retry`` times.

        This method is used by the read() and write() methods.

        Parameters:

            cmd (bytes): command bytes to send

            expected_reply_length (int): Number of bytes we expect in the reply, excluding the
                1-byte header. This is used to validate the reply and retry if necessary.

        Returns:

            bytes: The content of the reply packet without the header.

        Exceptions:

            IOError: Raised if a valid reply cannot be obtained after the retries.

        """
        raise NotImplementedError('Subclass must define the send method')

    def read(self, addr, type=np.dtype('>u1'), length=1,
             timeout=None, retry=None, resync=True):
        """
        Reads memory-mapped byte(s) from the FPGA through the Ethernet
        interface.

        'length' values of type 'type' are read. The Reads will be done in the
        minimum number of requests in order to read all bytes.

        ``resync``: If True, the receiver will ignore command sequence number
        mismatches and will resynchronize the local counter with the value
        that was received. This is normally done only once when the system is
        initialized.

        Returns a numpy array of uint8 where the bytes are intrepreted as a series of
        'length' elements of type 'type'.

        2014-02-06 JFC: Now reads multiple bytes at a time to improve
        efficiency by using the length field in the command word.
        """

        itemsize = np.dtype(type).itemsize  # number of bytes contained in the destinaion vector type
        byte_length = length * itemsize  # total number of bytes to read
        dout = np.zeros(byte_length, np.int8)  # initialize result vector as a byte array
        offset = 0
        # Loop to read all required bytes (the FPGA does not support multi-byte reads (yet))

        if timeout:
            self.set_timeout(timeout)

        if addr & self._RAM_BASE_ADDR:
            opcode = self.OPCODE_READ_RAM
        elif addr & self._STATUS_BASE_ADDR:
            opcode = self.OPCODE_READ_STATUS
        else:
            opcode = self.OPCODE_READ_CONTROL

        while offset < byte_length:
            # compute the log2 of the number of bytes to read, limited to 3 (i.e. 8 bytes)
            log2_length = min((byte_length - offset).bit_length() - 1, 3)
            read_length = 1 << log2_length  # number of bytes to read in this iteration
            command_bytes = bytes([
                    (opcode << 5) | (log2_length << 3) + ((addr >> 16) & 0x07),  # byte 0: opcode, length, MSB of address
                    (addr >> 8) & 0xFF,  # byte 1: address
                    addr & 0xFF])  # Byte 2: LSB of address

            data = self._send_command(command_bytes, read_length, retry, resync)
            if retry is not None and retry < 0:
                self.logger.warning('%r: FPGA_MMI retry = %i' % (self, retry))
                return
            if offset + read_length > byte_length:
                raise IOError('%r: mmi.read(): Received too many bytes' % self)
            dout[offset: offset + read_length] = np.frombuffer(data, dtype=np.uint8)  # store received byte
            addr += read_length
            offset += read_length

        dout.dtype = np.dtype(type)  # change interpretation of the byte array into a 'type' array

        # If we requested a single value (length=1), returns the object,
        # otherwise return a numpy array of objects

        if len(dout) == 1:
            # print(f'mmi read dout={dout} -> {dout[0]}')
            return dout[0]
        else:
            # print(f'mmi read dout={dout} )')
            return dout


    def _to_bytes(self, data):
        # print(f'to_bytes data = {data}')
        if isinstance(data, bytes):
            return data
        elif isinstance(data, list):
            return bytes(data)
        elif isinstance(data, np.ndarray):
            return bytes(iter(data))
        elif isinstance(data, int):
            return bytes([data])
        elif isinstance(data, (np.uint32, np.uint16, np.uint8)):
            return data.newbyteorder('>').tobytes()  # store as big endian (most significant byte first)
        else:
            return bytes([data])

    def write(self, addr, data, mask=None, retry=None, resync=True):
        """
        Writes byte(s) to memory-mapped registers in the FPGA through the
        Ethernet interface.

        'data' can be:
            - String
            - list of integers between 0 and 255
            - numpy array of integers between 0 and 255
            - 4 bytes in a numpy uint32. MSB is transmitted first
            - 2 bytes in a numpy uint16. MSB is transmitted first
            - 1 byte in a numpy uint8.
        """


        if addr & self._RAM_BASE_ADDR:
            opcode = self.OPCODE_WRITE_RAM
        elif addr & self._STATUS_BASE_ADDR:
            raise FpgaMmiException(
                'FpgaMmi: Attempt to write to a STATUS register')
        elif mask is None:
            opcode = self.OPCODE_WRITE_CONTROL
        else:
            opcode = self.OPCODE_WRITE_CONTROL_MASK

        command_bytes = bytes((
            (opcode << 5) | ((addr >> 16) & 0x07),
            (addr >> 8) & 0xFF,
            addr & 0xFF))

        data_bytes = self._to_bytes(data)
        length = len(data_bytes)

        # If there is a mask, interleave the data with the masks
        if mask is not None:
            mask_bytes = self._to_bytes(mask)
            data_bytes = b''.join(
                [bytes((d, m)) for (d, m) in zip(data_bytes, mask_bytes)])
        self._send_command(command_bytes + data_bytes, 0, retry, resync)
        return length


