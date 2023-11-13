# type hint definitions for _bases.py

from typing import TypeVar, Callable, Protocol, Optional, Union, ParamSpec, overload
import inspect as _inspect
Undefined = _inspect.Parameter.empty

T = TypeVar('T')

class TKeyedMethodCallable(Protocol[T]):
    @overload
    def __call__(self, set_value: T, **arguments) -> None: ...
    @overload
    def __call__(self, **arguments) -> T: ...

    def __call__(self, set_value: Optional[T] = Undefined, **arguments) -> Union[None, T]:
        ...

class TDecoratorCallable(Protocol[T]):
    _P = ParamSpec('_P')

    def __call__(self, func: Callable[_P, T]) -> Callable[_P, T]:
        ...