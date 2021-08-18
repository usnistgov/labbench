from . import util, value as value
from ._traits import HasTraits
from typing import Any, Optional

def list_devices(depth: int = ...): ...

class DisconnectedBackend:
    name: Any = ...
    def __init__(self, dev: Any) -> None: ...
    def __getattr__(self, key: Any) -> None: ...
    def __copy__(self, memo: Optional[Any] = ...): ...
    str: Any = ...
    __deepcopy__: Any = ...

class Device(HasTraits, util.Ownable):
    def __init__(self, resource: str = "str"): ...
    resource: Any = ...
    concurrency: Any = ...
    backend: Any = ...
    def open(self) -> None: ...
    def close(self) -> None: ...
    __children__: Any = ...
    @classmethod
    def __init_subclass__(cls, **value_defaults: Any) -> None: ...
    def __open_wrapper__(self) -> None: ...
    def __close_wrapper__(self) -> None: ...
    @classmethod
    def __imports__(cls) -> None: ...
    def __enter__(self): ...
    def __exit__(self, type_: Any, value: Any, traceback: Any) -> None: ...
    def __del__(self) -> None: ...
    def isopen(self): ...