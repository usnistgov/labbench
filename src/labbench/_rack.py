from __future__ import annotations

import contextlib
import importlib
import inspect
import sys
import time
import traceback
from copy import deepcopy
from ctypes import ArgumentError
from dataclasses import dataclass
from functools import wraps

import typing_extensions as typing

from . import _device as core
from . import util as util

if typing.TYPE_CHECKING:
    import pandas as pd
else:
    pd = util.lazy_import('pandas')

EMPTY = inspect.Parameter.empty


@contextlib.contextmanager
def null_context(owner):
    yield owner


class NeverRaisedException(BaseException):
    pass


_INSPECT_SKIP_PARAMETER_KINDS = (
    # remember only named keywords, not "*args" and "**kwargs" in call signatures
    inspect._ParameterKind.VAR_KEYWORD,
    inspect._ParameterKind.VAR_POSITIONAL,
)


def _filter_signature_parameters(params: dict):
    return {
        p.name: p
        for p in list(params.values())[1:]
        if p.kind not in _INSPECT_SKIP_PARAMETER_KINDS
    }


class notify:
    """Singleton notification handler shared by all Rack instances"""

    # the global mapping of references to notification callbacks
    _handlers = dict(returns=set(), calls=set(), iteration=set())

    _owner_hold_list = set()

    @classmethod
    def clear(cls):
        cls._handlers = dict(returns=set(), calls=set(), iteration=set())

    @classmethod
    def hold_owner_notifications(cls, *owners):
        for owner in owners:
            cls._owner_hold_list.add(owner)

    @classmethod
    def allow_owner_notifications(cls, *owners):
        for owner in owners:
            try:
                cls._owner_hold_list.remove(owner)
            except KeyError:
                pass

    @classmethod
    def return_event(cls, owner, returned: dict):
        if owner in cls._owner_hold_list:
            return

        if not isinstance(returned, dict):
            raise TypeError(f'returned data was {returned!r}, which is not a dict')
        for handler in cls._handlers['returns']:
            handler(dict(name=owner._owned_name, owner=owner, old=None, new=returned))

    @classmethod
    def call_event(cls, owner, parameters: dict):
        if owner in cls._owner_hold_list:
            return

        if not isinstance(parameters, dict):
            raise TypeError(f'parameters data was {parameters!r}, which is not a dict')
        for handler in cls._handlers['calls']:
            handler(dict(name=owner._owned_name, owner=owner, old=None, new=parameters))

    @classmethod
    def call_iteration_event(
        cls, owner, index: int, step_name: str = None, total_count: int = None
    ):
        if owner in cls._owner_hold_list:
            return

        for handler in cls._handlers['iteration']:
            handler(
                dict(
                    name=owner._owned_name,
                    owner=owner,
                    old=None,
                    new=dict(index=index, step_name=step_name, total_count=total_count),
                )
            )

    @classmethod
    def observe_returns(cls, handler):
        if not callable(handler):
            raise AttributeError(f'{handler!r} is not callable')
        cls._handlers['returns'].add(handler)

    @classmethod
    def observe_calls(cls, handler):
        if not callable(handler):
            raise AttributeError(f'{handler!r} is not callable')
        cls._handlers['calls'].add(handler)

    @classmethod
    def observe_call_iteration(cls, handler):
        if not callable(handler):
            raise AttributeError(f'{handler!r} is not callable')
        cls._handlers['iteration'].add(handler)

    @classmethod
    def unobserve_returns(cls, handler):
        if not callable(handler):
            raise AttributeError(f'{handler!r} is not callable')

        try:
            cls._handlers['returns'].remove(handler)
        except KeyError:
            pass

    @classmethod
    def unobserve_calls(cls, handler):
        if not callable(handler):
            raise AttributeError(f'{handler!r} is not callable')
        try:
            cls._handlers['calls'].remove(handler)
        except KeyError:
            pass

    @classmethod
    def unobserve_call_iteration(cls, handler):
        if not callable(handler):
            raise AttributeError(f'{handler!r} is not callable')
        try:
            cls._handlers['iteration'].remove(handler)
        except KeyError:
            pass


class CallSignatureTemplate:
    def __init__(self, target):
        self.target = target

    def get_target(self, owner):
        if self.target is None or callable(self.target):
            return self.target

        if isinstance(owner, util.Ownable) and not hasattr(self.target, '__name__'):
            # might have no signature yet if it has not been claimed by its owner
            return None

        target = owner._ownables.get(self.target.__name__, self.target)

        if not callable(target):
            raise TypeError(
                f"'{getattr(target, '_owned_name', '__name__')}' is not callable"
            )

        return target

    def get_keyword_parameters(self, owner, skip_names):
        template_sig = inspect.signature(self.get_target(owner).__call__)
        # template_sig = inspect.signature(template_sig.bind(owner))

        return {
            name: p
            for name, p in template_sig.parameters.items()
            if name not in skip_names and p.kind in (p.KEYWORD_ONLY,)
        }


