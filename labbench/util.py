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

from collections import OrderedDict
from contextlib import contextmanager, _GeneratorContextManager
from . import core
import inspect
import pandas as pd
import os
from queue import Queue, Empty
from sortedcontainers import SortedDict
import sys
from threading import Thread, ThreadError, Event
from functools import wraps
import psutil

from typing import Callable


import time
import traceback

__all__ = ['concurrently', 'sequentially', 'Call', 'ConcurrentException',
           'ConfigStore', 'ConcurrentRunner', 'FilenameDict', 'hash_caller',
           'kill_by_name', 'check_master',
           'retry', 'show_messages', 'sleep', 'stopwatch', 'ThreadSandbox',
           'ThreadEndedByMaster', 'until_timeout']


class ConcurrentException(Exception):
    ''' Raised on concurrency errors in `labbench.concurrently`
    '''


class MasterThreadException(ThreadError):
    ''' Raised to encapsulate a thread raised by the master thread during calls to `labbench.concurrently`
    '''


class ThreadEndedByMaster(ThreadError):
    ''' Raised in a thread to indicate the master thread requested termination
    '''


concurrency_count = 0
stop_request_event = Event()


def sleep(seconds, tick=1.):
    ''' Drop-in replacement for time.sleep that raises ConcurrentException
        if another thread requests that all threads stop.
    '''
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


def check_master():
    ''' Raise ThreadEndedByMaster if the master thread as requested this
        thread to end.
    '''
    sleep(0.)


def retry(exception_or_exceptions, tries=4, delay=0,
          backoff=0, exception_func=lambda: None):
    """ This decorator causes the function call to repeat, suppressing specified exception(s), until a
    maximum number of retries has been attempted.
    - If the function raises the exception the specified number of times, the underlying exception is raised.
    - Otherwise, return the result of the function call.

    :example:
    The following retries the telnet connection 5 times on ConnectionRefusedError::

        import telnetlib
    
        # Retry a telnet connection 5 times if the telnet library raises ConnectionRefusedError
        @retry(ConnectionRefusedError, tries=5)
        def connect(host, port):
            t = telnetlib.Telnet()
            t.open(host,port,5)
            return t


    Inspired by https://github.com/saltycrane/retry-decorator which is released
    under the BSD license.

    :param exception_or_exceptions: Exception (sub)class (or tuple of exception classes) to watch for
    :param tries: number of times to try before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: float
    :param backoff: backoff to multiply to the delay for each retry
    :type backoff: float
    :param exception_func: function to call on exception before the next retry
    :type exception_func: callable
    """
    def decorator(f):
        @wraps(f)
        def do_retry(*args, **kwargs):
            active_delay = delay
            for retry in range(tries):
                try:
                    ret = f(*args, **kwargs)
                except exception_or_exceptions as e:
                    ex = e
                    core.logger.warning(str(e))
                    core.logger.warning(
                        f'{f.__name__} retry (attempt {retry+1}/{tries})')
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


def until_timeout(exception_or_exceptions, timeout, delay=0,
                  backoff=0, exception_func=lambda: None):
    """ This decorator causes the function call to repeat, suppressing specified exception(s), until the
    specified timeout period has expired.
    - If the timeout expires, the underlying exception is raised.
    - Otherwise, return the result of the function call.

    Inspired by https://github.com/saltycrane/retry-decorator which is released
    under the BSD license.


    :example:
    The following retries the telnet connection for 5 seconds on ConnectionRefusedError::

        import telnetlib
    
        @until_timeout(ConnectionRefusedError, 5)
        def connect(host, port):
            t = telnetlib.Telnet()
            t.open(host,port,5)
            return t

    :param exception_or_exceptions: Exception (sub)class (or tuple of exception classes) to watch for
    :param timeout: time in seconds to continue calling the decorated function while suppressing exception_or_exceptions
    :type timeout: float
    :param delay: initial delay between retries in seconds
    :type delay: float
    :param backoff: backoff to multiply to the delay for each retry
    :type backoff: float
    :param exception_func: function to call on exception before the next retry
    :type exception_func: callable
    """
    def decorator(f):
        @wraps(f)
        def do_retry(*args, **kwargs):
            active_delay = delay
            t0 = time.time()
            while time.time() - t0 < timeout:                
                try:
                    ret = f(*args, **kwargs)
                except exception_or_exceptions as e:
                    progress = time.time() - t0
                    ex = e
                    core.logger.warning(str(e))
                    core.logger.warning(
                        f'{f.__name__} retry ({progress}s/{timeout}s elapsed)')
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


