"""
Icecore example Example code that demonstrate the use of the 'icecore' library
to access arrays of IceBoards and use that talk to the example FPGA firmware.


You can execute this script in ipython with:

run -i example1.py --log_target test.log --log_level debug --iceboards 10.10.10.7

You must specify the iceboard hostname (or ip address) with --iceboards.

--log_target is either, 'syslog', 'stream' for screen logging, or a filename.

--log_level is either 'debug' or 'info'

-- bitstream specifies the filename of the FPGA bitstream. If not specified,
   it defaults to the example FPGA firmware found in
       icecore/rtl/projects/iceboard_top_example/iceboard_top_example.runs/impl_1/iceboard_top_example.bit

By using the option '-i' with the ipython 'run' command, your ipython session
will have interactive access to all the variables that have been created by
the script. This is useful to play around with the iceboard object.
"""

import logging
import time
import sys

# Our example design uses the dummy 'examples/icecore' package which
# redirects to the top icecore package. If you run this in another folder than
# /examples or use another package name,  update the imports below and make
# sure that the package is accessible from the script location.
from icecore import IceBoard, IceBoardHandler
from icecore.session import load_session as load_yaml_hardware_map

from example_helper import get_command_line_arguments

#---------------------------------------------------------------------------
class FpgaBitstream(object):
    """ Helper object used to load and store a FPGA bitstream. You don't have
    to use it, but it makes the code look nicer"""
    bitstream = None

    def __init__(self, filename):
        with open(filename, 'rb') as file_:
            self.bitstream = file_.read()

    def __str__(self):
        """ Return the bitstream as a string. """
        return self.bitstream


#---------------------------------------------------------------------------
class ExampleIceBoardHandler(IceBoardHandler):
    """ Object used to handle your application-specific FPGA firmware.

    This handler gives access to the features available in the example FPGA
    firmware provided with the icecore.

    By inheriting IceBoardHandler, you also get all the basic functionalities
    of the IceBoard available from the IceBoardHandler object and the on-board
    ARM processor. This also gives you FPGA memory-mapped interface methods,
    which we use to access the example firmware registers. registers in your
    FPGA firmware.
    """
    # The attribute below is mandatory and allows this class to be
    # automatically registered as a handler for IceBoard
    __handler_for__ = IceBoard

    # Define firmware-specific constants
    USER_REGISTERS_BASE_ADDR = 0x00000100
    NUMBER_OF_USER_REGISTERS = 4
    LED_CONTROL_REG_ADDR = USER_REGISTERS_BASE_ADDR + 0x00
    OP1_REG_ADDR = USER_REGISTERS_BASE_ADDR + 0x04
    OP2_REG_ADDR = USER_REGISTERS_BASE_ADDR + 0x08
    SUM_REG_ADDR = USER_REGISTERS_BASE_ADDR + 0x0C

    def set_user_fpga_register(self, register_number, value):
        """ Read a 32-bit user register by register number."""
        if register_number >= self.NUMBER_OF_USER_REGISTERS:
            raise ValueError('Invalid register number')
        self.fpga_mmi_write(self.USER_REGISTERS_BASE_ADDR + 4 * register_number, value)

    def get_user_fpga_register(self, register_number):
        """ Write a 32-bit user register by register number."""
        if register_number >= self.NUMBER_OF_USER_REGISTERS:
            raise ValueError('Invalid register number')
        return self.fpga_mmi_read(self.USER_REGISTERS_BASE_ADDR + 4* register_number)

    def firmware_add(self, op1, op2):
        """ Sets the operands of the firmware 32-bit adder and get the
        resulting sum.
        """
        self.fpga_mmi_write(self.OP1_REG_ADDR, op1)
        self.fpga_mmi_write(self.OP2_REG_ADDR, op2)
        return self.fpga_mmi_read(self.SUM_REG_ADDR)

    def set_fpga_leds(self, led1, led2):
        """ Set the state of the FPGA leds located on the back edge of the
        IceBoard.
        """
        self.fpga_mmi_write(self.LED_CONTROL_REG_ADDR, bool(led1) | (bool(led2) << 1))


if __name__ == '__main__':
    """
    Demonstrates typical uses of the IceCore infrastructure.

    We first create a hardware map that describes the available iceboards. We
    then query that hardware map to select iceboards, we configure the
    firmware, and run little tests that make use of the features available in
    the example FPGA firmware.
    """

    # Get command line arguments
    args = get_command_line_arguments()

    # Set-up logging
    logger = logging.getLogger('')
    logger.setLevel(args.log_level)
    logger.addHandler(args.log_handler)

    # Load the bitstream and assign it to our handler
    if args.bitfile:
        fpga_bitstream = FpgaBitstream(args.bitfile)
        ExampleIceBoardHandler.register_fpga_bitstream(fpga_bitstream)

    # Create a YAML hardware map. Normally this loaded from a text file that
    # was created by the user for a specific experiment, but we dynamically
    # create it here because we don't know what boards the users will have
    # when running this example.
    yaml_hwm = """
        !HardwareMap
        - !IceBoard {{hostname: {0}, handler_name: "ExampleIceBoardHandler"}}
        """.format(args.iceboards[0])

    # Load the hardware map, which defines every piece of the hardware in the
    # array. For now, we have only one IceBoard.
    hwm = load_yaml_hardware_map(yaml_hwm)

    # Get the only Iceboard of the map
    ib = hwm.query(IceBoard).one()

    # Configure the FPGA with the bitstream associated with the handler
    if fpga_bitstream:
        ib.set_fpga_bitstream()

    # Check that we can read and write a user-defined 32-bit register in the
    # FPGA firmware
    test_value = 0x12345678
    for i in range(ib.NUMBER_OF_USER_REGISTERS):
        ib.set_user_fpga_register(i, test_value)
        read_value = ib.get_user_fpga_register(i)
        print 'Wrote register %i with 0x%08X, read back 0x%08X' % (i, test_value, read_value)

    # Test our firmware adder
    print 'Firmware add: %i + %i = %i ' % (10, 13, ib.firmware_add(10,13))

    # Test led control by blinking the FPGA leds for a while

    print 'FPGA Leds are now blinking. Check it out!'
    sys.stdout.flush() # Make sure the previous message is shown

    for i in range(16):
        ib.set_fpga_leds(led1=i & 0b01, led2=i & 0b10)
        time.sleep(0.3)
    print 'Done.'