class MethodTaggerDataclass:
    """subclasses decorated with @dataclass will operate as decorators that stash annotated keywords here into the pending attribute dict"""

    pending = {}

    def __call__(self, func):
        self.pending.setdefault(func, {}).update(
            {n: getattr(self, n) for n in self.__annotations__}
        )

        return func


@dataclass
class rack_input_table(MethodTaggerDataclass):
    """tag a method defined in a Rack to support execution from a flat table.

    In practice, this often means a very long argument list.

    Arguments:
        table_path: location of the input table
    """

    table_path: str


@dataclass
class rack_kwargs_template(MethodTaggerDataclass):
    """tag a method defined in a Rack to replace a **kwargs argument using the signature of the specified callable.

    In practice, this often means a very long argument list.

    Arguments:
        callable_template: replace variable keyword arguments (**kwargs) with the keyword arguments defined in this callable

        skip: list of column names to omit
    """

    template: callable = None


class rack_kwargs_skip(MethodTaggerDataclass):
    """tag a method defined in a Rack to replace a **kwargs argument using the signature of the specified callable.

    In practice, this often means a very long argument list.

    Arguments:
        callable_template: replace variable keyword arguments (**kwargs) with the keyword arguments defined in this callable

        skip: list of column names to omit
    """

    skip: list = None

    def __init__(self, *arg_names):
        self.skip = arg_names