@contextmanager
def limit_exception_traceback(limit):
    ''' Limit the tracebacks printed for uncaught
        exceptions to the specified depth. Works for
        regular CPython and IPython interpreters.
    '''

    def limit_hook(type, value, tb):
        traceback.print_exception(type, value, tb, limit=limit)

    if 'ipykernel' in repr(sys.excepthook):
        from ipykernel import kernelapp
        import IPython

        app = kernelapp.IPKernelApp.instance()
        ipyhook = app.shell.excepthook

        is_ipy = (sys.excepthook == ipyhook)
    else:
        is_ipy = False

    if is_ipy:
        def showtb(self, *args, **kws):
            limit_hook(*sys.exc_info())

        oldhook = ipyhook
        IPython.core.interactiveshell.InteractiveShell.showtraceback = showtb
    else:
        oldhook, sys.excepthook = sys.excepthook, limit_hook

    yield

    if is_ipy:
        app.showtraceback = oldhook
    else:
        sys.excepthook = oldhook


def show_messages(minimum_level):
    ''' Configure screen debug message output for any messages as least as important as indicated by `level`.

    :param minimum_level: One of 'debug', 'warning', 'error', or None. If None, there will be no output.
    :return: None
    '''

    import logging
    import coloredlogs

    err_map = {'debug': logging.DEBUG,
               'warning': logging.WARNING,
               'error': logging.ERROR,
               'info': logging.INFO,
               None: None}

    if minimum_level.lower() not in err_map:
        raise ValueError(
            f'message level must be one of {list(err_map.keys())}')
    level = err_map[minimum_level.lower()]

    core.logger.setLevel(logging.DEBUG)

    # Clear out any stale handlers
    if hasattr(core.logger, '_screen_handler'):
        core.logger.removeHandler(core.logger._screen_handler)

    if level is not None:
        core.logger._screen_handler = logging.StreamHandler()
        core.logger._screen_handler.setLevel(level)
        # - %(pathname)s:%(lineno)d'
        log_fmt = '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s'
        #    coloredlogs.install(level='DEBUG', logger=logger)
        core.logger._screen_handler.setFormatter(
            coloredlogs.ColoredFormatter(log_fmt))
        core.logger.addHandler(core.logger._screen_handler)


def kill_by_name(*names):
    ''' Kill one or more running processes by the name(s) of matching binaries.

        :param names: list of names of processes to kill
        :type names: str

        :example:
        >>> # Kill any binaries called 'notepad.exe' or 'notepad2.exe'
        >>> kill_by_name('notepad.exe', 'notepad2.exe')

        :Notes:
        Looks for a case-insensitive match against the Process.name() in the
        psutil library. Though psutil is cross-platform, the naming convention
        returned by name() is platform-dependent. In windows, for example, name()
        usually ends in '.exe'.
    '''
    for pid in psutil.pids():
        try:
            proc = psutil.Process(pid)
            for target in names:
                if proc.name().lower() == target.lower():
                    core.logger.info(f'killing process {proc.name()}')
                    proc.kill()
        except psutil.NoSuchProcess:
            continue


