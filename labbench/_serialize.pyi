from ._rack import Rack
from pathlib import Path
from typing import Any

def dump_rack(
    rack: Rack,
    output_path: Path,
    sourcepath: Path,
    pythonpath: Path = ...,
    exist_ok: bool = ...,
    with_defaults: bool = ...,
) -> Any: ...
def load_rack(output_path: Any, apply: Any = ...) -> Rack: ...
