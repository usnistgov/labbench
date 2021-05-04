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

from . import _device as core
from . import util as util

from functools import wraps
from pathlib import Path

import contextlib
import inspect
import logging
import time
import yaml


EMPTY = inspect._empty
BASIC_TYPES = bool, bytearray, bytes, complex, dict, float, frozenset, \
              int, list, set, reversed, slice, str, tuple

@contextlib.contextmanager
def null_context(owner):
    yield owner


class Step:
    """
    Wraps class methods to support use with Sequence
    """
    def __init__(self, owner, name):
        def ownable(obj, name):
            return isinstance(getattr(self.owner, name), util.Ownable)
        cls = owner.__class__
        obj = getattr(cls, name)
        if isinstance(obj, Step):
            obj = obj.__wrapped__
        self.__wrapped__ = obj
        self.owner = owner

        self.introspect()

        # self.__call__.__name__  = self.__name__ = obj.__name__
        # self.__qualname__ = obj.__qualname__
        self.__doc__ = obj.__doc__
        self.__name__ = name
        self.__qualname__ = getattr(obj, '__qualname__', obj.__class__.__qualname__)

        self.__repr__ = obj.__repr__

    def introspect(self):
        owner = self.owner
        # note the devices needed to execute this function
        if isinstance(owner, Rack):
            annotations = getattr(self.owner, '__annotations__', {})
            available = {getattr(self.owner, name) for name in annotations}

            accessed = {getattr(self.owner, name) for name in util.accessed_attributes(self.__wrapped__)
                        if not name.startswith('_')}
            self.dependencies = available.intersection(accessed)
        else:
            self.dependencies = set()
        self.args = list(inspect.signature(self.__wrapped__).parameters)[1:]

        # Ignore *args and **kwargs parameters
        skip_kinds = inspect._ParameterKind.VAR_KEYWORD, inspect._ParameterKind.VAR_POSITIONAL
        all_parameters = inspect.signature(self.__wrapped__).parameters.values()
        self.parameters = list((p for p in all_parameters if p.kind not in skip_kinds))[1:]


    def extended_signature(self):
        """ return a mapping keyed on call parameter name that gives a list [default value, annotation value].
            EMPTY is a sentinel value for "does not exist"
        """
        ext_args = self.extended_args()
        signature = dict([(k, [v.default, EMPTY]) for k, v in zip(ext_args, self.parameters)])

        for k, v in getattr(self.__wrapped__, '__annotations__', {}).items():
            signature[k][1] = v

        return signature

    def extended_args(self):
        return [(self.owner.__name__ + '_' + name) for name in self.args]

    @util.hide_in_traceback
    def extended_call(self, *args, **kws):
        i = len(self.owner.__name__)+1
        # remove the leading f"{self.owner.__name__}"
        kws = {k[i:]: v for k, v in kws.items()}
        return self.__call__(*args, **kws)

    @util.hide_in_traceback
    def __call__(self, *args, **kws):
        # ensure that required devices are connected
        closed = [repr(dev) for dev in self.dependencies if not dev.isopen]
        if len(closed) > 0:
            closed = ', '.join(closed)
            label = self.__class__.__qualname__ + '.' + self.__name__
            raise ConnectionError(f"devices {closed} must be connected to invoke {self.__qualname__}")

        # notify owner about the parameters passed
        name_prefix = str(self.owner).replace('.', '_') + '_'
        if len(kws) > 0:
            notify_params = {name_prefix + k: v for k, v in kws.items()}
            Rack._notify.call_event(notify_params)

        # invoke the wrapped function
        owner_name = getattr(self.owner, '__qualname__', str(self.owner))
        t0 = time.perf_counter()
        ret = self.__wrapped__(self.owner, *args, **kws)
        elapsed = time.perf_counter()-t0
        if elapsed > 0.1:
            util.console.debug(f"{owner_name} completed in {elapsed:0.2f}s")

        # notify owner of return value
        if ret is not None:
            notify = ret if isinstance(ret, dict) else {name_prefix + self.__name__: ret}
            Rack._notify.return_event(notify)

        return {} if ret is None else ret

    # implement the "&" operator to define concurrent steps for Sequence
    def __and__(self, other):
        # python objects call this when the left side of '&' is not a tuple
        return 'concurrent', self, other

    def __rand__(self, other):
        # python objects call this when the left side of '&' is already a tuple
        return other + (self,)

    def __repr__(self):
        return f"<method {repr(self.__wrapped__)[1:-1]}>"

    __str__ = __repr__