def hash_caller(call_depth=1):
    ''' Use introspection to return an SHA224 hex digest of the caller, which
        is almost certainly unique to the combination of the caller source code
        and the arguments passed it.
    '''
    import inspect
    import hashlib
    import pickle

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
def stopwatch(desc=''):
    ''' Time a block of code using a with statement like this:

    >>> with stopwatch('sleep statement'):
    >>>     time.sleep(2)
    sleep statement time elapsed 1.999s.

    :param desc: text for display that describes the event being timed
    :type desc: str
    :return: context manager
    '''   
    t0 = time.perf_counter()

    try:
        yield
    finally:
        T = time.perf_counter() - t0
        core.logger.info(f'{desc} time elapsed {T:0.3f}s'.lstrip())


class Call(object):
    ''' Wrap a function to apply arguments for threaded calls to `concurrently`.
        This can be passed in directly by a user in order to provide arguments;
        otherwise, it will automatically be wrapped inside `concurrently` to
        keep track of some call metadata during execution.
    '''

    def __init__(self, func, *args, **kws):
        if not callable(func):
            raise ValueError(
                '`func` argument is not callable; did you mistakenly add the () and call it?')
        self.func = func
        self.name = self.func.__name__
        self.args = args
        self.kws = kws
        self.queue = None

        # This is a means for the main thread to raise an exception
        # if this is running in a separate thread
        
    def __repr__(self):
        kws = ','.join([(repr(k)+'='+repr(v)) for k,v in self.kws.items()])
        args = ','.join([repr(v) for v in self.args])
        allargs = ','.join((args,kws))
        qualname = self.func.__module__ + '.' + self.func.__qualname__
        return f'Call({qualname},{allargs})'

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
        ''' Set the queue object used to communicate between threads
        '''
        self.queue = queue

    @classmethod
    def wrap_list_to_dict(cls, name_func_pairs):
        ''' Adjust naming and wrap callables with Call
        '''
        ret = OrderedDict()
        # First, generate the list of callables
        for name, func in name_func_pairs:
            if not isinstance(func, cls):
                func = cls(func)
            if name is None:
                name = func.name
            else:
                func.name = name
            if name in ret:
                msg = f'another callable is already named {repr(name)} - '\
                      f'pass as a keyword argument to specify a different name'
                raise KeyError(msg)
            ret[name] = func
            
        return ret

@contextmanager
def flexible_enter(call_handler: Callable[[dict,list,dict],dict],
                    params: dict,
                    objs: list):
    ''' Handle opening multiple contexts in a single `with` block. This is
        a threadsafe implementation that accepts a handler function that may
        implement any desired any desired type of concurrency in entering
        each context.

        The handler is responsible for sequencing the calls that enter each
        context. In the event of an exception, `flexible_enter` calls
        the __exit__ condition of each context that has already
        been entered.
        
        In the current implementation, __exit__ calls are made sequentially
        (not through call_handler), in the reversed order that each context
        __enter__ was called.
        
        
        :param call_handler: this callable executes entry into each context and any desired concurrency
        :param params: a dictionary of operating parameters (see `concurrently`)
        :param objs: a list of contexts to be entered and dict-like objects to return
        
        :returns: context object for use in a `with` statement
    '''
    t0 = time.perf_counter()
    exits = []

    def enter(c):
        exits.append(lambda *args: c.__exit__(*args))
        c.__enter__()

    try:
        call_objs = []
        for name, obj in objs:
            if name is None:
                name = f'{repr(obj)}.__enter__ at {hex(id(obj.__enter__))}'            
            obj = Call(enter, obj)
            obj.name = name
            call_objs.append((name, obj))     
        
        # Run the __enter__ methods
        call_handler(params, call_objs)

        elapsed = time.perf_counter()-t0
        if elapsed > 0.1 and params['name']:
            core.logger.debug(f'{params["name"]} - entry took {elapsed:0.2f}s')
        yield

    except BaseException:
        exc = sys.exc_info()
    else:
        exc = (None, None, None)

    t0 = time.perf_counter()
    while exits:
        exit = exits.pop()
        try:
            exit(*exc)
        except BaseException:
            exc = sys.exc_info()

    elapsed = time.perf_counter()-t0
    if elapsed > 0.1 and params['name']:
        core.logger.debug(f'{params["name"]} - exit took {elapsed:0.2f}s')

    if exc != (None, None, None):
        # sys.exc_info() may have been
        # changed by one of the exit methods
        # so provide explicit exception info
        for h in core.logger.handlers:
            h.flush()
        raise exc[1]


