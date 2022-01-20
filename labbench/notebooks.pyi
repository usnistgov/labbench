import logging
from ._backends import VISADevice as VISADevice
from ._host import Host as Host
from ._rack import Rack as Rack
from ._traits import observe as observe
from .util import show_messages as show_messages
from ipywidgets import HTML as HTML, IntProgress as IntProgress, VBox as VBox
from typing import Any

skip_traits: Any

def trait_table(device): ...

class TextareaLogHandler(logging.StreamHandler):
    log_format: str
    time_format: str
    max_buffer: int
    min_delay: float
    stream: Any
    widget: Any
    last_time: Any
    def __init__(self, level=...) -> None: ...
    def emit(self, record): ...

class panel:
    widget: Any
    ncols: int
    devices: Any
    children: Any
    def __new__(cls, source: int = ..., ncols: int = ...): ...
