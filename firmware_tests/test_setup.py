from pychfpga.fpga_array import FPGAArray
import logging
import pytest
from wtl.config import load_yaml_config

CONN_CONFIG = load_yaml_config("connection_config")
TEST_CONFIG = load_yaml_config("test_config")


@pytest.fixture(scope=TEST_CONFIG['conn_scope'])
def ice_conn(request):
    conn_logger_name = FPGAArray.__name__.rsplit('.', 1)[0] if '.' in __name__ else ''
    logging.getLogger(conn_logger_name).setLevel(TEST_CONFIG['loglevelconn'])

    logger = logging.getLogger(request.cls.__name__)
    logger.info("Connecting to the ICE board")
    ca = FPGAArray(**CONN_CONFIG)
    request.cls.board = ca.ib[0]
