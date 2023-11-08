from . import _bases


class bool(_bases.Bool):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[]
    ):
        ...
    ...


class float(_bases.Float):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        arguments: Dict=[],
        min: float=None,
        max: float=None,
        path_attr=None,
        index_lookup_attr=None,
        table_index_column: str=None,
        step: float=None
    ):
        ...
    ...


class int(_bases.Int):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        arguments: Dict=[],
        min: int=None,
        max: int=None,
        path_attr=None,
        index_lookup_attr=None,
        table_index_column: str=None
    ):
        ...
    ...


class complex(_bases.Complex):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[]
    ):
        ...
    ...


class str(_bases.Unicode):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[],
        case: bool=True
    ):
        ...
    ...


class bytes(_bases.Bytes):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[],
        case: bool=True
    ):
        ...
    ...


class list(_bases.List):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[]
    ):
        ...
    ...


class tuple(_bases.Tuple):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=False,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[]
    ):
        ...
    ...


class dict(_bases.Dict):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[]
    ):
        ...
    ...


class Path(_bases.Path):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[],
        must_exist: bool=False
    ):
        ...
    ...


class NetworkAddress(_bases.NetworkAddress):

    def __init__(
        key=None,
        argname: Optional=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        arguments: Dict=[],
        case: bool=True,
        accept_port: bool=True
    ):
        ...
    ...
