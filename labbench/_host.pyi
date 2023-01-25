import logging
from . import _device as core
from _typeshed import Incomplete


class LogStreamBuffer():

    def __init__(self) -> None:
        ...

    def write(self, msg):
        ...

    def read(self):
        ...

    def flush(self) -> None:
        ...


class LogStderr(core.Device):

    def __init__(self, resource: str='str'):
        ...
    log: str

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def write(self, what) -> None:
        ...

    def flush(self) -> None:
        ...


class Email(core.Device):

    def __init__(
        self,
        resource: str='str',
        port: str='int',
        sender: str='str',
        recipients: str='list',
        success_message: str='str',
        failure_message: str='str'
    ):
        ...
    resource: Incomplete
    port: Incomplete
    sender: Incomplete
    recipients: Incomplete
    success_message: Incomplete
    failure_message: Incomplete
    backend: Incomplete

    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def send_summary(self):
        ...


class JSONFormatter(logging.Formatter):
    t0: Incomplete

    def __init__(self, *args, **kws) -> None:
        ...

    @staticmethod
    def json_serialize_dates(obj):
        ...

    def format(self, rec):
        ...


class Host(core.Device):

    def __init__(self, resource: str='str', git_commit_in: str='NoneType'):
        ...
    git_commit_in: Incomplete
    time_format: str
    backend: Incomplete

    def open(self) -> None:
        ...

    @classmethod
    def __imports__(self) -> None:
        ...

    def close(self) -> None:
        ...

    def metadata(self):
        ...

    def time(self):
        ...

    def log(self):
        ...

    def git_commit_id(self):
        ...

    def git_remote_url(self):
        ...

    def hostname(self):
        ...

    def git_browse_url(self):
        ...

    def git_pending_changes(self):
        ...
