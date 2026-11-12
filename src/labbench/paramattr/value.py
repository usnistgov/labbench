from . import _types, _bases
from ._bases import Value
import builtins as _builtins
import typing as _typing
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
    # Type checkers see the value types as functions that return Any, so that
    #    field: int = attr.value.int(default=42)
    # checks, and the dataclass_transform on Device honors kw_only, init and
    # default (PEP 681 field specifiers must be functions or classes that name
    # those parameters; a Protocol instance is not recognized). The downside is
    # that type checker introspection misses the attributes of Value.

    def any(
        default: _typing.Any = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def bool(
        default: _builtins.bool | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def int(
        default: _builtins.int | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def float(
        default: _builtins.float | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def complex(
        default: _builtins.complex | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def str(
        default: _builtins.str | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def bytes(
        default: _builtins.bytes | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def list(
        default: _typing.Sequence | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def tuple(
        default: _typing.Sequence | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def dict(
        default: _typing.Mapping | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def Path(
        default: _Path | _builtins.str | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...

    def NetworkAddress(
        default: _builtins.str | None = None,
        *,
        key: _builtins.str | None = None,
        kw_only: _builtins.bool = True,
        init: _builtins.bool = True,
        allow_none: _builtins.bool | None = None,
        help: _builtins.str | None = None,
        **kws: _typing.Any,
    ) -> _typing.Any: ...


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
