from pychfpga.fpga_array import FPGAArray
import logging
import pytest
from wtl.config import load_yaml_config
from pathlib import Path

CONN_CONFIG = load_yaml_config("connection_config")
TEST_CONFIG = load_yaml_config("test_config")

RESULT_DIR = Path("test_results")
PLOT_DIR = RESULT_DIR / "comp_plots"

if TEST_CONFIG['comp_plots']:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope=TEST_CONFIG['conn_scope'])
def ice_conn(request):
    conn_logger_name = FPGAArray.__name__.rsplit('.', 1)[0] if '.' in __name__ else ''
    logging.getLogger(conn_logger_name).setLevel(TEST_CONFIG['loglevelconn'])

    logger = logging.getLogger(request.cls.__name__)
    logger.info("Connecting to the ICE board")
    ca = FPGAArray(**CONN_CONFIG)
    request.cls.board = ca.ib[0]


@pytest.fixture(scope=TEST_CONFIG['conn_scope'])
def setup_funcgen(request, ice_conn):
    logger = logging.getLogger(request.cls.__name__)
    request.cls.FG_NS = request.cls.board.ADC_SAMPLES_PER_FRAME
    # Should throw an exception when ADC_BYTES_PER_FRAME not 1 or 2 but the connection does it itself
    if request.cls.board.ADC_BYTES_PER_SAMPLE == 1:
        request.cls.FG_DTYPE = 'u1'
        request.cls.FG_LSHIFT = 8 - request.cls.board.ADC_BITS_PER_SAMPLE
    else:
        request.cls.FG_DTYPE = '>u2'
        request.cls.FG_LSHIFT = 16 - request.cls.board.ADC_BITS_PER_SAMPLE
    logger.debug(f"Setting fucgen output dtype to {request.cls.FG_DTYPE}")
