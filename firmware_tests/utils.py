import matplotlib.pyplot as plt
import numpy as np
from test_setup import PLOT_DIR, TEST_CONFIG


def plot_comp_data(fname: str, ref_data: np.ndarray, data: np.ndarray, x: np.ndarray = None, title: str = None, crop_data_ind: int = -1):
    data = np.atleast_2d(data)
    x = x or np.arange(ref_data.size)
    if fname == 'test_funcgen_ab':
        crop_data_ind = 50
    elif fname == 'test_funcgen_real_ramp':
        crop_data_ind = 300
    bbox_props = dict(boxstyle='round', facecolor='white', alpha=0.9)
    caption_props = dict(horizontalalignment='left', verticalalignment='center')

    fig, axs = plt.subplots(2, 1, figsize=(8, 6))
    axs[0].plot(x[:crop_data_ind], ref_data[:crop_data_ind], lw=2)
    axs[0].set_title('Reference')

    for i, data_row in enumerate(data):
        axs[1].plot(x[:crop_data_ind], data_row[:crop_data_ind], lw=2, ls='--', dashes=(5, i))
        break
    axs[1].set_title('Returned data')

    if crop_data_ind != -1:
        caption = f"CROPPED FROM LEN={len(ref_data)} TO LEN={crop_data_ind}"
        axs[0].text(0.02, 0.9, caption, bbox=bbox_props, **caption_props, transform=axs[0].transAxes)
        axs[1].text(0.02, 0.9, caption, bbox=bbox_props, **caption_props, transform=axs[1].transAxes)

    fig.suptitle(title)
    fig.tight_layout()
    plt.savefig(PLOT_DIR/fname)

def compare_plot_data(test_unit):
    """
    A wrapper for unit tests that plots data (if requested) and compares all read rows to reference data using
    np.isclose(). Unit tests must return data and ref_data which are np.ndarray type.
    """
    @wraps(test_unit)
    def wrapper(*args, **kwargs):
        data, ref_data = test_unit(*args, **kwargs)

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