class RackMethod(util.Ownable):
    """a wrapper that is applied behind the scenes in Rack classes to support introspection"""

    def __init__(self, owner, name: str, kwdefaults: dict = {}):
        super().__init__()

        # def ownable(obj, name):
        #     return isinstance(getattr(self._owner, name), util.Ownable)

        self._owner = owner
        cls = owner.__class__
        obj = getattr(cls, name)

        # overwrite the namespace with tags from the table input
        tags = MethodTaggerDataclass.pending.pop(obj, {})

        if isinstance(obj, RackMethod):
            self._wrapped = obj._wrapped
            self._kwdefaults = dict(obj._kwdefaults)
            self._callable_template = obj._callable_template
            self.tags = obj.tags
        else:
            self._wrapped = obj
            self._kwdefaults = kwdefaults
            self._callable_template = CallSignatureTemplate(tags.pop('template', None))
            self.tags = tags

        # self.__call__.__name__  = self.__name__ = obj.__name__
        # self.__qualname__ = obj.__qualname__
        self.__doc__ = obj.__doc__
        self.__name__ = name
        self.__qualname__ = getattr(obj, '__qualname__', obj.__class__.__qualname__)

        self._apply_signature()

        setattr(owner, name, self)

    def iterate_from_csv(self, path):
        """call the BoundSequence for each row in a csv table.
        keyword argument names are taken from the column header
        (0th row). keyword values are taken from corresponding column in
        each row.
        """
        table = pd.read_csv(path, index_col=0)
        for i, row in enumerate(table.index):
            util.logger.info(
                f"{self._owned_name} from '{path!s}' "
                f"- '{row}' ({i+1}/{len(table.index)})"
            )
            notify.call_iteration_event(self, i, row, len(table.index))
            yield row, self(**table.loc[row].to_dict())

    @classmethod
    def from_method(self, method):
        """make a new RackMethod instance by copying another"""
        return RackMethod(method._owner, method.__name__, method._kwdefaults)

    def __copy__(self):
        return self.from_method(self)

    def __deepcopy__(self, memo=None):
        return self.from_method(self)

    def __owner_subclass__(self, owner_cls):
        # allow the owner class a chance to set up self.
        super().__owner_subclass__(owner_cls)
        self._apply_signature()

    def _apply_signature(self):
        """updates self.__signature__

        __owner_subclass__ must have been called first to do introspection on self._callable_template.
        """
        self.__call__ = util.copy_func(self.__call__)

        # note the devices needed to execute this function
        if isinstance(self._owner, Rack):
            annotations = getattr(self._owner, '__annotations__', {})

            # set logic to identify Device dependencies
            available = {getattr(self._owner, name) for name in annotations}

            accessed = set()
            for name in util.accessed_attributes(self._wrapped):
                if name.startswith('_') or not hasattr(self._owner, name):
                    continue
                obj = getattr(self._owner, name)
                if isinstance(obj, (util.Ownable,)):
                    accessed.add(obj)

            self.dependencies = available & accessed
        else:
            self.dependencies = set()

        # get the signature, apply parameter defaults from self._kwdefaults
        sig = inspect.signature(self._wrapped)
        params = dict(sig.parameters)

        # replace the **kwargs with specific keywords from the template function
        skip_param_names = list(self.tags.get('skip', []))

        if self._callable_template.get_target(self._owner) is not None:
            for kws_name, param in params.items():
                if param.kind is param.VAR_KEYWORD:
                    break
            else:
                raise ArgumentError(
                    f'cannot apply keyword arguments template to "{self._owned_name or self.__name__}", which does not accept keyword arguments'
                )

            try:
                template_params = self._callable_template.get_keyword_parameters(
                    self._owner, skip_param_names
                )
            except TypeError:
                pass
            else:
                skip_param_names.append(kws_name)

                params = dict(params, **template_params)

        # apply updated defaults
        sig = sig.replace(
            parameters=(
                p.replace(default=self._kwdefaults.get(name, p.default))
                for name, p in params.items()
                if name not in skip_param_names
            )
        )

        # set the call signature shown by help(), or with ? in ipython/jupyter
        self.__signature__ = self.__call__.__signature__ = sig

        # remember only named keywords, not "*args" and "**kwargs" in call signatures
        self._parameters = list(_filter_signature_parameters(sig.parameters).values())

    def set_kwdefault(self, name, new_default):
        self._kwdefaults[name] = new_default

        sig = self.__call__.__signature__
        parameters = dict(sig.parameters)

        p = parameters[name]

        # if there was no default before, delete now to bump this
        # parameter the end of the dictionary. this ensures no
        # default-less parameters come before default parameters.
        if p.default is EMPTY and new_default is not EMPTY:
            del parameters[name]
            p = p.replace(kind=inspect.Parameter.KEYWORD_ONLY)
        parameters[name] = p.replace(default=new_default)

        sig = sig.replace(parameters=parameters.values())
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

    def extended_signature(self, name_map={}):
        """maps extended keyword argument names into a copy of self.__call__.__signature__"""
        sig = self.__call__.__signature__
        ext_names = self.extended_arguments(name_map)

        param_list = list(_filter_signature_parameters(sig.parameters).values())

        return sig.replace(
            parameters=[
                param.replace(name=k) for k, param in zip(ext_names, param_list)
            ]
        )

    def extended_arguments(self, name_map={}):
        """returns a list of argument names from in the owned context.

        Arguments:
            name_map (dict): name remapping, overriding self.tags
        """
        # TODO: should these all have 'owner' as a name, to specify the context?
        sig = self.__call__.__signature__
        if hasattr(self._owner, '__name__'):
            prefix = self._owner.__name__ + '_'
        else:
            prefix = ''

        shared_names = self.tags.get('shared_names', [])
        name_map = dict(dict(zip(shared_names, shared_names)), **name_map)

        names = list(sig.parameters.keys())[1:]
        return [name_map.get(name, prefix + name) for name in names]

    @util.hide_in_traceback
    def call_by_extended_argnames(self, *args, **kws):
        """rename keywords from the long form used by an owning class"""
        prefix = self._owner.__name__ + '_'
        prefix_start = len(prefix)

        # TODO: this will break in some keyword name edge-cases.
        # there should be an explicit dictionary mapping
        # into the extended arg name instead of guesswork
        # remove the leading name of the owner
        kws = {
            (k[prefix_start:] if k.startswith(prefix) else k): v for k, v in kws.items()
        }

        if len(kws) > 0:
            # notify_params = {name_prefix + k: v for k, v in kws.items()}
            notify.call_event(self, kws)

        # inspect.signature(self.__call__).bind(self, *args, **kws)
        return self.__call__(self, *args, **kws)

    @util.hide_in_traceback
    def __call__(self, *args, **kws):
        # validate arguments against the signature
        inspect.signature(self.__call__).bind(self, *args, **kws)

        # ensure that required devices are connected
        # TODO: let the devices handle this. some interactions with devices are necessary
        # and good without being connected, for example setting paramattr.value attributes.
        # closed = [dev._owned_name for dev in self.dependencies if not dev.isopen]
        # if len(closed) > 0:
        #     closed = ", ".join(closed)
        #     raise ConnectionError(
        #         f"devices {closed} must be connected to invoke {self.__qualname__}"
        #     )

        # notify observers about the parameters passed
        # name_prefix = "_".join((self._owner._owned_name or "").split(".")[1:]) + "_"
        # if len(kws) > 0:
        #     # notify_params = {name_prefix + k: v for k, v in kws.items()}
        #     notify.call_event(kws)

        # invoke the wrapped function
        t0 = time.perf_counter()
        ret = self._wrapped(self._owner, *args, **kws)
        elapsed = time.perf_counter() - t0
        if elapsed > 0.1:
            util.logger.debug(f'{self._owned_name} completed in {elapsed:0.2f}s')

        # notify observers about the returned value
        if ret is not None:
            need_notify = ret if isinstance(ret, dict) else {self._owned_name: ret}
            notify.return_event(self, need_notify)

        return {} if ret is None else ret

    def __repr__(self):
        try:
            wrapped = repr(self._wrapped)[1:-1]
            return f'<{wrapped} wrapped by {type(self).__module__}.{type(self).__name__} object>'
        except AttributeError:
            return f'<{type(self).__module__}.{type(self).__name__} wrapper>'


