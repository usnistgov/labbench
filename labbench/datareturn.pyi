from . import _traits


class bool(_traits.Bool):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={}
    ):
        ...
    ...


class float(_traits.Float):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        remap: dict={},
        min: float=None,
        max: float=None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str=None,
        step: float=None
    ):
        ...
    ...


class int(_traits.Int):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=True,
        remap: dict={},
        min: int=None,
        max: int=None,
        path_trait=None,
        index_lookup_trait=None,
        table_index_column: str=None
    ):
        ...
    ...


class complex(_traits.Complex):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={}
    ):
        ...
    ...


class str(_traits.Unicode):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={},
        case: bool=True
    ):
        ...
    ...


class bytes(_traits.Bytes):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={},
        case: bool=True
    ):
        ...
    ...


class list(_traits.List):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={}
    ):
        ...
    ...


class tuple(_traits.Tuple):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=False,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={}
    ):
        ...
    ...


class dict(_traits.Dict):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={}
    ):
        ...
    ...


class Path(_traits.Path):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={},
        must_exist: bool=False
    ):
        ...
    ...


class NetworkAddress(_traits.NetworkAddress):

    def __init__(
        func: _CallableType=None,
        help: str='',
        label: str='',
        sets: bool=True,
        gets: bool=True,
        cache: bool=False,
        only: tuple=(),
        allow_none: bool=False,
        remap: dict={},
        case: bool=True,
        accept_port: bool=True
    ):
        ...
    ...
