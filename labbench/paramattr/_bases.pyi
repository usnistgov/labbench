import typing
from .. import util as util
from _typeshed import Incomplete
from collections.abc import Generator
from pathlib import Path
from typing import Any, Callable, Dict, List, Type, Union
pd: Incomplete
Undefined: Incomplete
T = typing.TypeVar('T')


class ThisType(typing.Generic[T]):
    ...


class KeyAdapterBase():

    def __new__(cls, *args, **kws):
        ...

    def __call__(self, owner_cls):
        ...

    def get(self, trait_owner, key, trait: Incomplete | None=...) -> None:
        ...

    def set(self, trait_owner, key, value, trait: Incomplete | None=...) -> None:
        ...


class HasParamAttrsClsInfo():
    attrs: Dict[str, ParamAttr]
    key_adapter: KeyAdapterBase

    def __init__(self, attrs: Dict[str, ParamAttr]=..., key_adapter: KeyAdapterBase=...) -> None:
        ...

    def value_names(self) -> List[ParamAttr]:
        ...

    def method_names(self) -> List[ParamAttr]:
        ...

    def property_names(self) -> List[ParamAttr]:
        ...


class HasParamAttrsMeta(type):
    ns_pending: list

    @classmethod
    def __prepare__(metacls, names, bases, **kws):
        ...


class ParamAttr():

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...
    ROLE_VALUE: str
    ROLE_PROPERTY: str
    ROLE_METHOD: str
    ROLE_UNSET: str
    type: Incomplete
    role = ROLE_UNSET
    default: ThisType
    key: Undefined
    argname: Union[str, None]
    help: str
    label: str
    sets: bool
    gets: bool
    cache: bool
    only: tuple
    allow_none: bool
    argchecks: List[Callable]
    kws: Incomplete
    metadata: Incomplete

    @classmethod
    def __init_subclass__(cls, type=...) -> None:
        ...

    def copy(self, new_type: Incomplete | None=..., **update_kws):
        ...
    __objclass__: Incomplete
    name: Incomplete

    def __set_name__(self, owner_cls, name) -> None:
        ...

    def __init_owner_subclass__(self, owner_cls) -> None:
        ...

    def __init_owner_instance__(self, owner) -> None:
        ...

    def __set__(self, owner: HasParamAttrs, value):
        ...

    def __get__(self, owner, owner_cls: Incomplete | None=...):
        ...

    def __cast_get__(self, owner, value, strict: bool=...):
        ...

    def to_pythonic(self, value):
        ...

    def from_pythonic(self, value):
        ...

    def validate(self, value, owner: Incomplete | None=...):
        ...

    def contains(self, iterable, value):
        ...

    def __call__(self, func=..., **kwargs):
        ...

    def doc(self, as_argument: bool=..., anonymous: bool=...):
        ...

    def doc_params(self, omit=...):
        ...

    def update(self, obj: Incomplete | None=..., **attrs):
        ...

    def adopt(self, default=..., **trait_params):
        ...

def hold_trait_notifications(owner) -> Generator[None, None, None]:
    ...


class HasParamAttrsInstInfo():
    handlers: Dict[str, Callable]
    calibrations: Dict[str, Any]
    cache: Dict[str, Any]
    methods: Dict[str, Callable]

    def __init__(self, owner: HasParamAttrs) -> None:
        ...

def get_class_attrs(obj: Union[HasParamAttrs, Type[HasParamAttrs]]) -> Dict[str, ParamAttr]:
    ...

def list_value_attrs(obj: Union[HasParamAttrs, Type[HasParamAttrs]]) -> List[str]:
    ...

def list_method_attrs(obj: Union[HasParamAttrs, Type[HasParamAttrs]]) -> List[str]:
    ...

def list_property_attrs(obj: Union[HasParamAttrs, Type[HasParamAttrs]]) -> List[str]:
    ...


class HasParamAttrs(metaclass=HasParamAttrsMeta):

    def __init__(self, **values) -> None:
        ...

    def __init_subclass__(cls) -> None:
        ...

    def __notify__(self, name, value, type, cache) -> None:
        ...

    def __get_value__(self, name):
        ...

    def __set_value__(self, name, value) -> None:
        ...

def adjusted(trait: Union[ParamAttr, str], default: Any=..., **trait_params) -> HasParamAttrs:
    ...


class Any(ParamAttr, type=None):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...

    def validate(self, value, owner: Incomplete | None=...):
        ...

    def to_pythonic(self, value):
        ...

def observe(obj, handler, name=..., type_=...) -> None:
    ...

def unobserve(obj, handler) -> None:
    ...

def find_trait_in_mro(cls):
    ...


class DependentParamAttr(ParamAttr):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...

    def __set_name__(self, owner_cls, name) -> None:
        ...

    @classmethod
    def derive(mixin_cls, template_trait, dependent_attrs=..., *init_args, **init_kws):
        ...


class RemappingCorrectionMixIn(DependentParamAttr):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[],
        mapping=None
    ):
        ...
    mapping: Any
    EMPTY_STORE: Incomplete

    def __init_owner_instance__(self, owner) -> None:
        ...

    def lookup_cal(self, uncal, owner):
        ...

    def find_uncal(self, cal, owner):
        ...

    def set_mapping(self, series_or_uncal, cal: Incomplete | None=..., owner: Incomplete | None=...) -> None:
        ...

    def __get__(self, owner, owner_cls: Incomplete | None=...):
        ...

    def __set__(self, owner, cal) -> None:
        ...


