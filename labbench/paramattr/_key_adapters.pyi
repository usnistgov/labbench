from ._bases import (
    HasParamAttrs as HasParamAttrs,
    KeyAdapterBase as KeyAdapterBase,
    ParamAttr as ParamAttr,
    Undefined as Undefined,
)
from _typeshed import Incomplete
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
        query_fmt: Incomplete | None = ...,
        write_fmt: Incomplete | None = ...,
        write_func: Incomplete | None = ...,
        query_func: Incomplete | None = ...,
        remap=...,
    ) -> None: ...
    @classmethod
    def get_key_arguments(cls, s: str) -> List[str]: ...
    def from_message(self, msg): ...
    def to_message(self, value): ...
    def get(
        self,
        device: HasParamAttrs,
        scpi_key: str,
        trait: Incomplete | None = ...,
        arguments: Dict[str, Any] = ...,
    ): ...
    def set(
        self,
        device: HasParamAttrs,
        scpi_key: str,
        value,
        trait: Incomplete | None = ...,
        arguments: Dict[str, Any] = ...,
    ): ...
    def method_from_key(self, device: HasParamAttrs, trait: ParamAttr): ...

class visa_keying(message_keying):
    def __init__(self, query_fmt: str = ..., write_fmt: str = ..., remap=...) -> None: ...
