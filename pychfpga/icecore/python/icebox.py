#!/usr/bin/python
# Disable pylint Line too long (=C0301)
# pylint: C0301

"""iceboard_hardware.py module: Provides a class to access the hardware of IceBoard
(McGill Model MGK7MB).
"""

import iceboard as ib
import logging
import time

# Import IceBoard hardware handlers
from lib.fmc_eeprom import FMC_EEPROM
from lib import ina230 # I2C Voltage and current monitor
from lib import tmp421 # I2C temperature sensor
from lib import pca9698 # I2C 40-bit IO Expander

class IceBoxException(Exception):
    pass
class IceBox(object):
    """
    Provides access to the IceBox (IceBoard backplane):
    """

    #------------------------------------
    # Define hardware-specific constants
    #------------------------------------
    NUMBER_OF_SLOTS = 16 #
    BACKPLANE_EEPROM_DATA_ADDRESS = 0x54 # covers 0x54 - 0x57 ( 4 pages of 256 bytes, 1024 Bytes total)
    BACKPLANE_EEPROM_SERIAL_ADDRESS = 0x5C # 16 byte serial number starting at memory address 0x80
    BACKPLANE_EEPROM_ADDRESS_WIDTH = 10 # 2 bits are in the device address, the remaining are in the address byte following the command byte

    BACKPLANE_QSFP_ADDRESS=0x50 #QSFP standard address
    BACKPLANE_QSFP_ADDRESS_WIDTH=8


    _QSFP_CTRL_SETA_ADDR = 0b0100000
    _QSFP_CTRL_SETB_ADDR = 0b0100010
    _RESETS_CTRL_ADDR = 0b0100100

    _TMP_SLOT1_ADDR = 0x4E
    _TMP_SLOT16_ADDR = 0x4D

    _POWER_3V3_ADDR = 0x40

    # The following dictionnary describes the connectivity of the 10 Gbps mesh.
    # It indicates which transmitter (slot and lane number) is feeding a specified receiver.
    # The dictionnary is indexed by receiver number.
    _BP_RX_TO_TX_MAP = {
        # (rx_slot, rx_lane) <= (tx_slot_tx_lane)
        # Slots are numbered from 1 to 16
        # Lanes are numbered from 0 to 15. Lane 0 is internal to the FPGA.

        (1,0):(1,0), # direct internal link in FPGA
        (1,1):(12,1), (1,2):(10,11),  (1,3): (9,15),  (1,4): (6,8),  (1,5): (5,2),  (1,6): (3,8), (1,7): (8,6), (1,8):(2,10),
        (1,9):(15,3), (1,10):(16,11), (1,11):(11,13), (1,12):(14,5), (1,13):(13,1), (1,14):(4,7), (1,15):(7,13),

        (2,0):(2,0), # direct internal link in FPGA
        (2,1):(11,11), (2,2) :(16,7),  (2,3) :(12,13),  (2,4) :(6,14),  (2,5) :(5,4),  (2,6) :(15,5), (2,7) :(8,2), (2,8):(3,10),
        (2,9):(14,7),  (2,10):(13,2),  (2,11):(10,13),  (2,12):(9,13),  (2,13):(1,6),  (2,14):(4,8),  (2,15):(7,15),

        (3,0):(3,0), # direct internal link in FPGA
        (3,1):(9,12), (3,2):(12,14), (3,3):(14,11), (3,4):(11,12), (3,5):(5,8), (3,6):(2,6), (3,7):(8,4), (3,8):(4,10), (3,9):(6,4),
        (3,10):(1,4), (3,11):(15,11), (3,12):(16,12), (3,13):(10,15), (3,14):(13,4), (3,15):(7,14), (4,1):(15,2),


        (4,0):(4,0), # direct internal link in FPGA
        (4,2):(16,2), (4,3):(11,1), (4,4):(6,2), (4,5):(12,2), (4,6):(3,6), (4,7):(8,12), (4,8):(5,10), (4,9):(2,2),
        (4,10):(1,2), (4,11):(13,11), (4,12):(9,14), (4,13):(10,14), (4,14):(14,2), (4,15):(7,4),


        (5,0):(5,0), # direct internal link in FPGA
        (5,1):(9,2),  (5,2):(16,15), (5,3):(13,15),  (5,4):(15,15),  (5,5):(14,15), (5,6):(3,4),    (5,7):(8,8),  (5,8):(6,10),
        (5,9):(2,11), (5,10):(1,1),  (5,11):(10,12), (5,12):(11,14), (5,13):(4,6),  (5,14):(12,15), (5,15):(7,8),

        (6,0):(6,0), # direct internal link in FPGA
        (6,1):(16,5), (6,2):(15,13), (6,3):(9,4), (6,4):(14,14), (6,5):(13,5), (6,6):(3,2), (6,7):(8,9), (6,8):(7,10),
        (6,9):(2,12), (6,10):(1,11), (6,11):(10,2), (6,12):(12,4), (6,13):(5,6), (6,14):(4,4), (6,15):(11,4),


        (7,0):(7,0), # direct internal link in FPGA
        (7,1):(16,9), (7,2):(15,9), (7,3):(13,7), (7,4):(14,9), (7,5):(5,11), (7,6):(3,1), (7,7):(6,6), (7,8):(8,10),
        (7,9):(2,13), (7,10):(1,12), (7,11):(9,8), (7,12):(12,10), (7,13):(10,4), (7,14):(4,2), (7,15):(11,15),


        (8,0):(8,0), # direct internal link in FPGA
        (8,1):(6,11), (8,2):(16,8), (8,3):(14,8), (8,4):(15,8), (8,5):(5,12), (8,6):(3,11), (8,7):(7,6), (8,8):(9,10),
        (8,9):(2,14), (8,10):(1,13), (8,11):(10,8), (8,12):(13,8), (8,13):(12,8), (8,14):(4,1), (8,15):(11,8),

        (9,0):(9,0), # direct internal link in FPGA
        (9,1):(6,12), (9,2):(14,6), (9,3):(15,6), (9,4):(16,6), (9,5):(5,13), (9,6):(3,12), (9,7):(8,13), (9,8):(10,10),
        (9,9):(2,15), (9,10):(1,14), (9,11):(12,6), (9,12):(13,6), (9,13):(11,6), (9,14):(4,11), (9,15):(7,12),


        (10,0):(10,0), # direct internal link in FPGA
        (10,1):(6,13), (10,2):(4,12), (10,3):(7,2), (10,4):(8,14), (10,5):(5,15), (10,6):(3,13), (10,7):(9,6),
        (10,8):(11,10), (10,9):(2,1), (10,10):(1,15), (10,11):(16,14), (10,12):(15,14), (10,13):(14,13), (10,14):(13,14), (10,15):(12,11),

        (11,0):(11,0), # direct internal link in FPGA
        (11,1):(5,1), (11,2):(7,11), (11,3):(8,11), (11,4):(9,11), (11,5):(6,15), (11,6):(3,14), (11,7):(10,6),
        (11,8):(12,7), (11,9):(2,5), (11,10):(1,3), (11,11):(4,13), (11,12):(16,4), (11,13):(15,4), (11,14):(14,4), (11,15):(13,13),

        (12,0):(12,0), # direct internal link in FPGA
        (12,1):(7,1), (12,2):(8,1), (12,3):(9,1), (12,4):(10,1), (12,5):(5,14), (12,6):(3,15), (12,7):(11,2),
        (12,8):(13,10), (12,9):(2,7), (12,10):(1,5), (12,11):(15,1), (12,12):(16,1), (12,13):(14,1), (12,14):(4,14), (12,15):(6,1),

        (13,0):(13,0), # direct internal link in FPGA
        (13,1):(7,7), (13,2):(8,7), (13,3):(9,7), (13,4):(10,7), (13,5):(11,7), (13,6):(3,5), (13,7):(12,12),
        (13,8):(14,10), (13,9):(2,9), (13,10):(1,7), (13,11):(16,3), (13,12):(5,7), (13,13):(15,7), (13,14):(4,15), (13,15):(6,7),

        (14,0):(14,0), # direct internal link in FPGA
        (14,1):(7,5), (14,2):(8,5), (14,3):(9,5), (14,4):(10,5), (14,5):(11,5), (14,6):(12,5), (14,7):(13,12),
        (14,8):(15,10), (14,9):(2,8), (14,10):(1,9), (14,11):(5,5), (14,12):(6,5), (14,13):(4,5), (14,14):(3,7), (14,15):(16,13),


        (15,0):(15,0), # direct internal link in FPGA
        (15,1):(8,15), (15,2):(9,9), (15,3):(10,9), (15,4):(11,9), (15,5):(12,9), (15,6):(13,9), (15,7):(14,12),
        (15,8):(16,10), (15,9):(2,4), (15,10):(1,10), (15,11):(6,9), (15,12):(7,9), (15,13):(5,9), (15,14):(4,9), (15,15):(3,9),


        (16,0):(16,0), # direct internal link in FPGA
        (16,1):(8,3), (16,2):(9,3), (16,3):(10,3), (16,4):(11,3), (16,5):(12,3), (16,6):(13,3), (16,7):(15,12),
        (16,8):(14,3), (16,9):(7,3), (16,10):(1,8), (16,11):(5,3), (16,12):(6,3), (16,13):(4,3), (16,14):(3,3), (16,15):(2,3)
    }

    _BP_TX_TO_RX_MAP = {tx:rx for (rx,tx) in _BP_RX_TO_TX_MAP.items()}


    @classmethod
    def get_backplane_info(cls, iceboard):
        logger = logging.getLogger(__name__)
        logger.debug("Attempting to read backplane eeprom to determine board presence")
        eeprom = FMC_EEPROM(iceboard.i2c, 'BP', address=cls.BACKPLANE_EEPROM_DATA_ADDRESS, address_width=cls.BACKPLANE_EEPROM_ADDRESS_WIDTH)
        data = eeprom.read(0, length=1, noerror=True, verbose=1)
        logger.debug("Backplane EEPROM returned the value: %i", data[0])
        return (data[0], None)

    @classmethod
    def get_matching_tx(cls, rx_slot_lane_tuple):
        return cls._BP_RX_TO_TX_MAP[rx_slot_lane_tuple]

    @classmethod
    def get_matching_rx(cls, tx_slot_lane_tuple):
        return cls._BP_TX_TO_RX_MAP[tx_slot_lane_tuple]

    def __init__(self, iceboard):
        """
        Creates all the I2C objects needed to interface the hardware.
        For now, we can only do this when the FPGA is configured
        because access is done through the FPGA.

        For FPGA-based I2C:
            - fpga_core is not Null
            - fpga_core provides the following methods
                - i2c_set_port(...) # Port number 0 (connected to the FPGA I2C switch) is used for all accesses
                - i2c_write_read(...) # FPGA I2C engine
        """
        
        #import iceboard  as ib     
        #if not isinstance(iceboard, ib.IceBoard):
        #    raise IceBoxException('Please provide a single iceboard object')
       
        try:
            iter(iceboard)
        except TypeError:
            pass
        else:
            raise IceBoxException('Please provide a single iceboard object')
