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
"""
This implementation is deeply intertwined obscure details of the python object
model. Consider starting with a close read of the documentation and exploring
the objects in an interpreter instead of reverse-engineering this code.
"""

from __future__ import annotations
import builtins
import inspect
from copy import copy
import numbers
import typing
from contextlib import contextmanager
from typing_extensions import dataclass_transform
from typing import Union, Callable, Type, Optional, Generic, Any
from functools import wraps

Undefined = inspect.Parameter.empty

T = typing.TypeVar("T")


# for common types
from warnings import warn

from .. import util

try:
    pd = util.lazy_import("pandas")
except RuntimeError:
    # not executed: help coding tools recognize lazy_imports as imports
    import pandas as pd

class no_cast_argument:
    """duck-typed stand-in for an argument of arbitrary type"""

    @classmethod
    def __cast_get__(self, owner, value):
        return value

def get_owner_store(obj: HasParamAttrs) -> HasParamAttrsInstInfo:
    return obj._attr_store
    
def get_owner_defs(obj: typing.Union[HasParamAttrs, Type[HasParamAttrs]]) -> HasParamAttrsClsInfo:
    return obj._attr_defs

def get_class_attrs(
    obj: Union[HasParamAttrs, Type[HasParamAttrs]]
) -> typing.Dict[str, ParamAttr]:
    """returns a mapping of labbench paramattrs defined in `obj`"""
    return obj._attr_defs.attrs


class KeyAdapterBase:
    key_arguments: typing.Dict[str, ParamAttr]

    # @typing.overload
    # def __new__(cls, /, decorated_cls: Type[T], **kws) -> Type[T]:
    #     ...

    # @typing.overload
    # def __new__(cls, /, decorated_cls: type(None), **kws) -> KeyAdapterBase:
    #     ...

    # def __new__(cls, /, decorated_cls: Type[T] = None, **kws):
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

    def __init__(
        self,
        *,
        key_arguments: typing.Dict[str, ParamAttr] = {},
    ):
        self.key_arguments = key_arguments

    def __call__(self, owner_cls: THasParamAttrsCls) -> THasParamAttrsCls:
        owner_defs = get_owner_defs(owner_cls)

        # add our key arguments to what's already in owner_cls
        key_arguments = dict(owner_defs.key_adapter.key_arguments, **self.key_arguments)

        # apply the new key adapter
        owner_defs.key_adapter = self.copy(key_arguments)

        return owner_cls

    def copy(self, update_key_arguments={}):
        obj = copy(self)
        obj.key_arguments = dict(obj.key_arguments, **update_key_arguments)
        return obj

    def get(self, owner: HasParamAttrs, key: str, attr: ParamAttr = None):
        """this must be implemented by a subclass to support of `labbench.parameter.method`
        `labbench.parameter.property` attributes that are implemented through the `key` keyword.
        """
        raise NotImplementedError(
            f'key adapter does not implement "get" {repr(type(self))}'
        )

    def set(self, owner: HasParamAttrs, key: str, value, attr: ParamAttr = None):
        """this must be implemented by a subclass to support of `labbench.parameter.method`
        `labbench.parameter.property` attributes that are implemented through the `key` keyword.
        """
        raise NotImplementedError(
            f'key adapter does not implement "set" {repr(type(self))}'
        )

    def get_key_arguments(self, key: Any) -> typing.List[str]:
        """returns a list of arguments for the parameter attribute key.

        This must be implemented in order to define `labbench.paramattr.method` attributes
        using the `key` keyword.
        """
        raise NotImplementedError(
            'key adapter needs "get_key_arguments" to implement methods by "key" keyword'
        )

    def method_from_key(self, owner_cls: THasParamAttrsCls, paramattr: ParamAttr):
        """Autogenerate a parameter getter/setter method based on the message key defined in a ParamAttr method."""

        kwargs_params = []
        defaults = {}
        for name in self.get_key_arguments(paramattr.key):
            try:
                arg_annotation = self.key_arguments[name]._type
                if self.key_arguments[name].default is not Undefined:
                    defaults[name] = self.key_arguments[name].default
            except KeyError:
                if self.key_arguments[name].required:
                    paramattr_desc = f"{owner_cls.__qualname__}.{paramattr.name}"
                    raise AttributeError(
                        f'"{name}" keyword argument declaration missing in method "{paramattr_desc}"'
                    )
                else:
                    arg_annotation = Any

            kwargs_params.append(
                inspect.Parameter(
                    name,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    annotation=arg_annotation,
                )
            )

        pos_params = [
            inspect.Parameter("self", kind=inspect.Parameter.POSITIONAL_ONLY),
            inspect.Parameter(
                "set_value",
                default=Undefined,
                kind=inspect.Parameter.POSITIONAL_ONLY,
                annotation=Optional[paramattr._type],
            ),
        ]

        def method(
            owner, set_value: paramattr._type = Undefined, /, **key_arguments
        ) -> Union[None, paramattr._type]:
            """the autogenerated method that binds the key to an owner and the attribute definition"""

            validated_kws = {
                # cast each keyword argument
                k: self.key_arguments[k]._finalize_get_value(owner, v)
                for k, v in key_arguments.items()
            }

            if set_value is Undefined:
                return paramattr.get_from_owner(owner, validated_kws)
            else:
                return paramattr.set_in_owner(owner, set_value, validated_kws)

        method.__signature__ = inspect.Signature(
            pos_params + kwargs_params, return_annotation=Optional[paramattr._type]
        )
        method.__name__ = paramattr.name
        method.__module__ = f"{owner_cls.__module__}"
        method.__qualname__ = f"{owner_cls.__qualname__}.{paramattr.name}"
        method.__doc__ = paramattr.doc()

        return method


class HasParamAttrsClsInfo:
    attrs: typing.Dict[str, ParamAttr]
    key_adapter: KeyAdapterBase
    key_arguments: typing.Dict[str, KeywordArgument]

    # unbound methods``
    methods: typing.Dict[str, Callable]

    __slots__ = ["attrs", "key_adapter", "key_arguments", "methods"]

    def __init__(
        self,
        attrs: typing.Dict[str, ParamAttr],
        key_adapter: KeyAdapterBase,
    ):
        self.attrs = attrs
        self.key_adapter = key_adapter

    def value_names(self) -> typing.List[ParamAttr]:
        return [k for k, v in self.attrs.items() if v.role == ParamAttr.ROLE_VALUE]

    def method_names(self) -> typing.List[ParamAttr]:
        return [k for k, v in self.attrs.items() if v.role == ParamAttr.ROLE_METHOD]

    def property_names(self) -> typing.List[ParamAttr]:
        return [k for k, v in self.attrs.items() if v.role == ParamAttr.ROLE_PROPERTY]

    @classmethod
    def _copy_from(cls, owner: HasParamAttrs):
        obj = cls(
            attrs={},
            key_adapter=get_owner_defs(owner).key_adapter,
        )
        obj.attrs = {k: v.copy() for k, v in get_owner_defs(owner).attrs.items()}
        return obj


class HasParamAttrsMeta(type):
    # hold on to recent namespaces until they can be used to initialize descriptors
    ns_pending: list = []

    @classmethod
    def __prepare__(metacls, names, bases, **kws):
        """Prepare fresh cls._attr_defs.attrs mappings to allow copy-on-write of ParamAttr
        definitions in subclasses.
        """
        ns = dict()
        if len(bases) >= 1:
            cls_info = ns["_attr_defs"] = HasParamAttrsClsInfo._copy_from(bases[0])
            ns.update(cls_info.attrs)
            metacls.ns_pending.append(cls_info.attrs)
            return ns
        else:
            ns["_attr_defs"] = HasParamAttrsClsInfo(
                attrs={}, key_adapter=KeyAdapterBase()
            )
            metacls.ns_pending.append({})
        return ns


def _parameter_maybe_positional(param: inspect.Parameter):
    return param.kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    )


