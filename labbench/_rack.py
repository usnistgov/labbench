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
import copy
import importlib
import inspect
import logging
import pandas as pd
import time

from ruamel_yaml import YAML, round_trip_dump, round_trip_load
from ruamel_yaml.comments import CommentedMap
yaml = YAML()
yaml.indent(mapping=4, sequence=4)

EMPTY = inspect._empty
BASIC_TYPES = bool, bytearray, bytes, complex, dict, float, frozenset, \
              int, list, set, reversed, slice, str, tuple

@contextlib.contextmanager
def null_context(owner):
    yield owner


class notify:
    """
    Singleton notification handler shared globally by all Rack instances.
    """

    # the global mapping of references to notification callbacks
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


class Method(util.Ownable):
    """
    Wraps class methods to support use with Sequence
    """
    def __init__(self, owner, name, kwdefaults={}):
        super().__init__()

        def ownable(obj, name):
            return isinstance(getattr(self._owner, name), util.Ownable)

        self._owner = owner
        cls = owner.__class__
        obj = getattr(cls, name)

        if isinstance(obj, Method):
            self._wrapped = obj._wrapped
            self._kwdefaults = dict(obj._kwdefaults)
        else:
            self._wrapped = obj
            self._kwdefaults = kwdefaults

        # self.__call__.__name__  = self.__name__ = obj.__name__
        # self.__qualname__ = obj.__qualname__
        self.__doc__ = obj.__doc__
        self.__name__ = name
        self.__qualname__ = getattr(obj, '__qualname__', obj.__class__.__qualname__)

        self._introspect()

        setattr(owner, name, self)

    @classmethod
    def from_method(self, method):
        """ make a new Method instance by copying another
        """
        return Method(method._owner, method.__name__, method._kwdefaults)

    def __copy__(self):
        return self.from_method(self)

    def __deepcopy__(self, memo=None):
        return self.from_method(self)

    def _introspect(self):
        """ update self.__signature__
        """
        # note the devices needed to execute this function
        if isinstance(self._owner, Rack):
            annotations = getattr(self._owner, '__annotations__', {})

            # set logic to identify Device dependencies
            available = {getattr(self._owner, name) for name in annotations}

            accessed = {
                getattr(self._owner, name)
                for name in util.accessed_attributes(self._wrapped)
                if not name.startswith('_') and hasattr(self._owner, name)
            }

            self.dependencies = available.intersection(accessed)
        else:
            self.dependencies = set()

        # get the signature, apply parameter defaults from self._kwdefaults
        sig = inspect.signature(self._wrapped)
        sig = sig.replace(parameters=(
            p.replace(default=self._kwdefaults.get(k,p.default))
            for k,p in sig.parameters.items()
        ))

        # set the call signature shown by help(), or with ? in ipython/jupyter
        self.__signature__ = sig

        # remember only named keywords, not "*args" and "**kwargs" in call signatures
        SKIP_KINDS = inspect._ParameterKind.VAR_KEYWORD, inspect._ParameterKind.VAR_POSITIONAL
        self.args = list(sig.parameters.keys())[1:] # skip 'self' argument
        self._parameters = [
            p for p in sig.parameters.values()
            if p.kind not in SKIP_KINDS
        ][1:]

    def set_kwdefault(self, name, value):
        if value is EMPTY:
            self._kwdefaults.pop(name, None)
        elif name not in self.__signature__.parameters:
            raise TypeError(f"{self} has no keyword argument {repr(name)}")
        else:
            self._kwdefaults[name] = value

        self._introspect()

        # if value is EMPTY:
        #     del self._kwdefaults[name]
        # else:
        #     self._kwdefaults[name] = value

        # self.introspect()

    def long_kwarg_signature(self):
        """ return a mapping keyed on call parameter name that gives a list [default value, annotation value].
            EMPTY is a sentinel value for "does not exist"
        """
        ext_args = self.long_kwarg_names()
        annots = getattr(self._wrapped, '__annotations__', {})

        return {
            k:[v.default, annots.get(k, EMPTY)]
            for k, v in zip(ext_args, self._parameters)
        }

    def long_kwarg_names(self):
        return [(self._owner.__name__ + '_' + name) for name in self.args]

    @util.hide_in_traceback
    def long_kwarg_call(self, *args, **kws):
        """ rename keywords from the long form used by an owning class
        """
        i = len(self._owner.__name__)+1
        # remove the leading f"{self._owner.__name__}"
        kws = {k[i:]: v for k, v in kws.items()}
        return self.__call__(*args, **kws)

    @util.hide_in_traceback
    def __call__(self, *args, **kws):
        # ensure that required devices are connected
        closed = [dev._instname for dev in self.dependencies if not dev.isopen]
        if len(closed) > 0:
            closed = ', '.join(closed)
            label = self.__class__.__qualname__ + '.' + self.__name__
            raise ConnectionError(f"devices {closed} must be connected to invoke {self.__qualname__}")

        # notify observers about the parameters passed
        name_prefix = '_'.join(self._owner._instname.split('.')[1:])+'_'
        if len(kws) > 0:
            notify_params = {
                name_prefix + k: v for k, v in kws.items()
            }
            notify.call_event(notify_params)

        # invoke the wrapped function
        t0 = time.perf_counter()
        ret = self._wrapped(self._owner, *args, **kws)
        elapsed = time.perf_counter()-t0
        if elapsed > 0.1:
            util.console.debug(f"{self._instname} completed in {elapsed:0.2f}s")

        # notify observers about the returned value
        if ret is not None:
            need_notify = ret if isinstance(ret, dict) else {name_prefix + self.__name__: ret}
            notify.return_event(need_notify)

        return {} if ret is None else ret

    def __repr__(self):
        wrapped = repr(self._wrapped)[1:-1]
        return f'<{wrapped} wrapped by {type(self).__module__}.{type(self).__name__} object>'


