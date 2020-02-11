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

__all__ = ['Rack', 'Owner', 'Coordinate']

from . import _core as core
from . import util as util
import contextlib
import inspect
import time
import traceback


EMPTY = inspect._empty


@contextlib.contextmanager
def null_context(owner):
    yield owner


class Step:
    """
    Rack applies wraps its methods with Step to support use with Coordinate
    """
    def __init__(self, owner, name):
        cls = owner.__class__
        obj = getattr(cls, name)
        self.__wrapped__ = obj
        self.owner = owner

        # note the devices needed to execute this function
        if isinstance(owner, Rack):
            available = {getattr(self.owner, name) for name in getattr(self.owner, '__annotations__', {})}
            accessed = {getattr(self.owner, name) for name in util.accessed_attributes(obj)}
            self.dependencies = available.intersection(accessed)
        else:
            self.dependencies = set()
        self.args = list(inspect.signature(obj).parameters)[1:]

        # Ignore *args and **kwargs parameters
        skip_kinds = inspect._ParameterKind.VAR_KEYWORD, inspect._ParameterKind.VAR_POSITIONAL
        all_parameters = inspect.signature(obj).parameters.values()
        self.parameters = list((p for p in all_parameters if p.kind not in skip_kinds))[1:]

        # self.__call__.__name__  = self.__name__ = obj.__name__
        # self.__qualname__ = obj.__qualname__
        self.__doc__ = obj.__doc__
        self.__name__ = name
        self.__qualname__ = getattr(obj, '__qualname__', obj.__class__.__qualname__)

        self.__repr__ = obj.__repr__

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

    def extended_call(self, *args, **kws):
        i = len(self.owner.__name__)+1
        # remove the leading f"{self.owner.__name__}"
        kws = dict(((k[i:], v) for k, v in kws.items()))
        return self.__call__(*args, **kws)

    @util.hide_in_traceback
    def __call__(self, *args, **kws):
        # ensure that required devices are connected
        closed = [repr(dev) for dev in self.dependencies if not dev.connected]
        if len(closed) > 0:
            closed = ', '.join(closed)
            label = self.__class__.__qualname__ + '.' + self.__name__
            raise ConnectionError(f"devices {closed} must be connected to invoke {self.__qualname__}")

        # invoke the wrapped function
        owner_name = str(self.owner)
        t0 = time.perf_counter()
        ret = self.__wrapped__(self.owner, *args, **kws)
        elapsed = time.perf_counter()-t0
        if elapsed > 0.1:
            core.logger.debug(f"{owner_name} completed in {elapsed:0.2f}s")
        return {} if ret is None else ret

    # implement the "&" operator to define concurrent steps for Coordinate
    def __and__(self, other):
        # python objects call this when the left side of '&' is not a tuple
        return 'concurrent', self, other

    def __rand__(self, other):
        # python objects call this when the left side of '&' is already a tuple
        return other + (self,)

    def __repr__(self):
        return f"<method {repr(self.__wrapped__)[1:-1]}>"

    __str__ = __repr__


class RackMethod(util.Ownable):
    def __init__(self):
        self.to_template()

    def __call__(self, **kwargs):
        ret = {}

        for i, (name, sequence) in enumerate(self.sequence.items()):
            caller, step_kws = self._call_step(sequence, kwargs)

            core.logger.debug(f"{self.__objclass__.__qualname__}.{self.__name__} ({i+1}/{len(self.sequence)}) - '{name}'")
            ret.update(caller(**step_kws) or {})

        core.logger.debug(f"{self.__objclass__.__qualname__}.{self.__name__} finished")

        return ret

    @classmethod
    def to_template(cls, path=None):
        if path is None:
            path = f"{cls.__objclass__.__qualname__}.{cls.__name__} template.csv"
        core.logger.debug(f"writing csv template to {repr(path)}")
        import pandas as pd
        df = pd.DataFrame(columns=cls.params)
        df.index.name = 'Condition name'
        df.to_csv(path)

    def from_csv(self, path, after=None):
        import pandas as pd
        table = pd.read_csv(path, index_col=0)
        for i, row in enumerate(table.index):
            core.logger.info(f"{self.__objclass__.__qualname__}.{self.__name__} from '{str(path)}' "
                             f"- '{row}' ({i+1}/{len(table.index)})")
            self(**table.loc[row].to_dict())
            if after is not None:
                after()

    def _call_step(self, spec, kwargs):
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
                kws_out[name] = self._call_step(item, kwargs)
            else:
                msg = f"unsupported type '{type(item).__qualname__}' " \
                      f"in call sequence specification"
                raise ValueError(msg)

        return caller, kws_out

    def __repr__(self):
        return f"<function {self.__name__}>"