class BoundSequence(util.Ownable):
    """callable realization of a test sequence definition which
    takes the place of Sequence objects on instantiation of
    a new Rack object. its keyword arguments are aggregated
    from all of the methods called by the Sequence.
    """

    cleanup_func = None
    exception_allowlist = NeverRaisedException

    @util.hide_in_traceback
    def __call__(self, **kwargs):
        # validate arguments against the signature
        inspect.signature(self.__call__).bind(**kwargs)

        ret = {}

        notify.call_event(self, kwargs)

        try:
            for i, sequence in enumerate(self.sequence):
                step_kws = self._step(sequence, kwargs)

                util.logger.debug(
                    # TODO: removing name metadata from each step removed a descriptive name here.
                    # add something back?
                    f'{self.__objclass__.__qualname__}.{self.__name__} ({i}/{len(self.sequence)})'
                )
                ret.update(util.concurrently(**step_kws) or {})
        except self.exception_allowlist as e:
            core.logger.warning(f'{e!s}')
            ret['exception'] = e.__class__.__name__
            if self.cleanup_func is not None:
                self.cleanup_func()

        util.logger.debug(
            f'{self.__objclass__.__qualname__}.{self.__name__} ({len(self.sequence)}/{len(self.sequence)}, finished)'
        )

        return ret

    @classmethod
    def to_template(cls, path):
        if path is None:
            path = f'{cls.__name__} template.csv'
        util.logger.debug(f'writing csv template to {path!r}')
        params = inspect.signature(cls.__call__).parameters
        df = pd.DataFrame(columns=list(params)[1:])
        df.index.name = cls.INDEX_COLUMN_NAME
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
                f"{self._owned_name} from '{path!s}' "
                f"- '{row}' ({i+1}/{len(table.index)})"
            )
            notify.call_iteration_event(self, i, row, len(table.index))
            yield row, self(**table.loc[row].to_dict())

    def _step(self, spec, kwargs):
        """ """

        available = set(kwargs.keys())
        shared_names = self.tags['shared_names']
        name_map = dict(zip(shared_names, shared_names))

        def call(func):
            # make a Call object with the subset of `kwargs`

            keys = available.intersection(func.extended_arguments(name_map=name_map))
            params = {k: kwargs[k] for k in keys}
            ret = util.Call(func.call_by_extended_argnames, **params)
            return ret

        kws_out = {}

        for item in spec:
            if callable(item):
                name = item._owner.__class__.__qualname__ + '_' + item.__name__
                kws_out[name] = call(item)
            elif isinstance(item, list):
                kws_out[name] = self._step(item, kwargs)
            else:
                msg = (
                    f"unsupported type '{type(item).__qualname__}' "
                    f'in call sequence specification'
                )
                raise ValueError(msg)

        return kws_out


class OwnerContextAdapter:
    """transform calls to __enter__ -> open and __exit__ -> close"""

    def __init__(self, owner):
        self._owner = owner
        self._owned_name = getattr(owner, '_owned_name', repr(owner))
        # display_name = getattr(self, "_owned_name", type(self).__name__)

    def __enter__(self):
        try:
            hold = [
                o for o in self._owner._ownables.values() if isinstance(o, RackMethod)
            ]
            notify.hold_owner_notifications(*hold)
            cls = type(self._owner)
            for opener in util.find_methods_in_mro(cls, 'open', Owner)[::-1]:
                if isinstance(opener, WrappedOpen):
                    opener.unwrapped(self._owner)
                else:
                    opener(self._owner)

            getattr(self._owner, '_logger', util.logger).debug('opened')

        finally:
            notify.allow_owner_notifications(*hold)

    def __exit__(self, *exc_info):
        try:
            holds = [
                o for o in self._owner._ownables.values() if isinstance(o, RackMethod)
            ]
            notify.hold_owner_notifications(*holds)
            cls = type(self._owner)
            methods = util.find_methods_in_mro(cls, 'close', Owner)

            all_ex = []
            for closer in methods:
                if isinstance(closer, WrappedClose):
                    closer = closer.unwrapped

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
                    # sys.stderr.write("(Exception suppressed to continue close)\n\n")

            getattr(self._owner, '_logger', util.logger).debug('closed')

        finally:
            notify.allow_owner_notifications(*holds)

            if len(all_ex) > 1:
                ex = util.ConcurrentException(
                    f'multiple exceptions while closing {self}'
                )
                ex.thread_exceptions = all_ex
                print(methods, len(all_ex))
                raise ex
            elif len(all_ex) == 1:
                raise all_ex[0][1]

    def __repr__(self):
        return repr(self._owner)

    def __str__(self):
        return getattr(self._owner, '_owned_name', None) or repr(self)


