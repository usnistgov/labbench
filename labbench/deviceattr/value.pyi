from . import _api

class any(_api.Any):
    def __init__(
        default: str = None,
        help: str = "",
        label: str = "",
        sets: str = True,
        gets: str = True,
        cache: str = False,
        only: str = (),
        allow_none: str = False,
    ): ...
    ...

class bool(_api.Bool):
    def __init__(
        default: str = None,
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
        default: str = None,
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
        default: str = None,
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
        default: str = None,
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
        default: str = "",
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
        default: str = b"",
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
        default: str = None,
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
        default: str = None,
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
        default: str = None,
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
        default: str = None,
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
        default: str = "",
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
