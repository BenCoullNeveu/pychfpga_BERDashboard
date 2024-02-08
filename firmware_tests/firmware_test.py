import logging
import numpy as np
from test_setup import board_conn, setup_funcgen, TEST_CONFIG
from utils import plot_comp_data
import pytest
import socket
import psutil
from net_tools import ping_sources_async
from functools import wraps


def compare_plot_data(test_unit):
    """
    A wrapper for unit tests that plots data (if requested) and compares all read rows to reference data using
    np.isclose(). Unit tests must return data and ref_data which are np.ndarray type.
    """
    @wraps(test_unit)
    def wrapper(*args, **kwargs):
        data, ref_data = test_unit(*args, **kwargs)

        logger = TestFW.get_logger()

        if TEST_CONFIG['comp_plots']:
            logger.debug("Generating plots")
            plot_comp_data(test_unit.__name__, ref_data, data, title=test_unit.__name__)

        for i, data_row in enumerate(data):
            np.testing.assert_allclose(
                data_row,
                ref_data,
                err_msg=f"Data row with index {i} does not match the reference data",
            )
    return wrapper


class TestFW:
    """
    Collection of tests for an ICE/CRS board firmware. Most tests utilize the board_conn fixture, that reads
    connection parameters specified in config.yaml and connects to the boards. Some tests also use setup_funcgen
    fixture which allows controlling function generator within tests. The @compare_plot_data decorator is used
    to compare the data read from the board and reference data. For this to work, test units must return data and
    ref_data numpy arrays.
    """
    # All parameters are set by fixtures
    board = None
    FG_NS = None
    FG_DTYPE = None
    FG_LSHIFT = None

    @classmethod
    def get_logger(cls):
        logger = logging.getLogger(cls.__class__.__name__)
        logger.setLevel(TEST_CONFIG['logleveltest'])
        return logger

    def test_udp_buffers_size(self):
        logger = self.get_logger()
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
        logger = self.get_logger()
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
        logger = self.get_logger()
        logger.debug("Starting data capture for one period")
        self.board.start_data_capture(period=1)
        receiver = self.board.get_data_receiver()
        logger.debug("Reading raw frames")
        _, _, count = receiver.read_raw_frames()
        logger.info(f"Expected {len(count)} packages, received {len([p for p in count if p])}.")
        assert all(count), "Missing packages from ICE board. Check connection and system configuration."

    def _set_capture_funcgen(self, source: str, period: float = 1, **func_kwargs):
        """
        Set funcgen to specified data output and capture outcoming data within specified period.
        """
        logger = self.get_logger()
        logger.debug("Starting data capture from ADC")
        self.board.start_data_capture(period=period, source='adc')
        logger.debug(f"Setting data source to {source.upper()}")
        self.board.set_channelizer(data_source=source, **func_kwargs)
        logger.debug("Initializing data receiver")
        receiver = self.board.get_data_receiver()
        timestamp, data, count = receiver.read_raw_frames()
        return data

    @staticmethod
    def _compare_data(data: np.ndarray, ref_data: np.ndarray):
        pass

    @compare_plot_data
    def test_funcgen_ramp(self, board_conn, setup_funcgen):
        ref_data = np.arange(self.FG_NS, dtype=self.FG_DTYPE).view('i1')
        data = self._set_capture_funcgen('ramp')
        return data, ref_data

    @compare_plot_data
    def test_funcgen_sin(self, board_conn, setup_funcgen):
        sin_freq = 1
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * sin_freq) * 127).astype("i1")
        data = self._set_capture_funcgen('sin', freq=sin_freq)
        return data, ref_data

    @compare_plot_data
    def test_funcgen_arb(self, board_conn, setup_funcgen):
        freq_sin = 1
        freq_cos = 2
        t = np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS
        ref_data = (np.sin(t * freq_sin) * 127 / 2 + np.cos(t * freq_cos) * 127 / 2).astype("i1")
        data = self._set_capture_funcgen('arb', data=ref_data)
        return data, ref_data

    @compare_plot_data
    def test_funcgen_a(self, board_conn, setup_funcgen):
        a = 13 << self.FG_LSHIFT
        ref_data = np.full(self.FG_NS, a, self.FG_DTYPE).view('u1')
        data = self._set_capture_funcgen('a', a=a)
        return data, ref_data

    @compare_plot_data
    def test_funcgen_ab(self, board_conn, setup_funcgen):
        a = 13 << self.FG_LSHIFT
        b = 42 << self.FG_LSHIFT
        ref_data = np.tile(np.array((a, b), self.FG_DTYPE), self.FG_NS // 2).view('u1')
        data = self._set_capture_funcgen('ab', period=0.01, a=a, b=b)
        return data, ref_data

    @compare_plot_data
    def test_funcgen_real_ramp(self, board_conn, setup_funcgen):
        ref_data = (np.arange(self.FG_NS // 2) << 8).astype('>u2').view("i1")
        data = self._set_capture_funcgen('real_ramp')
        return data, ref_data

    @compare_plot_data
    def test_bypass_fft_and_scaler(self, board_conn, setup_funcgen):
        sin_freq = 100
        chan_params = dict(
            data_source='sin',
            freq=sin_freq,
            fft_bypass=1,
            scaler_bypass=1,
            scaler_eight_bit=1,
            prober_user_flags=0,
        )
        self.board.set_channelizer(**chan_params)
        self.board.start_data_capture(period=1, source='scaler')
        receiver = self.board.get_data_receiver()
        timestamp, data, count = receiver.read_raw_frames()

        sin_freq = 100
        ref_data = (np.sin(np.arange(self.FG_NS) * 2 * np.pi / self.FG_NS * sin_freq) * 127).astype("i1")
        return data, ref_data



