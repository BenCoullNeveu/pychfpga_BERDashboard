# Standard Python packages
import logging

# Local packages
from pychfpga.common import run_async, async_to_sync

from pychfpga.hardware.mezzanine import Mezzanine
from .icecore.hardware_assets import FMCMezzanineBase


class FMCMezzanine(Mezzanine, FMCMezzanineBase):
    """
    Provides the basic methods needed to operate a mezzanine.
    """

    part_number = None
    _ipmi_part_numbers = None  # Must match part number in IPMI data

    async def set_mezzanine_power_async(self, state):
        await self.iceboard.tuber_set_mezzanine_power_async(bool(state), self.mezzanine)

    async def get_mezzanine_power_async(self):
        return await self.iceboard.tuber_get_mezzanine_power_async(self.mezzanine)

    async def is_mezzanine_present_async(self):
        return await self.iceboard.tuber_is_mezzanine_present_async(self.mezzanine)

    def is_mezzanine_present(self):
        return self.iceboard.is_mezzanine_present(self.mezzanine)
