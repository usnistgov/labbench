from . import _bases


class any(_bases.Any):

    def __init__(
        default=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False
    ):
        ...
    ...


class bool(_bases.Bool):

    def __init__(
        default: bool=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False
    ):
        ...
    ...


class float(_bases.Float):

    def __init__(
        default: float=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        min: float=None,
        max: float=None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str=None,
        step: float=None
    ):
        ...
    ...


class int(_bases.Int):

    def __init__(
        default: int=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        min: int=None,
        max: int=None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str=None
    ):
        ...
    ...


class complex(_bases.Complex):

    def __init__(
        default: complex=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False
    ):
        ...
    ...


class str(_bases.Unicode):

    def __init__(
        default: str='',
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        case: bool=True
    ):
        ...
    ...


class bytes(_bases.Bytes):

    def __init__(
        default: bytes=b'',
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        case: bool=True
    ):
        ...
    ...


class list(_bases.List):

    def __init__(
        default: list=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False
    ):
        ...
    ...


class tuple(_bases.Tuple):

    def __init__(
        default: tuple=None,
        help: str='',
        label: str='',
        sets: bool=False,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False
    ):
        ...
    ...


class dict(_bases.Dict):

    def __init__(
        default: dict=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False
    ):
        ...
    ...


class Path(_bases.Path):

    def __init__(
        default: Path=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        must_exist: bool=False
    ):
        ...
    ...


class NetworkAddress(_bases.NetworkAddress):

    def __init__(
        default: str='',
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        case: bool=True,
        accept_port: bool=True
    ):
        ...
    ...
