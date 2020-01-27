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

from . import core, util
from collections import OrderedDict
import contextlib
import inspect
import os
import psutil
from queue import Queue, Empty
import re
import socket
import select
import sys
from threading import Thread, Event
import warnings

__all__ = ['CommandLineWrapper',
           'DotNetDevice',
           'EmulatedVISADevice',
           'LabviewSocketInterface',
           'SerialDevice',
           'SerialLoggingDevice',
           'TelnetDevice',
           'VISADevice',
           'Win32ComDevice']


class CommandLineWrapper(core.Device):
    """ Virtual device representing for interacting with a command line\
        executable. It supports threaded data logging through standard
        input, standard output, and standard error pipes.

        On open, the `backend` attribute is None. On a
        call to execute(), `backend` becomes is a subprocess instance. When
        EOF is reached on the executable's stdout, the backend is assumed
        terminated and is reset to None.

        When `execute` is called, the program runs in a subprocess.
        The output piped to the command line standard output is queued in a
        background thread. Call read_stdout() to retreive (and clear) this
        queued stdout.
    """

    binary_path: core.Unicode\
        (default=None, allow_none=True, help='path to the file to run')
    timeout: core.Float\
        (default=1, min=0, label='s', help='wait time after close before killing the process')
    arguments: core.List\
        (default=[], help='list of command line arguments to pass into the executable')
    arguments_min: core.Int\
        (default=0, settable=False, min=0, help='minimum extra command line arguments needed to run')

    def __imports__(self):
        global sp
        try:
            import subprocess32 as sp
        except BaseException:
            import subprocess as sp

    def open(self):
        """ The :meth:`open` method implements opening in the
            :class:`Device` object protocol. Call the
            :meth:`execute` method when open to
            execute the binary.
        """
        self.__contexts = {}

        def check_state_change(change={}):
            if self.running():
                raise ValueError(
                    'cannot change command line state traits during execution')

        if not os.path.exists(self.settings.binary_path):
            raise OSError(
                f'executable does not exist at resource=r"{self.settings.binary_path}"')

        self.backend = None

        self._stdout_queue = Queue()

        # Monitor state changes
        states = set(self.settings.traits().keys())\
            .difference(dir(CommandLineWrapper))
        self.settings.observe(check_state_change, tuple(states))

    @property
    @contextlib.contextmanager
    def no_state_arguments(self):
        ''' Use this context manager to disable automatic use of state traits
            in generating argument strings.
        '''
        self.__contexts['use_state_arguments'] = False
        yield
        self.__contexts['use_state_arguments'] = True

    @property
    @contextlib.contextmanager
    def respawn(self):
        ''' Use this context manager to respawning background execution.
        '''
        self.__contexts['respawn'] = True
        yield
        self.__contexts['respawn'] = False

    @property
    @contextlib.contextmanager
    def exception_on_stderr(self):
        ''' Use this context manager to raise exceptions if a process outputs
            to standard error during background execution.
        '''
        self.__contexts['exception_on_stderr'] = True
        yield
        self.__contexts['exception_on_stderr'] = False

    def foreground(self, *extra_arguments, **flags):
        ''' Blocking execution of the binary at the file location
            `self.settings.binary_path`.

            Normally, the command line arguments are determined by
            * appending extra_arguments to the global arguments in self.settings.arguments, and
            * appending pairs of [key,value] from the `flags` dictionary to the
              global flags defined with command flags in local state traits in
              `self.settings`

            Use the self.no_state_arguments context manager to skip these
            global arguments like this::

                with self.no_state_arguments:
                    self.foreground(...)

            :returns: the return code of the process after its completion
        '''
        cmdl = self.__make_commandline(*extra_arguments, **flags)
        try:
            path = os.path.relpath(cmdl[0])
        except ValueError:
            path = cmdl[0]
        self.logger.debug('foreground execute ' +
                          repr(' '.join((path,) + cmdl[1:])))
        cp = sp.run(cmdl, timeout=self.settings.timeout,
                    stdout=sp.PIPE)
        ret = cp.stdout

        if ret:
            lines = ret.decode().splitlines()
            show_count = min(40, len(lines))
            remaining = max(0, len(lines)-show_count)
            for line in lines[:show_count//2]:
                self.logger.debug(f'► {line}')
            if remaining>0:
                self.logger.debug(f'…{remaining} more lines')
            for line in lines[-show_count//2:]:
                self.logger.debug(f'► {line}')
        return ret

    def background(self, *extra_arguments, **flags):
        ''' Run the executable in the background (returning immediately while
            the executable continues running).

            Once the background process is running,

            * Retrieve standard output from the executable with self.read_stdout

            * Write to standard input self.write_stdin

            * Kill the process with self.kill

            * Check whether the process is running with self.running

            Normally, the command line arguments are determined by

            * appending extra_arguments to the global arguments in self.settings.arguments, and

            * appending pairs of [key,value] from the `flags` dictionary to the
              global flags defined with command flags in local state traits in
              `self.settings`

            Use the self.no_state_arguments context manager to skip these
            global arguments like this::

                with self.no_state_arguments:
                    self.background(...)

            :returns: None
        '''
        def stdout_to_queue(fd, cmdl):
            ''' Thread worker to funnel stdout into a queue
            '''
            def readline():
                return fd.readline()
            pid = self.backend.pid
            q = self._stdout_queue
            for line in iter(fd.readline, ''):
                line = line.decode(errors='replace').replace('\r', '')
                if len(line) > 0:
                    q.put(line)
                else:
                    break
            self.backend = None

            # Respawn (or don't)
            if self.__contexts.setdefault(
                    'respawn', False) and not self.__kill:
                self.logger.debug('respawning')
                self._kill_proc_tree(pid)
                spawn(cmdl)
            else:
                self.logger.debug('stdout closed; execution done')

        def stderr_to_exception(fd, cmdl):
            ''' Thread worker to raise exceptions on standard error output
            '''
            for line in iter(fd.readline, ''):
                if self.backend is None:
                    break
                line = line.decode(errors='replace').replace('\r', '')
                if len(line) > 0:
                    self.logger.debug(f'stderr {repr(line)}')
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
            if self.__contexts.setdefault('exception_on_stderr', False):
                Thread(target=lambda: stderr_to_exception(
                    proc.stderr, cmdl)).start()

        # Generate the commandline and spawn
        cmdl = self.__make_commandline(*extra_arguments, **flags)
        try:
            path = os.path.relpath(cmdl[0])
        except ValueError:
            path = cmdl[0]

        self.logger.debug(
            f"background execute: {repr(' '.join((path,) + cmdl[1:]))}")
        self.__kill = False
        spawn(self.__make_commandline(*extra_arguments, **flags))

    def __make_commandline(self, *extra_arguments, **flags):
        ''' Form a list of commandline argument strings for foreground
            or background calls.
        '''
        for k, v in flags.items():
            if not (isinstance(k, str) and isinstance(v, str)):
                raise ValueError(
                    'command line flag keys and values must be strings')

        if self.__contexts.setdefault('use_state_arguments', True):
            all_flags = dict(
                [(k, v) for k, v in self.settings.traits().items() if v.metadata['flag']])

            # Check for invalid flags
            bad_flags = set(flags.keys()).difference(all_flags.keys())
            if len(bad_flags) > 0:
                msg = f'command line keyword arguments {repr(tuple(bad_flags))} not found in {repr(self)}.settings'
                raise ValueError(msg)

            args = list(self.settings.arguments)
            if extra_arguments is not None:
                args = args + list(extra_arguments)
            if self.settings.arguments_min\
               and len(args) < self.settings.arguments_min:
                raise ValueError(
                    f'{repr(self)} given {repr(args)} arguments but needs at least {self.settings.arguments_min}')

            # Set flags according to the arguments
            for k, v in flags.items():
                setattr(self.settings, k, v)
        else:
            args = list(extra_arguments)
            # Set flags according to the arguments
            for k, v in flags.items():
                if not (isinstance(k, str) and isinstance(v, str)):
                    raise ValueError(
                        'command line values and flags must be strings')
                args += [k, v]

        cmd = (self.settings.binary_path,) + tuple(args)

        # Update state traits with the flags
        if self.__contexts['use_state_arguments']:
            for k, trait in self.settings.traits().items():
                v = getattr(self.settings, k)

                if trait.key and v is not None:
                    if isinstance(trait, core.Bool):
                        if v:
                            cmd = cmd + (trait.key,)
                    elif v is not None:
                        cmd = cmd + (trait.key, str(v))

        return cmd

    def read_stdout(self, wait_for=0):
        """ Return string output queued from stdout for a process running
            in the background. This clears the queue.

            Returns an empty string if the command line program has not been
            executed or is empty. Running the command line multiple times overwrites the queue.

            :returns: stdout
        """
        result = ''
        try:
            self._stdout_queue
        except BaseException:
            return result

        try:
            n = 0
            while True:
                line = self._stdout_queue.get(
                    wait_for > 0, timeout=self.settings.timeout)
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
        except core.ConnectionError:
            raise Exception("process not running, could not write no stdin")

    def kill(self):
        """ If a process is running in the background, kill it. Sends a logger
            warning if no process is running.
        """
        self.__kill = True
        backend = self.backend
        if self.running():
            self.logger.debug(f'killing process {backend.pid}') 
            self._kill_proc_tree(backend.pid)

    def running(self):
        """ Return whether the executable is currently running

            :returns: True if running, otherwise False
        """
        # Cache the current running one for a second in case the backend "closes"
        backend = self.backend
        return self.connected \
            and backend is not None \
            and backend.poll() is None

    def clear(self):
        """ Clear queued standard output, discarding any contents
        """
        self.read_stdout()

    def close(self):
        self.kill()

    @staticmethod
    def _kill_proc_tree(pid, including_parent=True):
        ''' Kill the process by pid, and any spawned child processes.
            What a dark metaphor.
        '''
        try:
            parent = psutil.Process(pid)

            # Ever notice that this metaphor is very dark?
            children = parent.children(recursive=False)

            # Get the parent first to prevent respawning
            if including_parent:
                parent.kill()
                parent.wait(5)

            for child in children:
                CommandLineWrapper._kill_proc_tree(child.pid)
        except psutil.NoSuchProcess:
            pass


class DotNetDevice(core.Device):
    """ This Device backend represents a wrapper around a .NET library. It is implemented
        with pythonnet, and handlesimports.

        In order to implement a DotNetDevice subclass:

        * define the attribute `library = <mypythonmodule.wheredllbinariesare>`, the python module with copies of the .NET DLLs are

        * define the attribute `dll_name = "mydllname.dll"`, the name of the DLL binary in the python module above

        When a DotNetDevice is instantiated, it tries to load the dll according to the above specifications.

        Other attributes of DotNetDevice use the following conventions

        * `backend` may be set by a subclass `open` method (otherwise it is left as None)

    """
    library = None  # Must be a module
    dll_name = None
    _dlls = {}

    def __imports__(self):
        """ DotNetDevice loads the DLL; importing in the
            class definition tries to load a lot of DLLs
            on import
            of ssmdevices, which would 1) break platforms
            that do not support the DLL, and 2) waste
            memory, and 3)
        """

        if hasattr(self.__class__, '__dll__') and not hasattr(self, 'dll'):
            self.dll = self.__class__.__dll__
            return

        if self.dll_name is None:
            raise Exception('Need file name of a dll binary')
        if self.library is None:
            raise Exception(
                'Need the python module that shares the library path')
        try:
            import clr
        except ImportError as err:
            if str(err) == 'No module named clr':
                warnings.warn(
                    'could not import pythonnet support via clr module; no support for .NET drivers')
                return None
            else:
                raise err

        import os
        clr.setPreload(False)
        # CPython and .NET libraries: Are they friends?
        clr.AddReference('System.Reflection')
        from System.Reflection import Assembly
        import System

#        if libname is None:
        libname = os.path.splitext(os.path.basename(self.dll_name))[0]

        if hasattr(self.library, '__loader__'):
            """ If the python module is packaged as a .egg file,
                then use some introspection and the module's
                __loader__ to load the contents of the dll
            """
#            relpath = module.__name__.replace('.', os.path.sep)
            self.dll_name = os.path.join(
                self.library.__path__[0], self.dll_name)
            contents = self.library.__loader__.get_data(self.dll_name)
        else:
            path = os.path.join(self.library.__path__[0], self.dll_name)
            with open(path, 'rb') as f:
                contents = f.read()

        name = System.Array[System.Byte](contents)
        self._dlls[self.dll_name] = Assembly.Load(name)
        self.dll = __import__(libname)
        try:
            self.__class__.__dll__ = self.dll
        except AttributeError:  # Race condition =/
            pass

    def open(self):
        pass


class LabviewSocketInterface(core.Device):
    """ Implement the basic sockets-based control interface for labview.
        This implementation uses a transmit and receive socket.

        State sets are implemented by simple ' command value' strings
        and implemented with the 'key' keyword (like VISA strings).
        Subclasses can therefore implement support for commands in
        specific labview VI the same was as in VISA commands by
        assigning the commands implemented in the corresponding labview VI.

        The `resource` argument (which can also be set as `settings.resource`)
        is the ip address of the host where the labview script
        is running. Use the tx_port and rx_port attributes to set the
        TCP/IP ports where communication is to take place.
    """

    resource: core.Address\
        (default='127.0.0.1', help='TCP/IP host address of the LabView VI host')
    tx_port: core.Int\
        (default=61551, help='TX port to send to the LabView VI')
    rx_port: core.Int\
        (default=61552, help='TX port to send to the LabView VI')
    delay: core.Float\
        (default=1, help='time to wait after each state write or query')
    timeout: core.Float\
        (default=2, help='maximum wait replies before raising TimeoutError')
    rx_buffer_size: core.Int\
        (default=1024, min=1)

    def open(self):
        self.backend = {'tx': socket.socket(socket.AF_INET, socket.SOCK_DGRAM),
                        'rx': socket.socket(socket.AF_INET, socket.SOCK_DGRAM)}

        self.backend['rx'].bind((self.settings.resource,
                                 self.settings.rx_port))
        self.backend['rx'].settimeout(self.settings.timeout)
        self.clear()

    def close(self):
        for sock in list(self.backend.values()):
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except BaseException:
                self.logger.error('could not close socket ', repr(sock))

    def write(self, msg):
        """ Send a string over the tx socket.
        """
        self.logger.debug(f'write {repr(msg)}')
        self.backend['tx'].sendto(msg, (self.settings.resource,
                                        self.settings.tx_port))
        util.sleep(self.settings.delay)

    def __command_set__(self, name, command, value):
        """ Send a formatted command string to implement state control.
        """
        self.write(f'{command} {value}')

    def read(self, convert_func=None):
        """ Receive from the rx socket until `self.settings.rx_buffer_size` samples
            are received or timeout happens after `self.timeout` seconds.

            Optionally, apply the conversion function to the value after
            it is received.
        """
        rx, addr = self.backend['rx'].recvfrom(self.settings.rx_buffer_size)
        if addr is None:
            raise Exception('received no data')
        rx_disp = rx[:min(80, len(rx))] + ('...' if len(rx) > 80 else '')
        self.logger.debug(f'read {repr(rx_disp)}')

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


class SerialDevice(core.Device):
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

        Subclassed devices that need state descriptors will need
        to implement state_get and state_set methods in order to define
        how the state descriptors set and get operations.
    """

    # Connection settings
    timeout: core.Float\
        (default=2,min=0, help='Max time to wait for a connection before raising TimeoutError.')
    write_termination: core.Bytes\
        (default=b'\n', help='Termination character to send after a write.')
    baud_rate: core.Int\
        (default=9600,min=1, help='Data rate of the physical serial connection.')
    parity: core.Bytes\
        (default=b'N', help='Parity in the physical serial connection.')
    stopbits: core.Float\
        (default=1, min=1, max=2, step=0.5, help='Number of stop bits, one of `[1., 1.5, or 2.]`.')
    xonxoff: core.Bool\
        (default=False, help='`True` to enable software flow control.')
    rtscts: core.Bool\
        (default=False, help='`True` to enable hardware (RTS/CTS) flow control.')
    dsrdtr: core.Bool\
        (default=False, help='`True` to enable hardware (DSR/DTR) flow control.')

    def __imports__(self):
        global serial
        import serial

    # Overload methods as needed to implement the Device object protocol
    def open(self):
        """ Connect to the serial device with the VISA resource string defined
            in self.settings.resource
        """
        keys = 'timeout', 'parity', 'stopbits',\
               'xonxoff', 'rtscts', 'dsrdtr'
        params = dict([(k, getattr(self, k)) for k in keys])
        self.backend = serial.Serial(
            self.settings.resource, self.baud_rate, **params)
        self.logger.debug(f'{repr(self)} connected')

    def close(self):
        """ Disconnect the serial instrument
        """
        self.backend.close()
        self.logger.debug(f'{repr(self)} closed')

    @classmethod
    def from_hwid(cls, hwid=None, *args, **connection_params):
        """ Instantiate a new SerialDevice from a `hwid' resource instead
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

    poll_rate: core.Float\
        (default=0.1, min=0, help='Data retreival rate from the device (in seconds)')
    data_format: core.Bytes\
        (default=b'', help='Data format metadata')
    stop_timeout: core.Float\
        (default=0.5, min=0, help='delay after `stop` before terminating run thread')
    max_queue_size: core.Int\
        (default=100000, min=1, help='bytes to allocate in the data retreival buffer')

    def configure(self):
        """ This is called at the beginning of the logging thread that runs
            on a call to `start`.

            This is a stub that does nothing --- it should be implemented by a
            subclass for a specific serial logger device.
        """
        self.logger.debug(
            f'{repr(self)}: no device-specific configuration implemented')

    def start(self):
        """ Start a background thread that acquires log data into a queue.

            :returns: None
        """
        from serial import SerialException

        def accumulate():
            timeout, self.backend.timeout = self.backend.timeout, 0
            q = self._queue
            stop_event = self._stop
            self.logger.debug(f'{repr(self)}: configuring log acquisition')
            self.configure()
            self.logger.debug(f'{repr(self)}: starting log acquisition')
            try:
                while stop_event.wait(self.settings.poll_rate) is not True:
                    q.put(self.backend.read(
                        10 * self.settings.baud_rate * self.settings.poll_rate))
            except SerialException as e:
                self._stop.set()
                self.close()
                raise e
            finally:
                self.logger.debug(f'{repr(self)} ending log acquisition')
                try:
                    self.backend.timeout = timeout
                except BaseException:
                    pass

        if self.running():
            raise Exception('already running')

        self._queue = Queue()
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
                ret += self._queue.get_nowait()
        except Empty:
            pass
        return ret

    def clear(self):
        """ Throw away any log data in the buffer.
        """
        self.fetch()

    def close(self):
        self.stop()


class TelnetDevice(core.Device):
    """ A general base class for communication devices via telnet.
        Unlike (for example) VISA instruments, there is no
        standardized command format like SCPI. The implementation is
        therefore limited to open and close, which open
        or close a pyserial connection object: the `backend` attribute.
        Subclasses can read or write with the backend attribute like they
        would any other telnetlib instance.

        A TelnetDevice `resource` string is an IP address. The port is specified
        by `port`. These can be set when you instantiate the TelnetDevice
        or by setting them afterward in `settings`.

        Subclassed devices that need state descriptors will need
        to implement __command_get__ and __command_set__ methods to implement
        the state set and get operations (as appropriate).
    """

    # Connection settings
    timeout: core.Float\
        (default=2, min=0, label='s', help='connection timeout')
    port: core.Int\
        (default=23, min=1)

    def __imports__(self):
        global Telnet
        from telnetlib import Telnet

    def open(self):
        """ Open a telnet connection to the host defined
            by the string in self.settings.resource
        """
        self.backend = Telnet(self.settings.resource, port=self.settings.port,
                              timeout=self.settings.timeout)

    def close(self):
        """ Disconnect the telnet connection
        """
        self.backend.close()


class VISADevice(core.Device):
    r""" .. class:: VISADevice(resource, read_termination='\\n', write_termination='\\n')

        VISADevice instances control VISA instruments using a
        pyvisa backend. Compared to direct use of pyvisa, this
        style of use permits use of labbench device `state`
        goodies for compact, gettable code, as well as type checking.

        For example, the following fetches the
        identity string from the remote instrument::

            with VISADevice('USB0::0x2A8D::0x1E01::SG56360004::INSTR') as instr:
                print(inst.identity)

        This is equivalent to the more pyvisa-style use as follows::

            inst = VISADevice('USB0::0x2A8D::0x1E01::SG56360004::INSTR')
            inst.open()
            print(inst.query('*IDN?'))

        Use of `inst` makes it possible to add callbacks to support
        automatic state logging, or to build a UI.
    """
    
    # Settings
    read_termination: core.Unicode\
        (default='\n', help='end-of-receive termination character')

    write_termination: core.Unicode\
        (default='\n', help='end-of-transmit termination character')

    # States
    identity = core.Unicode\
        (key='*IDN', settable=False, cache=True,
         help='identity string reported by the instrument')

    options = core.Unicode\
        (key='*OPT', settable=False, cache=True,
         help='options reported by the instrument')

    @core.Dict(key='*STB', settable=False)
    def status_byte(self):
        ''' VISA status byte reported by the instrument '''
        code = int(self.query('*STB?'))
        return {'error queue not empty': bool(code & 0b00000100),
                'questionable state': bool(code & 0b00001000),
                'message available': bool(code & 0b00010000),
                'event status flag': bool(code & 0b00100000),
                'service request': bool(code & 0b01000000),
                'master status summary': bool(code & 0b01000000),
                'operating': bool(code & 0b10000000),
                }

    _rm = None
    
    @classmethod
    def __imports__(cls):
        global pyvisa
        import pyvisa
        import pyvisa.constants
        if cls._rm is None:
            cls.set_backend('@ni')

    def __release_remote_control(self):
        # Found this in a mixture of R&S documentation and goofle-fu on pyvisa
        self.backend.visalib.viGpibControlREN(self.backend.session,
                                              pyvisa.constants.VI_GPIB_REN_ADDRESS_GTL)

    # Overload methods as needed to implement RemoteDevice
    def open(self):
        """ Connect to the VISA instrument defined by the VISA resource
            set by `self.settings.resource`. The pyvisa backend object is assigned
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
        # The resource manager is "global" at the class level here
        if VISADevice._rm is None:
             self.set_backend('@ni')

        self.backend = VISADevice._rm.open_resource(self.settings.resource,
                                                    read_termination=self.settings.read_termination,
                                                    write_termination=self.settings.write_termination)

    def close(self):
        """ Disconnect the VISA instrument. If you use a `with` block
            this is handled automatically and you do not need to
            call this method.

            :returns: None
        """
        try:
            with contextlib.suppress(pyvisa.errors.VisaIOError):
                self.__release_remote_control()
            with contextlib.suppress(pyvisa.Error):
                self.backend.clear()
        except BaseException as e:
            self.logger.warning('unhandled close error: ' + str(e))
        finally:
            self.backend.close()

    @classmethod
    def set_backend(cls, backend_name):
        """ Set the pyvisa resource manager for all VISA objects.

            :param backend_name str: '@ni' (the default) or '@py'
            :returns: None
        """
        try:
            cls._rm = pyvisa.ResourceManager(backend_name)
        except OSError as e:
            e.args = e.args + \
            (
                    'labbench VISA support requires NI VISA; is it installed?\nhttp://download.ni.com/support/softlib/visa/NI-VISA/16.0/Windows/NIVISA1600runtime.exe',)
            raise e

    @classmethod
    def list_resources(cls):
        """ List the resource strings of the available devices sensed by the VISA backend.
        """
        cls.__imports__()
        return cls._rm.list_resources()

    def write(self, msg):
        """ Write an SCPI command to the device with pyvisa.

            Handles debug logging and adjustments when in overlap_and_block
            contexts as appropriate.

            :param str msg: the SCPI command to send by VISA
            :returns: None
        """
        if self.__opc:
            msg = msg + ';*OPC'
        msg_out = repr(msg) if len(msg) < 1024 else f'({len(msg)} bytes)'
        self.logger.debug(f'write {repr(msg_out)}')
        self.backend.write(msg)

    def query(self, msg, timeout=None):
        """ Query an SCPI command to the device with pyvisa,
            and return a string containing the device response.

            Handles debug logging and adjustments when in overlap_and_block
            contexts as appropriate.

            :param str msg: the SCPI command to send by VISA
            :returns: the response to the query from the device
        """
        if timeout is not None:
            _to, self.backend.timeout = self.backend.timeout, timeout
        msg_out = repr(msg) if len(msg) < 80 else f'({len(msg)} bytes)'
        self.logger.debug(f'query {repr(msg_out)}')
        try:
            ret = self.backend.query(msg)
        finally:
            if timeout is not None:
                self.backend.timeout = _to
        msg_out = repr(ret) if len(ret) < 80 else f'({len(msg)} bytes)'
        self.logger.debug(f'      -> {msg_out}')
        return ret

    def __command_get__(self, name, command):
        """ Send an SCPI command to get a state value from the
            device. This function
            adds a '?' to match SCPI convention. This is
            automatically called for `state` attributes that
            define a message.

            :param str key: The SCPI command to send
            :param trait: The trait state corresponding with the command (ignored)
        """
        return self.query(command + '?').rstrip()

    def __command_set__(self, name, command, value):
        """ Send an SCPI command to set a state value on the
            device. This function adds a '?' to match SCPI convention. This is
            automatically called for `state` attributes that
            define a message.

            :param str key: The SCPI command to send
            :param trait: The trait state corresponding with the command (ignored)
            :param str value: The value to assign to the parameter
        """
        self.write(command + ' ' + str(value))

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

        def __exit__(self, exctype, excinst, exctb):
            return exctype == pyvisa.errors.VisaIOError \
                and excinst.error_code == pyvisa.errors.StatusCode.error_timeout


class EmulatedVISADevice(core.Device):
    """ Act as a VISA device without dispatching any visa commands
    """

    # Settings
    read_termination: core.Unicode\
        (default='\n', help='end-of-receive termination character')

    write_termination: core.Unicode\
        (default='\n', help='end-of-transmit termination character')

    # States
    @core.Unicode(key='*IDN', settable=False, cache=True)
    def identity(self):
        ''' identity string reported by the instrument '''
        return self.__class__.__qualname__

    @core.Unicode(key='*OPT', settable=False, cache=True)
    def options(self):
        ''' options reported by the instrument '''
        
        return ','.join(((f"{s.name}={repr(self.settings.__previous__[s.name])}"\
                          for s in self.settings)))

    @core.Dict(key='*STB', settable=False)
    def status_byte(self):
        ''' VISA status byte reported by the instrument '''
        return {'error queue not empty': False,
                'questionable state': False,
                'message available': False,
                'event status flag': False,
                'service request': False,
                'master status summary': False,
                'operating': True,
                }

    def __command_get__(self, name, command):
        import numpy as np

        trait = self[name]
        
        if isinstance(trait, core.Bool):
            if trait.remap:
                return np.random.choice(trait.remap.values())
            else:
                return np.random.choice(('TRUE', 'FALSE'))

        elif isinstance(trait, core.Unicode):
            return 'text'
        elif isinstance(trait, core.Float):
            return str(np.random.uniform(low=trait.min, high=trait.max))
        else:
            raise TypeError('No emulated values implemented for trait {repr(trait)}')


    def __command_set__(self, name, command, value):
        pass


class Win32ComDevice(core.Device):
    """ Basic support for calling win32 COM APIs.

        The python wrappers for COM drivers still basically require that
        threading is performed using the windows COM API, and not the python
        threading. Figuring this out with win32com calls within python is
        not for the faint of heart. Threading support is instead realized
        with util.ThreadSandbox, which ensures that all calls to the dispatched
        COM object block until the previous calls are completed from within
        a background thread. Set concurrency=True to decide whether
        this thread support wrapper is applied to the dispatched Win32Com object.
    """

    com_object: \
        core.Unicode(default='',
                     help='the win32com object string')  # Must be a module

    concurrency:\
        core.Bool(default=True,
                     help='whether this implementation supports threading')

    def __imports__(self):
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
            return win32com.client.Dispatch(self.settings.com_object)

        # Oddness for win32 threadsafety
        sys.coinit_flags = 0

        if self.settings.com_object == '':
            raise Exception('settings.com_object needs to be set')

        if self.settings.concurrency:
            self.backend = util.ThreadSandbox(factory, should_sandbox)
        else:
            self.backend = win32com.client.Dispatch(self.settings.com_object)

    def close(self):
        pass
