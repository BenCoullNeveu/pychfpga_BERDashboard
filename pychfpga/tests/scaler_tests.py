import argparse
import logging
import __main__

import matplotlib.pyplot as plt
import numpy as np

# NOTE: PYTHONPATH must be set so 'pychfpga' can be found
from pychfpga.core.icecore.tests import *

from pychfpga.core.icecore import IceBoardPlus, IceBoardPlusHandler, IceCrate, HardwareMap
from pychfpga.core.chFPGA_controller import chFPGA_controller
from pychfpga.core.chFPGA_receiver import chFPGA_receiver
from pychfpga.core.icecore.session import load_session as load_yaml_hardware_map

class ScalerTests(TestGroup):
    '''Tests the chFPGA SCALER operation.

    This is the top-level Quality Control script for the SCALER tests.
    '''

    def test_list(self):
        yield self.chfpga_init
        yield self.dummy_test

    def chfpga_init(self, ib):
        """ Initialize chFPGA firmware.
        """
        ib.open()
        config = ib.get_config()
        ib.r = chFPGA_receiver(config)

        yield PASSED(True)

    def dummy_test(self, ib):
        """ Dummy test function.

        No description
        """
        yield PASSED(True)


# class I2CTests(TestGroup):
#     '''I2C tests'''

#     def test_list(self):
#         yield self.test_eeprom_presence
#         yield self.get_eeprom_serial_number
#         yield self.test_image

#     def test_eeprom_presence(self, ib):
#         """ Check is the backplane is present.

#         For this we check if the backplane EEPROM responds to a dummy I2C command.
#         """
#         is_present = ib.is_backplane_present()
#         # yield is_present  # This is the PASS/FAIL criteria
#         # It would be clearer if we could just do
#         yield PASSED(is_present)

#         yield SUMMARY("Backplane is %spresent" % ('' if is_present else 'NOT '))

#         d= {1:1, 2:2, 3:3}
#         yield DETAILS(P('This was a good test. result is %r' % d))

#     def get_eeprom_serial_number(self, ib):
#         """ Get the backplane EEPROM serial number.
#         """
#         try:
#             serial = ib.bp.get_backplane_eeprom_serial_number()
#         except RuntimeError:
#             serial = None

#         yield PASSED(bool(serial)) # This is the PASS/FAIL criteria

#         yield SUMMARY("Backplane serial ]</div> is 0x%s" % (serial))
#         yield DETAILS(P('This was a good test'))
#         yield DETAILS(P('A very good test indeed'))
#         yield DETAILS('A test without P')
#         yield 'And a detail witout DETAIL'
#         yield """ This is a very long
#         multi-line comment. """
#         yield P(""" and this is
#         another one that doen't show""")
#         yield 123

#     def test_image(self, mezzanine):
#         '''Here's something that always fails, descriptively.'''

#         yield PASSED(False)

#         plt.figure(1)
#         plt.clf()
#         x = np.arange(1000)/100.
#         y = np.sin(x)
#         plt.plot(x,y)

#         yield PLOT('This is a sinewave that unequivoqually explains the test failure')


# class RailTests(TestGroup):
#     '''Voltage rails'''

#     def gen(self):
#         def test_vadj(mezzanine):
#             '''VADJ rail tolerance'''
#             return self.test_rail(mezzanine, 'MEZZANINE_RAIL_VADJ', 2.5)

#         def test_3v3(mezzanine):
#             '''3V3 rail tolerance'''
#             return self.test_rail(mezzanine, 'MEZZANINE_RAIL_VCC3V3', 3.3)

#         def test_12v(mezzanine):
#             '''12V rail tolerance'''
#             return self.test_rail(mezzanine, 'MEZZANINE_RAIL_VCC12V0', 12)

#         yield test_3v3
#         yield test_vadj
#         yield test_12v

#     def test_rail(self, mezzanine, rail, nom):
#         '''Testing mezzanine rail.'''

#         lo = nom*.95
#         hi = nom*1.05
#         got = mezzanine.get_mezzanine_voltage(rail)

#         if got < lo:
#             return False, \
#                 SUMMARY("%.2fv rail: Measured %.2f, lower bound %.2f" % \
#                         (nom, got, lo))
#         if got > hi:
#             return False, \
#                 SUMMARY("%.2fv rail: Measured %.2f, upper bound %.2f" % \
#                         (nom, got, hi))
#         return True


# class BasicTests(TestGroup):
#     '''Basic tests

#     This is a pretty degenerate test case right now, but it will eventually do
#     things that test the mezzanine's communications etc.
#     '''

#     def gen(self):
#         yield self.test_serial
#         yield self.test_something_that_fails

#     def test_serial(self, mezzanine):
#         '''Ensure the IPMI serial number matches the HWM.'''
#         expected = mezzanine.serial
#         got = mezzanine._get_mezzanine_serial()
#         if expected==got:
#             return True
#         return False, SUMMARY("got %s, expected %s" % (got, expected))

class FpgaBitstream(object):
    """ Helper object used to load and store a FPGA bitstream. You don't have
    to use it, but it makes the code look nicer"""
    bitstream = None

    def __init__(self, filename, auto_reload=True):
        self.filename = filename
        self.auto_reload = auto_reload
        if not self.auto_reload:
            self._load()
    def __str__(self):
        """ Return the bitstream as a string. """
        if self.auto_reload:
            self._load()
        return self.bitstream
    def _load(self):
        with open(self.filename, 'rb') as file_:
            self.bitstream = file_.read()


