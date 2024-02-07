from __future__ import annotations

import contextlib
import importlib
import inspect
import logging
import os
import platform
import select
import socket
import subprocess as sp
import sys
import warnings
from collections import OrderedDict
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Union

import serial
import typing_extensions as typing
from typing_extensions import Literal

from . import paramattr as attr
from . import util
from ._device import Device

if typing.TYPE_CHECKING:
    import telnetlib

    import psutil
    import pyvisa
else:
    telnetlib = util.lazy_import('telnetlib')
    psutil = util.lazy_import('psutil')
    pyvisa = util.lazy_import('pyvisa')


def shell_options_from_keyed_values(
    device: Device,
    skip_none=True,
    hide_false: bool = False,
    join_str: Union[Literal[False], str] = False,
    remap: dict = {},
    converter: callable = str,
) -> list[str]:
    """generate a list of command line argument strings based on
    :module:`labbench.paramattr.value` descriptors in `device`.

    Each of these descriptors defined with `key` may be treated as a command
    line option. Value descriptors are ignored when `key` is unset. The value
    for each option is determined by fetching the corresponding attribute from
    `device`.

    The returned list of strings can be used to build the `argv` needed to run
    shell commands using :class:`ShellBackend` or the `subprocess` module.

    Arguments:
        device: the device containing values to broadcast into command-line arguments
        skip_none: if True, no command-line argument string is generated for values that are unset in devices
        hide_false: if True, boolean options are treated as a flag (e.g., this triggers argument strings are omitted for False values)
        join_str: a string to use to join option (name, value) pairs, or False to generate as separate strings
        remap: a dictionary of {python_value: string_value} pairs to accommodate special cases in string conversion
        converter: function to use to convert the values to strings

    Example:
        Simple boolean options and flags:

        >>> import labbench as lb
        >>> class ShellCopy(ShellBackend):
        ...     recursive: bool = attr.value.bool(False, key='-R')
        >>> cp = ShellCopy(recursive=True)
        >>> print(shell_options_from_keyed_values(cp, hide_false=True))
        ['-R']
        >>> print(shell_options_from_keyed_values(cp, remap={True: 'yes', False: 'no'}))
        ['-R', 'yes']

    Example:
        A non-boolean option:

        >>> class DiskDuplicate(ShellBackend):
        ...     block_size: str = attr.value.str('1M', key='bs')
        >>> dd = DiskDuplicate()
        >>> dd.block_size = '1024k'
        >>> print(shell_options_from_keyed_values(dd, join_str='='))
        ['bs','1024k']
        >>> print(shell_options_from_keyed_values(dd, join_str='='))
        ['bs=1024k']
    """

    argv = []
    for name, attr_def in attr.get_class_attrs(device).items():
        if not isinstance(attr_def, attr.value.Value) or attr_def.key in (
            None,
            attr.Undefined,
        ):
            continue

        py_value = getattr(device, name)

        if not isinstance(attr_def.key, str):
            attr_desc = attr_def.__repr__(owner=device)
            raise TypeError(
                f'flags defined as keys must have type str, but {attr_desc}.key '
                f'has type {type(attr_def.key).__qualname__}'
            )

        if py_value is None:
            if skip_none:
                continue
            else:
                raise ValueError(
                    'None is an invalid flag argument value when skip_none is False'
                )

        elif attr_def._type is bool:
            if hide_false:
                str_args = [attr_def.key] if py_value else []
            elif py_value in remap:
                str_args = [attr_def.key, remap[py_value]]
            else:
                raise ValueError(
                    f'specify hide_false=True or set remap[{py_value}] to enable boolean value mapping'
                )

        else:
            py_value = remap.get(py_value, py_value)
            str_args = [attr_def.key, converter(py_value)]

        if join_str:
            str_args = [
                join_str.join(str_args),
            ]

        argv += str_args

    return argv