class SequencedMethod(util.Ownable):
    @util.hide_in_traceback
    def __call__(self, **kwargs):
        ret = {}

        for i, (name, sequence) in enumerate(self.sequence.items()):
            step_kws = self._call_step(sequence, kwargs)

            util.console.debug(f"{self.__objclass__.__qualname__}.{self.__name__} ({i+1}/{len(self.sequence)}) - '{name}'")
            ret.update(util.concurrently(**step_kws) or {})

        util.console.debug(f"{self.__objclass__.__qualname__}.{self.__name__} finished")

        return ret

    @classmethod
    def to_template(cls, path):
        if path is None:
            path = f"{cls.__objclass__.__qualname__}.{cls.__name__} template.csv"
        util.console.debug(f"writing csv template to {repr(path)}")
        import pandas as pd
        df = pd.DataFrame(columns=cls.params)
        df.index.name = 'Condition name'
        df.to_csv(path)

    def from_csv(self, path):
        import pandas as pd
        table = pd.read_csv(path, index_col=0)
        for i, row in enumerate(table.index):
            util.console.info(f"{self.__objclass__.__qualname__}.{self.__name__} from '{str(path)}' "
                             f"- '{row}' ({i+1}/{len(table.index)})")
            self.results = self(**table.loc[row].to_dict())

    def _call_step(self, spec, kwargs):
        available = set(kwargs.keys())

        def call(func):
            # make a Call object with the subset of `kwargs`
            keys = available.intersection(func.extended_args())
            params = {k: kwargs[k] for k in keys}
            return util.Call(func.extended_call, **params)

        kws_out = {}

        for item in spec:
            if callable(item):
                name = item.owner.__class__.__qualname__ + '_' + item.__name__
                kws_out[name] = call(item)
            elif isinstance(item, list):
                kws_out[name] = self._call_step(item, kwargs)
            else:
                msg = f"unsupported type '{type(item).__qualname__}' " \
                      f"in call sequence specification"
                raise ValueError(msg)

        return kws_out

    def __repr__(self):
        return f"<function {self.__name__}>"


class OwnerContextAdapter:
    """ transform calls to __enter__ -> _setup and __exit__ -> _cleanup

    """
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        self.owner._setup()

    def __exit__(self, *exc_info):
        self.owner._cleanup()

    def __repr__(self):
        return repr(self.owner)


def recursive_devices(top):
    ordered_entry = list(top._ordered_entry)
    devices = dict(top._devices)
    name_prefix = getattr(top, '__name__', '')
    if len(name_prefix) > 0:
        name_prefix = name_prefix + '.'

    for owner in top._owners.values():
        children, o_ordered_entry = recursive_devices(owner)

        # this might be faster by reversing key and value order in devices (and thus children)?
        for name, child in children.items():
            if child not in devices.values():
                devices[name_prefix+name] = child

        ordered_entry.extend(o_ordered_entry)

    return devices, ordered_entry


def recursive_owner_managers(top):
    managers = {}
    for name, owner in top._owners.items():
        managers.update({"{name}_{k}": cm
                         for k, cm in recursive_owner_managers(owner).items()})
        managers[name] = OwnerContextAdapter(owner)
    managers[repr(top)] = OwnerContextAdapter(top)
    return managers


