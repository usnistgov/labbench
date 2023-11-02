from . import util as util
from ._rack import (
    Rack as Rack,
    import_as_rack as import_as_rack,
    update_parameter_dict as update_parameter_dict,
)
from _typeshed import Incomplete
from pathlib import Path

RACK_CONFIG_FILENAME: str
EMPTY: Incomplete
INDEX_COLUMN_NAME: str

def write_table_stub(rack: Rack, name: str, path: Path, with_defaults: bool = ...): ...
def dump_rack(
    rack: Rack,
    output_path: Path,
    sourcepath: Path,
    pythonpath: Path = ...,
    exist_ok: bool = ...,
    with_defaults: bool = ...,
    skip_tables: bool = ...,
): ...
def read_yaml_config(config_path: str): ...
def load_rack(output_path: str, defaults: dict = ..., apply: bool = ...) -> Rack: ...
