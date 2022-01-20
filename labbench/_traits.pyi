import typing
from . import util as util
from contextlib import contextmanager as contextmanager
from typing import Any as _Any

Undefined: _Any
T: _Any

class ThisType: ...

class HasTraitsMeta(type):
    __cls_namespace__: _Any
    @classmethod
    def __prepare__(cls, names, bases, **kws): ...

class Trait:
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    ROLE_VALUE: str
    ROLE_PROPERTY: str
    ROLE_DATARETURN: str
    ROLE_UNSET: str
    type: _Any
    role: _Any
    default: ThisType
    key: Undefined
    func: typing.Callable
    help: str
    label: str
    sets: bool
    gets: bool
    cache: bool
    only: tuple
    allow_none: bool
    remap: dict
    kws: _Any
    metadata: _Any
    remap_inbound: _Any
    @classmethod
    def __init_subclass__(cls, type=...) -> None: ...
    def copy(self, new_type: _Any | None = ..., **update_kws): ...
    __objclass__: _Any
    name: _Any
    def __set_name__(self, owner_cls, name) -> None: ...
    def __init_owner_subclass__(self, owner_cls) -> None: ...
    def __init_owner_instance__(self, owner) -> None: ...
    def __set__(self, owner, value) -> None: ...
    def __get__(self, owner, owner_cls: _Any | None = ...): ...
    def __cast_get__(self, owner, value, strict: bool = ...): ...
    def to_pythonic(self, value): ...
    def from_pythonic(self, value): ...
    def validate(self, value, owner: _Any | None = ...): ...
    def contains(self, iterable, value): ...
    def __call__(self, func): ...
    def doc(self): ...
    def doc_params(self, omit=...): ...
    def update(self, obj: _Any | None = ..., **attrs): ...

class HasTraits(metaclass=HasTraitsMeta):
    __notify_list__: _Any
    __cls_namespace__: _Any
    __cache__: _Any
    def __init__(self, **values) -> None: ...
    def __init_subclass__(cls) -> None: ...
    def __notify__(self, name, value, type, cache) -> None: ...
    def set_key(self, key, value, name: _Any | None = ...) -> None: ...
    def get_key(self, key, name: _Any | None = ...) -> None: ...
    def __get_value__(self, name): ...
    def __set_value__(self, name, value) -> None: ...

class Any(Trait):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def validate(self, value, owner: _Any | None = ...): ...
    def to_pythonic(self, value): ...

def observe(obj, handler, name=..., type_=...) -> None: ...
def unobserve(obj, handler) -> None: ...
def find_trait_in_mro(cls): ...

class DependentTrait(Trait):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def __set_name__(self, owner_cls, name) -> None: ...
    @classmethod
    def derive(
        mixin_cls, template_trait, dependent_traits=..., *init_args, **init_kws
    ): ...

class RemappingCorrectionMixIn(DependentTrait):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        mapping=None,
    ): ...
    mapping: Any
    EMPTY_STORE: _Any
    def __init_owner_instance__(self, owner) -> None: ...
    def lookup_cal(self, uncal, owner): ...
    def find_uncal(self, cal, owner): ...
    def set_mapping(
        self, series_or_uncal, cal: _Any | None = ..., owner: _Any | None = ...
    ) -> None: ...
    def __get__(self, owner, owner_cls: _Any | None = ...): ...
    def __set__(self, owner, cal) -> None: ...

class TableCorrectionMixIn(RemappingCorrectionMixIn):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
        mapping=None,
        table_index_column: str = None,
    ): ...
    path_trait: _Any
    index_lookup_trait: _Any
    table_index_column: str
    def __init_owner_instance__(self, owner) -> None: ...

class TransformMixIn(DependentTrait):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def __init_owner_instance__(self, owner) -> None: ...
    def __owner_event__(self, msg) -> None: ...
    def __get__(self, owner, owner_cls: _Any | None = ...): ...
    def __set__(self, owner, value_request) -> None: ...

class BoundedNumber(Trait):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
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
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
    ): ...
    default: ThisType
    allow_none: bool
    min: ThisType
    max: ThisType
    def validate(self, value, owner: _Any | None = ...): ...
    path_trait: Any
    index_lookup_trait: Any
    table_index_column: str
    def calibrate_from_table(
        self,
        path_trait,
        index_lookup_trait,
        *,
        table_index_column: str = ...,
        help: str = ...,
        label=...,
        allow_none: bool = ...
    ): ...
    def calibrate_from_expression(
        self,
        trait_expression,
        help: str = ...,
        label: str = ...,
        allow_none: bool = ...,
    ): ...
    def transform(
        self,
        other_trait: Trait,
        forward: callable,
        reverse: callable,
        help: str = ...,
        allow_none: bool = ...,
    ): ...
    def __neg__(self): ...
    def __add__(self, other): ...
    __radd__: _Any
    def __sub__(self, other): ...
    def __rsub__(self, other): ...
    def __mul__(self, other): ...
    __rmul__: _Any
    def __truediv__(self, other): ...
    def __rdiv__(self, other): ...

class NonScalar(Any):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def validate(self, value, owner: _Any | None = ...): ...

class Int(BoundedNumber):
    def __init__(
        default: int = None,
        key=None,
        func: _CallableType = None,
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
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
    ): ...
    ...

class Float(BoundedNumber):
    def __init__(
        default: float = None,
        key=None,
        func: _CallableType = None,
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
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
        step: float = None,
    ): ...
    step: ThisType
    def validate(self, value, owner: _Any | None = ...): ...

class Complex(Trait):
    def __init__(
        default: complex = None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    allow_none: bool

class Bool(Trait):
    def __init__(
        default: bool = None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    allow_none: bool
    def validate(self, value, owner: _Any | None = ...): ...

class String(Trait):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
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
    case: bool
    def contains(self, iterable, value): ...

class Unicode(String):
    def __init__(
        default: str = "",
        key=None,
        func: _CallableType = None,
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
    default: ThisType
    def validate(self, value, owner: _Any | None = ...): ...

class Bytes(String):
    def __init__(
        default: bytes = b"",
        key=None,
        func: _CallableType = None,
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
    default: ThisType

class Iterable(Trait):
    def __init__(
        default=None,
        key=None,
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    def validate(self, value, owner: _Any | None = ...): ...

class Dict(Iterable):
    def __init__(
        default: dict = None,
        key=None,
        func: _CallableType = None,
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
        func: _CallableType = None,
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
        func: _CallableType = None,
        help: str = "",
        label: str = "",
        sets: bool = False,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        remap: dict = {},
    ): ...
    sets: bool

class Path(Trait):
    def __init__(
        default: Path = None,
        key=None,
        func: _CallableType = None,
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
    must_exist: bool
    def validate(self, value, owner: _Any | None = ...): ...

class PandasDataFrame(NonScalar):
    def __init__(
        default: DataFrame = None,
        key=None,
        func: _CallableType = None,
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
        func: _CallableType = None,
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
        func: _CallableType = None,
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
        func: _CallableType = None,
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
    accept_port: bool
    def validate(self, value, owner: _Any | None = ...): ...

VALID_TRAIT_ROLES: _Any

def subclass_namespace_traits(namespace_dict, role, omit_trait_attrs) -> None: ...
