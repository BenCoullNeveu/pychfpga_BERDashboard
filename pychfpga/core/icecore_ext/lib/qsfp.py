"""qsfp.py module: Provides a class to read/write to a QSFP cable
"""

# import iceboard as ib
import logging
from .eeprom import eeprom as EEPROM


class QSFP(object):
    """ Class defining the interface to a QSFP+ cable.
    """

    QSFP_EEPROM_MAP = {
         # Register Name : (datatype, memory location, bytes, page)
         'Identifier': ('bin', 0, 1, 0),
         'Status': ('bin', 1, 2, 0),
         'ChanStatusIntFlags': ('bin', 3, 2, 0),
         'ModMonIntFlags': ('bin', 6, 2, 0),
         'ChanMonIntFlags' : ('bin', 9, 4, 0),
         'MeasuredTemp' : ('bin', 22, 2, 0),
         'MeasuredSupV' : ('bin', 26, 2, 0),
         'ChanRxInPow': ('bin', 34, 8, 0),
         'ChanTxBias':('bin', 42, 8, 0),
         'LaserDisable':('bin', 86, 1, 0),
         'RateSelect':('bin', 87, 2, 0),
         'RxAppSelect':('bin', 89, 4, 0),
         'PowerSet':('bin', 93, 1, 0),
         'TxAppSelect':('bin', 94, 4, 0),
         'IntLMask_LOS':('bin', 100, 1, 0),
         'IntLMask_TXFault':('bin', 101, 1, 0),
         'IntLMask_Temp':('bin', 103, 1, 0),
         'IntLMask_Vcc':('bin', 104, 1, 0),
         'PageSelect':('bin', 127, 1, 0),

         'Identifier':('bin', 128, 1, 0),
         'ExtIdentifier':('bin', 129, 1, 0),
         'Connector':('bin', 130, 1, 0),
         'CompCodes':('bin', 131, 8, 0),
         'Encoding':('bin', 139, 1, 0),
         'BitRate':('bin', 140, 1, 0),
         'ExtRateSelectComp':('bin', 141, 1, 0),
         'SupportedLengths':('bin', 142, 5, 0),
         'DeviceTech':('bin', 147, 1, 0),
         'VendName':('str', 148, 16, 0),
         'ExtTranCode':('bin', 164, 1, 0),
         'VenOUI':('bin', 165, 3, 0),
         'VenPN':('str', 168, 16, 0),
         'VenRev':('bin', 184, 2, 0),
         'WaveLength':('bin', 186, 2, 0),
         'MaxCaseTemp':('bin', 190, 1, 0),
         'CCBase':('bin', 191, 1, 0),
         'ExtOptions':('bin', 192, 4, 0),
         'VenSN': ('str', 196, 16, 0),
         'DateCode':('str', 212, 8, 0),
         'DiagMon':('bin', 220, 1, 0),
         'EnhOpt':('bin', 221, 1, 0),
         'CCExt':('bin', 223, 1, 0),
         'VenSpecEEPROM':('str', 224, 32, 0)      #no idea if a string or binary info
         ##The other pages don't seem useful to us at all.
    }


    def __init__(self, i2c, bus_name, gpio, address=0x50):
        """ Create a QSFP object.

        `control_bits` is a dictionary defining:  {control_bit_name: (io_expander_object, register_number, bit_number, default), ... }
        Valid control bit names are: 'ModPrsL', 'ResetL', 'IntL', 'ModSelL', 'LPMode', 'Led'
        """
        self._logger = logging.getLogger(__name__)
        self._logger.debug('%.32r: Instantiating QSFP+ object' % self)

        self._i2c = i2c
        self._bus_name = bus_name
        self._address = address
        self._gpio = gpio

        self._qsfp_eeprom = EEPROM(self._i2c, bus_name=self._bus_name, address=self._address, address_width=8)

    def open(self):
        pass

    def close(self):
        pass

    def init(self):
        """Initializes the backplane hardware to a known state"""

    def set_control_bit(self, name, value, select=True):
        self._gpio.write(self._bus_name + '_' + name, value, select=select)

    def get_control_bit(self, name, select=True):
        return self._gpio.read(self._bus_name + '_' + name, select=select)

    def set_led(self, state):
        self.set_control_bit('Led', state)

    def get_led(self):
        return self.get_control_bit('Led')

    def reset(self, state=None):
        """
        Set the QSFP reset line state.

        The reset line is active if state=True. If state is omitted or is None
        the module is reset line is pulsed.
        """
        if state is None:
            self.set_control_bit('ResetL', 0)
            self.set_control_bit('ResetL', 1)
        else:
            self.set_control_bit('ResetL', not state)

    def status(self):
        """
        """
        return {bit_name: self.get_control_bit(bit_name) for bit_name in self._control_bits}

    def enable_i2c(self, enable):
        """
        Enables QSFP I2C  when enable = True
        """
        self.set_control_bit('ModSelL', not enable)

    def is_present(self):
        return not self.get_control_bit('ModPrsL')

    def write(self, addr, data, page=0, enable=True):

        if enable:
            self.enable_i2c(True)

        if page:
            self._qsfp_eeprom.write(addr=127, data=page, length=1)  # Writing to page select register

        self._qsfp_eeprom.write(addr, data) # Writing at specified address

        if page:
            self._qsfp_eeprom.write(addr=127, data=0, length=1)  # Putting page back to 0

        if enable:
            self.enable_i2c(False)


    def read(self, addr, length=1, page=0, enable=True):
        """
        Reads QSFP eeprom. Enables I2C, reads, Disables I2C
        """

        if enable:
            self.enable_i2c(True)

        if page:
            self._qsfp_eeprom.write(addr=127, data=page, length=1) #Writing to page select register

        data = self._qsfp_eeprom.read(addr=addr, length=length) #Reading at specified address

        if page:
            self._qsfp_eeprom.write(addr=127, data=0, length=1)  #Putting page back to 0

        if enable:
            self.enable_i2c(False)

        return data

    def read_str(self, addr=148, length=16, page=0):
        self.enable_i2c(True)
        data = ''.join([chr(x) for x in self.read(addr, length, page, enable=False)])
        self.enable_i2c(False)
        return data

    def get_info(self):
        """
        Gets all qsfp info marked up in the qsfp eeprom map for each slot
        Data is returned as a dictionary
        History:
        141015 AJG & JF: created
        """
        data = {}
        for (key, (datatype, addr, length, page)) in self.QSFP_EEPROM_MAP.items():
            if datatype == 'str': #String detected, converting to readable characters
                data[key] = self.read(addr=addr, length=length, page=page)
            else: #assuming binary
                data[key] = self.read(addr=addr, length=length, page=page)
        return data






































