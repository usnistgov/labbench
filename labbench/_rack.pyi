from . import util as util
from importlib import import_module as import_module
from ruamel_yaml import round_trip_load as round_trip_load
from typing import Any, Optional
yaml: Any
EMPTY: Any
BASIC_TYPES: Any

def null_context(owner: Any) -> None:
    ...


class notify():

    @classmethod
    def clear(cls) -> None:
        ...

    @classmethod
    def return_event(cls: Any, returned: dict) -> Any:
        ...

    @classmethod
    def call_event(cls: Any, parameters: dict) -> Any:
        ...

    @classmethod
    def observe_returns(cls, handler: Any) -> None:
        ...

    @classmethod
    def observe_calls(cls, handler: Any) -> None:
        ...

    @classmethod
    def unobserve_returns(cls, handler: Any) -> None:
        ...

    @classmethod
    def unobserve_calls(cls, handler: Any) -> None:
        ...


class Method(util.Ownable):
    __doc__: Any = ...
    __name__: Any = ...
    __qualname__: Any = ...

    def __init__(self, owner: Any, name: Any, kwdefaults: Any=...):
        ...

    @classmethod
    def from_method(self, method: Any):
        ...

    def __copy__(self):
        ...

    def __deepcopy__(self, memo: Optional[Any]=...):
        ...

    def set_kwdefault(self, name: Any, value: Any) -> None:
        ...

    def long_kwarg_signature(self):
        ...

    def long_kwarg_names(self):
        ...

    def long_kwarg_call(self, *args: Any, **kws: Any):
        ...

    def __call__(self, *args: Any, **kws: Any):
        ...


class BoundSequence(util.Ownable):

    def __call__(self, **kwargs: Any):
        ...

    @classmethod
    def to_template(cls, path: Any) -> None:
        ...
    results: Any = ...

    def iterate_from_csv(self, path: Any) -> None:
        ...


class OwnerContextAdapter():

    def __init__(self, owner: Any) -> None:
        ...

    def __enter__(self) -> None:
        ...

    def __exit__(self, *exc_info: Any) -> None:
        ...

def recursive_devices(top: Any):
    ...

def recursive_owner_managers(top: Any):
    ...

def owner_context_manager(top: Any):
    ...

def propagate_instnames(parent_obj: Any, parent_name: Optional[Any]=...) -> None:
    ...

def owner_getattr_chains(owner: Any):
    ...


class Owner():

    def __init_subclass__(cls: Any, ordered_entry: list=...) -> Any:
        ...

    def __meta_owner_init__(self, parent_name: Any) -> None:
        ...

    def __init__(self, **devices: Any) -> None:
        ...

    def __setattr__(self, key: Any, obj: Any) -> None:
        ...

    def close(self) -> None:
        ...

    def open(self) -> None:
        ...

    @property
    def __enter__(self):
        ...

    @property
    def __exit__(self):
        ...

def __call__():
    ...


class Sequence(util.Ownable):
    spec: Any = ...
    access_spec: Any = ...

    def __init__(self, **specification: Any):
        ...

    def __owner_subclass__(self, owner_cls: Any):
        ...
    last_spec: Any = ...

    def __owner_init__(self, owner: Any):
        ...


class RackMeta(type):
    CONFIG_FILENAME: str = ...

    @classmethod
    def from_module(metacls: Any, module_str: Any, cls_name: Any):
        ...

    def wrap_module(cls, module: Any):
        ...

    @classmethod
    def from_config(metacls: Any, config_path: Any, apply: bool=...):
        ...

    @classmethod
    def to_config(metacls: Any, cls: Any, path: Any, with_defaults: bool=...) -> None:
        ...

    def to_sequence_table(cls, name: Any, path: Any, with_defaults: bool=...) -> None:
        ...

    def __enter__(cls) -> None:
        ...

    def __exit__(cls, *exc_info: Any) -> None:
        ...


class Rack(Owner, util.Ownable, metaclass=RackMeta):

    def __init__():
        ...

    def __init_subclass__(cls, ordered_entry: Any=...) -> None:
        ...

    def __deepcopy__(self, memo: Optional[Any]=...):
        ...

    def __owner_init__(self, owner: Any) -> None:
        ...

    def __getattribute__(self, item: Any):
        ...

    def __getitem__(self, item: Any):
        ...

    def __len__(self):
        ...

    def __iter__(self) -> Any:
        ...
CONFIG_FILENAME: str
