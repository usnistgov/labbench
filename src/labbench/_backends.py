import contextlib
import functools
import importlib
import inspect
import logging
import os
import re
import select
import socket
import subprocess as sp
import sys
import typing_extensions as typing
from collections import OrderedDict
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

import psutil
import pyvisa
import pyvisa.errors
import warnings

from . import util
from ._device import Device
from . import paramattr as attr

try:
    serial = util.lazy_import("serial")
    telnetlib = util.lazy_import("telnetlib")
except RuntimeWarning:
    # not executed: help coding tools recognize lazy_imports as imports
    import telnetlib
    import serial


class ShellBackend(Device):
    """Virtual device controlled by a shell command in another process.

    Data can be captured from standard output, and standard error pipes, and
    optionally run as a background thread.

    After opening, `backend` is `None`. On a call to run(background=True), `backend`
    becomes is a subprocess instance. When EOF is reached on the executable's
    stdout, the backend resets to None.

    When `run` is called, the program runs in a subprocess.
    The output piped to the command line standard output is queued in a
    background thread. Call read_stdout() to retreive (and clear) this
    queued stdout.
    """

    binary_path: Path = attr.value.Path(
        default=None, allow_none=True, help="path to the file to run", cache=True
    )

    timeout: float = attr.value.float(
        default=1,
        min=0,
        help="wait time after close before killing background processes",
        label="s",
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
                    "cannot change command line property trait traits during execution"
                )

        if not os.path.exists(self.binary_path):
            raise OSError(f'executable does not exist at resource=r"{self.binary_path}"')

        # a Queue for stdout
        self.backend = None

        self._stdout = Queue()
        self._stderr = Queue()

        # Monitor property trait changes
        values = set(attr.list_value_attrs(self)).difference(dir(ShellBackend))

        attr.observe(self, check_state_change, name=tuple(values))

    def run(
        self,
        *argv,
        pipe=True,
        background=False,
        check_return=True,
        check_stderr=False,
        respawn=False,
        timeout=None,
    ):
        if pipe and background:
            return self._background_piped(
                *argv,
                check_return=check_return,
                check_stderr=check_stderr,
                timeout=timeout,
                respawn=respawn,
            )

        if respawn:
            raise ValueError("respawn argument requires pipe=True and background=True")

        if pipe and not background:
            return self._run_piped(
                *argv,
                check_return=check_return,
                check_stderr=check_stderr,
                timeout=timeout,
            )
        else:
            if background:
                raise ValueError("background argument requires pipe=True")
            if check_stderr:
                raise ValueError("check_stderr requires pipe=True")

            return self._run_simple(*argv, check_return=check_return, timeout=timeout)

    def _run_simple(self, *argv, check_return=False, timeout=None):
        """Blocking execution of the binary at `self.binary_path`. If check=True, raise an exception
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
            timeout = self.timeout

        return sp.run(self._commandline(argv), check=check_return, timeout=timeout)

    def _run_piped(self, *argv, check_return=False, check_stderr=False, timeout=None):
        """Blocking execution of the binary at `self.binary_path`, with a pipe to collect
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
            timeout = self.timeout

        cmdl = self._commandline(*argv)
        path = cmdl[0]
        try:
            rel = os.path.relpath(path)
            if len(rel) < len(path):
                path = rel
        except ValueError:
            pass

        self._logger.debug(f"shell execute '{repr(' '.join(cmdl))}'")
        cp = sp.run(cmdl, timeout=timeout, stdout=sp.PIPE, stderr=sp.PIPE, check=check_return)
        ret = cp.stdout

        err = cp.stderr.strip().rstrip().decode()
        if check_stderr and len(err) > 0:
            raise ChildProcessError(err)

        if ret:
            lines = ret.decode().splitlines()
            show_count = min(40, len(lines))
            remaining = max(0, len(lines) - show_count)

            logger_msgs = [f"► {line}" for line in lines[: show_count // 2]]
            if remaining > 0:
                logger_msgs.append(f"…{remaining} more lines")
            for line in lines[-show_count // 2 :]:
                logger_msgs.append(f"► {line}")
            self._logger.debug("\n".join(logger_msgs))
        return ret

    def _background_piped(
        self, *argv, check_return=False, check_stderr=False, respawn=False, timeout=None
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

        Returns:

            None
        """

        def stdout_to_queue(fd, cmdl):
            """Thread worker to funnel stdout into a queue"""

            pid = self.backend.pid
            q = self._stdout
            for line in iter(fd.readline, ""):
                line = line.decode(errors="replace").replace("\r", "")
                if len(line) > 0:
                    q.put(line)
                else:
                    break
            self.backend = None

            # Respawn (or don't)
            if respawn and not self.__kill:
                self._logger.debug("respawning")
                self._kill_proc_tree(pid)
                spawn(cmdl)
            else:
                self._logger.debug("process ended")

        def stderr_to_exception(fd, cmdl):
            """Thread worker to raise exceptions on standard error output"""
            q = self._stderr
            for line in iter(fd.readline, ""):
                if self.backend is None:
                    break
                line = line.decode(errors="replace").replace("\r", "")
                if len(line) > 0:
                    q.put(line)
                    self._logger.debug(f"stderr {repr(line)}")
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
                raise Exception("already running")

            si = sp.STARTUPINFO()
            si.dwFlags |= sp.STARTF_USESHOWWINDOW

            proc = sp.Popen(
                list(cmdl),
                stdout=sp.PIPE,
                startupinfo=si,
                creationflags=sp.CREATE_NEW_PROCESS_GROUP,
                stderr=sp.PIPE,
            )

            self.backend = proc
            Thread(target=lambda: stdout_to_queue(proc.stdout, cmdl)).start()
            if check_stderr:
                Thread(target=lambda: stderr_to_exception(proc.stderr, cmdl)).start()

        if not self.isopen:
            raise ConnectionError(
                f"{self} needs to be opened ({self}.open() or in a 'with' block) manage a background process"
            )

        # Generate the commandline and spawn
        cmdl = self._commandline(*argv)
        self._logger.debug(f"background execute: {repr(' '.join(cmdl))}")
        self.__kill = False
        spawn(cmdl)

    def _flags_to_argv(self, flags):
        # find keys in flags that do not exist as value traits
        unsupported = set(flags.keys()).difference(attr.list_value_attrs(self))
        if len(unsupported) > 1:
            raise KeyError(f"flags point to value traits {unsupported} that do not exist in {self}")

        argv = []
        for name, flag_str in flags.items():
            trait = self._attr_defs.attrs[name]
            trait_value = getattr(self, name)

            if not isinstance(flag_str, str) and flag_str is not None:
                raise TypeError(
                    f"keys defined in {self} must be str (for a flag) or None (for no flag"
                )

            if trait_value is None:
                continue

            elif trait.type is bool:
                if flag_str is None:
                    # this would require a remap parameter in value traits, which are not supported (should they be?)
                    # (better to use string?)
                    raise ValueError(
                        "cannot map a Bool onto a string argument specified by None mapping"
                    )

                elif trait_value:
                    # trait_value is truey
                    argv += [flag_str]
                    continue

                else:
                    # trait_value is falsey
                    continue

            elif flag_str is None:
                # do not add a flag

                if trait_value is None:
                    # when trait_value is 'None', don't include this flag
                    continue
                else:
                    argv += [str(trait_value)]

            elif isinstance(flag_str, str):
                argv += [flag_str, str(trait_value)]

            else:
                raise ValueError("unexpected error condition (this should not be possible)")

        return argv

    def _commandline(self, *argv_in):
        """return a new argv list in which dict instances have been replaced by additional
        strings based on the traits in `self`. these dict instances should map {trait_name: cmdline_flag},
        for example dict(force='-f') to map a boolean `self.force` trait value to the -f switch, or
        dict(extra_arg=None) to indicate that `self.extra_arg` will be inserted without a switch if
        `self.extra_arg` is not None.

        Returns:

            tuple of string
        """

        argv = [
            self.binary_path,
        ]

        # Update trait with the flags
        for item in argv_in:
            if isinstance(item, str):
                argv += [item]
            elif isinstance(item, dict):
                argv += self._flags_to_argv(item)
            else:
                raise TypeError(f"command line list item {item} has unsupported type")

        return argv

    def read_stdout(self, wait_for=0):
        """Pop any standard output that has been queued by a background run (see `run`).
        Afterward, the queue is cleared. Starting another background run also clears the queue.

        Returns:

            stdout
        """
        result = ""

        if not self.isopen:
            raise ConnectionError("open the device to read stdout from the background process")

        try:
            n = 0
            while True:
                line = self._stdout.get(wait_for > 0, timeout=self.timeout)
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
            raise Exception("process not running, could not write no stdin")

    def kill(self):
        """If a process is running in the background, kill it. Sends a console
        warning if no process is running.
        """
        self.__kill = True
        backend = self.backend
        if self.running():
            self._logger.debug(f"killing process {backend.pid}")
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
    library = attr.value.any(default=None, allow_none=True, sets=False)  # Must be a module
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
            raise ImportError("pythonnet module is required to use dotnet drivers")

        # base dotnet libraries needed to identify what we're working with
        clr.setPreload(False)
        clr.AddReference("System.Reflection")

        # more frustration for static linters
        import System
        from System.Reflection import Assembly

        try:
            contents = importlib.util.find_spec(library.__package__).loader.get_data(str(dll_path))
        except BaseException:
            with open(dll_path, "rb") as f:
                contents = f.read()

        # binary file contents
        contents = importlib.util.find_spec(library.__package__).loader.get_data(str(dll_path))

        # dump that into dotnet
        Assembly.Load(System.Array[System.Byte](contents))

        # do the actual import
        self.dll = importlib.import_module(dll_path.stem)


@attr.message_keying(write_fmt="{key} {value}", write_func="write")
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
        default="127.0.0.1", accept_port=False, help="LabView VI host address"
    )
    tx_port: int = attr.value.int(default=61551, help="TX port to send to the LabView VI")
    rx_port: int = attr.value.int(default=61552, help="TX port to send to the LabView VI")
    delay: float = attr.value.float(
        default=1, min=0, help="time to wait after each property trait write or query"
    )
    timeout: float = attr.value.float(
        default=2, min=0, help="maximum wait replies before raising TimeoutError"
    )
    rx_buffer_size: int = attr.value.int(default=1024, min=1)

    def open(self):
        self.backend = dict(
            tx=socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
            rx=socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
        )

        self.backend["rx"].bind((self.resource, self.rx_port))
        self.backend["rx"].settimeout(self.timeout)
        self.clear()

    def close(self):
        for sock in list(self.backend.values()):
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except BaseException:
                self._logger.error("could not close socket ", repr(sock))

    def write(self, msg):
        """Send a string over the tx socket."""
        self._logger.debug(f"write {repr(msg)}")
        self.backend["tx"].sendto(msg, (self.resource, self.tx_port))
        util.sleep(self.delay)

    def read(self, convert_func=None):
        """Receive from the rx socket until `self.rx_buffer_size` samples
        are received or timeout happens after `self.timeout` seconds.

        Optionally, apply the conversion function to the value after
        it is received.
        """
        rx, addr = self.backend["rx"].recvfrom(self.rx_buffer_size)
        if addr is None:
            raise Exception("received no data")
        rx_disp = rx[: min(80, len(rx))] + ("..." if len(rx) > 80 else "")
        self._logger.debug(f"read {repr(rx_disp)}")

        key, value = rx.rsplit(" ", 1)
        key = key.split(":", 1)[1].lstrip()
        if convert_func is not None:
            value = convert_func(value)
        return {key: value}

    def clear(self):
        """Clear any data present in the read socket buffer."""
        while True:
            inputready, o, e = select.select([self.backend["rx"]], [], [], 0.0)
            if len(inputready) == 0:
                break
            for s in inputready:
                try:
                    s.recv(1)
                except BaseException:
                    continue


@attr.adjust("resource", help="platform-dependent serial port address")
class SerialDevice(Device):
    """Base class for wrappers that communicate via pyserial.

    This implementation is very sparse because there is in general
    no messaging string format for serial devices.

    Attributes:
        - backend (serial.Serial): control object, after open
    """

    # Connection value traits
    timeout: float = attr.value.float(
        default=2,
        min=0,
        help="Max time to wait for a connection before raising TimeoutError.",
    )
    write_termination: bytes = attr.value.bytes(
        default=b"\n", help="Termination character to send after a write."
    )
    baud_rate: int = attr.value.int(
        default=9600, min=1, help="Data rate of the physical serial connection."
    )
    parity: bytes = attr.value.bytes(default=b"N", help="Parity in the physical serial connection.")
    stopbits: float = attr.value.float(default=1, only=[1, 1.5, 2], help="number of stop bits")
    xonxoff: bool = attr.value.bool(default=False, help="`True` to enable software flow control.")
    rtscts: bool = attr.value.bool(
        default=False, help="`True` to enable hardware (RTS/CTS) flow control."
    )
    dsrdtr: bool = attr.value.bool(
        default=False, help="`True` to enable hardware (DSR/DTR) flow control."
    )

    # Overload methods as needed to implement the Device object protocol
    def open(self):
        """Connect to the serial device with the VISA resource string defined
        in self.resource
        """
        keys = "timeout", "parity", "stopbits", "xonxoff", "rtscts", "dsrdtr"
        params = dict([(k, getattr(self, k)) for k in keys])
        self.backend = serial.Serial(self.resource, self.baud_rate, **params)
        self._logger.debug(f"opened")

    def close(self):
        """Disconnect the serial instrument"""
        self.backend.close()
        self._logger.debug(f"closed")

    @classmethod
    def from_hwid(cls, hwid=None, *args, **connection_params):
        """Instantiate a new SerialDevice from a windows `hwid' string instead
        of a comport resource. A hwid string in windows might look something
        like:

        r'PCI\\VEN_8086&DEV_9D3D&SUBSYS_06DC1028&REV_21\\3&11583659&1&B3'
        """

        usb_map = cls._map_serial_hwid_to_port()
        if hwid not in usb_map:
            raise Exception(f"Cannot find serial port with hwid {repr(hwid)}")
        return cls(usb_map[hwid], *args, **connection_params)

    @staticmethod
    def list_ports(hwid=None):
        """List USB serial devices on the computer

        Returns:
            list of port resource information
        """
        from serial.tools import list_ports

        ports = [
            (port.device, {"hwid": port.hwid, "description": port.description})
            for port in list_ports.comports()
        ]
        ports = OrderedDict(ports)

        if hwid is not None:
            ports = [(port, meta) for port, meta in list(ports.items()) if meta["id"] == hwid]

        return dict(ports)

    @staticmethod
    def _map_serial_hwid_to_label():
        """Map of the comports and their names.

        Returns:
            mapping {<comport name>: <comport ID>}
        """
        from serial.tools import list_ports

        return OrderedDict([(port[2], port[1]) for port in list_ports.comports()])

    @staticmethod
    def _map_serial_hwid_to_port():
        """Map of the comports and their names.

        Returns:
            mapping {<comport name>: <comport ID>}
        """
        from serial.tools import list_ports

        return OrderedDict([(port[2], port[0]) for port in list_ports.comports()])


class SerialLoggingDevice(SerialDevice):
    """Manage connection, acquisition, and data retreival on a single GPS device.
    The goal is to make GPS devices controllable somewhat like instruments:
    maintaining their own threads, and blocking during setup or stop
    command execution.

    Listener objects must implement an attach method with one argument
    consisting of the queue that the device manager uses to push data
    from the serial port.
    """

    poll_rate: float = attr.value.float(
        default=0.1, min=0, help="Data retreival rate from the device (in seconds)"
    )
    data_format: bytes = attr.value.bytes(default=b"", help="Data format metadata")
    stop_timeout: float = attr.value.float(
        default=0.5, min=0, help="delay after `stop` before terminating run thread"
    )
    max_queue_size: int = attr.value.int(
        default=100000, min=1, help="bytes to allocate in the data retreival buffer"
    )

    def configure(self):
        """This is called at the beginning of the logging thread that runs
        on a call to `start`.

        This is a stub that does nothing --- it should be implemented by a
        subclass for a specific serial logger device.
        """
        self._logger.debug(f"{repr(self)}: no device-specific configuration implemented")

    def start(self):
        """Start a background thread that acquires log data into a queue.

        Returns:
            None
        """

        def accumulate():
            timeout, self.backend.timeout = self.backend.timeout, 0
            q = self._stdout
            stop_event = self._stop
            self._logger.debug(f"{repr(self)}: configuring log acquisition")
            self.configure()
            self._logger.debug(f"{repr(self)}: starting log acquisition")
            try:
                while stop_event.wait(self.poll_rate) is not True:
                    q.put(self.backend.read(10 * self.baud_rate * self.poll_rate))
            except serial.SerialException as e:
                self._stop.set()
                self.close()
                raise e
            finally:
                self._logger.debug(f"{repr(self)} ending log acquisition")
                try:
                    self.backend.timeout = timeout
                except BaseException:
                    pass

        if self.running():
            raise Exception("already running")

        self._stdout = Queue()
        self._stop = Event()
        Thread(target=accumulate).start()

    def stop(self):
        """Stops the logger acquisition if it is running. Returns silently otherwise.

        Returns:

            None
        """
        try:
            self._stop.set()
        except BaseException:
            pass

    def running(self):
        """Check whether the logger is running.

        Returns:
            `True` if the logger is running
        """
        return hasattr(self, "_stop") and not self._stop.is_set()

    def fetch(self):
        """Retrieve and return any log data in the buffer.

        Returns:

            any bytes in the buffer
        """
        ret = b""
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
    resource: str = attr.value.NetworkAddress(default="127.0.0.1:23", help="server host address")
    timeout: float = attr.value.float(default=2, min=0, label="s", help="connection timeout")

    def open(self):
        """Open a telnet connection to the host defined
        by the string in self.resource
        """
        host, *port = self.resource.split(":")

        if len(port) > 0:
            port = int(port[0])
        else:
            port = 23

        self.backend = telnetlib.Telnet(self.resource, port=port, timeout=self.timeout)

    def close(self):
        """Disconnect the telnet connection"""
        self.backend.close()


_pyvisa_resource_managers = {}


@attr.visa_keying(query_fmt="{key}?", write_fmt="{key} {value}", remap={True: "ON", False: "OFF"})
class VISADevice(Device):
    r"""A basic VISA device wrapper.

    This exposes `pyvisa` instrument automation capabilities in a `labbench`
    object, and includes support for automatic connections based on make and model.

    Customized operation for specific instruments can be implemented by subclassing `VISADevice`.

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

    # Settings
    read_termination: str = attr.value.str(
        default="\n", cache=True, help="end of line string to expect in query replies"
    )

    write_termination: str = attr.value.str(
        default="\n", cache=True, help="end-of-line string to send after writes"
    )

    open_timeout: float = attr.value.float(
        default=None,
        allow_none=True,
        help="timeout for opening a connection to the instrument",
        label="s",
    )

    timeout: float = attr.value.float(
        default=None,
        cache=True,
        allow_none=True,
        help="message response timeout",
        label="s",
    )

    make = attr.value.str(
        default=None,
        allow_none=True,
        cache=True,
        help="device manufacturer name used to autodetect resource string",
    )

    model = attr.value.str(
        default=None,
        allow_none=True,
        cache=True,
        help="device model used to autodetect resource string",
    )

    @attr.property.str(sets=False, cache=True)
    def serial(self):
        """device-reported serial number"""
        make, model, serial, rev = _visa_parse_identity(self._identity)
        return serial

    @attr.property.str(sets=False, cache=True, help="device revision information")
    def _revision(self):
        """device-reported revision"""
        make, model, serial, rev = _visa_parse_identity(self._identity)
        return rev

    # Common VISA properties
    _identity = attr.property.str(
        key="*IDN",
        sets=False,
        cache=True,
        help="identity string reported by the instrument",
    )

    @attr.property.dict(sets=False)
    def status_byte(self):
        """instrument status decoded from '*STB?'"""
        code = int(self.query("*STB?"))

        return {
            "error queue not empty": bool(code & 0b00000100),
            "questionable state": bool(code & 0b00001000),
            "message available": bool(code & 0b00010000),
            "event status flag": bool(code & 0b00100000),
            "service request": bool(code & 0b01000000),
            "top level status summary": bool(code & 0b01000000),
            "operating": bool(code & 0b10000000),
        }

    _rm = "@py"
    _opc = False

    # Overload methods as needed to implement RemoteDevice
    def open(self):
        """opens the instrument.

        When managing device connection through a `with` context,
        this is called automatically and does not need
        to be invoked.
        """

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
                    f"treating resource as a serial number (pyvisa does not recognize it as a VISA name)"
                )
            # match the supplied (make, model) and/or treat self.resource as a serial number to match
            search_desc = ", ".join(
                [
                    f"{name} {repr(getattr(self, name))}"
                    for name in ("make", "model", "resource")
                    if getattr(self, name)
                ]
            ).replace("resource", "serial number")

            matches = visa_probe_devices(self)

            if len(matches) == 0:
                msg = (
                    f"could not open VISA device {repr(type(self))}: resource not specified, "
                    f"and no devices were discovered matching {search_desc}"
                )
                raise IOError(msg)
            elif len(matches) == 1:
                self._logger.debug(f"probed resource by matching {search_desc}")
                self.resource = matches[0].resource
            else:
                msg = (
                    f"resource ambiguity: {len(matches)} VISA resources matched {search_desc}, "
                    f"disconnect {len(matches)-1} or specify explicit resource names"
                )
                raise IOError(msg)
        else:
            raise ConnectionError(
                f"must specify a pyvisa resource name, an instrument serial number, or define {repr(type(self))} with default make and model"
            )

        if self.timeout is not None:
            kwargs["timeout"] = int(self.timeout * 1000)
        if self.open_timeout is not None:
            kwargs["open_timeout"] = int(self.open_timeout * 1000)

        rm = self._get_rm()
        self.backend = rm.open_resource(self.resource, **kwargs)

        if self.timeout is not None:
            self.backend.set_visa_attribute(
                pyvisa.constants.ResourceAttribute.timeout_value, int(self.timeout * 1000)
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
            if hasattr(self.backend.visalib, "viGpibControlREN"):
                with contextlib.suppress(pyvisa.errors.VisaIOError):
                    self.backend.visalib.viGpibControlREN(
                        self.backend.session, pyvisa.constants.VI_GPIB_REN_ADDRESS_GTL
                    )

        except BaseException as e:
            e = str(e)
            if len(e.strip()) > 0:
                # some emulated backends raise empty errors
                self._logger.warning("unhandled close error: " + e)

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
            msg = msg + ";*OPC"

        # substitute message based on remap() in self._keying
        kws = {k: self._keying.to_message(v) for k, v in kws.items()}
        msg = msg.format(**kws)

        # outbound message as truncated event log entry
        msg_out = repr(msg) if len(msg) < 1024 else f"({len(msg)} bytes)"
        self._logger.debug(f"write({msg_out})")
        self.backend.write(msg)

    def query(
        self, msg: str, timeout=None, remap: bool = False, kws: dict[str, typing.Any] = {}
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
        msg_out = repr(msg) if len(msg) < 80 else f"({len(msg)} bytes)"
        self._logger.debug(f"query({msg_out}):")

        try:
            ret = self.backend.query(msg)
        finally:
            if timeout is not None:
                self.backend.timeout = _to

        # inbound response as truncated event log entry
        msg_out = repr(ret) if len(ret) < 80 else f"({len(ret)} bytes)"
        self._logger.debug(f"    → {msg_out}")

        if remap:
            return self._keying.from_message(ret)
        else:
            return ret

    def query_ascii_values(
        self, msg: str, type_, separator=",", container=list, delay=None, timeout=None
    ):
        # pre debug
        if timeout is not None:
            _to, self.backend.timeout = self.backend.timeout, timeout

        msg_out = repr(msg) if len(msg) < 80 else f"({len(msg)} bytes)"
        self._logger.debug(f"query_ascii_values({msg_out}):")

        try:
            ret = self.backend.query_ascii_values(msg, type_, separator, container, delay)
        finally:
            if timeout is not None:
                self.backend.timeout = _to

        # post debug
        if len(ret) < 80 and len(repr(ret)) < 80:
            logmsg = repr(ret)
        elif hasattr(ret, "shape"):
            logmsg = f"({type(ret).__qualname__} with shape {ret.shape})"
        elif hasattr(ret, "__len__"):
            logmsg = f"({type(ret).__qualname__} with length {len(ret)})"
        else:
            logmsg = f"(iterable sequence of type {type(ret)})"

        self._logger.debug(f"    -> {logmsg}")

        return ret

    def wait(self):
        """sends '*WAI' to wait for all commands to complete before continuing"""
        self.write("*WAI")

    def preset(self):
        """sends '*RST' to reset the instrument to preset"""
        self.write("*RST")

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
        self.query("*OPC?", timeout=timeout)

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

        if backend_name in ("@ivi", "@ni"):
            is_ivi = True
            # compatibility layer for changes in pyvisa 1.12
            if "ivi" in pyvisa.highlevel.list_backends():
                backend_name = "@ivi"
            else:
                backend_name = "@ni"
        else:
            is_ivi = False

        if len(_pyvisa_resource_managers) == 0:
            visa_default_resource_manager(backend_name)

        try:
            rm = _pyvisa_resource_managers[backend_name]
        except OSError as e:
            if is_ivi:
                url = r"https://pyvisa.readthedocs.io/en/latest/faq/getting_nivisa.html#faq-getting-nivisa"
                msg = f"could not connect to resource manager - see {url}"
                e.args[0] += msg
            raise e

        return rm


def _visa_missing_pyvisapy_support() -> list[str]:
    """a list of names of resources not supported by the current pyvisa-py install"""
    missing = []

    # gpib
    try:
        warnings.filterwarnings("ignore", "GPIB library not found")
        import gpib_ctypes

        if not gpib_ctypes.gpib._load_lib():
            missing.append("GPIB")
    except ModuleNotFoundError:
        missing.append("GPIB")

    # hislip discovery
    try:
        import zeroconf
    except ModuleNotFoundError:
        missing.append("TCPIP")

    # libusb
    try:
        import usb1

        with usb1.USBContext() as context:
            pass
    except OSError:
        missing.append("USB")

    return missing


def _visa_parse_identity(identity: str):
    return identity.split(",", 4)


def visa_list_resources(resourcemanager: str = None) -> list[str]:
    """autodetects and returns a list of valid VISADevice resource strings"""
    if resourcemanager is None:
        rm = VISADevice()._get_rm()
    else:
        rm = pyvisa.ResourceManager(resourcemanager)

    return rm.list_resources()


def visa_default_resource_manager(name: str):
    """set the pyvisa resource manager used by labbench.

    Arguments:
        name: the name of the resource manager, such as '@py', '@sim', or '@ivi'
    """
    if name == "@sim":
        from .testing import pyvisa_sim_resource as full_name
    else:
        full_name = name

    if name == "@py":
        warnings.filterwarnings("ignore", "VICP resources discovery requires the zeroconf package")
        warnings.filterwarnings(
            "ignore", "TCPIP::hislip resource discovery requires the zeroconf package"
        )
        warnings.filterwarnings("ignore", "GPIB library not found")

    if name not in _pyvisa_resource_managers:
        _pyvisa_resource_managers[name] = pyvisa.ResourceManager(full_name)
    VISADevice._rm = name


@util.ttl_cache(10)  # a cache of recent resource parameters
def _visa_probe_resource(resource: str, open_timeout, timeout, encoding: "ascii") -> VISADevice:
    device = VISADevice(resource, open_timeout=open_timeout, timeout=timeout)
    device._logger = logging.getLogger()  # suppress the normal logger for probing

    def reopen():
        device.close()
        device.open()

    @util.retry(pyvisa.errors.VisaIOError, tries=3, log=False, exception_func=reopen)
    def probe_read_termination():
        query = "*IDN?" + device.write_termination
        device.backend.write_raw(query.encode(encoding))
        identity = device.backend.read_raw().decode(encoding)

        for read_termination in ("\r\n", "\n", "\r"):
            if identity.endswith(read_termination):
                identity = identity[: -len(read_termination)]
                break
        else:
            read_termination = ""

        return identity, read_termination

    try:
        device.open()
    except TimeoutError:
        return None

    for write_term in ("\n", "\r", "\r\n"):
        device.backend.write_termination = device.write_termination = write_term

        try:
            identity, read_termination = probe_read_termination()
            make, model, serial, rev = _visa_parse_identity(identity)

            device.read_termination = read_termination
            device.make = make
            device.model = model
            device._attr_store.cache.update(serial=serial, _revision=rev)

            break
        except pyvisa.errors.VisaIOError as ex:
            if "VI_ERROR_TMO" not in str(ex):
                raise
        except BaseException as ex:
            device._logger.debug(f"visa_list_identities exception on probing identity: {str(ex)}")
            raise
    else:
        device = None

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

        if target.resource is not None and not _visa_valid_resource_name(target.resource):
            # treat the resource string as a serial number, and filter
            if target.resource.lower() != device.serial.lower():
                return False

        return True

    calls = {
        res: util.Call(_visa_probe_resource, res, open_timeout, timeout, "ascii")
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
        default=True, sets=False, help="if False, enforces locking for single-threaded access"
    )

    # The python wrappers for COM drivers still basically require that
    # threading is performed using the windows COM API. Compatibility with
    # the python GIL is not for the faint of heart. Threading support is
    # instead realized with util.ThreadSandbox, which ensures that all calls
    # to the dispatched COM object block until the previous calls are completed
    # from within.

    com_object = attr.value.str(
        default="", sets=False, help="the win32com object string"
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

        if self.com_object == "":
            raise Exception("value traits.com_object needs to be set")

        if self.concurrency:
            self.backend = util.ThreadSandbox(factory, should_sandbox)
        else:
            self.backend = win32com.client.Dispatch(self.com_object)
