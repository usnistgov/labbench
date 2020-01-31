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

__all__ = ['Testbed', 'Task', 'Multitask']

from . import core, util
from .data import LogAggregator, RelationalTableLogger
from .host import Host, Email
from functools import wraps, update_wrapper
from weakref import proxy
import inspect


def find_devices(testbed):
    devices = {}

    for name, obj in testbed._contexts.items():
        if isinstance(obj, core.Device):
            if name in devices and devices[name] is not obj:
                raise AttributeError(f"name conflict between {repr(obj)} and {repr(devices[name])}")
            devices[name] = obj
        elif isinstance(obj, Testbed):
            new = obj._devices

            conflicts = set(devices.keys()).intersection(new.keys())
            if len(conflicts) > 0:
                raise AttributeError(f"name conflict(s) {tuple(conflicts)} in child testbed {obj}")

            devices.update(new)

    return devices

class Testbed:
    """ A Testbed is a container for devices, data managers, and test steps.

        The Testbed object provides connection management for
        all devices and data managers for `with` block::

            with Testbed() as testbed:
                # use the testbed here
                pass

        For functional validation, it is also possible to open only a subset
        of devices like this::

            testbed = Testbed()
            with testbed.dev1, testbed.dev2:
                # use the testbed.dev1 and testbed.dev2 here
                pass

        The following syntax creates a new Testbed class for an
        experiment:

            import labbench as lb

            class MyTestbed(lb.Testbed):
                db = lb.SQLiteManager()
                sa = MySpectrumAnalyzer()

                spectrogram = Spectrogram(db=db, sa=sa)

        method to define the Device or database manager instances, and
        a custom `startup` method to implement custom code to set up the
        testbed after all Device instances are open.
    """

    _contexts = {}
    __cm = None
    
    # Specify context manager types to open before others
    # and their order
    enter_first = Email, LogAggregator, Host

    def __init_subclass__(cls, concurrent=True):
        cls._contexts = dict(cls._contexts)
        cls._devices = find_devices(cls)
        cls._concurrent = concurrent

    def __init__(self, config=None):
        self.config = config

        for name, context in self._contexts.items():
            context.__init_testbed__(self)

        self.make()

    def __enter__(self):
        cms = dict(self._contexts)

        # Pull any objects of types listed by self.enter_first, in the
        # order of (1) the types listed in self.enter_first, then (2) the order
        # they appear in objs
        first_contexts = dict()
        for cls in self.enter_first:
            for attr, obj in dict(cms).items():
                if isinstance(obj, cls):
                    first_contexts[attr] = cms.pop(attr)

        other_contexts = cms

        # Enforce the ordering set by self.enter_first
        if self._concurrent:
            # Any remaining context managers will be run concurrently if concurrent=True
            others = util.concurrently(name=f'', **other_contexts)
            contexts = dict(first_contexts, others=others)
        else:
            # Otherwise, run them sequentially
            contexts = dict(first_contexts, **other_contexts)

        self.__cm = util.sequentially(name=f'{self.__class__.__qualname__} connections', **contexts)

        self.__cm.__enter__()
        self.startup()
        return self
    
    def __exit__(self, *args):
        try:
            self.cleanup()
        except BaseException as e:
            ex = e
        else:
            ex = None
        finally:
            ret = self.__cm.__exit__(*args)
            if ex is None:
                self.after()
            else:
                raise ex
            return ret
        
    def __repr__(self):
        return f'{self.__class__.__qualname__}()'

    def make(self):
        """ Implement this method in a subclass of Testbed. It should
            set drivers as attributes of the Testbed instance, for example::

                self.dev1 = MyDevice()

            This is called automatically when when the testbed class
            is instantiated.
        """
        pass

    def startup(self):
        """ This is called automatically after open if the testbed is
            opened using the `with` statement block.

            Implement any custom code here in Testbed subclasses to
            implement startup of the testbed given open Device
            instances.
        """
        pass

    def cleanup(self):
        """ This is called automatically immediately before close if the
            testbed is opened using the `with` context block.
            
            This is called even if the `with` context is left as a result of
            an exception.

            Implement any custom code here in Testbed subclasses to
            implement teardown of the testbed given open Device
            instances.
        """
        pass
    
    def after(self):
        """ This is called automatically after open, if no exceptions
            were raised.
        """
        pass


