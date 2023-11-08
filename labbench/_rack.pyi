import inspect
from . import util as util
from _typeshed import Incomplete
from collections.abc import Generator
EMPTY: Incomplete

def null_context(owner) -> Generator[Incomplete, None, None]:
    ...


class NeverRaisedException(BaseException):
    ...


class notify():

    @classmethod
    def clear(cls) -> None:
        ...

    @classmethod
    def hold_owner_notifications(cls, *owners) -> None:
        ...

    @classmethod
    def allow_owner_notifications(cls, *owners) -> None:
        ...

    @classmethod
    def return_event(cls, owner, returned: dict):
        ...

    @classmethod
    def call_event(cls, owner, parameters: dict):
        ...

    @classmethod
    def call_iteration_event(cls, owner, index: int, step_name: str=..., total_count: int=...):
        ...

    @classmethod
    def observe_returns(cls, handler) -> None:
        ...

    @classmethod
    def observe_calls(cls, handler) -> None:
        ...

    @classmethod
    def observe_call_iteration(cls, handler) -> None:
        ...

    @classmethod
    def unobserve_returns(cls, handler) -> None:
        ...

    @classmethod
    def unobserve_calls(cls, handler) -> None:
        ...

    @classmethod
    def unobserve_call_iteration(cls, handler) -> None:
        ...


class CallSignatureTemplate():
    target: Incomplete

    def __init__(self, target) -> None:
        ...

    def get_target(self, owner):
        ...

    def get_keyword_parameters(self, owner, skip_names):
        ...


class MethodTaggerDataclass():
    pending: Incomplete

    def __call__(self, func):
        ...


class rack_input_table(MethodTaggerDataclass):
    table_path: str

    def __init__(self, table_path) -> None:
        ...


class rack_kwargs_template(MethodTaggerDataclass):
    template: callable

    def __init__(self, template) -> None:
        ...


class rack_kwargs_skip(MethodTaggerDataclass):
    skip: list

    def __init__(self, *arg_names) -> None:
        ...


class RackMethod(util.Ownable):
    tags: Incomplete
    __doc__: Incomplete
    __name__: Incomplete
    __qualname__: Incomplete

    def __init__(self, owner, name: str, kwdefaults: dict=...) -> None:
        ...

    def iterate_from_csv(self, path) -> Generator[Incomplete, None, None]:
        ...
    debug: Incomplete

    @classmethod
    def from_method(self, method):
        ...

    def __copy__(self):
        ...

    def __deepcopy__(self, memo: Incomplete | None=...):
        ...

    def __owner_subclass__(self, owner_cls) -> None:
        ...

    def set_kwdefault(self, name, new_default) -> None:
        ...

    def extended_signature(self, name_map=...):
        ...

    def extended_arguments(self, name_map=...):
        ...

    def call_by_extended_argnames(self, *args, **kws):
        ...

    def __call__(self, *args, **kws):
        ...


class BoundSequence(util.Ownable):
    cleanup_func: Incomplete
    exception_allowlist = NeverRaisedException

    def __call__(self, **kwargs):
        ...

    @classmethod
    def to_template(cls, path) -> None:
        ...

    def iterate_from_csv(self, path) -> Generator[Incomplete, None, None]:
        ...


class OwnerContextAdapter():

    def __init__(self, owner) -> None:
        ...

    def __enter__(self) -> None:
        ...

    def __exit__(self, *exc_info) -> None:
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

    def __propagate_ownership__(self) -> None:
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

def recursive_devices(top: Owner):
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
    access_spec: Incomplete
    cleanup_func: Incomplete
    exception_allowlist = NeverRaisedException
    spec: Incomplete
    tags: Incomplete

    def __init__(self, *specification, shared_names=..., input_table: Incomplete | None=...) -> None:
        ...

    def return_on_exceptions(self, exception_or_exceptions, cleanup_func: Incomplete | None=...) -> None:
        ...

    def __owner_subclass__(self, owner_cls):
        ...
    last_spec: Incomplete

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

    def __deepcopy__(self, memo: Incomplete | None=...):
        ...

    def __owner_init__(self, owner) -> None:
        ...

    def __getattribute__(self, item):
        ...

    def __getitem__(self, item):
        ...

    def __len__(self) -> int:
        ...

    def __iter__(self):
        ...


class _use_module_path():
    path: Incomplete

    def __init__(self, path) -> None:
        ...

    def __enter__(self) -> None:
        ...

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        ...

def import_as_rack(
    import_string: str,
    *,
    cls_name: str=...,
    append_path: list=...,
    base_cls: type=...,
    replace_attrs: list=...
):
    ...

def find_owned_rack_by_type(parent_rack: Rack, target_type: Rack, include_parent: bool=...):
    ...