# This is only used for method types
TCall = typing.TypeVar("TCall")


class field(Generic[T]):
    # __slots__ = 'kw_only', 'default'

    def __new__(cls, default: T = Undefined, kw_only=True) -> T:
        if not kw_only:
            ret = object.__new__(cls)
            cls.__init__(ret, default=default, kw_only=kw_only)
        else:
            ret = default
        return ret

    def __init__(self, default=Undefined, kw_only=True):
        self.kw_only = kw_only
        self.default = default


@dataclass_transform(eq_default=False, kw_only_default=True, field_specifiers=(field[T],))
class ParamAttr(Generic[T]):
    """base class for typed descriptors in Device classes. These
    implement type checking, casting, decorators, and callbacks.

    A Device instance supports two types of ParamAttrs:

    * A _value attribute_ acts as an attribute variable in instantiated
      classes

    * A _property attribute_ applies get and set operations for a
      parameter that requires API calls in the owning class,
      exposed in the style of a python `property`

    * A _method attribute_ applies get and set operations for a
      parameter that requires API calls in the owning class,
      exposed in the style of a python function attribute (method)
      that can be called with additional arguments

    Arguments:
        key: specify automatic implementation with the Device (backend-specific)
        help: the ParamAttr docstring
        label: a label for the quantity, such as units
        sets: True if the attribute supports writes
        gets: True if the attribute supports reads
        cache: if True, interact with the device only once, then return copies (state attribute only)
        only: value allowlist; others raise ValueError
        allow_none: permit None values in addition to the specified type

    """

    ROLE_VALUE = "ROLE_VALUE"
    ROLE_PROPERTY = "ROLE_PROPERTY"
    ROLE_METHOD = "ROLE_METHOD"
    ROLE_UNSET = "ROLE_UNSET"
    ROLE_ARGUMENT = "ROLE_ARGUMENT"

    _type = None
    role = ROLE_UNSET

    # keyword argument types and default values
    help: str = ""
    label: str = ""
    sets: bool = True
    gets: bool = True
    cache: bool = False
    only: tuple = tuple()
    allow_none: bool = False

    _keywords = {}
    _defaults = {}
    _positional = []
    name = None

    def __init__(self, *args, **kws):
        # apply the dataclass entries
        for arg, name in zip(args, self._positional):
            kws[name] = arg

        self.kws = kws

        public_names = {name for name in kws.keys() if not name.startswith('_')}
        defaults = set(self._defaults.keys())
        annotated_names = set(self.__annotations__)
        private_names = defaults - public_names
        unexpected = (
            (public_names - annotated_names) # "public" annotated names
            | (private_names - defaults) # secret "private" arguments starting with _
        )
        if len(unexpected) > 0:
            unexpected = ', '.join(unexpected)
            raise TypeError(f'invalid keyword argument(s): {unexpected}')

        required = annotated_names - defaults
        missing_required = required - public_names
        if len(missing_required) > 0:
            missing_required = ', '.join(missing_required)
            raise TypeError(f'missing required keyword argument(s): {missing_required}')

        # set value attributes
        for k, v in dict(self._defaults, **kws).items():
            setattr(self, k, v)

    def copy(self, new_type=None, **update_kws):
        if new_type is None:
            new_type = type(self)
        obj = new_type(**dict(self.kws, **update_kws))
        return obj

    @classmethod
    def __init_subclass__(cls, type: typing.Type[T] = Undefined):
        """python triggers this call immediately after a ParamAttr subclass
            is defined, allowing us to automatically customize its implementation.

        Arguments:
            type: the python type of the parameter
        """
        if type is not Undefined:
            cls._type = type

        # cache annotated fields in the class for faster lookup later
        cls.__annotations__ = typing.get_type_hints(cls)
        cls._defaults = {}
        cls._positional = []
        for k in cls.__annotations__.keys():
            obj = getattr(cls, k)
            if isinstance(obj, field):
                if not obj.kw_only:
                    cls._positional.append(k)
                cls._defaults[k] = obj.default
            else:
                cls._defaults[k] = getattr(cls, k)

        # Help to reduce memory use by __slots__ definition (instead of __dict__)
        cls.__slots__ = [n for n in dir(cls) if not callable(getattr(cls, n))] + [
            "metadata",
            "kind",
            "name",
        ]

    # Descriptor methods (called automatically by the owning class or instance)
    def __set_name__(self, owner_cls, name):
        """Called on owner class instantiation (python object protocol)"""
        # other owning objects may unintentionally become owners; this causes problems
        # if they do not implement the HasParamAttrs object protocol
        if issubclass(owner_cls, HasParamAttrs):
            # inspect module expects this name - don't play with it
            self.__objclass__ = owner_cls

            # Take the given name
            self.name = name

            get_class_attrs(owner_cls)[name] = self

    def __init_owner_subclass__(self, owner_cls: Type[HasParamAttrs]):
        """The owner calls this in each of its ParamAttr attributes at the end of defining the subclass
        (near the end of __init_subclass__). Now it is time to ensure properties are compatible with the
        owner class. This is here --- not in __set_name__ --- because python
        obfuscates exceptions raised in __set_name__.

        This is also where we finalize selecting decorator behavior; is it a property or a method?
        """
        pass

    def __init_owner_instance__(self, owner: HasParamAttrs):
        pass

    @util.hide_in_traceback
    def _prepare_set_value(
        self, owner: HasParamAttrs, value, arguments: typing.Dict[str, Any] = {}
    ):
        # First, validate the pythonic types
        if not self.sets:
            raise AttributeError(f"{self.__str__()} cannot be set")
        if value is not None:
            # cast to self._type and validate
            value = self.to_pythonic(value)
            value = self.validate(value, owner)

            if len(self.only) > 0 and not self.contains(self.only, value):
                raise ValueError(
                    f"value '{value}' is not among the allowed values {repr(self.only)}"
                )
        elif self.allow_none:
            value = None
        else:
            raise ValueError(f"None value not allowed for parameter '{repr(self)}'")

        try:
            value = self.from_pythonic(value)
        except BaseException as e:
            name = owner.__class__.__qualname__ + "." + self.name
            e.args = (e.args[0] + f" in attempt to set '{name}'",) + e.args[1:]
            raise e

        return value

    def get_from_owner(
        self, owner: HasParamAttrs, arguments: typing.Dict[str, Any] = {}
    ):
        raise NotImplementedError

    def set_in_owner(
        self, owner: HasParamAttrs, value, arguments: typing.Dict[str, Any] = {}
    ):
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
            # name = owner.__class__.__qualname__ + '.' + self.name
            e.args = (
                e.args[0] + f" in attempt to get '{self.__repr__(owner_inst=owner)}'",
            ) + e.args[1:]
            raise e

        if value is None:
            log = getattr(owner, "_logger", warn)
            log(
                f"'{self.__repr__(owner_inst=owner)}' {self.role} received value None, which"
                f"is not allowed for {repr(self)}"
            )

        if len(self.only) > 0 and not self.contains(self.only, value):
            log = getattr(owner, "_logger", warn)
            log(
                f"'{self.__repr__(owner_inst=owner)}' {self.role} received {repr(value)}, which"
                f"is not in the valid value list {repr(self.only)}"
            )

        return value

    @util.hide_in_traceback
    def to_pythonic(self, value):
        """Convert a value from an unknown type to self._type."""
        return self._type(value)

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
                f"{repr(self)} type must be '{typename}', not '{valuetypename}'"
            )
        return value

    def contains(self, iterable, value):
        return value in iterable

    # introspection
    def doc(self, as_argument=False, anonymous=False):
        typename = "Any" if self._type is None else self._type.__qualname__

        if self.label:
            typename += f" ({self.label})"

        params = self.doc_params(omit=["help", "default", "label"])
        if as_argument:
            if anonymous:
                doc = f"{self.help}"
            else:
                doc = f"{self.name} ({typename}): {self.help}"

            if len(params) > 0:
                doc += f" (constraints: {params})"

        else:
            # as property
            if anonymous:
                doc = str(self.help)
            else:
                doc = f"{typename}: {self.help}"

            if len(params) > 0:
                doc += f"\n\nConstraints:\n    {params}"
        return doc

    def doc_params(self, omit=["help"]):
        pairs = []

        for name in typing.get_type_hints(self).keys():
            default = getattr(type(self), name)
            v = getattr(self, name)

            # skip uninformative debug info
            if name.startswith("_") or name in omit:
                continue

            # only show non-defaults
            v = getattr(self, name)
            if v is Undefined:
                continue
            elif name not in self._positional and v == default:
                continue

            pairs.append(f"{name}={repr(v)}")

        return ",".join(pairs)

    def __repr__(self, omit=["help"], owner_inst=None):
        declaration = f"{type(self).__module__}.{type(self).__qualname__}({self.doc_params(omit)})"

        if owner_inst is None:
            return declaration
        else:
            return f"<{owner_inst}.{self.name} defined as {declaration}>"

    __str__ = __repr__

    def _owned_name(self, owner):
        if owner._owned_name is None:
            return type(owner).__qualname__ + "." + self.name
        else:
            return owner._owned_name + "." + self.name

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
        obj.__dict__.update(attrs)
        return obj


