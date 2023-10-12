from . import _traits

class any(_traits.Any):
    def __init__(
        default=None,
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

class bool(_traits.Bool):
    def __init__(
        default: bool = None,
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
        default: float = None,
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
        default: int = None,
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
        default: complex = None,
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
        default: str = "",
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
        default: bytes = b"",
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
        default: list = None,
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
        default: tuple = None,
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
        default: dict = None,
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
        default: Path = None,
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
        default: str = "",
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
