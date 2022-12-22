#!/usr/bin/python

"""
hmc7044: Interface to the Analog Device HMC7044 PLL.

"""

import time
import os


class hmc7044(object):
    """
    Implements the interface to the Analog Device HMC7044 PLL.
    """

    RESET_REG = 0x0000
    REQUEST_REG = 0x0001

    regs = dict(
    # field_name = (addr, high_bit, low_bit, default)
    glbl_cfg1_swrst = (RESET_REG, 0, 0, 0x00),

    glbl_cfg1_sleep = (REQUEST_REG, 0, 0,  0x0),
    glbl_cfg1_restart = (REQUEST_REG, 1, 1,  0x0),
    sysr_cfg1_pulsor_req = (REQUEST_REG, 2, 2,  0x0),
    pll1_cfg1_forceholdover = (REQUEST_REG, 4, 4,  0x0),
    glbl_cfg1_perf_pllvco = (REQUEST_REG, 5, 5,  0x0),
    dist_cfg1_perf_floor = (REQUEST_REG, 6, 6,  0x1),
    sysr_cfg1_reseed_req = (REQUEST_REG, 7, 7,  0x0),

    sysr_cfg1_rev=(0x0002, 0, 0, 0x0),
    sysr_cfg1_slipN_req=(0x0002, 1, 1, 0x0),
    pll2_cfg1_autotune_trig=(0x0002, 2, 2, 0x0),

    glbl_cfg1_ena_pll1=(0x0003, 0, 0, 0x1),
    glbl_cfg1_ena_pll2=(0x0003, 1, 1, 0x1),
    glbl_cfg1_ena_sysr=(0x0003, 2, 2, 0x0),
    glbl_cfg2_ena_vcos=(0x0003, 4, 3, 0x1),
    glbl_cfg1_ena_sysri=(0x0003, 5, 5, 0x0),

    glbl_cfg7_ena_clkgr=(0x0004, 6, 0, 0x7F),

    glbl_cfg4_ena_rpath=(0x0005, 3, 0, 0xF),
    dist_cfg1_refbuf0_as_rfsync=(0x0005, 4, 4, 0x0),
    dist_cfg1_refbuf1_as_extvco=(0x0005, 5, 5, 0x0),
    pll2_cfg2_syncpin_modesel=(0x0005, 7, 6, 0x0),

    glbl_cfg1_clear_alarms=(0x0006, 0, 0, 0x0),
    )

    def __init__(self, spi_interface, spi_port=0, verbose=0):
        """
        """
        self.spi = spi_interface
        self.spi_port = spi_port

    def init(self, filename="../crs/CRS_CHORD_3000MHz.py"):
        """Initializes the PLL.

        """

        # self.reset()

        if filename:
            regs = self.load_config_file(filename)
            self.write_regs(regs)
        else:
            # Load the configuration updates (provided by Analog Devices) to
            # specific registers (see Table 74)
            self.set_reserved_control_registers()

            # Program PLL2. Select the VCO range (high or low). Then
            # program the dividers (R2, N2, and reference doubler).
            self.set_pll2()

            # Program PLL1. Set the lock detect timer threshold based
            # on the PLL1 BW of the user system. Set the LCM, R1, and
            # N1 divider setpoints. Enable the reference and VCXO
            # input buffer terminations.
            self.set_pll1()

            # Program the SYSREF timer. Set the divide ratio (a
            # submultiple of the lower output channel frequency). Set the
            # pulse generator mode configuration, for example, selecting
            # level sensitive option and the number of pulses desired.
            self.set_sysref()

            # Program the output channels. Set the output buffer modes
            # (for example, LVPECL, CML, and LVDS). Set the divide
            # ratio, channel start-up mode, coarse/analog delays, and
            # performance modes.
            self.set_outputs()

        # Wait until the VCO peak detector loop has stabilized, 10 ms after set_pll2
        time.sleep(0.01)

        # Issue a software restart to reset the system and initiate
        # calibration. Toggle the restart dividers/FSMs bit to 1 and
        # then back to 0.
        self.restart()

        # Wait for PLL2 to be locked (takes ~50 μs in typical configurations).

        # Confirm that PLL2 is locked by checking the PLL2 lock detect bit.

        # Send a sync request via the SPI (set the reseed request bit) to align the divider phases and send any initial pulse generator stream.

        # Wait 6 SYSREF periods (6 × SYSREF Timer[11:0]) to allow the outputs to phase appropriately (takes ~3 μs in typical configurations).

        # Confirm that the outputs have all reached their phases by checking that the clock outputs phases status bit = 1.

        # Wait for PLL1 to lock. This takes ~50 ms for a 100 Hz BW (from Step 11).

        # When all JESD204B slaves are powered and ready, send a pulse
        # generator request to send out a pulse generator chain on any SYSREF
        # channels programmed for pulse generator mode.



    def reset(self):
        self.write_reg(self.RESET_REG, 1)


    def restart(self):
        self.write_reg(self.REQUEST_REG, 2)


    def load_config_file(self, filename="../crs/CRS_CHORD_3000MHz.py"):
        """ Load HMC7044 configuration file as saved by the Analog Device HMC7044 Configuration GUI software.

        The configuration file is a python script with a series of write commands (e.g. ``dut.write(0x6, 0x0)``) for each register from the first to the last.
        The same register address is not repeated, and the writes are not made in a particular initialization sequence.
        Just writing the content of the registers to the PLL does not guarantee proper initialization.

        Returns:
            a list containing the (register_address, values) found in the file.
        """

        fullpath = os.path.join(os.path.dirname(__file__), filename)
        regs = []
        with open(fullpath, 'r') as f:
            for line in f.readlines():
                if line.startswith('dut.write'):
                    reg, val = eval(line[9:])
                    regs.append((reg, val))
        return regs


    def write_regs(self, regs):
        """Write a list of (register, value) tuples to the PLL.

        Parameters:
            regs (list): list of (register_address, value) tuples, where ``register_address`` and ``value`` are 13-bit and 8-bit values respectively.
        """

        for (reg, val) in regs:
            print(f'Writing Reg {reg:04X} with 0x{val:02X}')
            self.write_reg(reg, val)
            time.sleep(0.1)

    def write_reg(self, reg, val):
        """ Writes the register `reg` with 8-bit value `val`

        Parameters:

            reg (int): 13-bit address of register to write

            val (int): 8-bit value to write to the register
        """

        reg &= 0x1FFF  # limit register address to 13 bit
        spi_data = bytes([reg >> 8, reg & 0xFF, val]) # r/w=0, W1=0, W0=0
        self.spi.write_read(self.spi_port, spi_data, read_length=0)

    def read_reg(self, reg):
        """ Read the8-bit value from register `reg`.

        Parameters:

            reg (int): 13-bit address of register to read

        Returns:

            (int): 8-bit value that was read from the register
        """

        reg &= 0x1FFF  # limit register address to 13 bit
        spi_data = bytes([(reg >> 8) | 0x80, reg & 0xFF]) # r/w=0, W1=0, W0=0
        val = self.spi.write_read(self.spi_port, spi_data, read_length=1)
        return val[0]

    # def write_word(self, value):
    #         self.write(value.to_bytes(3, 'big'))  # Commands are 24-bits wide

