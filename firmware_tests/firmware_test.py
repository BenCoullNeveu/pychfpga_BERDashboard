import logging
from utils import check_udp_buffers_size, check_mtu_size
from test_setup import TEST_CONFIG, ice_conn


class TestFW:
    """
    Collection of tests for an ICE/CRS board firmware.
    """
    board = None

    def _get_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(TEST_CONFIG['logleveltest'])
        return logger

    def test_prerequisites(self):
        """
        Checks system parameters to ensure reliable connections to the motherboard.
        """
        logger = self._get_logger()
        logger.info("Checking UDP buffers size")
        check_udp_buffers_size()
        logger.info("Checking MTU size")
        check_mtu_size(logger)

    def test_packets_number(self, ice_conn):
        """
        Ensures that all packages sent by the motherboard are received.
        """
        logger = self._get_logger()
        logger.info("Starting data capture for one period")
        self.board.start_data_capture(period=1)
        receiver = self.board.get_data_receiver()
        logger.info("Reading raw frames")
        _, _, count = receiver.read_raw_frames()
        logger.info(f"Expected {len(count)} packages, received {len([p for p in count if p])}.")
        assert all(count), "Missing packages from ICE board. Check connection and system configuration."

    def test_funcgen_control(self, ice_conn):
        pass
