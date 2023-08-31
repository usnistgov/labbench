import contextlib
from . import util as util, value as value
from ._device import Device as Device
from ._traits import observe as observe
from _typeshed import Incomplete
from collections.abc import Generator
from typing import Dict


class ShellBackend(Device):

    def __init__(self, resource: str='str', binary_path: str='NoneType', timeout: str='int'):
        ...
    binary_path: Incomplete
    timeout: Incomplete
    backend: Incomplete

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
        timeout: Incomplete | None=...
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
    library: Incomplete
    dll_name: Incomplete
    dll: Incomplete

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
    resource: Incomplete
    tx_port: Incomplete
    rx_port: Incomplete
    delay: Incomplete
    timeout: Incomplete
    rx_buffer_size: Incomplete
    backend: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def write(self, msg) -> None:
        ...

    def read(self, convert_func: Incomplete | None=...):
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
    resource: Incomplete
    timeout: Incomplete
    write_termination: Incomplete
    baud_rate: int
    parity: Incomplete
    stopbits: Incomplete
    xonxoff: Incomplete
    rtscts: Incomplete
    dsrdtr: Incomplete
    backend: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    @classmethod
    def from_hwid(cls, hwid: Incomplete | None=..., *args, **connection_params):
        ...

    @staticmethod
    def list_ports(hwid: Incomplete | None=...):
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
    poll_rate: Incomplete
    data_format: Incomplete
    stop_timeout: Incomplete
    max_queue_size: Incomplete

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
    resource: Incomplete
    timeout: Incomplete
    backend: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...


class VISADevice(Device):

    def __init__(
        self,
        resource: str='str',
        read_termination: str='str',
        write_termination: str='str',
        open_timeout: str='NoneType',
        identity_pattern: str='NoneType',
        timeout: str='NoneType'
    ):
        ...
    read_termination: Incomplete
    write_termination: Incomplete
    open_timeout: Incomplete
    identity_pattern: Incomplete
    timeout: Incomplete
    identity: Incomplete
    options: Incomplete

    def status_byte(self):
        ...
    resource: Incomplete
    backend: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def write(self, msg: str):
        ...

    def query(self, msg: str, timeout: Incomplete | None=...) -> str:
        ...

    def query_ascii_values(
        self,
        msg: str,
        type_,
        separator: str=...,
        container=...,
        delay: Incomplete | None=...,
        timeout: Incomplete | None=...
    ):
        ...

    def wait(self) -> None:
        ...

    def preset(self) -> None:
        ...

    def overlap_and_block(self, timeout: Incomplete | None=..., quiet: bool=...) -> Generator[
        None,
        None,
        None,
    ]:
        ...


    class suppress_timeout(contextlib.suppress):

        def __exit__(self, exctype, excinst, exctb):
            ...

def visa_list_resources(resourcemanager: str=...):
    ...

def visa_default_resource_manager(name: Incomplete | None=...):
    ...

def visa_list_identities(skip_interfaces=...) -> Dict[str, str]:
    ...


class SimulatedVISADevice(VISADevice):

    def __init__(
        self,
        resource: str='str',
        read_termination: str='str',
        write_termination: str='str',
        open_timeout: str='NoneType',
        identity_pattern: str='NoneType',
        timeout: str='NoneType'
    ):
        ...
    yaml_source: Incomplete


class Win32ComDevice(Device):

    def __init__(self, resource: str='str'):
        ...
    com_object: Incomplete
    backend: Incomplete

    def open(self):
        ...
