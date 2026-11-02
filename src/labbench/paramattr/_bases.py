"""
Implementation of labbench descriptor objects.

This implementation is deeply intertwined obscure details of the python object
model. Consider starting with a close read of the documentation and exploring
the objects in an interpreter instead of reverse-engineering this code.
"""

from __future__ import annotations

import builtins
from dataclasses import field, Field, MISSING as Undefined
import functools
import inspect
import numbers
from contextlib import contextmanager
from copy import copy
from typing import Any, ClassVar, Sequence, Union
import types

# for common types
from warnings import warn

import typing_extensions as typing

from .. import util

if typing.TYPE_CHECKING:
    import pandas as pd
else:
    pd = util.lazy_import('pandas')

UndefinedType = type(Undefined)


class no_cast_argument:
    """duck-typed stand-in for an argument of arbitrary type"""

    @classmethod
    def __cast_get__(cls, owner, value):
        return value


def get_owner_store(obj: HasParamAttrs) -> HasParamAttrsInstInfo:
    return obj._attr_store


def get_owner_meta(
    obj: HasParamAttrs | type[HasParamAttrs],
) -> HasParamAttrsClsInfo:
    if not issubclass(type(obj), (HasParamAttrsMeta, HasParamAttrs)):
        raise TypeError('wrong metaclass')
    return obj._attr_defs


def get_class_attrs(
    obj: HasParamAttrs | type[HasParamAttrs],
) -> dict[str, ParamAttr[Any]]:
    """returns a mapping of labbench paramattrs defined in `obj`"""
    if obj._attr_defs is None:
        return {}
    else:
        return obj._attr_defs.attrs


def add_docstring_to_help(attr: ParamAttr, func: typing.Callable):
    doc = (func.__doc__ or '').strip().rstrip()
    if len(doc) > 0:
        # take func docstring as default self.help
        new_help = attr.help + '\n\n' + doc
        attr.help = attr.kws['help'] = new_help


def bound_valid_posargs(func: typing.Callable) -> tuple[int, int]:
    """bound on the number of acceptable positional arguments in `func`"""

    if isinstance(func, types.FunctionType):
        hi = func.__code__.co_argcount
        lo = hi - len(func.__defaults__ or tuple())

        return lo, hi
    else:
        raise TypeError(
            'can only guess argument count for types.FunctionType instances'
        )


def name_arguments(func: typing.Callable) -> tuple[str]:
    sig = getattr(func, '__signature__', None)
    if sig is not None:
        return tuple(sig.parameters.keys())
    elif isinstance(func, types.FunctionType):
        return func.__code__.co_varnames[: func.__code__.co_argcount]  # type: ignore
    else:
        func.__signature__ = inspect.signature(func)  # type: ignore
        return tuple(func.__signature__.parameters.keys())  # type: ignore


def default_arguments(func: types.FunctionType | typing.Callable) -> tuple[str, ...]:
    sig = getattr(func, '__signature__', None)
    if sig is not None:
        return tuple([
            p.default for p in sig.parameters.values() if p.default is not p.empty
        ])
    elif isinstance(func, types.FunctionType):
        arg_defaults = tuple(func.__defaults__ or ())
        kw_defaults = tuple((func.__kwdefaults__ or {}).keys() or ())
        return arg_defaults + kw_defaults
    else:
        sig = func.__signature__ = inspect.signature(func)  # type: ignore
        return tuple([
            p.default for p in sig.parameters.values() if p.default is not p.empty
        ])


def build_method_signature[V, **P](
    owner_cls: type[HasParamAttrs],
    method: Method[V],
    kwarg_names: Sequence[str],
    scope='all',
) -> inspect.Signature:
    kwargs_params = []
    defaults = {}
    bcast_kwargs = get_owner_meta(owner_cls).broadcast_kwargs

    for name in kwarg_names:
        try:
            arg_annotation = bcast_kwargs[name]._type
            if bcast_kwargs[name].default not in (None, Undefined):
                defaults[name] = chain_get(bcast_kwargs, method._kwargs, name).default
        except KeyError:
            arg_annotation = Any

        kwargs_params.append(
            inspect.Parameter(
                name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=arg_annotation,
            )
        )

    pos_params = [inspect.Parameter('self', kind=inspect.Parameter.POSITIONAL_ONLY)]

    if scope == 'all':
        pos_params += [
            inspect.Parameter(
                'new_value',
                default=inspect.Parameter.empty,
                kind=inspect.Parameter.POSITIONAL_ONLY,
                annotation=method._type | None,
            )
        ]
        return_annotation = method._type | None
    elif scope == 'getter':
        return_annotation = method._type
    elif scope == 'setter':
        pos_params += [
            inspect.Parameter(
                'new_value',
                kind=inspect.Parameter.POSITIONAL_ONLY,
                annotation=method._type,
            )
        ]
        return_annotation = None
    else:
        raise TypeError('scope argument must be one of (None, "getter", "setter")')

    sig = inspect.Signature(
        pos_params + kwargs_params, return_annotation=return_annotation
    )

    return sig


def chain_get[V](
    d1: dict[Any, V],
    d2: dict[Any, V],
    key: Any,
    default: UndefinedType | V = Undefined,
) -> V:
    """returns d1[key] if it exists, otherwise d2[key], otherwise default if it is not Undefined"""
    if default is Undefined:
        k = d2[key]
        return d1.get(key, k)
    else:
        k = d2.get(key, default)
        return d1.get(key, k)


def missing_kwargs[V, T, **P](
    source: dict[str, MethodKwArg[V, T, P]],
    into: dict[str, MethodKwArg[V, T, P]],
    only: Sequence[str] = [],
) -> dict[str, MethodKwArg[V, T, P]]:
    """return a dictionary of MethodKeywordArguments from self.broadcast_kwargs missing from method"""
    if only is None:
        only = source.keys()
    return {name: source[name] for name in only - into.keys() if name in source}


class KeyAdapterBase:
    """Decorates a :class:`labbench.Device` subclass to configure its
    implementation of the `key` argument passed to :mod:`labbench.paramattr.property` or
    :mod:`labbench.paramattr.method` descriptors.

    This can be use to to automate

    Example:

        Send a message string based on `key` (simplified from :func:`labbench.paramattr.visa_keying`)::

            import labbench as lb
            from labbench import paramattr as attr


            class custom_keying(attr.message_keying):
                def get(self, device: lb.Device, scpi_key: str, trait_name=None):
                    return device.query(key + '?')

                def set(self, device: lb.Device, scpi_key: str, value, trait_name=None):
                    return device.write(f'{scpi_key} {value}')


            @custom_keying
            class CustomDevice(lb.VISADevice):
                pass

    """

    # @typing.overload
    # def __new__(cls, /, decorated_cls: type[T], **kws) -> type[T]:
    #     ...

    # @typing.overload
    # def __new__(cls, /, decorated_cls: type(None), **kws) -> KeyAdapterBase:
    #     ...

    # def __new__(cls, /, decorated_cls: type[T] = None, **kws):
    #     """set up use as a class decorator"""

    #     obj = super().__new__(cls)

    #     if decorated_cls is not None:
    #         # instantiated as a decorator without arguments - do the decoration
    #         if not issubclass(decorated_cls, HasParamAttrs):
    #             raise TypeError(
    #                 f"{cls.__qualname__} must decorate a HasParamAttrs or Device class"
    #             )
    #         obj.__init__()
    #         return obj(decorated_cls)
    #     else:
    #         # instantiated with arguments - decoration happens later
    #         obj.__init__(**kws)
    #         return obj

    def __init__(self):
        pass

    def __call__[T: type[HasParamAttrs]](self, owner_cls: T) -> T:
        # TODO: is this really necessary?
        get_owner_meta(owner_cls).key_adapter = self.copy()
        return owner_cls

    def copy(self, update_key_arguments={}):
        obj = copy(self)
        return obj

    def get[V](
        self,
        owner: HasParamAttrs,
        key: str,
        attr: ParamAttr[V] | None = None,
        kwargs: dict[str, Any] = {},
    ) -> V:
        """this must be implemented by a subclass to support of `labbench.parameter.method`
        `labbench.parameter.property` attributes that are implemented through the `key` keyword.
        """
        raise NotImplementedError(
            f'key adapter does not implement "get" {type(self)!r}'
        )

    def set[V](
        self,
        owner: HasParamAttrs,
        key: str,
        value: V,
        attr: ParamAttr[V] | None = None,
        kwargs: dict[str, Any] = {},
    ):
        """this must be implemented by a subclass to support of `labbench.parameter.method`
        `labbench.parameter.property` attributes that are implemented through the `key` keyword.
        """
        raise NotImplementedError(
            f'key adapter does not implement "set" {type(self)!r}'
        )

    def get_kwarg_names(self, key: Any) -> list[str]:
        """returns a list of arguments for the parameter attribute key.

        This must be implemented in order to define `labbench.paramattr.method` attributes
        using the `key` keyword.
        """
        raise NotImplementedError(
            'key adapter needs "get_key_arguments" to implement methods by "key" keyword'
        )

    def method_signature[V, **P](
        self,
        owner_cls: type[HasParamAttrs],
        method: Method[V],
        scope='all',
    ) -> inspect.Signature:

        return build_method_signature(
            owner_cls, method, kwarg_names=self.get_kwarg_names(method.key), scope=scope
        )

    def fill_kwargs[V, **P](
        self,
        method: Method[V],
        owner_cls: type[HasParamAttrs],
    ) -> dict[str, MethodKwArg[V, Any, P]]:
        """return a dictionary of MethodKeywordArguments from broadcast_kwargs missing from method"""

        ret = missing_kwargs(
            source=get_owner_meta(owner_cls).broadcast_kwargs,
            into=method._kwargs,
            only=self.get_kwarg_names(method.key),
        )

        return ret

    def getter_factory[V, **P](
        self,
        owner_cls: type[HasParamAttrs],
        method: Method[V],
    ) -> _Getter[V, Any]:
        """return a getter function implemented with method.key"""

        def func(owner: HasParamAttrs, /, **kwargs) -> V:
            key = typing.cast(str, method.key)
            return self.get(owner, key, method, kwargs)

        func.__signature__ = self.method_signature(owner_cls, method, scope='getter')  # type: ignore
        func.__name__ = method.name + '_getter'  # type: ignore
        func.__module__ = f'{owner_cls.__module__}'
        func.__qualname__ = f'{owner_cls.__qualname__}.{method.name}'

        return func

    def setter_factory[V, **P](
        self,
        owner_cls: type[HasParamAttrs],
        method: Method[V],
    ) -> _Setter[V, Any]:
        """return a getter function implemented with method.key"""

        def func(owner: HasParamAttrs, new_value: V, /, **kwargs):
            key = typing.cast(str, method.key)
            self.set(owner, key, new_value, method, kwargs)

        signature = self.method_signature(owner_cls, method, scope='setter')
        func.__signature__ = signature  # type: ignore
        func.__name__ = method.name + '_setter'  # type: ignore
        func.__module__ = f'{owner_cls.__module__}'
        func.__qualname__ = f'{owner_cls.__qualname__}.{method.name}'

        return func


