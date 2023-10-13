from . import _api
from _typeshed import Incomplete

class message_keying(_api.PropertyKeyingBase):
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
    def get(
        self, device: _api.HasTraits, scpi_key: str, trait: Incomplete | None = ...
    ): ...
    def set(
        self,
        device: _api.HasTraits,
        scpi_key: str,
        value,
        trait: Incomplete | None = ...,
    ): ...

class visa_keying(message_keying):
    def __init__(
        self,
        query_fmt: str = ...,
        write_fmt: str = ...,
        write_func: str = ...,
        query_func: str = ...,
        remap=...,
    ) -> None: ...

class bool(_api.Bool):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class float(_api.Float):
    def __init__(
        key=None,
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
    ...

class int(_api.Int):
    def __init__(
        key=None,
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

class complex(_api.Complex):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class str(_api.Unicode):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        case: str = True,
    ): ...
    ...

class bytes(_api.Bytes):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        case: str = True,
    ): ...
    ...

class list(_api.List):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class tuple(_api.Tuple):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = False,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class dict(_api.Dict):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class Path(_api.Path):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
        must_exist: str = False,
    ): ...
    ...

class NetworkAddress(_api.NetworkAddress):
    def __init__(
        key=None,
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
    ...