class Value(ParamAttr[T]):
    role = ParamAttr.ROLE_VALUE
    default: T = field[T](default=Undefined, kw_only=False)
    allow_none: Union[bool, None] = None
    key: Any = None

    def __init__(self, *args, **kws):
        # kw_only is for the type checker only
        kws.pop('kw_only', None)
        super().__init__(*args, **kws)

        if self.allow_none is None:
            if self.default is None:
                self.allow_none = True
            else:
                self.allow_none = False 
        elif self.default is None and not self.allow_none:
            raise TypeError("cannot set default=None with allow_none=True")

    @util.hide_in_traceback
    def __get__(
        self: Value[T],
        owner: HasParamAttrs,
        owner_cls: Union[None, Type[HasParamAttrs]] = None,
    ) -> T:
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
        if owner is None:# or not isinstance(owner, HasParamAttrs):
            # escape an infinite recursion loop before accessing any class members
            return self

        cls_getter = owner_cls.__dict__.get(self.name, None)
        objclass_getter = self.__objclass__.__dict__.get(self.name)
        if cls_getter is not objclass_getter:
            return self
        else:
            return self.get_from_owner(owner)

    @util.hide_in_traceback
    def __set__(self, owner: HasParamAttrs, value: T):
        if isinstance(owner, HasParamAttrs):
            return self.set_in_owner(owner, value)
        else:
            return self

    def get_from_owner(
        self, owner: HasParamAttrs, arguments: typing.Dict[str, Any] = {}
    ) -> T:
        if not self.gets:
            # stop now if this is not a gets ParamAttr
            raise AttributeError(
                f"{self.__repr__(owner_inst=owner)} does not support get operations"
            )

        need_notify = self.name not in owner._attr_store.cache
        value = owner._attr_store.cache.setdefault(self.name, self.default)
        if need_notify:
            owner.__notify__(self.name, value, "get", cache=self.cache)
        return value

    @util.hide_in_traceback
    def set_in_owner(
        self, owner: HasParamAttrs, value: T, arguments: typing.Dict[str, Any] = {}
    ):
        value = self._prepare_set_value(owner, value, arguments)
        owner._attr_store.cache[self.name] = value
        owner.__notify__(self.name, value, "set", cache=self.cache)

    def __init_owner_subclass__(self, owner_cls: Type[HasParamAttrs]):
        pass


# import dataclasses
# dataclasses.dataclass

R = typing.TypeVar('R')
class KeywordArgument(ParamAttr[T]):
    role = ParamAttr.ROLE_ARGUMENT
    name: str = field(kw_only=False)
    default: T = Undefined
    required: bool = False

    # def __init__(self, name, **kws):
    #     super().__init__(**kws)
    #     self.name = name

    def __init_owner_subclass__(self, owner_cls: Type[HasParamAttrs]):
        raise AttributeError(
            "labbench.paramattr.kwarg instances should not be used as class attributes"
        )

    def __set_name__(self, owner_cls, name):
        super().__set_name__(owner_cls, self.name)

    def _owned_name(self, owner):
        return self.__repr__()

    @typing.overload
    def __call__(self, unvalidated_method: TMethod[T]) -> TMethod[T]: ...
    @typing.overload
    def __call__(self, unvalidated_method: typing.Callable[_P,R]) -> typing.Callable[_P,R]: ...
    def __call__(self, unvalidated_method):
        """decorate a method to apply type conversion and validation checks to one of its keyword arguments.

        These are applied to the keyword argument matching `self.name` immediately before each call to
        `invalidated_method`.
        """

        if isinstance(unvalidated_method, Method):
            # apply the decorations to any function(s) decorated by Method
            unvalidated_method._decorated_funcs = [self(func) for func in unvalidated_method._decorated_funcs]
            return unvalidated_method

        if self.default is not Undefined:
            raise TypeError("the default argument is not supported when used as a decorator")

        @wraps(unvalidated_method)
        @util.hide_in_traceback
        def validated_method(
            owner: HasParamAttrs, *args, **kwargs
        ) -> Union[None, self._type]:
            """the autogenerated method that binds the key to an owner and the attribute definition"""

            if self.name in kwargs:
                if not isinstance(owner, HasParamAttrs):
                    raise TypeError(f'labbench.kwarg.argument may only decorate methods of HasParamAttr instances')
                kwargs[self.name] = self._finalize_get_value(owner, kwargs[self.name])
            elif self.required:
                raise TypeError(f'missing required argument {self.name}')

            return unvalidated_method(owner, *args, **kwargs)

        return validated_method


    # def get_funcs_and_arguments(self):
    #     funcs = []
    #     args = [self]
    #     for f in self._decorated_funcs:
    #         if isinstance(f, Argument):
    #             sub_f, sub_args = f.get_argument_decorations()
    #             args += sub_args
    #             funcs += sub_f
    #         elif isinstance(f, Method):
    #             raise ValueError(f"decorated a method with two method decorators")
    #         else:
    #             funcs.append(f)
    #     return funcs, args

    # @util.hide_in_traceback
    # def __get__(
    #     self, owner: HasParamAttrs, owner_cls: Union[None, Type[HasParamAttrs]] = None
    # ):
    #     """Called by the class instance that owns this attribute to
    #     retreive its value. This, in turn, decides whether to call a wrapped
    #     decorator function or the owner's property adapter method to retrieve
    #     the result.

    #     Returns:
    #         retreived value
    #     """

    #     return self


