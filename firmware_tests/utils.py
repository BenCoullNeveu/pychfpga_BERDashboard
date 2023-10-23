import matplotlib.pyplot as plt
import numpy as np
from test_setup import PLOT_DIR


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
