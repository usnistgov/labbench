import typing
from . import util as util
from _typeshed import Incomplete
from collections.abc import Generator
from pathlib import Path
from typing import Any, Union

pd: Incomplete
Undefined: Incomplete
T = typing.TypeVar("T")

class ThisType(typing.Generic[T]): ...

class HasTraitsMeta(type):
    __cls_namespace__: Incomplete

    @classmethod
    def __prepare__(cls, names, bases, **kws): ...

class Trait:
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ROLE_VALUE: str
    ROLE_PROPERTY: str
    ROLE_DATARETURN: str
    ROLE_UNSET: str
    type: Incomplete
    role = ROLE_UNSET
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
    kws: Incomplete
    metadata: Incomplete

    @classmethod
    def __init_subclass__(cls, type=...) -> None: ...
    def copy(self, new_type: Incomplete | None = ..., **update_kws): ...
    __objclass__: Incomplete
    name: Incomplete

    def __set_name__(self, owner_cls, name) -> None: ...
    def __init_owner_subclass__(self, owner_cls) -> None: ...
    def __init_owner_instance__(self, owner) -> None: ...
    def __set__(self, owner: HasTraits, value): ...
    def __get__(self, owner, owner_cls: Incomplete | None = ...): ...
    def __cast_get__(self, owner, value, strict: bool = ...): ...
    def to_pythonic(self, value): ...
    def from_pythonic(self, value): ...
    def validate(self, value, owner: Incomplete | None = ...): ...
    def contains(self, iterable, value): ...
    def __call__(self, func=..., **kwargs): ...
    def doc(self, as_argument: bool = ..., anonymous: bool = ...): ...
    def doc_params(self, omit=...): ...
    def update(self, obj: Incomplete | None = ..., **attrs): ...
    def adopt(self, default=..., **trait_params): ...

def hold_trait_notifications(owner) -> Generator[None, None, None]: ...

class PropertyKeyingBase:
    def __new__(cls, *args, **kws): ...
    def __call__(self, owner_cls): ...
    def get(self, trait_owner, key, trait: Incomplete | None = ...) -> None: ...
    def set(self, trait_owner, key, value, trait: Incomplete | None = ...) -> None: ...

class HasTraits(metaclass=HasTraitsMeta):
    __notify_list__: Incomplete
    __cls_namespace__: Incomplete
    __cache__: Incomplete

    def __init__(self, **values) -> None: ...
    def __init_subclass__(cls) -> None: ...
    def __notify__(self, name, value, type, cache) -> None: ...
    def __get_value__(self, name): ...
    def __set_value__(self, name, value) -> None: ...

def adjusted(
    trait: Union[Trait, str], default: Any = ..., **trait_params
) -> HasTraits: ...

class Any(Trait, type=None):
    def __init__(
        default: str = None,
        key: str = None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    def validate(self, value, owner: Incomplete | None = ...): ...
    def to_pythonic(self, value): ...

def observe(obj, handler, name=..., type_=...) -> None: ...
def unobserve(obj, handler) -> None: ...
def find_trait_in_mro(cls): ...

class DependentTrait(Trait):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    def __set_name__(self, owner_cls, name) -> None: ...
    @classmethod
    def derive(
        mixin_cls, template_trait, dependent_traits=..., *init_args, **init_kws
    ): ...

class RemappingCorrectionMixIn(DependentTrait):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        mapping: str = None,
    ): ...
    mapping: Any
    EMPTY_STORE: Incomplete

    def __init_owner_instance__(self, owner) -> None: ...
    def lookup_cal(self, uncal, owner): ...
    def find_uncal(self, cal, owner): ...
    def set_mapping(
        self,
        series_or_uncal,
        cal: Incomplete | None = ...,
        owner: Incomplete | None = ...,
    ) -> None: ...
    def __get__(self, owner, owner_cls: Incomplete | None = ...): ...
    def __set__(self, owner, cal) -> None: ...

class TableCorrectionMixIn(RemappingCorrectionMixIn):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        mapping: str = None,
        table_index_column: str = None,
    ): ...
    path_trait: Incomplete
    index_lookup_trait: Incomplete
    table_index_column: str

    def __init_owner_instance__(self, owner) -> None: ...
    def __get__(self, owner, owner_cls: Incomplete | None = ...): ...
    def __set__(self, owner, cal) -> None: ...

class TransformMixIn(DependentTrait):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    def __init_owner_instance__(self, owner) -> None: ...
    def __owner_event__(self, msg) -> None: ...
    def __get__(self, owner, owner_cls: Incomplete | None = ...): ...
    def __set__(self, owner, value_request) -> None: ...

class BoundedNumber(Trait):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = True,
        min: str = None,
        max: str = None,
        path_trait: str = None,
        index_lookup_trait: str = None,
        table_index_column: str = None,
    ): ...
    default: ThisType
    allow_none: bool
    min: ThisType
    max: ThisType

    def validate(self, value, owner: Incomplete | None = ...): ...
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
        allow_none: bool = ...,
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
    __radd__ = __add__

    def __sub__(self, other): ...
    def __rsub__(self, other): ...
    def __mul__(self, other): ...
    __rmul__ = __mul__

    def __truediv__(self, other): ...
    def __rdiv__(self, other): ...

class NonScalar(Any):
    def __init__(
        default: str = None,
        key: str = None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    def validate(self, value, owner: Incomplete | None = ...): ...

class Int(BoundedNumber, type=int):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = True,
        min: str = None,
        max: str = None,
        path_trait: str = None,
        index_lookup_trait: str = None,
        table_index_column: str = None,
    ): ...
    ...

class Float(BoundedNumber, type=float):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = True,
        min: str = None,
        max: str = None,
        path_trait: str = None,
        index_lookup_trait: str = None,
        table_index_column: str = None,
        step: str = None,
    ): ...
    step: ThisType

    def validate(self, value, owner: Incomplete | None = ...): ...

class Complex(Trait, type=complex):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    allow_none: bool

class Bool(Trait, type=bool):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    allow_none: bool

    def validate(self, value, owner: Incomplete | None = ...): ...

class String(Trait):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        case: str = True,
    ): ...
    case: bool

    def contains(self, iterable, value): ...

class Unicode(String, type=str):
    def __init__(
        default: str = "",
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        case: str = True,
    ): ...
    default: ThisType

    def validate(self, value, owner: Incomplete | None = ...): ...

class Bytes(String, type=bytes):
    def __init__(
        default: str = b"",
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        case: str = True,
    ): ...
    default: ThisType

class Iterable(Trait):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    def validate(self, value, owner: Incomplete | None = ...): ...

class Dict(Iterable, type=dict):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class List(Iterable, type=list):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class Tuple(Iterable, type=tuple):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = False,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    sets: bool

class Path(Trait, type=Path):
    def __init__(
        default: str = None,
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        must_exist: str = False,
    ): ...
    must_exist: bool

    def validate(self, value, owner: Incomplete | None = ...): ...

class NetworkAddress(Unicode):
    def __init__(
        default: str = "",
        key=None,
        func: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        case: str = True,
        accept_port: str = True,
    ): ...
    accept_port: bool

    def validate(self, value, owner: Incomplete | None = ...): ...

VALID_TRAIT_ROLES: Incomplete

def subclass_namespace_traits(namespace_dict, role, omit_trait_attrs) -> None: ...
