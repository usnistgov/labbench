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

import contextlib
import copy
import importlib
import inspect
import logging
import sys
import time
import traceback
from functools import wraps
from pathlib import Path

import pandas as pd

from . import _device as core
from . import util as util

EMPTY = inspect.Parameter.empty


@contextlib.contextmanager
def null_context(owner):
    yield owner


class notify:
    """Singleton notification handler shared by all Rack instances"""

    # the global mapping of references to notification callbacks
    _handlers = dict(returns=set(), calls=set())

    @classmethod
    def clear(cls):
        cls._handlers = dict(returns=set(), calls=set())

    @classmethod
    def return_event(cls, returned: dict):
        if not isinstance(returned, dict):
            raise TypeError(f"returned data was {repr(returned)}, which is not a dict")
        for handler in cls._handlers["returns"]:
            handler(returned)

    @classmethod
    def call_event(cls, parameters: dict):
        if not isinstance(parameters, dict):
            raise TypeError(
                f"parameters data was {repr(parameters)}, which is not a dict"
            )
        for handler in cls._handlers["calls"]:
            handler(parameters)

    @classmethod
    def observe_returns(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers["returns"].add(handler)

    @classmethod
    def observe_calls(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers["calls"].add(handler)

    @classmethod
    def unobserve_returns(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers["returns"].remove(handler)

    @classmethod
    def unobserve_calls(cls, handler):
        if not callable(handler):
            raise AttributeError(f"{repr(handler)} is not callable")
        cls._handlers["calls"].remove(handler)


class Method(util.Ownable):
    """Wrapper for class methods to support use with Sequence"""

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
        self.__qualname__ = getattr(obj, "__qualname__", obj.__class__.__qualname__)

        self._introspect()

        setattr(owner, name, self)

    @classmethod
    def from_method(self, method):
        """make a new Method instance by copying another"""
        return Method(method._owner, method.__name__, method._kwdefaults)

    def __copy__(self):
        return self.from_method(self)

    def __deepcopy__(self, memo=None):
        return self.from_method(self)

    def _introspect(self):
        """update self.__signature__"""
        self.__call__ = util.copy_func(self.__call__)

        # note the devices needed to execute this function
        if isinstance(self._owner, Rack):
            annotations = getattr(self._owner, "__annotations__", {})

            # set logic to identify Device dependencies
            available = {getattr(self._owner, name) for name in annotations}

            accessed = {
                getattr(self._owner, name)
                for name in util.accessed_attributes(self._wrapped)
                if not name.startswith("_") and hasattr(self._owner, name)
            }

            self.dependencies = available.intersection(accessed)
        else:
            self.dependencies = set()

        # get the signature, apply parameter defaults from self._kwdefaults
        sig = inspect.signature(self._wrapped)
        sig = sig.replace(
            parameters=(
                p.replace(default=self._kwdefaults.get(k, p.default))
                for k, p in sig.parameters.items()
            )
        )

        # set the call signature shown by help(), or with ? in ipython/jupyter
        self.__call__.__signature__ = sig

        # remember only named keywords, not "*args" and "**kwargs" in call signatures
        SKIP_KINDS = (
            inspect._ParameterKind.VAR_KEYWORD,
            inspect._ParameterKind.VAR_POSITIONAL,
        )
        # self.args = list(sig.parameters.keys())[1:]  # skip 'self' argument
        self._parameters = [
            p for p in sig.parameters.values() if p.kind not in SKIP_KINDS
        ][1:]

    def set_kwdefault(self, name, value):
        self._kwdefaults[name] = value

        sig = self.__call__.__signature__
        update = {name: sig.parameters[name].replace(default=value)}
        sig = sig.replace(parameters=dict(sig.parameters, **update).values())
        self.__call__.__signature__ = sig

        # if value is EMPTY:
        #     self._kwdefaults.pop(name, None)
        # elif name not in self.__signature__.parameters:
        #     raise TypeError(f"{self} has no keyword argument {repr(name)}")
        # else:
        #     self._kwdefaults[name] = value

        # self._introspect()

        # if value is EMPTY:
        #     del self._kwdefaults[name]
        # else:
        #     self._kwdefaults[name] = value

        # self.introspect()

    def extended_signature(self):
        """maps extended keyword argument names into a copy of self.__call__.__signature__"""
        sig = self.__call__.__signature__
        ext_names = self.extended_argname_names()

        params = list(sig.parameters.values())[1:]

        return sig.replace(
            parameters=[param.replace(name=k) for k, param in zip(ext_names, params)]
        )

    def extended_argname_names(self):
        sig = self.__call__.__signature__
        prefix = self._owner.__name__ + "_"
        names = list(sig.parameters.keys())[1:]
        return [prefix + name for name in names]

    @util.hide_in_traceback
    def extended_argname_call(self, *args, **kws):
        """rename keywords from the long form used by an owning class"""
        i = len(self._owner.__name__) + 1

        # remove the leading name of the owner
        kws = {k[i:]: v for k, v in kws.items()}
        return self.__call__(*args, **kws)

    @util.hide_in_traceback
    def __call__(self, *args, **kws):
        # validate arguments against the signature
        inspect.signature(self.__call__).bind(*args, **kws)

        # ensure that required devices are connected
        closed = [dev._owned_name for dev in self.dependencies if not dev.isopen]
        if len(closed) > 0:
            closed = ", ".join(closed)
            raise ConnectionError(
                f"devices {closed} must be connected to invoke {self.__qualname__}"
            )

        # notify observers about the parameters passed
        name_prefix = "_".join(self._owner._owned_name.split(".")[1:]) + "_"
        if len(kws) > 0:
            notify_params = {name_prefix + k: v for k, v in kws.items()}
            notify.call_event(notify_params)

        # invoke the wrapped function
        t0 = time.perf_counter()
        ret = self._wrapped(self._owner, *args, **kws)
        elapsed = time.perf_counter() - t0
        if elapsed > 0.1:
            util.logger.debug(f"{self._owned_name} completed in {elapsed:0.2f}s")

        # notify observers about the returned value
        if ret is not None:
            need_notify = (
                ret if isinstance(ret, dict) else {name_prefix + self.__name__: ret}
            )
            notify.return_event(need_notify)

        return {} if ret is None else ret

    def __repr__(self):
        try:
            wrapped = repr(self._wrapped)[1:-1]
            return f"<{wrapped} wrapped by {type(self).__module__}.{type(self).__name__} object>"
        except AttributeError:
            return f"<{type(self).__module__}.{type(self).__name__} wrapper>"


class BoundSequence(util.Ownable):
    """callable realization of a test sequence definition which
    takes the place of Sequence objects on instantiation of
    a new Rack object. its keyword arguments are aggregated
    from all of the methods called by the Sequence.
    """

    @util.hide_in_traceback
    def __call__(self, **kwargs):
        # validate arguments against the signature
        inspect.signature(self.__call__).bind(**kwargs)

        ret = {}

        for i, (name, sequence) in enumerate(self.sequence.items()):
            step_kws = self._step(sequence, kwargs)

            util.logger.debug(
                f"{self.__objclass__.__qualname__}.{self.__name__} ({i+1}/{len(self.sequence)}) - '{name}'"
            )
            ret.update(util.concurrently(**step_kws) or {})

        util.logger.debug(f"{self.__objclass__.__qualname__}.{self.__name__} finished")

        return ret

    @classmethod
    def to_template(cls, path):
        if path is None:
            path = f"{cls.__name__} template.csv"
        util.logger.debug(f"writing csv template to {repr(path)}")
        params = inspect.signature(cls.__call__).parameters
        df = pd.DataFrame(columns=list(params)[1:])
        df.index.name = "Condition name"
        df.to_csv(path)

    def iterate_from_csv(self, path):
        """call the BoundSequence for each row in a csv table.
        keyword argument names are taken from the column header
        (0th row). keyword values are taken from corresponding column in
        each row.
        """
        table = pd.read_csv(path, index_col=0)
        for i, row in enumerate(table.index):
            util.logger.info(
                f"{self._owned_name} from '{str(path)}' "
                f"- '{row}' ({i+1}/{len(table.index)})"
            )
            self.results = self(**table.loc[row].to_dict())

    def _step(self, spec, kwargs):
        """ """

        available = set(kwargs.keys())

        def call(func):
            # make a Call object with the subset of `kwargs`
            keys = available.intersection(func.extended_argname_names())
            params = {k: kwargs[k] for k in keys}
            return util.Call(func.extended_argname_call, **params)

        kws_out = {}

        for item in spec:
            if callable(item):
                name = item._owner.__class__.__qualname__ + "_" + item.__name__
                kws_out[name] = call(item)
            elif isinstance(item, list):
                kws_out[name] = self._step(item, kwargs)
            else:
                msg = (
                    f"unsupported type '{type(item).__qualname__}' "
                    f"in call sequence specification"
                )
                raise ValueError(msg)

        return kws_out


class OwnerContextAdapter:
    """transform calls to __enter__ -> open and __exit__ -> close.
    each will be called

    """

    def __init__(self, owner):
        self._owner = owner
        self._owned_name = getattr(owner, "_owned_name", repr(owner))

        display_name = getattr(self, "_owned_name", type(self).__name__)

    def __enter__(self):
        cls = type(self._owner)
        for opener in core.trace_methods(cls, "open", Owner)[::-1]:
            opener(self._owner)

        # self._owner.open()
        getattr(self._owner, "_logger", util.logger).debug("opened")

    def __exit__(self, *exc_info):
        cls = type(self._owner)
        methods = core.trace_methods(cls, "close", Owner)

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
                sys.stderr.write("(Exception suppressed to continue close)\n\n")

        getattr(self._owner, "_logger", util.logger).debug("closed")

    def __repr__(self):
        return repr(self._owner)

    def __str__(self):
        return getattr(self._owner, "_owned_name", None) or repr(self)


def recursive_devices(top):
    entry_order = list(top._entry_order)
    devices = dict(top._devices)
    name_prefix = getattr(top, "__name__", "")
    if len(name_prefix) > 0:
        name_prefix = name_prefix + "."

    for owner in top._owners.values():
        children, o_entry_order = recursive_devices(owner)

        # this might be faster by reversing key and value order in devices (and thus children)?
        for name, child in children.items():
            if child not in devices.values():
                devices[name_prefix + name] = child

        entry_order.extend(o_entry_order)

    return devices, entry_order


def flatten_nested_owner_contexts(top) -> dict:
    """generate a flattened mapping of context managers to
    that nested Owner classes

    Returns:
        mapping of {name: contextmanager}
    """
    managers = {}
    for name, owner in top._owners.items():
        managers.update(flatten_nested_owner_contexts(owner))
        managers[name] = OwnerContextAdapter(owner)

    if getattr(top, "_owned_name", None) is not None:
        name = "_".join(top._owned_name.split(".")[1:])
        managers[name] = OwnerContextAdapter(top)
    elif "" not in managers:
        managers[""] = OwnerContextAdapter(top)
    else:
        raise KeyError(f"2 unbound owners in the manager tree")

    return managers


def package_owned_contexts(top):
    """
    Make a context manager for an owner that also enters any Owned members
    (recursively) Entry into this context will manage all of these.

    Arguments:
        top: top-level Owner

    Returns:
        Context manager
    """

    log = getattr(top, "_logger", util.logger)
    contexts, entry_order = recursive_devices(top)

    # like set(entry_order), but maintains order in python >= 3.7
    entry_order = tuple(dict.fromkeys(entry_order))
    order_desc = " -> ".join([e.__qualname__ for e in entry_order])
    log.debug(f"entry_order before other devices: {order_desc}")

    # Pull any objects of types listed by top.entry_order, in the
    # order of (1) the types listed in top.entry_order, then (2) the order
    # they appear in objs
    first = dict()
    remaining = dict(contexts)
    for cls in entry_order:
        for attr, obj in contexts.items():
            if isinstance(obj, cls):
                first[attr] = remaining.pop(attr)
    firsts_desc = "->".join([str(c) for c in first.values()])

    # then, other devices, which need to be ready before we start into Rack setup methods
    devices = {
        attr: remaining.pop(attr)
        for attr, obj in dict(remaining).items()
        if isinstance(obj, core.Device)
    }
    devices_desc = f"({', '.join([str(c) for c in devices.values()])})"
    devices = util.concurrently(name="", **devices)

    # what remain are instances of Rack and other Owner types
    owners = flatten_nested_owner_contexts(top)
    owners_desc = f"({','.join([str(c) for c in owners.values()])})"

    # TODO: concurrent rack entry. This would mean device dependency
    # checking to ensure avoid race conditions
    # owners = util.concurrently(name='', **owners) # <- something like this

    # top._recursive_owners()
    # top._context.__enter__()
    # for child in top._owners.values():
    #     child.open()
    # top.open()
    #
    # the dictionary here is a sequence
    seq = dict(first)
    if devices != {}:
        seq["_devices"] = devices
    seq.update(owners)

    desc = "->".join(
        [d for d in (firsts_desc, devices_desc, owners_desc) if len(d) > 0]
    )

    log.debug(f"context order: {desc}")
    return util.sequentially(name=f"{repr(top)}", **seq) or null_context(top)


def owner_getattr_chains(owner):
    """recursively perform getattr on the given sequence of names"""
    ret = {owner: tuple()}

    for name, sub_owner in owner._owners.items():
        # add only new changes (overwrite redundant keys with prior values)
        ret = {
            **{
                obj: (name,) + chain
                for obj, chain in owner_getattr_chains(sub_owner).items()
            },
            **ret,
        }

    return ret


class Owner:
    """own context-managed instances of Device as well as setup and cleanup calls to owned instances of Owner"""

    _entry_order = []
    _concurrent = True

    def __init_subclass__(cls, entry_order: list = None):
        # registries that will be context managed
        cls._devices = {}  # each of cls._devices.values() these will be context managed
        cls._owners = (
            {}
        )  # each of these will get courtesy calls to open and close between _device entry and exit
        cls._ownables = {}

        if entry_order is not None:
            for e in entry_order:
                if not issubclass(e, core.Device):
                    raise TypeError(f"entry_order item {e} is not a Device subclass")
            cls._entry_order = entry_order

        cls._propagate_ownership()

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
            obj.__set_name__(
                cls, name
            )  # in case it was originally instantiated outside cls
            obj = obj.__owner_subclass__(cls)

            setattr(cls, name, obj)

        # propagate_owned_names(cls, cls.__name__)

    def __init__(self, **update_ownables):
        self._owners = dict(self._owners)

        # are the given objects ownable
        unownable = {
            name: obj
            for name, obj in update_ownables.items()
            if not isinstance(obj, util.Ownable)
        }
        if len(unownable) > 0:
            raise TypeError(f"keyword argument objects {unownable} are not ownable")

        # update ownables
        unrecognized = set(update_ownables.keys()).difference(self._ownables.keys())
        if len(unrecognized) > 0:
            clsname = type(self).__qualname__
            unrecognized = tuple(unrecognized)
            raise TypeError(
                f"cannot update unrecognized attributes {unrecognized} of {clsname}"
            )
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
            raise TypeError(
                f"{clsname} Device attributes {unrecognized} can only be instantiated with Device objects"
            )
        self._devices = dict(self._devices, **update_devices)

        super().__init__()

        for obj in self._owners.values():
            obj.__owner_init__(self)

        for obj in self._ownables.values():
            # repeat this for Rack instances that are also Owners,
            # ensuring that obj._owned_name refers to the topmost
            # name
            obj.__owner_init__(self)

    def __setattr__(self, key, obj):
        # update naming for any util.Ownable instances
        if isinstance(obj, util.Ownable):
            self._ownables[key] = obj
            if getattr(obj, "__objclass__", None) is not type(self):
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
        self._context = package_owned_contexts(self)

        @wraps(type(self).__enter__.fget)
        def __enter__():
            self._context.__enter__()

            return self

        return __enter__

    @property
    def __exit__(self):
        # pass along from self._context
        return self._context.__exit__


def override_empty(a, b, param_name, field):
    """return no more than non-EMPTY value between two Parameter fields, otherwise raises TypeError"""

    nonempty = {a, b} - {EMPTY}

    if len(nonempty) == 2:
        msg = f"conflicting {field} {nonempty} in aggregating argument '{param_name}'"
        raise TypeError(msg)

    elif len(nonempty) == 1:
        ret = tuple(nonempty)[0]

        if field == "annotation" and not inspect.isclass(ret):
            raise TypeError(
                f"type annotation '{ret}' for parameter '{param_name}' is not a class"
            )

        return ret

    else:
        return EMPTY


def update_parameter_dict(dest: dict, signature: inspect.Signature):
    """updates the dest mapping with parameters taken from inspect.Signature.

    Items with the same name and defaults or annotations that are not EMPTY must be the same,
    or TypeError is raised.
    """
    # pull a dictionary of signature values (default, annotation) with EMPTY as a null sentinel value
    if not hasattr(signature, "parameters"):
        parameters = signature
    else:
        parameters = signature.parameters

    for name, param in parameters.items():
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            continue
        if name in dest:
            dest[name] = dest[name].replace(
                annotation=override_empty(
                    dest[name].annotation, param.annotation, name, "annotation"
                ),
                default=override_empty(
                    dest[name].default, param.default, name, "default"
                ),
            )

        else:
            dest[name] = param.replace(kind=inspect.Parameter.KEYWORD_ONLY)


def attr_chain_to_method(root_obj, chain):
    """follows the chain with nested getattr calls to access the chain object"""
    obj = root_obj

    for name in chain[:-1]:
        obj = getattr(obj, name)

    if hasattr(obj, "_methods"):
        return Method.from_method(obj._methods[chain[-1]])

    attr = getattr(obj, chain[-1])
    if isinstance(attr, Method):
        return Method.from_method(attr)

    else:
        return Method(obj, chain[-1])


def standardize_spec_step(sequence):
    """standardizes the sequence specification dict to  {name: [list of methods]}"""
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
        raise TypeError(
            f"object of type '{typename}' is neither a Rack method nor a nested tuple/list"
        )

    return sequence


class Sequence(util.Ownable):
    """Experiment definition from methods in Rack instances. The input is a specification for sequencing these
    steps, including support for threading. The output is a callable function that can be assigned as a method
    to a top-level "root" Rack.
    """

    def __init__(self, **specification):
        self.spec = {
            k: standardize_spec_step(spec) for k, spec in specification.items()
        }

        self.access_spec = None

    def __owner_subclass__(self, owner_cls):
        if self.access_spec is None:
            # transform the objects in self.spec
            # into attribute names for dynamic access
            # in case of later copying and subclassing
            chain = owner_getattr_chains(owner_cls)
            self.access_spec = {
                k: [chain[s._owner] + (s.__name__,) for s in spec]
                for k, spec in self.spec.items()
            }

        return self

    def __owner_init__(self, owner):
        """make a sequence bound to the owner"""

        # in case this is added through a
        self.__owner_subclass__(type(owner))

        super().__owner_init__(owner)

        # initialization on the parent class definition
        # waited until after __set_name__, because this depends on __name__ having been set for the tasks task
        spec = {
            k: [attr_chain_to_method(owner, c) for c in chain]
            for k, chain in self.access_spec.items()
        }
        self.last_spec = spec

        # build the callable object with a newly-defined subclass.
        # tricks ipython/jupyter into showing the call signature.
        ns = dict(
            sequence=spec,
            dependencies=self._dependency_map(spec),
            __name__=self.__name__,
            __qualname__=type(owner).__qualname__ + "." + self.__name__,
            __objclass__=self.__objclass__,
            __owner_subclass__=self.__owner_subclass__,  # in case the owner changes and calls this again
        )

        cls = type(BoundSequence.__name__, (BoundSequence,), ns)

        # Generate a signature for documentation and code autocomplete
        # params = [
        #     inspect.Parameter('self', kind=inspect.Parameter.POSITIONAL_ONLY),
        # ]

        # we need a wrapper so that __init__ can be modified separately for each subclass
        cls.__call__ = util.copy_func(cls.__call__)

        # merge together
        params = dict(
            self=inspect.Parameter("self", kind=inspect.Parameter.POSITIONAL_ONLY)
        )

        for funcs in spec.values():
            for func in funcs:
                update_parameter_dict(params, func.extended_signature())

        cls.__call__.__signature__ = inspect.Signature(parameters=params.values())

        # the testbed gets this BoundSequence instance in place of self
        obj = object.__new__(cls)
        obj.__init__()
        setattr(owner, self.__name__, obj)

    def _dependency_map(self, spec, owner_deps={}) -> dict:
        """maps the Device dependencies of each Method in spec.

        Returns:
            {Device instance: reference to method that uses Device instance}
        """

        deps = dict(owner_deps)

        for spec in spec.values():
            for func in spec:
                if not isinstance(func, (Method, BoundSequence)):
                    raise TypeError(
                        f"expected Method instance, but got '{type(func).__qualname__}' instead"
                    )

                # race condition check
                conflicts = set(deps.keys()).intersection(func.dependencies)
                if len(conflicts) > 0:
                    users = {deps[device] for device in conflicts}
                    raise RuntimeError(
                        f"risk of concurrent access to {conflicts} by {users}"
                    )

                deps.update({device.__name__: device for device in func.dependencies})

        return deps

    # def _aggregate_signatures(self, spec) -> inspect.Signature:
    #     """aggregates calls from the Sequence specification into a Signature object

    #     Arguments:
    #         spec: nested list of calls that contains the parsed call tree
    #     """

    #     agg_params = dict(
    #         self=inspect.Parameter('self', kind=inspect.Parameter.POSITIONAL_ONLY)
    #     )

    #     # collect the defaults
    #     for funcs in spec.values():
    #         for func in funcs:
    #             merge_keyword_parameters(agg_params, func.extended_signature().parameters)

    #     return inspect.Signature(parameters=agg_params.values())


class RackMeta(type):
    """metaclass for helpful exceptions"""

    def __enter__(cls):
        raise RuntimeError(
            f"the `with` block needs an instance - 'with {cls.__qualname__}():' instead of 'with {cls.__qualname__}:'"
        )

    def __exit__(cls, *exc_info):
        pass


class Rack(Owner, util.Ownable, metaclass=RackMeta):
    """A Rack provides context management and methods for groups of Device instances.

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

    def __init_subclass__(cls, entry_order=[]):
        cls._entry_order = entry_order

        # register step methods
        cls._methods = {}
        attr_names = sorted(set(dir(cls)).difference(dir(Owner)))

        # not using cls.__dict__ because it neglects parent classes
        for name in attr_names:
            obj = getattr(cls, name)
            if isinstance(obj, (core.Device, Owner, Sequence, BoundSequence)):
                continue
            if not name.startswith("_") and callable(obj):
                cls._methods[name] = obj

        # include annotations from parent classes
        cls.__annotations__ = dict(
            getattr(super(), "__annotations__", {}),
            **getattr(cls, "__annotations__", {}),
        )
        cls.__init__.__annotations__ = cls.__annotations__

        # adjust the __init__ signature for introspection/doc

        # Generate a signature for documentation and code autocomplete
        params = [
            inspect.Parameter("self", kind=inspect.Parameter.POSITIONAL_ONLY),
        ]

        # generate and apply the sequence of call signature parameters
        params += [
            inspect.Parameter(
                name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=getattr(cls, name, EMPTY),
                annotation=annot,
            )
            for name, annot in cls.__annotations__.items()
        ]

        # we need a wrapper so that __init__ can be modified separately for each subclass
        cls.__init__ = util.copy_func(cls.__init__)
        cls.__init__.__signature__ = inspect.Signature(params)

        super().__init_subclass__(entry_order=entry_order)

    def __init__(self, **ownables):
        # new dict mapping object for the same devices
        ownables = dict(ownables)
        annotations = dict(self.__annotations__)
        for name, dev in ownables.items():  # self.__annotations__.items():
            try:
                dev_type = annotations.pop(name)
            except KeyError:
                raise NameError(
                    f"{self.__class__.__qualname__}.__init__ was given invalid keyword argument '{name}'"
                )
            if not isinstance(dev, dev_type):
                msg = (
                    f"argument '{name}' is not an instance of '{dev_type.__qualname__}'"
                )
                raise AttributeError(msg)
            setattr(self, name, dev)

        # check for a valid instance in the class for each remaining attribute
        for name, dev_type in dict(annotations).items():
            if isinstance(getattr(self, name, EMPTY), dev_type):
                del annotations[name]

        # any remaining items in annotations are missing arguments
        if len(annotations) > 0:
            kwargs = [f"{repr(k)}: {v}" for k, v in annotations.items()]
            raise AttributeError(f"missing keyword arguments {', '.join(kwargs)}'")

        # now move forward with applying the devices
        super().__init__(**ownables)

        # wrap self._methods as necessary
        self._methods = {
            k: (obj if isinstance(obj, Method) else Method(self, k))
            for k, obj in self._methods.items()
        }

    def __deepcopy__(self, memo=None):
        """Called when an owning class is subclassed"""
        owners = {name: copy.deepcopy(obj) for name, obj in self._owners.items()}

        # steps = {name: copy.deepcopy(obj) for name, obj in type(self)._methods.items()}
        namespace = dict(
            __annotations__=type(self).__annotations__,
            __module__=type(self).__module__,
            **owners,
        )

        # return self
        namespace.update(owners)

        subcls = type(self.__class__.__name__, (type(self),), namespace)
        return subcls(**self._devices)

    def __owner_init__(self, owner):
        super().__owner_init__(owner)

    def __getattribute__(self, item):
        if item != "_methods" and item in self._methods:
            return self._methods[item]
        else:
            return super().__getattribute__(item)

    def __getitem__(self, item):
        return self._methods[item]

    def __len__(self):
        return len(self._methods)

    def __iter__(self):
        return (getattr(self, k) for k in self._methods)


def import_as_rack(
    import_str: str,
    cls_name: str = None,
    base_cls: type = Rack,
    replace_attrs: list = ["__doc__", "__module__"],
):
    """Creates a Rack subclass with the specified module's contents. Ownable objects are annotated
    by type, allowing the resulting class to be instantiated.

    Arguments:
        import_str: the name of the module to import

        cls_name: the name of the Rack subclass to import from the module (or None for a
                  new subclass with the module contents)

        base_cls: the base class to use for the new subclass

        replace_attrs: attributes of `base_cls` to replace from the module

    Exceptions:
        NameError: if there is an attribute name conflict between the module and base_cls

    Returns:
        A dynamically created subclass of base_cls
    """

    def isadaptable(name, obj):
        """skip function, module, and type attributes"""
        type_ok = not (
            inspect.isclass(obj) or inspect.ismodule(obj) or inspect.isfunction(obj)
        )

        # __name__ causes an undesired __name__ attribute to exist in the root Rack class
        # (this breaks logic that expects this to exist only in owned instances
        name_ok = name in replace_attrs or not name.startswith("_")

        return type_ok and name_ok

    module = importlib.import_module(import_str)

    if cls_name is not None:
        # work with the class specified in the module
        obj = getattr(module, cls_name)

        if issubclass(obj, base_cls):
            # it's already a Rack instance - return it
            return base_cls
        elif inspect.ismodule(obj):
            module = obj
        else:
            raise TypeError(
                f"{import_str}.{cls_name} is not a subclass of {base_cls.__qualname__}"
            )

        dunder_updates = dict()
    else:
        cls_name = "_as_rack"
        dunder_updates = dict(__module__=import_str)

    namespace = {
        # take namespace items that are not types or modules
        attr: obj
        for attr, obj in module.__dict__.items()
        if isadaptable(attr, obj)
    }

    # annotate the rack, which sets up the constructor signature that we use for config
    namespace["__annotations__"] = dict(
        {
            name: type(obj)
            for name, obj in namespace.items()
            if isinstance(obj, util.Ownable)
        },
        **getattr(module, "__attributes__", {}),
    )

    namespace.update(dunder_updates)

    # raise NameError on redundant names - overloading could be
    # very messy in this context
    name_conflicts = (
        set(namespace).intersection(base_cls.__dict__).difference(replace_attrs)
    )
    if len(name_conflicts) > 0:
        raise NameError(
            f"names {name_conflicts} in module '{module.__name__}' "
            f"conflict with attributes of '{base_cls.__qualname__}'"
        )

    # subclass into a new Rack
    return type(cls_name, (base_cls,), dict(base_cls.__dict__, **namespace))