class ShellBackend(Device):
    """A wrapper for running shell commands.

    This is a thin wrapper around the subprocess module. Data can be captured from standard output,
    and standard error pipes, and optionally run as a background thread.

    After opening, `backend` is `None`. On a call to run(background=True), `backend`
    becomes is a subprocess instance. When EOF is reached on the executable's
    stdout, the backend resets to None.

    When `run` is called, the program runs in a subprocess.
    The output piped to the command line standard output is queued in a
    background thread. Call read_stdout() to retreive (and clear) this
    queued stdout.
    """

    background_timeout: float = attr.value.float(
        default=1,
        min=0,
        help='wait time after close before killing background processes',
        label='s',
        cache=True,
    )

    def open(self):
        """The :meth:`open` method implements opening in the
        :class:`Device` object protocol. Call the
        :meth:`execute` method when open to
        execute the binary.
        """

        def check_state_change(change={}):
            if self.running():
                raise ValueError(
                    'cannot change command line property trait traits during execution'
                )

        # a Queue for stdout
        self.backend = None

        self._stdout = Queue()
        self._stderr = Queue()

        # Monitor property trait changes
        values = set(attr.list_value_attrs(self)) - set(dir(ShellBackend))

        attr.observe(self, check_state_change, name=tuple(values))

    def run(
        self,
        *argv,
        pipe=True,
        background=False,
        check_return=True,
        raise_on_stderr=False,
        respawn=False,
        timeout=None,
    ):
        if pipe and background:
            return self._background_piped(
                *argv,
                check_return=check_return,
                raise_on_stderr=raise_on_stderr,
                timeout=timeout,
                respawn=respawn,
            )

        if respawn:
            raise ValueError('respawn argument requires pipe=True and background=True')

        if pipe and not background:
            return self._run_piped(
                *argv,
                check_return=check_return,
                raise_on_stderr=raise_on_stderr,
                timeout=timeout,
            )
        else:
            if background:
                raise ValueError('background argument requires pipe=True')
            if raise_on_stderr:
                raise ValueError('raise_on_stderr requires pipe=True')

            return self._run_simple(*argv, check_return=check_return, timeout=timeout)

    def _run_simple(
        self, *argv: list[str], check_return: bool = False, timeout: bool = None
    ):
        """Blocking execution of the command line strings specified by `argv`. If check=True, raise an exception
        on non-zero return code.

        Each command line argument in argv is either
        * a string, which is passed to the binary as is, or
        * list-like sequence ('name0', 'name1', ...) that names value traits to insert as flag arguments

        Flag arguments are converted into a sequence of strings by (1) identifying the command line flag
        for each name as `self.flags[name]` (e.g., "-f"), (2) retrieving the value as getattr(self, name), and
        (3) *if* the value is not None, appending the flag to the list of arguments as appropriate.

        Returns:

            None?
        """
        if timeout is None:
            timeout = self.background_timeout

        return sp.run(argv, check=check_return, timeout=timeout)

    def _run_piped(
        self, *argv: list[str], check_return: bool=False, raise_on_stderr: bool = False, timeout: Union[float,None]=None
    ) -> None:
        """Blocking execution of the specified command line, with a pipe to collect
        stdout.

        Each command line argument in argv is either
        * a string, which is passed to the binary as is, or
        * list-like sequence ('name0', 'name1', ...) that names value traits to insert as flag arguments

        Flag arguments are converted into a sequence of strings by (1) identifying the command line flag
        for each name as `self.flags[name]` (e.g., "-f"), (2) retrieving the value as getattr(self, name), and
        (3) *if* the value is not None, appending the flag to the list of arguments as appropriate.

        Returns:
            stdout
        """
        if timeout is None:
            timeout = self.background_timeout

        path = argv[0]
        try:
            rel = os.path.relpath(path)
            if len(rel) < len(path):
                path = rel
        except ValueError:
            pass

        self._logger.debug(f"shell execute {' '.join(argv)!r}")
        cp = sp.run(
            argv, timeout=timeout, stdout=sp.PIPE, stderr=sp.PIPE, check=check_return
        )
        ret = cp.stdout

        err = cp.stderr.strip().rstrip().decode()
        if raise_on_stderr and len(err) > 0:
            raise ChildProcessError(err)

        if ret:
            lines = ret.decode().splitlines()
            show_count = min(40, len(lines))
            remaining = max(0, len(lines) - show_count)

            logger_msgs = [f'► {line}' for line in lines[: show_count // 2]]
            if remaining > 0:
                logger_msgs.append(f'…{remaining} more lines')
            for line in lines[-show_count // 2 :]:
                logger_msgs.append(f'► {line}')
            self._logger.debug('\n'.join(logger_msgs))
        return ret

    def _background_piped(
        self, *argv, check_return=False, raise_on_stderr=False, respawn=False, timeout=None
    ):
        """Run the executable in the background (returning immediately while
        the executable continues running).

        Once the background process is running,

        * Retrieve standard output from the executable with self.read_stdout

        * Write to standard input self.write_stdin

        * Kill the process with self.kill

        * Check whether the process is running with self.running

        Each command line argument in argv is either
        * a string, which is passed to the binary as is, or
        * list-like sequence ('name0', 'name1', ...) that names value traits to insert as flag arguments

        Flag arguments are converted into a sequence of strings by (1) identifying the command line flag
        for each name as `self.flags[name]` (e.g., "-f"), (2) retrieving the value as getattr(self, name), and
        (3) *if* the value is not None, appending the flag to the list of arguments as appropriate.
        """

        def stdout_to_queue(fd, cmdl):
            """Thread worker to funnel stdout into a queue"""

            pid = self.backend.pid
            q = self._stdout
            for line in iter(fd.readline, ''):
                line = line.decode(errors='replace').replace('\r', '')
                if len(line) > 0:
                    q.put(line)
                else:
                    break
            self.backend = None

            # Respawn (or don't)
            if respawn and not self.__kill:
                self._logger.debug('respawning')
                self._kill_proc_tree(pid)
                spawn(cmdl)
            else:
                self._logger.debug('process ended')

        def stderr_to_exception(fd, cmdl):
            """Thread worker to raise exceptions on standard error output"""
            q = self._stderr
            for line in iter(fd.readline, ''):
                if self.backend is None:
                    break
                line = line.decode(errors='replace').replace('\r', '')
                if len(line) > 0:
                    q.put(line)
                    self._logger.debug(f'stderr {line!r}')
                #                    raise Exception(line)
                else:
                    break

        def spawn(cmdl):
            """Execute the binary in the background (nonblocking),
            while funneling its standard output to a queue in a thread.

            Arguments:
                cmd: iterable containing the binary path, then
                        each argument to be passed to the binary.

            Returns:

                None
            """
            if self.running():
                raise Exception('already running')

            if platform.system().lower() == 'windows':
                si = sp.STARTUPINFO()
                si.dwFlags |= sp.STARTF_USESHOWWINDOW
                platform_flags = {
                    'startupinfo': si,
                    'creationflags': sp.CREATE_NEW_PROCESS_GROUP
                }
            else:
                platform_flags = {}

            proc = sp.Popen(
                list(cmdl),
                stdout=sp.PIPE,
                stderr=sp.PIPE,
                **platform_flags
            )

            self.backend = proc
            Thread(target=lambda: stdout_to_queue(proc.stdout, cmdl)).start()
            if raise_on_stderr:
                Thread(target=lambda: stderr_to_exception(proc.stderr, cmdl)).start()

        if not self.isopen:
            raise ConnectionError(
                f"{self} needs to be opened ({self}.open() or in a 'with' block) manage a background process"
            )

        # Generate the commandline and spawn
        self._logger.debug(f"background execute: {' '.join(argv)!r}")
        self.__kill = False
        spawn(argv)

    def read_stdout(self, wait_for=0):
        """Pop any standard output that has been queued by a background run (see `run`).
        Afterward, the queue is cleared. Starting another background run also clears the queue.

        Returns:

            stdout
        """
        result = ''

        if not self.isopen:
            raise ConnectionError(
                'open the device to read stdout from the background process'
            )

        try:
            n = 0
            while True:
                line = self._stdout.get(wait_for > 0, timeout=self.background_timeout)
                if isinstance(line, Exception):
                    raise line

                n += 1
                result += line

                if wait_for > 0 and n == wait_for:
                    break
        except Empty:
            pass

        return result

    def write_stdin(self, text):
        """Write characters to stdin if a background process is running. Raises
        Exception if no background process is running.
        """
        try:
            self.backend.stdin.write(text)
        except ConnectionError:
            raise Exception('process not running, could not write no stdin')

    def kill(self):
        """If a process is running in the background, kill it. Sends a console
        warning if no process is running.
        """
        self.__kill = True
        backend = self.backend
        if self.running():
            self._logger.debug(f'killing process {backend.pid}')
            self._kill_proc_tree(backend.pid)

    def running(self):
        """Check whether a background process is running.

        Returns:

            True if running, otherwise False
        """
        # Cache the current running one for a second in case the backend "closes"
        return self.isopen and self.backend is not None and self.backend.poll() is None

    def clear_stdout(self):
        """Clear queued standard output. Subsequent calls to `self.read_stdout()` will return
        ''.
        """
        self.read_stdout()

    def close(self):
        self.kill()

    @staticmethod
    def _kill_proc_tree(pid, including_parent=True):
        """Kill the process by pid, and any spawned child processes.
        What a dark metaphor.
        """
        try:
            parent = psutil.Process(pid)

            # Ever notice that this metaphor is very dark?
            children = parent.children(recursive=False)

            # Get the parent first to prevent respawning
            if including_parent:
                parent.kill()
                parent.wait(5)

            for child in children:
                ShellBackend._kill_proc_tree(child.pid)
        except psutil.NoSuchProcess:
            pass


class DotNetDevice(Device):
    """Base class for .NET library wrappers based on pythonnet.

    To implement a DotNetDevice subclass::

        import labbench as lb

        class MyLibraryWrapper(lb.DotNetDevice, libary=<imported python module colocated with dll>, dll_name='mylibrary.dll')
            ...

    When a DotNetDevice is instantiated, it looks to load the dll from the location of the python module
    and dll_name.

    Attributes:
        - `backend` is None after open and is available for replacement by the subclass
    """

    # these can only be set as arguments to a subclass definition
    library = attr.value.any(
        default=None, allow_none=True, sets=False
    )  # Must be a module
    dll_name = attr.value.str(default=None, allow_none=True, sets=False)

    _dlls = {}

    def open(self):
        """dynamically import a .net CLR as a python module at self.dll"""
        library = type(self).library.default
        dll_name = type(self).dll_name.default
        dll_path = Path(library.__path__[0]) / dll_name

        try:
            # static linters really don't like this, since it's created dynamically
            import clr
        except ImportError:
            raise ImportError('pythonnet module is required to use dotnet drivers')

        # base dotnet libraries needed to identify what we're working with
        clr.setPreload(False)
        clr.AddReference('System.Reflection')

        # more frustration for static linters
        import System
        from System.Reflection import Assembly

        try:
            contents = importlib.util.find_spec(library.__package__).loader.get_data(
                str(dll_path)
            )
        except BaseException:
            with open(dll_path, 'rb') as f:
                contents = f.read()

        # binary file contents
        contents = importlib.util.find_spec(library.__package__).loader.get_data(
            str(dll_path)
        )

        # dump that into dotnet
        Assembly.Load(System.Array[System.Byte](contents))

        # do the actual import
        self.dll = importlib.import_module(dll_path.stem)


@attr.message_keying(write_fmt='{key} {value}', write_func='write')
class LabviewSocketInterface(Device):
    """Base class demonstrating simple sockets-based control of a LabView VI.

    Keyed get/set with attr.property are implemented by simple ' command value'.
    Subclasses can therefore implement support for commands in
    specific labview VI similar to VISA commands by
    assigning the commands implemented in the corresponding labview VI.

    Attributes:
        - backend: connection object mapping {'rx': rxsock, 'tx': txsock}
    """

    resource: str = attr.value.NetworkAddress(
        default='127.0.0.1', accept_port=False, kw_only=False, help='LabView VI host address'
    )
    tx_port: int = attr.value.int(
        default=61551, help='TX port to send to the LabView VI'
    )
    rx_port: int = attr.value.int(
        default=61552, help='TX port to send to the LabView VI'
    )
    delay: float = attr.value.float(
        default=1, min=0, help='time to wait after each property trait write or query'
    )
    timeout: float = attr.value.float(
        default=2, min=0, help='maximum wait replies before raising TimeoutError'
    )
    rx_buffer_size: int = attr.value.int(default=1024, min=1)

    def open(self):
        self.backend = dict(
            tx=socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
            rx=socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
        )

        self.backend['rx'].bind((self.resource, self.rx_port))
        self.backend['rx'].settimeout(self.timeout)
        self.clear()

    def close(self):
        for sock in list(self.backend.values()):
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except BaseException:
                self._logger.error('could not close socket ', repr(sock))

    def write(self, msg):
        """Send a string over the tx socket."""
        self._logger.debug(f'write {msg!r}')
        self.backend['tx'].sendto(msg, (self.resource, self.tx_port))
        util.sleep(self.delay)

    def read(self, convert_func=None):
        """Receive from the rx socket until `self.rx_buffer_size` samples
        are received or timeout happens after `self.timeout` seconds.

        Optionally, apply the conversion function to the value after
        it is received.
        """
        rx, addr = self.backend['rx'].recvfrom(self.rx_buffer_size)
        if addr is None:
            raise Exception('received no data')
        rx_disp = rx[: min(80, len(rx))] + ('...' if len(rx) > 80 else '')
        self._logger.debug(f'read {rx_disp!r}')

        key, value = rx.rsplit(' ', 1)
        key = key.split(':', 1)[1].lstrip()
        if convert_func is not None:
            value = convert_func(value)
        return {key: value}

    def clear(self):
        """Clear any data present in the read socket buffer."""
        while True:
            inputready, o, e = select.select([self.backend['rx']], [], [], 0.0)
            if len(inputready) == 0:
                break
            for s in inputready:
                try:
                    s.recv(1)
                except BaseException:
                    continue


class SerialDevice(Device):
    """Base class for wrappers that communicate via pyserial.

    This implementation is very sparse because there is in general
    no messaging string format for serial devices.

    Attributes:
        - backend (serial.Serial): control object, after open
    """

    resource: str = attr.value.str(
        cache=True,
        kw_only=False,
        help='platform-dependent serial port address or URL',
    )

    # Connection value traits
    timeout: float = attr.value.float(
        default=None,
        min=0,
        label='s',
        help='max wait time on reads before raising TimeoutError',
    )
    write_timeout: float = attr.value.float(
        default=None,
        min=0,
        label='s',
        help='max wait time on writes before raising TimeoutError.',
    )
    baud_rate: int = attr.value.int(
        default=9600,
        min=1,
        label='bytes/s',
        help='data rate of the physical serial connection.',
    )
    parity: bytes = attr.value.str(
        default=serial.PARITY_NONE,
        only=tuple(serial.PARITY_NAMES.keys()),
        help='parity in the physical serial connection.',
    )
    stopbits: float = attr.value.float(
        default=None,
        only=[1, 1.5, 2],
        label='bits',
    )
    xonxoff: bool = attr.value.bool(
        default=False, help='whether to enable software flow control on open'
    )
    rtscts: bool = attr.value.bool(
        default=False,
        allow_none=True,
        help='whether to enable hardware (RTS/CTS) flow control on open',
    )
    dsrdtr: bool = attr.value.bool(
        default=False,
        allow_none=True,
        help='whether to enable hardware (DSR/DTR) flow control on open',
    )
    bytesize: int = attr.value.int(
        default=8, allow_none=True, only=(5, 6, 7, 8), label='bits'
    )

    # Overload methods as needed to implement the Device object protocol
    def open(self):
        """Connect to the serial device with the VISA resource string defined
        in self.resource
        """
        keys = 'timeout', 'parity', 'stopbits', 'xonxoff', 'rtscts', 'dsrdtr'
        with attr.hold_attr_notifications(self):
            params = {k: getattr(self, k) for k in keys}
            params = {k: v for k, v in params.items() if v is not None}
        self.backend = serial.serial_for_url(self.resource, self.baud_rate, **params)
        self._logger.debug('opened')

    def close(self):
        """Disconnect the serial instrument"""
        self.backend.close()
        self._logger.debug('closed')

    @classmethod
    def from_hwid(cls, hwid=None, *args, **connection_params) -> SerialDevice:
        """Instantiate a new SerialDevice from a windows `hwid' string instead
        of a comport resource. A hwid string in windows might look something
        like:

        r'PCI\\VEN_8086&DEV_9D3D&SUBSYS_06DC1028&REV_21\\3&11583659&1&B3'
        """

        usb_map = cls._map_serial_hwid_to_port()
        if hwid not in usb_map:
            raise Exception(f'Cannot find serial port with hwid {hwid!r}')
        return cls(usb_map[hwid], *args, **connection_params)

    @classmethod
    def from_url(cls, url, **kws) -> SerialDevice:
        defaults = dict(
            baudrate=None,
            bytesize=None,
            parity=None,
            stopbits=None,
            timeout=None,
            xonxoff=None,
            rtscts=None,
            write_timeout=None,
            dsrdtr=None,
            inter_byte_timeout=None,
            exclusive=None,
        )
        kws = dict(defaults, **kws)
        return cls(url, **kws)

    @staticmethod
    def list_ports(hwid=None):
        """List USB serial devices on the computer

        Returns:
            list of port resource information
        """
        from serial.tools import list_ports

        ports = [
            (port.device, {'hwid': port.hwid, 'description': port.description})
            for port in list_ports.comports()
        ]
        ports = OrderedDict(ports)

        if hwid is not None:
            ports = [
                (port, meta) for port, meta in list(ports.items()) if meta['id'] == hwid
            ]

        return dict(ports)

    @staticmethod
    def _map_serial_hwid_to_label() -> dict[str, str]:
        """Map of the comports and their names.

        Returns:
            mapping {<serial port resource>: <serial port number>}
        """
        from serial.tools import list_ports

        return {port.hwid: port.name for port in list_ports.grep('')}

    @staticmethod
    def _map_serial_hwid_to_port():
        """Map of the comports and their names.

        Returns:
            mapping {<comport name>: <comport ID>}
        """
        from serial.tools import list_ports

        return OrderedDict([(port[2], port[0]) for port in list_ports.comports()])


class SerialLoggingDevice(SerialDevice):
    """Manage connection, acquisition, and data retreival on a device
    that streams logs over serial in a background thread.
    maintaining their own threads, and blocking during setup or stop
    command execution.

    Listener objects must implement an attach method with one argument
    consisting of the queue that the device manager uses to push data
    from the serial port.
    """

    poll_rate: float = attr.value.float(
        default=0.1, min=0, help='Data retreival rate from the device (in seconds)'
    )
    stop_timeout: float = attr.value.float(
        default=0.5, min=0, help='delay after `stop` before terminating run thread'
    )
    max_queue_size: int = attr.value.int(
        default=100000, min=1, help='bytes to allocate in the data retreival buffer'
    )

    def start(self):
        """Start a background thread that acquires log data into a queue.

        Returns:
            None
        """

        q = self._stdout = Queue()
        stop_event = self._stop_requested = Event()
        finish_event = self._finished = Event()

        def accumulate():
            timeout, self.backend.timeout = self.backend.timeout, 0
            self._logger.debug(f'{self!r}: started log acquisition')

            try:
                while self.isopen:
                    buf = self.backend.read_all()
                    if len(buf) > 0:
                        q.put(buf)

                    if stop_event.wait(self.poll_rate) is not True:
                        # wait to check until here to guarantee >= 1 read
                        break
            except (ConnectionError, serial.serialutil.PortNotOpenError):
                # swallow .close() race condition
                stop_event.set()
            except serial.SerialException:
                stop_event.set()
                raise
            finally:
                finish_event.set()
                self._logger.debug(f'{self!r} stopped log acquisition')
                try:
                    self.backend.timeout = timeout
                except BaseException:
                    pass

        if self.running():
            raise Exception('already running')

        Thread(target=accumulate).start()

    def stop(self):
        """Stops the logger acquisition if it is running. Returns silently otherwise.

        Returns:

            None
        """
        self._stop_requested.set()
        self._finished.wait(max(self.poll_rate, self.stop_timeout))

    def running(self):
        """Check whether the logger is running.

        Returns:
            `True` if the logger is running
        """
        return hasattr(self, '_stop') and not self._stop_requested.is_set()

    def fetch(self):
        """Retrieve and return any log data in the buffer.

        Returns:

            any bytes in the buffer
        """
        ret = b''
        try:
            while True:
                ret += self._stdout.get_nowait()
        except Empty:
            pass
        return ret

    def clear(self):
        """Throw away any log data in the buffer."""
        self.fetch()

    def close(self):
        self.stop()


class TelnetDevice(Device):
    """A general base class for communication devices via telnet.
    Unlike (for example) VISA instruments, there is no
    standardized command format like SCPI. The implementation is
    therefore limited to open and close, which open
    or close a pyserial connection object: the `backend` attribute.
    Subclasses can read or write with the backend attribute like they
    would any other telnetlib instance.

    A TelnetDevice `resource` string is an IP address. The port is specified
    by `port`. These can be set when you instantiate the TelnetDevice
    or by setting them afterward in `value traits`.

    Subclassed devices that need property trait descriptors will need
    to implement get_key and set_key methods to implement
    the property trait set and get operations (as appropriate).
    """

    # Connection value traits
    resource: str = attr.value.NetworkAddress(
        cache=True,
        kw_only=False,
        accept_port=True,
        help='server host address',
    )    
    timeout: float = attr.value.float(
        default=2, min=0, label='s', help='connection timeout'
    )

    def open(self):
        """Open a telnet connection to the host defined
        by the string in self.resource
        """
        host, *port = self.resource.split(':')

        if len(port) > 0:
            port = int(port[0])
        else:
            port = 23

        self.backend = telnetlib.Telnet(self.resource, port=port, timeout=self.timeout)

    def close(self):
        """Disconnect the telnet connection"""
        self.backend.close()


_pyvisa_resource_managers = {}


@attr.visa_keying(
    query_fmt='{key}?', write_fmt='{key} {value}', remap={True: 'ON', False: 'OFF'}
)
class VISADevice(Device):
    r"""A wrapper for VISA device automation.

    This exposes `pyvisa` instrument automation capabilities in a `labbench`
    object. Automatic connection based on make and model is supported.

    Customized operation for specific instruments should be implemented in
    subclasses.

    Examples:

        Connect to a VISA device using a known resource string::

            with VISADevice('USB0::0x2A8D::0x1E01::SG56360004::INSTR') as instr:
                print(inst)

        Probe available connections and print valid `VISADevice` constructors::

            print(visa_probe_devices())

        Probe details of available connections and identity strings on the command line::

            labbench visa-probe

        Connect to instrument with serial number 'SG56360004' and query ':FETCH?' CSV::

            with VISADevice('SG56360004') as instr:
                print(inst.query_ascii_values(':FETCH?'))

    See also:
        * Pure python backend installation:
            https://pyvisa.readthedocs.io/projects/pyvisa-py/en/latest/installation.html

        * Proprietary backend installation:
            https://pyvisa.readthedocs.io/en/latest/faq/getting_nivisa.html#faq-getting-nivisa

        * Resource strings and basic configuration:
            https://pyvisa.readthedocs.io/en/latest/introduction/communication.html#getting-the-instrument-configuration-right

    Attributes:
        backend (pyvisa.Resource): instance of a pyvisa instrument object (when open)
    """

    resource: str = attr.value.str(
        default=None,
        cache=True,
        kw_only=False,
        help='VISA resource addressing string for device connection',
    )

    read_termination: str = attr.value.str(
        default='\n', cache=True, help='end-of-line string to delineate the end of ascii query replies'
    )

    write_termination: str = attr.value.str(
        default='\n', cache=True, help='end-of-line string to send after writes'
    )

    open_timeout: float = attr.value.float(
        default=None,
        allow_none=True,
        help='timeout for opening a connection to the instrument',
        label='s',
    )

    timeout: float = attr.value.float(
        default=None,
        cache=True,
        allow_none=True,
        help='message response timeout',
        label='s',
    )

    make = attr.value.str(
        default=None,
        allow_none=True,
        cache=True,
        help='device manufacturer name used to autodetect resource string',
    )

    model = attr.value.str(
        default=None,
        allow_none=True,
        cache=True,
        help='device model used to autodetect resource string',
    )

    @attr.property.str(sets=False, cache=True)
    def serial(self):
        """device-reported serial number"""
        make, model, serial, rev = _visa_parse_identity(self._identity)
        return serial

    @attr.property.str(sets=False, cache=True, help='device revision information')
    def _revision(self):
        """device-reported revision"""
        make, model, serial, rev = _visa_parse_identity(self._identity)
        return rev

    # Common VISA properties
    _identity = attr.property.str(
        key='*IDN',
        sets=False,
        cache=True,
        help='identity string reported by the instrument',
    )

    @attr.property.dict(sets=False, log=False)
    def status_byte(self):
        """instrument status decoded from '*STB?'"""
        code = int(self.query('*STB?'))

        return {
            'error queue not empty': bool(code & 0b00000100),
            'questionable state': bool(code & 0b00001000),
            'message available': bool(code & 0b00010000),
            'event status flag': bool(code & 0b00100000),
            'service request': bool(code & 0b01000000),
            'top level status summary': bool(code & 0b01000000),
            'operating': bool(code & 0b10000000),
        }

    _rm = None  # set at runtime
    _opc = False

    # Overload methods as needed to implement RemoteDevice
    def open(self):
        """opens the instrument.

        When managing device connection through a `with` context,
        this is called automatically and does not need
        to be invoked.
        """

        if type(self)._rm is None:
            visa_default_resource_manager()

        self._opc = False

        kwargs = dict(
            read_termination=self.read_termination,
            write_termination=self.write_termination,
        )

        is_valid_visa_name = _visa_valid_resource_name(self.resource)
        if is_valid_visa_name:
            # use the explicit visa resource name, if provided
            pass
        elif (self.make, self.model) != (None, None) or self.resource:
            if self.resource:
                self._logger.debug(
                    'treating resource as a serial number (pyvisa does not recognize it as a VISA name)'
                )
            # match the supplied (make, model) and/or treat self.resource as a serial number to match
            search_desc = ', '.join(
                [
                    f'{name} {getattr(self, name)!r}'
                    for name in ('make', 'model', 'resource')
                    if getattr(self, name)
                ]
            ).replace('resource', 'serial number')

            matches = visa_probe_devices(self)

            if len(matches) == 0:
                msg = (
                    f'could not open VISA device {type(self)!r}: resource not specified, '
                    f'and no devices were discovered matching {search_desc}'
                )
                raise OSError(msg)
            elif len(matches) == 1:
                self._logger.debug(f'probed resource by matching {search_desc}')
                self.resource = matches[0].resource
            else:
                msg = (
                    f'resource ambiguity: {len(matches)} VISA resources matched {search_desc}, '
                    f'disconnect {len(matches)-1} or specify explicit resource names'
                )
                raise OSError(msg)
        else:
            raise ConnectionError(
                f'must specify a pyvisa resource name, an instrument serial number, or define {type(self)!r} with default make and model'
            )

        if self.timeout is not None:
            kwargs['timeout'] = int(self.timeout * 1000)
        if self.open_timeout is not None:
            kwargs['open_timeout'] = int(self.open_timeout * 1000)

        rm = self._get_rm()
        self.backend = rm.open_resource(self.resource, **kwargs)

        if self.timeout is not None:
            self.backend.set_visa_attribute(
                pyvisa.constants.ResourceAttribute.timeout_value,
                int(self.timeout * 1000),
            )

    def close(self):
        """closes the instrument.

        When managing device connection through a `with` context,
        this is called automatically and does not need
        to be invoked.
        """
        if not self.isopen or self.backend is None:
            return

        try:
            if hasattr(self.backend.visalib, 'viGpibControlREN'):
                with contextlib.suppress(pyvisa.errors.VisaIOError):
                    self.backend.visalib.viGpibControlREN(
                        self.backend.session, pyvisa.constants.VI_GPIB_REN_ADDRESS_GTL
                    )

        except BaseException as e:
            e = str(e)
            if len(e.strip()) > 0:
                # some emulated backends raise empty errors
                self._logger.warning('unhandled close error: ' + e)

        finally:
            self.backend.close()

    def write(self, msg: str, kws: dict[str, typing.Any] = {}):
        """sends an SCPI message to the device.

        Wraps `self.backend.write`, and handles debug logging and adjustments
        when in overlap_and_block
        contexts as appropriate.

        Arguments:
            msg: the SCPI command to send

        Returns:
            None
        """

        # append the *OPC if we're in an overlap and add context
        # TODO: this implementation doesn't generalize, since not all instruments
        # support *OPC in this context
        if self._opc:
            msg = msg + ';*OPC'

        # substitute message based on remap() in self._keying
        kws = {k: self._keying.to_message(v) for k, v in kws.items()}
        msg = msg.format(**kws)

        # outbound message as truncated event log entry
        msg_out = repr(msg) if len(msg) < 1024 else f'({len(msg)} bytes)'
        self._logger.debug(f'write({msg_out})')
        self.backend.write(msg)

    def query(
        self,
        msg: str,
        timeout=None,
        remap: bool = False,
        kws: dict[str, typing.Any] = {},
    ) -> str:
        """queries the device with an SCPI message and returns its reply.

        Handles debug logging and adjustments when in overlap_and_block
        contexts as appropriate.

        Arguments:
            msg: the SCPI message to send
        """
        if timeout is not None:
            _to, self.backend.timeout = self.backend.timeout, timeout

        # substitute message based on remap() in self._keying
        kws = {k: self._keying.to_message(v) for k, v in kws.items()}
        msg = msg.format(**kws)

        # outbound message as truncated event log entry
        msg_out = repr(msg) if len(msg) < 80 else f'({len(msg)} bytes)'
        self._logger.debug(f'query({msg_out}):')

        try:
            ret = self.backend.query(msg)
        finally:
            if timeout is not None:
                self.backend.timeout = _to

        # inbound response as truncated event log entry
        msg_out = repr(ret) if len(ret) < 80 else f'({len(ret)} bytes)'
        self._logger.debug(f'    → {msg_out}')

        if remap:
            return self._keying.from_message(ret)
        else:
            return ret

    def query_ascii_values(
        self,
        msg: str,
        converter='f',
        separator=',',
        container=list,
        delay=None,
        timeout=None,
    ):
        # pre debug
        if timeout is not None:
            _to, self.backend.timeout = self.backend.timeout, timeout

        msg_out = repr(msg) if len(msg) < 80 else f'({len(msg)} bytes)'
        self._logger.debug(f'query_ascii_values({msg_out}):')

        try:
            ret = self.backend.query_ascii_values(
                msg,
                converter=converter,
                separator=separator,
                container=container,
                delay=delay,
            )
        finally:
            if timeout is not None:
                self.backend.timeout = _to

        # post debug
        if len(ret) < 80 and len(repr(ret)) < 80:
            logmsg = repr(ret)
        elif hasattr(ret, 'shape'):
            logmsg = f'({type(ret).__qualname__} with shape {ret.shape})'
        elif hasattr(ret, '__len__'):
            logmsg = f'({type(ret).__qualname__} with length {len(ret)})'
        else:
            logmsg = f'(iterable sequence of type {type(ret)})'

        self._logger.debug(f'    -> {logmsg}')

        return ret

    def wait(self):
        """sends '*WAI' to wait for all commands to complete before continuing"""
        self.write('*WAI')

    def preset(self):
        """sends '*RST' to reset the instrument to preset"""
        self.write('*RST')

    @contextlib.contextmanager
    def overlap_and_block(self, timeout=None, quiet=False):
        """context manager that sends '*OPC' on entry, and performs
        a blocking '*OPC?' query on exit.

        By convention, these SCPI commands give a hint to the instrument
        that commands sent inside this block may be executed concurrently.
        The context exit then blocks until all of the commands have
        completed.

        Example::

            with inst.overlap_and_block():
                inst.write('long running command 1')
                inst.write('long running command 2')

        Arguments:
            timeout: maximum time to wait for '*OPC?' reply, or None to use `self.backend.timeout`
            quiet: Suppress timeout exceptions if this evaluates as True

        Raises:
            TimeoutError: on '*OPC?' query timeout
        """
        self._opc = True
        yield
        self._opc = False
        self.query('*OPC?', timeout=timeout)

    class suppress_timeout(contextlib.suppress):
        """context manager that suppresses timeout exceptions on `write` or `query`.

        Example::

            with inst.suppress_timeout():
                inst.write('long command 1')
                inst.write('long command 2')

            If the command 1 raises an exception, command 2 will not execute
            the context block is complete, and the exception from command 1
            is swallowed.
        """

        def __exit__(self, exctype, excinst, exctb):
            EXC = pyvisa.errors.VisaIOError
            CODE = pyvisa.errors.StatusCode.error_timeout

            return exctype == EXC and excinst.error_code == CODE

    def _get_rm(self):
        backend_name = self._rm

        if backend_name in ('@ivi', '@ni'):
            is_ivi = True
            # compatibility layer for changes in pyvisa 1.12
            if 'ivi' in pyvisa.highlevel.list_backends():
                backend_name = '@ivi'
            else:
                backend_name = '@ni'
        else:
            is_ivi = False

        if len(_pyvisa_resource_managers) == 0:
            visa_default_resource_manager(backend_name)

        try:
            rm = _pyvisa_resource_managers[backend_name]
        except OSError as e:
            if is_ivi:
                url = r'https://pyvisa.readthedocs.io/en/latest/faq/getting_nivisa.html#faq-getting-nivisa'
                msg = f'could not connect to resource manager - see {url}'
                e.args[0] += msg
            raise e

        return rm


def _visa_missing_pyvisapy_support() -> list[str]:
    """a list of names of resources not supported by the current pyvisa-py install"""
    missing = []

    # gpib
    try:
        warnings.filterwarnings('ignore', 'GPIB library not found')
        import gpib_ctypes

        if not gpib_ctypes.gpib._load_lib():
            missing.append('GPIB')
    except ModuleNotFoundError:
        missing.append('GPIB')

    # hislip discovery
    if not importlib.util.find_spec('zeroconf'):
        missing.append('TCPIP')

    # libusb
    try:
        import usb1

        with usb1.USBContext():
            pass
    except OSError:
        missing.append('USB')

    # 2nd check for libusb
    import usb.core

    try:
        usb.core.find()
    except usb.core.NoBackendError:
        missing.append('USB')

    return missing


def _visa_parse_identity(identity: str):
    return identity.split(',', 4)


def visa_list_resources(resourcemanager: str = None) -> list[str]:
    """autodetects and returns a list of valid VISADevice resource strings"""
    if resourcemanager is None:
        rm = VISADevice()._get_rm()
    else:
        rm = pyvisa.ResourceManager(resourcemanager)

    return rm.list_resources()


def visa_default_resource_manager(name: str = None):
    """set the pyvisa resource manager used by labbench.

    Arguments:
        name: the name of the resource manager, such as '@py', '@sim-labbench', or '@ivi'
    """
    import pyvisa

    if name is None:
        import pyvisa.ctwrapper

        libs = pyvisa.ctwrapper.IVIVisaLibrary.get_library_paths()
        if len(libs) > 0:
            name = '@ivi'
        else:
            util.logger.info(
                'using pyvisa-py backend as fallback because no @ivi is installed'
            )
            name = '@py'

    elif name == '@sim-labbench':
        from .testing import pyvisa_sim_resource as name

    if name == '@py':
        warnings.filterwarnings(
            'ignore', 'VICP resources discovery requires the zeroconf package'
        )
        warnings.filterwarnings(
            'ignore', 'TCPIP::hislip resource discovery requires the zeroconf package'
        )
        warnings.filterwarnings('ignore', 'GPIB library not found')

    if name not in _pyvisa_resource_managers:
        _pyvisa_resource_managers[name] = pyvisa.ResourceManager(name)
    VISADevice._rm = name


@util.ttl_cache(10)  # a cache of recent resource parameters
def _visa_probe_resource(
    resource: str, open_timeout, timeout, encoding: ascii
) -> VISADevice:
    device = VISADevice(resource, open_timeout=open_timeout, timeout=timeout)
    device._logger = logging.getLogger()  # suppress the normal logger for probing

    def reopen():
        device.close()
        device.open()

    @util.retry(pyvisa.errors.VisaIOError, tries=3, log=False, exception_func=reopen)
    def probe_read_termination():
        query = '*IDN?' + device.write_termination
        device.backend.write_raw(query.encode(encoding))
        identity = device.backend.read_raw().decode(encoding)

        for read_termination in ('\r\n', '\n', '\r'):
            if identity.endswith(read_termination):
                identity = identity[: -len(read_termination)]
                break
        else:
            read_termination = ''

        return identity, read_termination

    try:
        device.open()
    except TimeoutError:
        return None

    for write_term in ('\n', '\r', '\r\n'):
        device.backend.write_termination = device.write_termination = write_term

        try:
            identity, read_termination = probe_read_termination()
            try:
                make, model, serial, *rev = _visa_parse_identity(identity)
            except ValueError:
                continue

            device.read_termination = read_termination
            device.make = make
            device.model = model
            device._attr_store.cache.update(serial=serial, _revision=rev)

            break
        except pyvisa.errors.VisaIOError as ex:
            if 'VI_ERROR_TMO' not in str(ex):
                raise
        except BaseException as ex:
            device._logger.debug(
                f'visa_list_identities exception on probing identity: {ex!s}'
            )
            raise
    else:
        device = None

    if device is not None:
        device.close()

    return device


def _visa_valid_resource_name(resource: str):
    from pyvisa import rname

    if resource is None:
        return False

    try:
        rname.ResourceName.from_string(resource)
    except rname.InvalidResourceName:
        return False
    else:
        return True


def visa_probe_devices(
    target: VISADevice = None,
    skip_interfaces: list[str] = [],
    open_timeout: float = 0.5,
    timeout: float = 0.25,
) -> list[VISADevice]:
    """discover devices available for communication and their required connection settings.

    Each returned `VISADevice` is and set with a combination of `resource`,
    `read_termination`, and `write_termination` that establishes communication, and the
    `make` and `model` reported by the instrument. The `pyvisa` resource manager is set
    by the most recent call to `visa_default_resource_manager`.

    The probe mechanism is to open a connection to each available resource, and
    if successful, query the instrument identity ('*IDN?'). Discovery will fail for
    devices that do not support this message.

    Arguments:
        target: if specified, return only devices that match target.make and target.model
        skip_interfaces: do not probe interfaces that begin with these strings (case-insensitive)
        open_timeout: timeout on resource open (in s)
        timeout: timeout on identity query (in s)
    """

    def keep_interface(name):
        for iface in skip_interfaces:
            if name.lower().startswith(iface.lower()):
                return False
        return True

    def match_target(device):
        if target is None:
            return True

        if target.make is not None:
            # apply the make filter
            if device.make.lower() != target.make.lower():
                return False

        if target.model is not None:
            # apply the model filter
            if not target.model.lower().startswith(device.model.lower()):
                return False

        if target.resource is not None and not _visa_valid_resource_name(
            target.resource
        ):
            # treat the resource string as a serial number, and filter
            if target.resource.lower() != device.serial.lower():
                return False

        return True

    calls = {
        res: util.Call(_visa_probe_resource, res, open_timeout, timeout, 'ascii')
        for res in visa_list_resources()
        if keep_interface(res)
    }

    devices = util.concurrently(**calls, catch=False, flatten=False)

    if len(devices) == 0:
        return []

    if target is not None:
        if not isinstance(target, Device) and issubclass(target, Device):
            target = target()

        devices = {
            resource: device
            for resource, device in devices.items()
            if match_target(device)
        }

    return list(devices.values())


class Win32ComDevice(Device):
    """Basic support for calling win32 COM APIs.

    a dedicated background thread. Set concurrency=True to decide whether
    this thread support wrapper is applied to the dispatched Win32Com object.
    """

    concurrency = attr.value.bool(
        default=True,
        sets=False,
        help='if False, enforces locking for single-threaded access',
    )

    # The python wrappers for COM drivers still basically require that
    # threading is performed using the windows COM API. Compatibility with
    # the python GIL is not for the faint of heart. Threading support is
    # instead realized with util.ThreadSandbox, which ensures that all calls
    # to the dispatched COM object block until the previous calls are completed
    # from within.

    com_object = attr.value.str(
        default='', sets=False, help='the win32com object string'
    )  # Must be a module

    def open(self):
        """Connect to the win32 com object"""
        import win32com
        import win32com.client

        def should_sandbox(obj):
            try:
                name = win32com.__name__
                return inspect.getmodule(obj).__name__.startswith(name)
            except AttributeError:
                return False

        def factory():
            from pythoncom import CoInitialize

            CoInitialize()
            return win32com.client.Dispatch(self.com_object)

        # Oddness for win32 threadsafety
        sys.coinit_flags = 0

        if self.com_object == '':
            raise Exception('value traits.com_object needs to be set')

        if self.concurrency:
            self.backend = util.ThreadSandbox(factory, should_sandbox)
        else:
            self.backend = win32com.client.Dispatch(self.com_object)