class Owner:
    """ own context-managed instances of Device, with setup and cleanup calls to owned instances of Owner
    """
    _ordered_entry = []
    _concurrent = True
    
    def __init_subclass__(cls, concurrent: bool = _concurrent, ordered_entry: list = None):
        # registries that will be context managed
        cls._devices = {} # each of cls._devices.values() these will be context managed
        cls._owners = {} # each of these will get courtesy calls to _setup and _cleanup between _device entry and exit

        #
        if ordered_entry is not None:
            for e in ordered_entry:
                if not issubclass(e, core.Device):
                    raise TypeError(f"ordered_entry item {e} is not a Device subclass")
            cls._ordered_entry = ordered_entry
        cls._concurrent = concurrent

        # prepare and register owned attributes
        for name, obj in dict(cls.__dict__).items():
            if isinstance(obj, util.Ownable):
                obj.__set_name__(cls, name)  # in case it was originally instantiated outside cls
                obj = obj.__owner_subclass__(cls)

            if isinstance(obj, core.Device):
                cls._devices[name] = obj
            elif isinstance(obj, Owner):
                cls._owners[name] = obj
            setattr(cls, name, obj)

    def __init__(self, **devices):
        # initialize everything before we cull the dictionary to limit context management scope
        for lookup in self._devices, self._owners:
            for name, obj in lookup.items():
                obj.__owner_init__(self)

        self._owners = dict(self._owners)
        self._devices = dict(self._devices, **devices)
        self.__context_manager = self.__new_manager()

        super().__init__()
        
    def __setattr__(self, key, obj):
        # keep util.Ownable instance naming up to date, as well as self._devices and self._owners
        if isinstance(obj, util.Ownable):
            if not hasattr(obj, '__objclass__') or obj.__objclass__ is not self.__class__:
                obj.__set_name__(self.__class__, key)
                obj.__owner_init__(self)

        if isinstance(obj, core.Device):
            self._devices[key] = obj

        elif isinstance(obj, Owner):
            self._owners[key] = obj

        object.__setattr__(self, key, obj)

    def __new_manager(self):
        """
        Add context management to an owner to support entry and exit from multiple connections

        :param owner: the sublass or instance that owns the connections to manage
        :param concurrent:
        :param ordered_entry:
        """

        contexts, ordered_entry = self._recursive_devices()

        # ensure a unique ordering without changing the order of the first entry
        ordered_entry = tuple(dict(((entry, None) for entry in ordered_entry)).keys())
        self.__effective_ordered_entry = [e.__qualname__ for e in ordered_entry]

        # owner.__enter__ = self.__enter__
        # owner.__exit__ = self.__exit__

        # Pull any objects of types listed by self.ordered_entry, in the
        # order of (1) the types listed in self.ordered_entry, then (2) the order
        # they appear in objs
        first_contexts = dict()
        other_contexts = dict(contexts)
        for cls in ordered_entry:
            for attr, obj in contexts.items():
                if isinstance(obj, cls):
                    first_contexts[attr] = other_contexts.pop(attr)

        # enforce ordering given by self.ordered_entry
        self.__context_description = ', '.join([repr(c) for c in first_contexts.values()])
        if self._concurrent:
            # any remaining context managers will be run concurrently if concurrent=True
            others = util.concurrently(name='', **other_contexts)
            contexts = dict(first_contexts, others=others)
            self.__context_description += f", ({' & '.join([repr(c) for c in other_contexts.values()])})"
        else:
            # otherwise, run them sequentially
            contexts = dict(first_contexts, **other_contexts)
            self.__context_description += f", {', '.join([repr(c) for c in other_contexts.values()])}"

        name = self.__class__.__qualname__
        return util.sequentially(name=f'{name} connection', **contexts) or null_context(self)

    def _recursive_devices(self):
        ordered_entry = list(self._ordered_entry)
        devices = dict(self._devices)
        name_prefix = getattr(self, '__name__', '')
        if len(name_prefix) > 0:
            name_prefix = name_prefix + '.'

        for owner in self._owners.values():
            children, o_ordered_entry = owner._recursive_devices()

            # this might be faster by reversing key and value order in devices (and thus children)?
            for name, child in children.items():
                if child not in devices.values():
                    devices[name_prefix+name] = child

            ordered_entry.extend(o_ordered_entry)

        return devices, ordered_entry

    def _cleanup(self):
        pass

    def _setup(self):
        pass

    def __enter__(self):
        log = getattr(self, 'logger', util.logger)
        log.debug(f"requested first entry order, in aggregate, was {self.__effective_ordered_entry}")
        log.debug(f"device open sequence will be {self.__context_description}")

        self.__context_manager.__enter__()
        for child in self._owners.values():
            child._setup()
        self._setup()
        return self

    def __exit__(self, *exc_info):
        try:
            self._cleanup()
        except BaseException as e:
            traceback.print_exc()

        for child in self._owners.values():
            try:
                child._cleanup()
            except BaseException as e:
                traceback.print_exc()

        return self.__context_manager.__exit__(*exc_info)