class TableCorrectionMixIn(RemappingCorrectionMixIn):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[],
        mapping=None,
        table_index_column: str=None
    ):
        ...
    path_trait: Incomplete
    index_lookup_trait: Incomplete
    table_index_column: str

    def __init_owner_instance__(self, owner) -> None:
        ...

    def __get__(self, owner, owner_cls: Incomplete | None=...):
        ...

    def __set__(self, owner, cal) -> None:
        ...


class TransformMixIn(DependentParamAttr):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...

    def __init_owner_instance__(self, owner) -> None:
        ...

    def __owner_event__(self, msg) -> None:
        ...

    def __get__(self, owner, owner_cls: Incomplete | None=...):
        ...

    def __set__(self, owner, value_request) -> None:
        ...


class BoundedNumber(ParamAttr):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        argchecks: List=[],
        min=None,
        max=None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str=None
    ):
        ...
    default: ThisType
    allow_none: bool
    min: ThisType
    max: ThisType

    def validate(self, value, owner: Incomplete | None=...):
        ...
    path_trait: Any
    index_lookup_trait: Any
    table_index_column: str

    def calibrate_from_table(
        self,
        path_trait,
        index_lookup_trait,
        *,
        table_index_column: str=...,
        help: str=...,
        label=...,
        allow_none: bool=...
    ):
        ...

    def calibrate_from_expression(
        self,
        trait_expression,
        help: str=...,
        label: str=...,
        allow_none: bool=...
    ):
        ...

    def transform(
        self,
        other_trait: ParamAttr,
        forward: callable,
        reverse: callable,
        help: str=...,
        allow_none: bool=...
    ):
        ...

    def __neg__(self):
        ...

    def __add__(self, other):
        ...
    __radd__ = __add__

    def __sub__(self, other):
        ...

    def __rsub__(self, other):
        ...

    def __mul__(self, other):
        ...
    __rmul__ = __mul__

    def __truediv__(self, other):
        ...

    def __rdiv__(self, other):
        ...


class NonScalar(Any):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...

    def validate(self, value, owner: Incomplete | None=...):
        ...


class Int(BoundedNumber, type=int):

    def __init__(
        default: int=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        argchecks: List=[],
        min: int=None,
        max: int=None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str=None
    ):
        ...
    ...


class Float(BoundedNumber, type=float):

    def __init__(
        default: float=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        argchecks: List=[],
        min: float=None,
        max: float=None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str=None,
        step: float=None
    ):
        ...
    step: ThisType

    def validate(self, value, owner: Incomplete | None=...):
        ...


class Complex(ParamAttr, type=complex):

    def __init__(
        default: complex=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...
    allow_none: bool


class Bool(ParamAttr, type=bool):

    def __init__(
        default: bool=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...
    allow_none: bool

    def validate(self, value, owner: Incomplete | None=...):
        ...


class String(ParamAttr):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[],
        case: bool=True
    ):
        ...
    case: bool

    def contains(self, iterable, value):
        ...


class Unicode(String, type=str):

    def __init__(
        default: str='',
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[],
        case: bool=True
    ):
        ...
    default: ThisType

    def validate(self, value, owner: Incomplete | None=...):
        ...


class Bytes(String, type=bytes):

    def __init__(
        default: bytes=b'',
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[],
        case: bool=True
    ):
        ...
    default: ThisType


class Iterable(ParamAttr):

    def __init__(
        default=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...

    def validate(self, value, owner: Incomplete | None=...):
        ...


class Dict(Iterable, type=dict):

    def __init__(
        default: dict=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...
    ...


class List(Iterable, type=list):

    def __init__(
        default: list=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...
    ...


class Tuple(Iterable, type=tuple):

    def __init__(
        default: tuple=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=False,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[]
    ):
        ...
    sets: bool


class Path(ParamAttr, type=Path):

    def __init__(
        default: Path=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[],
        must_exist: bool=False
    ):
        ...
    must_exist: bool

    def validate(self, value, owner: Incomplete | None=...):
        ...


class NetworkAddress(Unicode):

    def __init__(
        default: str='',
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        argchecks: List=[],
        case: bool=True,
        accept_port: bool=True
    ):
        ...
    accept_port: bool

    def validate(self, value, owner: Incomplete | None=...):
        ...
VALID_TRAIT_ROLES: Incomplete

def subclass_namespace_attrs(namespace_dict, role, omit_trait_attrs) -> None:
    ...


class message_keying(KeyAdapterBase):
    query_fmt: Incomplete
    write_fmt: Incomplete
    write_func: Incomplete
    query_func: Incomplete
    value_map: Incomplete
    message_map: Incomplete

    def __init__(
        self,
        query_fmt: Incomplete | None=...,
        write_fmt: Incomplete | None=...,
        write_func: Incomplete | None=...,
        query_func: Incomplete | None=...,
        remap=...
    ) -> None:
        ...

    @classmethod
    def get_key_arguments(cls, s: str) -> List[str]:
        ...

    def from_message(self, msg):
        ...

    def to_message(self, value):
        ...

    def get(
        self,
        device: HasParamAttrs,
        scpi_key: str,
        trait: Incomplete | None=...,
        arguments: Dict[str, Any]=...
    ):
        ...

    def set(
        self,
        device: HasParamAttrs,
        scpi_key: str,
        value,
        trait: Incomplete | None=...,
        arguments: Dict[str, Any]=...
    ):
        ...

    def method_from_key(self, device: HasParamAttrs, trait: ParamAttr):
        ...


class visa_keying(message_keying):

    def __init__(self, query_fmt: str=..., write_fmt: str=..., remap=...) -> None:
        ...
