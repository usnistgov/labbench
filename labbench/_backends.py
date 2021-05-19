# This software was developed by employees of the National Institute of
# Standards and Technology (NIST), an agency of the Federal Government.
# Pursuant to title 17 United States Code Section 105, works of NIST employees
# are not subject to copyright protection in the United States and are
# considered to be in the public domain. Permission to freely use, copy,
# modify, and distribute this software and its documentation without fee is
# hereby granted, provided that this notice and disclaimer of warranty appears
# in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
# EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
# THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
# INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
# SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE. IN NO EVENT
# SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
# INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM,
# OR IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON
# WARRANTY, CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED
# BY PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

from ._device import Device
from . import property as property_
from . import value
from ._traits import observe
from ._traits import unobserve
from . import util


from collections import OrderedDict
import contextlib
import inspect
import os
import psutil
import serial
import pyvisa
import pyvisa.constants
from queue import Queue, Empty
import re
import socket
import select
import sys
from threading import Thread, Event
import warnings


class ShellBackend(Device):
    """ Virtual device controlled by a shell command in another process. It supports
        threaded data logging through standard
        input, standard output, and standard error pipes.

        The shell is connection-less, so the `backend` is `None` after connect. On a
        call to execute(), `backend` becomes is a subprocess instance. When
        EOF is reached on the executable's stdout, the backend is assumed
        terminated and is reset to None.

        When `execute` is called, the program runs in a subprocess.
        The output piped to the command line standard output is queued in a
        background thread. Call read_stdout() to retreive (and clear) this
        queued stdout.

        Special behaviors:
        * traits in `ShellBackend` support the `key` argument, which can be a
        string to specify a command flag, `None` to specify an argument with no flags,
        or left as `lb.Undefined` to be ignored in forming a command line.
    """

    binary_path = value.Path(
        default=None,
        allow_none=True,
        help='path to the file to run',
        cache=True
    )

    timeout = value.float(
        default=1,
        min=0,
        help='wait time after close before killing the process',
        label='s',
        cache=True
    )

    # flags = value.dict({}, help="flag map, e.g., dict(force='-f') to connect the class value trait 'force' to '-f'")

    # arguments = value.list(
    #     default=[], help='list of command line arguments to pass into the executable'
    # )
    #
    # arguments_min = value.int(
    #     default=0, min=0,
    #     sets=False, help='minimum extra command line arguments needed to run'
    # )

    @classmethod
    def __imports__(cls):
        global sp
        import subprocess as sp

    def open(self):
        """ The :meth:`open` method implements opening in the
            :class:`Device` object protocol. Call the
            :meth:`execute` method when open to
            execute the binary.
        """
        def check_state_change(change={}):
            if self.running():
                raise ValueError('cannot change command line property trait traits during execution')

        if not os.path.exists(self.binary_path):
            raise OSError(
                f'executable does not exist at resource=r"{self.binary_path}"')

        # a Queue for stdout
        self.backend = None
        
        self._stdout = Queue()
        self._stderr = Queue()

        # Monitor property trait changes
        properties = set(self._value_attrs) \
            .difference(dir(ShellBackend))

        observe(self, check_state_change, name=tuple(properties))

    def run(self, *argv, pipe=True, background=False, check_return=True, check_stderr=False, respawn=False, timeout=None):
        if pipe and background:
            return self._background_piped(*argv, check_return=check_return, check_stderr=check_stderr, timeout=timeout, respawn=respawn)
    
        if respawn:
            raise ValueError(f'respawn argument requires pipe=True and background=True')

        if pipe and not background:
            return self._run_piped(*argv, check_return=check_return, check_stderr=check_stderr, timeout=timeout)
        else:
            if background:
                raise ValueError(f'background argument requires pipe=True')
            if check_stderr:
                raise ValueError(f'check_stderr requires pipe=True')

            return self._run_simple(*argv, check_return=check_return, timeout=timeout)


    def _run_simple(self, *argv, check_return=False, timeout=None):
        """ Blocking execution of the binary at `self.binary_path`. If check=True, raise an exception
            on non-zero return code.

            Each command line argument in argv is either
            * a string, which is passed to the binary as is, or
            * list-like sequence ('name0', 'name1', ...) that names value traits to insert as flag arguments
            
            Flag arguments are converted into a sequence of strings by (1) identifying the command line flag
            for each name as `self.flags[name]` (e.g., "-f"), (2) retrieving the value as getattr(self, name), and
            (3) *if* the value is not None, appending the flag to the list of arguments as appropriate.

            :returns: None?
        """
        if timeout is None:
            timeout = self.timeout

        return sp.run(self._commandline(argv), check=check_return, timeout=timeout)

    def _run_piped(self, *argv, check_return=False, check_stderr=False, timeout=None):
        """ Blocking execution of the binary at `self.binary_path`, with a pipe to collect
            stdout.

            Each command line argument in argv is either
            * a string, which is passed to the binary as is, or
            * list-like sequence ('name0', 'name1', ...) that names value traits to insert as flag arguments
            
            Flag arguments are converted into a sequence of strings by (1) identifying the command line flag
            for each name as `self.flags[name]` (e.g., "-f"), (2) retrieving the value as getattr(self, name), and
            (3) *if* the value is not None, appending the flag to the list of arguments as appropriate.

            :returns: stdout
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

        self._console.debug(f"shell execute '{repr(' '.join(cmdl))}'")
        cp = sp.run(cmdl, timeout=timeout, stdout=sp.PIPE, stderr=sp.PIPE, check=check_return)
        ret = cp.stdout

        err = cp.stderr.strip().rstrip().decode()
        if check_stderr and len(err) > 0:
            raise ChildProcessError(err)

        if ret:
            lines = ret.decode().splitlines()
            show_count = min(40, len(lines))
            remaining = max(0, len(lines) - show_count)
            for line in lines[:show_count // 2]:
                self._console.debug(f'► {line}')
            if remaining > 0:
                self._console.debug(f'…{remaining} more lines')
            for line in lines[-show_count // 2:]:
                self._console.debug(f'► {line}')
        return ret

    def _background_piped(self, *argv, check_return=False, check_stderr=False, respawn=False, timeout=None):
        """ Run the executable in the background (returning immediately while
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

            :returns: None
        """

        def stdout_to_queue(fd, cmdl):
            """ Thread worker to funnel stdout into a queue
            """

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
                self._console.debug('respawning')
                self._kill_proc_tree(pid)
                spawn(cmdl)
            else:
                self._console.debug('process ended')

        def stderr_to_exception(fd, cmdl):
            """ Thread worker to raise exceptions on standard error output
            """
            q = self._stderr
            for line in iter(fd.readline, ''):
                if self.backend is None:
                    break                
                line = line.decode(errors='replace').replace('\r', '')
                if len(line) > 0:
                    q.put(line)
                    self._console.debug(f'stderr {repr(line)}')
                #                    raise Exception(line)
                else:
                    break

        def spawn(cmdl):
            """ Execute the binary in the background (nonblocking),
                while funneling its standard output to a queue in a thread.

                :param cmd: iterable containing the binary path, then
                            each argument to be passed to the binary.

                :returns: None
            """
            if self.running():
                raise Exception('already running')

            si = sp.STARTUPINFO()
            si.dwFlags |= sp.STARTF_USESHOWWINDOW

            proc = sp.Popen(list(cmdl), stdout=sp.PIPE, startupinfo=si,
                            bufsize=1,
                            creationflags=sp.CREATE_NEW_PROCESS_GROUP,
                            stderr=sp.PIPE)

            self.backend = proc
            Thread(target=lambda: stdout_to_queue(proc.stdout, cmdl)).start()
            if check_stderr:
                Thread(target=lambda: stderr_to_exception(
                    proc.stderr, cmdl)).start()

        if not self.isopen:
            raise ConnectionError(f"{self} needs to be opened ({self}.open() or in a 'with' block) manage a background process")

        # Generate the commandline and spawn
        cmdl = self._commandline(*argv)
        self._console.debug(f"background execute: {repr(' '.join(cmdl))}")
        self.__kill = False
        spawn(cmdl)

    def _flags_to_argv(self, flags):
        # find keys in flags that do not exist as value traits
        unsupported = set(flags.keys()).difference(self._value_attrs)
        if len(unsupported) > 1:
            raise KeyError(f"flags point to value traits {unsupported} that do not exist in {self}")

        argv = []
        for name, flag_str in flags.items():
            trait = self._traits[name]
            trait_value = getattr(self, name)

            if not isinstance(flag_str, str) and flag_str is not None:
                raise TypeError(f"keys defined in {self} must be str (for a flag) or None (for no flag")

            if trait_value is None:
                continue

            elif trait.type is bool:
                if flag_str is None:
                    # this would require a remap parameter in value traits, which are not supported (should they be?)
                    # (better to use string?)
                    raise ValueError(f"don't know how to map a Bool onto a string argument as specified by None mapping")

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
                raise ValueError('unexpected error condition (this should not be possible)')

        return argv

    def _commandline(self, *argv_in):
        """ return a new argv list in which dict instances have been replaced by additional
            strings based on the traits in `self`. these dict instances should map {trait_name: cmdline_flag},
            for example dict(force='-f') to map a boolean `self.force` trait value to the -f switch, or
            dict(extra_arg=None) to indicate that `self.extra_arg` will be inserted without a switch if
            `self.extra_arg` is not None.

            :returns: tuple of string
        """

        argv = [self.binary_path,]

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
        """ Pop any standard output that has been queued by a background run (see `run`).
            Afterward, the queue is cleared. Starting another background run also clears the queue.

            :returns: stdout
        """
        result = ''
        
        if not self.isopen:
            raise ConnectionError(f"an open connection is necessary to read stdout from the background process")

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
        """ Write characters to stdin if a background process is running. Raises
            Exception if no background process is running.
        """
        try:
            self.backend.stdin.write(text)
        except ConnectionError:
            raise Exception("process not running, could not write no stdin")

    def kill(self):
        """ If a process is running in the background, kill it. Sends a console
            warning if no process is running.
        """
        self.__kill = True
        backend = self.backend
        if self.running():
            self._console.debug(f'killing process {backend.pid}')
            self._kill_proc_tree(backend.pid)

    def running(self):
        """ Check whether a background process is running.

            :returns: True if running, otherwise False
        """
        # Cache the current running one for a second in case the backend "closes"
        return self.isopen and self.backend is not None and self.backend.poll() is None

    def clear_stdout(self):
        """ Clear queued standard output. Subsequent calls to `self.read_stdout()` will return
            ''.
        """
        self.read_stdout()

    # def update_flags(self, **flags):
    #     """ update and validate value traits
    #     """

    #     bad_flags = set(flags.keys()).difference(self._value_attrs)
    #     if len(bad_flags) > 0:
    #         raise AttributeError(f"{self} cannot set flag(s) '{tuple(bad_flags)}' with no corresponding value trait")

    #     self.__dict__.update(flags)

    def close(self):
        self.kill()

    @staticmethod
    def _kill_proc_tree(pid, including_parent=True):
        """ Kill the process by pid, and any spawned child processes.
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

import importlib
from pathlib import Path

class DotNetDevice(Device):
    """ This Device backend represents a wrapper around a .NET library. It is implemented
        with pythonnet, and handlesimports.

        In order to implement a DotNetDevice subclass:

        * define the attribute `library = <mypythonmodule.wheredllbinariesare>`, the python module with copies of the .NET DLLs are

        * define the attribute `dll_name = "mydllname.dll"`, the name of the DLL binary in the python module above

        When a DotNetDevice is instantiated, it tries to load the dll according to the above specifications.

        Other attributes of DotNetDevice use the following conventions

        * `backend` may be set by a subclass `open` method (otherwise it is left as None)

    """

    # these can only be set as arguments to a subclass definition
    library = value.any(None, allow_none=True, sets=False)  # Must be a module
    dll_name = value.str(None, allow_none=True, sets=False)

    _dlls = {}

    def open(self):
        """ dynamically import a .net CLR as a python module at self.dll
        """
        library = type(self).library.default
        dll_name = type(self).dll_name.default
        dll_path = Path(library.__path__[0])/dll_name

        try:
            # static linters really don't like this, since it's created dynamically 
            import clr
        except ImportError:
            raise ImportError('pythonnet module is required to use dotnet drivers')

        # base dotnet libraries needed to identify what we're working with
        clr.setPreload(False)
        clr.AddReference('System.Reflection')

        # more frustration for static linters
        from System.Reflection import Assembly
        import System

        try:
            contents = importlib.util.find_spec(library.__package__).loader.get_data(str(dll_path))
        except:
            with open(dll_path, 'rb') as f:
                contents = f.read()

        # binary file contents
        contents = importlib.util.find_spec(library.__package__).loader.get_data(str(dll_path))

        # dump that into dotnet
        Assembly.Load(System.Array[System.Byte](contents))

        # do the actual import
        self.dll = importlib.import_module(dll_path.stem)

    def open(self):
        pass


class LabviewSocketInterface(Device):
    """ Implement the basic sockets-based control interface for labview.
        This implementation uses a transmit and receive socket.

        State sets are implemented by simple ' command value' strings
        and implemented with the 'key' keyword (like VISA strings).
        Subclasses can therefore implement support for commands in
        specific labview VI the same was as in VISA commands by
        assigning the commands implemented in the corresponding labview VI.

        The `resource` argument 
        is the ip address of the host where the labview script
        is running. Use the tx_port and rx_port attributes to set the
        TCP/IP ports where communication is to take place.
    """

    resource = value.NetworkAddress('127.0.0.1', accept_port=False, help='LabView VI host address')
    tx_port = value.int(61551, help='TX port to send to the LabView VI')
    rx_port = value.int(61552, help='TX port to send to the LabView VI')
    delay = value.float(1, help='time to wait after each property trait write or query')
    timeout = value.float(2, help='maximum wait replies before raising TimeoutError')
    rx_buffer_size = value.int(1024, min=1)

    def open(self):
        self.backend = dict(
            tx=socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
            rx=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
                self._console.error('could not close socket ', repr(sock))

    def write(self, msg):
        """ Send a string over the tx socket.
        """
        self._console.debug(f'write {repr(msg)}')
        self.backend['tx'].sendto(msg, (self.resource,
                                        self.tx_port))
        util.sleep(self.delay)

    def set_key(self, key, value, name):
        """ Send a formatted command string to implement property trait control.
        """
        self.write(f'{key} {value}')

    def read(self, convert_func=None):
        """ Receive from the rx socket until `self.rx_buffer_size` samples
            are received or timeout happens after `self.timeout` seconds.

            Optionally, apply the conversion function to the value after
            it is received.
        """
        rx, addr = self.backend['rx'].recvfrom(self.rx_buffer_size)
        if addr is None:
            raise Exception('received no data')
        rx_disp = rx[:min(80, len(rx))] + ('...' if len(rx) > 80 else '')
        self._console.debug(f'read {repr(rx_disp)}')

        key, value = rx.rsplit(' ', 1)
        key = key.split(':', 1)[1].lstrip()
        if convert_func is not None:
            value = convert_func(value)
        return {key: value}

    def clear(self):
        """ Clear any data present in the read socket buffer.
        """
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
    """ A general base class for communication with serial devices.
        Unlike (for example) VISA instruments, there is no
        standardized command format like SCPI. The implementation is
        therefore limited to open and close, which open
        or close a pyserial connection object: the `link` attribute.
        Subclasses can read or write with the link attribute like they
        would any other serial instance.

        A SerialDevice resource string is the same as the
        platform-dependent `port` argument to new serial.Serial
        objects.

        Subclassed devices that need property trait descriptors will need
        to implement state_get and state_set methods in order to define
        how the property trait descriptors set and get operations.
    """

    # Connection value traits
    timeout = value.float(2, min=0, help='Max time to wait for a connection before raising TimeoutError.')
    write_termination = value.bytes(b'\n', help='Termination character to send after a write.')
    baud_rate:int = value.int(9600, min=1, help='Data rate of the physical serial connection.')
    parity = value.bytes(b'N', help='Parity in the physical serial connection.')
    stopbits = value.float(1, min=1, max=2, step=0.5, help='Number of stop bits, one of `[1, 1.5, or 2.]`.')
    xonxoff = value.bool(False, help='`True` to enable software flow control.')
    rtscts = value.bool(False, help='`True` to enable hardware (RTS/CTS) flow control.')
    dsrdtr = value.bool(False, help='`True` to enable hardware (DSR/DTR) flow control.')

    # Overload methods as needed to implement the Device object protocol
    def open(self):
        """ Connect to the serial device with the VISA resource string defined
            in self.resource
        """
        keys = 'timeout', 'parity', 'stopbits', \
               'xonxoff', 'rtscts', 'dsrdtr'
        params = dict([(k, getattr(self, k)) for k in keys])
        self.backend = serial.Serial(
            self.resource, self.baud_rate, **params)
        self._console.debug(f'{repr(self)} connected')

    def close(self):
        """ Disconnect the serial instrument
        """
        self.backend.close()
        self._console.debug(f'{repr(self)} closed')

    @classmethod
    def from_hwid(cls, hwid=None, *args, **connection_params):
        """ Instantiate a new SerialDevice from a windows `hwid' string instead
            of a comport resource. A hwid string in windows might look something
            like:

            r'PCI\\VEN_8086&DEV_9D3D&SUBSYS_06DC1028&REV_21\\3&11583659&1&B3'
        """

        usb_map = cls._map_serial_hwid_to_port()
        if hwid not in usb_map:
            raise Exception(f'Cannot find serial port with hwid {repr(hwid)}')
        return cls(usb_map[hwid], *args, **connection_params)

    @staticmethod
    def list_ports(hwid=None):
        """ List USB serial devices on the computer

            :return: list of port resource information
        """
        from serial.tools import list_ports

        ports = [(port.device, {'hwid': port.hwid, 'description': port.description})
                 for port in list_ports.comports()]
        ports = OrderedDict(ports)

        if hwid is not None:
            ports = [(port, meta) for port, meta in list(
                ports.items()) if meta['id'] == hwid]

        return dict(ports)

    @staticmethod
    def _map_serial_hwid_to_label():
        """ Map of the comports and their names.

            :return: mapping {<comport name>: <comport ID>}
        """
        from serial.tools import list_ports

        return OrderedDict([(port[2], port[1])
                            for port in list_ports.comports()])

    @staticmethod
    def _map_serial_hwid_to_port():
        """ Map of the comports and their names.

            :return: mapping {<comport name>: <comport ID>}
        """
        from serial.tools import list_ports

        return OrderedDict([(port[2], port[0])
                            for port in list_ports.comports()])


class SerialLoggingDevice(SerialDevice):
    """ Manage connection, acquisition, and data retreival on a single GPS device.
        The goal is to make GPS devices controllable somewhat like instruments:
        maintaining their own threads, and blocking during setup or stop
        command execution.

        Listener objects must implement an attach method with one argument
        consisting of the queue that the device manager uses to push data
        from the serial port.
    """

    poll_rate = value.float(0.1, min=0, help='Data retreival rate from the device (in seconds)')
    data_format = value.bytes(b'', help='Data format metadata')
    stop_timeout = value.float(0.5, min=0, help='delay after `stop` before terminating run thread')
    max_queue_size = value.int(100000, min=1, help='bytes to allocate in the data retreival buffer')

    def configure(self):
        """ This is called at the beginning of the logging thread that runs
            on a call to `start`.

            This is a stub that does nothing --- it should be implemented by a
            subclass for a specific serial logger device.
        """
        self._console.debug(
            f'{repr(self)}: no device-specific configuration implemented')

    def start(self):
        """ Start a background thread that acquires log data into a queue.

            :returns: None
        """
        from serial import SerialException

        def accumulate():
            timeout, self.backend.timeout = self.backend.timeout, 0
            q = self._stdout
            stop_event = self._stop
            self._console.debug(f'{repr(self)}: configuring log acquisition')
            self.configure()
            self._console.debug(f'{repr(self)}: starting log acquisition')
            try:
                while stop_event.wait(self.poll_rate) is not True:
                    q.put(self.backend.read(
                        10 * self.baud_rate * self.poll_rate))
            except SerialException as e:
                self._stop.set()
                self.close()
                raise e
            finally:
                self._console.debug(f'{repr(self)} ending log acquisition')
                try:
                    self.backend.timeout = timeout
                except BaseException:
                    pass

        if self.running():
            raise Exception('already running')

        self._stdout = Queue()
        self._stop = Event()
        Thread(target=accumulate).start()

    def stop(self):
        """ Stops the logger acquisition if it is running. Returns silently otherwise.

            :returns: None
        """
        try:
            self._stop.set()
        except BaseException:
            pass

    def running(self):
        """ Check whether the logger is running.

            :returns: `True` if the logger is running
        """
        return hasattr(self, '_stop') and not self._stop.is_set()

    def fetch(self):
        """ Retrieve and return any log data in the buffer.

            :returns: any bytes in the buffer
        """
        ret = b''
        try:
            while True:
                ret += self._stdout.get_nowait()
        except Empty:
            pass
        return ret

    def clear(self):
        """ Throw away any log data in the buffer.
        """
        self.fetch()

    def close(self):
        self.stop()


class TelnetDevice(Device):
    """ A general base class for communication devices via telnet.
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
    resource = value.NetworkAddress('127.0.0.1:23', help='remote address of the telnet server (default port is 23)')
    timeout= value.float(2, min=0, label='s', help='connection timeout')

    @classmethod
    def __imports__(cls):
        global Telnet
        from telnetlib import Telnet

    def open(self):
        """ Open a telnet connection to the host defined
            by the string in self.resource
        """
        host, *port = self.resource.split(':')

        if len(port) > 0:
            port = int(port[0])
        else:
            port = 23

        self.backend = Telnet(self.resource, port=port,
                              timeout=self.timeout)

    def close(self):
        """ Disconnect the telnet connection
        """
        self.backend.close()


class VISADevice(Device):
    r""" .. class:: VISADevice(resource, read_termination='\\n', write_termination='\\n')

        VISADevice instances control VISA instruments using a
        pyvisa backend. Compared to direct use of pyvisa, this
        style of use permits use of labbench device `state`
        goodies for compact, gets code, as well as type checking.

        For example, the following fetches the
        identity string from the remote instrument::

            with VISADevice('USB0::0x2A8D::0x1E01::SG56360004::INSTR') as instr:
                print(inst.identity)

        This is equivalent to the more pyvisa-style use as follows::

            inst = VISADevice('USB0::0x2A8D::0x1E01::SG56360004::INSTR')
            inst.open()
            print(inst.query('*IDN?'))

        Use of `inst` makes it possible to add callbacks to support
        automatic property trait logging, or to build a UI.
    """

    # Settings
    read_termination = value.str('\n', help='end of line string for reads')

    write_termination = value.str('\n', help='end of line string for writes')

    # States
    identity = property_.str(
        key='*IDN', sets=False, cache=True,
        help='identity string reported by the instrument'
    )

    options = property_.str(
        key='*OPT', sets=False, cache=True,
        help='options reported by the instrument'
    )

    @property_.dict(sets=False)
    def status_byte(self):
        """ VISA status byte reported by the instrument """
        code = int(self.query('*STB?'))
        return {'error queue not empty': bool(code & 0b00000100),
                'questionable state': bool(code & 0b00001000),
                'message available': bool(code & 0b00010000),
                'event status flag': bool(code & 0b00100000),
                'service request': bool(code & 0b01000000),
                'top level status summary': bool(code & 0b01000000),
                'operating': bool(code & 0b10000000),
                }

    _rm = None

    @classmethod
    def __imports__(cls):
        if cls._rm is None:
            cls.set_backend('@ivi')

    def _release_remote_control(self):
        # From instrument and pyvisa docs
        self.backend.visalib.viGpibControlREN(self.backend.session,
                                              pyvisa.constants.VI_GPIB_REN_ADDRESS_GTL)

    # Overload methods as needed to implement RemoteDevice
    def open(self):
        """ Connect to the VISA instrument defined by the VISA resource
            set by `self.resource`. The pyvisa backend object is assigned
            to `self.backend`.

            :returns: None

            Instead of calling `open` directly, consider using
            `with` statements to guarantee a call to `close`
            if there is an error. For example, the following
            sets up a opened instance::

                with VISADevice('USB0::0x2A8D::0x1E01::SG56360004::INSTR') as inst:
                    print(inst.identity)
                    print(inst.status_byte)
                    print(inst.options)

            would instantiate a `VISADevice` and guarantee
            a call to `close` either at the successful completion
            of the `with` block, or if there is any exception.
        """

        self.__opc = False

        self.backend = self._rm.open_resource(
            self.resource,
            read_termination=self.read_termination,
            write_termination=self.write_termination
        )

    def close(self):
        """ Disconnect the VISA instrument. If you use a `with` block
            this is handled automatically and you do not need to
            call this method.

            :returns: None
        """
        if not self.isopen or self.backend is None:
            return

        try:
            with contextlib.suppress(pyvisa.errors.VisaIOError):
                self._release_remote_control()
            with contextlib.suppress(pyvisa.Error):
                self.backend.clear()

        except BaseException as e:
            e = str(e)
            if len(e.strip()) > 0:
                # some emulated backends raise empty errors
                self._console.warning('unhandled close error: ' + e)

        finally:
            self.backend.close()

    @classmethod
    def set_backend(cls, backend_name):
        """ Set the pyvisa resource manager for all VISA objects.

            :param backend_name str: '@ni' (the default) or '@py'
            :returns: None
        """

        if backend_name in ('@ivi','@ni'):
            is_ivi = True
            # compatibility layer for changes in pyvisa 1.12
            if 'ivi' in pyvisa.highlevel.list_backends():
                backend_name = '@ivi'
            else:
                backend_name = '@ni'
        else:
            is_ivi = False

        try:
            cls._rm = pyvisa.ResourceManager(backend_name)
        except OSError as e:
            if is_ivi:
                url = r'https://pyvisa.readthedocs.io/en/latest/faq/getting_nivisa.html#faq-getting-nivisa'
                msg = f'could not connect to NI VISA resource manager - see {url}'
                e.args = e.args + (msg,)
            raise e

    @classmethod
    def list_resources(cls):
        """ List the resource strings of the available devices sensed by the VISA backend.
        """
        cls.__imports__()
        return cls._rm.list_resources()

    def write(self, msg):
        """ Send an SCPI command to the device via the pyvisa backend.

            Handles debug logging and adjustments when in overlap_and_block
            contexts as appropriate.

            :param str msg: the SCPI command to send by VISA
            :returns: None
        """
        if self.__opc:
            msg = msg + ';*OPC'
        msg_out = repr(msg) if len(msg) < 1024 else f'({len(msg)} bytes)'
        self._console.debug(f'write {repr(msg_out)}')
        self.backend.write(msg)

    def query(self, msg, timeout=None) -> str:
        """ Query the device with an SCPI command via pyvisa,
            and return the device response string.

            Handles debug logging and adjustments when in overlap_and_block
            contexts as appropriate.

            :param str msg: the SCPI command to send by VISA
            :returns: the response to the query from the device
        """
        if timeout is not None:
            _to, self.backend.timeout = self.backend.timeout, timeout
        msg_out = repr(msg) if len(msg) < 80 else f'({len(msg)} bytes)'
        self._console.debug(f'query {msg_out}')
        try:
            ret = self.backend.query(msg)
        finally:
            if timeout is not None:
                self.backend.timeout = _to
        msg_out = repr(ret) if len(ret) < 80 else f'({len(msg)} bytes)'
        self._console.debug(f'      -> {msg_out}')
        return ret

    def query_ascii_values(self, msg: str, type_, separator=',', container=list, delay=None, timeout=None):
        # pre debug
        if timeout is not None:
            _to, self.backend.timeout = self.backend.timeout, timeout
        msg_out = repr(msg) if len(msg) < 80 else f'({len(msg)} bytes)'
        self._console.debug(f'query_ascii_values {msg_out}')

        try:
            ret = self.backend.query_ascii_values(msg, type_, separator, container, delay)
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

        self._console.debug(f'      -> {logmsg}')

        return ret

    def get_key(self, scpi_key, name=None):
        """ Send an SCPI command to get a property trait value from the
            device. This function
            adds a '?' to match SCPI convention.
            
            This is automatically called for property traits defined with 'key='.

            :param str key: The SCPI command to send
            :param trait: The trait property trait corresponding with the command (ignored)
        """
        if name is not None:
            trait = self._traits[name]

            if not all(isinstance(v,str) for v in trait.remap.values()):
                raise TypeError('VISADevice requires remap values to have type str')

        return self.query(scpi_key + '?').rstrip()

    def set_key(self, scpi_key, value, name=None):
        """ Send an SCPI command to set a property trait value on the
            device using the given key. The command string follows the SCPI convention
            by separating the key and value with a space.

            This is automatically called for property traits defined with 'key='.

            :param str key: The key string to use to  to send
            :param trait: The trait property trait corresponding with the command (ignored)
            :param str value: The value to assign to the parameter
        """
        self.write(f'{scpi_key} {value}')

    def wait(self):
        """ Convenience function to send standard SCPI '\\*WAI'
        """
        self.write('*WAI')

    def preset(self):
        """ Convenience function to send standard SCPI '\\*RST'
        """
        self.write('*RST')

    @contextlib.contextmanager
    def overlap_and_block(self, timeout=None, quiet=False):
        """ A request is sent to the instrument to overlap all of the
            VISA commands written while in this context. At the end
            of the block, wait until the instrument confirms that all
            operations have finished. This is the standard VISA ';\\*OPC'
            and '\\*OPC?' behavior.

            This is meant to be used in `with` blocks as follows::

                with inst.overlap_and_block():
                    inst.write('long running command 1')
                    inst.write('long running command 2')

            The wait happens on leaving the `with` block.

            :param timeout: delay (in milliseconds) on waiting for the instrument to finish the overlapped commands before a TimeoutError after leaving the `with` block. If `None`, use self.backend.timeout.
            :param quiet: Suppress timeout exceptions if this evaluates as True
        """
        self.__opc = True
        yield
        self.__opc = False
        self.query('*OPC?', timeout=timeout)

    class suppress_timeout(contextlib.suppress):
        """ Context manager to suppress timeout exceptions.

            Example::

                with inst.suppress_timeout():
                    inst.write('long running command 1')
                    inst.write('long running command 2')

            If the command 1 raises an exception, then command 2 will (silently)
            not execute.

        """

        EXC = pyvisa.errors.VisaIOError
        CODE = pyvisa.errors.StatusCode.error_timeout

        def __exit__(self, exctype, excinst, exctb):
            return exctype == self.EXC and excinst.error_code == self.CODE


class SimulatedVISADevice(VISADevice):
    """ wrap the pyvisa-sim resource manager (resource '@sim')
        for emulated instruments for the purposes of software testing
        and demo 
    """

    # can only set this when the class is defined
    yaml_source = value.Path('', sets=False, exists=True)

    @classmethod
    def __imports__(cls):
        cls.set_backend(f'{cls.yaml_source.default}@sim')

    def _release_remote_control(self):
        pass


class Win32ComDevice(Device, concurrency=True):
    """ Basic support for calling win32 COM APIs.

        a dedicated background thread. Set concurrency=True to decide whether
        this thread support wrapper is applied to the dispatched Win32Com object.
    """

    # The python wrappers for COM drivers still basically require that
    # threading is performed using the windows COM API. Compatibility with
    # the python GIL is not for the faint of heart. Threading support is
    # instead realized with util.ThreadSandbox, which ensures that all calls
    # to the dispatched COM object block until the previous calls are completed
    # from within.

    com_object = value.str(default='', help='the win32com object string')  # Must be a module

    @classmethod
    def __imports__(cls):
        global win32com
        import win32com
        import win32com.client

    def open(self):
        """ Connect to the win32 com object
        """

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

    def close(self):
        pass