class BoundSequence(util.Ownable):
    """ callable realization of a test sequence definition which
        takes the place of Sequence objects on instantiation of
        a new Rack object. its keyword arguments are aggregated
        from all of the methods called by the Sequence.
    """
    @util.hide_in_traceback
    def __call__(self, **kwargs):
        ret = {}

        for i, (name, sequence) in enumerate(self.sequence.items()):
            step_kws = self._step(sequence, kwargs)

            util.console.debug(f"{self.__objclass__.__qualname__}.{self.__name__} ({i+1}/{len(self.sequence)}) - '{name}'")
            ret.update(util.concurrently(**step_kws) or {})

        util.console.debug(f"{self.__objclass__.__qualname__}.{self.__name__} finished")

        return ret

    @classmethod
    def to_template(cls, path):
        if path is None:
            path = f"{cls.__name__} template.csv"
        util.console.debug(f"writing csv template to {repr(path)}")
        df = pd.DataFrame(columns=cls.params)
        df.index.name = 'Condition name'
        df.to_csv(path)

    def iterate_from_csv(self, path):
        """ call the BoundSequence for each row in a csv table.
            keyword argument names are taken from the column header
            (0th row). keyword values are taken from corresponding column in
            each row.
        """
        table = pd.read_csv(path, index_col=0)
        for i, row in enumerate(table.index):
            util.console.info(f"{self._instname} from '{str(path)}' "
                             f"- '{row}' ({i+1}/{len(table.index)})")
            self.results = self(**table.loc[row].to_dict())

    def _step(self, spec, kwargs):
        """ 
        """

        available = set(kwargs.keys())

        def call(func):
            # make a Call object with the subset of `kwargs`
            keys = available.intersection(func.long_kwarg_names())
            params = {k: kwargs[k] for k in keys}
            return util.Call(func.long_kwarg_call, **params)

        kws_out = {}

        for item in spec:
            if callable(item):
                name = item._owner.__class__.__qualname__ + '_' + item.__name__
                kws_out[name] = call(item)
            elif isinstance(item, list):
                kws_out[name] = self._step(item, kwargs)
            else:
                msg = f"unsupported type '{type(item).__qualname__}' " \
                      f"in call sequence specification"
                raise ValueError(msg)

        return kws_out

import sys, traceback