RUNNERS = {(False, False): None,
           (False, True): 'context',
           (True,False): 'callable',
           (True,True): 'both'}

DIR_DICT = set(dir(dict))

def isdictducktype(cls):
    return set(dir(cls)).issuperset(DIR_DICT)  

def enter_or_call(flexible_caller, objs, kws):
    ''' Extract settings from the keyword arguments flags, decide whether
        `objs` and `kws` should be treated as context managers or callables,
        and then either enter the contexts or call the callables.
    '''

    objs = list(objs)

    # Treat keyword arguments passed as callables should be left as callables;
    # otherwise, override the parameter setting
    params = dict(catch=False,
                  nones=False,
                  traceback_delay=False,
                  flatten=True,
                  name=None)
    
    def merge_inputs(dicts: list, candidates: list):
        ''' Merge nested returns and check for return data key conflicts in
            the callable
        '''
        ret = {}
        for name,d in dicts:
            common = set(ret.keys()).difference(d.keys())
            if len(common) > 0:
                which = ', '.join(common)
                msg = f'attempting to merge results and dict arguments, but the key names ({which}) conflict in nested calls'
                raise KeyError(msg)
            ret.update(d)
                
        conflicts = set(ret.keys()).intersection([n for (n,obj) in candidates])
        if len(conflicts) > 0:
            raise KeyError('keys of conflict in nested return dictionary keys with ')
            
        return ret

    def merge_results(inputs, result):
        for k,v in dict(result).items():
            if isdictducktype(v.__class__):
                conflicts = set(v.keys()).intersection(start_keys)
                if len(conflicts) > 0:
                    conflicts = ','.join(conflicts)
                    raise KeyError(f'conflicts in keys ({conflicts}) when merging return dictionaries')
                inputs.update(result.pop(k))

    # Pull parameters from the passed keywords
    for name in params.keys():
        if name in kws and not callable(kws[name]):
            params[name] = kws.pop(name)

    if params['name'] is None:
        stack = inspect.stack()
        params['name'] = stack[2].code_context[0].strip()
    
    # Combine the position and keyword arguments, and assign labels
    allobjs = list(objs) + list(kws.values())
    names = (len(objs)*[None]) + list(kws.keys())

    candidates = list(zip(names, allobjs))
    del allobjs, names

    dicts = []

    # Make sure candidates are either (1) all context managers
    # or (2) all callables. Decide what type of operation to proceed with.
    runner = None
    for i, (k, obj) in enumerate(candidates):
        # pass through dictionary objects from nested calls
        if isdictducktype(obj.__class__):
            dicts.append(candidates.pop(i))
            continue

        thisone = RUNNERS[(callable(obj) and not isinstance(obj, _GeneratorContextManager)), # Is it callable?
                          (hasattr(obj, '__enter__') or isinstance(obj, _GeneratorContextManager)) # Is it a context manager?
                         ]
            
        if thisone is None:
            msg = f'each argument must be a callable and/or a context manager, '
            
            if k is None:
                msg += f'but given {repr(obj)}'
            else:
                msg += f'but given {k}={repr(obj)}'

            raise TypeError(msg)
        elif runner in (None, 'both'):
            runner = thisone
        else:
            if thisone not in (runner, 'both'):
                raise TypeError(f'cannot run a mixture of context managers and callables')
                
    # Enforce uniqueness in the callable or context manager objects
    candidate_objs = [c[1] for c in candidates]
    if len(set(candidate_objs)) != len(candidate_objs):
        raise ValueError('each callable and context manager must be unique')                

    if runner is None:
        return {}
    elif runner == 'both':
        raise TypeError("all objects supported both calling and context management - not sure which to run")
    elif runner == 'context':
        if len(dicts) > 0:
            raise ValueError('unexpectedly return value dictionary argument for context management')
        return flexible_enter(flexible_caller, params, candidates)
    else:
        ret = merge_inputs(dicts, candidates)
        result = flexible_caller(params, candidates)
        start_keys = set(ret.keys()).union(result.keys())
        if params['flatten']:
            merge_results(ret, result)
        ret.update(result)
        return ret

