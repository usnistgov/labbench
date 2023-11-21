from . import _types
from . import _bases
import typing as _typing
from ._bases import TDecoratedMethod as _TDecoratedMethod
from ._bases import TKeyedMethod as _TKeyedMethod


class any(_bases.Method, _types.Any):

    @_typing.overload
    def __new__(
        cls,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class bool(_bases.Method, _types.Bool):

    @_typing.overload
    def __new__(
        cls,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class float(_bases.Method, _types.Float):

    @_typing.overload
    def __new__(
        cls,
        step: Optional=None,
        max: Optional=None,
        min: Optional=None,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        step: Optional=None,
        max: Optional=None,
        min: Optional=None,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class int(_bases.Method, _types.Int):

    @_typing.overload
    def __new__(
        cls,
        max: Optional=None,
        min: Optional=None,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        max: Optional=None,
        min: Optional=None,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class complex(_bases.Method, _types.Complex):

    @_typing.overload
    def __new__(
        cls,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class str(_bases.Method, _types.Unicode):

    @_typing.overload
    def __new__(
        cls,
        case: bool=True,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        case: bool=True,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class bytes(_bases.Method, _types.Bytes):

    @_typing.overload
    def __new__(
        cls,
        case: bool=True,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        case: bool=True,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class list(_bases.Method, _types.List):

    @_typing.overload
    def __new__(
        cls,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class tuple(_bases.Method, _types.Tuple):

    @_typing.overload
    def __new__(
        cls,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=False,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=False,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class dict(_bases.Method, _types.Dict):

    @_typing.overload
    def __new__(
        cls,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class Path(_bases.Method, _types.Path):

    @_typing.overload
    def __new__(
        cls,
        must_exist: bool=False,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        must_exist: bool=False,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass


class NetworkAddress(_bases.Method, _types.NetworkAddress):

    @_typing.overload
    def __new__(
        cls,
        accept_port: bool=True,
        case: bool=True,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TDecoratedMethod:
        ...

    @_typing.overload
    def __new__(
        cls,
        key,
        accept_port: bool=True,
        case: bool=True,
        allow_none: bool=False,
        only: tuple=(),
        cache: bool=False,
        gets: bool=True,
        sets: bool=True,
        label: str='',
        help: str=''
    ) -> _bases.TKeyedMethod:
        ...
    pass