def flatten_nested_owner_contexts(top) -> dict:
    """recursively generate a flattened mapping of context managers nested Owners

    Returns:
        mapping of {name: contextmanager}
    """
    managers = {}
    for name, owner in top._owners.items():
        managers.update(flatten_nested_owner_contexts(owner))
        managers[name] = OwnerContextAdapter(owner)

    if '' in managers:
        obj = managers.pop('')
        managers[obj._owned_name] = obj

    if getattr(top, '_owned_name', None) is not None:
        name = '_'.join(top._owned_name.split('.')[1:])
        managers[name] = OwnerContextAdapter(top)
    elif '' not in managers:
        managers[''] = OwnerContextAdapter(top)
    else:
        raise KeyError(
            f"unbound owners in the manager tree: {managers['']._owned_name}"
        )

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

    log = getattr(top, '_logger', util.logger)
    contexts, entry_order = recursive_devices(top)

    # like set(entry_order), but maintains order in python >= 3.7
    entry_order = tuple(dict.fromkeys(entry_order))
    order_desc = ' -> '.join([e.__qualname__ for e in entry_order])
    if len(order_desc) > 0:
        log.debug(f'entry_order before other devices: {order_desc}')

    # Pull any objects of types listed by top.entry_order, in the
    # order of (1) the types listed in top.entry_order, then (2) the order
    # they appear in objs
    first = dict()
    remaining = dict(contexts)
    for cls in entry_order:
        for attr, obj in contexts.items():
            if isinstance(obj, cls):
                first[attr] = remaining.pop(attr)
    firsts_desc = '->'.join([str(c) for c in first.values()])

    # then, other devices, which need to be ready before we start into Rack setup methods
    devices = {
        attr: remaining.pop(attr)
        for attr, obj in dict(remaining).items()
        if isinstance(obj, core.Device)
    }
    devices_desc = f"({', '.join([str(c) for c in devices.values()])})"
    devices = util.concurrently(name='', which='context', **devices)

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
        seq['_devices'] = devices
    seq.update(owners)

    desc = '->'.join(
        [d for d in (firsts_desc, devices_desc, owners_desc) if len(d) > 0]
    )

    log.debug(f'context order: {desc}')
    return util.sequentially(name=f'{top!r}', **seq) or null_context(top)


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


class WrappedOpen:
    def __init__(self, obj: Owner):
        open_func = object.__getattribute__(obj, 'open')
        self.__call__ = wraps(open_func)(self)
        self.obj = obj
        self.unwrapped = open_func

    def __call__(self):
        if self.obj._context is None:
            self.obj._context = package_owned_contexts(self.obj)
            self.obj._context.__enter__()


class WrappedClose:
    def __init__(self, obj: Owner):
        close_func = object.__getattribute__(obj, 'close')
        self.__call__ = wraps(close_func)(self)
        self.obj = obj
        self.unwrapped = close_func

    def __call__(self):
        if self.obj._context is not None:
            try:
                self.obj._context.__exit__(*sys.exc_info())
            finally:
                self.obj._context = None
        else:
            self.unwrapped()