def concurrently_call(params: dict, name_func_pairs: list) -> dict:
    global concurrency_count

    def traceback_skip(exc_tuple, count):
        ''' Skip the first `count` traceback entries in
            an exception.
        '''
        tb = exc_tuple[2]
        for i in range(count):
            if tb.tb_next is not None:
                tb = tb.tb_next
        return exc_tuple[:2] + (tb,)

    def check_thread_support(func_in):
        ''' Setup threading (concurrent execution only), including
            checks for whether a Device instance indicates it supports
            concurrent execution or not.
        '''
        func = func_in.func if isinstance(func_in, Call) else func_in
        if hasattr(func, '__self__') \
                and isinstance(func.__self__, core.Device):
            if not func.__self__.settings.concurrency_support:
                raise ConcurrentException(
                    f'{func.__self__} does not support concurrency')
        return func_in

    stop_request_event.clear()

    results = {}

    catch = params['catch']
    traceback_delay = params['traceback_delay']

    # Setup calls then funcs
    # Set up mappings between wrappers, threads, and the function to call
    wrappers = Call.wrap_list_to_dict(name_func_pairs)
    threads = OrderedDict([(name, Thread(target=w))
                           for name, w in wrappers.items()])

    # Start threads with calls to each function
    finished = Queue()
    for name, thread in list(threads.items()):
        wrappers[name].set_queue(finished)
        thread.start()
        concurrency_count += 1

    # As each thread ends, collect the return value and any exceptions
    tracebacks = []
    master_exception = None
    
    t0 = time.perf_counter()

    while len(threads) > 0:
        try:
            called = finished.get(timeout=0.25)
        except Empty:
            if time.perf_counter() - t0 > 60*15:
                names = ','.join(list(threads.keys()))
                core.logger.debug(f'{names} threads are still running')
                t0 = time.perf_counter()
            continue
        except BaseException as e:
            master_exception = e
            stop_request_event.set()
            called = None

        if called is None:
            continue
        
        # Below only happens when called is not none
        if master_exception is not None:
            names = ', '.join(list(threads.keys()))
            core.logger.error(
                f'raising {master_exception.__class__.__name__} in main thread after child threads {names} return')

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
                    sys.stderr.write('\nthread exception, but failed to print exception')
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
    if master_exception is not None:        
        for h in core.logger.handlers:
            h.flush()

        for tb in tracebacks:
            try:
                traceback.print_exception(*tb)
            except BaseException:
                sys.stderr.write('\nthread error (fixme to print message)')
                sys.stderr.write('\n')
            
        raise master_exception

    elif len(tracebacks) > 0 and not catch:
        for h in core.logger.handlers:
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

            with limit_exception_traceback(5):
                raise ConcurrentException(
                    f'{len(tracebacks)} call(s) raised exceptions')

    return results