class OwnerAccessAttr(ParamAttr[T], Generic[T, TCall]):
    _setter = None
    _getter = None
    _method = None
    _decorated_funcs = []

    def __init__(self, **kws):
        super().__init__(**kws)
        self._decorated_funcs = []

    @util.hide_in_traceback
    def __call__(self, /, func=Undefined, **kwargs):
        """decorate a class attribute with the ParamAttr"""
        # only decorate functions.
        if not callable(func):
            raise Exception(
                f"object of type '{func.__class__.__qualname__}' must be callable"
            )

        self._decorated_funcs.append(func)

        # Register in the list of decorators, in case we are overwritten by an
        # overloading function
        if getattr(self, "name", None) is None:
            self.name = func.__name__
        else:
            self._keywords = kwargs
        if len(HasParamAttrsMeta.ns_pending) > 0:
            HasParamAttrsMeta.ns_pending[-1][func.__name__] = self

        # return self to ensure `self` is the value assigned in the class definition
        return self

    @util.hide_in_traceback
    def get_from_owner(
        self, owner: HasParamAttrs, arguments: typing.Dict[str, Any] = {}
    ):
        if not self.gets:
            # stop now if this is not a gets ParamAttr
            raise AttributeError(
                f"{self.__repr__(owner_inst=owner)} does not support get operations"
            )

        if self.cache and self.name in owner._attr_store.cache:
            # return the cached value if applicable
            return owner._attr_store.cache[self.name]

        elif self._getter is not None:
            # get value with the decorator implementation, if available
            value = self._getter(owner, **arguments)

        else:
            # otherwise, use the key owner's key adapter, if available
            if self.key is None:
                # otherwise, 'get'
                objname = owner.__class__.__qualname__
                # ownername = self.__repr__(owner_inst=owner)
                raise AttributeError(
                    f"to set the property {self.name}, decorate a method in {objname} or use the function key argument"
                )
            value = get_owner_defs(owner).key_adapter.get(owner, self.key, self, arguments)

        value = self._finalize_get_value(owner, value, strict=False)
        owner.__notify__(
            self.name, value, "get", cache=self.cache or (self.role == self.ROLE_VALUE)
        )
        return value

    @util.hide_in_traceback
    def set_in_owner(
        self, owner: HasParamAttrs, value, arguments: typing.Dict[str, Any] = {}
    ):
        value = self._prepare_set_value(owner, value, arguments)

        # The remaining roles act as function calls that are implemented through self.key
        # or by decorating a function.
        if self._setter is not None:
            # a decorated setter function, if used as a decorator
            self._setter(owner, value, **arguments)

        elif self.key is not None:
            # send to the key adapter
            get_owner_defs(owner).key_adapter.set(owner, self.key, value, self, arguments)

        else:
            objname = owner.__class__.__qualname__ + "." + self.name
            raise AttributeError(
                f"cannot set {objname}: no @{self.__repr__(owner_inst=owner)}."
                f"setter and no key argument"
            )

        owner.__notify__(self.name, value, "set", cache=self.cache)

    def copy(self, new_type=None, **update_kws):
        obj = super().copy(new_type=new_type, **update_kws)
        obj._getter = self._getter
        obj._setter = self._setter
        obj._method = self._method
        return obj

_P = typing.ParamSpec("_P")
TMethod = typing.TypeVar('TMethod', bound='Method')
Tcall = typing.TypeVar('Tcall')

# _M = Callable[_P,T]
# class TWrappedMethod(typing.[TMethod,T]):
#     def __call__(self: TMethod[T], *args: _M.args, **kws: _M.kwargs): ...

# class TKeyedMethod(typing.Protocol[TMethod,T]):
#     @typing.overload
#     def __call__(self: TMethod[T], set_value: T, **arguments) -> None:
#         ...

#     @typing.overload
#     def __call__(self: TMethod[T], **arguments) -> T:
#         ...

#     def __call__(
#         self: TMethod[T], set_value: Optional[T] = Undefined, **arguments
#     ) -> Union[None, T]:
#         ...


# class TDecoratorMethod(typing.Protocol[TMethod,T]):
#     def __call__(self: TMethod[T], func: _M) -> TWrappedMethod[TMethod[T], _M]:
#         ...

@dataclass_transform(kw_only_default=True, eq_default=False)
class _MethodDataClass(OwnerAccessAttr[T]):
    # typing shim to get the callable signature type hints
    @typing.overload
    def __new__(cls, key: typing.Any, **arguments) -> TKeyedMethod[T]:
        ...

    @typing.overload
    def __new__(cls, **arguments) -> TDecorator[T,_P]:
        ...

    __new__ = OwnerAccessAttr.__new__


class Method(_MethodDataClass[T]):
# class Method(_MethodDataClass[T], Generic[T,Tcall]):
    role = ParamAttr.ROLE_METHOD
    key: Any = Undefined

    def get_key_arguments(self, owner_cls, validate=False):
        if self.key is not Undefined:
            return get_owner_defs(owner_cls).key_adapter.get_key_arguments(self.key)

        _, *params = inspect.signature(self._method).parameters.items()

        if self.sets:
            # must support a positional argument unless sets=False
            if len(params) == 0 or not _parameter_maybe_positional(params[0][1]):
                label = f"{owner_cls.__qualname__}.{self.name}"
                raise TypeError(
                    f"{label}: method signature must start with 1 positional argument to support setting (or define with `sets=False`)"
                )
            else:
                value_argument_name, _ = params[0]
                params = params[1:]

        else:
            # otherwise, must *not* support a positional argument if sets=False
            if len(params) > 0 and _parameter_maybe_positional(params[0]):
                label = f"{owner_cls.__qualname__}.{self.name}"
                raise TypeError(
                    f'{label}: no positional arguments allowed when gets=False (indicate keyword arguments by defining "self, * ,")'
                )
            else:
                value_argument_name = None

        params = dict(params)

        if not validate:
            return tuple(params.keys())

        for name, attr_def in params.items():
            if attr_def.kind in (
                inspect.Parameter.VAR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            ):
                label = f"{owner_cls.__qualname__}.{self.name}"
                raise TypeError(
                    f"{label}: keyword arguments must be explicit in ParamAttr methods - variable argument for '{name}' is not supported"
                )

            if _parameter_maybe_positional(attr_def):
                label = f"{owner_cls.__qualname__}{self.name}"
                if value_argument_name is None:
                    suggested = f"(self, *, {name}...)"
                else:
                    suggested = f"(self, {value_argument_name}, *, {name}...)"
                raise TypeError(
                    f'{label}: arguments starting with {name} must be keyword-only. did you mean to include * as in "{suggested}"?'
                )

        return tuple(params.keys())

    def _emit_setattr_error(self, owner, value):
          raise AttributeError(f"to set {self}, call it as a function {self}(...)")

    def __init_owner_instance__(self, owner: HasParamAttrs):
        super().__init_owner_instance__(owner)

        if self.key is Undefined:
            unbound_method = self._decorated_funcs[0]
        else:
            cls_info = get_owner_defs(owner)
            unbound_method = cls_info.key_adapter.method_from_key(type(owner), self)
        bound_method = unbound_method.__get__(owner, type(owner))
        setattr(owner, self.name, bound_method)
        # cls_info.methods[self.name] = cls_info.key_adapter.method_from_key(
        #     owner, self
        # )

        # func = cls_info.methods[self.name]
        # method = func.__get__(owner, type(owner))

        # TODO: inject hooks

        self.__set__ = self._emit_setattr_error

    def __init_owner_subclass__(self, owner_cls: Type[HasParamAttrs]):
        """The owner calls this in each of its ParamAttr attributes at the end of defining the subclass
        (near the end of __init_subclass__). Now it is time to ensure properties are compatible with the
        owner class. This is here --- not in __set_name__ --- because python
        obfuscates exceptions raised in __set_name__.

        This is also where we finalize selecting decorator behavior; is it a property or a method?
        """

        positional_argcounts = [
            f.__code__.co_argcount - len(f.__defaults__ or tuple())
            for f in self._decorated_funcs
        ]

        if self.key is Undefined:
            if len(self._decorated_funcs) == 0:
                if self.key is Undefined:
                    raise AttributeError(
                        f'{self} must be defined with "key" keyword unless used as a decorator'
                    )
            elif len(self._decorated_funcs) == 1:
                pass
            else:
                raise AttributeError(f"{self} may not decorate more than one method")

            for func, argcount in zip(self._decorated_funcs, positional_argcounts):
                if len(self.help.rstrip().strip()) == 0:
                    # take func docstring as default self.help
                    self.help = (func.__doc__ or "").rstrip().strip()

                self._method = func

            # validate the key arguments
            self.get_key_arguments(owner_cls, validate=True)

    def __call__(self, unvalidated_method):
        @wraps(unvalidated_method)
        def method(
            owner, set_value: self._type = Undefined, **arguments
        ) -> Union[None, self._type]:
            """the autogenerated method that binds the key to an owner and the attribute definition"""

            if set_value is not Undefined:
                set_value = self._prepare_set_value(owner, set_value)

            return unvalidated_method(owner, set_value, **arguments)

        self._decorated_funcs.append(method)
        return self

    # @util.hide_in_traceback
    # def __get__(
    #     self, owner: Union[None, HasParamAttrs], owner_cls: Type[HasParamAttrs] = None
    # ) -> TKeyedMethodCallable[T]:
    #     """Called by the class instance that owns this attribute to
    #     retreive its value. This, in turn, decides whether to call a wrapped
    #     decorator function or the owner's property adapter method to retrieve
    #     the result.

    #     Returns:
    #         retreived value
    #     """

    #     # only continue to get the value if the __get__ was called for an owning
    #     # instance, and owning class is a match for what we were told in __set_name__.
    #     # otherwise, someone else is trying to access `self` and we
    #     # shouldn't get in their way.
    #     if owner is None:
    #         # escape an infinite recursion loop before accessing any class members
    #         return self

    #     cls_getter = owner_cls.__dict__.get(self.name, None)
    #     objclass_getter = self.__objclass__.__dict__.get(self.name)
    #     if cls_getter is not objclass_getter:
    #         return self

    #     else:
    #         # inject the labbench ParamAttr hooks into the return value
    #         func = get_owner_defs(owner_cls).methods[self.name]
    #         method = func.__get__(owner, owner_cls)

    #         # TODO: inject hooks

    #         # @wraps(method)
    #         # def method(*args, **kws):
    #         #     value = func.__get__(owner, owner_cls)(*args, **kws)
    #         #     return self.__cast_get__(owner, value)

    #         return method

    # def __set__(self, owner: HasParamAttrs, value):
    #     obj = getattr(owner, self.name)
    #     if hasattr(obj, '__self__'):
    #         # raise the error if this is already a bound method
    #         raise AttributeError(f"call {self}(...) to set parameter value, not assignment")
    #     else:
    #         # otherwise, allow the set in order to bind the method
    #         object.__setattr__(owner, self.name, value)

