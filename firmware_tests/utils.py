import matplotlib.pyplot as plt
from cycler import cycler
import numpy as np
from test_setup import PLOT_DIR, TEST_CONFIG
from functools import wraps
from textwrap import wrap

styles = cycler(color=['tab:blue', 'orange', 'forestgreen'], marker=['.', ' ', ' '])
plt.rc('axes', prop_cycle=styles)

def plot(datasets, labels=[], y_range=None, data_range=None, split_complex=False, title="test", xlabel=None, ylabel=None, folder=None):
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
    

    fig, axs = plt.subplots(2 if split_complex else 1)
    for i in range(2*len(datasets)):
        im = i >= len(datasets)
        ax = axs[int(im)] if split_complex else axs
        if im and not split_complex:
            break
        if y_range is not None:
            ax.set_ylim(y_range)
        if split_complex and not im:
            ax.plot(datasets[i][data_range[0]:data_range[1]:2], label=labels[i] + "(Re)")
        elif split_complex and im:
            ax.plot(datasets[i % len(datasets)][data_range[0]+1:data_range[1]:2], label=labels[i % len(datasets)] + "(Im)")
        else:
            ax.plot(datasets[i][data_range[0]:data_range[1]], label=labels[i])
        
        #axs.set_title(labels[i])
        ax.legend()
        
    fig.supxlabel("Bin" if xlabel is None else xlabel)
    fig.supylabel("Output" if ylabel is None else ylabel)
    fig.suptitle("\n".join(wrap(title, 60)))
    dir = PLOT_DIR if folder is None else PLOT_DIR / folder
    dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(dir/title)


def gen_data(func, samples=2048, **kwargs):
    if func == 'a':
        return np.ones(samples) * kwargs.get('a', 1)
    elif func == 'ab':
        period = kwargs.get('period', 1)
        res = np.tile(np.concatenate((np.repeat(kwargs.get('a', 0), period), np.repeat(kwargs.get('b', 1), period))), samples//(2*period))
        return np.append(res, np.repeat(kwargs.get('a', 0), samples - res.size))
    elif func == 'ramp':
        min = kwargs.get('min', 0)
        max = kwargs.get('max', samples)
        res = np.repeat(np.arange(min, max + 1), samples // (max - min + 1))
        return np.append(res, max * np.ones(samples - res.size))
    elif func == 'periodic_ramp':
        #TODO: fix to ensure bounds are always exactly respected
        min = kwargs.get('min', 0)
        max = kwargs.get('max', samples)
        res = np.tile(np.arange(min, max + 1), samples // (max - min + 1))
        return np.append(res, np.arange(min, min + (samples - res.size)))
    elif func == 'complex_ramp':
        min = kwargs.get('min', 0)
        max = kwargs.get('max', np.sqrt(samples))
        half_samples = samples // 2
        reals = np.repeat(np.arange(min, max + 1), half_samples // (max - min + 1))
        reals = np.append(reals, max * np.ones(half_samples - reals.size))
        cmplx = np.tile(np.arange(min, max + 1), half_samples // (max - min + 1))
        cmplx = np.append(cmplx, np.arange(min, min + half_samples - cmplx.size))
        return np.stack((reals, cmplx), axis=1).reshape(-1) #interleave the real and complex arrays
    elif func == 'arb':
        return kwargs.get('data', np.zeros(2048))
    


def compare_plot_data(test_unit=None, *, split_plots=False, approximate=False, atol=0.1):
    def _decorate(test_unit):
        @wraps(test_unit)
        def wrapper(*args, **kwargs):
            res = test_unit(*args, **kwargs)
            if res is None:
                return
            data = res[0][0]
            ref_data = res[0][1]
            title = test_unit.__name__[5:] if len(res) < 2 else res[1]
            title = title.replace('_', ' ')
            title = title.capitalize()
            folder = test_unit.__name__[5:] if len(res) >= 2 else None 
            plot_kwargs = {} if len(res) < 3 else res[2]
            if len(data.shape) > 1:
                for i in range(data.shape[0]):
                    if not np.equal(data[0], data[i]).all():
                        plot(datasets=[data[0], data[i]], labels=["First channel", f"{i}th channel"], title=f"Different channeliser outputs for {title}")
                    np.testing.assert_equal(data[0], data[i])
                actual_data = data[0]
            else:
                actual_data = data
            if TEST_CONFIG['always_plot'] or (TEST_CONFIG['plot_on_failure'] and not np.equal(data, ref_data).all()):
                plot(datasets=[*res[0][1:], actual_data], labels=['Reference', 'Returned'], title=title, folder=folder, **plot_kwargs)
            if not TEST_CONFIG.get('only_plot', False):
                if approximate:
                    np.testing.assert_allclose(actual_data, ref_data, atol=atol)
                else:
                    np.testing.assert_equal(actual_data, ref_data)
        return wrapper
    if test_unit:
        return _decorate(test_unit)
    return _decorate

def unsplit_imag(array):
    return (array[::2] + array[1::2]*1j).astype(np.complex64)

def split_imag(array):
    return np.stack((np.real(array), np.imag(array)), axis=1).reshape(-1).astype(np.int64)