def concurrently(*objs, **kws):
    r''' If `*objs` are callable (like functions), call each of
         `*objs` in concurrent threads. If `*objs` are context
         managers (such as Device instances to be connected),
         enter each context in concurrent threads.

        Multiple references to the same function in `objs` only result in one call. The `catch` and `nones`
        arguments may be callables, in which case they are executed (and each flag value is treated as defaults).

        :param objs:  each argument may be a callable (function or class that defines a __call__ method), or context manager (such as a Device instance)
        :param catch:  if `False` (the default), a `ConcurrentException` is raised if any of `funcs` raise an exception; otherwise, any remaining successful calls are returned as normal
        :param nones: if not callable and evalues as True, includes entries for calls that return None (default is False)
        :param flatten: if `True`, results of callables that returns a dictionary are merged into the return dictionary with update (instead of passed through as dictionaries)
        :param traceback_delay: if `False`, immediately show traceback information on a thread exception; if `True` (the default), wait until all threads finish
        :return: the values returned by each function
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

        :Example: To pass arguments, use the Call wrapper

        >>> def do_something_3 (a,b,c):
        >>>     time.sleep(2)
        >>>     return a,b,c
        >>> rets = concurrent(myfunc1, Call(myfunc3,a,b,c=c))
        >>> rets[do_something_3]
        a, b, c

        **Caveats**

        - Because the calls are in different threads, not different processes,
          this should be used for IO-bound functions (not CPU-intensive functions).
        - Be careful about thread safety.

        When the callable object is a Device method, :func concurrency: checks
        the Device object state.concurrency_support for compatibility
        before execution. If this check returns `False`, this method
        raises a ConcurrentException.

    '''
    
    return enter_or_call(concurrently_call, objs, kws)

def sequentially_call(params: dict, name_func_pairs: list) -> dict:
    ''' Emulate `concurrently_call`, with sequential execution. This is mostly
        only useful to guarantee compatibility with `concurrently_call`
        dictionary-style returns.
    '''
    results = {}

    wrappers = Call.wrap_list_to_dict(name_func_pairs)

    # Run each callable
    for name, wrapper in wrappers.items():
        ret = wrapper()       
        if ret is not None or params['nones']:
            results[name] = ret

    return results


def sequentially(*objs, **kws):
    r''' If `*objs` are callable (like functions), call each of
         `*objs` in the given order. If `*objs` are context
         managers (such as Device instances to be connected),
         enter each context in the given order, and return a context manager
         suited for a `with` statement.
         This is the sequential implementation of the `concurrently` function,
         with a compatible convention of returning dictionaries.

        Multiple references to the same function in `objs` only result in one call. The `nones` 
        argument may be callables in  case they are executed (and each flag value is treated as defaults).

        :param objs:  each argument may be a callable (function, or class that defines a __call__ method), or context manager (such as a Device instance)
        :param kws: dictionary of further callables or context managers, with names set by the dictionary key
        :param nones: if True, include dictionary entries for calls that return None (default is False); left as another entry in `kws` if callable or a context manager
        :param flatten: if `True`, results of callables that returns a dictionary are merged into the return dictionary with update (instead of passed through as dictionaries)        
        :return: a dictionary keyed on the object name containing the return value of each function
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
        >>> rets = concurrent(myfunc1, Call(myfunc3,a,b,c=c))
        >>> rets[do_something_3]
        a, b, c

        **Caveats**

        - Unlike `concurrently`, an exception in a context manager's __enter__ 
          means that any remaining context managers will not be entered.

        When the callable object is a Device method, :func concurrency: checks
        the Device object state.concurrency_support for compatibility
        before execution. If this check returns `False`, this method
        raises a ConcurrentException.
        '''

    return enter_or_call(sequentially_call, objs, kws)


OP_CALL = 'op'
OP_GET = 'get'
OP_SET = 'set'
OP_QUIT = None


