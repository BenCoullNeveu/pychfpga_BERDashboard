"""Top-level packaging for 'icecore'.

Code using icecore should use top-level imports. For example:

    >>> from icecore import HardwareMap  # good!

...rather than relative imports:

    >>> from pydfmux.hardware_map import HardwareMap  # bad!

This allows __init__ to structure the package's API separately from Python
code, which means we can evolve it more freely.
"""

# ***JFC: How do we want to allow access to class IceBoard in module 'iceboard'
# Method 1) import icecore.iceboard;  x=icecore.iceboard.IceBoard # works if icecore.__init__ redefines __path__. This also gives access to *everything* in icecore/python
# Method 1) from icecore.iceboard import IceBoard; x = Iceboard # idem
# Method 2) import icecore; x=icecore.iceboard.IceBoard  # works if icecore.__init__ imports iceboard
# Method 2) from icecore import iceboard; x= iceboard.IceBoard # idem
# Method 3) from icecore import IceBoard; x = IceBoard  # works if icecore.__init__ imports IceBoard
#
# Note: 'from x import y' does not resolve circular module references. 'import y' does.

# Source code lives in python/ -- and we don't want to expose that fact to
# Python code using us. Make code in python available as if it was here.
# *** JFC: Allows Method 1
__path__= [__path__[0] + '/python']


# Provide access to main modules
# *** JFC: Allows Method 2
# from .python import (
#     hardware_map,
#     iceboard,
#     fpga_bitstream,
#     tuber,
#     fmc_mezzanine
#     )

# *** JFC: Allows Method 3
# *** JFC: Need to add .python if Method 1 is not allowed
from hardware_map import (
    Base,
    HWMQueryException,
    HWMQuery,
    HWMResource,
    macro, algorithm,
    HardwareMap,
    Boolean,
    Session,
    set_session_class,
)

from tuber import (
    TuberError,
    TuberRemoteError,
    TuberCategory,
    TuberObject,
)

from handler import (
    HandlerObject,
    Handler
)

from iceboard import (
    IceBoard,
    IceBoardHandler
)


from icecrate import (
    IceCrate,
    IceCrateHandler
)

from fmc_mezzanine import (
    FMCMezzanine,
    FMCMezzanineHandler
)

from session import (
    YAMLLoader,
    HWMConstructor,
    HWMCSVConstructor,
    IncludedYAMLValue,
    load_session,
    set_yaml_loader_class,
)


# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
