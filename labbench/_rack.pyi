import inspect
from . import util as util
from pathlib import Path as Path
from typing import Any, Optional
EMPTY: Any

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

    def extended_signature(self):
        ...

    def extended_argname_names(self):
        ...

    def extended_argname_call(self, *args: Any, **kws: Any):
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

def flatten_nested_owner_contexts(top: Any) -> dict:
    ...

def package_owned_contexts(top: Any):
    ...

def owner_getattr_chains(owner: Any):
    ...


class Owner():

    def __init_subclass__(cls: Any, entry_order: list=...) -> Any:
        ...

    def __init__(self, **update_ownables: Any) -> None:
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

def override_empty(a: Any, b: Any, param_name: Any, field: Any):
    ...

def update_parameter_dict(dest: dict, signature: inspect.Signature) -> Any:
    ...

def attr_chain_to_method(root_obj: Any, chain: Any):
    ...

def standardize_spec_step(sequence: Any):
    ...


class Sequence(util.Ownable):
    spec: Any = ...
    access_spec: Any = ...

    def __init__(self, **specification: Any) -> None:
        ...

    def __owner_subclass__(self, owner_cls: Any):
        ...
    last_spec: Any = ...

    def __owner_init__(self, owner: Any) -> None:
        ...


class RackMeta(type):

    def __enter__(cls) -> None:
        ...

    def __exit__(cls, *exc_info: Any) -> None:
        ...


class Rack(Owner, util.Ownable, metaclass=RackMeta):

    def __init__():
        ...

    def __init_subclass__(cls, entry_order: Any=...) -> None:
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

def import_as_rack(import_str: str, cls_name: str=..., base_cls: type=..., replace_attrs: list=...) -> Any:
    ...
