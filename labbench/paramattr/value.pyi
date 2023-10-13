from . import _bases

class any(_bases.Any):
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

class bool(_bases.Bool):
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

class float(_bases.Float):
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

class int(_bases.Int):
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

class complex(_bases.Complex):
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

class str(_bases.Unicode):
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

class bytes(_bases.Bytes):
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

class list(_bases.List):
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

class tuple(_bases.Tuple):
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

class dict(_bases.Dict):
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

class Path(_bases.Path):
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

class NetworkAddress(_bases.NetworkAddress):
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
