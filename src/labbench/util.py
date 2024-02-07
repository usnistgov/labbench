from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import logging
import pickle
import re
import sys
import textwrap
import time
import traceback
import types
import typing
from collections.abc import Callable
from contextlib import _GeneratorContextManager, contextmanager
from functools import wraps
from queue import Empty, Queue
from threading import Event, RLock, Thread, ThreadError
from typing import Union

from typing_extensions import Literal, TypeVar

__all__ = [  # "misc"
    'hash_caller',
    'kill_by_name',
    'show_messages',
    'logger',
    'find_methods_in_mro',
    # concurrency and sequencing
    'concurrently',
    'sequentially',
    'lazy_import',
    'Call',
    'ConcurrentException',
    'check_hanging_thread',
    'ThreadSandbox',
    'ThreadEndedByMaster',
    'single_threaded_call_lock',
    # timing and flow management
    'retry',
    'until_timeout',
    'sleep',
    'stopwatch',
    'timeout_iter',
    # wrapper helpers
    'copy_func',
    # traceback scrubbing
    'hide_in_traceback',
    '_force_full_traceback',
    'force_full_traceback',
    # helper objects
    'Ownable',
]

# the base object for labbench loggers
logger = logging.LoggerAdapter(
    logging.getLogger('labbench'),
    dict(
        label='labbench'
    ),  # description of origin within labbench (for screen logs only)
)

_LOG_LEVEL_NAMES = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARN,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}

_LogLevelType = Union[
    Literal['debug'],
    Literal['warning'],
    Literal['error'],
    Literal['info'],
    Literal['critical'],
]


def show_messages(
    minimum_level: Union[_LogLevelType, Literal[False], None], colors: bool = True
):
    """filters logging messages displayed to the console by importance

    Arguments:
        minimum_level: 'debug', 'warning', 'error', or None (to disable all output)
    Returns:
        None
    """

    err_map = {
        'debug': logging.DEBUG,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'info': logging.INFO,
        None: None,
        False: None,
    }

    if minimum_level not in err_map and not isinstance(minimum_level, int):
        raise ValueError(
            f'message level must be a flag {tuple(err_map)} or an integer, not {minimum_level!r}'
        )

    level = (
        err_map[minimum_level.lower()]
        if isinstance(minimum_level, str)
        else minimum_level
    )

    logger.setLevel(level)

    # Clear out any stale handlers
    if hasattr(logger, '_screen_handler'):
        logger.logger.removeHandler(logger._screen_handler)

    if level is None:
        return

    logger._screen_handler = logging.StreamHandler()
    logger._screen_handler.setLevel(level)

    if colors:
        log_fmt = '\x1b[1;30m{levelname:^7s}\x1b[0m \x1b[32m{asctime}.{msecs:03.0f}\x1b[0m • \x1b[34m{label}:\x1b[0m {message}'
    else:
        log_fmt = '{levelname:^7s} {asctime}.{msecs:03.0f} • {label}: {message}'
    formatter = logging.Formatter(log_fmt, style='{')

    logger._screen_handler.setFormatter(formatter)
    logger.logger.addHandler(logger._screen_handler)


show_messages('info')


def repr_as_log_dict(obj: typing.Any) -> dict[str, str]:
    """summarize an object description for the labbench logger"""

    d = dict(
        object=repr(obj),
        origin=type(obj).__qualname__,
        owned_name=obj._owned_name,
    )

    if d['owned_name'] is not None:
        d['label'] = d['owned_name']
    elif repr(obj) == object.__repr__(obj):
        d['label'] = type(obj).__qualname__ + '(...)'
    else:
        txt = repr(obj)
        if len(txt) > 20:
            txt = txt[:-1].split(',')[0] + ')'
        d['label'] = txt

    return d


def callable_logger(func: callable) -> logging.Logger:
    """return the most specialized available logger for the input object"""
    if isinstance(getattr(func, '__self__', None), Ownable):
        return func.__self__._logger
    else:
        return logger


def find_methods_in_mro(
    cls: type[object], name: str, until_cls: Union[type[object], None] = None
) -> list[callable]:
    """list all methods named `name` in `cls` and its parent classes.

    Args:
        cls: the class to introspect
        name: the method to introspect in each subclass
        until_cls: stop introspection after checking this base class

    Returns:
        All unique methods named `name` starting from `cls` and working toward the base classes
    """
    methods = []

    if until_cls is not None and not issubclass(cls, until_cls):
        raise TypeError(
            f'class {until_cls.__qualname__} is not a base class of {cls.__qualname__}'
        )

    for cls in cls.__mro__:
        try:
            this_method = getattr(cls, name)
        except AttributeError:
            continue
        if this_method not in methods:
            methods.append(this_method)
        if cls is until_cls:
            break

    return methods


class Ownable:
    """Subclass to pull in name from an owning class."""

    __objclass__ = None
    _owned_name = None
    _logger = logger

    def __init__(self):
        self._logger = logging.LoggerAdapter(
            logger.logger,
            extra=repr_as_log_dict(self),
        )

    def __set_name__(self, owner_cls, name):
        self.__objclass__ = owner_cls
        self.__name__ = name

    def __get__(self, owner, owner_cls=None):
        return self

    def __owner_init__(self, owner):
        """called on instantiation of the owner (again for its parent owner)"""
        if owner._owned_name is None:
            self._owned_name = self.__name__
        else:
            self._owned_name = owner._owned_name + '.' + self.__name__

    def __owner_subclass__(self, owner_cls):
        """Called after the owner class is instantiated; returns an object to be used in the Rack namespace"""
        # TODO: revisit whether there should be any assignment of _owned_name here
        if self._owned_name is None:
            self._owned_name = self.__name__

        return self

    def __repr__(self):
        if self.__objclass__ is not None:
            cls = type(self)
            ownercls = self.__objclass__

            typename = cls.__module__ + '.' + cls.__name__
            ownedname = ownercls.__qualname__
            return f'<{typename} object at {hex(id(self))} bound to {ownedname} class at {hex(id(ownercls))}>'

        else:
            return object.__repr__(self)

    def __str__(self):
        return self._owned_name or repr(self)