class HasParamAttrsClsInfo:
    attrs: dict[str, ParamAttr]
    key_adapter: KeyAdapterBase
    broadcast_kwargs: dict[str, MethodKwArg]

    # unbound methods
    methods: dict[str, typing.Callable]

    __slots__ = ['attrs', 'key_adapter', 'broadcast_kwargs', 'methods']

    def __init__(
        self,
        key_adapter: KeyAdapterBase,
        broadcast_kwargs: dict[str, MethodKwArg] = {},
        attrs: dict[str, ParamAttr] = {},
    ):
        self.attrs = attrs
        self.key_adapter = key_adapter
        self.broadcast_kwargs = broadcast_kwargs

    def value_names(self) -> list[str]:
        return [k for k, v in self.attrs.items() if isinstance(v, Value)]

    def method_names(self) -> list[str]:
        return [k for k, v in self.attrs.items() if isinstance(v, Method)]

    def property_names(self) -> list[str]:
        return [k for k, v in self.attrs.items() if isinstance(v, Property)]

    @classmethod
    def copy_from(cls, owner_cls: type[HasParamAttrs]) -> typing.Self:
        obj = cls(
            attrs={},
            key_adapter=get_owner_meta(owner_cls).key_adapter,
            broadcast_kwargs=dict(get_owner_meta(owner_cls).broadcast_kwargs),
        )
        obj.attrs = {k: v.copy() for k, v in get_owner_meta(owner_cls).attrs.items()}
        return obj


@functools.cache
def get_cls_annotations(cls: type):
    anns = {}
    g = globals()

    for kls in cls.__mro__[::-1]:
        parent_annots = typing.get_annotations(kls, globals=g, eval_str=True)
        anns |= {
            k: v
            for k, v in parent_annots.items()
            if getattr(v, '__origin__', None) is not typing.ClassVar
        }
    return dict(anns)


class HasParamAttrsMeta(type):
    @classmethod
    def __prepare__(mcls, names, bases, **kws):
        """Prepare fresh cls._attr_defs.attrs mappings to allow copy-on-write of ParamAttr
        definitions in subclasses.
        """
        ns = dict()

        if len(bases) >= 1:
            cls_info = None
            attrs = {}

            # multiple inheritance: pull in other paramattr definitions
            for base in bases[::-1]:
                if issubclass(base, HasParamAttrs):
                    cls_info = HasParamAttrsClsInfo.copy_from(base)
                    attrs.update(cls_info.attrs)

            if cls_info is not None:
                cls_info.attrs = attrs
            ns['_attr_defs'] = cls_info
            # ns.update(attrs, _attr_defs=cls_info)
            return ns
        else:
            ns['_attr_defs'] = HasParamAttrsClsInfo(key_adapter=KeyAdapterBase())

        return ns


@typing.dataclass_transform(
    eq_default=False, kw_only_default=True, field_specifiers=(field,)
)
class ParamAttrMeta(type):
    pass