if __name__=='__main__':

    # Get command line arguments
    default_bitfile = (
        '../../../chfpga/xilinx_projects/CHFPGA_MGK7MB_REV2/CHFPGA_MGK7MB_REV2.runs/impl_Rev2/CHFPGA_MGK7MB_REV2.bit')

    # Configure the various loggers to provide adequate levels of details
    log_levels = {'info': logging.INFO, 'debug': logging.DEBUG}

    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]) # description is the first line of the docstring
    parser.add_argument('-t', '--log_target', action='store', type=str, default='syslog', help="Logging target ('stream', 'syslog' or a filename)")
    parser.add_argument('-l', '--log_level', action='store', type=str, choices=log_levels, default='debug', help='Logging level')
    parser.add_argument('-b', '--iceboards', action='store', nargs='+', type=str, help="Space-separated list of the iceboard hostnames (e.g. 10.10.10.7 or iceboard0007.local if the mDNS system is operational")
    parser.add_argument('-s', '--subarray', action='store', nargs='+', type=int, help='Space-separated list of subarrays to include')
    parser.add_argument('-f', '--bitfile', action='store', type=str, default= default_bitfile,  help='Filename of the bitfile used to to program the FPGAs')
    parser.add_argument('-i', '--if_ip', action='store', type=str, default=None, help='IP address of adapter through which the connection to the FPGA will be established. This is used solely for direct UDP communications with the FPGA.')
    parser.add_argument('--force', action='store', type=int, default=0, help='Force FPGA programming even if the firmware is already programmed.')
    args = parser.parse_args()

    __main__._host_interface_ip_addr = args.if_ip


    # -------------------------------
    # Set-up logging
    # -------------------------------

    logger = logging.getLogger('')
    logger.handlers = []  # Clear all existing handlers

    # Make sure SQLAlchemy does not log too much
    sql_logger = logging.getLogger('sqlalchemy.engine.base.Engine')
    sql_logger.setLevel(logging.INFO)

    if args.log_target == 'stream':
        log_handler = logging.StreamHandler()
    elif args.log_target == 'syslog':
        log_handler = logging.handlers.SysLogHandler()
    else:
        log_handler = logging.FileHandler(args.log_target)

    # Set-up log for this test run
    logger.setLevel(log_levels[args.log_level])
    logger.addHandler(log_handler)


    # Associate the bitstream with the target Handler
    fpga_bitstream = FpgaBitstream(args.bitfile)
    # chFPGA_controller.register_fpga_bitstream(fpga_bitstream)


    # -------------------------------
    # Create IceBoard
    # -------------------------------

    # # Create the IceBoard instance
    # # ib = IceBoard(hostname=args.iceboards[0], handler_name=chFPGA_controller.get_handler_name())
    # ib = IceBoard(hostname=args.iceboards[0])
    # ib.handler.register_fpga_bitstream(fpga_bitstream)

    # # Add it to the hardware map
    # hwm = hardware_map.HardwareMap()
    # hwm.add(ib)
    # hwm.commit()

    yaml_hwm = """
        !HardwareMap
            - !IceCrate
                serial: "003"
                slots:
                    16:  !IceBoardPlus {{hostname: {0} }}
        """.format(args.iceboards[0])

    # yaml_hwm = """
    #     !IceCrateHandler
    #         serial: "003"
    #         slot:
    #             &s1 3:  !IceBoardHandler {{hostname: {0}, slot: *s1}}
    #             &s2 2:  !IceBoardHandler {{slot: *s2}}
    #     """.format(args.iceboards[0])

    # yaml_hwm = """
    #     &A x: [*A]
    #     """

    # hwm = load_yaml_hardware_map(yaml_hwm)


    # -------------------------------
    # Create a hardware map consisting of a bunch of iceboards
    # -------------------------------
    hwm = HardwareMap()  # Create empty hardware map
    for hostname in args.iceboards:
        hwm.add(IceBoardPlus(hostname=hostname))
    hwm.flush()

    # -------------------------------
    # Check if specified iceboards are on-line before going any further
    # -------------------------------
    # from pychfpga.core.icecore import TuberObject
    for ib in hwm.query(IceBoardPlus):
        if not ib.ping():
            raise RuntimeError("%r could not be found at '%s'"
                               % (ib, ib.tuber_uri))
    c=[ib for ib in hwm.query(IceBoardPlus) if ib.ping()]

    # for ib in  hwm.query(HWMIceBoard):
    #     if ib.hostname:
    #         ib._initialize_backplane()

    ib = hwm.query(IceBoardPlus)
    # ic = hwm.query(IceCrate).one()
    ib1 = ib[0]
    # ib2 = ib[1]

    # ic = load_yaml_hardware_map(yaml_hwm)

    # ib.set_handler(IceBoardPlusHandler, fpga_bitstream)
    ib.set_handler(chFPGA_controller, fpga_bitstream)


    # Configure the FPGA with the bitstream associated with the handler
    ib.set_fpga_bitstream(force=args.force)
    # ib.open()
    # test_filename = 'results/scaler_test'
    # # Get the backplane test engine and execute the tests
    # te = ScalerTests(context={
    #     "Date": datetime.datetime.now(),
    #     "Bitstream filename": args.bitfile,
    #     "Bitstream CRC32": '0x%08X' % ib.get_fpga_bitstream_crc(),
    #     "Master Iceboard hostname": args.iceboards[0],
    #     "Iceboard handler name": type(ib.handler).__handler_name__,
    #     })
    # try:
    #     te.run(ib)
    # except Exception:
    #     raise
    # finally:
    #     te.write_xml(test_filename + '.xml')
    #     # te.write_html(test_filename + '.html')
    #     print '\n'.join(te.synopsis_as_strings())
# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
