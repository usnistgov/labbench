from . import _traits
from _typeshed import Incomplete

class message_keying(_traits.PropertyKeyingBase):
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
        self, device: _traits.HasTraits, scpi_key: str, trait: Incomplete | None = ...
    ): ...
    def set(
        self,
        device: _traits.HasTraits,
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

class bool(_traits.Bool):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
    ): ...
    ...

class float(_traits.Float):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        recheck: bool = False,
        min: float = None,
        max: float = None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
        step: float = None,
    ): ...
    ...

class int(_traits.Int):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        recheck: bool = False,
        min: int = None,
        max: int = None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
    ): ...
    ...

class complex(_traits.Complex):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
    ): ...
    ...

class str(_traits.Unicode):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
        case: bool = True,
    ): ...
    ...

class bytes(_traits.Bytes):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
        case: bool = True,
    ): ...
    ...

class list(_traits.List):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
    ): ...
    ...

class tuple(_traits.Tuple):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = False,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
    ): ...
    ...

class dict(_traits.Dict):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
    ): ...
    ...

class Path(_traits.Path):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
        must_exist: bool = False,
    ): ...
    ...

class NetworkAddress(_traits.NetworkAddress):
    def __init__(
        key=None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        recheck: bool = False,
        case: bool = True,
        accept_port: bool = True,
    ): ...
    ...