class TDecoratedMethod(Method[T], Generic[T,_P]):
    def __call__(self, *args: _P.args, **arguments: _P.kwargs) -> Union[T,None]:
        ...

class TKeyedMethod(Method[T]):
    @typing.overload
    def __call__(self, /, set_value: T, **arguments) -> None:
        ...

    @typing.overload
    def __call__(self, **arguments) -> T:
        ...

class TDecorator(Method[T]):
    def __call__(self, func: typing.Callable[_P,typing.Union[None,T]]) -> TDecoratedMethod[T,_P]:
        ...


class Property(OwnerAccessAttr[T]):
    role = ParamAttr.ROLE_PROPERTY
    key: Any = Undefined

    def __init_owner_subclass__(self, owner_cls: Type[HasParamAttrs]):
        """The owner calls this in each of its ParamAttr attributes at the end of defining the subclass
        (near the end of __init_subclass__). Now it is time to ensure properties are compatible with the
        owner class. This is here --- not in __set_name__ --- because python
        obfuscates exceptions raised in __set_name__.

        This is also where we finalize selecting decorator behavior; is it a property or a method?
        """

        if len(self._decorated_funcs) == 0:
            return

        positional_argcounts = [
            f.__code__.co_argcount - len(f.__defaults__ or tuple())
            for f in self._decorated_funcs
        ]

        if set(positional_argcounts) not in ({1}, {1, 2}, {2}):
            raise AttributeError(
                f"a decorator implementation with @{self} must apply to a getter "
                f"(above `def func(self)`) and/or setter (above `def func(self, value):`)"
            )
        for func, argcount in zip(self._decorated_funcs, positional_argcounts):
            doc = (func.__doc__ or "").strip().rstrip()
            if len(doc) > 0:
                # take func docstring as default self.help
                self.help = self.kws["help"] = doc

            if argcount == 1:
                self._getter = func
            else:
                self._setter = func

    @util.hide_in_traceback
    def __get__(
        self: Property[T],
        owner: HasParamAttrs,
        owner_cls: Union[None, Type[HasParamAttrs]] = None,
    ) -> T:
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

        cls_getter = owner_cls.__dict__.get(self.name, None)
        objclass_getter = self.__objclass__.__dict__.get(self.name)
        if cls_getter is not objclass_getter:
            return self
        else:
            return self.get_from_owner(owner)

    @util.hide_in_traceback
    def __set__(self, owner: HasParamAttrs, value):
        return self.set_in_owner(owner, value)


@contextmanager
def hold_attr_notifications(owner):
    def skip_notify(name, value, type, cache):
        # old = owner._attr_store.cache.setdefault(name, Undefined)
        # msg = dict(new=value, old=old, owner=owner, name=name, type=type, cache=cache)

        owner._attr_store.cache[name] = value

    original, owner.__notify__ = owner.__notify__, skip_notify
    yield
    owner.__notify__ = original


class HasParamAttrsInstInfo:
    handlers: typing.Dict[str, Callable]
    calibrations: typing.Dict[str, Any]
    cache: typing.Dict[str, Any]

    __slots__ = "handlers", "calibrations", "cache"

    def __init__(self, owner: HasParamAttrs):
        self.handlers = {}
        self.cache = {}
        self.calibrations = {}

def get_key_adapter(obj: Union[HasParamAttrs, Type[HasParamAttrs]]) -> KeyAdapterBase:
    return obj._attr_defs.key_adapter


def list_value_attrs(
    obj: Union[HasParamAttrs, Type[HasParamAttrs]]
) -> typing.List[str]:
    """returns a mapping of names of labbench value paramattrs defined in `obj`"""
    return get_owner_defs(obj).value_names()


def list_method_attrs(
    obj: Union[HasParamAttrs, Type[HasParamAttrs]]
) -> typing.List[str]:
    """returns a mapping of names of labbench method paramattrs defined in `obj`"""
    return get_owner_defs(obj).method_names()


def list_property_attrs(
    obj: Union[HasParamAttrs, Type[HasParamAttrs]]
) -> typing.List[str]:
    """returns a list of names of labbench property paramattrs defined in `obj`"""
    return get_owner_defs(obj).property_names()


class HasParamAttrs(metaclass=HasParamAttrsMeta):
    def __init__(self, **values):
        self._attr_store = HasParamAttrsInstInfo(self)
        for name, attr in get_class_attrs(self).items():
            attr.__init_owner_instance__(self)

    @util.hide_in_traceback
    def __init_subclass__(cls):
        MANAGED_ROLES = ParamAttr.ROLE_PROPERTY, ParamAttr.ROLE_METHOD

        attr_defs = get_class_attrs(cls)

        for name, attr_def in dict(attr_defs).items():
            # Apply the decorator to the object if it is "part 2" of a decorator
            obj = getattr(cls, name)

            if not isinstance(obj, ParamAttr):
                if attr_def.role in MANAGED_ROLES and callable(obj):
                    # if it's a method, decorate it
                    attr_defs[name] = attr_def(obj)
                else:
                    # if not decorating, clear from the attrs dict, and emit a warning at runtime
                    thisclsname = cls.__qualname__
                    parentclsname = cls.__mro__[1].__qualname__
                    warn(
                        f"'{name}' in {thisclsname} is not a ParamAttr instance, but replaces one in parent class {parentclsname}"
                    )
                    attr_defs.attrs[name]

                    continue

            setattr(cls, name, attr_defs[name])

        # clear the initialized attributes from the pending entries in the metaclass
        if attr_defs in type(cls).ns_pending:
            type(cls).ns_pending.remove(attr_defs)

        # finalize attribute setup
        for name, attr_def in dict(attr_defs).items():
            if not hasattr(attr_def, "__objclass__"):
                attr_def.__set_name__(cls, name)
            attr_def.__init_owner_subclass__(cls)

    @util.hide_in_traceback
    def __notify__(self, name, value, type, cache):
        old = self._attr_store.cache.setdefault(name, Undefined)

        msg = dict(new=value, old=old, owner=self, name=name, type=type, cache=cache)

        for handler in self._attr_store.handlers.values():
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
        pass


