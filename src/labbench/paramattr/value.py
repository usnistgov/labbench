from . import _types
from ._bases import Value


class any(Value, _types.Any):
    """defines a value attribute that validates any python object"""


class bool(Value, _types.Bool):
    """defines a value attribute that casts to python builtin bool"""


class float(Value, _types.Float):
    """defines a value attribute that casts to python builtin float"""


class int(Value, _types.Int):
    """defines a value attribute that casts to python builtin int"""


class complex(Value, _types.Complex):
    """defines a value attribute that casts to python complex"""


class str(Value, _types.Unicode):
    """defines a value attribute that casts to python builtin str"""


class bytes(Value, _types.Bytes):
    """defines a value attribute that casts to python builtin bytes"""


class list(Value, _types.List):
    """defines a value attribute that casts to python builtin list"""


class tuple(Value, _types.Tuple):
    """defines a value attribute that casts to python builtin tuple"""


class dict(Value, _types.Dict):
    """defines a value attribute that casts to python builtin dict"""


class Path(Value, _types.Path):
    """defines a value attribute that casts to python pathlib.Path"""


class NetworkAddress(Value, _types.NetworkAddress):
    """defines a value attribute that casts to a network address"""


# used to set up hints for static type checking
_ALL_TYPES = (
    Value,
    any,
    bool,
    float,
    int,
    complex,
    str,
    bytes,
    list,
    tuple,
    dict,
    Path,
    NetworkAddress,
)
