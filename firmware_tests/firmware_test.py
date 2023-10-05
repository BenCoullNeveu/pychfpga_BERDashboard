import logging
import numpy as np
import psutil
import netifaces
from test_setup import TEST_CONFIG, ice_conn
from test_setup import ice_conn, setup_funcgen, TEST_CONFIG


class TestFW:
    """
    Collection of tests for an ICE/CRS board firmware.
    """
    # All parameters are set by fixtures
    board = None
    FG_NS = None
    FG_DTYPE = None
    FG_LSHIFT = None

    def _get_logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(TEST_CONFIG['logleveltest'])
        return logger

    def test_udp_buffers_size(self):
        logger = self._get_logger()
        buff_config = list()
        logger.debug("Reading system files in /proc/sys/net")
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
        logger.debug("Starting data capture for one period")
        self.board.start_data_capture(period=1)
        receiver = self.board.get_data_receiver()
        logger.debug("Reading raw frames")
        _, _, count = receiver.read_raw_frames()
        logger.info(f"Expected {len(count)} packages, received {len([p for p in count if p])}.")
        assert all(count), "Missing packages from ICE board. Check connection and system configuration."

    def test_funcgen_control(self, ice_conn):
        pass
    def _test_funcgen_output(self, ref_data: np.ndarray, function: str, period: float = 1, **func_kwargs):
        logger = self._get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(period=period, source='adc')
        logger.debug(f"Setting data source to funcgen and funcgen output to {function.upper()}")
        self.board.set_channelizer(function=function, data_source='funcgen', **func_kwargs)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        timestamp, data, count = receiver.read_raw_frames()
        for i, data_row in enumerate(data):
            assert np.all(np.isclose(data_row, ref_data)), \
                f"Data row with index {i} does not match the reference data"

    def test_funcgen_ramp(self, ice_conn, setup_funcgen):
        ref_data = np.arange(self.FG_NS, dtype=self.FG_DTYPE).view('i1')
        self._test_funcgen_output(ref_data, 'ramp')

    def test_funcgen_sin(self, ice_conn, setup_funcgen):
        freq = 1
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * freq) * 127).astype("i1")
        self._test_funcgen_output(ref_data, 'sin', freq=freq)

    def test_funcgen_arb(self, ice_conn, setup_funcgen):
        freq_sin = 1
        freq_cos = 2
        t = np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS
        ref_data = (np.sin(t * freq_sin) * 127 / 2 + np.cos(t * freq_cos) * 127 / 2).astype("i1")
        self._test_funcgen_output(ref_data, 'arb', data=ref_data)

    def test_funcgen_ab(self, ice_conn, setup_funcgen):
        logger = self._get_logger()
        a = 13 << self.FG_LSHIFT
        b = 42 << self.FG_LSHIFT
        ref_data_a = np.full(self.FG_NS, a, self.FG_DTYPE).view('u1')
        ref_data_b = np.full(self.FG_NS, b, self.FG_DTYPE).view('u1')
        ref_data_ab = np.tile(np.array((a, b), self.FG_DTYPE), self.FG_NS // 2).view('u1')
        logger.debug("Testing function 'a': all bytes equal some constant A")
        self._test_funcgen_output(ref_data_a, 'a', a=a)
        logger.debug("Testing function 'b': all bytes equal some constant B")
        self._test_funcgen_output(ref_data_b, 'b', b=b)
        logger.debug("Testing function 'ab': bytes alternate between constants A and B")
        self._test_funcgen_output(ref_data_ab, 'ab', period=0.01, a=a, b=b)

    def test_funcgen_real_ramp(self, ice_conn, setup_funcgen):
        ref_data = (np.arange(self.FG_NS // 2) << 8).astype('>u2').view("i1")
        self._test_funcgen_output(ref_data, 'real_ramp')