def adjusted(
    paramattr: Union[ParamAttr, str], default: Any = Undefined, /, **kws
) -> Callable[[Type[T]], Type[T]]:
    """decorates a Device subclass to copy the specified ParamAttr with a specified name.

    This can be applied to inherited classes that need one of its parents attributes
    with an adjusted definition. Multiple decorators can be stacked to the
    same class definition.

    Args:
        paramattr: ParamAttr instance or name of the attribute to adjust in the wrapped class
        default: new default value (for value attributes only)

    Raises:
        ValueError: invalid type of ParamAttr argument, or when d
        TypeError: _description_
        ValueError: _description_

    Returns:
        HasParamAttrs or Device with adjusted attributes value
    """
    if isinstance(paramattr, ParamAttr):
        name = paramattr.name
    elif isinstance(paramattr, builtins.str):
        name = paramattr
    else:
        raise ValueError("expected ParamAttr or str instance for `paramattr` argument")

    def apply_adjusted_paramattr(owner_cls: HasParamAttrs):
        if not issubclass(owner_cls, HasParamAttrs):
            raise TypeError("adopt must decorate a Device class definition")
        if name not in owner_cls.__dict__:
            raise ValueError(f'no ParamAttr "{name}" in {repr(owner_cls)}')

        attr = getattr(owner_cls, name)
        attr.update(**kws)
        # owner_cls.__update_signature__()
        return owner_cls

    return apply_adjusted_paramattr


THasParamAttrsCls = Type[typing.TypeVar('THasParamAttrs', bound=HasParamAttrs)]
def register_key_argument(
    kwarg_def: KeywordArgument
) -> Callable[[THasParamAttrsCls], THasParamAttrsCls]:
    """decorates a Device subclass to copy the specified ParamAttr with a specified name.

    This can be applied to inherited classes that need one of its parents attributes
    with an adjusted definition. Multiple decorators can be stacked to the
    same class definition.

    Args:
        paramattr: ParamAttr instance or name of the attribute to adjust in the wrapped class
        default: new default value (for value attributes only)

    Raises:
        ValueError: invalid type of ParamAttr argument, or when d
        TypeError: _description_
        ValueError: _description_

    Returns:
        HasParamAttrs or Device with adjusted attributes value
    """

    def adjust_owner(owner_cls: THasParamAttrsCls) -> THasParamAttrsCls:
        cls_info = get_owner_defs(owner_cls)
        cls_info.key_adapter = cls_info.key_adapter.copy({kwarg_def.name: kwarg_def})
        return owner_cls

    return adjust_owner


def observe(obj, handler, name=Undefined, type_=("get", "set")):
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
            raise TypeError(f"cannot observe {obj}.{n} because it is not a attribute")

    if not callable(handler):
        raise ValueError(
            f"argument 'handler' is {repr(handler)}, which is not a callable"
        )

    if isinstance(name, str):
        validate_name(name)
        name = (name,)
    elif isinstance(name, (tuple, list)):
        for n in name:
            validate_name(n)
    elif name is not Undefined:
        raise ValueError(
            f"name argument {name} has invalid type - must be one of (str, tuple, list), or the value Undefined"
        )

    if isinstance(type, str):
        type_ = (type_,)

    def wrapped(msg):
        # filter according to name and type
        if name is not Undefined and msg["name"] not in name:
            return
        elif msg["type"] not in type_:
            return
        elif isinstance(msg["new"], ParamAttr):
            raise TypeError("ParamAttr instance returned as a callback value")
        handler(msg)

    if isinstance(obj, HasParamAttrs):
        obj._attr_store.handlers[handler] = wrapped
    else:
        raise TypeError("object to observe must be an instance of Device")


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
            raise ValueError(f"{handler} was not registered to observe {obj}")
    else:
        raise TypeError("object to unobserve must be an instance of Device")


def find_paramattr_in_mro(cls):
    if issubclass(cls, DependentParamAttr):
        return find_paramattr_in_mro(type(cls._paramattr_dependencies["base"]))
    else:
        return cls


class DependentParamAttr(ParamAttr):
    _paramattr_dependencies = set()

    def __set_name__(self, owner_cls, name):
        super().__set_name__(owner_cls, name)

        # propagate ownership of dependent ParamAttr instances, if available
        if isinstance(owner_cls, HasParamAttrs):
            objclass = owner_cls
        elif hasattr(self, "__objclass__"):
            objclass = self.__objclass__
        else:
            return

        for attr_def in self._paramattr_dependencies.values():
            attr_def.__objclass__ = objclass

    def _validate_attr_dependencies(self, owner, allow_none: bool, operation="access"):
        if allow_none:
            return

        none_names = [
            f"{owner}.{attr.name}"
            for attr in self._paramattr_dependencies.values()
            if getattr(owner, attr.name) is None
        ]

        if len(none_names) == 1:
            raise ValueError(
                f"cannot {operation} {owner}.{self.name} while {none_names[0]} is None"
            )
        elif len(none_names) > 1:
            raise ValueError(
                f"cannot {operation} {owner}.{self.name} while {tuple(none_names)} are None"
            )

    @classmethod
    def derive(
        mixin_cls, template_attr: ParamAttr, dependent_attrs={}, *init_args, **init_kws
    ):
        name = template_attr.__class__.__name__
        name = ("" if name.startswith("dependent_") else "dependent_") + name

        dependent_attrs["base"] = template_attr

        attrs_dict = {}

        for c in mixin_cls.__mro__:
            if issubclass(c, DependentParamAttr):
                attrs_dict.update(c._paramattr_dependencies)

        attrs_dict.update(dependent_attrs)

        ns = dict(_paramattr_dependencies=attrs_dict, **dependent_attrs)

        ttype = type(name, (mixin_cls, find_paramattr_in_mro(type(template_attr))), ns)

        obj = ttype(*init_args, **init_kws)
        return obj


