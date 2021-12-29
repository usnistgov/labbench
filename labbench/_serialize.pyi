import pandas as pd
from . import util as util
from ._rack import (
    BoundSequence as BoundSequence,
    Rack as Rack,
    Sequence as Sequence,
    import_as_rack as import_as_rack,
    update_parameter_dict as update_parameter_dict,
)
from pathlib import Path
from typing import Any
RACK_CONFIG_FILENAME: str
EMPTY: Any

def make_sequence_stub(rack: Rack, name: str, path: Path, with_defaults: bool=...) -> pd.DataFrame:
    ...

def dump_rack(
    rack: Rack,
    output_path: Path,
    sourcepath: Path,
    pythonpath: Path=...,
    exist_ok: bool=...,
    with_defaults: bool=...
):
    ...

def load_rack(output_path: str, defaults: dict=..., apply: bool=...) -> Rack:
    ...