class ConcurrentException(Exception):
    """Raised on concurrency errors in `labbench.concurrently`"""

    thread_exceptions = []


class OwnerThreadException(ThreadError):
    """Raised to encapsulate a thread raised by the owning thread during calls to `labbench.concurrently`"""


class ThreadEndedByMaster(ThreadError):
    """Raised in a thread to indicate the owning thread requested termination"""


concurrency_count = 0
stop_request_event = Event()

TRACEBACK_HIDE_TAG = '🦙 hide from traceback 🦙'

_T = TypeVar('_T')
_Tfunc = Callable[..., typing.Any]


class _ContextManagerType(typing.Protocol):
    def __enter__(self):
        pass

    def __exit__(self, /, type, value, traceback):
        pass


def hide_in_traceback(func: _Tfunc) -> _Tfunc:
    """decorates a method or function to hide it from tracebacks.

    The intent is to remove clutter in the middle of deep stacks in object call stacks.

    To disable this behavior in all methods, call `force_full_traceback(True)`.

    Args:
        func: The function to skip in

    Returns:
        Callable[P, T]: _description_
    """

    def adjust(f: _Tfunc) -> None:
        code_obj = f.__code__
        f.__code__ = f.__code__.replace(
            co_consts=code_obj.co_consts + (TRACEBACK_HIDE_TAG,)
        )

    if not callable(func):
        raise TypeError(f'{func} is not callable')

    if hasattr(func, '__code__'):
        adjust(func)
    elif hasattr(func.__call__, '__code__'):
        adjust(func.__call__)

    return func


def force_full_traceback(force: bool) -> None:
    """configure whether to disable traceback hiding for internal API calls inside labbench"""
    exc_info.debug = force


def _force_full_traceback(force: bool) -> None:
    """configure whether to disable traceback hiding for internal API calls inside labbench"""
    logger.warning(
        'labbench._force_full_traceback has been deprecated - use labbench.util.force_full_traceback instead',
    )
    force_full_traceback(force)


class exc_info:
    """a duck-typed replacement for sys.exc_info that removes
    functions from traceback printouts that are tagged with
    TRACEBACK_HIDE_TAG
    """

    sys_exc_info = sys.exc_info
    debug = False

    @classmethod
    def __call__(cls):
        etype, evalue, tb = cls.sys_exc_info()
        return cls.filter(etype, evalue, tb)

    @classmethod
    def filter(
        cls, etype: type(BaseException), evalue: BaseException, tb: types.TracebackType
    ):
        if cls.debug or tb is None:
            return etype, evalue, tb

        prev_tb = tb
        this_tb = prev_tb.tb_next

        # step through the stack traces
        while this_tb is not None:
            if TRACEBACK_HIDE_TAG in this_tb.tb_frame.f_code.co_consts:
                # filter this traceback
                if this_tb is tb:
                    # shift the starting traceback
                    this_tb = prev_tb = tb = this_tb.tb_next
                else:
                    # skip this traceback
                    this_tb = prev_tb.tb_next = this_tb.tb_next
            else:
                # pass this traceback
                prev_tb, this_tb = this_tb, this_tb.tb_next

        return etype, evalue, tb


if not isinstance(sys.exc_info, exc_info):
    # monkeypatch sys.exc_info
    sys.exc_info = exc_info()


class excepthook:
    sys_excepthook = sys.excepthook

    @classmethod
    def __call__(
        cls, etype: type(BaseException), evalue: BaseException, tb: types.TracebackType
    ):
        return cls.sys_excepthook(*exc_info.filter(type, evalue, tb))


if not isinstance(sys.excepthook, excepthook):
    # monkeypatch sys.excepthook
    sys.excepthook = excepthook()


def copy_func(
    func: _T,
    assigned: tuple[str] = (
        '__module__',
        '__name__',
        '__qualname__',
        '__doc__',
        '__annotations__',
    ),
    updated: tuple[str] = ('__dict__',),
) -> _T:
    """returns a copy of func with specified attributes (following the inspect.wraps arguments).

    This is similar to wrapping `func` with `lambda *args, **kws: func(*args, **kws)`, except
    the returned callable contains a duplicate of the bytecode in `func`. The idea is that the
    returned copy has fresh __doc__, __signature__, etc., which can be changed
    independently of `func`.
    """

    new = types.FunctionType(
        func.__code__,
        func.__globals__,
        func.__name__,
        func.__defaults__,
        func.__closure__,
    )

    for attr in assigned:
        setattr(new, attr, getattr(func, attr))

    for attr in updated:
        getattr(new, attr).update(getattr(func, attr))

    return new


def sleep(seconds: float, tick=1.0):
    """Drop-in replacement for time.sleep that raises ConcurrentException
    if another thread requests that all threads stop.
    """
    t0 = time.time()
    global stop_request_event
    remaining = 0

    while True:
        # Raise ConcurrentException if the stop_request_event is set
        if stop_request_event.wait(min(remaining, tick)):
            raise ThreadEndedByMaster

        remaining = seconds - (time.time() - t0)

        # Return normally if the sleep finishes as requested
        if remaining <= 0:
            return


def check_hanging_thread():
    """Raise ThreadEndedByMaster if the process has requested this
    thread to end.
    """
    sleep(0.0)


