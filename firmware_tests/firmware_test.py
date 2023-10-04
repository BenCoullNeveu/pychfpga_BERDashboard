import logging
import psutil
import netifaces
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

    def test_udp_buffers_size(self):
        buff_config = list()
        with open("/proc/sys/net/core/rmem_max") as file:
            buff_config.append(int(file.readline()))
        with open("/proc/sys/net/core/rmem_default") as file:
            buff_config.append(int(file.readline()))
        with open("/proc/sys/net/ipv4/udp_mem") as file:
            for val in file.readline().split():
                buff_config.append(int(val))
        with open("/proc/sys/net/ipv4/udp_rmem_min") as file:
            buff_config.append(int(file.readline()))

        if any(val < 26214400 for val in buff_config):
            raise RuntimeError(
                "The UDP buffers' memory parameters (net.core.rmem_max, net.core.rmem_default, "
                "net.ipv4.udp_mem, net.ipv4.udp_rmem_min) are too low. Increase them to at least 26214400 "
                "bytes. \nYou can do it by running:\n"
                ">>> sudo sysctl -w net.core.rmem_max=26214400 net.core.rmem_default=26214400 "
                "net.ipv4.udp_mem='26214400 26214400 26214400' net.ipv4.udp_rmem_min=26214400"
            )

    def test_mtu_size(self):
        logger = self._get_logger()
        gws = netifaces.gateways()
        logger.debug("Getting the ip address of the default gateway.")
        try:
            def_interface = gws['default'][netifaces.AF_INET][1]
        except KeyError:
            raise RuntimeError("The default network interface cannot communicate with IPv4. Check your connection.")

        ifstats = psutil.net_if_stats()
        logger.debug("Getting the default gateway MTU size.")
        def_mtu = ifstats[def_interface].mtu
        if def_mtu < 9000:
            raise RuntimeError(f"Default network interface has MTU={def_mtu} (<9000). Please set MTU to 9000 to "
                               f"prevent loss of packages.")

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
