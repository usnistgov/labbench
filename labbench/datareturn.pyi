from . import _traits


class bool(_traits.Bool):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False
    ):
        ...
    ...


class float(_traits.Float):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=True,
        min: str=None,
        max: str=None,
        path_trait: str=None,
        index_lookup_trait: str=None,
        table_index_column: str=None,
        step: str=None
    ):
        ...
    ...


class int(_traits.Int):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=True,
        min: str=None,
        max: str=None,
        path_trait: str=None,
        index_lookup_trait: str=None,
        table_index_column: str=None
    ):
        ...
    ...


class complex(_traits.Complex):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False
    ):
        ...
    ...


class str(_traits.Unicode):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False,
        case: str=True
    ):
        ...
    ...


class bytes(_traits.Bytes):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False,
        case: str=True
    ):
        ...
    ...


class list(_traits.List):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False
    ):
        ...
    ...


class tuple(_traits.Tuple):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=False,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False
    ):
        ...
    ...


class dict(_traits.Dict):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False
    ):
        ...
    ...


class Path(_traits.Path):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False,
        must_exist: str=False
    ):
        ...
    ...


class NetworkAddress(_traits.NetworkAddress):

    def __init__(
        func: str=None,
        help: str='',
        label: str='',
        sets: str=True,
        gets: str=True,
        cache: str=False,
        only: str=(),
        allow_none: str=False,
        case: str=True,
        accept_port: str=True
    ):
        ...
    ...
