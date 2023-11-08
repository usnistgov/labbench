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


class no_cast_argument():

    @classmethod
    def __cast_get__(self, owner, value):
        ...


class KeyAdapterBase():
    arguments: Dict[str, ParamAttr]

    def __new__(cls, decorated_cls: HasParamAttrs=..., **kws):
        ...
    strict_arguments: Incomplete

    def __init__(self, *, arguments: Dict[str, ParamAttr]=..., strict_arguments: bool=...) -> None:
        ...

    def __call__(self, owner_cls: Type[HasParamAttrs]):
        ...

    def get(self, owner: HasParamAttrs, key: str, attr: ParamAttr=...):
        ...

    def set(self, owner: HasParamAttrs, key: str, value, attr: ParamAttr=...):
        ...

    def get_key_arguments(self, key: Any) -> List[str]:
        ...

    def method_from_key(self, owner_cls: Type[HasParamAttrs], trait: ParamAttr):
        ...


class HasParamAttrsClsInfo():
    attrs: Dict[str, ParamAttr]
    key_adapter: KeyAdapterBase
    methods: Dict[str, Callable]

    def __init__(self, attrs: Dict[str, ParamAttr], key_adapter: KeyAdapterBase) -> None:
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
        arguments: Dict=[]
    ):
        ...
    ROLE_VALUE: str
    ROLE_PROPERTY: str
    ROLE_METHOD: str
    ROLE_UNSET: str
    ROLE_ARGUMENT: str
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
    arguments: Dict[Any, ParamAttr]
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

    def __init_owner_subclass__(self, owner_cls: Type[HasParamAttrs]):
        ...

    def __init_owner_instance__(self, owner) -> None:
        ...

    def __set__(self, owner: HasParamAttrs, value):
        ...

    def set_in_owner(self, owner: HasParamAttrs, value, arguments: Dict[str, Any]=...):
        ...

    def __get__(self, owner: HasParamAttrs, owner_cls: Union[None, Type[HasParamAttrs]]=...):
        ...

    def get_from_owner(self, owner: HasParamAttrs, arguments: Dict[str, Any]=...):
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

def hold_attr_notifications(owner) -> Generator[None, None, None]:
    ...


class HasParamAttrsInstInfo():
    handlers: Dict[str, Callable]
    calibrations: Dict[str, Any]
    cache: Dict[str, Any]

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

def adjusted(paramattr: Union[ParamAttr, str], default: Any=..., **kws) -> HasParamAttrs:
    ...


class Any(ParamAttr, type=object):

    def __init__(
        default: object=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[]
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

def find_paramattr_in_mro(cls):
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
        arguments: Dict=[]
    ):
        ...

    def __set_name__(self, owner_cls, name) -> None:
        ...

    @classmethod
    def derive(mixin_cls, template_attr: ParamAttr, dependent_attrs=..., *init_args, **init_kws):
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
        arguments: Dict=[],
        mapping=None
    ):
        ...
    mapping: Any
    EMPTY_STORE: Incomplete

    def __init_owner_instance__(self, owner: HasParamAttrs):
        ...

    def lookup_cal(self, uncal, owner):
        ...

    def find_uncal(self, cal, owner):
        ...

    def set_mapping(self, series_or_uncal, cal: Incomplete | None=..., owner: Incomplete | None=...) -> None:
        ...

    def get_from_owner(self, owner: HasParamAttrs, arguments: Dict[str, Any]=...):
        ...

    def set_in_owner(self, owner: HasParamAttrs, cal_value, arguments: Dict[str, Any]=...):
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
        arguments: Dict=[],
        mapping=None,
        table_index_column: str=None
    ):
        ...
    path_attr: Incomplete
    index_lookup_attr: Incomplete
    table_index_column: str

    def __init_owner_instance__(self, owner) -> None:
        ...

    def get_from_owner(self, owner: HasParamAttrs, arguments: Dict[str, Any]=...):
        ...

    def set_in_owner(self, owner: HasParamAttrs, cal_value, arguments: Dict[str, Any]=...):
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
        arguments: Dict=[]
    ):
        ...

    def __init_owner_instance__(self, owner) -> None:
        ...

    def __owner_event__(self, msg) -> None:
        ...

    def get_from_owner(self, owner: HasParamAttrs, arguments: Dict[str, Any]=...):
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
        arguments: Dict=[],
        min=None,
        max=None,
        path_attr=None,
        index_lookup_attr=None,
        table_index_column: str=None
    ):
        ...
    default: ThisType
    allow_none: bool
    min: ThisType
    max: ThisType

    def validate(self, value, owner: Incomplete | None=...):
        ...
    path_attr: Any
    index_lookup_attr: Any
    table_index_column: str

    def calibrate_from_table(
        self,
        path_attr: Unicode,
        index_lookup_attr: ParamAttr,
        *,
        table_index_column: str=...,
        help: str=...,
        label=...,
        allow_none: bool=...
    ):
        ...

    def calibrate_from_expression(
        self,
        attr_expression: ParamAttr,
        help: str=...,
        label: str=...,
        allow_none: bool=...
    ):
        ...

    def transform(
        self,
        other_attr: ParamAttr,
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
        default: object=None,
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[]
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
        arguments: Dict=[],
        min: int=None,
        max: int=None,
        path_attr=None,
        index_lookup_attr=None,
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
        arguments: Dict=[],
        min: float=None,
        max: float=None,
        path_attr=None,
        index_lookup_attr=None,
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
        arguments: Dict=[]
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
        arguments: Dict=[]
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
        arguments: Dict=[],
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
        arguments: Dict=[],
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
        arguments: Dict=[],
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
        arguments: Dict=[]
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
        arguments: Dict=[]
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
        arguments: Dict=[]
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
        arguments: Dict=[]
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
        arguments: Dict=[],
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
        arguments: Dict=[],
        case: bool=True,
        accept_port: bool=True
    ):
        ...
    accept_port: bool

    def validate(self, value, owner: Incomplete | None=...):
        ...
VALID_PARAMATTR_ROLES: Incomplete

def subclass_namespace_attrs(namespace_dict, role, omit_param_attrs) -> None:
    ...