class RemappingCorrectionMixIn(DependentParamAttr):
    """act as another BoundedNumber ParamAttr, calibrated with a mapping"""

    mapping: Any = None  # really a pandas Series

    EMPTY_STORE = dict(by_cal=None, by_uncal=None)

    def _min(self, owner: HasParamAttrs):
        by_uncal = owner._attr_store.calibrations.get(self.name, {}).get(
            "by_uncal", None
        )
        if by_uncal is None:
            return None
        else:
            return by_uncal.min()

    def _max(self, owner: HasParamAttrs):
        by_uncal = owner._attr_store.calibrations.get(self.name, {}).get(
            "by_uncal", None
        )
        if by_uncal is None:
            return None
        else:
            return by_uncal.max()

    def __init_owner_instance__(self, owner: HasParamAttrs):
        self.set_mapping(self.mapping, owner=owner)
        observe(
            owner,
            self._on_base_paramattr_change,
            name=self._paramattr_dependencies["base"].name,
        )

    def _on_base_paramattr_change(self, msg):
        owner = msg["owner"]
        owner.__notify__(
            self.name,
            self.lookup_cal(msg["new"], owner),
            msg["type"],
            cache=msg["cache"],
        )

    def lookup_cal(self, uncal, owner):
        """look up and return the calibrated value, given the uncalibrated value"""
        owner_cal = owner._attr_store.calibrations.get(self.name, self.EMPTY_STORE)
        if owner_cal.get("by_uncal", None) is None:
            return None

        try:
            return owner_cal["by_uncal"].loc[uncal]
        except KeyError:
            # spare us pandas details in the traceback
            util.logger.warning(
                f"{self.__repr__(owner_inst=owner)} has no entry at {repr(uncal)} {self.label}"
            )

        return None

    def find_uncal(self, cal, owner):
        """look up the calibrated value for the given uncalibrated value. In the event of a lookup
        error, then if `self.allow_none` evaluates as True, triggers return of None, or if
         `self.allow_none` evaluates False, ValueError is raised.
        """
        owner_cal = owner._attr_store.calibrations.get(self.name, self.EMPTY_STORE)

        if owner_cal["by_uncal"] is None:
            return None

        i = owner_cal["by_cal"].index.get_indexer([cal], method="nearest")[0]
        return owner_cal["by_cal"].iloc[i]

    def set_mapping(self, series_or_uncal, cal=None, owner=None):
        """set the lookup mapping as `set_mapping(series)`, where `series` is a pandas Series (uncalibrated
        values in the index), or `set_mapping(cal_vector, uncal_vector)`, where both vectors have 1
        dimension of the same length.
        """

        if owner is None:
            raise ValueError("must pass owner to set_mapping")

        if isinstance(series_or_uncal, pd.Series):
            by_uncal = pd.Series(series_or_uncal).copy()
        elif cal is not None:
            by_uncal = pd.Series(cal, index=series_or_uncal)
        elif series_or_uncal is None:
            return
        else:
            raise ValueError(
                f"must call set_mapping with None, a Series, or a pair of vector "
                f"arguments, not {series_or_uncal}"
            )
        by_uncal = by_uncal[~by_uncal.index.duplicated(keep="first")].sort_index()
        by_uncal.index.name = "uncal"
        by_uncal.name = "cal"

        by_cal = pd.Series(by_uncal.index, index=by_uncal.values, name="uncal")
        by_cal = by_cal[~by_cal.index.duplicated(keep="first")].sort_index()
        by_cal.index.name = "cal"

        (
            owner._attr_store.calibrations
            .setdefault(self.name, {})
            .update(by_cal=by_cal, by_uncal=by_uncal)
        )

    @util.hide_in_traceback
    def get_from_owner(
        self, owner: HasParamAttrs, arguments: typing.Dict[str, Any] = {}
    ):
        # by_cal, by_uncal = owner._attr_store.calibrations.get(self.name, (None, None))
        self._validate_attr_dependencies(owner, self.allow_none, "get")

        uncal = self._paramattr_dependencies["base"].get_from_owner(owner, arguments)

        cal = self.lookup_cal(uncal, owner)

        if cal is None:
            ret = uncal
        else:
            ret = cal

        if hasattr(self, "name"):
            owner.__notify__(
                self.name,
                ret,
                "get",
                cache=self.cache or (self.role == self.ROLE_VALUE),
            )

        return ret

    @util.hide_in_traceback
    def set_in_owner(
        self, owner: HasParamAttrs, cal_value, arguments: typing.Dict[str, Any] = {}
    ):
        # owner_cal = owner._attr_store.calibrations.get(self.name, self.EMPTY_STORE)
        self._validate_attr_dependencies(owner, False, "set")

        # start with type conversion and validation on the requested calibrated value
        cal_value = self._paramattr_dependencies["base"].to_pythonic(cal_value)

        # lookup the uncalibrated value that results in the nearest calibrated result
        uncal_value = self.find_uncal(cal_value, owner)
        base = self._paramattr_dependencies["base"]

        if uncal_value is None:
            base.set_in_owner(owner, cal_value, arguments)
        elif uncal_value != type(base).validate(self, uncal_value, owner):
            # raise an exception if the calibration table contains invalid
            # values, instead
            raise ValueError(
                f"calibration lookup in {self.__repr__(owner_inst=owner)} produced invalid value {repr(uncal_value)}"
            )
        else:
            # execute the set
            self._paramattr_dependencies["base"].set_in_owner(
                owner, uncal_value, arguments
            )

        if hasattr(self, "name"):
            owner.__notify__(
                self.name,
                cal_value,
                "set",
                cache=self.cache or (self.role == self.ROLE_VALUE),
            )


