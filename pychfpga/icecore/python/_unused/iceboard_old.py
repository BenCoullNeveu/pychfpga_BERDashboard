"""Base object for IceBoard objects.

To specialize an IceBoard object for a particular experiment, you're
encouraged to create a subclass. There should be good examples
available.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from tuber import TuberHWMResource
import fmc_mezzanine


class IceBoard(TuberHWMResource):
    __tablename__ = 'iceboards'
    __table_args__ = (
        UniqueConstraint('serial_number'),
    )
    __mapper_args__ = {
            'polymorphic_identity': 'iceboard',
            'polymorphic_on': 'cls'
    }

    pk = Column(Integer, primary_key=True)
    cls = Column(String, nullable=False)
    tuber_objname = Column(String, nullable=False, default='iceboard')

    # Set up explicit mezz1 / mezz2 links.
    mezz1_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz1 = relationship("FMCMezzanine", foreign_keys=[mezz1_pk])

    mezz2_pk = Column(Integer, ForeignKey('fmc_mezzanines.pk'), index=True)
    mezz2 = relationship("FMCMezzanine", foreign_keys=[mezz2_pk])

    # Although we've already catalogued the mezz linkages, it's sometimes
    # useful to use an array. (For example, it lets us trivially write
    # join() calls in HWM queries.)
    mezz = relationship("FMCMezzanine",
        uselist=True,
        primaryjoin="or_(FMCMezzanine.pk==IceBoard.mezz1_pk,FMCMezzanine.pk==IceBoard.mezz2_pk)",
    )

    serial_number = Column(Integer)
    revision = Column(Integer)

    def configure_fpga(self, buf):
        '''
        Configures the FPGA with the specified buffer.

        The buffer is an ordinary string object or similar, and
        contains an already loaded .BIT or .BIN file. We hash it
        here, but the FPGA itself is responsible for accepting
        or rejecting it. (It's got internal checksums and will
        notice if you pass it garbage.)
        '''

        import base64, hashlib

        md5_string = hashlib.md5(buf).hexdigest()
        b64_string = base64.b64encode(buf)
        self.load_fpga_bitstream(b64_string, md5_string)

# vim: sts=4 ts=4 sw=4 tw=80 smarttab expandtab