def owner_context_manager(top):
    """
    Make a context manager for an owner, as well as any of its owned instances of Device and Owner
    (recursively).
    Entry into this context will manage all of these.

    :param top: Owner instance
    :returns: Context manager
    """

    log = getattr(top, '_console', util.console)
    contexts, ordered_entry = recursive_devices(top)

    # like set(ordered_entry), but maintains order in python >= 3.7
    ordered_entry = tuple(dict.fromkeys(ordered_entry))
    order_desc = ' -> '.join([e.__qualname__ for e in ordered_entry])
    log.debug(f"ordered_entry before other devices: {order_desc}")

    # Pull any objects of types listed by top.ordered_entry, in the
    # order of (1) the types listed in top.ordered_entry, then (2) the order
    # they appear in objs
    first = dict()
    remaining = dict(contexts)
    for cls in ordered_entry:
        for attr, obj in contexts.items():
            if isinstance(obj, cls):
                first[attr] = remaining.pop(attr)
    firsts_desc = '->'.join([repr(c) for c in first.values()])

    # then, other devices, which need to be ready before we start into Rack setup methods
    devices = {attr: remaining.pop(attr)
               for attr, obj in dict(remaining).items()
               if isinstance(obj, core.Device)}
    devices_desc = f"({', '.join([repr(c) for c in devices.values()])})"
    devices = util.concurrently(name='', **devices)

    # what remain are instances of Rack and other Owner types
    owners = recursive_owner_managers(top)
    owners_desc = f"({'->'.join([repr(c) for c in owners.values()])})"

    # top._recursive_owners()
    # top.__context_manager.__enter__()
    # for child in top._owners.values():
    #     child._setup()
    # # top._setup()
    #
    # the dictionary here is a sequence
    seq = dict(first, _devices=devices, **owners)

    desc = '->'.join([d for d in (firsts_desc, devices_desc, owners_desc)
                      if len(d)>0])

    log.debug(f"context order: {desc}")
    return util.sequentially(name=f'{repr(top)}', **seq) or null_context(top)


class Owner:
    """ own context-managed instances of Device as well as setup and cleanup calls to owned instances of Owner
    """
    _ordered_entry = []
    _concurrent = True
    
    def __init_subclass__(cls, ordered_entry: list = None):

        # registries that will be context managed
        cls._devices = {} # each of cls._devices.values() these will be context managed
        cls._owners = {} # each of these will get courtesy calls to _setup and _cleanup between _device entry and exit

        if ordered_entry is not None:
            for e in ordered_entry:
                if not issubclass(e, core.Device):
                    raise TypeError(f"ordered_entry item {e} is not a Device subclass")
            cls._ordered_entry = ordered_entry

        ownable = {}

        # prepare and register owned attributes
        for name, obj in dict(cls.__dict__).items():

            ownable[name] = obj
            # prepare these first, so they are available to owned classes on __owner_subclass__
            if isinstance(obj, core.Device):
                cls._devices[name] = obj
            elif isinstance(obj, Owner):
                cls._owners[name] = obj

        # run the hooks in owned classes, now that cls._devices and cls._owners are ready for them
        for name, obj in ownable.items():
            if isinstance(obj, util.Ownable):
                obj.__set_name__(cls, name)  # in case it was originally instantiated outside cls
                obj = obj.__owner_subclass__(cls)

            setattr(cls, name, obj)

    def __init__(self, **devices):
        # initialize everything before we cull the dictionary to limit context management scope
        self._owners = dict(self._owners)
        self._devices = dict(self._devices, **devices)

        super().__init__()

        for lookup in self._devices, self._owners:
            for name, obj in lookup.items():
                obj.__owner_init__(self)

    def __setattr__(self, key, obj):
        # update naming for any util.Ownable instances
        if isinstance(obj, util.Ownable):
            if getattr(obj, '__objclass__', None) is not type(self):
                obj.__set_name__(type(self), key)
                obj.__owner_init__(self)

        if isinstance(obj, core.Device):
            self._devices[key] = obj

        elif isinstance(obj, Owner):
            self._owners[key] = obj

        object.__setattr__(self, key, obj)

    def _cleanup(self):
        pass

    def _setup(self):
        pass

    @property
    def __enter__(self):
        # Rack._notify.clear()
        self.__context_manager = owner_context_manager(self)
        # self.__context_manager.__enter__()
        # return self

        @wraps(type(self).__enter__.fget)
        def __enter__():
            self.__context_manager.__enter__()
            return self

        return __enter__

    @property
    def __exit__(self):
        # pass along from self.__context_manager
        return self.__context_manager.__exit__