class Owner:
    """own context-managed instances of Device as well as setup and cleanup calls to owned instances of Owner"""

    _entry_order = []
    _concurrent = True

    def __init_subclass__(cls, entry_order: list = None):
        """type configuration performed each time a new subclass is created"""
        # registries that will be context managed
        cls._devices = {}  # each of cls._devices.values() these will be context managed
        cls._owners = {}  # each of these will get courtesy calls to open and close between _device entry and exit
        cls._ownables = {}

        if entry_order is not None:
            for e in entry_order:
                if not issubclass(e, core.Device):
                    raise TypeError(f'entry_order item {e} is not a Device subclass')
            cls._entry_order = entry_order

        cls.__propagate_cls_ownership__()

    @classmethod
    def __propagate_cls_ownership__(cls, copy=None):
        cls._ownables = {}

        # prepare and register owned attributes
        attr_names = set(dir(cls)).difference(dir(Owner))

        # don't use cls.__dict__ here since we also need parent attributes
        for name in attr_names:
            obj = getattr(cls, name)

            if not isinstance(obj, util.Ownable):
                continue

            if copy is None:
                need_copy = isinstance(getattr(super(), name, None), util.Ownable)
            else:
                need_copy = copy

            # prepare these first, so they are available to owned classes on __owner_subclass__
            if isinstance(obj, core.Device):
                if need_copy:
                    obj = deepcopy(obj)
                cls._devices[name] = obj
                setattr(cls, name, obj)

            elif isinstance(obj, Owner):
                if need_copy:
                    obj = deepcopy(obj)
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
        # seed the mappings for our instance from the class definition
        for name, obj in update_ownables.items():
            if not isinstance(obj, util.Ownable):
                type_desc = type(name).__qualname__
                raise TypeError(
                    f"'{name}' must have an ownable object like Device, not <{type_desc}>"
                )
            if name not in self._ownables.keys():
                raise TypeError(f"invalid keyword argument '{name}'")

            self._ownables[name] = obj
            if isinstance(obj, core.Device):
                self._devices[name] = obj
        self.__propagate_inst_ownership__()
        self._context = None

    def __propagate_inst_ownership__(self):
        for obj in self._owners.values():
            obj.__owner_init__(self)
            util.Ownable.__init__(obj)

        for obj in self._ownables.values():
            # repeat this for Rack instances that are also Owners,
            # ensuring that obj._owned_name refers to the topmost
            # name
            obj.__owner_init__(self)
            util.Ownable.__init__(obj)

    def __setattr__(self, name, obj):
        # update naming for any util.Ownable instances
        if isinstance(obj, util.Ownable):
            self._ownables[name] = obj
            if getattr(obj, '__objclass__', None) is not type(self):
                obj.__set_name__(type(self), name)
                obj.__owner_init__(self)
                if isinstance(obj, Owner):
                    obj.__propagate_inst_ownership__()

        if isinstance(obj, core.Device):
            self._devices[name] = obj

        if isinstance(obj, Owner):
            self._owners[name] = obj

        super().__setattr__(name, obj)

    def __getattribute__(self, name):
        if name in ('_ownables', '_devices', '_owners'):
            # dicts that need to be a fresh mapping, not the class def
            obj = super().__getattribute__(name)
            if obj is getattr(type(self), name):
                obj = dict(obj)
                setattr(self, name, obj)
            return obj
        elif name == 'open':
            return WrappedOpen(self)
        elif name == 'close':
            return WrappedClose(self)
        else:
            return super().__getattribute__(name)

    def close(self):
        pass

    def open(self):
        pass

    @property
    def __enter__(self):
        context = self._context = package_owned_contexts(self)

        @wraps(type(self).__enter__.fget)
        def __enter__():
            context.__enter__()

            return self

        return __enter__

    @property
    def __exit__(self):
        # set self._context to None before __exit__ so it can tell
        # whether it was invoked through context entry
        context, self._context = self._context, None
        return context.__exit__


def recursive_devices(top: Owner):
    entry_order = list(top._entry_order)
    devices = dict(top._devices)
    top_name_prefix = getattr(top, '__name__', '')
    if len(top_name_prefix) > 0:
        top_name_prefix = top_name_prefix + '.'

    for owner in top._owners.values():
        children, o_entry_order = recursive_devices(owner)
        name_prefix = top_name_prefix + owner.__name__ + '.'

        # this might be faster if the key/value order is transposed in devices?
        for name, child in children.items():
            if child not in devices.values():
                devices[name_prefix + name] = child

        entry_order.extend(o_entry_order)

    return devices, entry_order


def override_empty(a, b, param_name, field):
    """return no more than non-EMPTY value between two Parameter fields, otherwise raises TypeError"""

    nonempty = {a, b} - {EMPTY}

    if len(nonempty) == 2:
        msg = f"conflicting {field} {nonempty} in aggregating argument '{param_name}'"
        raise TypeError(msg)

    elif len(nonempty) == 1:
        ret = tuple(nonempty)[0]

        if field == 'annotation' and not inspect.isclass(ret):
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
    if not hasattr(signature, 'parameters'):
        parameters = signature
    else:
        parameters = signature.parameters

    for name, param in parameters.items():
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            continue
        if name in dest:
            dest[name] = dest[name].replace(
                annotation=override_empty(
                    dest[name].annotation, param.annotation, name, 'annotation'
                ),
                default=override_empty(
                    dest[name].default, param.default, name, 'default'
                ),
            )

        else:
            dest[name] = param.replace(kind=inspect.Parameter.KEYWORD_ONLY)


def attr_chain_to_method(root_obj, chain):
    """follows the chain with nested getattr calls to access the chain object"""
    obj = root_obj

    for name in chain[:-1]:
        obj = getattr(obj, name)

    if hasattr(obj, '_methods'):
        return RackMethod.from_method(obj._methods[chain[-1]])

    attr = getattr(obj, chain[-1])
    if isinstance(attr, RackMethod):
        return RackMethod.from_method(attr)

    else:
        return RackMethod(obj, chain[-1])


