from . import _types
from ._bases import KeywordArgument
import typing as _typing


class any(KeywordArgument, _types.Any):
    pass


class bool(KeywordArgument, _types.Bool):
    pass


class float(KeywordArgument, _types.Float):
    pass


class int(KeywordArgument, _types.Int):
    pass


class complex(KeywordArgument, _types.Complex):
    pass


class str(KeywordArgument, _types.Unicode):
    pass


class bytes(KeywordArgument, _types.Bytes):
    pass


class list(KeywordArgument, _types.List):
    pass


class tuple(KeywordArgument, _types.Tuple):
    pass


class dict(KeywordArgument, _types.Dict):
    pass


class Path(KeywordArgument, _types.Path):
    pass


class NetworkAddress(KeywordArgument, _types.NetworkAddress):
    pass
