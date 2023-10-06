import logging
import numpy as np
import psutil
import netifaces
from test_setup import board_conn, setup_funcgen, TEST_CONFIG
from utils import plot_comp_data
import pytest
import socket
import psutil
from net_tools import ping_sources_async


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

    @pytest.mark.asyncio
    async def test_mtu_size(self, board_conn):
        logger = self._get_logger()
        logger.debug("Getting the board's address")
        port_map = dict(
            port=self.board.get_data_socket().getsockname()[1],
            sources=[(self.board.hostname, 80)]
        )
        logger.debug(f"The board located at {port_map['sources'][0][0]}")
        logger.debug("Pinging the board to determine interface used")
        src_if_addrs = await ping_sources_async([port_map])
        if_ip = list(src_if_addrs.values())[0]
        logger.debug(f"Interface address: {if_ip[0]}:{if_ip[1]}")
        if_addrs = psutil.net_if_addrs()
        if_name = None
        for key in if_addrs.keys():
            for snic_addr in if_addrs[key]:
                if snic_addr[0] == socket.AF_INET:
                    if snic_addr[1] == if_ip[0]:
                        if_name = key
        logger.debug(f"Interface name: {if_name}")
        if_stats = psutil.net_if_stats()
        mtu = if_stats[if_name].mtu
        logger.debug(f"Interface MTU size: {mtu}")

        if mtu < 9000:
            raise RuntimeError(f"Default network interface has MTU={mtu} (<9000). Please set MTU to 9000 to "
                               f"prevent loss of packages.")

    def test_packets_number(self, board_conn):
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

    def _test_funcgen_output(self, ref_data: np.ndarray, source: str, period: float = 1, **func_kwargs):
        logger = self._get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(period=period, source='adc')
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source, **func_kwargs)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        timestamp, data, count = receiver.read_raw_frames()
        if TEST_CONFIG['comp_plots']:
            logger.debug("Generating plots")
            plot_comp_data(f"funcgen_{source}", ref_data, data,
                           title=f"Testing {source} funcgen ouput")
        for i, data_row in enumerate(data):
            assert np.all(np.isclose(data_row, ref_data)), \
                f"Data row with index {i} does not match the reference data"

    def test_funcgen_ramp(self, board_conn, setup_funcgen):
        ref_data = np.arange(self.FG_NS, dtype=self.FG_DTYPE).view('i1')
        self._test_funcgen_output(ref_data, 'ramp')

    def test_funcgen_sin(self, board_conn, setup_funcgen):
        freq = 1
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * freq) * 127).astype("i1")
        self._test_funcgen_output(ref_data, 'sin', freq=freq)

    def test_funcgen_arb(self, board_conn, setup_funcgen):
        freq_sin = 1
        freq_cos = 2
        t = np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS
        ref_data = (np.sin(t * freq_sin) * 127 / 2 + np.cos(t * freq_cos) * 127 / 2).astype("i1")
        self._test_funcgen_output(ref_data, 'arb', data=ref_data)

    def test_funcgen_ab(self, board_conn, setup_funcgen):
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

    def test_funcgen_real_ramp(self, board_conn, setup_funcgen):
        ref_data = (np.arange(self.FG_NS // 2) << 8).astype('>u2').view("i1")
        self._test_funcgen_output(ref_data, 'real_ramp')
