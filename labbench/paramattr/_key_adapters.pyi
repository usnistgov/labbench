from . import argument as argument
from ._bases import (
    HasParamAttrs as HasParamAttrs,
    KeyAdapterBase as KeyAdapterBase,
    ParamAttr as ParamAttr,
    Undefined as Undefined,
)
from _typeshed import Incomplete
from functools import partialmethod as partialmethod
from typing import Any, Dict, List, Type

class no_cast_argument:
    @classmethod
    def __cast_get__(self, owner, value): ...

class message_keying(KeyAdapterBase):
    query_fmt: Incomplete
    write_fmt: Incomplete
    write_func: Incomplete
    query_func: Incomplete
    arguments: Incomplete
    strict_arguments: Incomplete
    value_map: Incomplete
    message_map: Incomplete

    def __init__(
        self,
        *,
        query_fmt: Incomplete | None = ...,
        write_fmt: Incomplete | None = ...,
        write_func: Incomplete | None = ...,
        query_func: Incomplete | None = ...,
        remap=...,
        arguments: Dict[Any, ParamAttr] = ...,
        strict_arguments: bool = ...,
    ) -> None: ...
    @classmethod
    def get_key_arguments(cls, s: str) -> List[str]: ...
    def from_message(self, msg): ...
    def to_message(self, value): ...
    def get(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        paramattr: ParamAttr = ...,
        arguments: Dict[str, Any] = ...,
    ): ...
    def set(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        value,
        paramattr: ParamAttr = ...,
        arguments: Dict[str, Any] = ...,
    ): ...
    def method_from_key(self, owner_cls: Type[HasParamAttrs], trait: ParamAttr): ...

class visa_keying(message_keying):
    def __init__(
        self,
        *,
        query_fmt: str = ...,
        write_fmt: str = ...,
        remap=...,
        arguments: Dict[str, ParamAttr] = ...,
    ) -> None: ...
