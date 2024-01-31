from . import _types
from ._bases import MethodKeywordArgument


class any(MethodKeywordArgument, _types.Any):
    pass


class bool(MethodKeywordArgument, _types.Bool):
    pass


class float(MethodKeywordArgument, _types.Float):
    pass


class int(MethodKeywordArgument, _types.Int):
    pass


class complex(MethodKeywordArgument, _types.Complex):
    pass


class str(MethodKeywordArgument, _types.Unicode):
    pass


class bytes(MethodKeywordArgument, _types.Bytes):
    pass


class list(MethodKeywordArgument, _types.List):
    pass


class tuple(MethodKeywordArgument, _types.Tuple):
    pass


class dict(MethodKeywordArgument, _types.Dict):
    pass


class Path(MethodKeywordArgument, _types.Path):
    pass


class NetworkAddress(MethodKeywordArgument, _types.NetworkAddress):
    pass