@util.hide_in_traceback
def __call__():
    # util.wrap_attribute will munge the call signature above for clean introspection in IDEs
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))
    return self.__call___wrapped(**items)


class Coordinate(util.Ownable):
    """ Define an experiment built from steps in Rack instances. The input is a specification for sequencing these
    steps, including support for threading. The output is a callable function that can be assigned as a method
    to a top-level "master" Rack.
    """

    def __init__(self, **spec):
        self.sequence = dict(((k, self._parse_sequence(seq)) for k, seq in spec.items()))

    def __owner_subclass__(self, testbed_cls):
        # initialization on the parent class definition
        # waited until after __set_name__, because this depends on __name__ having been set for the tasks task

        # determine the call signature for the new Coordinate procedure
        signatures = self._collect_signatures(tuple(self.sequence.values()))
        params = tuple(signatures.keys())  # *all* of the parameters, before pruning non-default params
        defaults = dict([(arg, sig[0]) for arg, sig in signatures.items() if sig[0] is not EMPTY])
        annots = dict([(arg, sig[1]) for arg, sig in signatures.items() if sig[1] is not EMPTY])

        # this builds the callable object with a newly-defined subclass.
        # this tricks some IDEs into showing the call signature.
        cls = type(self.__name__, (RackMethod,),
                   dict(sequence=self.sequence,
                        params=params,
                        defaults=defaults,
                        annotations=annots,
                        dependency_tree=self._dependency_tree(),
                        __name__=self.__name__,
                        __qualname__=testbed_cls.__name__+'.'+self.__name__,
                        __objclass__=self.__objclass__))

        util.wrap_attribute(cls, '__call__', __call__, fields=params, defaults=defaults,
                            annotations=annots,
                            positional=0)

        # The testbed takes this RackMethod instance in place of self
        obj = object.__new__(cls)
        obj.__init__()
        return obj

    def _parse_sequence(self, sequence):
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

        elif isinstance(sequence, util.Ownable) and callable(sequence):
            invoke = util.sequentially
            sequence = [Step(sequence, '__call__')]

        else:
            typename = type(sequence).__qualname__
            raise TypeError(f"object of type '{typename}' is neither a Rack method nor a nested tuple/list")

        # step through, if this is a sequence
        for i in range(len(sequence)):
            # validate replace each entry in the sequence with a parsed item
            if isinstance(sequence[i], (list, tuple)):
                sequence[i] = self._parse_sequence(sequence[i])
            elif not isinstance(sequence[i], Step):
                typename = type(sequence).__qualname__
                raise TypeError(f"object of type '{typename}' is neither a "
                                f"Rack method nor a nested tuple/list")

        return invoke, sequence

    def _dependency_tree(self, concurrent_parent=None, call_tree=None, dependency_tree={}):
        """ generate a list of Device dependencies in each call
        """

        if call_tree is None:
            call_tree = tuple(self.sequence.values())

        for caller, args in call_tree:
            # dependencies are keyed on the arguments of the parent call to util.concurrently.
            if concurrent_parent:
                next_parent = concurrent_parent
            elif caller is util.sequentially:
                next_parent = None
            elif caller is util.concurrently:
                next_parent = tuple(args)
            else:
                raise ValueError(f"unhandled caller '{repr(caller)}'")

            # if caller is not util.concurrently and not concurrent_parent:
            #     # no risk of concurrency here
            #     continue
            # now caller is util.sequentially or concurrent_parent is False
            
            for arg in args:
                if isinstance(arg, list):
                    self._group_dependencies(concurrent_parent=next_parent,
                                             call_tree=arg,
                                             dependency_tree=dependency_tree)

                elif isinstance(arg, Step):
                    for child_dep in arg.dependencies:
                        dependency_tree.setdefault(next_parent,{}).setdefault(child_dep, []).append(arg)

                else:
                    raise TypeError(f"parsed tree should not include arguments of type '{type(arg).__qualname__}'")

        return dependency_tree

    def _collect_signatures(self, tree=None):
        """ collect a dictionary of parameter default values

        :param tree: nested list of calls that contains the parsed call tree
        :return: dict keyed on parameter name, with values that are a list of (caller, default_value) pairs.
            default_value is `EMPTY` if there is no default.
        """

        if tree is None:
            tree = self.sequence

        signatures = {}

        # collect the defaults
        for caller, args in tree:
            if caller in (util.concurrently, util.sequentially):
                funcs = args
            else:
                raise ValueError(f"first element with type '{repr(caller)}' does not indicate lb.concurrently or lb.sequentially")

            for func in funcs:
                if isinstance(func, list):
                    signatures.update(self._collect_signatures(func))
                    continue
                elif not callable(func):
                    raise ValueError(f"object of type '{type(func).__qualname__}' is neither a callable nor a nested list of callables")

                # pull in a dictionary of signature values (default, annotation) with EMPTY as a null sentinel value
                for argname, (def_, annot) in func.extended_signature().items():
                    prev_def_, prev_annot = signatures.setdefault(argname, [EMPTY, EMPTY])

                    if prev_annot is not EMPTY and annot is not EMPTY and prev_annot != annot:
                        msg = f"conflicting type annotations {repr(prev_annot)}, {repr(annot)} for argument '{argname}'"
                        raise ValueError(msg)
                    else:
                        signatures[argname][1] = annot

                    if def_ is EMPTY:
                        signatures[argname][0] = EMPTY
                    elif prev_def_ is not EMPTY and def_ != prev_def:
                        signatures[argname][0] = EMPTY
                    elif prev_def_ is not EMPTY:
                        signatures[argname][0] = def_

        return signatures


