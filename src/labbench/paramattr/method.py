from . import _bases, _types
from ._bases import Method, _InstanceMethod
from pathlib import Path as _Path
import typing as _typing


class any(Method[_typing.Any], _types.Any):
    pass


class bool(Method[bool], _types.Bool):
    pass


class float(Method[float], _types.Float):
    pass


class int(Method[int], _types.Int):
    pass


class complex(Method[complex], _types.Complex):
    pass


class str[**P](Method[str], _types.Unicode):
    pass


class bytes[**P](Method[bytes], _types.Bytes):
    pass


class list[**P](_bases.Method[list], _types.List):
    pass


class tuple[**P](_bases.Method[list], _types.Tuple):
    pass


class dict[**P](_bases.Method[dict], _types.Dict):
    pass


class Path[**P](_bases.Method[_Path], _types.Path):
    pass


class NetworkAddress[**P](_bases.Method[_typing.Any], _types.NetworkAddress):
    pass