@util.hide_in_traceback
def __call__():
    # util.wrap_attribute will munge the call signature above for clean introspection in IDEs
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))
    return self.__call___wrapped(**items)


class Sequence(util.Ownable):
    """ Define an experiment built from steps in Rack instances. The input is a specification for sequencing these
    steps, including support for threading. The output is a callable function that can be assigned as a method
    to a top-level "master" Rack.
    """

    def __init__(self, **specification):
        def spec_entry(sequence):
            if isinstance(sequence, (list, tuple)):
                # specification for a concurrent and/or sequential calls to Step methods
                sequence = list(sequence)

            elif isinstance(sequence, Step):
                # a Step method that is already packaged for use
                sequence = [sequence]

            elif isinstance(getattr(sequence, '__self__', sequence), util.Ownable) and \
                    callable(sequence):
                # some other kind of callable function that seems reasonable to adopt as a Step method
                sequence = [Step(sequence, '__call__')]

            else:
                typename = type(sequence).__qualname__
                raise TypeError(f"object of type '{typename}' is neither a Rack method nor a nested tuple/list")

            return sequence

        self.spec = {k: spec_entry(spec) for k, spec in specification.items()}

    def __owner_subclass__(self, testbed_cls):
        # initialization on the parent class definition
        # waited until after __set_name__, because this depends on __name__ having been set for the tasks task

        # determine the call signature for the new Sequence procedure
        signatures = self._collect_signatures()
        params = tuple(signatures.keys())  # *all* of the parameters, before pruning non-default ones
        defaults = dict([(arg, sig[0]) for arg, sig in signatures.items() if sig[0] is not EMPTY])
        annots = dict([(arg, sig[1]) for arg, sig in signatures.items() if sig[1] is not EMPTY])

        # this builds the callable object with a newly-defined subclass.
        # this tricks some IDEs into showing the call signature.
        cls = type(self.__name__, (SequencedMethod,),
                   dict(sequence=self.spec,
                        params=params,
                        defaults=defaults,
                        annotations=annots,
                        signatures=signatures,
                        dependencies=self._dependency_map(),
                        __name__=self.__name__,
                        __qualname__=testbed_cls.__name__+'.'+self.__name__,
                        __objclass__=self.__objclass__,
                        __owner_subclass__=self.__owner_subclass__ # in case the owner changes and calls this again
                        ))

        util.wrap_attribute(cls, '__call__', __call__, fields=params, defaults=defaults,
                            annotations=annots,
                            positional=0)


        # the testbed gets this SequencedMethod instance in place of self
        obj = object.__new__(cls)
        obj.__init__()
        return obj

    def _dependency_map(self, owner_deps={}) -> dict:
        """ generate a list of Device dependencies in each Step.

        :returns: {Device instance: reference to method that uses Device instance}
        """

        deps = dict(owner_deps)

        for spec in self.spec.values():
            for func in spec:
                if not isinstance(func, (Step, SequencedMethod)):
                    raise TypeError(f"expected Step instance, but got '{type(func).__qualname__}' instead")

                # race condition check
                conflicts = set(deps.keys()).intersection(func.dependencies)
                if len(conflicts) > 0:
                    users = {deps[device] for device in conflicts}
                    raise RuntimeError(f"risk of concurrent access to {conflicts} by {users}")

                deps.update({device.__name__: device for device in func.dependencies})

        return deps

    def _collect_signatures(self):
        """ collect a dictionary of parameter default values

        :param tree: nested list of calls that contains the parsed call tree
        :return: dict keyed on parameter name, with values that are a list of (caller, default_value) pairs.
            default_value is `EMPTY` if there is no default.
        """

        signatures = {}

        # collect the defaults
        for funcs in self.spec.values():
            for func in funcs:
                # pull a dictionary of signature values (default, annotation) with EMPTY as a null sentinel value
                for argname, (def_, annot) in func.extended_signature().items():
                    prev_def_, prev_annot = signatures.setdefault(argname, [EMPTY, EMPTY])

                    if prev_annot is not EMPTY and annot is not EMPTY and prev_annot != annot:
                        msg = f"conflicting type annotations {repr(prev_annot)}, {repr(annot)} for argument '{argname}'"
                        raise ValueError(msg)
                    else:
                        signatures[argname][1] = annot

                    if def_ is not EMPTY:
                        signatures[argname][0] = def_
                    if prev_def_ is not EMPTY and def_ != prev_def_:
                        signatures[argname][0] = EMPTY
                    elif prev_def_ is not EMPTY:
                        signatures[argname][0] = def_

        return signatures