class TableCorrectionMixIn(RemappingCorrectionMixIn):
    _CAL_TABLE_KEY = "table"

    path_attr: ParamAttr = None  # a dependent Unicode ParamAttr
    index_lookup_attr: ParamAttr = None  # a dependent ParamAttr
    table_index_column: str = None

    def __init_owner_instance__(self, owner):
        super().__init_owner_instance__(owner)

        observe(
            owner,
            self._on_cal_update_event,
            name=[self.path_attr.name, self.index_lookup_attr.name],
            type_="set",
        )

    def _on_cal_update_event(self, msg):
        owner = msg["owner"]

        if msg["name"] == self.path_attr.name:
            # if msg['new'] == msg['old']:
            #     return

            path = msg["new"]
            index = getattr(owner, self.index_lookup_attr.name)

            ret = self._load_calibration_table(owner, path)
            self._update_index_value(owner, index)

            return ret

        elif msg["name"] == self.index_lookup_attr.name:
            # if msg['new'] == msg['old']:
            #     return
            path = getattr(owner, self.path_attr.name)
            index = msg["new"]

            if self._CAL_TABLE_KEY not in owner._attr_store.calibrations.get(
                self.name, {}
            ):
                self._load_calibration_table(owner, path)

            ret = self._update_index_value(owner, index)

            return ret

        else:
            raise KeyError(f"unsupported parameter attribute name {msg['name']}")

        # return self._update_index_value(msg["owner"], msg["new"])

    def _load_calibration_table(self, owner, path):
        """stash the calibration table from disk"""

        def read(path):
            # quick read
            cal = pd.read_csv(str(path), index_col=self.table_index_column, dtype=float)

            cal.columns = cal.columns.astype(float)
            if self.index_lookup_attr.max in cal.index:
                cal.drop(self.index_lookup_attr.max, axis=0, inplace=True)
            #    self._cal_offset.values[:] = self._cal_offset.values-self._cal_offset.columns.values[np.newaxis,:]

            owner._attr_store.calibrations.setdefault(self.name, {}).update(
                {self._CAL_TABLE_KEY: cal}
            )

            owner._logger.debug(f'calibration data read from "{path}"')

        if path is None:
            if not self.allow_none:
                raise ValueError(
                    f"{self} defined w.cacith allow_none=False; path_attr must not be None"
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
            txt = "index_value change has no effect because calibration_data has not been set"
        elif index_value is None:
            cal = None
            txt = "set {owner}.{self.index_lookup_attr.name} to enable calibration"
        else:
            # pull in the calibration mapping specific to this index_value
            # i_freq = cal.index.get_loc(index_value, "nearest")
            i_freq = cal.index.get_indexer([index_value], method="nearest")[0]
            cal = cal.iloc[i_freq]
            txt = f"calibrated to {index_value} {self.label}"
        owner._logger.debug(txt)

        self.set_mapping(cal, owner=owner)

    @util.hide_in_traceback
    def get_from_owner(
        self, owner: HasParamAttrs, arguments: typing.Dict[str, Any] = {}
    ):
        self._touch_table(owner)
        return super().get_from_owner(owner, arguments)

    @util.hide_in_traceback
    def set_in_owner(
        self, owner: HasParamAttrs, cal_value, arguments: typing.Dict[str, Any] = {}
    ):
        self._touch_table(owner)
        super().set_in_owner(owner, cal_value, arguments)


class TransformMixIn(DependentParamAttr):
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
        base_attr = self._paramattr_dependencies["base"]

        if msg["name"] != getattr(base_attr, "name", None) or not hasattr(
            base_attr, "__objclass__"
        ):
            return

        owner = msg["owner"]
        owner.__notify__(self.name, msg["new"], msg["type"], cache=msg["cache"])

    def _transformed_extrema(self, owner):
        base_attr = self._paramattr_dependencies["base"]
        base_bounds = [base_attr._min(owner), base_attr._max(owner)]

        other_attr = self._paramattr_dependencies.get("other", None)

        if other_attr is None:
            trial_bounds = [
                self._forward(base_bounds[0]),
                self._forward(base_bounds[1]),
            ]
        else:
            other_value = getattr(owner, other_attr.name)
            # other_bounds = [
            #     other_attr._min(owner),
            #     other_attr._max(owner),
            # ]

            # trial_bounds = [
            #     self._forward(base_bounds[0], other_bounds[0]),
            #     self._forward(base_bounds[0], other_bounds[1]),
            #     self._forward(base_bounds[1], other_bounds[0]),
            #     self._forward(base_bounds[1], other_bounds[1]),
            # ]
            trial_bounds = [
                self._forward(base_bounds[0], other_value),
                self._forward(base_bounds[1], other_value),
            ]

        if None in trial_bounds:
            return None, None

        return min(trial_bounds), max(trial_bounds)

    def _min(self, owner):
        # TODO: ensure this works properly for any reversible self._forward()?
        lo, hi = self._transformed_extrema(owner)

        if lo is None:
            return None
        else:
            return min(lo, hi)

    def _max(self, owner):
        # TODO: ensure this works properly for any reversible self._forward()?
        lo, hi = self._transformed_extrema(owner)

        if hi is None:
            return None
        else:
            return max(lo, hi)

    def get_from_owner(
        self, owner: HasParamAttrs, arguments: typing.Dict[str, Any] = {}
    ):
        base_value = self._paramattr_dependencies["base"].get_from_owner(
            owner, arguments
        )

        if "other" in self._paramattr_dependencies:
            other_value = self._paramattr_dependencies["other"].get_from_owner(
                owner, arguments
            )
            ret = self._forward(base_value, other_value)
        else:
            ret = self._forward(base_value)

        if hasattr(self, "name"):
            owner.__notify__(
                self.name,
                ret,
                "get",
                cache=self.cache or (self.role == self.ROLE_VALUE),
            )

        return ret

    def __set__(self, owner, value_request):
        # use the other to the value into the proper format and validate it
        base_attr = self._paramattr_dependencies["base"]
        value = base_attr.to_pythonic(value_request)

        # now reverse the transformation
        if "other" in self._paramattr_dependencies:
            other_attr = self._paramattr_dependencies["other"]
            other_value = other_attr.__get__(owner, other_attr.__objclass__)

            base_value = self._reverse(value, other_value)
        else:
            base_value = self._reverse(value)

        # set the value of the base attr with the reverse-transformed value
        base_attr.__set__(owner, base_value)

        if hasattr(self, "name"):
            owner.__notify__(
                self.name,
                value,
                "set",
                cache=self.cache or (self.role == self.ROLE_VALUE),
            )


class BoundedNumber(ParamAttr[T]):
    """accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking)"""

    min: Union[T,None] = None
    max: Union[T,None] = None

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if not isinstance(value, (bytes, str, bool, numbers.Number)):
            raise ValueError(
                f"a '{type(self).__qualname__}' attribute supports only numerical, str, or bytes types"
            )

        # Check bounds once it's a numerical type
        min = self._min(owner)
        max = self._max(owner)

        if max is not None and value > max:
            raise ValueError(
                f"{value} is greater than the max limit {max} of {self._owned_name(owner)}"
            )
        if min is not None and value < min:
            raise ValueError(
                f"{value} is less than the min limit {min} of {self._owned_name(owner)}"
            )

        return value

    def _max(self, owner):
        """overload this to dynamically compute max"""
        return self.max

    def _min(self, owner):
        """overload this to dynamically compute max"""
        return self.min

    path_attr = None  # TODO: should be a Unicode string attribute

    index_lookup_attr = (
        None  # TODO: this attribute should almost certainly be a BoundedNumber?
    )

    table_index_column = None

    def calibrate_from_table(
        self,
        path_attr: ParamAttr,
        index_lookup_attr: ParamAttr,
        *,
        table_index_column: str = None,
        help="",
        label=Undefined,
        allow_none=False,
    ):
        """generate a new ParamAttr with value dependent on another attribute. their configuration
        comes from a attribute in the owner.

        Arguments:
            offset_name: the name of a value attribute in the owner containing a numerical offset
            lookup1d: a table containing calibration data, or None to configure later
        """

        if label is Undefined:
            label = self.label

        ret = TableCorrectionMixIn.derive(
            self,
            dict(
                path_attr=path_attr,
                index_lookup_attr=index_lookup_attr,
            ),
            help=help,
            label=self.label if label is Undefined else label,
            sets=self.sets,
            gets=self.gets,
            allow_none=allow_none,
            table_index_column=table_index_column,
        )

        return ret

    def calibrate_from_expression(
        self,
        attr_expression: ParamAttr,
        help: str = "",
        label: str = Undefined,
        allow_none: bool = False,
    ):
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
        if isinstance(self, DependentParamAttr):
            # This a little unsatisfying, but the alternative would mean
            # solving the attr_expression for `self`
            obj = attr_expression
            while isinstance(obj, DependentParamAttr):
                obj = obj._paramattr_dependencies["base"]
                if obj == self:
                    break
            else:
                raise TypeError(
                    "calibration target attribute definition must first in the calibration expression"
                )

        return self.update(
            attr_expression, help=help, label=label, allow_none=allow_none
        )

    def transform(
        self,
        other_attr: ParamAttr,
        forward: callable,
        reverse: callable,
        help="",
        allow_none=False,
    ):
        """generate a new attribute subclass that adjusts values in other attributes.

        Arguments:
            forward: implementation of the forward transformation
            reverse: implementation of the reverse transformation
        """

        obj = TransformMixIn.derive(
            self,
            dependent_attrs={} if other_attr is None else dict(other=other_attr),
            help=help,
            label=self.label,
            sets=self.sets,
            gets=self.gets,
            allow_none=allow_none,
            _forward=forward,
            _reverse=reverse,
        )

        return obj

    def __neg__(self):
        def neg(x, y=None):
            return None if x is None else -x

        return self.transform(
            None, neg, neg, allow_none=self.allow_none, help=f"-1*({self.help})"
        )

    def __add__(self, other):
        def add(x, y):
            return None if None in (x, y) else x + y

        def sub(x, y):
            return None if None in (x, y) else x - y

        return self.transform(
            other, add, sub, allow_none=self.allow_none, help=f"({self.help}) + {other}"
        )

    __radd__ = __add__

    def __sub__(self, other):
        def add(x, y):
            return None if None in (x, y) else x + y

        def sub(x, y):
            return None if None in (x, y) else x - y

        return self.transform(
            other, sub, add, allow_none=self.allow_none, help=f"({self.help}) + {other}"
        )

    def __rsub__(self, other):
        def add(x, y):
            return None if None in (x, y) else y + x

        def sub(x, y):
            return None if None in (x, y) else y - x

        return self.transform(
            other, sub, add, allow_none=self.allow_none, help=f"({self.help}) + {other}"
        )

    def __mul__(self, other):
        def mul(x, y):
            return None if None in (x, y) else x * y

        def div(x, y):
            return None if None in (x, y) else x / y

        return self.transform(
            other, mul, div, allow_none=self.allow_none, help=f"({self.help}) + {other}"
        )

    __rmul__ = __mul__

    def __truediv__(self, other):
        def mul(x, y):
            return None if None in (x, y) else x * y

        def div(x, y):
            return None if None in (x, y) else x / y

        return self.transform(
            other, div, mul, allow_none=self.allow_none, help=f"({self.help}) + {other}"
        )

    def __rdiv__(self, other):
        def mul(x, y):
            return None if None in (x, y) else y * x

        def div(x, y):
            return None if None in (x, y) else y / x

        return self.transform(
            other, div, mul, allow_none=self.allow_none, help=f"({self.help}) + {other}"
        )


class NonScalar(Any):
    """generically non-scalar data, such as a list, array, but not including a string or bytes"""

    @util.hide_in_traceback
    def validate(self, value, owner=None):
        if isinstance(value, (bytes, str)):
            raise ValueError("given text data but expected a non-scalar data")
        if not hasattr(value, "__iter__") and not hasattr(value, "__len__"):
            raise ValueError("expected non-scalar data but given a non-iterable")
        return value