class StepMethod:
    def __init__(self, owner_cls, obj, name, dependencies):
        self.__wrapped__ = obj
        self.label = owner_cls.__name__ + '.' + name
        self.dependencies = dependencies

        update_wrapper(self.__call__, self.__wrapped__,)


class SequencedMethod:
    def __init__(self, owner, name):
        cls = owner.__class__
        obj = getattr(cls, name)

        # introspect to identify device dependencies in each step method
        sig = inspect.signature(obj)
        source = inspect.getsource(obj)
        selfname = next(iter(sig.parameters.keys()))  # the name given to the 'self' method
        deps = tuple((name for name in cls.__annotations__ if selfname + '.' + name in source))

        self.owner = owner
        self.label = cls.__name__ + '.' + name
        self.dependencies = deps
        # self.__call__.__name__  = self.__name__ = obj.__name__
        # self.__qualname__ = obj.__qualname__
        self.__doc__ = obj.__doc__
        self.__name__ = name
        self.__qualname__ = getattr(obj, '__qualname__', obj.__class__.__qualname__)

        self.__wrapped__ = obj
        self.__repr__ = obj.__repr__

    @util.hide_in_traceback
    def __call__(self, *args, **kws):
        # ensure that required devices are connected
        closed = [n for n in self.dependencies \
                  if not getattr(self.owner, n).connected]
        if len(closed) > 0:
            closed = ','.join(closed)
            raise ConnectionError(f"devices {closed} must be connected to invoke {self.label}")

        # invoke the wrapped function
        core.logger.debug(f"{self.label} start")
        with util.stopwatch(f"{self.label}"):
            ret = self.__wrapped__(self.owner, *args, **kws)
            return {} if ret is None else ret

    # methods that implement the "&" operator for test sequence definitions
    def __and__(self, other):
        # python objects call this when the left side of '&' is not a tuple
        return 'concurrent', self, other

    def __rand__(self, other):
        # python objects call this when the left side of '&' is already a tuple
        return other + (self,)

    def __repr__(self):
        return f"<sequenced {repr(self.__wrapped__)[1:-1]}>"

    __str__ = __repr__


class Task(core.InTestbed):
    """ Subclass this to define experimental procedures for groups of Devices in a Testbed.
    """
    __steps__ = dict()
    __wrappers__ = dict()

    def __init_subclass__(cls):
        # By introspection, identify the methods that define test steps
        cls.__steps__ = dict(((k, v) for k, v in cls.__dict__.items()\
                              if callable(v) and k not in Task.__dict__))

        # include annotations from parent classes
        cls.__annotations__ = dict(getattr(super(), '__annotations__', {}),
                                   **getattr(cls, '__annotations__', {}))
        cls.__init__.__annotations__ = cls.__annotations__

        # sentinel values for annotations outside this class
        for name in cls.__annotations__:
            if name not in cls.__dict__:
                setattr(cls, name, None)

    def __init__(self, **devices):
        # a fresh mapping to modify without changing the parent
        devices = dict(devices)

        # set attributes in self
        for name, devtype in self.__annotations__.items():
            try:
                dev = devices.pop(name)
            except KeyError:
                raise KeyError(f"{self.__class__.__qualname__} is missing required argument '{name}'")
            if not isinstance(dev, devtype):
                msg = f"argument '{name}' must be an instance of '{devtype.__qualname__}'"
                raise AttributeError(msg)
            setattr(self, name, dev)

        # if there are remaining unsupported devices, raise an exception
        if len(devices) > 0:
            raise ValueError(f"{tuple(devices.keys())} are invalid arguments")

        # instantiate the wrappers for self.__steps__, and update self
        self.__wrappers__ = {}
        for k in list(self.__steps__.keys()):
            self.__wrappers__[k] = self.__steps__[k] = SequencedMethod(self, k)

    def __getattribute__(self, item):
        if item != '__wrappers__' and item in self.__wrappers__:
            return self.__wrappers__[item]
        else:
            return object.__getattribute__(self, item)

    def __getitem__(self, item):
        return self.__steps__[item]

    def __len__(self):
        return len(self.__steps__)

    def __iter__(self):
        return iter(self.__steps__)

    def items(self):
        return self.__steps__.items()

    def values(self):
        return self.__steps__.values()

    def keys(self):
        return self.__steps__.keys()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def parse_sequence(sequence):
    if isinstance(sequence, (list, tuple)):
        if sequence[0] == 'concurrent':
            invoke = util.concurrently
            sequence = sequence[1:]
        else:
            invoke = util.sequentially
        sequence = list(sequence)

    elif isinstance(sequence, SequencedMethod):
        invoke = util.sequentially
        sequence = [sequence]

    else:
        typename = type(sequence).__qualname__
        raise TypeError(f"object of type '{typename}' is neither a Task method nor a nested tuple/list")

    # step through, if this is a sequence
    for i in range(len(sequence)):
        # validate replace each entry in the sequence with a parsed item
        if isinstance(sequence[i], (list, tuple)):
            sequence[i] = parse_sequence(sequence[i])
        elif not isinstance(sequence[i], SequencedMethod):
            typename = type(sequence).__qualname__
            raise TypeError(f"object of type '{typename}' is neither a "\
                            f"Task method nor a nested tuple/list")

    return invoke, sequence


