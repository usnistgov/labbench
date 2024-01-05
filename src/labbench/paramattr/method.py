from . import _types
from . import _bases
import typing as _typing
from ._bases import Method


class any(_bases.Method, _types.Any):
    pass


class bool(_bases.Method, _types.Bool):
    pass


class float(_bases.Method, _types.Float):
    pass


class int(_bases.Method, _types.Int):
    pass


class complex(_bases.Method, _types.Complex):
    pass


class str(_bases.Method[str], _types.Unicode):
    pass


class bytes(_bases.Method, _types.Bytes):
    pass


class list(_bases.Method, _types.List):
    pass


class tuple(_bases.Method, _types.Tuple):
    pass


class dict(_bases.Method, _types.Dict):
    pass


class Path(_bases.Method, _types.Path):
    pass


class NetworkAddress(_bases.Method, _types.NetworkAddress):
    pass
