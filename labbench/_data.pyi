import io
from . import _device as core, util as util, value as value
from ._device import Device as Device
from ._rack import Owner as Owner, Rack as Rack
from ._traits import Trait as Trait, observe as observe
from collections.abc import Generator
from contextlib import ExitStack as ExitStack
from re import L as L
from typing import Any

EMPTY: Any
INSPECT_SKIP_FILES: Any

class MungerBase(core.Device):
    def __init__(
        self,
        resource: str = "WindowsPath",
        text_relational_min: str = "int",
        force_relational: str = "list",
        dirname_fmt: str = "str",
        nonscalar_file_type: str = "str",
        metadata_dirname: str = "str",
    ): ...
    resource: Any
    text_relational_min: Any
    force_relational: Any
    dirname_fmt: Any
    nonscalar_file_type: Any
    metadata_dirname: Any
    def __call__(self, index, row): ...
    def save_metadata(self, name, key_func, **extra): ...

class MungeToDirectory(MungerBase):
    def __init__(
        self,
        resource: str = "WindowsPath",
        text_relational_min: str = "int",
        force_relational: str = "list",
        dirname_fmt: str = "str",
        nonscalar_file_type: str = "str",
        metadata_dirname: str = "str",
    ): ...
    ...

class TarFileIO(io.BytesIO):
    tarfile: Any
    overwrite: bool
    name: Any
    mode: Any
    def __init__(
        self, open_tarfile, relname, mode: str = ..., overwrite: bool = ...
    ) -> None: ...
    def __del__(self) -> None: ...
    def close(self) -> None: ...

class MungeToTar(MungerBase):
    def __init__(
        self,
        resource: str = "WindowsPath",
        text_relational_min: str = "int",
        force_relational: str = "list",
        dirname_fmt: str = "str",
        nonscalar_file_type: str = "str",
        metadata_dirname: str = "str",
    ): ...
    tarname: str
    tarfile: Any
    def open(self) -> None: ...
    def close(self) -> None: ...

class Aggregator(util.Ownable):
    name_map: Any
    trait_rules: Any
    metadata: Any
    def __init__(self, persistent_state: bool = ...) -> None: ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
    def get(self) -> dict: ...
    def key(self, device_name, state_name): ...
    def set_device_labels(self, **mapping) -> None: ...
    def observe(self, devices, changes: bool = ..., always=..., never=...) -> None: ...

class RelationalTableLogger(Owner, util.Ownable):
    index_label: str
    aggregator: Any
    host: Any
    munge: Any
    pending: Any
    path: Any
    def __init__(
        self,
        path: Any | None = ...,
        *,
        append: bool = ...,
        text_relational_min: int = ...,
        force_relational=...,
        dirname_fmt: str = ...,
        nonscalar_file_type: str = ...,
        metadata_dirname: str = ...,
        tar: bool = ...,
        git_commit_in: Any | None = ...,
        persistent_state: bool = ...
    ) -> None: ...
    def __copy__(self): ...
    def __owner_init__(self, owner) -> None: ...
    def observe(self, devices, changes: bool = ..., always=..., never=...) -> None: ...
    def set_row_preprocessor(self, func): ...
    def new_row(self, *args, **kwargs) -> None: ...
    def write(self) -> None: ...
    def context(self, *args, **kws) -> Generator[(Any, None, None)]: ...
    def clear(self) -> None: ...
    def set_relational_file_format(self, format) -> None: ...
    def set_path_format(self, format) -> None: ...
    last_index: int
    def open(self): ...
    def close(self) -> None: ...

class CSVLogger(RelationalTableLogger):
    root_file: str
    nonscalar_file_type: str
    df: Any
    def open(self) -> None: ...
    def close(self) -> None: ...

class MungeToHDF(Device):
    def __init__(self, resource: str = "WindowsPath", key_fmt: str = "str"): ...
    resource: Any
    key_fmt: Any
    backend: Any
    def open(self) -> None: ...
    def close(self) -> None: ...
    def __call__(self, index, row): ...
    def save_metadata(self, name, key_func, **extra): ...

class HDFLogger(RelationalTableLogger):
    nonscalar_file_type: str
    munge: Any
    def __init__(
        self,
        path,
        *,
        append: bool = ...,
        key_fmt: str = ...,
        git_commit_in: Any | None = ...,
        persistent_state: bool = ...
    ) -> None: ...
    df: Any
    def open(self) -> None: ...
    def close(self) -> None: ...

class SQLiteLogger(RelationalTableLogger):
    index_label: str
    root_filename: str
    table_name: str
    inprogress: Any
    committed: Any
    last_index: int
    def open(self) -> None: ...
    def close(self) -> None: ...
    def key(self, name, attr): ...

def to_feather(data, path) -> None: ...
def read_sqlite(
    path,
    table_name: str = ...,
    columns: Any | None = ...,
    nrows: Any | None = ...,
    index_col=...,
): ...
def read(
    path_or_buf,
    columns: Any | None = ...,
    nrows: Any | None = ...,
    format: str = ...,
    **kws
): ...

class MungeTarReader:
    tarnames: Any
    tarfile: Any
    def __init__(self, path, tarname: str = ...) -> None: ...
    def __call__(self, key, *args, **kws): ...

class MungeDirectoryReader:
    path: Any
    def __init__(self, path) -> None: ...
    def __call__(self, key, *args, **kws): ...

class MungeReader:
    def __new__(cls, path): ...

def read_relational(
    path,
    expand_col,
    root_cols: Any | None = ...,
    target_cols: Any | None = ...,
    root_nrows: Any | None = ...,
    root_format: str = ...,
    prepend_column_name: bool = ...,
) -> Generator[(None, None, Any)]: ...
