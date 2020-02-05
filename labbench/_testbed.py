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

from . import _core as core
from . import util as util
from .data import LogAggregator, RelationalTableLogger
from ._host import Host, Email
from functools import wraps, update_wrapper
from weakref import proxy
import inspect
import time


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
        cls._concurrent = concurrent
        cls._devices = find_devices(cls)
        for name, c in dict(cls._contexts).items():
            c = c.__init_testbed_class__(cls)
            cls._contexts[name] = c
            setattr(cls, name, c)


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


class Step:
    """
    Wrapper function that Task applies to its methods, permitting to permit '&' notation for Multitask definitions
    """
    def __init__(self, owner, name):
        cls = owner.__class__
        obj = getattr(cls, name)
        self.owner = owner

        # note the devices needed to execute this function
        available = {getattr(self.owner, name) for name in getattr(self.owner, '__annotations__', {})}
        self.dependencies = available.intersection(util.accessed_attributes(obj))
        self.args = list(inspect.signature(obj).parameters)[1:]
        self.parameters = list(inspect.signature(obj).parameters.values())[1:]

        # self.__call__.__name__  = self.__name__ = obj.__name__
        # self.__qualname__ = obj.__qualname__
        self.__doc__ = obj.__doc__
        self.__name__ = name
        self.__qualname__ = getattr(obj, '__qualname__', obj.__class__.__qualname__)

        self.__wrapped__ = obj
        self.__repr__ = obj.__repr__

    def extended_defaults(self):
        return dict([(k, v.default) for k, v in zip(self.extended_args(), self.parameters)])

    def extended_args(self):
        return [(self.owner.__name__ + '_' + name) for name in self.args]

    def extended_call(self, *args, **kws):
        i = len(self.owner.__name__)+1
        # remove the leading f"{self.owner.__name__}"
        kws = dict(((k[i:], v) for k, v in kws.items()))
        return self.__call__(*args, **kws)

    @util.hide_in_traceback
    def __call__(self, *args, **kws):
        # ensure that required devices are connected
        closed = [name for name in self.dependencies
                  if not getattr(self.owner, name).connected]
        if len(closed) > 0:
            closed = ','.join(closed)
            label = self.__class__.__qualname__ + '.' + self.__name__
            raise ConnectionError(f"devices {closed} must be connected to invoke {self.label}")

        # invoke the wrapped function
        owner_name = str(self.owner)
        t0 = time.perf_counter()
        ret = self.__wrapped__(self.owner, *args, **kws)
        elapsed = time.perf_counter()-t0
        if elapsed > 0.1:
            core.logger.debug(f"{owner_name} completed in {elapsed:0.2f}s")
        return {} if ret is None else ret

    # implement the "&" operator to define concurrent steps for Multitask
    def __and__(self, other):
        # python objects call this when the left side of '&' is not a tuple
        return 'concurrent', self, other

    def __rand__(self, other):
        # python objects call this when the left side of '&' is already a tuple
        return other + (self,)

    def __repr__(self):
        return f"<method {repr(self.__wrapped__)[1:-1]}>"

    __str__ = __repr__


class Task(util.InTestbed):
    """ Subclass this to define experimental procedures for groups of Devices in a Testbed.
    """
    __steps__ = dict()

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

        # set devices in self
        for name, devtype in self.__annotations__.items():
            try:
                dev = devices.pop(name)
            except KeyError:
                raise KeyError(f"{self.__class__.__qualname__} is missing required argument '{name}'")
            if not isinstance(dev, devtype):
                msg = f"argument '{name}' is not an instance of '{devtype.__qualname__}'"
                raise AttributeError(msg)
            setattr(self, name, dev)

        # if there are remaining unsupported devices, raise an exception
        if len(devices) > 0:
            raise ValueError(f"{tuple(devices.keys())} are invalid arguments")

        # replace self.__steps__ with new mapping of wrappers
        self.__steps__ = dict(((k, Step(self, k)) for k in self.__steps__))

    def __getattribute__(self, item):
        if item != '__steps__' and item in self.__steps__:
            return self.__steps__[item]
        else:
            return super().__getattribute__(item)

    def __getitem__(self, item):
        return self.__steps__[item]

    def __len__(self):
        return len(self.__steps__)

    def __iter__(self):
        return (getattr(self, k) for k in self.__steps__)

    def __repr__(self):
        return repr(self.__wrapped__)

    def __str__(self):
        if hasattr(self, '__name__'):
            return self.__objclass__.__qualname__ + '.' + self.__name__
        else:
            return repr(self)


