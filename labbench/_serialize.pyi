from ._rack import Rack
from pathlib import Path
from typing import Any

def dump_rack(rack: Rack, dir_path: Path, exist_ok: bool=..., with_defaults: bool=...) -> Any:
    ...

def load_rack(dir_path: Any, apply: Any=...) -> Rack:
    ...