class Rack(Owner, util.Ownable):
    """ A Rack is a container for devices, data managers, and method functions that define test steps.

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

    def __init_subclass__(cls, ordered_entry=[], concurrent=True):
        # cls._racks = dict(((k, v) for k, v in cls.__dict__.items() if isinstance(v, Rack)))

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

        super().__init_subclass__(concurrent=concurrent, ordered_entry=ordered_entry)

        # # sentinel values for each annotations (largely to support IDE introspection)
        # for name, annot_cls in cls.__annotations__.items():
        #     if name in cls._steps:
        #         clsname = cls.__qualname__
        #         raise AttributeError(f"'{clsname}' device annotation and method conflict for attribute '{name}'")
        #     else:
        #         setattr(cls, name, annot_cls())

    def __init__(self, config={}, **devices):
        super().__init__(**devices)

        self._config = config

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
            kwargs = [f"{repr(k)}: {repr(v)}" for k, v in annotations.items()]
            raise AttributeError(f"missing keyword arguments '{', '.join(kwargs)}'")

        # replace self._steps with new mapping of wrappers
        self._steps = dict(((k, obj) if isinstance(obj, RackMethod) else (k, Step(self, k))
                            for k, obj in self._steps.items()))

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
        return repr(self.__wrapped__)

    def __str__(self):
        if hasattr(self, '__name__'):
            return self.__objclass__.__qualname__ + '.' + self.__name__
        else:
            return repr(self)

    def _cleanup(self):
        """ This is called on disconnect by the context management in self or in an owning testbed
        """
        pass

    def __repr__(self):
        return f'{self.__class__.__qualname__}()'

    @classmethod
    def _from_module(cls, name_or_module):
        """
        Return a new Rack subclass composed of any instances of Device, Rack, data loggers, or dicts contained
        in a python module namespace.

        :param name_or_module: a string containing the module to import, or a module object that is already imported
        :return: class that is a subclass of Rack
        """
        if isinstance(name_or_module, str):
            import importlib
            name_or_module = importlib.import_module(name_or_module)
        elif not inspect.ismodule(name_or_module):
            raise TypeError(f"object of type '{type(name_or_module)}' is not a module")

        # pull in only dictionaries (for config) and instances of Device, Rack, etc
        namespace = dict(((attr, obj) for attr, obj in name_or_module.__dict__.items()
                          if isinstance(obj, (util.Ownable, dict)) and not attr.startswith('_')))

        # block attribute overrides
        name_conflicts = set(namespace).intersection(cls.__dict__)
        if len(name_conflicts) > 0:
            raise NameError(f"names {name_conflicts} in module '{name_or_module.__name__}' "
                            f"conflict with attributes of '{cls.__qualname__}'")

        # subclass into a new Rack
        return type(cls.__name__, (cls,), dict(cls.__dict__, **namespace))
