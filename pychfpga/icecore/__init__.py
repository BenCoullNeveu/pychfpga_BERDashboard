"""Top-level packaging for 'icecore'.

Code using icecore should use top-level imports. For example:

    >>> from icecore import HardwareMap  # good!

...rather than relative imports:

    >>> from pydfmux.hardware_map import HardwareMap  # bad!

This allows __init__ to structure the package's API separately from Python
code, which means we can evolve it more freely.
"""

# Source code lives in python/ -- and we don't want to expose that fact to
# Python code using us. Make code in python available as if it was here.
__path__= [__path__[0] + '/python']

from hardware_map import (
    Base, HWMQueryException,
    HWMQuery, HWMResource, TuberHWMResource,
    macro, algorithm, HardwareMap,
    Boolean,
    Session,
    set_session_class,
)

from iceboard import (
    IceCrate,
    IceBoard,
    FMCMezzanine,
)

from session import (
    YAMLLoader,
    HWMConstructor,
    HWMCSVConstructor,
    IncludedYAMLValue,
    load_session,
    set_yaml_loader_class,
)

from tuber import (
    TuberError,
    TuberRemoteError,
    TuberCategory,
    TuberObject,
)

# vim: sts=4 ts=4 sw=4 tw=78 smarttab expandtab
