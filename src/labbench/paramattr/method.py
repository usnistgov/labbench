from . import _bases, _types
from ._bases import Method


class any(Method, _types.Any):
    pass


class bool(Method[bool], _types.Bool):
    pass


class float(Method[float], _types.Float):
    pass


class int(Method[int], _types.Int):
    pass


class complex(Method[complex], _types.Complex):
    pass


class str(Method[str], _types.Unicode):
    pass


class bytes(Method, _types.Bytes):
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