def standardize_spec_step(sequence):
    """standardizes the sequence specification dict to  {name: [list of methods]}"""
    if isinstance(sequence, (list, tuple)):
        # specification for a concurrent and/or sequential calls to RackMethod methods
        sequence = list(sequence)

    elif isinstance(sequence, (Sequence, RackMethod)):
        # a RackMethod method that is already packaged for use
        sequence = [sequence]

    elif inspect.ismethod(sequence):
        # it is a class method, just need to wrap it
        sequence = [RackMethod(sequence.__self__, sequence.__name__)]

    elif hasattr(sequence, '__wrapped__'):
        # if it's a wrapper as implemented by functools, try again on the wrapped callable
        return standardize_spec_step(sequence.__wrapped__)

    else:
        typename = type(sequence).__qualname__
        raise TypeError(
            f"object of type '{typename}' is neither a Rack method, Sequence, nor a nested tuple/list"
        )

    return sequence


class Sequence(util.Ownable):
    """An experimental procedure defined with methods in Rack instances. The input is a specification for sequencing these
    steps, including support for threading.

    Sequence are meant to be defined as attributes of Rack subclasses in instances of the Rack subclasses.
    """

    access_spec = None
    cleanup_func = None
    exception_allowlist = NeverRaisedException

    def __init__(self, *specification, shared_names=[], input_table=None):
        self.spec = [standardize_spec_step(spec) for spec in specification]
        self.tags = dict(
            table_path=input_table,
            shared_names=shared_names,
        )

    def return_on_exceptions(self, exception_or_exceptions, cleanup_func=None):
        """Configures calls to the bound Sequence to swallow the specified exceptions raised by
        constitent steps. If an exception is swallowed, subsequent steps
        Sequence are not executed. The dictionary of return values from each Step is returned with
        an additional 'exception' key indicating the type of the exception that occurred.
        """
        self.exception_allowlist = exception_or_exceptions
        self.cleanup_func = cleanup_func

    def __owner_subclass__(self, owner_cls):
        def extend_chain(chain, spec_entry):
            if spec_entry._owner not in chain:
                print(self.spec)
                raise TypeError(
                    f'method "{spec_entry._owner}.{spec_entry.__name__}" in Sequence does not belong to a Rack'
                )
            return chain[spec_entry._owner] + (spec_entry.__name__,)

        if self.access_spec is None:
            # transform the objects in self.spec
            # into attribute names for dynamic access
            # in case of later copying and subclassing
            chain = owner_getattr_chains(owner_cls)

            self.access_spec = [
                [extend_chain(chain, s) for s in spec] for spec in self.spec
            ]

        return self

    def __owner_init__(self, owner):
        """make a sequence bound to the owner"""

        # in case this is added through a
        self.__owner_subclass__(type(owner))

        super().__owner_init__(owner)

        # initialization on the parent class definition
        # waited until after __set_name__, because this depends on __name__ having been set for the tasks task
        spec = [
            [attr_chain_to_method(owner, c) for c in chain]
            for chain in self.access_spec
        ]
        self.last_spec = spec

        # build the callable object with a newly-defined subclass.
        # tricks ipython/jupyter into showing the call signature.
        ns = dict(
            sequence=spec,
            dependencies=self._dependency_map(spec),
            cleanup_func=self.cleanup_func,
            exception_allowlist=self.exception_allowlist,
            tags=self.tags,
            __name__=self.__name__,
            __qualname__=type(owner).__qualname__ + '.' + self.__name__,
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
            self=inspect.Parameter('self', kind=inspect.Parameter.POSITIONAL_ONLY)
        )

        shared_names = self.tags['shared_names']
        name_map = dict(zip(shared_names, shared_names))
        for funcs in spec:
            for func in funcs:
                update_parameter_dict(
                    params, func.extended_signature(name_map=name_map)
                )

        cls.__call__.__signature__ = inspect.Signature(parameters=params.values())

        # the testbed gets this BoundSequence instance in place of self
        obj = object.__new__(cls)
        obj.__init__()
        setattr(owner, self.__name__, obj)

    def _dependency_map(self, spec, owner_deps={}) -> dict:
        """maps the Device dependencies of each RackMethod in spec.

        Returns:
            {Device instance: reference to method that uses Device instance}
        """

        deps = dict(owner_deps)

        for spec in spec:
            for func in spec:
                if not isinstance(func, (RackMethod, BoundSequence)):
                    raise TypeError(
                        f"expected RackMethod instance, but got '{type(func).__qualname__}' instead"
                    )

                # race condition check
                conflicts = set(deps.keys()).intersection(func.dependencies)
                if len(conflicts) > 0:
                    users = {deps[device] for device in conflicts}
                    raise RuntimeError(
                        f'risk of concurrent access to {conflicts} by {users}'
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


@typing.dataclass_transform()
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
            if not name.startswith('_') and callable(obj):
                cls._methods[name] = obj

        # include annotations from parent classes
        cls.__annotations__ = dict(
            getattr(super(), '__annotations__', {}),
            **getattr(cls, '__annotations__', {}),
        )
        cls.__init__.__annotations__ = cls.__annotations__

        # adjust the __init__ signature for introspection/doc

        # Generate a signature for documentation and code autocomplete
        params = [
            inspect.Parameter('self', kind=inspect.Parameter.POSITIONAL_ONLY),
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
                # allow the sentinel EMPTY to instantiate for introspection
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
            kwargs = [f'{k!r}: {v}' for k, v in annotations.items()]
            raise AttributeError(f"missing keyword arguments {', '.join(kwargs)}'")

        # now move forward with applying the devices
        super().__init__(**ownables)

        # wrap self._methods as necessary
        self._methods = {
            k: (obj if isinstance(obj, RackMethod) else RackMethod(self, k))
            for k, obj in self._methods.items()
        }

    def __deepcopy__(self, memo=None):
        """Called when an owning class is subclassed"""
        owners = {name: deepcopy(obj) for name, obj in self._owners.items()}

        # steps = {name: deepcopy(obj) for name, obj in type(self)._methods.items()}
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


Rack.__init_subclass__()


class _use_module_path:
    def __init__(self, path):
        if isinstance(path, str):
            path = [path]

        self.path = path

    def __enter__(self):
        sys.path = list(self.path) + sys.path

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            sys.path = sys.path[len(self.path) :]
        except ValueError:
            pass


def import_as_rack(
    import_string: str,
    *,
    # working_dir: str,
    cls_name: str = None,
    append_path: list = [],
    base_cls: type = Rack,
    replace_attrs: list = ['__doc__', '__module__'],
):
    """Creates a Rack subclass with the specified module's contents. Ownable objects are annotated
    by type, allowing the resulting class to be instantiated.

    Arguments:
        import_string: for the module that contains the Rack to import

        cls_name: the name of the Rack subclass to import from the module (or None to build a
                  new subclass with the module contents)

        base_cls: the base class to use for the new subclass

        append_path: list of paths to append to sys.path before import

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
        name_ok = name in replace_attrs or not name.startswith('_')

        return type_ok and name_ok

    # start_dir = Path('.').absolute()
    # os.chdir(working_dir)
    if append_path:
        with _use_module_path(append_path):
            module = importlib.import_module(import_string)
    else:
        module = importlib.import_module(import_string)

    if cls_name is not None:
        # work with the class specified in the module
        cls = getattr(module, cls_name)

        if issubclass(cls, base_cls):
            # it's already a Rack instance - return it
            return cls
        elif inspect.ismodule(cls):
            module = cls
        else:
            raise TypeError(f'{cls_name} is not a subclass of {base_cls.__qualname__}')

        dunder_updates = dict()
    else:
        cls_name = '__main__'

        dunder_updates = dict(
            __module__=module.__name__,
            __attributes__=dict(
                getattr(base_cls, '__attributes__', {}),
                **getattr(module, '__attributes__', {}),
            ),
        )

    namespace = {
        # take namespace items that are not types or modules
        attr: obj
        for attr, obj in module.__dict__.items()
        if isadaptable(attr, obj)
    }

    # # annotate the rack, which sets up the constructor signature that we use for config
    # namespace["__annotations__"] = {
    #         name: type(obj)
    #         for name, obj in namespace.items()
    #         if isinstance(obj, util.Ownable)
    # }

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

    namespace.update(dunder_updates)

    # subclass into a new Rack
    return type(cls_name, (base_cls,), dict(base_cls.__dict__, **namespace))


def find_owned_rack_by_type(
    parent_rack: Rack, target_type: Rack, include_parent: bool = True
):
    """return a rack instance of `target_type` owned by `parent_rack`. if there is
    not exactly 1 for `target_type`, TypeError is raised.
    """
    # TODO: add this to labbench
    if include_parent and isinstance(parent_rack, target_type):
        target_rack = parent_rack
    else:
        type_matches = {
            name: obj
            for name, obj in parent_rack._ownables.items()
            # need to think about why the inheritance tree is broken here
            if str(type(obj).__mro__) == str(target_type.__mro__)
        }

        if len(type_matches) == 0:
            raise TypeError(f'{parent_rack} contains no racks of type {target_type}')
        elif len(type_matches) > 1:
            raise TypeError(
                f'{parent_rack} contains multiple racks {type_matches.keys()} of type {target_type}'
            )
        else:
            (target_rack,) = type_matches.values()

    return target_rack