@hide_in_traceback
def retry(
    exception_or_exceptions: Union[BaseException, typing.Iterable[BaseException]],
    tries: int = 4,
    *,
    delay: float = 0,
    backoff: float = 0,
    exception_func=lambda *args, **kws: None,
    log: bool = True,
) -> callable[_Tfunc, _Tfunc]:
    """calls to the decorated function are repeated, suppressing specified exception(s), until a
    maximum number of retries has been attempted.

    If the function raises the exception the specified number of times, the underlying exception is raised.
    Otherwise, return the result of the function call.

    Example:

        The following retries the telnet connection 5 times on ConnectionRefusedError::

            import telnetlib


            # Retry a telnet connection 5 times if the telnet library raises ConnectionRefusedError
            @retry(ConnectionRefusedError, tries=5)
            def open(host, port):
                t = telnetlib.Telnet()
                t.open(host, port, 5)
                return t


    Inspired by https://github.com/saltycrane/retry-decorator which is released
    under the BSD license.

    Arguments:
        exception_or_exceptions: Exception (sub)class (or tuple of exception classes) to watch for
        tries: number of times to try before giving up
        delay: initial delay between retries in seconds
        backoff: backoff to multiply to the delay for each retry
        exception_func: function to call on exception before the next retry
        log: whether to emit a log message on the first retry
    """

    def decorator(f):
        @wraps(f)
        @hide_in_traceback
        def do_retry(*args, **kwargs):
            notified = False
            active_delay = delay
            for retry in range(tries):
                try:
                    ret = f(*args, **kwargs)
                except exception_or_exceptions as e:
                    if not notified and log:
                        etype = type(e).__qualname__
                        msg = (
                            f"caught '{etype}' on first call to '{f.__name__}' - repeating the call "
                            f'{tries-1} more times or until no exception is raised'
                        )

                        callable_logger(f).info(msg)

                        notified = True
                    ex = e
                    exception_func(*args, **kwargs)
                    sleep(active_delay)
                    active_delay = active_delay * backoff
                else:
                    break
            else:
                raise ex

            return ret

        return do_retry

    return decorator


@hide_in_traceback
def until_timeout(
    exception_or_exceptions: Union[BaseException, typing.Iterable[BaseException]],
    timeout: float,
    delay: float = 0,
    backoff: float = 0,
    exception_func: callable = lambda: None,
) -> callable[_Tfunc, _Tfunc]:
    """calls to the decorated function are repeated, suppressing specified exception(s), until the
    specified timeout period has expired.

    - If the timeout expires, the underlying exception is raised.
    - Otherwise, return the result of the function call.

    Inspired by https://github.com/saltycrane/retry-decorator which is released
    under the BSD license.

    Example:
        The following retries the telnet connection for 5 seconds on ConnectionRefusedError::

            import telnetlib


            @until_timeout(ConnectionRefusedError, 5)
            def open(host, port):
                t = telnetlib.Telnet()
                t.open(host, port, 5)
                return t

    Arguments:
        exception_or_exceptions: Exception (sub)class (or tuple of exception classes) to watch for
        timeout: time in seconds to continue calling the decorated function while suppressing exception_or_exceptions
        delay: initial delay between retries in seconds
        backoff: backoff to multiply to the delay for each retry
        exception_func: function to call on exception before the next retry
    """

    def decorator(f):
        @wraps(f)
        @hide_in_traceback
        def do_retry(*args, **kwargs):
            notified = False
            active_delay = delay
            t0 = time.time()
            while time.time() - t0 < timeout:
                try:
                    ret = f(*args, **kwargs)
                except exception_or_exceptions as e:
                    progress = time.time() - t0

                    if not notified and timeout - progress > 0:
                        etype = type(e).__qualname__
                        msg = (
                            f"caught '{etype}' in first call to '{f.__name__}' - repeating calls for "
                            f'another {timeout-progress:0.3f}s, or until no exception is raised'
                        )

                        callable_logger(f).info(msg)

                        notified = True

                    ex = e
                    exception_func()
                    sleep(active_delay)
                    active_delay = active_delay * backoff
                else:
                    break
            else:
                raise ex

            return ret

        return do_retry

    return decorator


def timeout_iter(duration):
    """sets a timer for `duration` seconds, yields time elapsed as long as timeout has not been reached"""

    t0 = time.perf_counter()
    elapsed = 0

    while elapsed < duration:
        yield elapsed
        elapsed = time.perf_counter() - t0


def hash_caller(call_depth: int = 1):
    """introspect the caller to return an SHA224 hex digest that
    is almost certainly unique to the combination of the caller source code
    and the arguments passed it.
    """

    thisframe = inspect.currentframe()
    frame = inspect.getouterframes(thisframe)[call_depth]
    arginfo = inspect.getargvalues(frame.frame)

    # get the function object for a simple function
    if frame.function in frame.frame.f_globals:
        func = frame.frame.f_globals[frame.function]
        argnames = arginfo.args

    # get the function object for a method in a class
    elif len(arginfo.args) > 0:  # arginfo.args[0] == 'self':
        name = arginfo.args[0]
        if name not in frame.frame.f_locals:
            raise ValueError('failed to find function object by introspection')
        func = getattr(frame.frame.f_locals[name], frame.function)
        argnames = arginfo.args[1:]

    # there weren't any arguments
    else:
        argnames = []

    args = [arginfo.locals[k] for k in argnames]

    s = inspect.getsource(func) + str(pickle.dumps(args))
    return hashlib.sha224(s.encode('ascii')).hexdigest()