class ParamAttr[V](metaclass=ParamAttrMeta):
    """base class for helper descriptors in :class:`labbench.Device`. These
    are multi-tools for type checking, casting, decorators, API wrapping, and callbacks.

    The basic types of `ParamAttr` descriptors implemented in :mod:`labbench` are

    * :mod:`Value <labbench.paramattr.value>`, a simple variable stored in the Device object

    * :mod:`Property <labbench.paramattr.property>`, a parameter of an underlying API (often `Device.backend`) implemented in the style of a :func:`property`

    * :mod:`Method <labbench.paramattr.method>`, a parameter of an underlying API (often `Device.backend`) implemented as a method that can support additional keyword arguments

    Each of these are modules that contain more specialized descriptors targeted toward various python types.
    Method definitions also use :mod:`KeywordArgument <labbench.paramattr.kwarg>`, which are not used as descriptors.

    Arguments:
        key: specify automatic implementation with the Device (backend-specific)
        help: the ParamAttr docstring
        label: a label for the quantity, such as units
        sets: True if the attribute supports writes
        gets: True if the attribute supports reads
        cache: if True, interact with the device only once, then return copies (state attribute only)
        only: an allow-list of values; if set, others values raise ValueError
        allow_none: permit None values in addition to the specified type
        log: whether to emit logging/UI notifications when the value changes
        inherit: if True, use the definition in a parent class as defaults
    """

    # __objclass__: type

    # the python type representation defined by ParamAttr subclasses
    _type: type = object

    # description of the general behavior of this subclass
    ROLE = 'base class'

    # keyword argument types and default values
    help: str = ''
    label: str = ''
    sets: bool = True
    gets: bool = True
    cache: bool = False
    only: Sequence[V] = tuple()
    allow_none: bool = False
    log: bool = True
    inherit: bool = False
    name: str | None = field(default=None, init=False, repr=False)

    _keywords = {}
    _defaults = {}
    _positional = []

    def __init__(self, *args, **kws):
        # apply the dataclass entries
        for arg, name in zip(args, self._positional):
            kws[name] = arg
        self.kws = kws

        public_names = {name for name in kws.keys() if not name.startswith('_')}
        defaults = set(self._defaults.keys())

        field_names = set(self._defaults.keys()) | set(self._positional) - set(
            self._skip_init
        )
        private_names = defaults - public_names
        unexpected = (public_names - field_names) | (  # "public" annotated names
            private_names - defaults
        )  # secret "private" arguments starting with _

        if len(unexpected) > 0:
            unexpected = ', '.join(unexpected)
            raise TypeError(f'invalid keyword argument(s): {unexpected}')

        required = field_names - defaults
        missing_required = required - public_names
        if len(missing_required) > 0:
            missing_required = ', '.join(missing_required)
            raise TypeError(f'missing required keyword argument(s): {missing_required}')

        # set value attributes
        for k, v in dict(self._defaults, **kws).items():
            setattr(self, k, v)

    def copy(
        self, new_type: type[typing.Self] | None = None, default=Undefined, **update_kws
    ) -> typing.Self:
        if new_type is None:
            new_type = type(self)
        if default is not Undefined:
            update_kws['default'] = default
        kws = dict(self.kws, inherit=False)
        kws.update(update_kws)
        obj = new_type(**kws)
        return obj

    @classmethod
    def __init_subclass__(cls, type: builtins.type | UndefinedType = Undefined):
        """python triggers this call immediately after a ParamAttr subclass
            is defined, allowing us to automatically customize its implementation.

        Arguments:
            type: the python type of the parameter
        """
        if type is not Undefined:
            cls._type = type

        # cache annotated fields in the class for faster lookup later
        cls.__annotations__ = get_cls_annotations(cls)
        cls._defaults = {}
        cls._positional = []
        cls._skip_init = []

        for k in cls.__annotations__.keys():
            if not hasattr(cls, k):
                continue
            obj = getattr(cls, k)
            if isinstance(obj, Field):
                if not obj.init:
                    cls._skip_init.append(k)
                elif not obj.kw_only:
                    cls._positional.append(k)
                cls._defaults[k] = obj.default
            else:
                cls._defaults[k] = getattr(cls, k)

        # Help to reduce memory use by __slots__ definition (instead of __dict__)
        cls.__slots__ = [n for n in dir(cls) if not callable(getattr(cls, n))] + [
            'ROLE',
            'name',
            '_defaults',
            '_keywords',
            '_positional',
            '_skip_init',
            '__annotations__',
        ]

    # Descriptor methods (called automatically by the owning class or instance)
    @util.hide_in_traceback
    def __set_name__(self, owner_cls: type, name: str):
        """Called on owner class instantiation (python object protocol)"""

        if getattr(self, 'name', None) not in (name, None):
            # extra calls here result when .setter() and .getter()
            # decorators are applied in Method or Property
            return

        if not issubclass(owner_cls, HasParamAttrs):
            # other owning objects may unintentionally become owners; this causes problems
            # if they do not implement the HasParamAttrs object protocol
            return

        class_attrs: dict[str, Any] = get_class_attrs(owner_cls)
        if self.inherit:
            if name not in class_attrs:
                owner_name = owner_cls.__qualname__
                raise TypeError(
                    f'cannot inherit defaults for {owner_name}.{name} '
                    f'because {name} is not defined in any {owner_name} parent'
                )

            # if the parent class defines this paramattr, and it
            # has the same type, inherit its definition to set our
            # own defaults
            parent_attr = class_attrs[name]
            if type(parent_attr) is not type(self):
                owner_name = owner_cls.__qualname__
                type_name = type(parent_attr).__qualname__
                raise TypeError(
                    f'cannot inherit defaults for {owner_name}.{name} '
                    f'because it was defined with a different type {type_name}'
                )

            if parent_attr is not self:
                self = parent_attr.copy(**self.kws)
                setattr(owner_cls, name, self)

        # inspect module expects this name - don't play with it
        self.__objclass__ = owner_cls

        # Take the given name
        self.name = name

        class_attrs[name] = self

    def __init_owner_subclass__(self, owner_cls: type[HasParamAttrs]):
        """The owner calls this in each of its ParamAttr attributes at the end of defining the subclass
        (near the end of __init_subclass__). Now it is time to ensure properties are compatible with the
        owner class. This is here --- not in __set_name__ --- because python
        obfuscates exceptions raised in __set_name__.

        This is also where we finalize selecting decorator behavior; is it a property or a method?
        """

    def __init_owner_instance__(self, owner: HasParamAttrs):
        pass

    @util.hide_in_traceback
    def _prepare_set_value(
        self, owner: HasParamAttrs, value, kwargs: dict[str, Any] = {}
    ):
        # First, validate the pythonic types
        if not self.sets:
            raise AttributeError(f'{self.__str__()} cannot be set')
        if value is not None:
            # cast to self._type and validate
            value = self.to_pythonic(value)
            value = self.validate(value, owner)

            if len(self.only) > 0 and not self.contains(self.only, value):
                raise ValueError(
                    f"value '{value}' is not among the allowed values {self.only!r}"
                )
        elif self.allow_none:
            value = None
        else:
            raise ValueError(f"None value not allowed for parameter '{self!r}'")

        try:
            value = self.from_pythonic(value)
        except BaseException as e:
            name = type(owner).__qualname__ + '.' + str(self.name)
            e.args = (e.args[0] + f" in attempt to set '{name}'",) + e.args[1:]
            raise e

        return value

    def get_from_owner(self, owner: HasParamAttrs, kwargs: dict[str, Any] = {}):
        raise NotImplementedError

    def set_in_owner(self, owner: HasParamAttrs, value, kwargs: dict[str, Any] = {}):
        raise NotImplementedError

    @util.hide_in_traceback
    def _finalize_get_value(self, owner, value, strict=False):
        """Examine value and either return a valid pythonic value or raise an exception if it cannot be cast.

        Arguments:
            owner: the class instance that owns the attribute
            value: the value we need to validate and notify
        :return:
        """
        if self.allow_none and value is None:
            # skip validation if None and None values are allowed
            return None

        try:
            value = self.to_pythonic(value)
            self.validate(value, owner)
        except BaseException as e:
            if hasattr(e, 'add_note'):
                # python >= 3.10
                e.add_note(f"while attempting to get attribute '{self}' in {owner}")
            raise

        return value

    @util.hide_in_traceback
    def to_pythonic(self, value):
        """Convert a value from an unknown type to self._type."""
        if self._type is object:
            raise value
        elif not callable(self._type):
            raise TypeError(f'need to implement to_pythonic for type {self._type}')

        try:
            return self._type(value)
        except TypeError as ex:
            ex.add_note(f'instantiating attribute {self!r}')
            raise ex

    @util.hide_in_traceback
    def from_pythonic(self, value):
        """convert from a python type representation to the format needed to communicate with the device"""
        return value

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        """This is the default validator, which requires that attribute value have the same type as self._type.
        A ValueError is raised for other types.

        Arguments:
            value: value to check
        Returns:
            a valid value
        """
        if not isinstance(value, self._type):
            typename = self._type.__qualname__
            valuetypename = type(value).__qualname__
            raise ValueError(
                f"{self!r} type must be '{typename}', not '{valuetypename}'"
            )
        return value

    def contains(self, iterable, value):
        return value in iterable

    # introspection
    def doc(self, as_argument=False):
        doc_param_funcs = util.find_methods_in_mro(type(self), 'doc_params', ParamAttr)[
            ::-1
        ]
        doc_kws = {
            'as_argument': as_argument,
            'skip': ['help', 'default', 'label', 'cache', 'allow_none'],
        }
        doc_params = [f(self, **doc_kws) for f in doc_param_funcs]
        doc_params = [s for s in doc_params if s]

        doc = f'{self.help}'
        if self.label:
            doc += f' ({self.label})'

        # params = self.doc_params(skip=["help", "default", "label"])
        if as_argument:
            # document for Device.__init__
            param_str = ', '.join(doc_params)
            if len(param_str) > 0:
                doc += f' ({param_str})'

        else:
            # document as an attribute
            if len(doc_params) > 0:
                doc += '\n\n' + '\n'.join(doc_params)
        return doc

    def doc_params(
        self, skip: list[str] = ['help', 'label'], as_argument: bool = False
    ) -> str:
        pairs = []

        if as_argument:
            # simple comma-separated list for Device.__init__
            type_hints = get_cls_annotations(type(self))
            for name in type_hints.keys():
                default = getattr(type(self), name)
                v = getattr(self, name)

                # skip uninformative debug info
                if name.startswith('_') or name in skip:
                    continue

                # only show non-defaults
                v = getattr(self, name)
                if v is Undefined:
                    continue
                elif name not in self._positional and v == default:
                    continue

                pairs.append(f'{name}={v!r}')

            return ', '.join(pairs)

        else:
            # for text docs: allow subclasses to document their own params
            docs = []
            access_limits = []
            if not self.sets:
                access_limits.append('set')
            if not self.gets:
                access_limits.append('get')
            if access_limits:
                docs.append(
                    f'* Cannot be {" or ".join(access_limits)} after device creation'
                )
            if self.only:
                only = set(list(self.only) + ([None] if self.allow_none else []))
                docs.append(f'\n\n* Allowed values are {only!r}')

            if self.cache:
                docs.append('* Logging event stored in metadata log after first access')
            else:
                docs.append(
                    '* Logging events are triggered on each access, and are stored as a key or column'
                )

            return '\n'.join(docs)

    def __repr__(
        self,
        skip_params=['help', 'label'],
        owner: None | HasParamAttrs = None,
        with_declaration: bool = True,
    ):
        param_doc = self.doc_params(skip=skip_params, as_argument=True)
        declaration = f'{type(self).__module__}.{type(self).__qualname__}({param_doc})'

        if owner is None and not with_declaration:
            raise TypeError(
                'must specify at least one of `declaration` and `owner_inst`'
            )

        elif owner is None:
            if self.name is None:
                return f'<{declaration}>'
            else:
                return f'<{declaration} as {self.name}>'

        if get_class_attrs(owner).get(self.name or '', None) is None:
            raise AttributeError(f'{self} is not owned by {owner}')
        if with_declaration:
            return f'<{declaration} as {self._owned_name(owner)}>'
        else:
            return self._owned_name(owner)

    __str__ = __repr__

    def _owned_name(self, owner):
        if owner._owned_name is None:
            return type(owner).__qualname__ + '.' + self.name
        else:
            return owner._owned_name + '.' + self.name

    def update(self, obj=None, /, **attrs):
        """returns `self` or (if `obj` is None) or `other`, after updating its keyword
        parameters with `attrs`
        """
        if obj is None:
            obj = self
        # invalid_params = set(attrs).difference(obj.__dict__)
        # if len(invalid_params) > 0:
        #     raise AttributeError(
        #         f"{obj} does not have the parameter(s) {invalid_params}"
        #     )

        # validate by trying to make a copy
        obj.copy(**attrs)

        # apply
        obj.__dict__.update(attrs)  # pyright: ignore
        return obj


class Value[V](ParamAttr[V]):
    """represent a single parameter attribute in instances of the owning class.

    Compared to simple assignment of parameters, this implements type validation,
    simple access control, and enables tracking/recording by UIs or automatic data loggers.

    Arguments:
        default: the initial value when the owning class is instantiated
        key: specify automatic implementation with the Device (backend-specific)
        help: the ParamAttr docstring
        label: a label for the quantity, such as units
        sets: True if the attribute supports writes
        gets: True if the attribute supports reads
        cache: if True, interact with the device only once, then return copies (state attribute only)
        only: value allowlist; others raise ValueError
        allow_none: permit None values in addition to the specified type
        log: whether to emit logging/UI notifications when the value changes
        inherit: if True, use the definition in a parent class as defaults
        kw_only: whether to force keyword-only when annotated as a constructor argument in the owner
    """

    default: V = field(kw_only=False)
    key: str | None = None
    allow_none: bool | None = None
    kw_only: bool = True
    init: bool = True

    ROLE = 'value'

    def __init__(self, *args, **kws):
        super().__init__(*args, **kws)

        if self.inherit and not (len(args) > 0 or 'default' in kws):
            raise TypeError(
                'to avoid type hint inconsistencies, default must '
                'be specified for values with inherit=True'
            )

        if self.allow_none is None:
            if self.default is None:
                self.allow_none = True  # pyright: ignore
            else:
                self.allow_none = False  # pyright: ignore
        elif self.default is None and not self.allow_none:
            raise TypeError('cannot set default=None with allow_none=True')

    @typing.overload
    def __get__(self, owner: None, owner_cls: Any) -> Value[V]: ...

    @typing.overload
    def __get__(self, owner: HasParamAttrs, owner_cls: Any) -> V: ...

    @util.hide_in_traceback
    def __get__(
        self,
        owner: HasParamAttrs | None,
        owner_cls: type[HasParamAttrs],
    ) -> Any:
        """Called by the class instance that owns this attribute to
        retreive its value. This, in turn, decides whether to call a wrapped
        decorator function or the owner's property adapter method to retrieve
        the result.

        Returns:
            retreived value
        """

        # only continue to get the value if the __get__ was called for an owning
        # instance, and owning class is a match for what we were told in __set_name__.
        # otherwise, someone else is trying to access `self` and we
        # shouldn't get in their way.
        if owner is None:  # or not isinstance(owner, HasParamAttrs):
            # escape an infinite recursion loop before accessing any class members
            return self

        cls_getter = owner_cls.__dict__.get(self.name, None)  # type: ignore
        objclass_getter = self.__objclass__.__dict__.get(self.name)  # type: ignore
        if cls_getter is not objclass_getter:
            return self
        else:
            return self.get_from_owner(owner)

    @util.hide_in_traceback
    def __set__(self, owner: HasParamAttrs, value: V):
        if isinstance(owner, HasParamAttrs):
            return self.set_in_owner(owner, value)
        else:
            return self

    def get_from_owner(self, owner: HasParamAttrs, kwargs: dict[str, Any] = {}) -> V:
        if not self.gets:
            # stop now if this is not a gets ParamAttr
            raise AttributeError(f'{self.__repr__(owner=owner)} does not support gets')

        value = owner._attr_store.cache.setdefault(self.name, self.default)
        if self.name not in owner._attr_store.cache:
            owner.__notify__(self.name, value, 'get', cache=self.cache)

        return value

    @util.hide_in_traceback
    def set_in_owner(self, owner: HasParamAttrs, value: V, kwargs: dict[str, Any] = {}):
        value = self._prepare_set_value(owner, value, kwargs)
        owner._attr_store.cache[self.name] = value
        owner.__notify__(self.name, value, 'set', cache=self.cache)

    def __init_owner_instance__(self, owner: HasParamAttrs):
        super().__init_owner_instance__(owner)

        if self.default is not Undefined:
            self.sets, sets = True, self.sets
            self.set_in_owner(owner, self.default)
            self.sets = sets