class notify:
    """
    Singleton notification handler shared by all Rack instances.
    """
    _handlers = dict(returns=set(), calls=set())

    @classmethod
    def clear(cls):
        cls._handlers = dict(returns=set(), calls=set())

    @classmethod
    def return_event(cls, returned: dict):
        if not isinstance(returned, dict):
            raise TypeError(f"returned data was {repr(returned)}, which is not a dict")
        for handler in cls._handlers['returns']:
            handler(returned)

    @classmethod
    def call_event(cls, parameters: dict):
        if not isinstance(parameters, dict):
            raise TypeError(f"parameters data was {repr(parameters)}, which is not a dict")
        for handler in cls._handlers['calls']:
            handler(parameters)

    @classmethod
    def observe_returns(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers['returns'].add(handler)

    @classmethod
    def observe_calls(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers['calls'].add(handler)

    @classmethod
    def unobserve_returns(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers['returns'].remove(handler)

    @classmethod
    def unobserve_calls(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers['calls'].remove(handler)


class RackMeta(type):
    def take_module(cls, module):
        """
        Return a new Rack subclass composed of any instances of Device, Rack, data loggers, or dicts contained
        in a python module namespace.

        :param name_or_module: a string containing the module to import, or a module object that is already imported
        :return: class that is a subclass of Rack
        """
        if isinstance(module, str):
            import importlib
            module = importlib.import_module(module)
        if not inspect.ismodule(module):
            raise TypeError(f"object of type '{type(module)}' is not a module")

        # pull in only dictionaries (for config) and instances of Device, Rack, etc

        namespace = {attr: obj for attr, obj in module.__dict__.items()
                     if not attr.startswith('_') and isinstance(obj, BASIC_TYPES + (core.Device, Owner, util.Ownable))}

        # block attribute overrides
        name_conflicts = set(namespace).intersection(cls.__dict__)
        if len(name_conflicts) > 0:
            raise NameError(f"names {name_conflicts} in module '{module.__name__}' "
                            f"conflict with attributes of '{cls.__qualname__}'")

        # subclass into a new Rack
        return type(module.__name__.rsplit('.')[-1], (cls,), dict(cls.__dict__, **namespace))

    def __enter__(cls):
        raise RuntimeError(f"the `with` block needs an instance - 'with {cls.__qualname__}():' instead of 'with {cls.__qualname__}:'")

    def __exit__(cls, *exc_info):
        pass


class Rack(Owner, util.Ownable, metaclass=RackMeta):
    """ A Rack contains and coordinates devices and data handling with method functions that define test steps.

        The Rack object provides connection management for
        all devices and data managers for `with` block::

            with Rack() as testbed:
                # use the testbed here
                pass

        For functional validation, it is also possible to open only a subset
        of devices like this::

            testbed = Rack()
            with testbed.dev1, testbed.dev2:
                # use the testbed.dev1 and testbed.dev2 here
                pass

        The following syntax creates a new Rack class for an
        experiment:

            import labbench as lb

            class MyRack(lb.Rack):
                db = lb.SQLiteManager()
                sa = MySpectrumAnalyzer()

                spectrogram = Spectrogram(db=db, sa=sa)

    """

    _notify = notify

    def __init_subclass__(cls, ordered_entry=[]):
        cls._ordered_entry = ordered_entry

        # register step methods
        cls._steps = {}
        for name, obj in cls.__dict__.items():
            if isinstance(obj, (core.Device, Owner)):
                continue
            if not name.startswith('_') and callable(obj):
                cls._steps[name] = obj

        # include annotations from parent classes
        cls.__annotations__ = dict(getattr(super(), '__annotations__', {}),
                                   **getattr(cls, '__annotations__', {}))
        cls.__init__.__annotations__ = cls.__annotations__

        super().__init_subclass__(ordered_entry=ordered_entry)

        # # sentinel values for each annotations (largely to support IDE introspection)
        # for name, annot_cls in cls.__annotations__.items():
        #     if name in cls._steps:
        #         clsname = cls.__qualname__
        #         raise AttributeError(f"'{clsname}' device annotation and method conflict for attribute '{name}'")
        #     else:
        #         setattr(cls, name, annot_cls())

    def __init__(self, **devices):
        self._console = util.console.logger.getChild(str(self))
        self._console = logging.LoggerAdapter(self._console, dict(rack=repr(self), origin=f" - " + str(self)))

        super().__init__(**devices)

        # match the device arguments to annotations
        devices = dict(devices)
        annotations = dict(self.__annotations__)
        for name, dev in devices.items():#self.__annotations__.items():
            try:
                dev_type = annotations.pop(name)
            except KeyError:
                raise NameError(f"{self.__class__.__qualname__}.__init__ was given invalid keyword argument '{name}'")
            if not isinstance(dev, dev_type):
                msg = f"argument '{name}' is not an instance of '{dev_type.__qualname__}'"
                raise AttributeError(msg)
            setattr(self, name, dev)

        # check for the is a valid instance in the class for each remaining attribute
        for name, dev_type in dict(annotations).items():
            if isinstance(getattr(self, name, EMPTY), dev_type):
                del annotations[name]

        # any remaining items in annotations are missing arguments
        if len(annotations) > 0:
            kwargs = [f"{repr(k)}: {v}" for k, v in annotations.items()]
            raise AttributeError(f"missing keyword arguments {', '.join(kwargs)}'")

        # replace self._steps with new mapping of wrappers
        self._steps = {k: (obj if isinstance(obj, SequencedMethod) else Step(self, k))
                       for k, obj in self._steps.items()}

    def __owner_init__(self, owner):
        super().__owner_init__(owner)
        self._console = util.console.logger.getChild(str(self))
        self._console = logging.LoggerAdapter(self._console, dict(rack=repr(self), origin=f" - "+str(self)))

    def __getattribute__(self, item):
        if item != '_steps' and item in self._steps:
            return self._steps[item]
        else:
            return super().__getattribute__(item)

    def __getitem__(self, item):
        return self._steps[item]

    def __len__(self):
        return len(self._steps)

    def __iter__(self):
        return (getattr(self, k) for k in self._steps)

    def __repr__(self):
        return f'{self.__class__.__qualname__}()'


class Configuration(util.Ownable):
    def __init__(self, root_path: Path):
        super().__init__()    

        self.path = Path(root_path)
        self.path.mkdir(exist_ok=True, parents=True)

    def __owner_subclass__(self, owner_cls):
        super().__owner_subclass__(owner_cls)
        self._rack_defaults(owner_cls)

        return self

    def make_templates(self):
        for name, attr in self.__objclass__.__dict__.items():
            if name == 'run':
                print("run! ", attr, type(attr), isinstance(attr, Sequence), isinstance(attr, SequencedMethod))
            if isinstance(attr, SequencedMethod):
                method = attr

                print('make a template for ',name)
                name = f"{type(method).__objclass__.__qualname__}.{type(method).__name__} template.csv"
                method.to_template(self.path/name)


    def parameters(self, cls):
        defaults = {}
        annots = {}
        methods = {}
        names = {}

        for owner in cls._owners.values():
            if isinstance(owner, Rack):
                d, a, m, n = self.parameters(owner)
                defaults.update({owner.__name__+'_'+k: v for k, v in d.items()})
                annots.update({owner.__name__+'_'+k: v for k, v in a.items()})
                methods.update({owner.__name__ + '_' + k: v for k, v in m.items()})
                names.update({owner.__name__ + '_' + k: k for k, v in m.items()})

        for step in cls._steps.values():
            params = iter(inspect.signature(step).parameters.items())
            next(params) # skip 'self'

            for k, p in params:
                methods[k] = step
                if annots.setdefault(k, p.annotation) is EMPTY:
                    annots[k] = p.annotation
                elif EMPTY not in (p.annotation, annots[k]) and p.annotation != annots[k]:
                    raise ValueError(f"conflicting type annotations '{p.annotation}' and '{annots[k]}' in {cls.__qualname__} methods")
                if not inspect.isclass(annots[k]):
                    raise TypeError(f"annotation '{annots[k]}' for parameter '{k}' in '{cls.__qualname__}' is not a class")

                if defaults.setdefault(k, p.default) is EMPTY:
                    defaults[k] = p.default
                elif EMPTY not in (p.default, defaults[k]) and p.default != defaults[k]:
                    raise ValueError(f"conflicting defaults '{p.default}' and '{defaults[k]}' in {cls.__qualname__} methods")

            for k in defaults:
                if EMPTY not in (annots[k], defaults[k]) and not isinstance(defaults[k], annots[k]):
                    raise TypeError(f"default '{defaults[k]}' does not match type annotation "
                                    f"'{annots[k]}' in '{cls.__qualname__}' is not a class")

        return defaults, annots, methods, names

    def _rack_defaults(self, cls):
        """ adjust the method argument parameters in the Rack subclass `cls` according to config file
        """
        path = Path(self.path)/f"{cls.__qualname__}.defaults.yaml"

        if getattr(cls, '__config_path__', None) == str(path):
            util.console.debug(f"already have {path}")
            util.console.debug(f"already have {cls.__config_path__}")
            return
        else:
            cls.__config_path__ = str(path)

        defaults, annots, methods, names = self.parameters(cls)

        # read the existing defaults
        defaults_in = {}
        if path.exists():
            with open(path, 'rb') as f:
                defaults_in = yaml.safe_load(f) or {}

        util.console.debug(f"read {defaults_in.keys()} from {path}")

        for k, v in dict(defaults_in).items():
            if v == defaults[k]:
                del defaults_in[k]
                continue

            if k not in methods:
                raise KeyError(f"'{k}' in '{str(path)}' is not a parameter in any method of '{cls.__qualname__}'")
            elif annots[k] is not EMPTY and not isinstance(v, annots[k]):
                raise TypeError(f"the parameter '{k}' with value '{v}' in '{str(path)}' conflicts "
                                f"with type annotation '{annots[k]}'")

            # update the call signature
            method = methods[k]

            if isinstance(method, Step):
                if method.__wrapped__.__kwdefaults__ is None:
                    method.__wrapped__.__kwdefaults__ = {}
                method.__wrapped__.__kwdefaults__[names[k]] = v
                method.introspect()
                # step = Step(method.owner, method.__name__)
                # print(method.__name__, step.parameters[0].default)
                # setattr(method.owner, method.__name__, step)
                #
                # print(getattr(method.owner, method.__name__).parameters[0].default, step.parameters[0].default, getattr(method.owner, method.__name__)==step)
            else:
                if method.__kwdefaults__ is None:
                    method.__kwdefaults__ = {}
                method.__kwdefaults__[names[k]] = v

        if len(defaults_in) > 0:
            util.console.debug(f"applied defaults {defaults_in}")

        # take the updated defaults
        defaults.update(defaults_in)

        # update the defaults on disk
        with open(path, 'wb') as f:
            for k, default in defaults.items():
                if default is EMPTY:
                    s = f'# {k}: \n'.encode('utf-8')
                else:
                    s = yaml.dump({k: default}, encoding='utf-8', allow_unicode=True)
                if annots[k] is not EMPTY:
                    before, *after = s.split(b'\n', 1)
                    s = b'\n'.join([before+f" # {annots[k].__qualname__}".encode('utf-8')] + after)
                f.write(s)

        # reinitialize the subclass to propagate changes to the keyword signature
        for name, obj in dict(cls.__dict__).items():
            if isinstance(obj, util.Ownable):
                obj.__set_name__(cls, name)  # in case it was originally instantiated outside cls
                obj = obj.__owner_subclass__(cls)