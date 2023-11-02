from . import util
from .paramattr._bases import HasParamAttrs
from _typeshed import Incomplete

def list_devices(depth: int = ...): ...

class DisconnectedBackend:
    name: Incomplete

    def __init__(self, dev) -> None: ...
    def __getattr__(self, key) -> None: ...
    def __copy__(self, memo: Incomplete | None = ...): ...
    str: Incomplete
    __deepcopy__ = __copy__

class Device(HasParamAttrs, util.Ownable):
    def __init__(self, resource: str = "str"): ...
    resource: Incomplete
    concurrency: Incomplete
    backend: Incomplete

    def open(self) -> None: ...
    def close(self) -> None: ...
    __children__: Incomplete

    @classmethod
    def __init_subclass__(cls) -> None: ...
    @classmethod
    def __update_signature__(cls) -> None: ...
    def __open_wrapper__(self) -> None: ...
    def __close_wrapper__(self) -> None: ...
    def __enter__(self): ...
    def __exit__(self, type_, value, traceback) -> None: ...
    def __del__(self) -> None: ...
    def isopen(self): ...

def trait_info(device: Device, name: str) -> dict: ...