def collect_defaults(tree):
    """ collect a dictionary of parameter default values

    :param tree: nested list of calls that contains the parsed call tree
    :return: dict keyed on parameter name, with values that are a list of (caller, default_value) pairs.
        default_value is `inspect._empty` if there is no default.
    """

    defaults = {}

    # collect the defaults
    for caller, args in tree:
        if caller in (util.concurrently, util.sequentially):
            funcs = args
        else:
            raise ValueError(f"first element with type '{repr(caller)}' must reference to lb.concurrently or lb.sequentially")

        for func in funcs:
            if isinstance(func, list):
                defaults.update(collect_defaults(func))
                continue
            elif not callable(func):
                raise ValueError(f"object of type '{type(func).__qualname__}' is not callable nor nested list of callables")

            params = iter(inspect.signature(func).parameters.items())

            if inspect.ismethod(func) or isinstance(func, SequencedMethod):
                # skip 'self', if this is a method
                next(params)
            else:
                print('interesting - ', func)

            for _, param in params:
                defaults.setdefault(param.name, []).append((func, param.default))

    return defaults

def call_sequence(spec, kwargs):
    available = set(kwargs.keys())

    def call(func):
        # make a Call object with the subset of `kwargs`
        sig = inspect.signature(func)
        keys = available.intersection(sig.parameters)
        params = dict(((k, kwargs[k]) for k in keys))
        return util.Call(func, **params)

    kws_out = {}
    caller, sequence = spec

    for item in sequence:
        if callable(item):
            name = item.owner.__class__.__qualname__ + '_' + item.__name__
            kws_out[name] = call(item)
        elif isinstance(item, list):
            kws_out[name] = call_sequence(item, kwargs)
        else:
            msg = f"unsupported type '{type(item).__qualname__}' " \
                  f"in call sequence specification"
            raise ValueError(msg)

    return caller, kws_out


@util.hide_in_traceback
def __call__():
    # util._wrap_attribute will munge the call signature above for clean introspection in IDEs
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))
    return self.__call___wrapped(**items)


class Multitask(core.InTestbed):
    def __new__(cls, **sequences):
        # Make a new subclass so that we can change its __call__ signature
        cls = type('Experiment', (cls,), {})

        sequences = dict(((name, parse_sequence(seq)) for name, seq in sequences.items()))

        defaults = collect_defaults(sequences.values())

        params = list(defaults.keys())

        # prune any defaults that are inconsistent across all cases
        for param, uses in tuple(defaults.items()):
            # ensure that default values are
            unique = tuple(set([default for user, default in uses]))
            if len(unique) > 1 or unique == (inspect._empty,):
                del defaults[param]
            else:
                defaults[param] = unique[0]

        util._wrap_attribute(cls, '__call__', __call__, tuple(params), {}, 0)
        cls.__call__.__kwdefaults__ = defaults

        # populate our new object
        obj = object.__new__(cls)
        obj.sequences = sequences
        obj.defaults = defaults
        obj.params = params

        return obj

    def __call__(self, **kwargs):
        ret = {}

        for step, sequence in self.sequences.items():
            caller, step_kws = call_sequence(sequence, kwargs)

            core.logger.info(f"{self.__name__} {step} start")
            with util.stopwatch(f"{self.__name__} {step}"):
                ret.update(caller(**step_kws) or {})

        return ret