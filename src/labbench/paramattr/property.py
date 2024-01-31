from . import _types
from ._bases import Property


class any(Property, _types.Any):
    pass


class bool(Property, _types.Bool):
    pass


class float(Property, _types.Float):
    pass


class int(Property, _types.Int):
    pass


class complex(Property, _types.Complex):
    pass


class str(Property, _types.Unicode):
    pass


class bytes(Property, _types.Bytes):
    pass


class list(Property, _types.List):
    pass


class tuple(Property, _types.Tuple):
    pass


class dict(Property, _types.Dict):
    pass


class Path(Property, _types.Path):
    pass


class NetworkAddress(Property, _types.NetworkAddress):
    pass
