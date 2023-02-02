import io
from . import _device as core, util as util, value as value
from ._device import Device as Device
from ._rack import Owner as Owner, Rack as Rack
from ._traits import observe as observe
from _typeshed import Incomplete
from collections.abc import Generator
EMPTY: Incomplete
INSPECT_SKIP_FILES: Incomplete


class MungerBase(core.Device):

    def __init__(
        self,
        resource: str='WindowsPath',
        text_relational_min: str='int',
        force_relational: str='list',
        dirname_fmt: str='str',
        nonscalar_file_type: str='str',
        metadata_dirname: str='str'
    ):
        ...
    resource: Incomplete
    text_relational_min: Incomplete
    force_relational: Incomplete
    dirname_fmt: Incomplete
    nonscalar_file_type: Incomplete
    metadata_dirname: Incomplete

    def __call__(self, index, row):
        ...

    def save_metadata(self, name, key_func, **extra):
        ...


class MungeToDirectory(MungerBase):

    def __init__(
        self,
        resource: str='WindowsPath',
        text_relational_min: str='int',
        force_relational: str='list',
        dirname_fmt: str='str',
        nonscalar_file_type: str='str',
        metadata_dirname: str='str'
    ):
        ...
    ...


class TarFileIO(io.BytesIO):
    tarfile: Incomplete
    overwrite: bool
    name: Incomplete
    mode: Incomplete

    def __init__(self, open_tarfile, relname, mode: str=..., overwrite: bool=...) -> None:
        ...

    def __del__(self) -> None:
        ...

    def close(self) -> None:
        ...


class MungeToTar(MungerBase):

    def __init__(
        self,
        resource: str='WindowsPath',
        text_relational_min: str='int',
        force_relational: str='list',
        dirname_fmt: str='str',
        nonscalar_file_type: str='str',
        metadata_dirname: str='str'
    ):
        ...
    tarname: str
    tarfile: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...


class Aggregator(util.Ownable):
    PERSISTENT_TRAIT_ROLES: Incomplete
    name_map: Incomplete
    trait_rules: Incomplete
    metadata: Incomplete

    def __init__(self) -> None:
        ...

    def enable(self) -> None:
        ...

    def disable(self) -> None:
        ...

    def is_persistent_trait(self, device, attr):
        ...

    def get(self) -> None:
        ...

    def key(self, device_name, state_name):
        ...

    def set_device_labels(self, **mapping) -> None:
        ...

    def observe(self, devices, changes: bool=..., always=..., never=...) -> None:
        ...


class RelationalTableLogger(Owner, util.Ownable):
    index_label: str
    aggregator: Incomplete
    host: Incomplete
    munge: Incomplete
    last_row: int
    pending_output: Incomplete
    pending_input: Incomplete
    path: Incomplete

    def __init__(
        self,
        path: Incomplete | None=...,
        *,
        append: bool=...,
        text_relational_min: int=...,
        force_relational=...,
        dirname_fmt: str=...,
        nonscalar_file_type: str=...,
        metadata_dirname: str=...,
        tar: bool=...,
        git_commit_in: Incomplete | None=...
    ) -> None:
        ...

    def __copy__(self):
        ...

    def __owner_init__(self, owner) -> None:
        ...

    def observe(self, devices, changes: bool=..., always=..., never=...) -> None:
        ...

    def set_row_preprocessor(self, func):
        ...

    def new_row(self, *args, **kwargs) -> None:
        ...

    def write(self) -> None:
        ...

    def context(self, *args, **kws) -> Generator[Incomplete, None, None]:
        ...

    def clear(self) -> None:
        ...

    def set_relational_file_format(self, format) -> None:
        ...

    def set_path_format(self, format) -> None:
        ...
    output_index: int

    def open(self):
        ...

    def close(self) -> None:
        ...


class CSVLogger(RelationalTableLogger):
    ROOT_FILE_NAME: str
    OUTPUT_FILE_NAME: str
    INPUT_FILE_NAME: str
    output_index: int
    tables: Incomplete
    nonscalar_file_type: str

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...


class MungeToHDF(Device):

    def __init__(self, resource: str='WindowsPath', key_fmt: str='str'):
        ...
    resource: Incomplete
    key_fmt: Incomplete
    backend: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def __call__(self, index, row):
        ...

    def save_metadata(self, name, key_func, **extra):
        ...


class HDFLogger(RelationalTableLogger):
    KEY_OUTPUT: str
    KEY_INPUT: str
    nonscalar_file_type: str
    munge: Incomplete

    def __init__(
        self,
        path,
        *,
        append: bool=...,
        key_fmt: str=...,
        git_commit_in: Incomplete | None=...
    ) -> None:
        ...
    df: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...


class SQLiteLogger(RelationalTableLogger):
    index_label: str
    ROOT_FILE_NAME: str
    OUTPUT_TABLE_NAME: str
    inprogress: Incomplete
    committed: Incomplete
    output_index: int

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def key(self, name, attr):
        ...

def to_feather(data, path) -> None:
    ...

def read_sqlite(
    path,
    table_name=...,
    columns: Incomplete | None=...,
    nrows: Incomplete | None=...,
    index_col=...
):
    ...

def read(
    path_or_buf,
    columns: Incomplete | None=...,
    nrows: Incomplete | None=...,
    format: str=...,
    **kws
):
    ...


class MungeTarReader():
    tarnames: Incomplete
    tarfile: Incomplete

    def __init__(self, path, tarname: str=...) -> None:
        ...

    def __call__(self, key, *args, **kws):
        ...


class MungeDirectoryReader():
    path: Incomplete

    def __init__(self, path) -> None:
        ...

    def __call__(self, key, *args, **kws):
        ...


class MungeReader():

    def __new__(cls, path):
        ...

def read_relational(
    path,
    expand_col,
    root_cols: Incomplete | None=...,
    target_cols: Incomplete | None=...,
    root_nrows: Incomplete | None=...,
    root_format: str=...,
    prepend_column_name: bool=...
):
    ...
