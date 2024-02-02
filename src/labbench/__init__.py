from . import paramattr, util
from .util import (
    Call,
    concurrently,
    logger,
    retry,
    sequentially,
    show_messages,
    sleep,
    stopwatch,
    timeout_iter,
    until_timeout,
)

util.force_full_traceback(True)

from ._backends import (
    DotNetDevice,
    LabviewSocketInterface,
    SerialDevice,
    SerialLoggingDevice,
    ShellBackend,
    TelnetDevice,
    VISADevice,
    Win32ComDevice,
    shell_options_from_keyed_values,
    visa_default_resource_manager,
    visa_list_resources,
    visa_probe_devices,
)
from ._data import CSVLogger, SQLiteLogger, read, read_relational
from ._device import Device
from ._host import Email
from ._rack import (
    Rack,
    Sequence,
    find_owned_rack_by_type,
    import_as_rack,
    rack_input_table,
    rack_kwargs_skip,
    rack_kwargs_template,
)
from ._serialize import dump_rack, load_rack
from ._version import __version__
from .paramattr import Undefined

# scrub __module__ for cleaner repr() and doc
for _obj in dict(locals()).values():
    if getattr(_obj, '__module__', '').startswith('labbench.'):
        _obj.__module__ = 'labbench'
del _obj

util.force_full_traceback(False)


def _force_full_traceback(force: bool) -> None:
    """configure whether to disable traceback hiding for internal API calls inside labbench"""
    logger.warning(
        'labbench._force_full_traceback has been deprecated - use labbench.util.force_full_traceback instead'
    )
    util.force_full_traceback(True)
