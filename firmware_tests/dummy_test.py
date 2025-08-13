from random import randint
from time import sleep
from wtl.pytest_xreport import xr

import pytest
import numpy as np
import matplotlib.pyplot as plt


def test_dummy(xr):

    plt.figure(1)

    ideal_ramp = (np.arange(2048) - 128).astype(np.int8)

    print('allo')
    plt.plot(ideal_ramp)
    xr.insert_plot('Ideal ramp')