from . import _bases

class bool(_bases.Bool):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
    ): ...
    ...

class float(_bases.Float):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        argchecks: List = [],
        min: float = None,
        max: float = None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
        step: float = None,
    ): ...
    ...

class int(_bases.Int):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = True,
        argchecks: List = [],
        min: int = None,
        max: int = None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str = None,
    ): ...
    ...

class complex(_bases.Complex):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
    ): ...
    ...

class str(_bases.Unicode):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
        case: bool = True,
    ): ...
    ...

class bytes(_bases.Bytes):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
        case: bool = True,
    ): ...
    ...

class list(_bases.List):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
    ): ...
    ...

class tuple(_bases.Tuple):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = False,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
    ): ...
    ...

class dict(_bases.Dict):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
    ): ...
    ...

class Path(_bases.Path):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
        must_exist: bool = False,
    ): ...
    ...

class NetworkAddress(_bases.NetworkAddress):
    def __init__(
        key=None,
        argname: Optional = None,
        help: str = "",
        label: str = "",
        sets: bool = True,
        gets: bool = True,
        cache: bool = False,
        only: tuple = (),
        allow_none: bool = False,
        argchecks: List = [],
        case: bool = True,
        accept_port: bool = True,
    ): ...
    ...
