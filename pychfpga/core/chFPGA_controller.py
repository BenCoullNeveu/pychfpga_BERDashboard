#!/usr/bin/python

"""
This module defines the `chFPGA_controller` class, which provides a Python interface to operate an
IceBoard and its chFPGA firmware.

.. Notes:
..     Created 2011-01-10. See GIT for commit history.
"""

# Python Standard Library packages
import logging
import time
import os
import pickle
from datetime import datetime
from collections import OrderedDict
from functools import wraps
import subprocess
import shlex
import bz2
import socket
import __main__
import asyncio
import traceback

# PyPi external packages
import numpy as np
import yaml

# Private external packages

from wtl.metrics import Metrics

# Local packages

# from .icecore.session import load_session as load_yaml
# from .icecore import load_yaml  # Py3: non-database version
from .icecore_ext.iceboard_ext import IceBoard, async_to_sync, run_async

from .chFPGA_receiver import chFPGA_receiver
# from pychfpga.common import util  # Py3: does not seem to be used

from .icecore_ext.tcpipe import TCPipe_BSB_MMI


class chFPGA_controller(IceBoard):
    def __init__(
            self,
            hostname=None,
            serial=None,
            subarray=None,
            slot=None,
            fpga_ip_addr=None):
        """
        Creates an empty IceBoard/chFPGA handler object, but do not interact with the board yet.

        Parameters:

            hostname (str): hostname or IP address of the ICEBoard ARM
                processor (mandatory)

            serial (str): Serial number of the board. Can be provided by the
                ARM.

            crate (IceCrateHandler): = object that handle the backplane on
                which the board is connected. ``None`` if the board is not
                connected to a backplane.

            slot (int): Slot number in which the board is installed ona
                backplane. None if there is no backplane.


        The `__init__` function stores the parameters as instance attributes
        of the same name.

        Note: `__init__` *only* create an empty `chFPGA_controller` object and hold basic
            configuration information but does not attempt to interact with the FPGA. Interaction
            with the FPGA starts with `open`. This means that `chFPGA_controller` objects can be
            created for board that do not exist are are not powered up yet. This is useful when
            arrays of boards are loaded from an unfiltered hardware map.
        """

        super().__init__(
            hostname=hostname,
            serial=serial,
            slot=slot,
            subarray=subarray,
            fpga_ip_addr=fpga_ip_addr,
            local_control_port_number=None  # 0: always select randomly,  `None`:use crate/slot if available else randomly
            )
