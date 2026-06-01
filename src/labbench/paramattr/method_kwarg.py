from . import _types
from ._bases import MethodKwArg


class any(MethodKwArg, _types.Any):
    pass


class bool(MethodKwArg, _types.Bool):
    pass


class float(MethodKwArg, _types.Float):
    pass


class int(MethodKwArg, _types.Int):
    pass


class complex(MethodKwArg, _types.Complex):
    pass


class str(MethodKwArg, _types.Unicode):
    pass


class bytes(MethodKwArg, _types.Bytes):
    pass


class list(MethodKwArg, _types.List):
    pass


class tuple(MethodKwArg, _types.Tuple):
    pass


class dict(MethodKwArg, _types.Dict):
    pass


class Path(MethodKwArg, _types.Path):
    pass


class NetworkAddress(MethodKwArg, _types.NetworkAddress):
    pass
