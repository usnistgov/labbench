import inspect
from . import util as util
from collections.abc import Generator
from functools import partial as partial
from pathlib import Path as Path
from typing import Any
EMPTY: Any

def null_context(owner) -> Generator[(Any, None, None)]:
    ...


class NeverRaisedException(BaseException):
    ...


class notify():

    @classmethod
    def clear(cls) -> None:
        ...

    @classmethod
    def return_event(cls, returned: dict):
        ...

    @classmethod
    def call_event(cls, parameters: dict):
        ...

    @classmethod
    def observe_returns(cls, handler) -> None:
        ...

    @classmethod
    def observe_calls(cls, handler) -> None:
        ...

    @classmethod
    def unobserve_returns(cls, handler) -> None:
        ...

    @classmethod
    def unobserve_calls(cls, handler) -> None:
        ...


class CallSignatureTemplate():
    target: Any

    def __init__(self, target) -> None:
        ...

    def get_target(self, owner):
        ...

    def get_keyword_parameters(self, owner, skip_names):
        ...


class MethodTaggerDataclass():
    pending: Any

    def __call__(self, func):
        ...


class table_input(MethodTaggerDataclass):
    input_table: Any
    pass_kwargs: callable
    skip: tuple


class RackMethod(util.Ownable):
    __doc__: Any
    __name__: Any
    __qualname__: Any

    def __init__(self, owner, name: str, kwdefaults: dict=...) -> None:
        ...
    debug: Any

    @classmethod
    def from_method(self, method):
        ...

    def __copy__(self):
        ...

    def __deepcopy__(self, memo: Any | None=...):
        ...

    def __owner_subclass__(self, owner_cls) -> None:
        ...

    def set_kwdefault(self, name, value) -> None:
        ...

    def extended_signature(self):
        ...

    def extended_arguments(self):
        ...

    def extended_argname_call(self, *args, **kws):
        ...

    def __call__(self, *args, **kws):
        ...


class BoundSequence(util.Ownable):
    INDEX_COLUMN_NAME: str
    cleanup_func: Any
    exception_allowlist: Any

    def __call__(self, **kwargs):
        ...

    @classmethod
    def to_template(cls, path) -> None:
        ...

    def iterate_from_csv(self, path) -> Generator[(Any, None, None)]:
        ...


class OwnerContextAdapter():

    def __init__(self, owner) -> None:
        ...

    def __enter__(self) -> None:
        ...

    def __exit__(self, *exc_info) -> None:
        ...

def recursive_devices(top):
    ...

def flatten_nested_owner_contexts(top) -> dict:
    ...

def package_owned_contexts(top):
    ...

def owner_getattr_chains(owner):
    ...


class Owner():

    def __init_subclass__(cls, entry_order: list=...):
        ...

    def __init__(self, **update_ownables) -> None:
        ...

    def __setattr__(self, key, obj) -> None:
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

def override_empty(a, b, param_name, field):
    ...

def update_parameter_dict(dest: dict, signature: inspect.Signature):
    ...

def attr_chain_to_method(root_obj, chain):
    ...

def standardize_spec_step(sequence):
    ...


class Sequence(util.Ownable):
    access_spec: Any
    cleanup_func: Any
    exception_allowlist: Any
    spec: Any

    def __init__(self, *specification) -> None:
        ...

    def return_on_exceptions(self, exception_or_exceptions, cleanup_func: Any | None=...) -> None:
        ...

    def __owner_subclass__(self, owner_cls):
        ...
    last_spec: Any

    def __owner_init__(self, owner) -> None:
        ...


class RackMeta(type):

    def __enter__(cls) -> None:
        ...

    def __exit__(cls, *exc_info) -> None:
        ...


class Rack(Owner, util.Ownable, metaclass=RackMeta):

    def __init__():
        ...

    def __init_subclass__(cls, entry_order=...) -> None:
        ...

    def __deepcopy__(self, memo: Any | None=...):
        ...

    def __owner_init__(self, owner) -> None:
        ...

    def __getattribute__(self, item):
        ...

    def __getitem__(self, item):
        ...

    def __len__(self):
        ...

    def __iter__(self):
        ...


class _use_module_path():
    path: Any

    def __init__(self, path) -> None:
        ...

    def __enter__(self) -> None:
        ...

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        ...

def import_as_rack(
    import_string: str,
    cls_name: str=...,
    append_path: list=...,
    base_cls: type=...,
    replace_attrs: list=...
):
    ...

def find_owned_rack_by_type(parent_rack: Rack, target_type: Rack, include_parent: bool=...):
    ...