class ThreadDelegate(object):
    _sandbox = None
    _obj = None
    _dir = None
    _repr = None

    def __init__(self, sandbox, obj, dir_, repr_):
        self._sandbox = sandbox
        self._obj = obj
        self._dir = dir_
        self._repr = repr_

    def __call__(self, *args, **kws):
        return message(self._sandbox, OP_CALL, self._obj, None, args, kws)

    def __getattribute__(self, name):
        if name in delegate_keys:
            return object.__getattribute__(self, name)
        else:
            return message(self._sandbox, OP_GET, self._obj, name, None, None)

    def __dir__(self):
        return self._dir

    def __repr__(self):
        return f'ThreadDelegate({self._repr})'

    def __setattr__(self, name, value):
        if name in delegate_keys:
            return object.__setattr__(self, name, value)
        else:
            return message(self._sandbox, OP_SET, self._obj, name, value, None)


delegate_keys = set(ThreadDelegate.__dict__.keys()
                    ).difference(object.__dict__.keys())


def message(sandbox, *msg):
    req, rsp = sandbox._requestq, Queue(1)

    # Await and handle request. Exception should be raised in this
    # (main) thread
    req.put(msg + (rsp,), True)
    ret, exc = rsp.get(True)
    if exc is not None:
        raise exc

    return ret


class ThreadSandbox(object):
    ''' Execute all calls in the class in a separate background thread. This
        is intended to work around challenges in threading wrapped win32com APIs.

        Use it as follows:
    
            obj = ThreadSandbox(MyClass(myclassarg, myclasskw=myclassvalue))

        Then use `obj` as a normal MyClass instance.
    '''
    __repr_root__ = 'uninitialized ThreadSandbox'
    __dir_root__ = []
    __thread = None
    _requestq = None

    def __init__(self, factory, should_sandbox_func=None):
        # Start the thread and block until it's ready
        self._requestq = Queue(1)
        ready = Queue(1)
        self.__thread = Thread(target=self.__worker, args=(
            factory, ready, should_sandbox_func))
        self.__thread.start()
        exc = ready.get(True)
        if exc is not None:
            raise exc

    def __worker(self, factory, ready, sandbox_check_func):
        ''' This is the only thread allowed to access the protected object.
        '''

        try:
            root = factory()

            def default_sandbox_check_func(obj):
                try:
                    return inspect.getmodule(obj).__name__.startswith(
                        inspect.getmodule(root).__name__)
                except AttributeError:
                    return False

            if sandbox_check_func is None:
                sandbox_check_func = default_sandbox_check_func

            self.__repr_root__ = repr(root)
            self.__dir_root__ = sorted(
                list(set(dir(root) + list(sandbox_keys))))
            exc = None
        except Exception as e:
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
                    ret = ThreadDelegate(self, ret,
                                         dir_=dir(ret),
                                         repr_=repr(ret))

            # Catch all exceptions
            except Exception as e:
                exc = e
                exc = e

            rsp.put((ret, exc), True)

        core.logger.write('ThreadSandbox worker thread finished')

    def __getattr__(self, name):
        if name in sandbox_keys:
            return object.__getattribute__(self, name)
        else:
            return message(self, OP_GET, None, name, None, None)

    def __setattr__(self, name, value):
        if name in sandbox_keys:
            return object.__setattr__(self, name, value)
        else:
            return message(self, OP_SET, None, name, value, None)

    def _stop(self):
        message(self, OP_QUIT, None, None, None, None, None)

    def _kill(self):
        if isinstance(self.__thread, Thread):
            self.__thread.join(0)
        else:
            raise Exception("no thread running to kill")

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


sandbox_keys = set(ThreadSandbox.__dict__.keys()
                   ).difference(object.__dict__.keys())


