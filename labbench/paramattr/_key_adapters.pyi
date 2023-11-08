from . import argument as argument
from ._bases import (
    HasParamAttrs as HasParamAttrs,
    KeyAdapterBase as KeyAdapterBase,
    ParamAttr as ParamAttr,
    Undefined as Undefined,
)
from _typeshed import Incomplete
from functools import partialmethod as partialmethod
from typing import Any, Dict, List


class message_keying(KeyAdapterBase):
    query_fmt: Incomplete
    write_fmt: Incomplete
    write_func: Incomplete
    query_func: Incomplete
    value_map: Incomplete
    message_map: Incomplete

    def __init__(
        self,
        *,
        query_fmt: Incomplete | None=...,
        write_fmt: Incomplete | None=...,
        write_func: Incomplete | None=...,
        query_func: Incomplete | None=...,
        remap=...,
        arguments: Dict[Any, ParamAttr]=...,
        strict_arguments: bool=...
    ) -> None:
        ...

    def get_key_arguments(self, s: str) -> List[str]:
        ...

    def from_message(self, msg):
        ...

    def to_message(self, value):
        ...

    def get(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        paramattr: ParamAttr=...,
        arguments: Dict[str, Any]=...
    ):
        ...

    def set(
        self,
        owner: HasParamAttrs,
        scpi_key: str,
        value,
        attr: ParamAttr=...,
        arguments: Dict[str, Any]=...
    ):
        ...


class visa_keying(message_keying):

    def __init__(
        self,
        *,
        query_fmt: str=...,
        write_fmt: str=...,
        remap=...,
        arguments: Dict[str, ParamAttr]=...
    ) -> None:
        ...
