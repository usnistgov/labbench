import typing
from . import util as util
from _typeshed import Incomplete
from collections.abc import Generator
from typing import Union

Undefined: Incomplete
T: Incomplete

class ThisType: ...

class HasTraitsMeta(type):
    __cls_namespace__: Incomplete

    @classmethod
    def __prepare__(cls, names, bases, **kws): ...

class Trait:
    def __init__(
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
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
    def __set__(self, owner, value) -> None: ...
    def __get__(self, owner, owner_cls: Incomplete | None = ...): ...
    def __cast_get__(self, owner, value, strict: bool = ...): ...
    def to_pythonic(self, value): ...
    def from_pythonic(self, value): ...
    def validate(self, value, owner: Incomplete | None = ...): ...
    def contains(self, iterable, value): ...
    def __call__(self, func): ...
    def doc(self, as_argument: bool = ...): ...
    def doc_params(self, omit=...): ...
    def update(self, obj: Incomplete | None = ..., **attrs): ...

def hold_trait_notifications(owner) -> Generator[None, None, None]: ...

class BackendPropertyAdapter:
    def __new__(cls, *args, **kws): ...
    def __call__(self, owner_cls): ...
    def get(self, trait_owner, key, trait: Incomplete | None = ...) -> None: ...
    def set(self, trait_owner, key, value, trait: Incomplete | None = ...) -> None: ...

class MessagePropertyAdapter(BackendPropertyAdapter):
    query_fmt: Incomplete
    write_fmt: Incomplete
    value_map: Incomplete
    message_map: Incomplete

    def __init__(
        self, query_fmt: str = ..., write_fmt: str = ..., remap=...
    ) -> None: ...

class HasTraits(metaclass=HasTraitsMeta):
    __notify_list__: Incomplete
    __cls_namespace__: Incomplete
    __cache__: Incomplete

    def __init__(self, **values) -> None: ...
    def __init_subclass__(cls) -> None: ...
    def __notify__(self, name, value, type, cache) -> None: ...
    def __get_value__(self, name): ...
    def __set_value__(self, name, value) -> None: ...

class Any(Trait):
    def __init__(
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    def validate(self, value, owner: Incomplete | None = ...): ...
    def to_pythonic(self, value): ...

def observe(obj, handler, name=..., type_=...) -> None: ...
def mutate_trait(trait_or_name: Union[Trait, str], **trait_params): ...
def unobserve(obj, handler) -> None: ...
def find_trait_in_mro(cls): ...

class DependentTrait(Trait):
    def __init__(
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
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
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        mapping=None,
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
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        mapping=None,
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
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    def __init_owner_instance__(self, owner) -> None: ...
    def __owner_event__(self, msg) -> None: ...
    def __get__(self, owner, owner_cls: Incomplete | None = ...): ...
    def __set__(self, owner, value_request) -> None: ...

class BoundedNumber(Trait):
    def __init__(
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
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
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    def validate(self, value, owner: Incomplete | None = ...): ...

class Int(BoundedNumber):
    def __init__(
        default: int = None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
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
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        min: float = None,
        max: float = None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
        step: float = None,
    ): ...
    step: ThisType

    def validate(self, value, owner: Incomplete | None = ...): ...

class Complex(Trait):
    def __init__(
        default: complex = None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    allow_none: bool

class Bool(Trait):
    def __init__(
        default: bool = None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    allow_none: bool

    def validate(self, value, owner: Incomplete | None = ...): ...

class String(Trait):
    def __init__(
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        case: bool = True,
    ): ...
    case: bool

    def contains(self, iterable, value): ...

class Unicode(String):
    def __init__(
        default: str = "",
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        case: bool = True,
    ): ...
    default: ThisType

    def validate(self, value, owner: Incomplete | None = ...): ...

class Bytes(String):
    def __init__(
        default: bytes = b"",
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        case: bool = True,
    ): ...
    default: ThisType

class Iterable(Trait):
    def __init__(
        default=None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    def validate(self, value, owner: Incomplete | None = ...): ...

class Dict(Iterable):
    def __init__(
        default: dict = None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    ...

class List(Iterable):
    def __init__(
        default: list = None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    ...

class Tuple(Iterable):
    def __init__(
        default: tuple = None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = False,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
    ): ...
    sets: bool

class Path(Trait):
    def __init__(
        default: Path = None,
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        must_exist: bool = False,
    ): ...
    must_exist: bool

    def validate(self, value, owner: Incomplete | None = ...): ...

class NetworkAddress(Unicode):
    def __init__(
        default: str = "",
        key=None,
        func: Callable = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        case: bool = True,
        accept_port: bool = True,
    ): ...
    accept_port: bool

    def validate(self, value, owner: Incomplete | None = ...): ...

VALID_TRAIT_ROLES: Incomplete

def subclass_namespace_traits(namespace_dict, role, omit_trait_attrs) -> None: ...