class OwnerContextAdapter:
    """ transform calls to __enter__ -> open and __exit__ -> close.
        each will be called 

    """
    def __init__(self, owner):
        self._owner = owner
        self._instname = getattr(owner, '_instname', repr(owner))

    def __enter__(self):
        cls = type(self._owner)
        for opener in core.trace_methods(cls, 'open', Owner)[::-1]:
            opener(self._owner)

        self._owner.open()
        self._owner._console.debug('opened')

    def __exit__(self, *exc_info):
        cls = type(self._owner)
        methods = core.trace_methods(cls, 'close', Owner)

        all_ex = []
        for closer in methods:
            try:
                closer(self._owner)
            except BaseException:
                all_ex.append(sys.exc_info())

        # Print tracebacks for any suppressed exceptions
        for ex in all_ex[::-1]:
            # If ThreadEndedByMaster was raised, assume the error handling in
            # util.concurrently will print the error message
            if ex[0] is not util.ThreadEndedByMaster:
                depth = len(tuple(traceback.walk_tb(ex[2])))
                traceback.print_exception(*ex, limit=-(depth - 1))
                sys.stderr.write('(Exception suppressed to continue close)\n\n')

        self._owner._console.debug('closed')

    def __repr__(self):
        return repr(self._owner)

    def __str__(self):
        return getattr(self._owner, '_instname', None) or repr(self)


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
        managers.update(recursive_owner_managers(owner))
        # managers[name] = OwnerContextAdapter(owner)

    if getattr(top, '_instname', None) is not None:
        name = '_'.join(top._instname.split('.')[1:])
        managers[name] = OwnerContextAdapter(top)
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
    firsts_desc = '->'.join([str(c) for c in first.values()])

    # then, other devices, which need to be ready before we start into Rack setup methods
    devices = {attr: remaining.pop(attr)
               for attr, obj in dict(remaining).items()
               if isinstance(obj, core.Device)}
    devices_desc = f"({', '.join([str(c) for c in devices.values()])})"
    devices = util.concurrently(name='', **devices)

    # what remain are instances of Rack and other Owner types    
    owners = recursive_owner_managers(top)
    owners_desc = f"({','.join([str(c) for c in owners.values()])})"

    # TODO: concurrent rack entry. This would mean device dependency
    # checking to ensure avoid race conditions
    # owners = util.concurrently(name='', **owners) # <- something like this

    # top._recursive_owners()
    # top._context.__enter__()
    # for child in top._owners.values():
    #     child.open()
    # # top.open()
    #
    # the dictionary here is a sequence
    seq = dict(first)
    if devices != {}:
        seq['_devices'] = devices
    seq.update(owners)

    desc = '->'.join([
        d for d in (firsts_desc, devices_desc, owners_desc)
        if len(d)>0]
    )

    log.debug(f"context order: {desc}")
    return util.sequentially(name=f'{repr(top)}', **seq) or null_context(top)


def propagate_instnames(parent_obj, parent_name=None):
    """ recursively update _instname in child instances of Owner
        classes or instances
    """
    if parent_name is None:
        parent_name = parent_obj.__name__

    for name, obj in parent_obj._owners.items():
        propagate_instnames(obj, parent_name+'.'+name)

    # some objects may be reused by children. apply
    # our own namespace last to ensure the highest-level
    # ownership is attributed
    for name, obj in parent_obj._ownables.items():
        obj._instname = parent_name+'.'+name


def owner_getattr_chains(owner):
    """ recursively perform getattr on the given sequence of names
    """
    ret = {owner: tuple()}

    for name, sub_owner in owner._owners.items():
        # add only new changes (overwrite redundant keys with prior values)
        ret = {
            **{
                obj: (name,)+chain
                for obj, chain in owner_getattr_chains(sub_owner).items()
            },
            **ret
        }

    return ret


