"""icecrate_handler.py module: Provides a class to access the hardware of ICE backplane (McGill Model MGK7BP).
"""

import logging
import time

from ..icecore import IceCrate, IceCrateHandler
from ..icecore import session

from lib.eeprom import eeprom as EEPROM
from lib import ina230  # I2C Voltage and current monitor
from lib import tmp421  # I2C temperature sensor
from lib import pca9698  # I2C 40-bit IO Expander
from lib import amc6821  # I2C fan Controller

@session.register_yaml_object()
class IceCrateExt(IceCrate):
    handler_name = 'IceCrateExtHandler'
    __mapper_args__ = {'polymorphic_identity': 'IceCrateExt'}
    __ipmi_part_number__ = ['MGK7BP', 'MGK7BP16']  # Must match part number in IPMI data

class IceCrateExtHandler(IceCrateHandler):
    """ IceCrate handler that provides access to the backplane through an IceBoard.
    """

    #------------------------------------
    # Define hardware-specific constants
    #------------------------------------
    NUMBER_OF_SLOTS = 16  #
    BACKPLANE_EEPROM_DATA_ADDRESS = 0x54  # covers 0x54 - 0x57 ( 4 pages of 256 bytes, 1024 Bytes total)
    BACKPLANE_EEPROM_SERIAL_ADDRESS = 0x5C  # 16 byte serial number starting at memory address 0x80
    BACKPLANE_EEPROM_ADDRESS_WIDTH = 10  # 2 bits are in the device address, the remaining are in the address byte following the command byte
    BACKPLANE_EEPROM_PAGE_SIZE = 16 #

    BACKPLANE_QSFP_ADDRESS = 0x50  # QSFP standard address (it is the same for all QSFPs)
    BACKPLANE_QSFP_ADDRESS_WIDTH = 8


    _QSFP_CTRL_SETA_ADDR = 0x20
    _QSFP_CTRL_SETB_ADDR = 0x22
    _RESETS_CTRL_ADDR = 0x24

    _TMP_SLOT1_ADDR = 0x4E
    _TMP_SLOT16_ADDR = 0x4D

    _FAN_CTRL_ADDR = 0x18  # AMC6821 Fan controller, connected on backplane external I2C connector

    _POWER_3V3_ADDR = 0x40

    # The following dictionnary describes the connectivity of the 10 Gbps mesh.
    # It indicates which transmitter (slot and lane number) is feeding a specified receiver.
    # The dictionnary is indexed by receiver number.
    _BP_RX_TO_TX_MAP = {
        # (rx_slot, rx_lane) <= (tx_slot_tx_lane)
        # Slots are numbered from 1 to 16
        # Lanes are numbered from 0 to 15. Lane 0 is internal to the FPGA.

        # Slot 1 receivers
        (1,   0): (1,   0),  # direct internal link in FPGA
        (1,   1): (12,  1), (1,   2): (10, 11), (1,   3): (9,  15),
        (1,   4): (6,   8), (1,   5): (5,   2), (1,   6): (3,   8),
        (1,   7): (8,   6), (1,   8): (2,  10), (1,   9): (15,  3),
        (1,  10): (16, 11), (1,  11): (11, 13), (1,  12): (14,  5),
        (1,  13): (13,  1), (1,  14): (4,   7), (1,  15): (7,  13),

        # Slot 2 receivers
        (2,   0): (2,   0),  # direct internal link in FPGA
        (2,   1): (11, 11), (2,   2): (16,  7),  (2,   3): (12, 13),
        (2,   4): (6,  14), (2,   5): (5,   4),  (2,   6): (15,  5),
        (2,   7): (8,   2), (2,   8): (3,  10),  (2,  9): (14,  7),
        (2,  10): (13,  2), (2,  11): (10, 13),  (2,  12): (9,  13),
        (2,  13): (1,   6), (2,  14): (4,   8),  (2,  15): (7,  15),

        # Slot 3 receivers
        (3,   0): (3,   0),  # direct internal link in FPGA
        (3,   1): (9,  12), (3,   2): (12, 14), (3,   3): (14, 11),
        (3,   4): (11, 12), (3,   5): (5,   8), (3,   6): (2,   6),
        (3,   7): (8,   4), (3,   8): (4,  10), (3,   9): (6,   4),
        (3,  10): (1,   4), (3,  11): (15, 11), (3,  12): (16, 12),
        (3,  13): (10, 15), (3,  14): (13,  4), (3,  15): (7,  14),

        # Slot 4 receivers
        (4,   0): (4,   0),  # direct internal link in FPGA
        (4,   1): (15,  2), (4,   2): (16,  2), (4,   3): (11,  1),
        (4,   4): (6,   2), (4,   5): (12,  2), (4,   6): (3,   6),
        (4,   7): (8,  12), (4,   8): (5,  10), (4,   9): (2,   2),
        (4,  10): (1,   2), (4,  11): (13, 11), (4,  12): (9,  14),
        (4,  13): (10, 14), (4,  14): (14,  2), (4,  15): (7,   4),

        # Slot 5 receivers
        (5,   0): (5,   0),  # direct internal link in FPGA
        (5,   1): (9,   2),  (5,   2): (16, 15), (5,   3): (13, 15),
        (5,   4): (15, 15),  (5,   5): (14, 15), (5,   6): (3,   4),
        (5,   7): (8,   8),  (5,   8): (6,  10), (5,   9): (2,  11),
        (5,  10): (1,   1),  (5,  11): (10, 12), (5,  12): (11, 14),
        (5,  13): (4,   6),  (5,  14): (12, 15), (5,  15): (7,   8),

        # Slot 6 receivers
        (6,   0): (6,   0),  # direct internal link in FPGA
        (6,   1): (16,  5), (6,   2): (15, 13), (6,   3): (9,   4),
        (6,   4): (14, 14), (6,   5): (13,  5), (6,   6): (3,   2),
        (6,   7): (8,   9), (6,   8): (7,  10), (6,   9): (2,  12),
        (6,  10): (1,  11), (6,  11): (10,  2), (6,  12): (12,  4),
        (6,  13): (5,   6), (6,  14): (4,   4), (6,  15): (11,  4),


        # Slot 7 receivers
        (7,   0): (7,   0),  # direct internal link in FPGA
        (7,   1): (16,  9), (7,   2): (15,  9), (7,   3): (13,  7),
        (7,   4): (14,  9), (7,   5): (5,  11), (7,   6): (3,   1),
        (7,   7): (6,   6), (7,   8): (8,  10), (7,   9): (2,  13),
        (7,  10): (1,  12), (7,  11): (9,   8), (7,  12): (12, 10),
        (7,  13): (10,  4), (7,  14): (4,   2), (7,  15): (11, 15),

        # Slot 8 receivers
        (8,   0): (8,   0),  # direct internal link in FPGA
        (8,   1): (6,  11), (8,   2): (16,  8), (8,   3): (14,  8),
        (8,   4): (15,  8), (8,   5): (5,  12), (8,   6): (3,  11),
        (8,   7): (7,   6), (8,   8): (9,  10), (8,   9): (2,  14),
        (8,  10): (1,  13), (8,  11): (10,  8), (8,  12): (13,  8),
        (8,  13): (12,  8), (8,  14): (4,   1), (8,  15): (11,  8),

        # Slot 9 receivers
        (9,   0): (9,   0),  # direct internal link in FPGA
        (9,   1): (6,  12), (9,   2): (14,  6), (9,   3): (15,  6),
        (9,   4): (16,  6), (9,   5): (5,  13), (9,   6): (3,  12),
        (9,   7): (8,  13), (9,   8): (10, 10), (9,   9): (2,  15),
        (9,  10): (1,  14), (9,  11): (12,  6), (9,  12): (13,  6),
        (9,  13): (11,  6), (9,  14): (4,  11), (9,  15): (7,  12),

        # Slot 10 receivers
        (10,  0): (10,  0),  # direct internal link in FPGA
        (10,  1): (6,  13), (10,  2): (4,  12), (10,  3): (7,   2),
        (10,  4): (8,  14), (10,  5): (5,  15), (10,  6): (3,  13),
        (10,  7): (9,   6), (10,  8): (11, 10), (10,  9): (2,   1),
        (10, 10): (1,  15), (10, 11): (16, 14), (10, 12): (15, 14),
        (10, 13): (14, 13), (10, 14): (13, 14), (10, 15): (12, 11),

        # Slot 11 receivers
        (11,  0): (11,  0),  # direct internal link in FPGA
        (11,  1): (5,   1), (11,  2): (7,  11), (11,  3): (8,  11),
        (11,  4): (9,  11), (11,  5): (6,  15), (11,  6): (3,  14),
        (11,  7): (10,  6), (11,  8): (12,  7), (11,  9): (2,   5),
        (11, 10): (1,   3), (11, 11): (4,  13), (11, 12): (16,  4),
        (11, 13): (15,  4), (11, 14): (14,  4), (11, 15): (13, 13),

        # Slot 12 receivers
        (12,  0): (12,  0),  # direct internal link in FPGA
        (12,  1): (7,   1), (12,  2): (8,   1), (12,  3): (9,   1),
        (12,  4): (10,  1), (12,  5): (5,  14), (12,  6): (3,  15),
        (12,  7): (11,  2), (12,  8): (13, 10), (12,  9): (2,   7),
        (12, 10): (1,   5), (12, 11): (15,  1), (12, 12): (16,  1),
        (12, 13): (14,  1), (12, 14): (4,  14), (12, 15): (6,   1),

        # Slot 13 receivers
        (13,  0): (13,  0),  # direct internal link in FPGA
        (13,  1): (7,   7), (13,  2): (8,   7), (13,  3): (9,   7),
        (13,  4): (10,  7), (13,  5): (11,  7), (13,  6): (3,   5),
        (13,  7): (12, 12), (13,  8): (14, 10), (13,  9): (2,   9),
        (13, 10): (1,   7), (13, 11): (16,  3), (13, 12): (5,   7),
        (13, 13): (15,  7), (13, 14): (4,  15), (13, 15): (6,   7),

        # Slot 14 receivers
        (14,  0): (14,  0),  # direct internal link in FPGA
        (14,  1): (7,   5), (14,  2): (8,   5), (14,  3): (9,   5),
        (14,  4): (10,  5), (14,  5): (11,  5), (14,  6): (12,  5),
        (14,  7): (13, 12), (14,  8): (15, 10), (14,  9): (2,   8),
        (14, 10): (1,   9), (14, 11): (5,   5), (14, 12): (6,   5),
        (14, 13): (4,   5), (14, 14): (3,   7), (14, 15): (16, 13),

        # Slot 15 receivers
        (15,  0): (15,  0),  # direct internal link in FPGA
        (15,  1): (8,  15), (15,  2): (9,   9), (15,  3): (10,  9),
        (15,  4): (11,  9), (15,  5): (12,  9), (15,  6): (13,  9),
        (15,  7): (14, 12), (15,  8): (16, 10), (15,  9): (2,   4),
        (15, 10): (1,  10), (15, 11): (6,   9), (15, 12): (7,   9),
        (15, 13): (5,   9), (15, 14): (4,   9), (15, 15): (3,   9),


        # Slot 16 receivers
        (16,  0): (16,  0),  # direct internal link in FPGA
        (16,  1): (8,   3), (16,  2): (9,   3), (16,  3): (10,  3),
        (16,  4): (11,  3), (16,  5): (12,  3), (16,  6): (13,  3),
        (16,  7): (15, 12), (16,  8): (14,  3), (16,  9): (7,   3),
        (16, 10): (1,   8), (16, 11): (5,   3), (16, 12): (6,   3),
        (16, 13): (4,   3), (16, 14): (3,   3), (16, 15): (2,   3)
    }

    _BP_TX_TO_RX_MAP = {tx:rx for (rx, tx) in _BP_RX_TO_TX_MAP.items()}

    _BP_RX_NET_LENGTH = {
        (1, 0): 0,
        (1, 1): 13131.376, (1, 2): 11758.891, (1, 3): 10895.916, (1, 4): 10765.111, (1, 5): 8343.244,
        (1, 6): 5610.788, (1, 7): 10499.916, (1, 8): 2251.116, (1, 9): 14138.428, (1, 10): 15522.835,
        (1, 11): 12234.071, (1, 12): 13136.188, (1, 13): 13206.662, (1, 14): 7691.596, (1, 15): 7987.345,

        (2, 0): 0,
        (2, 1): 11124.978, (2, 2): 15584.631, (2, 3): 14869.477, (2, 4): 9722.815, (2, 5): 7578.678,
        (2, 6): 14074.08, (2, 7): 9082.473, (2, 8): 2090.903, (2, 9): 12981.864, (2, 10): 11834.697,
        (2, 11): 10400.101, (2, 12): 9642.671, (2, 13): 2437.647, (2, 14): 6931.064, (2, 15): 6688.326,

        (3, 0): 0,
        (3, 1): 8394.233, (3, 2): 15200.568, (3, 3): 14434.448, (3, 4): 10605.683, (3, 5): 6948.454,
        (3, 6): 2040.877, (3, 7): 7407.712, (3, 8): 2090.903, (3, 9): 8421.202, (3, 10): 5549.809,
        (3, 11): 13843.897, (3, 12): 14180.565, (3, 13): 9448.714, (3, 14): 11780.901, (3, 15): 5891.432,

        (4, 0): 0,
        (4, 1): 12438.695, (4, 2): 13217.23, (4, 3): 9463.142, (4, 4): 6703.4, (4, 5): 15219.163,
        (4, 6): 2102.121, (4, 7): 6893.787, (4, 8): 2151.083, (4, 9): 5353.125, (4, 10): 5981.645,
        (4, 11): 12486.929, (4, 12): 7058.997, (4, 13): 8534.292, (4, 14): 12718.623, (4, 15): 4774.782,

        (5, 0): 0,
        (5, 1): 5899.434, (5, 2): 15246.84, (5, 3): 11682.228, (5, 4): 14157.666, (5, 5): 12484.28,
        (5, 6): 6033.559, (5, 7): 6620.503, (5, 8): 2152.62, (5, 9): 5548.213, (5, 10): 6522.7,
        (5, 11): 7989.084, (5, 12): 8766.109, (5, 13): 2460.308, (5, 14): 10647.818, (5, 15): 3161.519,

        (6, 0): 0,
        (6, 1): 15384.024, (6, 2): 14202.352, (6, 3): 5213.583, (6, 4): 12843.446, (6, 5): 11451.217,
        (6, 6): 6185.288, (6, 7): 5911.775, (6, 8): 2212.097, (6, 9): 6298.076, (6, 10): 7098.358,
        (6, 11): 6868.901, (6, 12): 9788.995, (6, 13): 2528.858, (6, 14): 5852.603, (6, 15): 8774.817,

        (7, 0): 0,
        (7, 1): 13934.62, (7, 2): 12807.943, (7, 3): 10900.704, (7, 4): 11674.562, (7, 5): 4955.973,
        (7, 6): 6740.449, (7, 7): 1930.764, (7, 8): 2219.849, (7, 9): 6978.013, (7, 10): 7885.079,
        (7, 11): 4162.8, (7, 12): 9958.301, (7, 13): 7370.388, (7, 14): 6281.698, (7, 15): 8488.357,

        (8, 0): 0,
        (8, 1): 4950.405, (8, 2): 9537.772, (8, 3): 7623.096, (8, 4): 8478.028, (8, 5): 5825.926,
        (8, 6): 7359.715, (8, 7): 2110.033, (8, 8): 2159.28, (8, 9): 7876.757, (8, 10): 8692.76,
        (8, 11): 4116.646, (8, 12): 6790.19, (8, 13): 5734.886, (8, 14): 6872.901, (8, 15): 4613.62,

        (9, 0): 0,
        (9, 1): 6175.016, (9, 2): 7927.647, (9, 3): 9333.019, (9, 4): 10368.077, (9, 5): 6591.689,
        (9, 6): 8280.523, (9, 7): 1556.778, (9, 8): 2200.965, (9, 9): 8620.932, (9, 10): 9482.499,
        (9, 11): 5736.888, (9, 12): 6621.687, (9, 13): 4715.076, (9, 14): 7449.623, (9, 15): 3705.239,

        (10, 0): 0,
        (10, 1): 5967.156, (10, 2): 8770.085, (10, 3): 4457.519, (10, 4): 2949.672, (10, 5): 7437.995,
        (10, 6): 8950.525, (10, 7): 2170.895, (10, 8): 2208.202, (10, 9): 9889.087, (10, 10): 10295.806,
        (10, 11): 6936.655, (10, 12): 6183.788, (10, 13): 4833.609, (10, 14): 3428.478, (10, 15): 2494.009,

        (11, 0): 0,
        (11, 1): 8206.255, (11, 2): 5005.379, (11, 3): 4421.502, (11, 4): 4081.863, (11, 5): 6051.148,
        (11, 6): 9739.858, (11, 7): 2107.874, (11, 8): 2016.311, (11, 9): 10441.592, (11, 10): 11385.772,
        (11, 11): 9264.139, (11, 12): 5031.549, (11, 13): 4275.474, (11, 14): 3590.566, (11, 15): 2736.974,

        (12, 0): 0,
        (12, 1): 6629.96, (12, 2): 5711.805, (12, 3): 4946.236, (12, 4): 4191.797, (12, 5): 8846.665,
        (12, 6): 10472.176, (12, 7): 1691.623, (12, 8): 2229.949, (12, 9): 11276.357, (12, 10): 12104.001,
        (12, 11): 3314.999, (12, 12): 4784.985, (12, 13): 2519.396, (12, 14): 9448.016, (12, 15): 7957.923,

        (13, 0): 0,
        (13, 1): 8441.844, (13, 2): 7191.1, (13, 3): 6169.519, (13, 4): 5414.659, (13, 5): 4658.298,
        (13, 6): 10635.975, (13, 7): 1515.203, (13, 8): 2183.776, (13, 9): 12529.891, (13, 10): 12858.422,
        (13, 11): 3413.873, (13, 12): 10182.247, (13, 13): 2989.034, (13, 14): 9964.449, (13, 15): 9927.224,

        (14, 0): 0,
        (14, 1): 8920.113, (14, 2): 7774.449, (14, 3): 6828.819, (14, 4): 5970.981, (14, 5): 5407.159,
        (14, 6): 4108.82, (14, 7): 1613.146, (14, 8): 2305.122, (14, 9): 12327.087, (14, 10): 13690.052,
        (14, 11): 11200.154, (14, 12): 10414.064, (14, 13): 12065.649, (14, 14): 11920.867, (14, 15): 2755.219,

        (15, 0): 0,
        (15, 1): 8600.002, (15, 2): 7846.819, (15, 3): 7121.911, (15, 4): 6467.004, (15, 5): 5449.227,
        (15, 6): 4857.292, (15, 7): 1696.647, (15, 8): 2223.447, (15, 9): 13609, (15, 10): 14610.615,
        (15, 11): 11278.824, (15, 12): 9966.145, (15, 13): 12496.163, (15, 14): 13626.36, (15, 15): 14162.375,

        (16, 0): 0,
        (16, 1): 9580.145, (16, 2): 8719.981, (16, 3): 7798.304, (16, 4): 6780.144, (16, 5): 6010.335,
        (16, 6): 5144.09, (16, 7): 1636.564, (16, 8): 4373.744, (16, 9): 11123.971, (16, 10): 15700.299,
        (16, 11): 12557.924, (16, 12): 11689.21, (16, 13): 13797.941, (16, 14): 14954.197, (16, 15): 16081.059 }

    @classmethod
    def get_matching_tx(cls, rx_slot_lane_tuple):
        return cls._BP_RX_TO_TX_MAP[rx_slot_lane_tuple]

    @classmethod
    def get_matching_rx(cls, tx_slot_lane_tuple):
        return cls._BP_TX_TO_RX_MAP[tx_slot_lane_tuple]

    @classmethod
    def get_rx_net_length(cls, rx_slot_lane_tuple):
        return cls._BP_RX_NET_LENGTH[rx_slot_lane_tuple]

    class dynamic_i2c(object):
        def __init__(self, icecrate):
            self._icecrate = icecrate
        def __getattr__(self, name):
            return getattr(self._icecrate.master_iceboard.i2c, name)

    # def __getattr__(self, name):
    #     """ Fetches attributes from the master iceboard's backplane handling object 'bp'
    #     """
    #     if self.master_iceboard:
    #         return getattr(self.master_iceboard.bp, name)
    #     else:
    #         return AttributeError("%r does not have an attribute '%s'" % (self, name))

    # def __dir__(self):
    #     class_attributes = [item  for class_ in type(self).mro() for item in dir(class_)]
    #     instance_attributes = self.__dict__.keys()
    #     backplane_attributes = dir(self.master_iceboard.bp) if self.master_iceboard else []
    #     return list(set(class_attributes + instance_attributes + backplane_attributes))

    def __init__(self, **kwargs):
        """ Create all the I2C objects needed to interface the backplane hardware.

        This instance keeps a local reference to 'iceboard', which is a
        reference to the IceBoard handler (not the HWM object, as this is a
        transient object). 'iceoard' must provide:

            - iceboard.i2c: a I2C interface object that provides standardized
              I2C access (handles switch config, bus names etc)

            - iceoard.slot_number: the backplane slot numbe ron which this
              iceboard is, so we don't reset ourself

        """
        super(IceCrateExtHandler, self).__init__(**kwargs)

        self._logger = logging.getLogger(__name__)
        self._logger.debug('%r: Instantiating backplane hardware' % self)

        self._i2c = self.dynamic_i2c(self)

        self._logger.info(' Instantiating Backplane I2C resource managers')
        self._eeprom_data = EEPROM(self._i2c, bus_name='BP', address=self.BACKPLANE_EEPROM_DATA_ADDRESS, address_width=self.BACKPLANE_EEPROM_ADDRESS_WIDTH, write_page_size = self.BACKPLANE_EEPROM_PAGE_SIZE)
        self._eeprom_serial = EEPROM(self._i2c, bus_name='BP', address=self.BACKPLANE_EEPROM_SERIAL_ADDRESS, address_width=self.BACKPLANE_EEPROM_ADDRESS_WIDTH, write_page_size = self.BACKPLANE_EEPROM_PAGE_SIZE)
        self._qsfp_eeprom = EEPROM(self._i2c, bus_name='BP', address=self.BACKPLANE_QSFP_ADDRESS, address_width=self.BACKPLANE_QSFP_ADDRESS_WIDTH)

        self._logger.info(' Instantiating Backplane I2C temperature sensors')
        self._tmp_slot1 = tmp421.tmp421(self._i2c, self._TMP_SLOT1_ADDR, 'BP')
        self._tmp_slot16 = tmp421.tmp421(self._i2c, self._TMP_SLOT16_ADDR, 'BP')

        self._logger.info(' Instantiating Backplane I2C current/power monitor')
        self._power_3v3 = ina230.ina230(self._i2c, self._POWER_3V3_ADDR, 'BP')

        self._logger.info(' Instantiating Backplane I2C I/O expanders')
        self._qsfp_ctrla = pca9698.pca9698(self._i2c, self._QSFP_CTRL_SETA_ADDR, 'BP')
        self._qsfp_ctrlb = pca9698.pca9698(self._i2c, self._QSFP_CTRL_SETB_ADDR, 'BP')
        self._reset_ctrl = pca9698.pca9698(self._i2c, self._RESETS_CTRL_ADDR, 'BP')

        self._fan_ctrl = amc6821.AMC6821(self._i2c, self._FAN_CTRL_ADDR, 'BP')

        self.QSFP_CTRL_MAP = {
             # Slot num : (expander object, Register, bit number ModPrs, bit number Reset, bit number IntL, bit number ModSel)
             1: (self._qsfp_ctrla, 2,    0, 1, 2, 3 ),
             2: (self._qsfp_ctrla, 2,    4, 5, 6, 7 ),
             3: (self._qsfp_ctrla, 1,    0, 1, 2, 3 ),
             4: (self._qsfp_ctrla, 1,    4, 5, 6, 7 ),
             5: (self._qsfp_ctrla, 0,    0, 1, 2, 3 ),
             6: (self._qsfp_ctrla, 0,    4, 5, 6, 7 ),
             7: (self._qsfp_ctrla, 3,    0, 1, 2, 3 ),
             8: (self._qsfp_ctrla, 3,    4, 5, 6, 7 ),

             9:  (self._qsfp_ctrlb, 2,   0, 1, 2, 3 ),
             10: (self._qsfp_ctrlb, 2,   4, 5, 6, 7 ),
             11: (self._qsfp_ctrlb, 1,   0, 1, 2, 3 ),
             12: (self._qsfp_ctrlb, 1,   4, 5, 6, 7 ),
             13: (self._qsfp_ctrlb, 0,   0, 1, 2, 3 ),
             14: (self._qsfp_ctrlb, 0,   4, 5, 6, 7 ),
             15: (self._qsfp_ctrlb, 3,   0, 1, 2, 3 ),
             16: (self._qsfp_ctrlb, 3,   4, 5, 6, 7 )
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

    def open(self):
        """
        """
        pass


    def close(self):
        self._logger.info('Closing Icebox hardware')

    def init(self):
        """Initializes the backplane hardware to a known state"""


        # Check if the fan controller is connected
        self._fan_ctrl_present = self._fan_ctrl.is_present()

        # Check if the power/reset control IO expander is accessible
        self._reset_ctrl_present = self._reset_ctrl.is_present()

        self._init_qsfp_ctrl()
        if self._reset_ctrl_present:
            self._init_reset_ctrl()  # The power I2c bus needs to be bridged to the monitor I2C bus for this to work
        self._init_eeprom()
        self._init_temperature_sensors()
        self._init_power_sensors()
        if self._fan_ctrl_present:
            self._fan_ctrl.init()
        self._i2c.select_bus([])  # Make sure we don't load the bus

    def _init_temperature_sensors(self, temperature_sensor_name=None):
        """
        initializes temperature sensors
        'temperature_sensor_name' can be a list of temperature sensor names found in TEMPERATURE_SENSOR_TABLE.

        History:
        140318 JM: created
        """
        if temperature_sensor_name is None:
            temperature_sensor_name = self.TEMPERATURE_SENSOR_TABLE.keys()
        elif isinstance(temperature_sensor_name, str):
            temperature_sensor_name = [temperature_sensor_name]

        for temp_sensor in temperature_sensor_name:
            if temp_sensor not in self.TEMPERATURE_SENSOR_TABLE:
                raise ValueError('Invalid temperature sensor name')
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
                raise ValueError('Invalid current/power monitor name')
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
        self._reset_ctrl.init(
            cfg0_def=0xFF, cfg1_def=0xFF, cfg2_def=0xFF,
            cfg3_def=0xFF, cfg4_def=0xFF,
            out0_def=0x15, out1_def=0xFF, out2_def=0xFF,
            out3_def=0xFF, out4_def=0xFF)
        #By default setting all pins to inputs, with default output level logic 1 (no reset possible) for all banks except 0
        #On bank 0, default levels are such that LED default is 0, Reset clear is active, and reset pins are functionality is maximily off

    def _init_eeprom(self):
        """initializes EEPROM"""
        pass

    def get_number_of_slots(self):
        return self.NUMBER_OF_SLOTS

    def read_backplane_eeprom(self, addr, length=1, **kwargs):
        return self._eeprom_data.read(addr, length, **kwargs)

    def write_backplane_eeprom(self, addr, data, **kwargs):
        return self._eeprom_data.write(addr, data, **kwargs)

    # def is_backplane_present(self):
    #     """ Detect if the backplane is present by probing its EEPROM with a dummy I2C acces.
    #     """
    #     return self._eeprom_data.is_present() # perform a dummy access

    # def read_eeprom(self, addr, length=1):
    #     return self._eeprom.read(addr, length = length)

    def get_backplane_eeprom_serial_number(self):
        """ return the 128-bit hardware-coded EEPROM serial number as a hex string. """
        return ''.join(['%02X' % ord(v) for v in self._eeprom_serial.read(0x80, length=16)])

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
                raise ValueError('Invalid LED name')
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
                raise ValueError('Invalid LED name')
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
                raise ValueError('Invalid temperature sensor name')
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
                raise ValueError('Invalid power sensor name')
            else:
                power_sensor_list = self.POWER_SENSOR_TABLE[power_sensor]
                power_object = power_sensor_list[0]
                power_dict[power_sensor]=(power_object.get_bus_voltage(), power_object.get_shunt_voltage(), power_object.get_current(), power_object.get_power())

        return power_dict


    def get_serial_number(self):
        """
        Returns the board's serial number.
        """
        return self.get_backplane_eeprom_serial_number(); # tentative code

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
                raise ValueError('Invalid Slot number %i' % slots)

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
                raise ValueError('Invalid Slot number %i' % slotnum)
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
                raise ValueError('Invalid Slot number %i' % slotnum)
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
            raise ValueError('Must perform action on one slot at a time. Slot must be an integer.')
        if slot not in range(1,self.NUMBER_OF_SLOTS + 1) :
            raise ValueError('Invalid Slot number %i' % slot)
        qstatus=self.qsfp_status(slot)

        if not qstatus['present'][0]:  #Checking to see if QSPF present
            raise RuntimeError('No QSFP device loaded on slot number %i' % slot)

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
                raise ValueError('Invalid Slot number %i' % slotnum)
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
        if not self._reset_ctrl_present:
            raise RuntimeError('The Power/Reset backplane I/O Expander was not detected at init. Was the POW I2C bus accessible?')

        if slots=='ALL' and state==1:  #We wish to perform a full crate reset

            if reset_type not in self.FULLBP_RESETS_MAP:
                raise ValueError('Unknown reset type %s' % reset_type)
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
                if slot == self._iceboard.slot_number:
                    print 'Warning, will not perform reset on the controlling slot %i' % slot

                # if isenabled and slot != self._iceboard.slot_number  :
                elif slot not in range(1, self.NUMBER_OF_SLOTS + 1) :
                    raise ValueError('Invalid Slot number %i' % slot)
                else:
                    (reset_control_obj, arm_reset_reg, power_down_reg, bitnumber) = self.SLOT_RESETS_MAP[slot]
                    if resettype == 'ARM':
                        reset_cfg_register ='CFG%i' % arm_reset_reg
                        reset_output_register = 'OUT%i' % arm_reset_reg
                    elif resettype == 'POWER':
                        reset_cfg_register = 'CFG%i' % power_down_reg
                        reset_output_register = 'OUT%i' % power_down_reg
                    else:
                        raise ValueError('Unknown reset type, will not perform reset on slot %i' % slot)

                    mask = 1 << bitnumber
                    if isenabled == 1 or isenabled == 'pulse':  # Turning reset on

                        reset_control_obj.write(reset_output_register, 0, mask) #Setting output register to logic 0 (reset active)
                        reset_control_obj.write(reset_cfg_register, 0, mask) #Setting direction register from input to output - Performing reset

                    if isenabled == 0 or isenabled == 'pulse':  #Turning reset off
                        if isenabled=='pulse':
                            time.sleep(2)
                        reset_control_obj.write(reset_output_register,  mask, mask) #Setting output register to logic 1 (reset inactive) - Removing reset
                        reset_control_obj.write(reset_cfg_register,  mask, mask) #Setting direction register from output to input - Back to default state

    def set_fan_speed(self, speed):
        """ Set the speed of the crate fan. `speed` is a value from 0 to 100.
        """
        if not self._fan_ctrl_present:
            raise RuntimeError('There is no fan controller connected on the backplane I2C bus')
        self._fan_ctrl.set_duty_cycle(speed)




@session.register_yaml_object()
class IceCrate_MGK7BP1(IceCrate):
    handler_name = 'IceCrate_MGK7BP1_Handler'
    __mapper_args__ = {'polymorphic_identity': 'IceCrate_MGK7BP1'}
    __ipmi_part_number__ = ['MGK7BP1']  # Must match part number in IPMI data

class IceCrate_MGK7BP1_Handler(IceCrateHandler):
    """
    Provides access to the 1-slot test backplane.
    """

    #------------------------------------
    # Define hardware-specific constants
    #------------------------------------
    NUMBER_OF_SLOTS = 1 #
    BACKPLANE_EEPROM_DATA_ADDRESS = 0x54 # covers 0x54 - 0x57 ( 4 pages of 256 bytes, 1024 Bytes total)
    BACKPLANE_EEPROM_SERIAL_ADDRESS = 0x5C # 16 byte serial number starting at memory address 0x80
    BACKPLANE_EEPROM_ADDRESS_WIDTH = 10 # 2 bits are in the device address, the remaining are in the address byte following the command byte


    _GPIO_CTRL_ADDR = 0b0101111

    # The following dictionnary describes the connectivity of the 10 Gbps mesh.
    # It indicates which transmitter (slot and lane number) is feeding a specified receiver.
    # The dictionnary is indexed by receiver number.
    _BP_RX_TO_TX_MAP = { (i,0):(i,0) for i in range(16)}
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

        self._logger.info(' Instantiating Backplane I2C I/O expanders')
        self._gpio_ctrl = pca9575.pca9575(self._i2c, self._GPIO_CTRL_ADDR, 'BP')


        self._GPIO_CTRL_MAP = {
             # Slot num : (expander object, Register, bit number)
             'SLOTADDR0': (self._gpio_ctrl, 0,0),
             'SLOTADDR1': (self._gpio_ctrl, 0,1),
             'SLOTADDR2': (self._gpio_ctrl, 0,2),
             'SLOTADDR3': (self._gpio_ctrl, 0,3),

             'SYNC':  (self._gpio_ctrl, 0,6),
             'TIME':  (self._gpio_ctrl, 1,3),
             'TRIG':  (self._gpio_ctrl, 1,4),

             'PLLSYNC': (self._gpio_ctrl, 0,7),

             'BPIO3': (self._gpio_ctrl, 1,0),
             'BPIO4': (self._gpio_ctrl, 1,1),
             'BPIO5': (self._gpio_ctrl, 1,2)
        }

        self.LED_MAP = {
             # LEDName : (expander object, Register, bit number)
             'LED1': (self._gpio_ctrl, 1, 5),
             'LED2': (self._gpio_ctrl, 1, 6),
             'LED3': (self._gpio_ctrl, 1, 7)
        }

        self._RESETS_MAP = {
             # ResetType : (expander object, Register, bit)
             'ARM':       (self._gpio_ctrl, 0, 4),
             'FPGA':      (self._gpio_ctrl, 0, 5)
        }

    def open(self):
        """
        """
        pass

    def close(self):
        self._logger.info('Closing Icebox hardware')

    def init(self):
        """Initializes the backplane to a known state"""
        self._init_gpio_ctrl() # The power I2c bus needs to be bridged to the monitor I2C bus for this to work
        self._init_eeprom()



    def _init_gpio_ctrl(self):
        """
        initializes reset control
        History:
        141075 AJG: created
        """
        gpio_ctrl=self._gpio_ctrl

        gpio_ctrl.init(cfg0_def=0xFF, cfg1_def=0xFF)
        #By default setting all pins to inputs, with default output level logic 0

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
                name='LED%i' % name
            led_name[pos]=name

        if isinstance(state, (bool, int)):
            state = [state] * len(led_name)

        for (led, led_state) in zip(led_name,state):
            if led not in self.LED_MAP:
                raise IceBoxException('Invalid LED name')
            else:
                (led_control_object, led_control_register, led_control_bitnumber) = self.LED_MAP[led]
                mask = 1<<led_control_bitnumber
                led_control_object.write('CFG%i' % led_control_register, 0, mask=mask) #Setting LED pin to output
                led_control_object.write('OUT%i' % led_control_register, mask * bool(not(led_state)), mask=mask) #Turning LED on and off

    def get_led(self, led_name):
        """
        Returns the status of specified LED(s) in a dictionary
        led_status where each key is a led_name and the respective value
        is the led status.
        """
        led_status = {}
        if isinstance(led_name, (str,int)):
            led_name = [led_name]

        for pos, name in enumerate(led_name):
            if isinstance(name, int):
                name='LED%i' % name
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

    def set_slot_addr(self, slotnum):
            """
            Sets the backplane slot number to the number specified slot number from 1 to 16
            """

            if slotnum not in range(1,16 + 1):
                    raise IceBoxException('Invalid slot number')
            slotnum-=1  #Slot 1 is binary 0000, slot 16 is binary 1111

            for addr in range(0,4):
                (ctrlobj, reg, bitnum) = self._GPIO_CTRL_MAP['SLOTADDR%i' % addr]
                mask = 1<<bitnum
                ctrlobj.write('CFG%i' % reg, 0, mask=mask) #Setting addr pin to output

                bitlevel= (slotnum >> addr) & 1
                ctrlobj.write('OUT%i' % reg, mask * bitlevel, mask=mask) #Turning pin off

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






