#
#        if type(iceboard)!=ib.IceBoard:
#            raise IceBoxException('Please provide a single iceboard object')
#


        self._I2C_BACKPLANE_BUS_NAME = 'BP'
        self._logger = logging.getLogger(__name__)
        self._logger.debug('Initializing Iceboard hardware')
        self._i2c = iceboard.i2c
        self._iceboard_hw = iceboard.hw
        self._iceboard = iceboard

        self._logger.info(' Instantiating Backplane I2C resource managers')
        self._eeprom = FMC_EEPROM(iceboard.i2c, 'BP', address=self.BACKPLANE_EEPROM_DATA_ADDRESS, address_width=self.BACKPLANE_EEPROM_ADDRESS_WIDTH)
        self._serial = FMC_EEPROM(iceboard.i2c, 'BP', address=self.BACKPLANE_EEPROM_SERIAL_ADDRESS, address_width=self.BACKPLANE_EEPROM_ADDRESS_WIDTH)
        self._qsfp_eeprom = FMC_EEPROM(iceboard.i2c, 'BP', address=self.BACKPLANE_QSFP_ADDRESS, address_width=self.BACKPLANE_QSFP_ADDRESS_WIDTH)

        self._logger.info(' Instantiating Backplane I2C temperature sensors')
        self._tmp_slot1 = tmp421.tmp421(self._i2c, self._TMP_SLOT1_ADDR, 'BP')
        self._tmp_slot16 = tmp421.tmp421(self._i2c, self._TMP_SLOT16_ADDR, 'BP')

        self._logger.info(' Instantiating Backplane I2C current/power monitor')
        self._power_3v3 = ina230.ina230(self._i2c, self._POWER_3V3_ADDR, 'BP')

        self._logger.info(' Instantiating Backplane I2C I/O expanders')
        self._qsfp_ctrla = pca9698.pca9698(self._i2c, self._QSFP_CTRL_SETA_ADDR, 'BP')
        self._qsfp_ctrlb = pca9698.pca9698(self._i2c, self._QSFP_CTRL_SETB_ADDR, 'BP')
        self._reset_ctrl = pca9698.pca9698(self._i2c, self._RESETS_CTRL_ADDR, 'BP')


        self.QSFP_CTRL_MAP = {
             # Slot num : (expander object, Register, bit number ModPrs, bit number Reset, bit number IntL, bit number ModSel)
             1: (self._qsfp_ctrla, 2,    0,1,2,3 ),
             2: (self._qsfp_ctrla, 2,    4,5,6,7 ),
             3: (self._qsfp_ctrla, 1,    0,1,2,3 ),
             4: (self._qsfp_ctrla, 1,    4,5,6,7 ),
             5: (self._qsfp_ctrla, 0,    0,1,2,3 ),
             6: (self._qsfp_ctrla, 0,    4,5,6,7 ),
             7: (self._qsfp_ctrla, 3,    0,1,2,3 ),
             8: (self._qsfp_ctrla, 3,    4,5,6,7 ),

             9:  (self._qsfp_ctrlb, 2,   0,1,2,3 ),
             10: (self._qsfp_ctrlb, 2,   4,5,6,7 ),
             11: (self._qsfp_ctrlb, 1,   0,1,2,3 ),
             12: (self._qsfp_ctrlb, 1,   4,5,6,7 ),
             13: (self._qsfp_ctrlb, 0,   0,1,2,3 ),
             14: (self._qsfp_ctrlb, 0,   4,5,6,7 ),
             15: (self._qsfp_ctrlb, 3,   0,1,2,3 ),
             16: (self._qsfp_ctrlb, 3,   4,5,6,7 )
        }

        self.LED_MAP = {
             # LEDName : (expander object, Register, bit number)
             'QSFP1': (self._qsfp_ctrla, 4, 0),
             'QSFP2': (self._qsfp_ctrla, 4, 1),
             'QSFP3': (self._qsfp_ctrla, 4, 2),
             'QSFP4': (self._qsfp_ctrla, 4, 3),
             'QSFP5': (self._qsfp_ctrla, 4, 4),
             'QSFP6': (self._qsfp_ctrla, 4, 5),
             'QSFP7': (self._qsfp_ctrla, 4, 6),
             'QSFP8': (self._qsfp_ctrla, 4, 7),

             'QSFP9': (self._qsfp_ctrlb, 4, 0),
             'QSFP10': (self._qsfp_ctrlb, 4, 1),
             'QSFP11': (self._qsfp_ctrlb, 4, 2),
             'QSFP12': (self._qsfp_ctrlb, 4, 3),
             'QSFP13': (self._qsfp_ctrlb, 4, 4),
             'QSFP14': (self._qsfp_ctrlb, 4, 5),
             'QSFP15': (self._qsfp_ctrlb, 4, 6),
             'QSFP16': (self._qsfp_ctrlb, 4, 7),
             'LED1': (self._reset_ctrl, 0, 7)
        }


        self.SLOT_RESETS_MAP = {
            # Slot num : (expander object, ARM Register, Power Down Register, Bit number)
            1: (self._reset_ctrl, 1, 2, 0),
            2: (self._reset_ctrl, 1, 2, 1),
            3: (self._reset_ctrl, 1, 2, 2),
            4: (self._reset_ctrl, 1, 2, 3),
            5: (self._reset_ctrl, 1, 2, 4),
            6: (self._reset_ctrl, 1, 2, 5),
            7: (self._reset_ctrl, 1, 2, 6),
            8: (self._reset_ctrl, 1, 2, 7),
            9: (self._reset_ctrl,  3, 4, 0),
            10: (self._reset_ctrl, 3, 4, 1),
            11: (self._reset_ctrl, 3, 4, 2),
            12: (self._reset_ctrl, 3, 4, 3),
            13: (self._reset_ctrl, 3, 4, 4),
            14: (self._reset_ctrl, 3, 4, 5),
            15: (self._reset_ctrl, 3, 4, 6),
            16: (self._reset_ctrl, 3, 4, 7)
        }

        self.FULLBP_RESETS_MAP = {
             # ResetType : (expander object, Register, mask, inactive, active)
             'ARM':       (self._reset_ctrl, 0, 0b01000011, 0b00000001, 0b01000010),
             'POWER':     (self._reset_ctrl, 0, 0b01001100, 0b00000100, 0b01001000),
             'FPGA':      (self._reset_ctrl, 0, 0b01110000, 0b00010000, 0b01100000)

        }


        self.TEMPERATURE_SENSOR_TABLE = {
             # sensor name: tmp object
             'TEMP_SLOT1': self._tmp_slot1,
             'TEMP_SLOT16': self._tmp_slot16,
         }

        self.POWER_SENSOR_TABLE = {
             # sensor name : (ina230 object, output voltage(volts), rshunt(inductor) (mohm), typical current(amps), current tolerance (0<tol<1))
             'BP_3V3': (self._power_3v3, 3.3, 2.6, 2., 0.5),
        }

        self.QSFP_EEPROM_MAP = {
             # Register Name : (datatype, memory location, bytes, page)
             'Identifier': ('bin', 0, 1, 0),
             'Status': ('bin',1, 2, 0),
             'ChanStatusIntFlags': ('bin',3, 2, 0),
             'ModMonIntFlags': ('bin',6, 2, 0),
             'ChanMonIntFlags' : ('bin',9, 4, 0),
             'MeasuredTemp' : ('bin',22, 2, 0),
             'MeasuredSupV' : ('bin',26, 2, 0),
             'ChanRxInPow': ('bin',34, 8, 0),
             'ChanTxBias':('bin',42, 8, 0),
             'LaserDisable':('bin',86, 1, 0),
             'RateSelect':('bin',87, 2, 0),
             'RxAppSelect':('bin',89, 4, 0),
             'PowerSet':('bin',93, 1, 0),
             'TxAppSelect':('bin',94, 4, 0),
             'IntLMask_LOS':('bin',100, 1, 0),
             'IntLMask_TXFault':('bin',101, 1, 0),
             'IntLMask_Temp':('bin',103, 1, 0),
             'IntLMask_Vcc':('bin',104, 1, 0),
             'PageSelect':('bin',127, 1, 0),

             'Identifier':('bin',128, 1, 0),
             'ExtIdentifier':('bin',129, 1, 0),
             'Connector':('bin',130, 1, 0),
             'CompCodes':('bin',131, 8, 0),
             'Encoding':('bin',139, 1, 0),
             'BitRate':('bin',140, 1, 0),
             'ExtRateSelectComp':('bin',141, 1, 0),
             'SupportedLengths':('bin',142, 5, 0),
             'DeviceTech':('bin',147, 1, 0),
             'VendName':('str',148, 16, 0),
             'ExtTranCode':('bin',164, 1, 0),
             'VenOUI':('bin',165, 3, 0),
             'VenPN':('str',168, 16,0),
             'VenRev':('bin',184, 2,0),
             'WaveLength':('bin',186, 2, 0),
             'MaxCaseTemp':('bin',190, 1, 0),
             'CCBase':('bin',191, 1, 0),
             'ExtOptions':('bin',192, 4, 0),
             'VenSN': ('str',196, 16, 0),
             'DateCode':('str',212, 8, 0),
             'DiagMon':('bin',220, 1, 0),
             'EnhOpt':('bin',221, 1, 0),
             'CCExt':('bin',223, 1, 0),
             'VenSpecEEPROM':('str',224, 32, 0)      #no idea if a string or binary info
             ##The other pages don't seem useful to us at all.
        }


    def open(self):
        """
        """
        pass


    def close(self):
        self._logger.info('Closing Icebox hardware')


    # def get_backplane_info(self, iceboard):
    #     # logger = logging.getLogger(__name__)
    #     self._logger.debug("Attempting to read backplane eeprom to determine board presence")
    #     # eeprom = FMC_EEPROM(iceboard.i2c, 'BP', address=cls.BACKPLANE_EEPROM_ADDRESS)
    #     eeprom_data = self._eeprom.read(0, length=1, noerror=True, verbose=1)
    #     self._logger.debug("Backplane EEPROM returned the value: %i", data[0])
    #     slot_number = self._iceboard.get_slot_number()
    #     return (eeprom_data[0], slot_number)


    def init(self):
        """Initializes the backplane to a known state"""

        self._init_qsfp_ctrl()
        self._init_reset_ctrl() # The power I2c bus needs to be bridged to the monitor I2C bus for this to work
        self._init_eeprom()
        self._init_temperature_sensors()
        self._init_power_sensors()


    def _init_temperature_sensors(self, temperature_sensor_name=None):
        """
        initializes temperature sensors
        'temperature_sensor_name' can be a list of temperature sensor names found in TEMPERATURE_SENSOR_TABLE.

        History:
        140318 JM: created
        """
        if temperature_sensor_name == None:
            temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
        elif isinstance(temperature_sensor_name, str):
            temperature_sensor_name = [temperature_sensor_name]

        for temp_sensor in temperature_sensor_name:
            if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                raise IceBoxException('Invalid temperature sensor name')
            else:
                tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
                tmp_object.init()

    def _init_power_sensors(self, power_sensor_name='BP_3V3'):
        """
        initializes current/power monitors
        'power_sensor_name' can be a list of current/power monitor names found in POWER_SENSOR_TABLE. If power_sensor_name=None, all sensors in
        POWER_SENSOR_TABLE are initialized.

        History:
        140320 JM: created
        """


        if power_sensor_name == None:
            power_sensor_name = self.POWER_SENSOR_TABLE.keys()
        elif isinstance(power_sensor_name, str):
            power_sensor_name = [power_sensor_name]

        for power_sensor in power_sensor_name:
            if power_sensor not in self.POWER_SENSOR_TABLE:
                raise IceBoxException('Invalid current/power monitor name')
            else:
                power_sensor_list = self.POWER_SENSOR_TABLE[power_sensor]
                power_sensor_object = power_sensor_list[0]
                power_sensor_object.init(v_out=power_sensor_list[1], r_shunt=power_sensor_list[2], i_typ=power_sensor_list[3], tol_i=power_sensor_list[4])


    def _init_qsfp_ctrl(self):
            """
            initializes QSFP control
            History:
            141015 AJG: created
            """
            qsfpa_ctrl=self._qsfp_ctrla
            qsfpb_ctrl=self._qsfp_ctrlb

            qsfpa_ctrl.init(cfg0_def=0x55, cfg1_def=0x55,cfg2_def=0x55,cfg3_def=0x55,cfg4_def=0xff,out0_def=0xaa, out1_def=0xaa,out2_def=0xaa,out3_def=0xaa,out4_def=0)
            qsfpb_ctrl.init(cfg0_def=0x55, cfg1_def=0x55,cfg2_def=0x55,cfg3_def=0x55,cfg4_def=0xff,out0_def=0xaa, out1_def=0xaa,out2_def=0xaa,out3_def=0xaa,out4_def=0)
            #By default LEDs are off (dir=inputs , outputs=0), ModPrsL and IntL (dir=input, output = 0), ResetL and ModselL (dir=output, output=1)

    def _init_reset_ctrl(self):
            """
            initializes reset control
            History:
            141075 AJG: created
            """
            reset_ctrl=self._reset_ctrl

            reset_ctrl.init(cfg0_def=0xFF, cfg1_def=0xFF,cfg2_def=0xFF,cfg3_def=0xFF,cfg4_def=0xFF,out0_def=0x15, out1_def=0xFF,out2_def=0xFF,out3_def=0xFF,out4_def=0xFF)
            #By default setting all pins to inputs, with default output level logic 1 (no reset possible) for all banks except 0
            #On bank 0, default levels are such that LED default is 0, Reset clear is active, and reset pins are functionality is maximily off

    def _init_eeprom(self):
        """initializes EEPROM"""
        pass

    def get_number_of_slots(self):
        return self.NUMBER_OF_SLOTS

    def read_eeprom(self, addr, length=1):
        return self._eeprom.read(addr, length = length)

    def get_eeprom_serial_number(self):
        """ return the 128-bit hardware-coded EEPROM serial number as a hex string. """
        return ''.join(['%02X' % v for v in self._serial.read(0x80, length=16)])

    def set_led(self, led_name, state):
        """
        Set the LED(s) specified in 'led_name' to the the 'state'.
        'led_name' can be a list of LED names found in
        LED_MAP.  'state' can be a single boolean value, or
        an array with the same length as 'led_name'
        """
        if isinstance(led_name, (str, int)):
            led_name = [led_name]

        for pos, name in enumerate(led_name):
            if isinstance(name, int):
                name='QSFP%i' % name
            led_name[pos]=name

        if isinstance(state, (bool, int)):
            state = [state] * len(led_name)

        for (led, led_state) in zip(led_name,state):
            if led not in self.LED_MAP:
                raise IceBoxException('Invalid LED name')
            else:
                (led_control_object, led_control_register, led_control_bitnumber) = self.LED_MAP[led]
                led_control_register='CFG%i' % led_control_register #Converting the resister in the map into the correct string format
                #Note that we are cheating here, we are flipping the bits on the IO Expander from input mode to output mode, inputs are default floating
                #Turning on the LED requires a output of 0 which is the default state in output mode
                mask = 1<<led_control_bitnumber
                led_control_object.write(led_control_register, (not led_state) * mask, mask=mask)

    def get_led(self, led_name):
        """
        Returns the status of specified LED(s) in a dictionary
        led_status where each key is a led_name and the respective value
        is the led status.
        """
        led_status = {}
        if isinstance(led_name, str):
            led_name = [led_name]

        for pos, name in enumerate(led_name):
            if isinstance(name, int):
                name='QSFP%i' % name
            led_name[pos]=name

        for led in led_name:
            if led not in self.LED_MAP:
                raise IceBoxException('Invalid LED name')
            else:
                (led_control_object, led_control_register, led_control_bitnumber) = self.LED_MAP[led]
                led_control_register='IN%i' % led_control_register #Converting the resister in the map into the correct string format
                #Note that we are cheating here, we are flipping the bits on the IO Expander from input mode to output mode, inputs are default floating
                #Turning on the LED requires a output of 0 which is the default state in output mode
                regout=led_control_object.read(led_control_register)
                led_status[led]= not bool( (regout & (1<<led_control_bitnumber))>>led_control_bitnumber)

        return led_status

    def get_temperature(self, temperature_sensor_name=None):
        """
        Returns the current temperature measured on the specified
        sensor(s).  NOTE: some temperatures are taken from the FPGA
        inetrnal SYSTEM monitor.

        initializes temperature expanders
        'temperature_sensor_name' can be a list of temperature sensor
        names found in TEMPERATURE_SENSOR_TABLE

        Returns a dictionary with keys corresponding to the temperature_sensor_name names.

        History:
        140318 JM: created
        """
        temperature_dict = {}
        if temperature_sensor_name == None:
            temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
        elif isinstance(temperature_sensor_name, str):
            temperature_sensor_name = [temperature_sensor_name]

        for temp_sensor in temperature_sensor_name:
            if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                raise IceBoxException('Invalid temperature sensor name')
            else:
                tmp_object = self.TEMPERATURE_SENSOR_TABLE[temp_sensor]
                temperature_dict[temp_sensor]=tmp_object.get_temperature()

        return temperature_dict

    def get_power(self, power_sensor_name=None):
        """
        Returns the voltage, current and power of the power monitoring system.
        Includes power measured internally from  the FPGA's system monitor.
        Multiple targets can be specified.

        Arguments:

           'power_sensor_name' can be a list of power sensor
            names found in POWER_SENSOR_TABLE. If
            power_sensor_name=None, measurements of all sensors in
            power_sensor_table are returned.

        Returns dictionary with keys corresponding to the
        power_sensor_name names. The respective value is a (bus
        voltage (V), shunt voltage (V), current (A), power (W)) tuple.

        History:
        140320 JM: created
        """
        power_dict = {}
        if power_sensor_name == None:
            power_sensor_name = self.POWER_SENSOR_TABLE.keys()
        elif isinstance(power_sensor_name, str):
            power_sensor_name = [power_sensor_name]

        for power_sensor in power_sensor_name:
            if power_sensor not in self.POWER_SENSOR_TABLE:
                raise IceBoxException('Invalid power sensor name')
            else:
                power_sensor_list = self.POWER_SENSOR_TABLE[power_sensor]
                power_object = power_sensor_list[0]
                power_dict[power_sensor]=(power_object.get_bus_voltage(), power_object.get_shunt_voltage(), power_object.get_current(), power_object.get_power())

        return power_dict


    def get_serial_number(self):
        """
        Returns the board's serial number.
        """
        return self.get_eeprom_serial_number(); # tentative code

    def get_info(self):
        """Loads the info data on the motherboard"""
        pass

    def status(self):
        """Displays the status of the motherboard"""

    def set_qsfp_led(self, slots, state):
        """
        Set the QSFP LED state for a given slot
        History:
        141015 AJG & JF: created
        """
        if isinstance(slots, (int,str)):
            slots = [slots]

        for slotnum in slots:
            if slotnum not in range(1,self.NUMBER_OF_SLOTS + 1) :
                raise IceBoxException('Invalid Slot number %i' % slots)

        self.set_led(slots, state)


    def qsfp_reset(self, slots, state=None):
        """
        reset the specified QSFPs , reset performed by pulling corresponding ResetL pins low
        History:
        141015 AJG & JF: created
        """

        if isinstance(slots, int):
            slots = [slots]

        for slotnum in slots:

            if slotnum not in range(1,self.NUMBER_OF_SLOTS + 1) :
                raise IceBoxException('Invalid Slot number %i' % slotnum)
            else:
                (qsfp_control_object, control_register, ModPrs_bitnum, ResetL_bitnum, IntL_bitnum, ModSelL_bitnum) = self.QSFP_CTRL_MAP[slotnum]
                mask = 1<< ResetL_bitnum

                qsfp_control_register = 'OUT%i' % control_register
                if state is None:
                    qsfp_control_object.write(qsfp_control_register, 0 * mask, mask=mask)
                    qsfp_control_object.write(qsfp_control_register, 1 * mask, mask=mask)
                else:
                    qsfp_control_object.write(qsfp_control_register, bool(state) * mask, mask=mask)

    def qsfp_status(self, slots=range(1, NUMBER_OF_SLOTS + 1)):
        """
        checks slots to see if QSFP present
        History:
        141015 AJG & JF: created
        """

        if isinstance(slots, int):
            slots = [slots]

        output={}

        present=[]
        reset=[]
        intl=[]
        modsel=[]


        for slotnum in slots:

            if slotnum not in range(1,self.NUMBER_OF_SLOTS + 1) :
                raise IceBoxException('Invalid Slot number %i' % slotnum)
            else:
                (qsfp_control_object, control_register, ModPrs_bitnum, ResetL_bitnum, IntL_bitnum, ModSelL_bitnum) = self.QSFP_CTRL_MAP[slotnum]

                qsfp_control_register='IN%i' % control_register
                outputreg=qsfp_control_object.read(qsfp_control_register)

                present.append(not((outputreg & (1 << ModPrs_bitnum)) >> ModPrs_bitnum))   #copying the info at this bit number into the status reg
                reset.append(not((outputreg & (1 << ResetL_bitnum)) >> ResetL_bitnum))     #copying the info at this bit number into the status reg
                intl.append(not((outputreg & (1 << IntL_bitnum)) >> IntL_bitnum))          #copying the info at this bit number into the status reg
                modsel.append(not((outputreg & (1 << ModSelL_bitnum)) >> ModSelL_bitnum))  #copying the info at this bit number into the status reg

        output['present']=present
        output['reset']=reset
        output['intl']=intl
        output['modsel']=modsel
        output['slots']=slots

        return output

    def qsfp_enable_i2c(self, slot, state):
        """
        Enables QSFP I2C - Pulls ModselL low
        History:
        141015 AJG & JF: created
        """

        if not isinstance(slot, int):
            raise IceBoxException('Must perform action on one slot at a time. Slot must be an integer.')
        if slot not in range(1,self.NUMBER_OF_SLOTS + 1) :
            raise IceBoxException('Invalid Slot number %i' % slot)
        qstatus=self.qsfp_status(slot)

        if not qstatus['present'][0]:  #Checking to see if QSPF present
            raise IceBoxException('No QSFP device loaded on slot number %i' % slot)

        (qsfp_control_object, control_register, ModPrs_bitnum, ResetL_bitnum, IntL_bitnum, ModSelL_bitnum) = self.QSFP_CTRL_MAP[slot]

        mask = 1 << ModSelL_bitnum
        qsfp_control_register = 'OUT%i' % control_register
        qsfp_control_object.write(qsfp_control_register, (not state)*mask, mask=mask)

    def write_qsfp(self, slot, addr, data, page=0):

        self.qsfp_enable_i2c(slot, True)

        if (page !=0):
            self._qsfp_eeprom.write(addr=127, data=page, length =1) #Writing to page select register

        self._qsfp_eeprom.write(addr, data) #Writing at specified address

        if (page !=0):
            self._qsfp_eeprom.write(addr=127, data=0, length =1)  #Putting page back to 0

        self.qsfp_enable_i2c(slot, False)


    def read_qsfp(self, slot, addr, length=1, page=0):
        """
        Reads QSFP eeprom on given slot slot. Enables I2C, reads, Disables I2C
        History:
        141015 AJG & JF: created
        """

        self.qsfp_enable_i2c(slot, True)

        if (page !=0):
            self._qsfp_eeprom.write(addr=127, data=page, length =1) #Writing to page select register

        data = self._qsfp_eeprom.read(addr=addr, length = length) #Reading at specified address

        if (page !=0):
            self._qsfp_eeprom.write(addr=127, data=0, length =1)  #Putting page back to 0

        self.qsfp_enable_i2c(slot, False)

        return data

    def qsfp_i2c_read_str(self, slot, addr=148, length=16, page=0):
        return ''.join([chr(x) for x in self.read_qsfp(slot, addr, length, page)])


    def get_qsfp_info(self, slots=range(1, NUMBER_OF_SLOTS + 1)):
        """
        Gets all qsfp info marked up in the qsfp eeprom map for each slot
        Data is returned as a list of dictionaries
        History:
        141015 AJG & JF: created
        """

        if isinstance(slots, int):
            slots = [slots]
        qstatus=self.qsfp_status(slots)

        qsfpdata=[]
        for slotnum in slots:

            if slotnum not in range(1,self.NUMBER_OF_SLOTS + 1) :
                raise IceBoxException('Invalid Slot number %i' % slotnum)
            else:

                data={}
                data['QSFPNumber']=slotnum
                data['QSFPPresent']=False

                if qstatus['present'][slotnum-1]:
                    data['QSFPPresent']=True
                    for (key, (datatype, addr, length, page)) in self.QSFP_EEPROM_MAP.items():

                        if datatype == 'str': #String detected, converting to readable characters
                            data[key]=self.qsfp_i2c_read_str(slot=slotnum, addr=addr, length=length, page=page)
                        else: #assuming binary
                            data[key]=self.read_qsfp(slot=slotnum, addr=addr, length=length, page=page)

                qsfpdata.append(data)
        return qsfpdata

    def reset_slot(self, slots, state, reset_type='ARM'):
        """
        Function performs Resets. If slots 'ALL' will perform full backplane reset, Type can be 'ARM', 'POWER' or'FPGA'
        For full backplane reset state must be True.

        For individual slot reset (can be a list)
        State must be True, False, or 'pulse', reset type must be 'ARM' or 'POWER'

        History:
        141015 AJG & JF: created
        """


        if slots=='ALL' and state==1:  #We wish to perform a full crate reset

            if reset_type not in self.FULLBP_RESETS_MAP:
                raise IceBoxException('Unknown reset type %s' % reset_type)
            else:

                (reset_control_obj, controlreg, mask, inactive, active) = self.FULLBP_RESETS_MAP[reset_type]
                reset_cfg_register='CFG%i' % controlreg
                reset_output_register='OUT%i' % controlreg


                self.set_led('LED1', not(self.get_led('LED1')['LED1'])) #Flipping state of LED so that we know a reset was performed
                #not sure what the defualt LED state will be so this is a flip at the moment

                reset_control_obj.write(reset_output_register, active, mask) #Setting output register to reset value
                reset_control_obj.write(reset_cfg_register,  0, mask) #Setting direction register to output (this performs the reset)



        else:  #We wish to perform individual resets

            if isinstance(slots, int):
                slots = [slots]

            if isinstance(state, (bool, int, str)):
                    state = ([state] * len(slots))

            if isinstance(reset_type, (str)):
                    reset_type = ([str(reset_type)] * len(slots))

            for (slot, isenabled, resettype) in zip(slots, state, reset_type):
                if slot == self._iceboard.slot_number+1:
                    print 'Warning, will not perform reset on the controlling slot %i' % slot

                # if isenabled and slot != self._iceboard.slot_number  :
                elif slot not in range(1,self.NUMBER_OF_SLOTS + 1) :
                    raise IceBoxException('Invalid Slot number %i' % slot)
                else:
                    (reset_control_obj, arm_reset_reg, power_down_reg, bitnumber) = self.SLOT_RESETS_MAP[slot]
                    if resettype == 'ARM':
                        reset_cfg_register='CFG%i' % arm_reset_reg
                        reset_output_register='OUT%i' % arm_reset_reg
                    elif resettype == 'POWER':
                        reset_cfg_register='CFG%i' % power_down_reg
                        reset_output_register='OUT%i' % power_down_reg
                    else:
                        raise IceBoxException('Unknown reset type, will not perform reset on slot %i' % slot)
                    
                    mask = 1 << bitnumber
                    if isenabled==1 or isenabled=='pulse':  #Turning reset on
                        
                        reset_control_obj.write(reset_output_register,  0, mask) #Setting output register to logic 0 (reset active)
                        reset_control_obj.write(reset_cfg_register,  0, mask) #Setting direction register from input to output - Performing reset

                    if isenabled==0 or isenabled=='pulse': #Turning reset off
                        if isenabled=='pulse':
                            #time.sleep(0.1)
                            pass
                        reset_control_obj.write(reset_output_register,  mask, mask) #Setting output register to logic 1 (reset inactive) - Removing reset
                        reset_control_obj.write(reset_cfg_register,  mask, mask) #Setting direction register from output to input - Back to default state

    def flash_leds(self, testduration=60, pausetime=0.5):
        """
        Turns all the LEDs on then turns them off one a a time until all off
        will repeat until the the time duration of the test has passed the specified test duration

        History:
        141218 AJG : created
        """
        timestart=time.time()
        runtime=0
        
        while runtime < testduration:
            
            for ledname in self.LED_MAP.keys():
                self.set_led(ledname, 1) #Turn on LEDs
            
            time.sleep(pausetime)

            for ledname in self.LED_MAP.keys():
                self.set_led(ledname,0) #Turn off LEDs
                
            runtime=time.time()-timestart
    
    def cont_read_eeprom(self, testduration=60, pausetime=0.5):
        """
        Repeately reads the eeprom  - a test function

        History:
        141218 AJG : created
        """
        timestart=time.time()
        runtime=0
        
        while runtime < testduration:
            try:
                time.sleep(pausetime)
                self.read_eeprom( addr=1, length=1)
            
                
            except:
                pass
                                
            runtime=time.time()-timestart
            







