class ConfigStore:
    ''' Define dictionaries of configuration settings
        in subclasses of this object. Each dictionary should
        be an attribute of the subclass. The all() class method
        returns a flattened dictionary consisting of all values
        of these dictionary attributes, keyed according to
        '{attr_name}_{attr_key}', where {attr_name} is the
        name of the dictionary attribute and {attr_key} is the
        nested dictionary key.
    '''

    @classmethod
    def all(cls):
        ''' Return a dictionary of all attributes in the class
        '''
        ret = {}
        for k, v in cls.__dict__.items():
            if isinstance(v, dict) and not k.startswith('_'):
                ret.update([(k + '_' + k2, v2) for k2, v2 in v.items()])
        return ret

    @classmethod    
    def frame(cls):
        ''' Return a pandas DataFrame containing all attributes
            in the class
        '''
        df = pd.DataFrame([cls.all()]).T
        df.columns.name = 'Value'
        df.index.name = 'Parameter'
        return df


class FilenameDict(SortedDict):
    ''' Sometimes instrument configuration file can be defined according
        to a combination of several test parameters.

        This class provides a way of mapping these parameters to and from a
        filename string.

        They keys are sorted alphabetically, just as in the underlying
        SortedDict.
    '''

    def __init__(self, *args, **kws):
        if len(args) == 1 and isinstance(args[0], str):
            d = self.from_filename(args[0])
            super(FilenameDict, self).__init__()
            self.update(d)
        elif len(args) >= 1 and isinstance(args[0], (pd.Series, pd.DataFrame)):
            d = self.from_index(*args, **kws)
            super(FilenameDict, self).__init__()
            self.update(d)
        else:
            super(FilenameDict, self).__init__(*args, **kws)

    def __str__(self):
        ''' Convert the dictionary to a filename. It is not guaranteed
            to fit within file name length limit of any filesystem.
        '''
        return ','.join([f'{k}={v}' for k, v in self.items()])

    def __repr__(self):
        return f'{self.__class__.__name__}({repr(str(self))})'

    @classmethod
    def from_filename(cls, filename):
        ''' Convert from a FilenameDict filename string to a FilenameDict
            object.
        '''
        filename = os.path.splitext(os.path.basename(filename))[0]
        fields = filename.split(',')
        fields = [f.split('=') for f in fields]
        return cls(fields)

    @classmethod
    def from_index(cls, df, value=None):
        ''' Make a FilenameDict where the keys are taken from df.index
            and the values are constant values provided.
        '''
        keys = df.index.tolist()
        values = len(keys) * [value]
        return cls(zip(keys, values))


class ConcurrentRunner:
    ''' Concurrently runs all staticmethods or classmethods
        defined in the subclass.

        This has been deprecated - don't use in new code.
    '''

    def __new__(cls):
        def log_wrapper(func, func_name):
            def wrap():
                ret = func()
                core.logger.info(
                    f'concurrent run {cls.__name__}.{func_name} done')
                return ret

            return wrap

        methods = {}

        # Only attributes that are not in this base class
        attrs = set(dir(cls)).difference(dir(ConcurrentRunner))

        for k in sorted(attrs):
            if not k.startswith('_'):
                v = getattr(cls, k)
                clsmeth = inspect.ismethod(v) \
                    and v.__self__ is cls
                staticmeth = callable(v) and not hasattr(v, '__self__')
                if clsmeth or staticmeth:
                    methods[k] = log_wrapper(v, k)
                elif callable(v):
                    core.logger.info(f'skipping {cls.__name__}.{k}')

        core.logger.info(
            f"concurrent run {cls.__name__} {list(methods.keys())}")
        return concurrently(*methods.values())


if __name__ == '__main__':
    def do_something_1():
        print('start 1')
        sleep(1)
        print('end 1')
        return 1

    def do_something_2():
        print('start 2')
        sleep(2)
        print('end 2')
        return 2

    def do_something_3(a, b, c):
        print('start 2')
        sleep(2.5)
        print('end 2')
        return a, b, c

    def do_something_4():
        print('start 1')
        sleep(3)
        raise ValueError('I had an error')
        print('end 1')
        return 1

    results = concurrently(do_something_1, do_something_2, do_something_3)

    print('results were', results)