class Owner:
    """ own context-managed instances of Device as well as setup and cleanup calls to owned instances of Owner
    """
    _ordered_entry = []
    _concurrent = True
    
    def __init_subclass__(cls, ordered_entry: list = None):
        # registries that will be context managed
        cls._devices = {} # each of cls._devices.values() these will be context managed
        cls._owners = {} # each of these will get courtesy calls to open and close between _device entry and exit
        cls._ownables = {}

        if ordered_entry is not None:
            for e in ordered_entry:
                if not issubclass(e, core.Device):
                    raise TypeError(f"ordered_entry item {e} is not a Device subclass")
            cls._ordered_entry = ordered_entry

        cls._propagate_ownership()

    def __meta_owner_init__(self, parent_name):
        """ called recursively on initialization of any owner above the
            scope of this owner
        """
        self._instname = parent_name+'.'+self.__name__

    @classmethod
    def _propagate_ownership(cls):
        cls._ownables = {}

        # prepare and register owned attributes
        attr_names = set(dir(cls)).difference(dir(Owner))

        # don't use cls.__dict__ here since we also need parent attributes
        for name in attr_names:
            obj = getattr(cls, name)

            if not isinstance(obj, util.Ownable):
                continue

            need_copy = isinstance(getattr(super(), name, None), util.Ownable)

            # prepare these first, so they are available to owned classes on __owner_subclass__
            if isinstance(obj, core.Device):
                if need_copy:
                    obj = copy.deepcopy(obj)
                cls._devices[name] = obj
                setattr(cls, name, obj)

            elif isinstance(obj, Owner):
                if need_copy:
                    obj = copy.deepcopy(obj)
                cls._owners[name] = obj
                setattr(cls, name, obj)

            cls._ownables[name] = obj

        # run the hooks in owned classes, now that cls._devices and cls._owners are ready for them
        for name, obj in cls._ownables.items():
            obj.__set_name__(cls, name)  # in case it was originally instantiated outside cls
            obj = obj.__owner_subclass__(cls)

            setattr(cls, name, obj)

        propagate_instnames(cls, cls.__name__)

    def __init__(self, **update_ownables):
        self._owners = dict(self._owners)

        # are the given objects ownable        
        unownable = {
            name: obj
            for name, obj in update_ownables.items()
            if not isinstance(obj, util.Ownable)
        }
        if len(unownable) > 0:
            raise TypeError(f"keyword arguments {unownable} are not ownable objects")            

        # update ownables
        unrecognized = set(update_ownables.keys()).difference(self._ownables.keys())
        if len(unrecognized) > 0:
            clsname = type(self).__qualname__
            unrecognized = tuple(unrecognized)
            raise TypeError(f"cannot update unrecognized attributes {unrecognized} of {clsname}")
        self._ownables = dict(self._ownables, **update_ownables)

        # update devices
        update_devices = {
            name: obj
            for name, obj in update_ownables.items()
            if isinstance(obj, core.Device)
        }
        unrecognized = set(update_devices.keys()).difference(self._devices.keys())
        if len(unrecognized) > 0:
            clsname = type(self).__qualname__
            unrecognized = tuple(unrecognized)
            raise TypeError(f"{clsname} Device attributes {unrecognized} can only be instantiated with Device objects")
        self._devices = dict(self._devices, **update_devices)

        super().__init__()

        propagate_instnames(self, type(self).__name__)

        for name, obj in self._ownables.items():
            obj.__owner_init__(self)
        

    def __setattr__(self, key, obj):
        # update naming for any util.Ownable instances
        if isinstance(obj, util.Ownable):
            self._ownables[key] = obj
            if getattr(obj, '__objclass__', None) is not type(self):
                obj.__set_name__(type(self), key)
                obj.__owner_init__(self)

        if isinstance(obj, core.Device):
            self._devices[key] = obj

        if isinstance(obj, Owner):
            self._owners[key] = obj

        object.__setattr__(self, key, obj)

    def close(self):
        pass

    def open(self):
        pass

    @property
    def __enter__(self):
        self._context = owner_context_manager(self)

        @wraps(type(self).__enter__.fget)
        def __enter__():
            self._context.__enter__()
            return self

        return __enter__

    @property
    def __exit__(self):
        # pass along from self._context
        return self._context.__exit__


@util.hide_in_traceback
def __call__():
    # util.wrap_attribute will munge the call signature above for clean introspection in IDEs
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))
    return self.__call___wrapped(**items)


