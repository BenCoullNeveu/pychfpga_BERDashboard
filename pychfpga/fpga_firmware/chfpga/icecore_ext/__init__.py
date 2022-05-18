""" Icecore Extensions

This package provide IceBoard and IceCrate classes that extends the features offered by the Icecore library:
	- Basic IceBoard, IceCrate  objects
	   - Are self-managed by a lightweight, list-based dynamic hardware map
	   - IceBoard completely FPGA firmware agnostic
	   - Self discovery of model, serial numbers, slot number, crate and mezzanines by the Iceboard
	   - Exposes the SPI-based memory-mapped interface to the FPGA (via the ARM)

   - IceBoardPlus adds:
	  - Assumes a basic icecore FPGA firmware
	  - Provides access to a basic set of icecore firmware SPI register
	  - Provides more advanced bitstream management, with already-programmed bitstream detection

   - Defines a IceCrateExt and IceCrateExtHandler:
	  - Assumes a chfpga-like core FPGA firmware
	  - Provides access to an extended set of icecore firmware functionalities accessed through the SPI:
	  	- IRIG-B
	  	- Frame number capture
	  	- FPGA direct IP networking configuration
      - Provides access the FPGA memory map over a direct Ethernet link with the FPGA
      - Provides access to core UDP-accessed firmware functionalities
      	- GPIO, SPI, I2C
      - Provides access to the IceBoard hardware via the FPGA
      - Defines functionnalities specific to the MGK7BP16 backplane
"""
# from .iceboard_ext import HardwareMap
from .motherboard import Motherboard
from .crate import Crate
from .icecrate_ext import IceCrate
from .iceboard_ext import IceBoard  #, IceBoardPlus, IceBoardExt
from .zcu111 import ZCU111
from .iceboard_ext import FMCMezzanine
from .async_utils import run_async, async_to_sync
from .fpga_firmware import FPGAFirmware
from .fpga_bitstream import FPGABitstream
from .mdns_discovery import mdns_discover, mdns_resolve
from .ccoll import Ccoll
# from .myasync import myasync, async_sleep, async_return, async_moment
