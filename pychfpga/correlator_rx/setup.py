from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
import numpy as np

ext_modules=[
    Extension("iceboard_receiver",
              ["iceboard_receiver.pyx", "ciceboard_receiver.c" ],
              libraries=["hdf5", "hdf5_hl", 'm', 'pthread'],
              library_dirs = ['/home/sean/work/anaconda3/lib/'],
              include_dirs = [np.get_include(),'/home/sean/work/anaconda3/include/'],
              extra_compile_args = ['-std=c99']) # Unix-like specific
]

setup(
  name = "iceboard_receiver",
  cmdclass = {"build_ext": build_ext},
  ext_modules = ext_modules
)
