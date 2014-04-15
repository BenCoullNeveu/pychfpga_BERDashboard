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
from hardware_map import HWMResource, Integer, Column, String, ForeignKey, UniqueConstraint, reconstructor

class FpgaFirmware(HWMResource):
    """
    Represents the firmware that is running or to be run on the IceBoard FPGA.
    """

    __tablename__ = 'fpgafirmware'
    __mapper_args__ = {
            'polymorphic_on': 'firmware_class',
            'polymorphic_identity': 'fpgafirmware'
    }

    pk = Column(Integer, primary_key=True)

    firmware_class = Column(String, nullable=False) # String that identifies the class of this object (is set to polymorphic_identity defined above, which is redefined by subclasses)
    firmware_filename = Column(String, nullable=False)
    firmware_crc32 = Column(Integer)

    firmware_bitstream = None # we don't have access to the actual bistream data until it is loaded.


    def __init__(self, bitstream_object):
        self.logger = logging.getLogger(__name__)
        self.firmware_filename = bitstream_object.filename
        self.firmware_crc32 = bitstream_object.crc32
        self.firmware_bitstream_object = bitstream_object

    @reconstructor
    def _init_from_database(self):
        """
        Re-creates the firmware object from the database data.
        """
        #try to reload the bitstream
        self.logger = logging.getLogger(__name__)
        # we leave the local self.bistream set to None.
        # bitstream = FpgaBitFile(self.filename)
        # if bitstream.crc32 != self.bitstream.crc32:
        #     self.logger.warning('Bitstream does not have the expected CRC')
        # self.firmware_class = pickle.loads(self.firmware_class_pickle)


