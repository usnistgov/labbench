import typing
from . import util as util
from contextlib import contextmanager as contextmanager
from typing import Any as _Any, Optional

Undefined: _Any
T: _Any

class ThisType: ...

class HasTraitsMeta(type):
    __cls_namespace__: _Any = ...
    @classmethod
    def __prepare__(cls, names: _Any, bases: _Any, **kws: _Any): ...

class Trait:
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    ROLE_VALUE: str = ...
    ROLE_PROPERTY: str = ...
    ROLE_DATARETURN: str = ...
    ROLE_UNSET: str = ...
    type: _Any = ...
    role: _Any = ...
    default: ThisType = ...
    key: Undefined = ...
    func: typing.Callable = ...
    help: str = ...
    label: str = ...
    sets: bool = ...
    gets: bool = ...
    cache: bool = ...
    only: tuple = ...
    allow_none: bool = ...
    remap: dict = ...
    kws: _Any = ...
    metadata: _Any = ...
    remap_inbound: _Any = ...
    @classmethod
    def __init_subclass__(cls, type: _Any = ...) -> None: ...
    def copy(self, new_type: Optional[_Any] = ..., **update_kws: _Any): ...
    __objclass__: _Any = ...
    name: _Any = ...
    def __set_name__(self, owner_cls: _Any, name: _Any) -> None: ...
    def __init_owner_subclass__(self, owner_cls: _Any) -> None: ...
    def __init_owner_instance__(self, owner: _Any) -> None: ...
    def __set__(self, owner: _Any, value: _Any) -> None: ...
    def __get__(self, owner: _Any, owner_cls: Optional[_Any] = ...): ...
    def __cast_get__(self, owner: _Any, value: _Any, strict: bool = ...): ...
    def to_pythonic(self, value: _Any): ...
    def from_pythonic(self, value: _Any): ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...
    def contains(self, iterable: _Any, value: _Any): ...
    def __call__(self, func: _Any): ...
    def doc(self): ...
    def doc_params(self, omit: _Any = ...): ...

class HasTraits(metaclass=HasTraitsMeta):
    __notify_list__: _Any = ...
    __cls_namespace__: _Any = ...
    __cache__: _Any = ...
    def __init__(self, **values: _Any) -> None: ...
    def __init_subclass__(cls) -> None: ...
    def __notify__(self, name: _Any, value: _Any, type: _Any, cache: _Any) -> None: ...
    def set_key(self, key: _Any, value: _Any, name: Optional[_Any] = ...) -> None: ...
    def get_key(self, key: _Any, name: Optional[_Any] = ...) -> None: ...
    def __get_value__(self, name: _Any): ...
    def __set_value__(self, name: _Any, value: _Any) -> None: ...

class Any(Trait):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...
    def to_pythonic(self, value: _Any): ...

def observe(obj: _Any, handler: _Any, name: _Any = ..., type_: _Any = ...) -> None: ...
def unobserve(obj: _Any, handler: _Any) -> None: ...

class LookupCorrectionMixIn(Trait):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        table=None,
    ): ...
    table: Any = ...
    def __init_owner_instance__(self, owner: _Any) -> None: ...
    def __owner_event__(self, msg: _Any) -> None: ...
    def lookup_cal(self, uncal: _Any, owner: _Any): ...
    def find_uncal(self, cal: _Any, owner: _Any): ...
    def set_table(
        self,
        series_or_uncal: _Any,
        cal: Optional[_Any] = ...,
        owner: Optional[_Any] = ...,
    ) -> None: ...
    def __get__(self, owner: _Any, owner_cls: Optional[_Any] = ...): ...
    def __set__(self, owner: _Any, cal: _Any) -> None: ...

class OffsetCorrectionMixIn(Trait):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        offset_name: str = None,
    ): ...
    offset_name: str = ...
    def __init_owner_instance__(self, owner: _Any) -> None: ...
    def __offset_update__(self, msg: _Any) -> None: ...
    def __other_update__(self, msg: _Any) -> None: ...
    def __get__(self, owner: _Any, owner_cls: Optional[_Any] = ...): ...
    def __set__(self, owner: _Any, value: _Any) -> None: ...

class TransformMixIn(Trait):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def __init_owner_instance__(self, owner: _Any) -> None: ...
    def __owner_event__(self, msg: _Any) -> None: ...
    def __get__(self, owner: _Any, owner_cls: Optional[_Any] = ...): ...
    def __set__(self, owner: _Any, value: _Any) -> None: ...

class BoundedNumber(Trait):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        remap: dict = {},
        min=None,
        max=None,
    ): ...
    default: ThisType = ...
    allow_none: bool = ...
    min: ThisType = ...
    max: ThisType = ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...
    def calibrate(
        self,
        offset_name: _Any = ...,
        lookup: _Any = ...,
        help: str = ...,
        label: _Any = ...,
        allow_none: bool = ...,
    ): ...
    def transform(
        self, forward: _Any, reverse: _Any, help: str = ..., allow_none: bool = ...
    ): ...
    def __neg__(self): ...
    def __add__(self, other: _Any): ...
    __radd__: _Any = ...
    def __sub__(self, other: _Any): ...
    def __rsub__(self, other: _Any): ...
    def __mul__(self, other: _Any): ...
    __rmul__: _Any = ...
    def __truediv__(self, other: _Any): ...
    def __rdiv__(self, other: _Any): ...

class NonScalar(Any):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...

class Int(BoundedNumber):
    def __init__(
        default: int = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        remap: dict = {},
        min: int = None,
        max: int = None,
    ): ...
    ...

class Float(BoundedNumber):
    def __init__(
        default: float = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        remap: dict = {},
        min: float = None,
        max: float = None,
        step: float = None,
    ): ...
    step: ThisType = ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...

class Complex(Trait):
    def __init__(
        default: complex = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    allow_none: bool = ...

class Bool(Trait):
    def __init__(
        default: bool = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    allow_none: bool = ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...

class String(Trait):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        case: bool = True,
    ): ...
    case: bool = ...
    def contains(self, iterable: _Any, value: _Any): ...

class Unicode(String):
    def __init__(
        default: str = "",
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        case: bool = True,
    ): ...
    default: ThisType = ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...

class Bytes(String):
    def __init__(
        default: bytes = b"",
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        case: bool = True,
    ): ...
    default: ThisType = ...

class Iterable(Trait):
    def __init__(
        default=None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...

class Dict(Iterable):
    def __init__(
        default: dict = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    ...

class List(Iterable):
    def __init__(
        default: list = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    ...

class Tuple(Iterable):
    def __init__(
        default: tuple = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = False,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    sets: bool = ...

class Path(Trait):
    def __init__(
        default: Path = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        must_exist: bool = False,
    ): ...
    must_exist: bool = ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...

class PandasDataFrame(NonScalar):
    def __init__(
        default: DataFrame = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    ...

class PandasSeries(NonScalar):
    def __init__(
        default: Series = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    ...

class NumpyArray(NonScalar):
    def __init__(
        default: ndarray = None,
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    ...

class NetworkAddress(Unicode):
    def __init__(
        default: str = "",
        key=None,
        func: typing.Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        case: bool = True,
        accept_port: bool = True,
    ): ...
    accept_port: bool = ...
    def validate(self, value: _Any, owner: Optional[_Any] = ...): ...

VALID_TRAIT_ROLES: _Any

def subclass_namespace_traits(
    namespace_dict: _Any, role: _Any, omit_trait_attrs: _Any
) -> None: ...
