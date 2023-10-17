import logging
from ._backends import VISADevice as VISADevice
from ._host import Host as Host
from ._rack import Rack as Rack
from .paramattr import get_class_attrs as get_class_attrs, observe as observe
from .util import show_messages as show_messages
from _typeshed import Incomplete

skip_traits: Incomplete

def trait_table(device): ...

class TextareaLogHandler(logging.StreamHandler):
    log_format: str
    time_format: str
    max_buffer: int
    min_delay: float
    stream: Incomplete
    widget: Incomplete
    last_time: Incomplete

    def __init__(self, level=...) -> None: ...
    def emit(self, record): ...

class panel:
    widget: Incomplete
    ncols: int
    devices: Incomplete
    children: Incomplete

    def __new__(cls, source: int = ..., ncols: int = ...): ...
