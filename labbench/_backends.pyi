import contextlib
from . import util as util, value as value
from ._device import Device as Device
from ._traits import observe as observe, unobserve as unobserve
from collections.abc import Generator
from typing import Any
win32com: Any


class ShellBackend(Device):

    def __init__(self, resource: str='str', binary_path: str='NoneType', timeout: str='int'):
        ...
    binary_path: Any
    timeout: Any

    @classmethod
    def __imports__(cls) -> None:
        ...
    backend: Any

    def open(self) -> None:
        ...

    def run(
        self,
        *argv,
        pipe: bool=...,
        background: bool=...,
        check_return: bool=...,
        check_stderr: bool=...,
        respawn: bool=...,
        timeout: Any | None=...
    ):
        ...

    def read_stdout(self, wait_for: int=...):
        ...

    def write_stdin(self, text) -> None:
        ...

    def kill(self) -> None:
        ...

    def running(self):
        ...

    def clear_stdout(self) -> None:
        ...

    def close(self) -> None:
        ...


class DotNetDevice(Device):

    def __init__(self, resource: str='str'):
        ...
    library: Any
    dll_name: Any
    dll: Any

    def open(self) -> None:
        ...

    def open(self) -> None:
        ...


class LabviewSocketInterface(Device):

    def __init__(
        self,
        resource: str='str',
        tx_port: str='int',
        rx_port: str='int',
        delay: str='int',
        timeout: str='int',
        rx_buffer_size: str='int'
    ):
        ...
    resource: Any
    tx_port: Any
    rx_port: Any
    delay: Any
    timeout: Any
    rx_buffer_size: Any
    backend: Any

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def write(self, msg) -> None:
        ...

    def set_key(self, key, value, name) -> None:
        ...

    def read(self, convert_func: Any | None=...):
        ...

    def clear(self) -> None:
        ...


class SerialDevice(Device):

    def __init__(
        self,
        resource: str='str',
        timeout: str='int',
        write_termination: str='bytes',
        baud_rate: str='int',
        parity: str='bytes',
        stopbits: str='int',
        xonxoff: str='bool',
        rtscts: str='bool',
        dsrdtr: str='bool'
    ):
        ...
    resource: Any
    timeout: Any
    write_termination: Any
    baud_rate: int
    parity: Any
    stopbits: Any
    xonxoff: Any
    rtscts: Any
    dsrdtr: Any
    backend: Any

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    @classmethod
    def from_hwid(cls, hwid: Any | None=..., *args, **connection_params):
        ...

    @staticmethod
    def list_ports(hwid: Any | None=...):
        ...


class SerialLoggingDevice(SerialDevice):

    def __init__(
        self,
        resource: str='str',
        timeout: str='int',
        write_termination: str='bytes',
        baud_rate: str='int',
        parity: str='bytes',
        stopbits: str='int',
        xonxoff: str='bool',
        rtscts: str='bool',
        dsrdtr: str='bool',
        poll_rate: str='float',
        data_format: str='bytes',
        stop_timeout: str='float',
        max_queue_size: str='int'
    ):
        ...
    poll_rate: Any
    data_format: Any
    stop_timeout: Any
    max_queue_size: Any

    def configure(self) -> None:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def running(self):
        ...

    def fetch(self):
        ...

    def clear(self) -> None:
        ...

    def close(self) -> None:
        ...


class TelnetDevice(Device):

    def __init__(self, resource: str='str', timeout: str='int'):
        ...
    resource: Any
    timeout: Any

    @classmethod
    def __imports__(cls) -> None:
        ...
    backend: Any

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...


class VISADevice(Device):

    def __init__(
        self,
        resource: str='str',
        read_termination: str='str',
        write_termination: str='str'
    ):
        ...
    read_termination: Any
    write_termination: Any
    identity: Any
    options: Any

    def status_byte(self):
        ...

    @classmethod
    def __imports__(cls) -> None:
        ...
    backend: Any

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    @classmethod
    def list_resources(cls):
        ...

    def write(self, msg: str):
        ...

    def query(self, msg: str, timeout: Any | None=...) -> str:
        ...

    def query_ascii_values(
        self,
        msg: str,
        type_,
        separator: str=...,
        container=...,
        delay: Any | None=...,
        timeout: Any | None=...
    ):
        ...

    def get_key(self, scpi_key, name: Any | None=...):
        ...

    def set_key(self, scpi_key, value, name: Any | None=...) -> None:
        ...

    def wait(self) -> None:
        ...

    def preset(self) -> None:
        ...

    def overlap_and_block(self, timeout: Any | None=..., quiet: bool=...) -> Generator[(
        None,
        None,
        None,
    )]:
        ...


    class suppress_timeout(contextlib.suppress):

        def __exit__(self, exctype, excinst, exctb):
            ...


class SimulatedVISADevice(VISADevice):

    def __init__(
        self,
        resource: str='str',
        read_termination: str='str',
        write_termination: str='str'
    ):
        ...
    yaml_source: Any


class Win32ComDevice(Device):

    def __init__(self, resource: str='str'):
        ...
    com_object: Any

    @classmethod
    def __imports__(cls) -> None:
        ...
    backend: Any

    def open(self):
        ...