class Sequence(util.Ownable):
    """ Define an experiment built from methods in Rack instances. The input is a specification for sequencing these
    steps, including support for threading. The output is a callable function that can be assigned as a method
    to a top-level "root" Rack.
    """

    def __init__(self, **specification):
        def spec_step(sequence):
            """ standardize the specification dict to  {name: [methods]}
            """
            if isinstance(sequence, (list, tuple)):
                # specification for a concurrent and/or sequential calls to Method methods
                sequence = list(sequence)

            elif isinstance(sequence, Method):
                # a Method method that is already packaged for use
                sequence = [sequence]

            elif inspect.ismethod(sequence):
                sequence = [Method(sequence.__self__, sequence.__name__)]

            else:
                typename = type(sequence).__qualname__
                raise TypeError(f"object of type '{typename}' is neither a Rack method nor a nested tuple/list")

            return sequence

        self.spec = {
            k: spec_step(spec)
            for k, spec in specification.items()
        }

        self.access_spec = None

    def __owner_subclass__(self, owner_cls):
        if self.access_spec is None:
            # transform the objects in self.spec
            # into attribute names for dynamic access
            # in case of later copying and subclassing
            chain = owner_getattr_chains(owner_cls)
            self.access_spec = {
                k: [chain[s._owner]+(s.__name__,) for s in spec]
                for k, spec in self.spec.items()
            }

        return self

    @staticmethod
    def _subclass_method_remap(cls):
        return {}
        if hasattr(cls, '__mro__'):
            cls = cls
        else:
            cls = type(cls)

        parent = cls.__mro__[1]

        ret = {}
        for owner in cls._owners.values():
            ret.update(Sequence._subclass_method_remap(owner))

        if hasattr(cls, '_methods'):
            ret.update({
                obj: getattr(cls, name)
                for name, obj in parent._methods.items()
            })
        # ret.update(cls_or_obj._ownables)
        return ret


    def __owner_init__(self, owner):
        """ make a bound sequence for the owner when it is instantiated,
            which can be called.
        """

        def attr_chain_to_method(root_obj, chain):
            """ follow the chain with nested getattr
                calls to access the chain object
            """
            obj = root_obj

            for name in chain[:-1]:
                obj = getattr(obj, name)
            
            if hasattr(obj, '_methods'):
                return Method.from_method(obj._methods[chain[-1]])
            
            attr = getattr(obj, chain[-1])
            if isinstance(attr, Method):
                return Method.from_method(attr)

            else:
                return Method(obj, chain[-1])

        super().__owner_init__(owner)

        # initialization on the parent class definition
        # waited until after __set_name__, because this depends on __name__ having been set for the tasks task
        spec = {
            k: [attr_chain_to_method(owner,c) for c in chain]
            for k, chain in self.access_spec.items()
        }
        self.last_spec = spec

        # determine the call signature for the new Sequence procedure
        signatures = self._collect_signatures(spec)
        params = tuple(signatures.keys())  # *all* of the parameters, before pruning non-default ones
        defaults = dict([(arg, sig[0]) for arg, sig in signatures.items() if sig[0] is not EMPTY])
        annots = dict([(arg, sig[1]) for arg, sig in signatures.items() if sig[1] is not EMPTY])

        # build the callable object with a newly-defined subclass.
        # tricks ipython/jupyter into showing the call signature.
        ns = dict(
            sequence=spec,
            params=params,
            defaults=defaults,
            annotations=annots,
            signatures=signatures,
            dependencies=self._dependency_map(spec),
            __name__=self.__name__,
            __qualname__=type(owner).__qualname__+'.'+self.__name__,
            __objclass__=self.__objclass__,
            __owner_subclass__=self.__owner_subclass__ # in case the owner changes and calls this again
        )

        cls = type(BoundSequence.__name__, (BoundSequence,), ns)

        util.wrap_attribute(
            cls, '__call__', __call__, fields=params, defaults=defaults,
            annotations=annots, positional=0
        )

        # the testbed gets this BoundSequence instance in place of self
        obj = object.__new__(cls)
        obj.__init__()
        setattr(owner, self.__name__, obj)

    def _dependency_map(self, spec, owner_deps={}) -> dict:
        """ list of Device dependencies of each Method.

        :returns: {Device instance: reference to method that uses Device instance}
        """

        deps = dict(owner_deps)

        for spec in spec.values():
            for func in spec:
                if not isinstance(func, (Method, BoundSequence)):
                    raise TypeError(f"expected Method instance, but got '{type(func).__qualname__}' instead")

                # race condition check
                conflicts = set(deps.keys()).intersection(func.dependencies)
                if len(conflicts) > 0:
                    users = {deps[device] for device in conflicts}
                    raise RuntimeError(f"risk of concurrent access to {conflicts} by {users}")

                deps.update({device.__name__: device for device in func.dependencies})

        return deps

    def _collect_signatures(self, spec):
        """ collect a dictionary of parameter default values

        :param tree: nested list of calls that contains the parsed call tree
        :return: dict keyed on parameter name, with values that are a list of (caller, default_value) pairs.
            default_value is `EMPTY` if there is no default.
        """

        signatures = {}

        # collect the defaults
        for funcs in spec.values():
            for func in funcs:
                # pull a dictionary of signature values (default, annotation) with EMPTY as a null sentinel value
                for argname, (def_, annot) in func.long_kwarg_signature().items():
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