@contextmanager
def stopwatch(
    desc: str = '', threshold: float = 0, logger_level: _LogLevelType = 'info'
):
    """Time a block of code using a with statement like this:

    >>> with stopwatch('sleep statement'):
    >>>     time.sleep(2)
    sleep statement time elapsed 1.999s.

    Arguments:
        desc: text for display that describes the event being timed
        threshold: only show timing if at least this much time (in s) elapsed
    :
    Returns:
        context manager
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t0
        if elapsed >= threshold:
            msg = str(desc) + ' ' if len(desc) else ''
            msg += f'{elapsed:0.3f} s elapsed'

            exc_info = sys.exc_info()
            if exc_info != (None, None, None):
                msg += f' before exception {exc_info[1]}'

            try:
                level = _LOG_LEVEL_NAMES[logger_level]
            except KeyError:
                raise ValueError(
                    f'logger_level must be one of {tuple(_LOG_LEVEL_NAMES.keys())}'
                )

            logger.log(level, msg.lstrip())


class Call:
    """Wrap a function to apply arguments for threaded calls to `concurrently`.
    This can be passed in directly by a user in order to provide arguments;
    otherwise, it will automatically be wrapped inside `concurrently` to
    keep track of some call metadata during execution.
    """

    def __init__(self, func: callable, *args, **kws):
        if not callable(func):
            raise ValueError('`func` argument is not callable')
        self.func = func
        self.name = self.func.__name__
        self.args = args
        self.kws = kws
        self.queue = None

    def rename(self, name):
        self.name = name
        return self

    def __repr__(self):
        args = ','.join(
            [repr(v) for v in self.args]
            + [(k + '=' + repr(v)) for k, v in self.kws.items()]
        )
        qualname = self.func.__module__ + '.' + self.func.__qualname__
        return f'Call({qualname},{args})'

    @hide_in_traceback
    def __call__(self):
        try:
            self.result = self.func(*self.args, **self.kws)
        except BaseException:
            self.result = None
            self.traceback = sys.exc_info()
        else:
            self.traceback = None

        if self.queue is not None:
            self.queue.put(self)
        else:
            return self.result

    def set_queue(self, queue):
        """Set the queue object used to communicate between threads"""
        self.queue = queue

    @classmethod
    def wrap_list_to_dict(cls, name_func_pairs: dict[str, callable]) -> dict[str, Call]:
        """adjusts naming and wraps callables with Call"""
        ret = {}
        # First, generate the list of callables
        for name, func in name_func_pairs:
            try:
                if name is None:
                    if hasattr(func, 'name'):
                        name = func.name
                    elif hasattr(func, '__name__'):
                        name = func.__name__
                    else:
                        raise TypeError(f'could not find name of {func}')

                if not isinstance(func, cls):
                    func = cls(func)

                func.name = name

                if name in ret:
                    msg = (
                        f'another callable is already named {name!r} - '
                        'pass as a keyword argument to specify a different name'
                    )
                    raise KeyError(msg)

                ret[name] = func
            except BaseException:
                raise

        return ret


class MultipleContexts:
    """Handle opening multiple contexts in a single `with` block. This is
    a threadsafe implementation that accepts a handler function that may
    implement any desired any desired type of concurrency in entering
    each context.

    The handler is responsible for sequencing the calls that enter each
    context. In the event of an exception, `MultipleContexts` calls
    the __exit__ condition of each context that has already
    been entered.

    In the current implementation, __exit__ calls are made sequentially
    (not through call_handler), in the reversed order that each context
    __enter__ was called.
    """

    def __init__(
        self, call_handler: Callable[[dict, list, dict], dict], params: dict, objs: list
    ):
        """
            call_handler: one of `sequentially_call` or `concurrently_call`
            params: a dictionary of operating parameters (see `concurrently`)
            objs: a list of contexts to be entered and dict-like objects to return

        Returns:

            context object for use in a `with` statement

        """

        # enter = self.enter
        # def wrapped_enter(name, context):
        #     return enter(name, context)
        # wrapped_enter.__name__ = 'MultipleContexts_enter_' + hex(id(self)+id(call_handler))

        def name(o):
            return

        self.abort = False
        self._entered = {}
        self.__name__ = '__enter__'

        # make up names for the __enter__ objects
        self.objs = [(f'enter_{type(o).__name__}_{hex(id(o))}', o) for _, o in objs]

        self.params = params
        self.call_handler = call_handler
        self.exc = {}

    @hide_in_traceback
    def enter(self, name: str, context: object):
        """
        enter!
        """
        if not self.abort:
            # proceed only if there have been no exceptions
            try:
                context.__enter__()  # start of a context entry thread
            except BaseException:
                self.abort = True
                self.exc[name] = sys.exc_info()
                raise
            else:
                self._entered[name] = context

    @hide_in_traceback
    def __enter__(self):
        calls = [(name, Call(self.enter, name, obj)) for name, obj in self.objs]

        try:
            with stopwatch(
                f"entry into context for {self.params['name']}",
                0.5,
                logger_level='debug',
            ):
                self.call_handler(self.params, calls)
        except BaseException as e:
            try:
                self.__exit__(None, None, None)  # exit any open contexts before raise
            finally:
                raise e

    @hide_in_traceback
    def __exit__(self, *exc):
        with stopwatch(
            f"{self.params['name']} - context exit", 0.5, logger_level='debug'
        ):
            for name in tuple(self._entered.keys())[::-1]:
                context = self._entered[name]

                if name in self.exc:
                    continue

                try:
                    context.__exit__(None, None, None)
                except BaseException:
                    exc = sys.exc_info()
                    traceback.print_exc()

                    # don't overwrite the original exception, if there was one
                    self.exc.setdefault(name, exc)

            contexts = dict(self.objs)
            for name, exc in self.exc.items():
                if name in contexts and name not in self._entered:
                    try:
                        contexts[name].__exit__(None, None, None)
                    except BaseException as e:
                        if e is not self.exc[name][1]:
                            msg = (
                                f'{name}.__exit__ raised {e} in cleanup attempt after another '
                                f'exception in {name}.__enter__'
                            )

                            log_obj = callable_logger(contexts[name].__exit__)

                            log_obj.warning(msg)

        if len(self.exc) == 1:
            exc_info = list(self.exc.values())[0]
            raise exc_info[1]
        elif len(self.exc) > 1:
            ex = ConcurrentException(
                f'exceptions raised in {len(self.exc)} contexts are printed inline'
            )
            ex.thread_exceptions = self.exc
            raise ex
        if exc != (None, None, None):
            # sys.exc_info() may have been
            # changed by one of the exit methods
            # so provide explicit exception info
            for h in logger.logger.handlers:
                h.flush()

            raise exc[1]


RUNNERS = {
    (False, False): None,
    (False, True): 'context',
    (True, False): 'callable',
    (True, True): 'both',
}

DIR_DICT = set(dir(dict))


def isdictducktype(cls):
    return set(dir(cls)).issuperset(DIR_DICT)


def _select_enter_or_call(
    candidate_objs: typing.Iterable[Union[_ContextManagerType, callable]],
) -> str:
    """ensure candidates are either (1) all context managers
    or (2) all callables. Decide what type of operation to proceed with.
    """
    which = None
    for k, obj in candidate_objs:
        thisone = RUNNERS[
            (
                callable(obj) and not isinstance(obj, _GeneratorContextManager)
            ),  # Is it callable?
            (
                hasattr(obj, '__enter__') or isinstance(obj, _GeneratorContextManager)
            ),  # Is it a context manager?
        ]

        if thisone is None:
            msg = 'each argument must be a callable and/or a context manager, '

            if k is None:
                msg += f'but given {obj!r}'
            else:
                msg += f'but given {k}={obj!r}'

            raise TypeError(msg)
        elif which in (None, 'both'):
            which = thisone
        else:
            if thisone not in (which, 'both'):
                raise TypeError('cannot mix context managers and callables')

    # Enforce uniqueness in the (callable or context manager) object
    candidate_objs = [c[1] for c in candidate_objs]
    if len(set(candidate_objs)) != len(candidate_objs):
        raise ValueError('each callable and context manager must be unique')

    return which


@hide_in_traceback
def enter_or_call(
    flexible_caller: callable,
    objs: typing.Iterable[Union[_ContextManagerType, callable]],
    kws: dict[str, typing.Any],
):
    """Extract value traits from the keyword arguments flags, decide whether
    `objs` and `kws` should be treated as context managers or callables,
    and then either enter the contexts or call the callables.
    """

    objs = list(objs)

    # Treat keyword arguments passed as callables should be left as callables;
    # otherwise, override the parameter
    params = dict(
        catch=False,
        nones=False,
        traceback_delay=False,
        flatten=True,
        name=None,
        which='auto',
    )

    def merge_inputs(dicts: list, candidates: list):
        """merges nested returns and check for data key conflicts"""
        ret = {}
        for name, d in dicts:
            common = set(ret.keys()).difference(d.keys())
            if len(common) > 0:
                which = ', '.join(common)
                msg = f'attempting to merge results and dict arguments, but the key names ({which}) conflict in nested calls'
                raise KeyError(msg)
            ret.update(d)

        conflicts = set(ret.keys()).intersection([n for (n, obj) in candidates])
        if len(conflicts) > 0:
            raise KeyError('keys of conflict in nested return dictionary keys with ')

        return ret

    def merge_results(inputs, result):
        for k, v in dict(result).items():
            if isdictducktype(v.__class__):
                conflicts = set(v.keys()).intersection(start_keys)
                if len(conflicts) > 0:
                    conflicts = ','.join(conflicts)
                    raise KeyError(
                        f'conflicts in keys ({conflicts}) when merging return dictionaries'
                    )
                inputs.update(result.pop(k))

    # Pull parameters from the passed keywords
    for name in params.keys():
        if name in kws and not callable(kws[name]):
            params[name] = kws.pop(name)

    if params['name'] is None:
        # come up with a gobbledigook name that is at least unique
        frame = inspect.currentframe().f_back.f_back
        params[
            'name'
        ] = f'<{frame.f_code.co_filename}:{frame.f_code.co_firstlineno} call 0x{hashlib.md5().hexdigest()}>'

    # Combine the position and keyword arguments, and assign labels
    allobjs = list(objs) + list(kws.values())
    names = (len(objs) * [None]) + list(kws.keys())

    candidates = list(zip(names, allobjs))
    del allobjs, names

    dicts = []
    for i, (_, obj) in enumerate(candidates):
        # pass through dictionary objects from nested calls
        if isdictducktype(obj.__class__):
            dicts.append(candidates.pop(i))

    if params['which'] == 'auto':
        which = _select_enter_or_call(candidates)
    else:
        which = params['which']

    if which is None:
        return {}
    elif which == 'both':
        raise TypeError(
            'all objects supported both calling and context management - not sure which to run'
        )
    elif which == 'context':
        if len(dicts) > 0:
            raise ValueError(
                f'unexpected return value dictionary argument for context management {dicts}'
            )
        return MultipleContexts(flexible_caller, params, candidates)
    else:
        ret = merge_inputs(dicts, candidates)
        result = flexible_caller(params, candidates)

        start_keys = set(ret.keys()).union(result.keys())
        if params['flatten']:
            merge_results(ret, result)
        ret.update(result)
        return ret


@hide_in_traceback
def concurrently_call(params: dict, name_func_pairs: list) -> dict:
    global concurrency_count

    def traceback_skip(exc_tuple, count):
        """Skip the first `count` traceback entries in
        an exception.
        """
        tb = exc_tuple[2]
        for i in range(count):
            if tb is not None and tb.tb_next is not None:
                tb = tb.tb_next
        return exc_tuple[:2] + (tb,)

    stop_request_event.clear()

    results = {}

    catch = params['catch']
    traceback_delay = params['traceback_delay']

    # Setup calls then funcs
    # Set up mappings between wrappers, threads, and the function to call
    wrappers = Call.wrap_list_to_dict(name_func_pairs)
    threads = {name: Thread(target=w, name=name) for name, w in wrappers.items()}

    # Start threads with calls to each function
    finished = Queue()
    for name, thread in list(threads.items()):
        wrappers[name].set_queue(finished)
        thread.start()
        concurrency_count += 1

    # As each thread ends, collect the return value and any exceptions
    tracebacks = []
    parent_exception = None

    t0 = time.perf_counter()

    while len(threads) > 0:
        try:
            called = finished.get(timeout=0.25)
        except Empty:
            if time.perf_counter() - t0 > 60 * 15:
                names = ','.join(list(threads.keys()))
                logger.debug(f'{names} threads are still running')
                t0 = time.perf_counter()
            continue
        except BaseException as e:
            parent_exception = e
            stop_request_event.set()
            called = None

        if called is None:
            continue

        # Below only happens when called is not none
        if parent_exception is not None:
            names = ', '.join(list(threads.keys()))
            logger.error(
                f'raising {parent_exception.__class__.__name__} in main thread after child threads {names} return'
            )

        # if there was an exception that wasn't us ending the thread,
        # show messages
        if called.traceback is not None:
            tb = traceback_skip(called.traceback, 1)

            if called.traceback[0] is not ThreadEndedByMaster:
                #                exception_count += 1
                tracebacks.append(tb)
                last_exception = called.traceback[1]

            if not traceback_delay:
                try:
                    traceback.print_exception(*tb)
                except BaseException as e:
                    sys.stderr.write(
                        '\nthread exception, but failed to print exception'
                    )
                    sys.stderr.write(str(e))
                    sys.stderr.write('\n')
        else:
            if params['nones'] or called.result is not None:
                results[called.name] = called.result

        # Remove this thread from the dictionary of running threads
        del threads[called.name]
        concurrency_count -= 1

    # Clear the stop request, if there are no other threads that
    # still need to exit
    if concurrency_count == 0 and stop_request_event.is_set():
        stop_request_event.clear()

    # Raise exceptions as necessary
    if parent_exception is not None:
        for h in logger.logger.handlers:
            h.flush()

        for tb in tracebacks:
            try:
                traceback.print_exception(*tb)
            except BaseException:
                sys.stderr.write('\nthread error (fixme to print message)')
                sys.stderr.write('\n')

        raise parent_exception

    elif len(tracebacks) > 0 and not catch:
        for h in logger.logger.handlers:
            h.flush()
        if len(tracebacks) == 1:
            raise last_exception
        else:
            for tb in tracebacks:
                try:
                    traceback.print_exception(*tb)
                except BaseException:
                    sys.stderr.write('\nthread error (fixme to print message)')
                    sys.stderr.write('\n')

            ex = ConcurrentException(f'{len(tracebacks)} call(s) raised exceptions')
            ex.thread_exceptions = tracebacks
            raise ex

    return results


@hide_in_traceback
def concurrently(*objs, **kws):
    r"""If `*objs` are callable (like functions), call each of
     `*objs` in concurrent threads. If `*objs` are context
     managers (such as Device instances to be connected),
     enter each context in concurrent threads.

    Multiple references to the same function in `objs` only result in one call. The `catch` and `nones`
    arguments may be callables, in which case they are executed (and each flag value is treated as defaults).

    Arguments:
        objs:  each argument may be a callable (function or class that defines a __call__ method), or context manager (such as a Device instance)
        catch:  if `False` (the default), a `ConcurrentException` is raised if any of `funcs` raise an exception; otherwise, any remaining successful calls are returned as normal
        nones: if not callable and evalues as True, includes entries for calls that return None (default is False)
        flatten: if `True`, results of callables that returns a dictionary are merged into the return dictionary with update (instead of passed through as dictionaries)
        traceback_delay: if `False`, immediately show traceback information on a thread exception; if `True` (the default), wait until all threads finish
        operation: if 'auto' (default), try to determine automatically; otherwise, 'context' or 'call'
    Returns:
        the values returned by each call
    :rtype: dictionary keyed by function name

    Here are some examples:

    :Example: Call each function `myfunc1` and `myfunc2`, each with no arguments:

    >>> def do_something_1 ():
    >>>     time.sleep(0.5)
    >>>     return 1
    >>> def do_something_2 ():
    >>>     time.sleep(1)
    >>>     return 2
    >>> rets = concurrent(myfunc1, myfunc2)
    >>> rets[do_something_1]

    :Example: To pass arguments, use the Call wrapper

    >>> def do_something_3 (a,b,c):
    >>>     time.sleep(2)
    >>>     return a,b,c
    >>> rets = concurrent(myfunc1, Call(myfunc3, a, b, c=c))
    >>> rets[do_something_3]
    a, b, c

    **Caveats**

    - Because the calls are in different threads, not different processes,
      this should be used for IO-bound functions (not CPU-intensive functions).
    - Be careful about thread-safety.

    """

    return enter_or_call(concurrently_call, objs, kws)


@hide_in_traceback
def sequentially_call(params: dict, name_func_pairs: list) -> dict:
    """Emulate `concurrently_call`, with sequential execution. This is mostly
    only useful to guarantee compatibility with `concurrently_call`
    dictionary-style returns.
    """
    results = {}

    wrappers = Call.wrap_list_to_dict(name_func_pairs)

    # Run each callable
    for name, wrapper in wrappers.items():
        ret = wrapper()
        if wrapper.traceback is not None:
            raise wrapper.traceback[1]
        if ret is not None or params['nones']:
            results[name] = ret

    return results


@hide_in_traceback
def sequentially(*objs, **kws):
    r"""If `*objs` are callable (like functions), call each of
     `*objs` in the given order. If `*objs` are context
     managers (such as Device instances to be connected),
     enter each context in the given order, and return a context manager
     suited for a `with` statement.
     This is the sequential implementation of the `concurrently` function,
     with a compatible convention of returning dictionaries.

    Multiple references to the same function in `objs` only result in one call. The `nones`
    argument may be callables in  case they are executed (and each flag value is treated as defaults).

    Arguments:
        objs:  callables or context managers or Device instances for connections
        kws: dictionary of additional callables or Device instances for connections
        nones: `True` to include dictionary entries for calls that return None (default: False)
        flatten: `True` to flatten any `dict` return values into the return dictionary
    Returns:
        a dictionary keyed on the object name containing the return value of each function
    :rtype: dictionary of keyed by function

    Here are some examples:

    :Example: Call each function `myfunc1` and `myfunc2`, each with no arguments:

    >>> def do_something_1 ():
    >>>     time.sleep(0.5)
    >>>     return 1
    >>> def do_something_2 ():
    >>>     time.sleep(1)
    >>>     return 2
    >>> rets = concurrent(myfunc1, myfunc2)
    >>> rets[do_something_1]
    1

    :Example: To pass arguments, use the Call wrapper

    >>> def do_something_3 (a,b,c):
    >>>     time.sleep(2)
    >>>     return a,b,c
    >>> rets = concurrent(myfunc1, Call(myfunc3, a, b, c=c))
    >>> rets[do_something_3]
    a, b, c

    **Caveats**

    - Unlike `concurrently`, an exception in a context manager's __enter__
      means that any remaining context managers will not be entered.

    """

    if kws.get('catch', False):
        raise ValueError('catch=True is not supported by sequentially')

    return enter_or_call(sequentially_call, objs, kws)


OP_CALL = 'op'
OP_GET = 'get'
OP_SET = 'set'
OP_QUIT = None


class ThreadDelegate:
    _sandbox = None
    _obj = None
    _dir = None
    _repr = None

    def __init__(self, sandbox, obj, dir_, repr_):
        self._sandbox = sandbox
        self._obj = obj
        self._dir = dir_
        self._repr = repr_

    @hide_in_traceback
    def __call__(self, *args, **kws):
        return message(self._sandbox, OP_CALL, self._obj, None, args, kws)

    def __getattribute__(self, name):
        if name in _delegate_keys:
            return object.__getattribute__(self, name)
        else:
            return message(self._sandbox, OP_GET, self._obj, name, None, None)

    def __dir__(self):
        return self._dir

    def __repr__(self):
        return f'ThreadDelegate({self._repr})'

    def __setattr__(self, name, value):
        if name in _delegate_keys:
            return object.__setattr__(self, name, value)
        else:
            return message(self._sandbox, OP_SET, self._obj, name, value, None)


_delegate_keys = ThreadDelegate.__dict__.keys() - object.__dict__.keys()


@hide_in_traceback
def message(sandbox, *msg):
    req, rsp = sandbox._requestq, Queue(1)

    # Await and handle request. Exception should be raised in this
    # (main) thread
    req.put(msg + (rsp,), True)
    ret, exc = rsp.get(True)
    if exc is not None:
        raise exc

    return ret


class ThreadSandbox:
    """Wraps accesses to object attributes in a separate background thread. This
    is intended to work around challenges in threading wrapped win32com APIs.

    Example:

        obj = ThreadSandbox(MyClass(myclassarg, myclasskw=myclassvalue))

    Then, use `obj` as a normal MyClass instance.
    """

    __repr_root__ = 'uninitialized ThreadSandbox'
    __dir_root__ = []
    __thread = None
    _requestq = None

    def __init__(self, factory, should_sandbox_func=None):
        # Start the thread and block until it's ready
        self._requestq = Queue(1)
        ready = Queue(1)
        self.__thread = Thread(
            target=self.__worker, args=(factory, ready, should_sandbox_func)
        )
        self.__thread.start()
        exc = ready.get(True)
        if exc is not None:
            raise exc

    @hide_in_traceback
    def __worker(self, factory, ready, sandbox_check_func):
        """This is the only thread allowed to access the protected object."""

        try:
            root = factory()

            def default_sandbox_check_func(obj):
                try:
                    return inspect.getmodule(obj).__name__.startswith(
                        inspect.getmodule(root).__name__
                    )
                except AttributeError:
                    return False

            if sandbox_check_func is None:
                sandbox_check_func = default_sandbox_check_func

            self.__repr_root__ = repr(root)
            self.__dir_root__ = sorted(list(set(dir(root) + list(_sandbox_keys))))
            exc = None
        except BaseException as e:
            exc = e
        finally:
            ready.put(exc, True)
        if exc:
            return

        # Do some sort of setup here
        while True:
            ret = None
            exc = None

            op, obj, name, args, kws, rsp = self._requestq.get(True)

            # End if that's good
            if op is OP_QUIT:
                break
            if obj is None:
                obj = root

            # Do the op
            try:
                if op is OP_GET:
                    ret = getattr(obj, name)
                elif op is OP_CALL:
                    ret = obj(*args, **kws)
                elif op is OP_SET:
                    ret = setattr(obj, name, args)

                # Make it a delegate if it needs to be protected
                if sandbox_check_func(ret):
                    ret = ThreadDelegate(self, ret, dir_=dir(ret), repr_=repr(ret))

            # Catch all exceptions
            except Exception as e:
                exc = e
                exc = e

            rsp.put((ret, exc), True)

        logger.debug('ThreadSandbox worker thread finished')

    @hide_in_traceback
    def __getattr__(self, name):
        if name in _sandbox_keys:
            return object.__getattribute__(self, name)
        else:
            return message(self, OP_GET, None, name, None, None)

    @hide_in_traceback
    def __setattr__(self, name, value):
        if name in _sandbox_keys:
            return object.__setattr__(self, name, value)
        else:
            return message(self, OP_SET, None, name, value, None)

    def _stop(self):
        message(self, OP_QUIT, None, None, None, None, None)

    def _kill(self):
        if isinstance(self.__thread, Thread):
            self.__thread.join(0)
        else:
            raise Exception('no thread running to kill')

    def __del__(self):
        try:
            del_ = message(self, OP_GET, None, '__del__', None, None)
        except AttributeError:
            pass
        else:
            del_()
        finally:
            try:
                self._kill()
            except BaseException:
                pass

    def __repr__(self):
        return f'ThreadSandbox({self.__repr_root__})'

    def __dir__(self):
        return self.__dir_root__


_sandbox_keys = ThreadSandbox.__dict__.keys() - object.__dict__.keys()


class single_threaded_call_lock:
    """decorates a function to ensure executes in only one thread at a time.

    This is a low-performance way to ensure thread-safety.
    """

    def __new__(cls, func):
        obj = super().__new__(cls)
        obj.func = func
        obj.lock = RLock()
        obj = wraps(func)(obj)
        return obj

    @hide_in_traceback
    def __call__(self, *args, **kws):
        self.lock.acquire()

        # no other threads are running self.func; invoke it in this one
        try:
            ret = self.func(*args, **kws)
        finally:
            self.lock.release()

        return ret


# otherwise turns out not to be thread-safe
@single_threaded_call_lock
def lazy_import(module_name: str):
    """postponed import of the module with the specified name.

    The import is not performed until the module is accessed in the code. This
    reduces the total time to import labbench by waiting to import the module
    until it is used.
    """
    # see https://docs.python.org/3/library/importlib.html#implementing-lazy-imports
    try:
        ret = sys.modules[module_name]
        return ret
    except KeyError:
        pass

    spec = importlib.util.find_spec(module_name)
    if spec is None:
        raise ImportError(f'no module found named "{module_name}"')
    spec.loader = importlib.util.LazyLoader(spec.loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ttl_cache:
    def __init__(self, timeout):
        self.timeout = timeout
        self.call_timestamp = None
        self.last_value = {}

    def __call__(self, func: _Tfunc) -> _Tfunc:
        @wraps(func)
        @hide_in_traceback
        def wrapper_decorator(*args, **kws):
            time_elapsed = time.perf_counter() - (self.call_timestamp or 0)
            key = tuple(args), tuple(kws.keys()), tuple(kws.values())

            if (
                self.call_timestamp is None
                or time_elapsed > self.timeout
                or key not in self.last_value
            ):
                ret = self.last_value[key] = func(*args, **kws)
                self.call_timestamp = time.perf_counter()
            else:
                ret = self.last_value[key]

            return ret

        return wrapper_decorator


def accessed_attributes(method: _Tfunc) -> tuple[str]:
    """enumerate the attributes of the parent class accessed by `method`

    :method: callable that is a method or defined in a class
    Returns:
        tuple of attribute names
    """

    # really won't work unless method is a callable defined inside a class
    if not inspect.isroutine(method):
        raise ValueError(f'{method} is not a method')
    elif not inspect.ismethod(method) and '.' not in method.__qualname__:
        raise ValueError(f'{method} is not defined in a class')

    # parse into a code tree
    source = inspect.getsource(method)

    # filter out lines that start with comments, which have no tokens and confuse textwrap.dedent
    source = '\n'.join(re.findall('^[ \t\r\n]*[^#].*', source, re.MULTILINE))

    parsed = ast.parse(textwrap.dedent(source))
    if len(parsed.body) > 1:
        # this should not be possible
        raise Exception('ast parsing gave unexpected extra nodes')

    # pull out the function node and the name for the class instance
    func = parsed.body[0]
    if not isinstance(func, ast.FunctionDef):
        raise SyntaxError("this object doesn't look like a method")

    self_name = func.args.args[0].arg

    def isselfattr(node):
        return (
            isinstance(node, ast.Attribute)
            and getattr(node.value, 'id', None) == self_name
        )

    return tuple({node.attr for node in ast.walk(func) if isselfattr(node)})


if typing.TYPE_CHECKING:
    # we have to delay this import until after lazy_import is defined
    import psutil
else:
    psutil = lazy_import('psutil')


def kill_by_name(*names):
    """Kill one or more running processes by the name(s) of matching binaries.

    Arguments:
        names: list of names of processes to kill
    :type names: str

    Example:
        >>> # Kill any binaries called 'notepad.exe' or 'notepad2.exe'
        >>> kill_by_name('notepad.exe', 'notepad2.exe')

    Notes:
        Looks for a case-insensitive match against the Process.name() in the
        psutil library. Though psutil is cross-platform, the naming convention
        returned by name() is platform-dependent. In windows, for example, name()
        usually ends in '.exe'.
    """
    for pid in psutil.pids():
        try:
            proc = psutil.Process(pid)
            for target in names:
                if proc.name().lower() == target.lower():
                    logger.info(f'killing process {proc.name()}')
                    proc.kill()
        except psutil.NoSuchProcess:
            continue
