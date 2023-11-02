import io
from . import _device as core, _host, util as util
from ._device import Device as Device
from ._rack import Owner as Owner, Rack as Rack
from .paramattr import observe as observe
from _typeshed import Incomplete
from collections.abc import Generator
from pathlib import Path
from typing import Dict, List, Union

h5py: Incomplete
np: Incomplete
pd: Incomplete
sqlalchemy: Incomplete
feather: Incomplete
EMPTY: Incomplete
INSPECT_SKIP_FILES: Incomplete

class MungerBase(core.Device):
    def __init__(
        self,
        resource: str = "WindowsPath",
        text_relational_min: str = "int",
        force_relational: str = "list",
        relational_name_fmt: str = "str",
        nonscalar_file_type: str = "str",
        metadata_dirname: str = "str",
    ): ...
    resource: Incomplete
    text_relational_min: Incomplete
    force_relational: Incomplete
    relational_name_fmt: Incomplete
    nonscalar_file_type: Incomplete
    metadata_dirname: Incomplete

    def __call__(self, index, row): ...
    def save_metadata(self, name, key_func, **extra): ...
    def open(self) -> None: ...

class MungeToDirectory(MungerBase):
    def __init__(
        self,
        resource: str = "WindowsPath",
        text_relational_min: str = "int",
        force_relational: str = "list",
        relational_name_fmt: str = "str",
        nonscalar_file_type: str = "str",
        metadata_dirname: str = "str",
    ): ...
    ...

class TarFileIO(io.BytesIO):
    tarfile: Incomplete
    overwrite: bool
    name: Incomplete
    mode: Incomplete

    def __init__(self, open_tarfile, relname, mode: str = ..., overwrite: bool = ...) -> None: ...
    def __del__(self) -> None: ...
    def close(self) -> None: ...

class MungeToTar(MungerBase):
    def __init__(
        self,
        resource: str = "WindowsPath",
        text_relational_min: str = "int",
        force_relational: str = "list",
        relational_name_fmt: str = "str",
        nonscalar_file_type: str = "str",
        metadata_dirname: str = "str",
    ): ...
    tarname: str
    tarfile: Incomplete

    def open(self) -> None: ...
    def close(self) -> None: ...

class Aggregator(util.Ownable):
    PERSISTENT_TRAIT_ROLES: Incomplete
    name_map: Incomplete
    trait_rules: Incomplete
    incoming_trait_auto: Incomplete
    incoming_trait_always: Incomplete
    incoming_rack_output: Incomplete
    incoming_rack_input: Incomplete
    metadata: Incomplete

    def __init__(self) -> None: ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
    def is_always_trait(self, device, attr): ...
    def get(self) -> None: ...
    def key(self, device_name, state_name): ...
    def set_device_labels(self, **mapping: Dict[Device, str]): ...
    def update_name_map(self, ownables, owner_prefix: Incomplete | None = ...) -> None: ...
    def observe(
        self,
        devices,
        changes: bool = ...,
        always: Union[str, List[str]] = ...,
        never: Union[str, List[str]] = ...,
    ): ...
    def inspect_object_name(self, target, max_levels: int = ...): ...

class TabularLoggerBase(Owner, util.Ownable, entry_order=(_host.Email, MungerBase, _host.Host)):
    INDEX_LABEL: str
    path: Incomplete
    last_row: int
    pending_output: Incomplete
    pending_input: Incomplete
    aggregator: Incomplete
    host: Incomplete
    munge: Incomplete

    def __init__(
        self,
        path: Path = ...,
        *,
        append: bool = ...,
        text_relational_min: int = ...,
        force_relational: List[str] = ...,
        nonscalar_file_type: str = ...,
        metadata_dirname: str = ...,
        tar: bool = ...,
        git_commit_in: str = ...,
    ) -> None: ...
    def __copy__(self): ...
    def __owner_init__(self, owner: Owner): ...
    def observe(
        self,
        devices,
        changes: bool = ...,
        always: Union[str, List[str]] = ...,
        never: Union[str, List[str]] = ...,
    ): ...
    def set_row_preprocessor(self, func): ...
    def new_row(self, *args, **kwargs) -> None: ...
    def write(self) -> None: ...
    def context(self, *args, **kws) -> Generator[Incomplete, None, None]: ...
    def clear(self) -> None: ...
    def set_relational_file_format(self, format: str): ...
    output_index: int

    def open(self): ...
    def close(self) -> None: ...

class CSVLogger(TabularLoggerBase):
    ROOT_FILE_NAME: str
    OUTPUT_FILE_NAME: str
    INPUT_FILE_NAME: str
    output_index: int
    tables: Incomplete
    nonscalar_file_type: str

    def open(self) -> None: ...

class MungeToHDF(Device):
    def __init__(self, resource: str = "WindowsPath", key_fmt: str = "str"): ...
    resource: Incomplete
    key_fmt: Incomplete
    backend: Incomplete

    def open(self) -> None: ...
    def close(self) -> None: ...
    def __call__(self, index, row): ...
    def save_metadata(self, name, key_func, **extra): ...

class HDFLogger(TabularLoggerBase):
    KEY_OUTPUT: str
    KEY_INPUT: str
    nonscalar_file_type: str
    munge: Incomplete

    def __init__(
        self,
        path: Path = ...,
        *,
        append: bool = ...,
        key_fmt: str = ...,
        git_commit_in: str = ...,
    ) -> None: ...
    df: Incomplete

    def open(self) -> None: ...
    def close(self) -> None: ...

class SQLiteLogger(TabularLoggerBase):
    INDEX_LABEL: str
    ROOT_FILE_NAME: str
    OUTPUT_TABLE_NAME: str
    inprogress: Incomplete
    committed: Incomplete
    output_index: int

    def open(self) -> None: ...
    def close(self) -> None: ...
    def key(self, name, attr): ...

def to_feather(data, path) -> None: ...
def read_sqlite(
    path,
    table_name=...,
    columns: Incomplete | None = ...,
    nrows: Incomplete | None = ...,
    index_col=...,
): ...
def read(
    path_or_buf: str,
    columns: List[str] = ...,
    nrows: int = ...,
    format: str = ...,
    **kws,
): ...

class MungeTarReader:
    tarnames: Incomplete
    tarfile: Incomplete

    def __init__(self, path, tarname: str = ...) -> None: ...
    def __call__(self, key, *args, **kws): ...

class MungeDirectoryReader:
    path: Incomplete

    def __init__(self, path) -> None: ...
    def __call__(self, key, *args, **kws): ...

class MungeReader:
    def __new__(cls, path): ...

def read_relational(
    path: Union[str, Path],
    expand_col: str,
    root_cols: Union[List[str], None] = ...,
    target_cols: Union[List[str], None] = ...,
    root_nrows: Union[int, None] = ...,
    root_format: str = ...,
    prepend_column_name: bool = ...,
): ...