def _note_before(cm, key, text, indent=0):
    cm.yaml_set_comment_before_after_key(key, before=text, indent=indent)

def _note_eol(cm, key, text):
    cm.yaml_add_eol_comment(comment=text, key=key)


class RackMeta(type):
    CONFIG_FILENAME = f'rack.yaml'

    @classmethod
    def from_module(metacls, module_str, cls_name):
        module = importlib.import_module(module_str)
        return getattr(module, cls_name)

    def wrap_module(cls, module):
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

    @classmethod
    def from_config(metacls, config_path, apply=True):
        """ read a
        """
        with open(Path(config_path)/metacls.CONFIG_FILENAME,'r') as f:
            config = yaml.load(f)
            util.console.debug(f"loaded configuration from {repr(str(config_path))}")

        rack_cls = metacls.from_module(
            config['source']['module'],
            config['source']['name']
        )

        # subclass the Rack so that we don't change its values
        if apply:
            # prepare a subclassed copy to avoid changing the actual class definition
            new_cls = type(rack_cls.__name__, (rack_cls,), {})
            new_cls.__qualname__ = rack_cls.__qualname__
            new_cls.__module__ = rack_cls.__module__

            metacls._apply_device_values(new_cls, config['devices'])
            metacls._apply_sequence_defaults(new_cls, config['sequence_kwdefaults'])

            rack_cls._propagate_ownership()
            rack_cls = new_cls
        
        return rack_cls

    def _apply_device_values(rack_cls, device_kwargs):
        """ make a dictionary of new device instances using the supplied
            mapping of keyword argument dictionarys, keyed on {device_name: kwargs_dict}
        """
        
        for dev_name, dev in rack_cls._devices.items():
            for trait_name, value in device_kwargs[dev_name].items():
                setattr(dev, trait_name, value)

    @classmethod
    def _apply_sequence_defaults(metacls, rack_cls, defaults_in):
        """ adjust the method argument parameters in the Rack subclass `cls` according to config file
        """
        # path = Path(root_path)/self.CONFIG_FILENAME

        # # if getattr(self.rack_cls, '__config_path__', None) == str(path):
        # #     util.console.debug(f"already have {path}")
        # #     util.console.debug(f"already have {cls.__config_path__}")
        # #     return
        # # else:
        # #     cls.__config_path__ = str(path)

        defaults, annots, methods, names = metacls._get_sequence_parameters(rack_cls)

        # # read the existing defaults
        # defaults_in = {}
        # if path.exists():
        #     with open(path, 'rb') as f:
        #         defaults_in = yaml.safe_load(f) or {}

        for k, v in dict(defaults_in).items():
            if v == defaults[k]:
                del defaults_in[k]
                continue

            if k not in methods:
                raise KeyError(f"sequence_kwdefaults configuration key '{k}' is not a parameter in any method of '{rack_cls.__qualname__}'")
            elif annots[k] is not EMPTY and not isinstance(v, annots[k]):
                raise TypeError(f"the sequence_kwdefaults configuration at key '{k}' with value '{v}' conflicts "
                                f"with type annotation '{annots[k]}'")

            # update the call signature
            method = methods[k]

            if isinstance(method, Method):
                method.set_kwdefault(names[k], v)
            else:
                if method.__kwdefaults__ is None:
                    method.__kwdefaults__ = {}
                method.__kwdefaults__[names[k]] = v

        if len(defaults_in) > 0:
            util.console.debug(f"applied defaults {defaults_in}")

        # take the updated defaults
        defaults.update(defaults_in)

    # def _repropagate_ownership(rack_cls):
    #     # reinitialize the subclass to propagate changes to Sequence keyword signatures
    #     for name in dir(rack_cls):
    #         obj = getattr(rack_cls, name)
    #         if isinstance(obj, util.Ownable):
    #             obj.__set_name__(rack_cls, name)  # in case it was originally instantiated outside cls
    #             new_obj = obj.__owner_subclass__(rack_cls)

    #             setattr(rack_cls, name, new_obj)

    @classmethod
    def to_config(metacls, cls, path, with_defaults=False):
        path = Path(path)
        path.mkdir(exist_ok=False, parents=True)

        with open(path/metacls.CONFIG_FILENAME, 'w') as stream:
            cm = CommentedMap(
                source=dict(
                    name=cls.__name__,
                    module=cls.__module__
                ),
                sequence_kwdefaults=metacls._serialize_sequence_parameters(cls),
                devices=metacls._serialize_devices(cls),
            )

            _note_before(
                cm,
                'source',
                'Rack class source import strings for the python interpreter'
            )

            _note_before(
                cm,
                'sequence_defaults',
                '\nparameter defaults for sequences in rack:'
                '\nthese parameters can be omitted from sequence table columns'
            )

            _note_before(
                cm,
                'devices',
                '\ndevice settings: initial values for value traits'
            )

            yaml.dump(cm, stream)

        for name, attr in cls.__dict__.items():
            if isinstance(attr, Sequence):
                metacls.to_sequence_table(cls, name, path, with_defaults=with_defaults)

    def to_sequence_table(cls, name, path, with_defaults=False):
        # TODO: configure whether/which defaults are included as columns
        root_path = Path(path)
        
        seq = getattr(cls, name)
        if not isinstance(seq, Sequence):
            raise TypeError(f"{seq} is not a Sequence")

        sigs = [
            name
            for name,(default,annot) in seq._collect_signatures(seq.spec).items()
            if with_defaults or default is EMPTY
        ]

        df = pd.DataFrame(columns=sigs)
        df.index.name = 'Condition name'
        path = root_path/f'{seq.__name__}.csv'
        df.to_csv(path)
        util.console.debug(f"writing csv template to {repr(path)}")

    @classmethod
    def _serialize_sequence_parameters(metacls, cls):
        defaults, annots, *_ = metacls._get_sequence_parameters(cls)

        cm = CommentedMap({
            k:(None if v is EMPTY else v)
            for k,v in defaults.items()
        })

        keys = list(cm.keys())

        # find the last key for a non-default entry, which we'll need to comment out lines before the last one
        for k in keys[::-1]:
            if defaults[k] is not EMPTY:
                last_default_key = k
                break
        else:
            raise ValueError(f"currently require a default keyword from least 1 parameter (TODO: fix this)")

        for i,k in enumerate(keys[::-1]):
            if defaults[k] is EMPTY:
                _note_before(cm, last_default_key, round_trip_dump({k: None}))
                del cm[k]
            else:
                last_default_key = k
                if annots[k] is not EMPTY:
                    _note_eol(cm, k, f'{annots[k].__name__}')

        return cm

    def _serialize_devices(cls):
        defaults = {
            dev_name: {k:getattr(dev, k) for k in dev._value_attrs if dev._traits[k].sets}
            for dev_name, dev in cls._devices.items()
        }

        return CommentedMap(defaults)

    @classmethod
    def _get_sequence_parameters(metacls, rack_cls):
        """ introspect the arguments used in a sequence. cls is the Rack class or a subclass
        """
        defaults = {}
        annots = {}
        methods = {}
        names = {}

        for owner in rack_cls._owners.values():
            if isinstance(owner, Rack):
                d, a, m, n = metacls._get_sequence_parameters(owner)
                defaults.update({owner.__name__+'_'+k: v for k, v in d.items()})
                annots.update({owner.__name__+'_'+k: v for k, v in a.items()})
                methods.update({owner.__name__ + '_' + k: v for k, v in m.items()})
                names.update({owner.__name__ + '_' + k: k for k, v in m.items()})

        for step in rack_cls._methods.values():
            params = iter(inspect.signature(step).parameters.items())
            next(params) # skip 'self'

            for k, p in params:
                methods[k] = step
                if annots.setdefault(k, p.annotation) is EMPTY:
                    annots[k] = p.annotation
                elif EMPTY not in (p.annotation, annots[k]) and p.annotation != annots[k]:
                    raise ValueError(f"conflicting type annotations '{p.annotation}' and '{annots[k]}' in {rack_cls.__qualname__} methods")
                if not inspect.isclass(annots[k]):
                    raise TypeError(f"annotation '{annots[k]}' for parameter '{k}' in '{rack_cls.__qualname__}' is not a class")

                if defaults.setdefault(k, p.default) is EMPTY:
                    defaults[k] = p.default
                elif EMPTY not in (p.default, defaults[k]) and p.default != defaults[k]:
                    raise ValueError(f"conflicting defaults '{p.default}' and '{defaults[k]}' in {rack_cls.__qualname__} methods")

            for k in defaults:
                if EMPTY not in (annots[k], defaults[k]) and not isinstance(defaults[k], annots[k]):
                    raise TypeError(f"default '{defaults[k]}' does not match type annotation "
                                    f"'{annots[k]}' in '{rack_cls.__qualname__}' is not a class")

        return defaults, annots, methods, names        

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

    def __init_subclass__(cls, ordered_entry=[]):
        cls._ordered_entry = ordered_entry

        # register step methods
        cls._methods = {}
        attr_names = sorted(set(dir(cls)).difference(dir(Owner)))
        # attrs = ((name, getattr(cls, name)) for name in attr_names)
        # cls._methods = {
        #     name: obj
        #     for name, obj in attrs
        #     if name[0] != '_' and (inspect.ismethod(obj) or isinstance(obj, Method))
        # }

        # not using cls.__dict__ because it neglects parent classes
        for name in attr_names:
            obj = getattr(cls, name)
            if isinstance(obj, (core.Device, Owner, Sequence, BoundSequence)):
                continue
            if not name.startswith('_') and callable(obj):
                cls._methods[name] = obj

        # include annotations from parent classes
        cls.__annotations__ = dict(getattr(super(), '__annotations__', {}),
                                   **getattr(cls, '__annotations__', {}))
        cls.__init__.__annotations__ = cls.__annotations__

        super().__init_subclass__(ordered_entry=ordered_entry)

        # # sentinel values for each annotations (largely to support IDE introspection)
        # for name, annot_cls in cls.__annotations__.items():
        #     if name in cls._methods:
        #         clsname = cls.__qualname__
        #         raise AttributeError(f"'{clsname}' device annotation and method conflict for attribute '{name}'")
        #     else:
        #         setattr(cls, name, annot_cls())

    def __init__(self, **devices):
        super().__init__(**devices)

        display_name = getattr(self, '_instname', type(self).__name__)
        self._console = util.console.logger.getChild(str(self))
        self._console = logging.LoggerAdapter(self._console, dict(rack=display_name, origin=f" - " + str(self)))

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

        # wrap self._methods as necessary
        self._methods = {
            k: (obj if isinstance(obj, Method) else Method(self, k))
            for k, obj in self._methods.items()
        }

    def __deepcopy__(self, memo=None):
        """ Called when an owning class is subclassed
        """
        owners = {
            name: copy.deepcopy(obj)
            for name, obj in self._owners.items()
        }

        # steps = {name: copy.deepcopy(obj) for name, obj in type(self)._methods.items()}
        namespace = dict(
            __annotations__=type(self).__annotations__,
            __module__ = type(self).__module__,
            **owners
        )

        # return self
        namespace.update(owners)

        subcls = type(self.__class__.__name__, (type(self),), namespace)
        return subcls(**self._devices)

    def __owner_init__(self, owner):
        super().__owner_init__(owner)
        self._console = util.console.logger.getChild(str(self))
        self._console = logging.LoggerAdapter(self._console, dict(rack=repr(self), origin=f" - "+str(self)))

    def __getattribute__(self, item):
        if item != '_methods' and item in self._methods:
            return self._methods[item]
        else:
            return super().__getattribute__(item)

    def __getitem__(self, item):
        return self._methods[item]

    def __len__(self):
        return len(self._methods)

    def __iter__(self):
        return (getattr(self, k) for k in self._methods)