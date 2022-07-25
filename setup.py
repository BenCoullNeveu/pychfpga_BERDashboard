from setuptools import setup, find_packages
from os import path

import versioneer


here = path.abspath(path.dirname(__file__))

# Load the requirements for the base configuration and the extras.
# The environment marks are removed.
reqs = {}
for req_name in ('','qc','docs'):
  req_filename = f"{req_name}{'_' if req_name else ''}requirements.txt"
  with open(path.join(here, req_filename)) as f:
      reqs[req_name] = [line.split(';')[0].rstrip() for line in f]

# Load the long description from the README file
with open("README", "r", encoding='utf-8') as f:
    long_description = f.read()

# Install the python packages.
setup(
      name="pychfpga",
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      # cmdclass = {'build_ext': build_ext},
      description=('Control and monitors a array of ICEBoard '
                   'running the chfpga (X-Engine + corner-turn) '
                   'or sifpga (F-Engine + 16-channel X-Engine) FPGA firmware'),
      long_description=long_description,
      long_description_content_type="text/x-rst",
      url='https://bitbucket.org/winterlandcosmology/pychfpga',
      author='McGill University',
      author_email='jfcliche@jfcliche.com',
      packages=find_packages(include=['pychfpga','pychfpga.*']), # include only pychfpga and its sub-packages, nothing from qc or test folders.
      classifiers=[
              "Programming Language :: Python :: 3",
              "Operating System :: OS Independent",
              "Topic :: Scientific/Engineering :: Astronomy",
              "Intended Audience :: Science/Research",
          ],
      python_requires='>=3.7',
      install_requires=reqs[''],
      extras_require={
        'qc': reqs['qc'],
        'docs': reqs['docs']
        },

      include_package_data=True,
      entry_points={
          "console_scripts": [
              "fpga_master=pychfpga.fpga_master:main",
              "chime_gps=pychfpga.gps:main",
              "chime_raw_acq=pychfpga.raw_acq:main",
              "chime_rx_ps=pychfpga.ps:main",
          ]
      },
     )
