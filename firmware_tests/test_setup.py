from pychfpga.fpga_array import FPGAArray
import logging
import pytest
from wtl.config import load_yaml_config
from pathlib import Path
import os
import glob

CONN_CONFIG = load_yaml_config("connection_config")
TEST_CONFIG = load_yaml_config("test_config")

RESULT_DIR = Path("test_results")
PLOT_DIR = RESULT_DIR / "comp_plots"


if TEST_CONFIG['always_plot'] or TEST_CONFIG['plot_on_failure']:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope=TEST_CONFIG['conn_scope'])
def delete_plots(request):
    logger = logging.getLogger(request.cls.__name__)
    if not os.path.isdir(PLOT_DIR):
        logger.warning(f"{PLOT_DIR} does not exist")
        return
    if TEST_CONFIG['delete_plots_before_run']:
        logger.info('Deleting previous plots')
        for file in PLOT_DIR.rglob('*.png'):
            os.remove(file)
    for dirpath, dirnames, filenames in os.walk(PLOT_DIR, topdown=False):
        if not dirnames and not filenames:
            os.rmdir(dirpath)

@pytest.fixture(scope=TEST_CONFIG['conn_scope'])
def board_conn(request, delete_plots):
    conn_logger_name = FPGAArray.__name__.rsplit('.', 1)[0] if '.' in __name__ else ''
    logging.getLogger(conn_logger_name).setLevel(TEST_CONFIG['loglevelconn'])
    logger = logging.getLogger(request.cls.__name__)
    logger.info("Connecting to the ICE board")
    ca = FPGAArray(**CONN_CONFIG)
    request.cls.board = ca.ib[0]

@pytest.fixture(scope='function')
def setup_funcgen(request, board_conn):
    logger = logging.getLogger(request.cls.__name__)
    request.cls.FG_NS = request.cls.board.ADC_SAMPLES_PER_FRAME
    # Should throw an exception when ADC_BYTES_PER_FRAME not 1 or 2 but the connection does it itself
    if request.cls.board.ADC_BYTES_PER_SAMPLE == 1:
        request.cls.FG_DTYPE = 'u1'
        request.cls.FG_LSHIFT = 8 - request.cls.board.ADC_BITS_PER_SAMPLE
    else:
        request.cls.FG_DTYPE = '>u2'
        request.cls.FG_LSHIFT = 16 - request.cls.board.ADC_BITS_PER_SAMPLE
    logger.debug(f"Setting funcgen output dtype to {request.cls.FG_DTYPE}")

@pytest.fixture(scope='function')
def setup_scaler(request, board_conn):
    logger = logging.getLogger(request.cls.__name__)
    request.cls.FG_NS = request.cls.board.chan[0].FUNCGEN.NS
    request.cls.board.set_channelizer(
        fft_bypass=True, 
        scaler_bypass=False, 
        offset_binary_encoding=False, 
        scaler_eight_bit=False, 
        prober_user_flags=False, 
        scaler_rounding_mode=0, 
        symmetric_saturation=False)
    logger.debug("Setup channelizer for testing scaler")
