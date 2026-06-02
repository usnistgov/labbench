from . import _types, _bases
from ._bases import Value
import builtins as _builtins
import typing_extensions as _typing
from pathlib import Path as _Path
from numbers import Number as _Number


class any(Value, _types.Any):
    """defines a value attribute that validates any python object"""


class bool(Value, _types.Bool):
    """defines a value attribute that casts to python builtin bool"""


class int(Value, _types.Int):
    """defines a value attribute that casts to python builtin bool"""


class float(Value, _types.Float):
    """defines a value attribute that casts to python builtin float"""


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


if _typing.TYPE_CHECKING:
    # trick type-checkers to interpret the value types as int.
    # this allows declarations of init functions as e.g.
    #    field: int = attr.value.int(default=42)
    # with the downside that type checker introspection will miss
    # the actual attributes of Value
    from typing import Callable as _Callable, Protocol as _Protocol, Literal as _Literal

    _V1 = _typing.TypeVar('_V1')
    _V2 = _typing.TypeVar('_V2')
    _P = _typing.ParamSpec('_P')

    class _ValueProto(_Protocol):
        def __call__(
            self,
            default: _V1 | None = None,
            kw_only: _builtins.bool = True,
            help: _builtins.str | None = None,
            init: _builtins.bool = True,
            *args: _P.args,
            **kwargs: _P.kwargs,
        ) -> _typing.Any: ...

    def _hint1(
        stub: _Callable[_P, _typing.Any], t1: type[_V1]
    ) -> _Callable[[_Callable], _ValueProto[_P, _V1]]: ...

    def _hint2(
        stub: _Callable[_P, _typing.Any], t1: type[_V1], t2: type[_V2]
    ) -> _Callable[[_Callable], _ValueProto[_P, _V1 | _V2]]: ...

    @_hint1(_types.Bool, _builtins.bool)
    def bool(*args, **kws): ...

    @_hint1(_types.Int, _builtins.int)
    def int(*args, **kws): ...

    @_hint1(_types.Float, _builtins.float)
    def float(*args, **kws): ...

    @_hint1(_types.Complex, _builtins.complex)
    def complex(*args, **kws): ...

    @_hint1(_types.Unicode, _builtins.str)
    def str(*args, **kws): ...

    @_hint1(_types.Bytes, _builtins.bytes)
    def bytes(*args, **kws): ...

    @_hint1(_types.List, _typing.Sequence)
    def list(*args, **kws): ...

    @_hint1(_types.Tuple, _typing.Sequence)
    def tuple(*args, **kws): ...

    @_hint1(_types.Dict, _typing.Mapping)
    def dict(*args, **kws): ...

    @_hint2(_types.Path, _Path, _builtins.str)
    def Path(*args, **kws): ...

    @_hint1(_types.NetworkAddress, _builtins.str)
    def NetworkAddress(*args, **kws): ...


# used to set up hints for static type checking
_ALL_TYPES = (
    Value,
    any,
    bool,
    bytes,
    complex,
    dict,
    float,
    int,
    list,
    Path,
    str,
    tuple,
    NetworkAddress,
)
