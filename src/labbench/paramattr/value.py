from . import _types, _bases
from ._bases import Value
import builtins as _builtins
import typing as _typing
from typing import Callable as _Callable, Protocol as _Protocol, Literal as _Literal
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
    class _ValueProto[**P, V](_Protocol):
        def __call__(
            self,
            default: V | None = None,
            kw_only: _builtins.bool = True,
            help: _builtins.str | None = None,
            *args: P.args,
            **kwargs: P.kwargs,
        ): ...

    class _ValuePathProto[**P, V](_Protocol):
        def __call__(
            self,
            default: _Path | _builtins.str | None = None,
            kw_only: _builtins.bool = True,
            *args: P.args,
            **kwargs: P.kwargs,
        ): ...

    def _hint_as[V, **P](
        stub: _Callable[P, _typing.Any], type: type[V]
    ) -> _Callable[[_Callable], _ValueProto[P, V]]:
        """fill in type hints for the analysis parameters"""
        return lambda f: f

    def _hint_as_path[V, **P](
        stub: _Callable[P, _typing.Any], type: type[V]
    ) -> _Callable[[_Callable], _ValuePathProto[P, V]]:
        """fill in type hints for the analysis parameters"""
        return lambda f: f

    @_hint_as(_types.Bool, _builtins.bool)
    def bool(*args, **kws): ...

    @_hint_as(_types.Int, _builtins.int)
    def int(*args, **kws): ...

    @_hint_as(_types.Float, _builtins.float)
    def float(*args, **kws): ...

    @_hint_as(_types.Complex, _builtins.complex)
    def complex(*args, **kws): ...

    @_hint_as(_types.Unicode, _builtins.str)
    def str(*args, **kws): ...

    @_hint_as(_types.Bytes, _builtins.bytes)
    def bytes(*args, **kws): ...

    @_hint_as(_types.List, _typing.Sequence)
    def list(*args, **kws): ...

    @_hint_as(_types.Tuple, _typing.Sequence)
    def tuple(*args, **kws): ...

    @_hint_as(_types.Dict, _typing.Mapping)
    def dict(*args, **kws): ...

    @_hint_as_path(_types.Path, _Path)
    def Path(*args, **kws): ...

    @_hint_as(_types.NetworkAddress, _builtins.str)
    def NetworkAddress(*args, **kws): ...


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
