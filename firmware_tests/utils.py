import matplotlib.pyplot as plt
import numpy as np
from test_setup import PLOT_DIR
import pathlib


'''def plot_comp_data(fname: str, ref_data: np.ndarray, data: np.ndarray, x: np.ndarray = None, title: str = None, crop_data_ind: int = -1):
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
    plt.savefig(PLOT_DIR/fname)'''

def plot(datasets, labels=[], y_range=None, data_range=None, split_complex=False, title="test", folder=None):
    if labels is None:
        labels = []

    l = len(labels)
    for i in range(len(datasets) - l):
        labels.append(f"Datset {i}")
    
    # Check all datasets are the same length
    lengths = [d.size for d in datasets]
    if len(set(lengths)) != 1 and data_range is None:
        raise ValueError("All datasets must be the same length if data_range is not specified")

    # Infer data range if not given
    if data_range is None:
        data_range = (0, lengths[0])
    elif np.isscalar(data_range):
        data_range = (0, data_range)
   
    fig, axs = plt.subplots(len(datasets), figsize=(8, 6))
    for i in range(len(datasets)):
        if y_range is not None:
            axs[i].set_ylim(y_range)
        if split_complex:
            axs[i].plot(datasets[i][data_range[0]+1:data_range[1]:2], color="blue")
            axs[i].plot(datasets[i][data_range[0]:data_range[1]:2], color="orange")
        else:
            axs[i].plot(datasets[i][data_range[0]:data_range[1]])
        axs[i].set_title(labels[i])
    fig.suptitle(title)
    fig.tight_layout()
    dir = PLOT_DIR if folder is None else PLOT_DIR / folder
    dir.mkdir(exist_ok=True)
    plt.savefig(dir/title)


def gen_data(func, samples=2048, **kwargs):
    if func == 'const':
        return np.ones(samples) * kwargs.get('a', 1)
    elif func == 'alternate':
        return np.tile((kwargs.get('a', 0), kwargs.get('b', 1)), samples//2)
    elif func == 'ramp':
        min = kwargs.get('min', 0)
        max = kwargs.get('max', samples)
        return np.arange(samples) // int(samples / (max - min)) + min
    elif func == 'periodic_ramp':
        min = kwargs.get('min', 0)
        max = kwargs.get('max', samples)
        res = np.tile(np.arange(min, max), samples // (max - min))
        return np.append(res, np.arange(min, min + (samples - res.size)))
    elif func == 'complex_ramp':
        min = kwargs.get('min', 0)
        max = kwargs.get('max', np.sqrt(samples))
        half_samples = samples // 2
        reals = np.arange(half_samples) // int(half_samples / (max - min)) + min
        cmplx = np.tile(np.arange(min, max), half_samples // (max - min))
        cmplx = np.append(cmplx, np.arange(min, min + half_samples - cmplx.size))
        return np.stack((reals, cmplx), axis=1).reshape(-1) #interleave the real and complex arrays
    elif func == 'arb':
        return kwargs.get('data', np.zeros(2048))