def parse_sequence(sequence):
    if isinstance(sequence, (list, tuple)):
        if sequence[0] == 'concurrent':
            invoke = util.concurrently
            sequence = sequence[1:]
        else:
            invoke = util.sequentially
        sequence = list(sequence)

    elif isinstance(sequence, Step):
        invoke = util.sequentially
        sequence = [sequence]

    elif isinstance(sequence, util.InTestbed) and callable(sequence):
        invoke = util.sequentially
        sequence = [Step(sequence, '__call__')]

    else:
        typename = type(sequence).__qualname__
        raise TypeError(f"object of type '{typename}' is neither a Task method nor a nested tuple/list")

    # step through, if this is a sequence
    for i in range(len(sequence)):
        # validate replace each entry in the sequence with a parsed item
        if isinstance(sequence[i], (list, tuple)):
            sequence[i] = parse_sequence(sequence[i])
        elif not isinstance(sequence[i], Step):
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
            raise ValueError(f"first element with type '{repr(caller)}' does not indicate lb.concurrently or lb.sequentially")

        for func in funcs:
            if isinstance(func, list):
                defaults.update(collect_defaults(func))
                continue
            elif not callable(func):
                raise ValueError(f"object of type '{type(func).__qualname__}' is neither a callable nor a nested list of callables")

            for argname, def_ in func.extended_defaults().items():
                if def_ is inspect._empty:
                    defaults[argname] = inspect._empty
                elif defaults.get(argname,None) is not inspect._empty:
                    defaults[argname] = def_

    return defaults


def call_step(spec, kwargs):
    available = set(kwargs.keys())

    def call(func):
        # make a Call object with the subset of `kwargs`
        keys = available.intersection(func.extended_args())
        params = dict(((k, kwargs[k]) for k in keys))
        return util.Call(func.extended_call, **params)

    kws_out = {}
    caller, sequence = spec

    for item in sequence:
        if callable(item):
            name = item.owner.__class__.__qualname__ + '_' + item.__name__
            kws_out[name] = call(item)
        elif isinstance(item, list):
            kws_out[name] = call_step(item, kwargs)
        else:
            msg = f"unsupported type '{type(item).__qualname__}' " \
                  f"in call sequence specification"
            raise ValueError(msg)

    return caller, kws_out


class TestbedMethod(util.InTestbed):
    def __init__(self):
        self.to_template()

    def __call__(self, **kwargs):
        ret = {}

        for i, sequence in enumerate(self.sequence):
            caller, step_kws = call_step(sequence, kwargs)

            core.logger.debug(f"{self.__objclass__.__qualname__}.{self.__name__}: start step {i+1}/{len(self.sequence)}")
            ret.update(caller(**step_kws) or {})

        core.logger.debug(f"{self.__objclass__.__qualname__}.{self.__name__} finished")

        return ret

    @classmethod
    def to_template(cls, path=None):
        if path is None:
            path = f"{cls.__objclass__.__qualname__}.{cls.__name__} template.csv"
        print('write to ', path)
        import pandas as pd
        df = pd.DataFrame(columns=cls.params)
        df.index.name = 'Condition name'
        df.to_csv(path)

    def from_csv(self, path, after=None):
        import pandas as pd
        table = pd.read_csv(path, index_col=0)
        for row in table.index:
            core.logger.info(f"Condition {row}")
            self(**table.loc[row].to_dict())
            if after is not None:
                after()

    def __repr__(self):
        return f"<function {self.__name__}>"


@util.hide_in_traceback
def __call__():
    # util.wrap_attribute will munge the call signature above for clean introspection in IDEs
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))
    return self.__call___wrapped(**items)


class Multitask(util.InTestbed):
    def __init__(self, *sequence):
        self.sequence = [parse_sequence(seq) for seq in sequence]

    def __init_testbed_class__(self, testbed_cls):
        # determine the call signature for this new Multitask procedure
        # needed to wait until now, because the signature depends on __name__ of each task
        defaults = collect_defaults(self.sequence)
        params = tuple(defaults.keys())  # *all* of the parameters, before pruning non-default params
        defaults = dict([(arg, def_) for arg, def_ in defaults.items() if def_ is not inspect._empty])

        # make a new callable object based on the aggregate. subclassing into a new class tricks some
        # IDEs into showing the call signature.
        cls = type(self.__name__, (TestbedMethod,),
                   dict(sequence=self.sequence,
                        params=params,
                        defaults=defaults,
                        __name__=self.__name__,
                        __qualname__=testbed_cls.__name__+'.'+self.__name__,
                        __objclass__=self.__objclass__))

        util.wrap_attribute(cls, '__call__', __call__, fields=params, defaults=defaults,
                            positional=0)

        # The testbed takes this TestbedMethod instance in place of self
        obj = object.__new__(cls)
        obj.__init__()
        return obj