class MethodKwArg[V, T, **P](ParamAttr[V]):
    name: str = field(kw_only=False)
    default: V | None | UndefinedType = Undefined

    ROLE = 'keyword argument'

    # decorated keyword arguments not yet adopted by a Method
    _decorated: typing.ClassVar[dict[typing.Callable, dict[str, 'MethodKwArg']]] = {}

    def __init_owner_subclass__(self, owner_cls: type[HasParamAttrs]):
        raise AttributeError(
            'labbench.paramattr.kwarg instances should not be used as class attributes'
        )

    def __set_name__(self, owner_cls, name):
        super().__set_name__(owner_cls, self.name)

    def _owned_name(self, owner):
        return self.__repr__()

    @typing.overload
    def __call__(self, decorated: _Getter[T, P]) -> _Getter[T, P]: ...

    @typing.overload
    def __call__(self, decorated: _Setter[T, P]) -> _Setter[T, P]: ...

    @typing.overload
    def __call__(self, decorated: THasParamAttrs) -> THasParamAttrs: ...

    def __call__(
        self,
        decorated: _Getter[T, P] | _Setter[T, P] | THasParamAttrs,
    ) -> _Getter[T, P] | _Setter[T, P] | THasParamAttrs:
        """decorate a method to apply type conversion and validation checks to one of its keyword arguments.

        These are applied to the keyword argument matching `self.name` immediately before each call to
        `invalidated_method`.
        """

        if self.default is not Undefined:
            raise TypeError(
                'the default argument is not supported when decorating a method'
            )

        if isinstance(decorated, (HasParamAttrs, type(HasParamAttrs))):
            get_owner_meta(decorated).broadcast_kwargs[self.name] = self  # ty: ignore
            decorated.__init_subclass__()
        elif isinstance(decorated, Method):
            raise TypeError('decorate keyword arguments after methods')
        elif callable(decorated):
            self._decorated.setdefault(decorated, {}).setdefault(self.name, self)
        elif isinstance(decorated, (Value, Property)):
            raise TypeError(
                '{to_decorate.ROLE} paramattrs do not accept keyword arguments'
            )

        return decorated


class OwnerAccessAttr[V](ParamAttr[V]):
    """base class for property and method paramattrs, which implement wrappers into their owners
    as specified by their key arguments and/or decorators"""

    key: str | None = field(default=None, kw_only=False)
    _setter = None
    _getter = None

    def __init_owner_subclass__(self, owner_cls: type[HasParamAttrs]):
        """The owner calls this in each of its ParamAttr attributes at the end of defining the subclass
        (near the end of __init_subclass__). Now it is time to ensure properties are compatible with the
        owner class. This is here --- not in __set_name__ --- because python
        obfuscates exceptions raised in __set_name__.

        This is also where we finalize selecting decorator behavior; is it a property or a method?
        """
        # delete any leftovers from .setter() and .getter(), such as '_'
        for func in self._setter, self._getter:
            func_name = getattr(func, '__name__', self.name)
            assert func_name is not None
            if func_name != self.name and getattr(owner_cls, func_name, None) is self:
                delattr(owner_cls, func_name)

        missing_set = self.key is None and not self._setter
        if 'sets' in self.kws:
            # for an explicit sets=True, ensure it's implemented
            if self.sets and missing_set:
                raise TypeError(
                    f'decorate @{self}.setter or define with a key to implement sets=True'
                )
        elif missing_set:
            # otherwise if a set implementation is missing, set sets=False
            self.sets = False

        missing_get = self.key is None and not self._getter
        if 'gets' in self.kws:
            # for an explicit gets=True, ensure it's implemented
            if self.gets and missing_get:
                raise TypeError(
                    f'decorate @{self}.getter or define with a key to implement gets=True'
                )
        elif missing_get:
            # otherwise if a get implementation is missing, set gets=False
            self.gets = False

    @util.hide_in_traceback
    def get_from_owner(self, owner: HasParamAttrs, kwargs: dict[str, Any] = {}):
        if not self.gets:
            # stop now if this is not a gets ParamAttr
            raise AttributeError(
                f'{self.__repr__(owner=owner)} does not support get operations'
            )

        if self.cache and self.name in owner._attr_store.cache:
            # return the cached value if applicable
            return owner._attr_store.cache[self.name]

        elif self._getter is not None:
            # get value with the decorator implementation, if available
            self._getter
            value = self._getter(owner, **kwargs)  # pyright: ignore

        else:
            # otherwise, use the key owner's key adapter, if available

            if isinstance(self.key, str):
                value = get_owner_meta(owner).key_adapter.get(
                    owner, self.key, self, kwargs
                )
            else:
                raise TypeError('self.key is invalid type')

        value = self._finalize_get_value(owner, value, strict=False)
        owner.__notify__(self.name, value, 'get', cache=self.cache, kwargs=kwargs)
        return value

    @util.hide_in_traceback
    def set_in_owner(
        self, owner: HasParamAttrs, value, kwargs: dict[str, Any] = {}
    ) -> None:
        value = self._prepare_set_value(owner, value, kwargs)

        # The remaining roles act as function calls that are implemented through self.key
        # or by decorating a function.
        if self._setter is not None:
            # a decorated setter function, if used as a decorator
            self._setter(owner, value, **kwargs)  # pyright: ignore

        elif self.key is not None:
            # send to the key adapter
            get_owner_meta(owner).key_adapter.set(owner, self.key, value, self, kwargs)

        else:
            assert self.name is not None
            objname = str(type(owner).__qualname__) + '.' + (self.name)
            raise AttributeError(
                f'cannot set {objname}: no @{self.__repr__(owner=owner)}.'
                f'setter and no key argument'
            )

        owner.__notify__(self.name, value, 'set', cache=self.cache, kwargs=kwargs)

    @util.hide_in_traceback
    def getter(self, func):
        """decorate a getter method to implement behavior in the owner"""

        # validate signature
        arg_lo, arg_hi = bound_valid_posargs(func)
        if arg_hi < 1 or arg_lo > 1:
            raise TypeError(
                'decorated getter method must accept one positional argument: self'
            )

        # validate access constraints
        if not self.gets:
            raise TypeError('tried to implement a getter, but gets=False')

        self._getter = func
        self.kws['_getter'] = func
        add_docstring_to_help(self, func)

        if self.name is None and hasattr(func, '__name__'):
            self.name = func.__name__

        return self

    @util.hide_in_traceback
    def setter(self, func):
        """decorate a setter method to implement behavior in the owner"""

        # validate signature
        arg_lo, arg_hi = bound_valid_posargs(func)
        if arg_hi < 2 or arg_lo > 2:
            # allow more to support methods that may have additional keyword arguments
            raise TypeError(
                'decorated setter method must accept two positional arguments: (self, new_value)'
            )

        # validate access constraints
        if not self.sets:
            raise TypeError('tried to implement a setter, but sets=False')

        self._setter = func
        self.kws['_setter'] = func  # for proper copying
        add_docstring_to_help(self, func)

        if self.name is None and hasattr(func, '__name__'):
            self.name = func.__name__

        return self

    __call__ = getter


class _Getter[T, **P](typing.Protocol):
    """call signature protocol for *decorated* methods of Method descriptors"""

    __name__: typing.ClassVar[str]

    def __call__(
        _,
        self: Any,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T: ...


class _Setter[T, **P](typing.Protocol):
    """call signature protocol for *decorated* methods of Method descriptors"""

    __name__: typing.ClassVar[str]

    def __call__(
        _,
        self: Any,
        /,
        new_value: T,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None: ...


class _MethodDescriptor[V, **P]:
    __slots__ = ('method', 'owner', '__signature__')

    def __init__(self, method: Method[V], owner: HasParamAttrs, /):
        self.method = method
        self.owner = owner
        self.__signature__ = build_method_signature(
            type(owner), method, method.get_kwarg_names()
        )

    @typing.overload
    def __call__(self, new_value: V, *args: P.args, **kwargs: P.kwargs) -> None: ...

    @typing.overload
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> V: ...

    @util.hide_in_traceback
    def __call__(
        self,
        new_value: V | None | UndefinedType = Undefined,
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> V | None | UndefinedType:
        for name in self.method._kwargs.keys() & kwargs.keys():
            # apply keyword argument validation to incoming keyword arguments
            kwargs[name] = self.method._kwargs[name]._finalize_get_value(
                self.owner, kwargs[name]
            )

        if new_value is not Undefined:
            self.method.set_in_owner(self.owner, new_value, kwargs)
            if self.method.get_on_set:
                value = self.method.get_from_owner(self.owner, kwargs)
            else:
                value = None
        else:
            value = self.method.get_from_owner(self.owner, kwargs)

        return value


class _GetterMethod[V, **P](typing.Protocol):
    # call signature for type hinting decorated Method descriptors

    def __call__(self: Any, *args: P.args, **kwargs: P.kwargs) -> V: ...

    def setter(self, func: _Setter[V, P]) -> _GetterSetterMethod[V, P]: ...

    def getter(self, func: _Getter[V, P]) -> _GetterMethod[V, P]: ...


class _SetterMethod[V, **P](typing.Protocol):
    # call signature for type hinting decorated Method descriptors

    def __call__(self, new_value: V, *args: P.args, **kwargs: P.kwargs) -> None: ...

    def setter(self, func: _Setter[V, P]) -> _SetterMethod[V, P]: ...

    def getter(self, func: _Getter[V, P]) -> _GetterSetterMethod[V, P]: ...


class _GetterSetterMethod[V, **P](typing.Protocol):
    # call signature for type hinting decorated Method descriptors

    @typing.overload
    def __call__(self, new_value: V, *args: P.args, **kwargs: P.kwargs) -> None: ...

    @typing.overload
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> V: ...

    def setter(self, func: _Setter[V, P]) -> _GetterSetterMethod[V, P]: ...

    def getter(self, func: _Getter[V, P]) -> _GetterSetterMethod[V, P]: ...


class Method[V](OwnerAccessAttr[V]):
    # this structure seems to trick some type checkers into honoring the @overloads in
    # _MethodMeta
    key: str | None = field(default=None, kw_only=False)
    """when set, this defines the method implementation based on a key adapter in the owner"""

    get_on_set: bool = False

    """if True, a property get follows immediately to log the "accepted" property value"""
    ROLE = 'method'

    _kwargs: dict[str, MethodKwArg] = {}

    def __init_owner_instance__(self, owner: HasParamAttrs):
        """bind a callable method in the owner"""

        super().__init_owner_instance__(owner)
        assert self.name is not None
        owner._attr_store.methods[self.name] = _MethodDescriptor(self, owner)

    def __set__(self, owner, value):
        # more informative exception in case of use as a property descriptor
        call_name = self.__repr__(owner=owner, with_declaration=False)
        raise AttributeError(
            f'set {self.name} with the function call {call_name}(new_value, ...), by assignment'
        )

    # if typing.TYPE_CHECKING:
    #     # call signatures hints for IDEs

    #     def __new__(cls, *args, **kwargs) -> Method[V, _InstanceMethod[V,Any]]: ...

    @typing.overload
    def __get__(
        self, owner: HasParamAttrs, owner_cls: type[HasParamAttrs] | None
    ) -> _MethodDescriptor[V, Any]: ...

    @typing.overload
    def __get__(
        self, owner: None, owner_cls: type[HasParamAttrs] | None
    ) -> typing.Self: ...

    def __get__(
        self, owner: HasParamAttrs | None, owner_cls: type[HasParamAttrs] | None = None
    ) -> _MethodDescriptor[V, Any] | typing.Self:
        if owner is None:
            # __init_owner_instance__ has not yet been called
            return self
        else:
            # __init_owner_instance__ has already been called
            assert self.name is not None
            return owner._attr_store.methods[self.name]

    def __init_owner_subclass__(self, owner_cls: type[HasParamAttrs]):
        super().__init_owner_subclass__(owner_cls)
        key_adapter = get_key_adapter(owner_cls)

        if self.key is None:
            # fill in missing kwargs with any broadcast kwargs
            new_kwargs = missing_kwargs(
                into=self._kwargs,
                source=get_owner_meta(owner_cls).broadcast_kwargs,
                only=self.get_kwarg_names(),
            )
            self._kwargs.update(new_kwargs)

        else:
            # fill in undefined getter/setter with the key adapter
            self._kwargs.update(key_adapter.fill_kwargs(self, owner_cls))

            if self.gets and self._getter is None:
                self.getter(key_adapter.getter_factory(owner_cls, self))
            if self.sets and self._setter is None:
                self.setter(key_adapter.setter_factory(owner_cls, self))

    @util.hide_in_traceback
    def getter[**P](self, func: _Getter[V, P]) -> _GetterMethod[V, P]:
        super().getter(func)

        # apply any new keyword arguments
        if func in MethodKwArg._decorated:
            getter_kwargs = MethodKwArg._decorated.pop(func)
            if self._setter is None:
                self._kwargs = getter_kwargs
            else:
                raise TypeError(
                    'apply kwarg decorators to the setter, since it was defined first'
                )

        # validate arguments
        if self._setter is not None:
            self._validate_paired_signatures()

        return typing.cast(_GetterMethod[V, P], self)

    @util.hide_in_traceback
    def setter[**P](self, func: _Setter[V, P]) -> _SetterMethod[V, P]:
        super().setter(func)

        # apply new keyword arguments
        if func in MethodKwArg._decorated:
            setter_kwargs = MethodKwArg._decorated.pop(func)
            if self._getter is None:
                self._kwargs = setter_kwargs
            else:
                raise TypeError(
                    'apply kwarg decorators to the getter, since it was defined first'
                )

        if self._getter is not None:
            self._validate_paired_signatures()

        return typing.cast(_SetterMethod[V, P], self)

    __call__ = getter

    def get_kwarg_names(self):
        # assumes that the two below have already been validated to be the
        # same, e.g., in self.setter and self.getter
        if self.gets and self._getter:
            return name_arguments(self._getter)[1:]
        elif self.sets and self._setter:
            return name_arguments(self._setter)[2:]
        else:
            return tuple()

    def _raise_on_setattr(self, owner, value):
        me = self.__repr__(owner=owner)
        call_name = self.__repr__(owner=owner, with_declaration=False)
        raise AttributeError(
            f'set {me} through the function call {call_name}(new_value, ...)'
        )

    @util.hide_in_traceback
    def _validate_paired_signatures(self):
        """called when both getter and setter are decorated to ensure that their arguments match"""

        if (
            self.name is None
            and self.key is not None
            and self._getter is not None
            and self._setter is not None
        ):
            # in this case, we've defined the setter and getter through decorators, even though we expect
            # a key implementation
            util.logger.warning(
                f'{self} key argument overridden by both @getter and @setter'
            )

        # number and names of arguments
        assert self._setter is not None
        assert self._getter is not None

        if name_arguments(self._setter)[2:] != name_arguments(self._getter)[1:]:
            ex = TypeError('setter and getter keyword argument names must match')
            if hasattr(ex, 'add_note'):
                # python >= 3.10

                ex.add_note(f'method name: {self.name}')
                ex.add_note(f'setter arguments: {name_arguments(self._setter)}')
                ex.add_note(f'getter arguments: {name_arguments(self._getter)}')
            raise ex

        # defaults
        getter_defaults = default_arguments(self._getter)
        setter_defaults = default_arguments(self._setter)
        if getter_defaults[::-1] != setter_defaults[::-1][: len(getter_defaults)]:
            raise TypeError('setter and getter default arguments must match')


class Property[V](OwnerAccessAttr[V]):
    key: str | None = field(default=None, kw_only=False)
    """when set, this defines the property implementation based on a key adapter in the owner"""

    get_on_set: bool = False
    """if True, a property get follows in order to log the "accepted" property value"""

    # for descriptive purposes
    ROLE = 'property'

    @typing.overload
    def __get__(self, owner: None, owner_cls: type[HasParamAttrs]) -> Property[V]: ...

    @typing.overload
    def __get__(self, owner: HasParamAttrs, owner_cls: type[HasParamAttrs]) -> V: ...

    @util.hide_in_traceback
    def __get__(
        self,
        owner: None | HasParamAttrs,
        owner_cls: Any,
    ) -> Property[V] | V:
        """Called by the class instance that owns this attribute to
        retreive its value. This, in turn, decides whether to call a wrapped
        decorator function or the owner's property adapter method to retrieve
        the result.

        Returns:
            retreived value
        """

        # only continue to get the value if the __get__ was called for an owning
        # instance, and owning class is a match for what we were told in __set_name__.
        # otherwise, someone else is trying to access `self` and we
        # shouldn't get in their way.
        if owner is None:
            # escape an infinite recursion loop before accessing any class members
            return self

        cls_getter = owner_cls.__dict__.get(self.name or '', None)
        objclass_getter = self.__objclass__.__dict__.get(self.name or '')
        if cls_getter is not objclass_getter:
            return self
        else:
            return self.get_from_owner(owner)

    @util.hide_in_traceback
    def __set__(self, owner: HasParamAttrs, value: V | None):
        self.set_in_owner(owner, value)

        if self.get_on_set:
            self.__get__(owner, type(owner))

    @util.hide_in_traceback
    def getter(self, func: typing.Callable[[Any], V]) -> typing.Self:
        return super().getter(func)

    @util.hide_in_traceback
    def setter(self, func: typing.Callable[[Any, V], None]) -> typing.Self:
        return super().setter(func)

    __call__ = getter


@contextmanager
def hold_attr_notifications(owner: HasParamAttrs):
    def skip_notify(name, value, type, cache, kwargs={}):
        # old = owner._attr_store.cache.setdefault(name, Undefined)
        # msg = dict(new=value, old=old, owner=owner, name=name, type=type, cache=cache)
        owner._attr_store.cache[name] = value

    original, owner.__notify__ = owner.__notify__, skip_notify  # type: ignore
    yield
    owner.__notify__ = original  # type: ignore


class HasParamAttrsInstInfo:
    handlers: dict[str, typing.Callable]
    calibrations: dict[None | str, Any]
    cache: dict[None | str, Any]
    methods: dict[str, _MethodDescriptor]

    __slots__ = 'handlers', 'calibrations', 'cache', 'methods'

    def __init__(self, owner: HasParamAttrs):
        self.handlers = {}
        self.cache = {}
        self.calibrations = {}
        self.methods = {}


def get_key_adapter(obj: HasParamAttrs | type[HasParamAttrs]) -> KeyAdapterBase:
    return obj._attr_defs.key_adapter


def list_value_attrs(obj: HasParamAttrs | type[HasParamAttrs]) -> list[str]:
    """returns a mapping of names of labbench value paramattrs defined in `obj`"""
    return get_owner_meta(obj).value_names()


def list_method_attrs(obj: HasParamAttrs | type[HasParamAttrs]) -> list[str]:
    """returns a mapping of names of labbench method paramattrs defined in `obj`"""
    return get_owner_meta(obj).method_names()


def list_property_attrs(obj: HasParamAttrs | type[HasParamAttrs]) -> list[str]:
    """returns a list of names of labbench property paramattrs defined in `obj`"""
    return get_owner_meta(obj).property_names()


class HasParamAttrs(metaclass=HasParamAttrsMeta):
    _attr_defs: typing.ClassVar[HasParamAttrsClsInfo]

    def __init__(self, **values):
        self._attr_store = HasParamAttrsInstInfo(self)
        for attr_def in get_class_attrs(self).values():
            attr_def.__init_owner_instance__(self)

    @util.hide_in_traceback
    def __init_subclass__(cls):
        attr_defs = get_class_attrs(cls)

        for name, attr_def in dict(attr_defs).items():
            # Apply the decorator to the object if it is "part 2" of a decorator
            obj = getattr(cls, name)

            if not isinstance(obj, ParamAttr):
                if isinstance(attr_def, (Method, Property)) and callable(obj):
                    # if it's a method, decorate it.
                    # TODO: check if this is really necessary
                    attr_defs[name] = attr_def(obj)  # type: ignore
                else:
                    # if not decorating, clear from the attrs dict, and emit a warning at runtime
                    thisclsname = cls.__qualname__
                    parentclsname = cls.__mro__[1].__qualname__
                    warn(
                        f"'{name}' in {thisclsname} is not a ParamAttr instance, but replaces one in parent class {parentclsname}"
                    )

                    continue

            setattr(cls, name, attr_defs[name])

        # # clear the initialized attributes from the pending entries in the metaclass
        # if attr_defs in type(cls).ns_pending:
        #     type(cls).ns_pending.remove(attr_defs)

        # finalize attribute setup
        for name, attr_def in dict(attr_defs).items():
            if not hasattr(attr_def, '__objclass__'):
                attr_def.__set_name__(cls, name)
            attr_def.__init_owner_subclass__(cls)

    @util.hide_in_traceback
    def __notify__(self, name, value, type, cache, kwargs={}):
        msg = dict(
            new=value,
            old=self._attr_store.cache.setdefault(name, Undefined),
            owner=self,
            name=name,
            paramattr=get_class_attrs(self)[name],
            type=type,
            cache=cache,
            kwargs=kwargs,
        )

        for handler in list(self._attr_store.handlers.values()):
            handler(dict(msg))

        self._attr_store.cache[name] = value

    @util.hide_in_traceback
    def __get_value__(self, name):
        """returns the cached value of a value attribute for this instance.

        Arguments:
            name: Name of the attribute in self
        Returns:
            cached value of the type specified by its ParamAttr
        """
        return self._attr_store.cache[name]

    @util.hide_in_traceback
    def __set_value__(self, name, value):
        """Set value of a attribute for this value attributes instance

        Arguments:
            name: Name of the attribute
            value: value to assign
        Returns:
            None
        """
        # assignment to to self.__cache__ here would corrupt 'old' message key in __notify__


def adjust(
    paramattr: ParamAttr | str, default_or_key: Any = Undefined, /, **kws
) -> typing.Callable[[type[THasParamAttrs]], type[THasParamAttrs]]:
    """decorates a Device subclass to adjust the definition of the specified ParamAttr.

    This can be applied to inherited classes that need one of its parents attributes
    with an adjusted definition. Multiple decorators can be stacked to the
    same class definition.

    Args:
        paramattr: the ParamAttr name or instance to adjust
        default_or_key: new default or key argument (these can also be passed in **kws)

    Raises:
        ValueError: invalid type of ParamAttr argument, or when d
        TypeError: _description_
        ValueError: _description_

    Note:
        Changes to value defaults are not captured in type hints. Therefore,
        the defaults in their owning classes will not change in IDEs.

    Returns:
        HasParamAttrs or Device with adjusted attributes value
    """
    warn(
        'labbench.paramattr.adjusted("param_name") has been deprecated in favor '
        'of the labbench.paramattr.copy(DeviceName.param_name), to improve type '
        'hinting compatibility',
        DeprecationWarning,
        stacklevel=2,
    )
    if isinstance(paramattr, ParamAttr):
        name = paramattr.name
    elif isinstance(paramattr, builtins.str):
        name = paramattr
    else:
        raise ValueError('expected ParamAttr or str instance for `paramattr` argument')

    if name is None:
        raise TypeError('cannot use unnamed paramattr')

    def apply_adjusted_paramattr(
        owner_cls: type[THasParamAttrs],
    ) -> type[THasParamAttrs]:
        if not issubclass(owner_cls, HasParamAttrs):
            raise TypeError('must decorate a Device class definition')
        attr_def = getattr(owner_cls, name)
        if default_or_key is not Undefined:
            if isinstance(attr_def, Value):
                kws['default'] = default_or_key
            elif isinstance(attr_def, (Property, Method)):
                kws['key'] = default_or_key

        if name not in owner_cls.__dict__:
            raise ValueError(
                f'the decorated class {owner_cls!r} has no paramattr "{name}"'
            )

        parent_attr = super(owner_cls, owner_cls)
        if parent_attr is attr_def:
            # don't clobber the parent's paramattr
            attr_def = attr_def.copy(kws)
            setattr(owner_cls, name, attr_def)
        else:
            attr_def.update(**kws)
        # owner_cls.__update_signature__()
        return owner_cls

    return apply_adjusted_paramattr


THasParamAttrs = typing.TypeVar('THasParamAttrs', bound=HasParamAttrs)


def observe(obj, handler, name=Undefined, type_=('get', 'set')):
    """Register a handler function to be called on changes to attributes defined with ParamAttr.

    The handler function takes a single message argument. This
    dictionary message has the keys

    * `new`: the updated value
    * `old`: the previous value
    * `owner`: the object that owns the attribute
    * `name`: the name of the attribute
    * 'event': 'set' or 'get'

    Arguments:
        handler: the handler function to call when the value changes
        names: notify only changes to these attribute names (None to disable filtering)
    """

    def validate_name(n):
        attr = getattr(type(obj), n, Undefined)
        if attr is Undefined:
            raise TypeError(f'there is no attribute "{n}" to observe in "{obj}"')
        elif not isinstance(attr, ParamAttr):
            raise TypeError(f'cannot observe {obj}.{n} because it is not a attribute')

    if not callable(handler):
        raise ValueError(f"argument 'handler' is {handler!r}, which is not a callable")

    if isinstance(name, str):
        validate_name(name)
        name = (name,)
    elif isinstance(name, (tuple, list)):
        for n in name:
            validate_name(n)
    elif name is not Undefined:
        raise ValueError(
            f'name argument {name} has invalid type - must be one of (str, tuple, list), or the value Undefined'
        )

    if isinstance(type, str):
        type_ = (type_,)

    def wrapped(msg):
        # filter according to name and type
        if name is not Undefined and msg['name'] not in name:
            return
        elif msg['type'] not in type_:
            return
        elif isinstance(msg['new'], ParamAttr):
            raise TypeError('ParamAttr instance returned as a callback value')
        handler(msg)

    if isinstance(obj, HasParamAttrs):
        obj._attr_store.handlers[handler] = wrapped
    else:
        raise TypeError('object to observe must be an instance of Device')


def unobserve(obj, handler):
    """Unregister a handler function from notifications in obj."""
    if isinstance(obj, HasParamAttrs):
        try:
            del obj._attr_store.handlers[handler]
        except KeyError as e:
            ex = e
        else:
            ex = None
        if ex:
            raise KeyError(f'{handler} was not registered to observe {obj}')
    else:
        raise TypeError('object to unobserve must be an instance of Device')


def find_paramattr_in_mro(cls):
    if issubclass(cls, DependentNumberParamAttr):
        return find_paramattr_in_mro(type(cls._cal_deps['base']))
    else:
        return cls


class DependentParamAttr[V](ParamAttr[V]):
    _cal_deps: dict[str, ParamAttr] = dict()

    def __set_name__(self, owner_cls, name):
        if self.name not in (name, None):
            # extra calls here result when .setter() and .getter()
            # decorators are applied in Method or Property
            return

        super().__set_name__(owner_cls, name)

        # propagate ownership of dependent ParamAttr instances, if available
        if isinstance(owner_cls, HasParamAttrs):
            objclass = owner_cls
        elif hasattr(self, '__objclass__'):
            objclass = self.__objclass__
        else:
            return

        for attr_def in self._cal_deps.values():
            attr_def.__objclass__ = objclass

    def _validate_attr_dependencies(self, owner, allow_none: bool, operation='access'):
        if allow_none:
            return

        none_names = [
            f'{owner}.{attr.name}'
            for attr in self._cal_deps.values()
            if getattr(owner, attr.name) is None  # ty: ignore
        ]

        if len(none_names) == 1:
            raise ValueError(
                f'cannot {operation} {owner}.{self.name} while {none_names[0]} is None'
            )
        elif len(none_names) > 1:
            raise ValueError(
                f'cannot {operation} {owner}.{self.name} while {tuple(none_names)} are None'
            )

    @classmethod
    def derive[T: ParamAttr](
        mixin_cls: type[ParamAttr],
        template_attr: ParamAttr,
        dependent_attrs={},
        *init_args,
        **init_kws,
    ) -> type[ParamAttr]:
        type_name = type(template_attr).__name__
        type_name = ('' if type_name.startswith('derived') else 'derived_') + type_name

        dependent_attrs['base'] = template_attr

        attrs_dict = {}

        for c in mixin_cls.__mro__:
            if issubclass(c, DependentNumberParamAttr):
                attrs_dict.update(c._cal_deps)

        attrs_dict.update(dependent_attrs)

        ns = dict(_cal_deps=attrs_dict, **dependent_attrs)

        ttype = type(
            type_name, (mixin_cls, find_paramattr_in_mro(type(template_attr))), ns
        )

        obj = typing.cast(type[ParamAttr], ttype(*init_args, **init_kws))
        return obj

    def doc_params(
        self, skip: list[str] = ['help', 'label'], as_argument: bool = False
    ) -> str:
        if as_argument:
            return ''
        else:
            return '* Bounds depend on calibration data at run-time'


class DependentNumberParamAttr[V](DependentParamAttr[V]):
    def derived_max(self, owner) -> V:
        """this should be overloaded to dynamically compute max"""
        assert isinstance(self, BoundedNumber)
        return typing.cast(V, self.max)

    def derived_min(self, owner) -> V:
        """this should be overloaded to dynamically compute max"""
        assert isinstance(self, BoundedNumber)
        return typing.cast(V, self.min)

    @util.hide_in_traceback
    def check_bounds(self, value, owner=None):
        max_ = self.derived_max(owner)
        if max_ is None:
            ex = ValueError(f'cannot set {self} while dependent attributes are unset')
            if hasattr(ex, 'add_note'):
                for dep in self._cal_deps.values():
                    # python >= 3.10
                    ex.add_note(f'dependent attribute: {dep}')
            raise ex
        if value > max_:
            raise ValueError(
                f'{value} is greater than the max limit {max_} of {self._owned_name(owner)}'
            )

        min_ = self.derived_min(owner)
        if value < min_:
            raise ValueError(
                f'{value} is less than the min limit {min_} of {self._owned_name(owner)}'
            )


class RemappedBoundedNumberMixIn(DependentNumberParamAttr):
    """act as another BoundedNumber ParamAttr, calibrated with a mapping"""

    mapping: Any = None  # really a pandas Series

    EMPTY_STORE = dict(by_cal=None, by_uncal=None)

    def __init_owner_instance__(self, owner: HasParamAttrs):
        super().__init_owner_instance__(owner)
        self.set_mapping(self.mapping, owner=owner)
        observe(
            owner,
            self._on_base_paramattr_change,
            name=self._cal_deps['base'].name,
        )

    def _on_base_paramattr_change(self, msg):
        owner = msg['owner']
        owner.__notify__(
            self.name,
            self.lookup_cal(msg['new'], owner),
            msg['type'],
            cache=msg['cache'],
        )

    def lookup_cal(self, uncal, owner):
        """look up and return the calibrated value, given the uncalibrated value"""
        owner_cal = owner._attr_store.calibrations.get(self.name, self.EMPTY_STORE)
        if owner_cal.get('by_uncal', None) is None:
            return None
        try:
            return owner_cal['by_uncal'].loc[uncal]
        except KeyError:
            # spare us pandas details in the traceback
            util.logger.warning(
                f'{self.__repr__(owner=owner)} has no entry at {uncal!r} {self.label}'
            )

        return None

    def find_uncal(self, cal, owner):
        """look up the calibrated value for the given uncalibrated value. In the event of a lookup
        error, then if `self.allow_none` evaluates as True, triggers return of None, or if
         `self.allow_none` evaluates False, ValueError is raised.
        """
        owner_cal = owner._attr_store.calibrations.get(self.name, self.EMPTY_STORE)

        if owner_cal['by_uncal'] is None:
            return None

        i = owner_cal['by_cal'].index.get_indexer([cal], method='nearest')[0]
        return owner_cal['by_cal'].iloc[i]

    def set_mapping(self, series_or_uncal, cal=None, owner=None):
        """set the lookup mapping as `set_mapping(series)`, where `series` is a pandas Series (uncalibrated
        values in the index), or `set_mapping(cal_vector, uncal_vector)`, where both vectors have 1
        dimension of the same length.
        """

        if owner is None:
            raise ValueError('must pass owner to set_mapping')

        if isinstance(series_or_uncal, pd.Series):
            by_uncal = pd.Series(series_or_uncal).copy()
        elif cal is not None:
            by_uncal = pd.Series(cal, index=series_or_uncal)
        elif series_or_uncal is None:
            return
        else:
            raise ValueError(
                f'must call set_mapping with None, a Series, or a pair of vector '
                f'arguments, not {series_or_uncal}'
            )
        by_uncal = by_uncal[~by_uncal.index.duplicated(keep='first')].sort_index()
        by_uncal.index.name = 'uncal'
        by_uncal.name = 'cal'

        by_cal = pd.Series(by_uncal.index, index=by_uncal.values, name='uncal')
        by_cal = by_cal[~by_cal.index.duplicated(keep='first')].sort_index()
        by_cal.index.name = 'cal'

        (
            owner._attr_store.calibrations.setdefault(self.name, {}).update(
                by_cal=by_cal, by_uncal=by_uncal
            )
        )

    def derived_min(self, owner):
        table = (
            get_owner_store(owner)
            .calibrations.setdefault(self.name, {})
            .get('by_cal', None)
        )

        if table is None:
            return None
        else:
            return table.index[0]

    def derived_max(self, owner):
        table = (
            get_owner_store(owner)
            .calibrations.setdefault(self.name, {})
            .get('by_cal', None)
        )

        if table is None:
            return None
        else:
            return table.index[-1]

    @util.hide_in_traceback
    def get_from_owner(self, owner: HasParamAttrs, kwargs: dict[str, Any] = {}):
        # by_cal, by_uncal = owner._attr_store.calibrations.get(self.name, (None, None))
        self._validate_attr_dependencies(owner, self.allow_none, 'get')

        uncal = self._cal_deps['base'].get_from_owner(owner, kwargs)

        cal = self.lookup_cal(uncal, owner)

        if cal is None:
            ret = uncal
        else:
            ret = cal

        if getattr(self, 'name', None) is not None:
            owner.__notify__(
                self.name,
                ret,
                'get',
                cache=self.cache or isinstance(self, Value),
            )

        return ret

    @util.hide_in_traceback
    def set_in_owner(self, owner: HasParamAttrs, value, kwargs: dict[str, Any] = {}):
        # owner_cal = owner._attr_store.calibrations.get(self.name, self.EMPTY_STORE)
        self._validate_attr_dependencies(owner, False, 'set')
        self._prepare_set_value(owner, value, kwargs)

        # start with type conversion and validation on the requested calibrated value
        value = self._cal_deps['base'].to_pythonic(value)

        # lookup the uncalibrated value that results in the nearest calibrated result
        uncal_value = self.find_uncal(value, owner)
        base = self._cal_deps['base']

        if uncal_value is None:
            base.set_in_owner(owner, value, kwargs)
        elif uncal_value != base.validate(uncal_value, owner):
            # raise an exception if the calibration table contains invalid values instead
            raise ValueError(
                f'calibration lookup in {self.__repr__(owner=owner)} produced invalid value {uncal_value!r}'
            )
        else:
            # execute the set
            self._cal_deps['base'].set_in_owner(owner, uncal_value, kwargs)

        if getattr(self, 'name', None) is not None:
            owner.__notify__(
                self.name,
                value,
                'set',
                cache=self.cache or isinstance(self, Value),
            )


class TableCorrectionMixIn(RemappedBoundedNumberMixIn):
    _CAL_TABLE_KEY = 'table'

    path_attr: ParamAttr = field()  # a dependent Unicode ParamAttr
    index_lookup_attr: 'BoundedNumber' = field()  # a dependent ParamAttr
    table_index_column: str | None = None

    def __init_owner_instance__(self, owner):
        super().__init_owner_instance__(owner)

        assert self.path_attr.name is not None
        assert self.index_lookup_attr.name is not None

        # seed the calibration table if the depenent attributes allow
        path = getattr(owner, self.path_attr.name)

        if path is not None:
            self._load_calibration_table(owner, path)

            index = getattr(owner, self.index_lookup_attr.name)
            if index is not None:
                self._update_index_value(owner, index)

        observe(
            owner,
            self._on_cal_update_event,
            name=[self.path_attr.name, self.index_lookup_attr.name],
            type_='set',
        )

    def _on_cal_update_event(self, msg):
        owner = msg['owner']

        if msg['name'] == self.path_attr.name:
            # if msg['new'] == msg['old']:
            #     return

            assert self.index_lookup_attr.name is not None

            path = msg['new']
            index = getattr(owner, self.index_lookup_attr.name)

            ret = self._load_calibration_table(owner, path)
            self._update_index_value(owner, index)

            return ret

        elif msg['name'] == self.index_lookup_attr.name:
            # if msg['new'] == msg['old']:
            #     return
            assert self.path_attr.name is not None
            path = getattr(owner, self.path_attr.name)
            index = msg['new']

            if self._CAL_TABLE_KEY not in owner._attr_store.calibrations.get(
                self.name, {}
            ):
                self._load_calibration_table(owner, path)

            ret = self._update_index_value(owner, index)

            return ret

        else:
            raise KeyError(f'unsupported parameter attribute name {msg["name"]}')

    def _load_calibration_table(self, owner, path):
        """stash the calibration table from disk"""

        def read(path):
            # quick read
            cal = pd.read_csv(str(path), index_col=self.table_index_column, dtype=float)

            cal.columns = cal.columns.astype(float)

            if self.index_lookup_attr.max in cal.index:
                cal.drop(self.index_lookup_attr.max, axis=0, inplace=True)
            #    self._cal_offset.values[:] = self._cal_offset.values-self._cal_offset.columns.values[np.newaxis,:]

            owner._attr_store.calibrations.setdefault(self.name, {}).update({
                self._CAL_TABLE_KEY: cal
            })

            owner._logger.debug(f'calibration data read from "{path}"')

        if path is None:
            if not self.allow_none:
                desc = self.__repr__(owner=owner, with_declaration=False)
                raise ValueError(
                    f'{desc} defined with allow_none=False; path_attr must not be None'
                )
            else:
                return None

        read(path)

    def _touch_table(self, owner):
        # make sure that calibrations have been initialized
        table = owner._attr_store.calibrations.get(self.name, {}).get(
            self._CAL_TABLE_KEY, None
        )

        if table is None:
            assert self.path_attr.name is not None
            assert self.index_lookup_attr.name is not None
            path = getattr(owner, self.path_attr.name)
            index = getattr(owner, self.index_lookup_attr.name)

            if None not in (path, index):
                setattr(owner, self.path_attr.name, path)
                setattr(owner, self.index_lookup_attr.name, index)

    def _update_index_value(self, owner, index_value):
        """update the calibration on change of index_value"""
        cal = owner._attr_store.calibrations.get(self.name, {}).get(
            self._CAL_TABLE_KEY, None
        )

        if cal is None:
            txt = 'index_value change has no effect because calibration_data has not been set'
        elif index_value is None:
            cal = None
            txt = 'set {owner}.{self.index_lookup_attr.name} to enable calibration'
        else:
            # pull in the calibration mapping specific to this index_value
            # i_freq = cal.index.get_loc(index_value, "nearest")
            i_freq = cal.index.get_indexer([index_value], method='nearest')[0]
            cal = cal.iloc[i_freq]
            txt = f'calibrated to {index_value} {self.label}'
        owner._logger.debug(txt)

        self.set_mapping(cal, owner=owner)

    @util.hide_in_traceback
    def get_from_owner(self, owner: HasParamAttrs, kwargs: dict[str, Any] = {}):
        self._touch_table(owner)
        return super().get_from_owner(owner, kwargs)

    @util.hide_in_traceback
    def set_in_owner(self, owner: HasParamAttrs, value, kwargs: dict[str, Any] = {}):
        self._touch_table(owner)
        super().set_in_owner(owner, value, kwargs)

    def doc_params(
        self, skip: list[str] = ['help', 'label'], as_argument: bool = False
    ) -> str:
        if as_argument:
            return ''
        else:
            return (
                f'* Returns None unless both {self.index_lookup_attr.name!r} '
                f' and {self.path_attr.name!r} are set'
            )


class TransformedNumberMixIn[V](DependentNumberParamAttr[V]):
    """act as an arbitrarily-defined (but reversible) transformation of another BoundedNumber"""

    @staticmethod
    def _forward(x, y):
        return x

    @staticmethod
    def _reverse(x, y):
        return x

    def __init_owner_instance__(self, owner):
        super().__init_owner_instance__(owner)
        observe(owner, self.__owner_event__)

    def __owner_event__(self, msg):
        # pass on a corresponding notification when the base changes
        base_attr = self._cal_deps['base']

        if msg['name'] != getattr(base_attr, 'name', None) or not hasattr(
            base_attr, '__objclass__'
        ):
            return

        owner = msg['owner']
        if self.name is not None:
            owner.__notify__(self.name, msg['new'], msg['type'], cache=msg['cache'])

    def _transformed_extrema(self, owner):
        base_attr = self._cal_deps['base']
        assert isinstance(base_attr, TransformedNumberMixIn)
        base_bounds = base_attr.derived_min(owner), base_attr.derived_max(owner)

        other_attr = self._cal_deps.get('other', None)

        if other_attr is None:
            trial_bounds = [
                self._forward(base_bounds[0]),  # ty: ignore
                self._forward(base_bounds[1]),  # ty: ignore
            ]
        else:
            assert other_attr.name is not None
            other_value = getattr(owner, other_attr.name)
            trial_bounds = [
                self._forward(base_bounds[0], other_value),
                self._forward(base_bounds[1], other_value),
            ]

        if None in trial_bounds:
            return None, None

        return min(trial_bounds), max(trial_bounds)

    def derived_min(self, owner):
        # TODO: ensure this works properly for any reversible self._forward()?
        lo, hi = self._transformed_extrema(owner)

        if lo is None:
            return None
        else:
            return min(lo, hi)

    def derived_max(self, owner):
        # TODO: ensure this works properly for any reversible self._forward()?
        lo, hi = self._transformed_extrema(owner)

        if hi is None:
            return None
        else:
            return max(lo, hi)

    def get_from_owner(self, owner: HasParamAttrs, kwargs: dict[str, Any] = {}):
        base_value = self._cal_deps['base'].get_from_owner(owner, kwargs)

        if 'other' in self._cal_deps:
            other_value = self._cal_deps['other'].get_from_owner(owner, kwargs)
            ret = self._forward(base_value, other_value)
        else:
            ret = base_value

        if getattr(self, 'name', None) is not None:
            owner.__notify__(
                self.name,
                ret,
                'get',
                cache=self.cache or isinstance(self, Value),
            )

        return ret

    def set_in_owner(self, owner: HasParamAttrs, value, kwargs: dict[str, Any] = {}):
        # use the other to the value into the proper format and validate it
        base_attr = self._cal_deps['base']
        value = base_attr.to_pythonic(value)

        # now reverse the transformation
        if 'other' in self._cal_deps:
            other_attr = self._cal_deps['other']
            other_value = other_attr.get_from_owner(owner, kwargs)

            base_value = self._reverse(value, other_value)
        else:
            base_value = value

        # set the value of the base attr with the reverse-transformed value
        base_attr.set_in_owner(owner, base_value, kwargs)

        if getattr(self, 'name', None) is not None:
            owner.__notify__(
                self.name,
                value,
                'set',
                cache=self.cache or isinstance(self, Value),
            )


class BoundedNumber[V](ParamAttr[V]):
    """accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking)"""

    min: V | None = None
    max: V | None = None

    path_attr = None  # TODO: should be a Unicode string attribute
    index_lookup_attr = None
    table_index_column = None

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if not isinstance(value, (bytes, str, bool, numbers.Number)):
            raise ValueError(
                f"a '{type(self).__qualname__}' attribute supports only numerical, str, or bytes types"
            )
        self.check_bounds(value, owner)
        return value

    @util.hide_in_traceback
    def check_bounds(self, value, owner=None):
        # dynamic checks against self.derived_max() or self.derived_min() are left to derived classes
        if self.max is not None and value > self.max:
            raise ValueError(
                f'{value} is greater than the max limit {self.max} of {self._owned_name(owner)}'
            )
        if self.min is not None and value < self.min:
            raise ValueError(
                f'{value} is less than the min limit {self.min} of {self._owned_name(owner)}'
            )

    def doc_params(
        self, skip: list[str] = ['help', 'label'], as_argument: bool = False
    ) -> str:
        if as_argument:
            return ''

        else:
            # for text docs: allow subclasses to document their own params
            docs = []
            if self.min is not None:
                docs.append(f'* Minimum: {self.min} {self.label}')
            if self.max is not None:
                docs.append(f'* Maximum: {self.max} {self.label}')

            return '\n'.join(docs) + '\n'

    def corrected_from_table(
        self,
        path_attr: ParamAttr,
        index_lookup_attr: ParamAttr,
        *,
        table_index_column: str | None = None,
        help='',
        label: str | UndefinedType = Undefined,
        allow_none=False,
    ) -> typing.Self:
        """generate a new ParamAttr with value dependent on another attribute. their configuration
        comes from a attribute in the owner.

        Arguments:
            offset_name: the name of a value attribute in the owner containing a numerical offset
            lookup1d: a table containing calibration data, or None to configure later
        """

        if label is Undefined:
            label = self.label
        kws = dict(self.kws, label=label, help=help, allow_none=allow_none)

        ret = TableCorrectionMixIn.derive(
            self,
            dict(
                path_attr=path_attr,
                index_lookup_attr=index_lookup_attr,
            ),
            table_index_column=table_index_column,
            **kws,
        )

        return typing.cast(typing.Self, ret)

    def corrected_from_expression[T: ParamAttr](
        self,
        attr_expression: T,
        help: str = '',
        label: str | UndefinedType = Undefined,
        allow_none: bool = False,
    ) -> T:
        """create a read-only dependent attribute defined in terms of arithmetic operations on other ParamAttr
        instances.

        Example:
            attenuation = attenuation_setting.calibrate_from_table(
                path_attr=calibration_path,
                index_lookup_attr=frequency,
                table_index_column="Frequency(Hz)",
                help="calibrated attenuation",
            )

            output_power = attenuation.calibrate_from_expression(
                -attenuation + output_power_offset,
                help="calibrated output power level",
                label="dBm",
            )

        Args:
            attr_expression (_type_): an attribute formed of arithmetic operations on other ParamAttr instances
            help: documentation string for the resulting attribute
            label: label attribute in the returned ParamAttr
            allow_none (bool): Whether to allow None values in the returned ParamAttr.

        Raises:
            TypeError: _description_

        Returns:
            _type_: _description_
        """
        if isinstance(self, DependentNumberParamAttr):
            # This a little unsatisfying, but the alternative would mean
            # solving the attr_expression for `self`
            obj = attr_expression
            while isinstance(obj, DependentNumberParamAttr):
                obj = obj._cal_deps['base']
                if obj == self:
                    break
            else:
                raise TypeError(
                    'calibration target attribute be first in the calibration expression'
                )

        return self.update(
            attr_expression, help=help, label=label, allow_none=allow_none
        )

    def transform[T: ParamAttr](
        self,
        other_attr: T,
        forward: typing.Callable,
        reverse: typing.Callable,
        help: str = '',
        allow_none: bool = False,
    ) -> typing.Self:
        """generate a new attribute subclass that adjusts values in other attributes.

        Arguments:
            forward: implementation of the forward transformation
            reverse: implementation of the reverse transformation
        """

        obj = TransformedNumberMixIn.derive(
            self,
            dependent_attrs={} if other_attr is None else dict(other=other_attr),
            help=help,
            label=self.label,
            allow_none=allow_none,
            _forward=forward,
            _reverse=reverse,
        )

        return typing.cast(typing.Self, obj)

    def __neg__(self) -> typing.Self:
        def neg(x, y=None):
            return None if x is None else -x

        return self.transform(
            self, neg, neg, allow_none=self.allow_none, help=f'-1*({self.help})'
        )

    def __add__(self, other: ParamAttr) -> typing.Self:
        def add_fwd(x, y):
            return None if None in (x, y) else x + y

        def add_rev(x, y):
            return None if None in (x, y) else x - y

        return self.transform(
            other,
            add_fwd,
            add_rev,
            allow_none=self.allow_none,
            help=f'({self.help}) + {other}',
        )

    __radd__ = __add__

    def __sub__(self, other) -> typing.Self:
        def sub_fwd(x, y):
            return None if None in (x, y) else x - y

        def sub_rev(x, y):
            return None if None in (x, y) else x + y

        return self.transform(
            other,
            sub_fwd,
            sub_rev,
            allow_none=self.allow_none,
            help=f'({self.help}) + {other}',
        )

    def __rsub__(self, other) -> typing.Self:
        def rsub_rev(x, y):
            return None if None in (x, y) else y + x

        def rsub_fwd(x, y):
            return None if None in (x, y) else y - x

        return self.transform(
            other,
            rsub_fwd,
            rsub_rev,
            allow_none=self.allow_none,
            help=f'({self.help}) + {other}',
        )

    def __mul__(self, other) -> typing.Self:
        def mul(x, y):
            return None if None in (x, y) else x * y

        def div(x, y):
            return None if None in (x, y) else x / y

        return self.transform(
            other, mul, div, allow_none=self.allow_none, help=f'({self.help}) + {other}'
        )

    __rmul__ = __mul__

    def __truediv__(self, other) -> typing.Self:
        def mul(x, y):
            return None if None in (x, y) else x * y

        def div(x, y):
            return None if None in (x, y) else x / y

        return self.transform(
            other, div, mul, allow_none=self.allow_none, help=f'({self.help}) + {other}'
        )

    def __rdiv__(self, other) -> typing.Self:
        def mul(x, y):
            return None if None in (x, y) else y * x

        def div(x, y):
            return None if None in (x, y) else y / x

        return self.transform(
            other, div, mul, allow_none=self.allow_none, help=f'({self.help}) + {other}'
        )
