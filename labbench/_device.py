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

from . import util as util

from typing import Generic, T
from warnings import warn, simplefilter
from functools import wraps

import logging
import numbers
import re
import sys
import traceback

__all__ = ['Trait', 'Undefined', 'Any', 'Int', 'Float', 'Unicode', 'Complex', 'Bytes',
           'Bool', 'List', 'Dict', 'Address', 'NonScalar',

           'Device', 'list_devices',
           'observe', 'unobserve'
           ]


class LabbenchDeprecationWarning(DeprecationWarning):
    pass


simplefilter('once', LabbenchDeprecationWarning)

Undefined = type(None)


class ThisType(Generic[T]):
    pass


def trace_methods(cls, name, until_cls=None):
    """ Look for a method called `name` in cls and all of its parent classes.
    """
    methods = []
    last_method = None

    for cls in cls.__mro__:
        try:
            this_method = getattr(cls, name)
        except AttributeError:
            continue
        if this_method != last_method:
            methods.append(this_method)
            last_method = this_method
        if cls is until_cls:
            break

    return methods


def trim(docstring):
    if not docstring:
        return ''
    # Convert tabs to spaces (following the normal Python rules)
    # and split into a list of lines:
    lines = docstring.expandtabs().splitlines()
    # Determine minimum indentation (first line doesn't count):
    indent = sys.maxsize
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            indent = min(indent, len(line) - len(stripped))
    # Remove indentation (first line is special):
    trimmed = [lines[0].strip()]
    if indent < sys.maxsize:
        for line in lines[1:]:
            trimmed.append(line[indent:].rstrip())
    # Strip off trailing and leading blank lines:
    while trimmed and not trimmed[-1]:
        trimmed.pop()
    while trimmed and not trimmed[0]:
        trimmed.pop(0)
    # Return a single string:
    return '\n'.join(trimmed)


def list_devices(depth=1):
    """ Look for Device instances, and their names, in the calling
        code context (depth == 1) or its callers (if depth in (2,3,...)).
        Checks locals() in that context first.
        If no Device instances are found there, search the first
        argument of the first function argument, in case this is
        a method in a class.
    """
    from inspect import getouterframes, currentframe
    from sortedcontainers import sorteddict

    f = frame = currentframe()
    for i in range(depth):
        f = f.f_back
    try:
        ret = sorteddict.SortedDict()
        for k, v in list(f.frame.f_locals.items()):
            if isinstance(v, Device):
                ret[k] = v

        # If the context is a function, look in its first argument,
        # in case it is a method. Search its class instance.
        if len(ret) == 0 and len(f.frame.f_code.co_varnames) > 0:
            obj = f.frame.f_locals[f.frame.f_code.co_varnames[0]]
            for k, v in obj.__dict__.items():
                if isinstance(v, Device):
                    ret[k] = v
    finally:
        del f, frame

    return ret


@util.hide_in_traceback
def __init__():
    """ Wrapper function to call __init__ with adjusted function signature
    """

    # The signature has been dynamically replaced and is unknown. Pull it in
    # via locals() instead. We assume we're inside a __init__(self, ...) call.
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))
    self.__init___wrapped(**items)


class HasTraitsMeta(type):
    __pending__ = []

    @classmethod
    def __prepare__(cls, names, bases):
        """ Prepare copies of cls.__traits__, to ensure that any traits defined
            in the definition don't clobber parents' traits.
        """
        ns = dict()
        if len(bases) >= 1:
            if hasattr(bases, '__children__'):
                ns['__children__'] = {}
            traits = {k: v.copy() for k, v in bases[0].__traits__.items()}
            ns.update(traits)
            ns['__traits__'] = traits
            HasTraitsMeta.__pending__.append(traits)
            return ns
        else:
            HasTraitsMeta.__pending__.append({})
            return dict(__traits__=HasTraitsMeta.__pending__[-1])


class Trait:
    """ This type of Trait is a swiss army knife object for typing checking,
        casting, decorators, and callbacks in Device classes. Together, these
        help reduce code errors that result from "copy and paste" boilerplate,
        and help to clarify the intent of the code.

        A Device instance supports two types of Traits:

        * A _setting trait_ just performs type checking and notifies callback functions
          for locally-cached variables.

        * A _state trait_ triggers set and get operations that are implemented by the
          owning class. Implement the get and set operations in the owning class;
          hook them to this trait by decorating with this trait, or through
          __get_by_key__ and __set_by_key__ in the owning class.

        The trait behavior is determined by whether its owner is a Device or HasSettings
        instance.

        :param default: the default value of the trait (settings only)

        :param key: some types of Device use of this key to automate interaction with the device (state traits only)

        :param help: the Trait docstring

        :param help: a label for the quantity, such as units

        :param settable: True if the trait supports writes

        :param gettable: True if the trait supports reads

        :param cache: if True, interact with the device only once, then return copies (state traits only)

        :param only: a whitelist of valid values; setting others raise ValueError

        :param allow_none: permit None values in addition to the specified type

        :param remap: a lookup table that maps the python type (keys) to a potentially different backend values (values) ,
                      in places of the to_pythonic and from_pythonic methods (states only)

    """
    type = None

    # These annotations define the arguments to __init__ @dataclass above
    default: ThisType = None
    key: None.__class__ = None
    help: str = ''
    label: str = ''
    settable: bool = True
    gettable: bool = True
    cache: bool = False
    only: tuple = tuple()
    allow_none: bool = False
    remap: dict = {}

    # If the trait is used for a state, it can operate as a decorator to
    # implement communication with a device
    __setter__ = None
    __getter__ = None
    __returner__ = None
    __decorator_pending__ = []
    __decorator_action__ = None
    
    def __init__(self, *args, **kws):
        if callable(kws['default']):
            msg = f"trait decorators need to be instantiated - "\
                  f"@{self.__class__.__qualname__}() instead of @{self.__class__.__qualname__}"
            raise AttributeError(msg)

        # Apply the settings
        for k, v in kws.items():
            setattr(self, k, v)
        self.kws = kws

        # Now go back and type-check
        for k, v in kws.items():
            t = self.__annotations__[k]

            if t is ThisType:
                # replace the ThisType placeholder in the definition with the actual type
                t = self.type
            elif t is Any:
                # do no more additional work for parameters that accept any type
                continue
            elif k == 'default' and self.allow_none and isinstance(v, type(None)):
                # for the 'default' parameter, be fine with None
                continue
            elif not isinstance(v, t):
                # complain if the parameter is set to the wrong type
                tname = t.__qualname__
                vname = type(v).__qualname__
                raise ValueError(f"argument '{k}' has type '{vname}', but it should be '{tname}'")
                
        # Some trickery to define with
        if self.remap and self.only:
            raise ValueError(f"the 'remap' and 'valid' parameters are redundant")

        # Replace self.from_pythonic and self.to_pythonic with lookups in self.remap (if defined)
        if len(self.remap) > 0:
            remap_inbound = {v: k for k, v in self.remap.items()}
            if len(self.remap) != len(remap_inbound):
                raise ValueError(f"'remap' has duplicate values")

            self.from_pythonic = self.remap.__getitem__
            self.to_pythonic = remap_inbound.__getitem__

        self.metadata = {}
        self.__decorator_pending__ = []

    @classmethod
    def __init_subclass__(cls, type=None):
        """ customize the class definition before it is created

        :param type: the python type represented by the trait
        """
        if type is not None:
            cls.type = type

        # complete the annotation dictionary with the parent
        annots = dict(getattr(cls.__mro__[1], '__annotations__', {}),
                      **getattr(cls, '__annotations__', {}))

        cls.__annotations__ = dict(annots)

        # apply an explicit signature to cls.__init__
        annots = {k: cls.type if v is ThisType else (k, v) \
                  for k, v in annots.items()}
        cls.__defaults__ = dict((k, getattr(cls, k)) for k in annots.keys())
        util.wrap_attribute(cls, '__init__', __init__, tuple(annots.keys()), cls.__defaults__, 1, annots)
        
        # Help to reduce memory use by __slots__ definition (instead of __dict__)
        cls.__slots__ = [n for n in dir(cls) if not n.startswith('_')] + ['metadata', 'kind', 'name']

    def copy(self, **update_kws):
        obj = self.__class__(**dict(self.kws, **update_kws))
        obj.__getter__ = self.__getter__
        obj.__setter__ = self.__setter__
        obj.__returner__ = self.__returner__
        return obj

    ### Descriptor methods (called automatically by the owning class or instance)
    def __set_name__(self, owner_cls, name):
        """ Immediately after an owner class is instantiated, it calls this
            method for each of its attributes that implements this method.

            Trait takes advantage of this to remember the owning class for debug
            messages and to register with the owner class.
        """
        self.__objclass__ = owner_cls # inspect module expects this

        # Take the given name, unless we've bene tagged with a different
        self.name = name

        if issubclass(owner_cls, HasTraits):
            owner_cls.__traits__[name] = self
            self.kind = 'trait'
        else:
            self.kind = None

    def __init_owner_subclass__(self, owner_cls):
        """ At this point, definition in the owner subclass is complete, and its __init_subclass__
            has been called. Now it is time to ensure properties are compatible with the owner class.
            This is here --- not in __set_name__ --- because python
            obfuscates exceptions raised in __set_name__.

            This is also where we finalize selecting decorator behavior; is it a property or a method?
        """

        # classify the owner
        if issubclass(owner_cls, HasSettings):
            self.kind = 'setting'
            invalid = ('key', 'remap')

            if self.__decorator_action__ is not None or len(self.__decorator_pending__) > 0:
                raise AttributeError(f"{self} is a settings trait -- it cannot be used as a decorator")

        elif issubclass(owner_cls, HasStates):
            self.kind = 'state'
            invalid = ('default',)
        else:
            # some other kind of Trait behavior?
            invalid = tuple()

        for k in invalid:
            if self.__defaults__[k] != getattr(self, k):
                name = owner_cls.__qualname__
                raise AttributeError(f"'{name}' classes do not support traits with parameter '{k}'")

        # and now, finalize the behavior of decorated functions
        if self.kind == 'state':
            # were there any decorator requests?
            if len(self.__decorator_pending__) == 0:
                if self.__decorator_action__ is not None:
                    raise AttributeError(f"requested a decorator action but decorated no functions!")
                else:
                    return

            # otherwise, set to work
            positional_argcounts = [f.__code__.co_argcount - len(f.__defaults__ or tuple()) \
                                    for f in self.__decorator_pending__]

            # if there have been no hints, try to guess at the intent of the decorated methods
            if self.__decorator_action__ is None:
                if set(positional_argcounts) in ({1}, {1, 2}, {2}):
                    self.__decorator_action__ = 'property'
                else:
                    raise AttributeError(f"the intended behavior of the method(s) decorated by {self} "\
                                          "is ambiguous - specify with @labbench.property or @labbench.method")

            if self.__decorator_action__ == 'property':
                # adopt the properties!
                if set(positional_argcounts) not in ({1}, {1, 2}, {2}):
                    raise AttributeError(f"a decorator implementation with @{self} must apply to a getter "\
                                         f"(above `def func(self)`) and/or setter (above `def func(self, value):`)")
                for func, argcount in zip(self.__decorator_pending__, positional_argcounts):
                    if len(self.help.rstrip().strip()) == 0:
                        # take func docstring as default self.help
                        self.help = (func.__doc__ or '').rstrip().strip()

                    if argcount == 1:
                        self.__getter__ = func
                    else:
                        self.__setter__ = func
            else:
                raise AttributeError(f"{self} failed to implement a decorator")

    @util.hide_in_traceback
    def __set__(self, owner, value):
        # First, validate the pythonic types
        if not self.settable:
            raise AttributeError(f"{self} is not settable")

        # Validate the pythonic value
        if value is not None:
            # Convert to the representation expected by owner.__set_by_key__
            try:
                value = Trait.to_pythonic(self, value)
                value = self.validate(value)
            except BaseException as e:
                name = owner.__class__.__qualname__ + '.' + self.name
                e.args = (f" in attempt to set '{name}', " + e.args[0],) + e.args[1:]
                raise e
            
            if len(self.only) > 0 and not self.contains(self.only, value):
                raise ValueError(f"value '{value}' is not among the allowed values {repr(self.only)}")
        elif self.allow_none:
            value = None
        else:
            raise ValueError(f"None value not allowed for trait '{repr(self)}'")

        try:
            value = self.from_pythonic(value)
        except BaseException as e:
            name = owner.__class__.__qualname__ + '.' + self.name
            e.args = (e.args[0] + f" in attempt to set '{name}'",) + e.args[1:]
            raise e

        # Apply value
        if self.kind == 'setting':
            # from the setting
            owner.__set_value__(self.name, value)
        
        elif self.__setter__ is not None:
            # from the function decorated by this trait
            self.__setter__(owner, value)
            
        elif self.key is None:
            # from the command (with below)
            objname = owner.__class__.__qualname__ + '.' + self.name
            raise AttributeError(f"cannot set {objname}: no @{self.name} "\
                                 f"setter is defined, and command is None")
        else:
            owner.__set_by_key__(self.name, self.key, value)

        owner.__notify__(self.name, value, 'set', cache=self.cache)

    @util.hide_in_traceback
    def __get__(self, owner, owner_cls=None):
        """ Called by the class instance that owns this attribute to
        retreive its value. This, in turn, decides whether to call a wrapped
        decorator function or the owner's __get_by_key__ method to retrieve
        the result.

        :return: retreived value
        """

        if owner is None:
            # this is the owner class looking for the trait instance itself
            return self
        elif self.__returner__ is not None:
            
            # Inject the labbench Trait hooks into the return value
            @wraps(self.__returner__)
            def method(*args, **kws):
                value = self.__returner__(owner, *args, **kws)
                return self.__cast_get__(owner, value)

            return method

        elif not self.gettable:
            # stop now if this is not a gettable Trait
            raise AttributeError(f"{self} is not gettable")

        elif self.kind == 'setting':
            value = owner.__get_value__(self.name)
            
        elif (self.cache and self.name in owner.__previous__):
            # return the cached value if applicable
            return owner.__previous__[self.name]
        
        elif self.__getter__ is not None:
            # get value with the decorator implementation, if available
            value = self.__getter__(owner)
            
        else:
            # otherwise, get with owner.__get_by_key__, if available
            if self.key is None:
                # otherwise, 'get' 
                objname = owner.__class__.__qualname__ + '.' + self.name
                raise AttributeError(f"cannot set {objname}: no @{self.name} "\
                                     f"getter is defined, and command is None")
            value = owner.__get_by_key__(self.name, self.key)

        return self.__cast_get__(owner, value, strict=False)

    @util.hide_in_traceback
    def __cast_get__(self, owner, value, strict=False):
        """ Examine value and either return a valid pythonic value or raise an exception if it cannot be cast.

        :param owner: the class that owns the trait
        :param value: the value we need to validate and notify
        :return:
        """
        if self.allow_none and value is None:
            pass
        else:
            # skip validation if None and None values are allowed
            try:
                value = self.to_pythonic(value)
            except BaseException as e:
                name = owner.__class__.__qualname__ + '.' + self.name
                e.args = (e.args[0] + f" in attempt to get '{name}'",) + e.args[1:]
                raise e
            
            # Once we have a python value, give warnings (not errors) if the device value fails further validation
            if isinstance(owner, Device) and hasattr(owner, '_console'):
                log = owner._console.warning
            else:
                log = warn
    
            try:
                if value != self.validate(value):
                    raise ValueError
            except ValueError:
                log(f"'{self.name}' {self.kind} received the value {repr(value)}, " \
                    f"which fails {repr(self)}.validate()")
            if value is None and not self.allow_none:
                log(f"'{self.name}' {self.kind} received value None, which" \
                    f"is not allowed for {repr(self)}")
            if len(self.only) > 0 and not self.contains(self.only, value):
                log(f"'{self.name}' {self.kind} received {repr(value)}, which" \
                    f"is not in the valid value list {repr(self.only)}")

        owner.__notify__(self.name, value, 'get', cache=self.cache or (self.kind == 'setting'))

        return value

    @util.hide_in_traceback
    def to_pythonic(self, value):
        """ Convert a value from an unknown type to self.type.
        """
        return self.type(value)

    @util.hide_in_traceback
    def from_pythonic(self, value):
        """ convert from a python type representation to the format needed to communicate with the device
        """
        return value

    @util.hide_in_traceback
    def validate(self, value):
        """ This is the default validator, which requires that trait values have the same type as self.type.
            A ValueError is raised for other types.
        :param value: value to check
        :return: a valid value
        """
        if isinstance(value, self.type):
            raise ValueError(f"a '{type(self).__qualname__}' trait only accepts" \
                             f"values of type '{type(self.type).__qualname__}'")
        return value

    def contains(self, iterable, value):
        return value in iterable

    ### Decorator methods
    @util.hide_in_traceback
    def __call__(self, func):
        """ use the Trait as a decorator, which ties this Trait instance to evaluate a property or method in the
            owning class. you can specify
        """
        # only decorate functions.
        if not callable(func):
            raise Exception(f"object of type '{func.__class__.__qualname__}' must be callable")

        # take any hints from func about the type of decorator action
        if self.__decorator_action__ is None:
            self.__decorator_action__ = getattr(func, '__decorator_action__', None)
        elif hasattr(func, '__decorator_action__'):
            if func.__decorator_action__ != self.__decorator_action__:
                raise AttributeError(f"the given function {repr(func)} is decorated "\
                                     f"to act as {func.__decorator_action__}, but "\
                                     f"{repr(self)} is already decorated to act as {self.__decorator_action__}")
            self.__decorator_action__ = func.__decorator_action__

        self.__decorator_pending__.append(func)

        # Register in the list of decorators, in case we are overwritten by an
        # overloading function
        if getattr(self, 'name', None) is None:
            self.name = func.__name__
        if len(HasTraitsMeta.__pending__) > 0:
            HasTraitsMeta.__pending__[-1][func.__name__] = self

        # return self to ensure `self` is the value assigned in the class definition
        return self

    ### Object protocol boilerplate methods
    def __repr__(self, omit=[]):
        owner_cls = getattr(self, '__objclass__', None)

        if owner_cls is None:
            # revert to the class definition if the owning class
            # hasn't claimed us yet
            pairs = []
            for k, default in self.__defaults__.items():
                v = getattr(self, k)
                if v != default:
                    pairs.append(f'{k}={repr(v)}')
            name = self.__class__.__qualname__
            return f"{name}({','.join(pairs)})"

        else:
            # otherwise, this is more descriptive
            return f"{owner_cls.__qualname__}.{self.name}"

    __str__ = __repr__

    def doc(self):
        traitdoc = self.__repr__(omit=["help"])
        return f"`{traitdoc}` {self.help}"

    def tag(self, **kws):
        self.metadata.update(kws)
        return self


Trait.__init_subclass__()


# def method(obj):
#     """ Add this decorator in addition to a trait decorator to specify that
#         the trait should behave as a callable method. For example:
#
#             ```python
#             import labbench as lb
#
#             class MyDevice(lb.Device)
#                 @lb.method
#                 @lb.Int(min=0, max=10)
#                 def fetch_int(self):
#                     return 6
#
#             with MyDevice as m:
#                 print(m.fetch_int())
#             ```
#
#         Decorate either before or after the trait decorator.
#     """
#     if not isinstance(obj, Trait) and not callable(obj):
#         raise ValueError('the method "method" decorator must be applied to a callable')
#     obj.__decorator_action__ = 'method'
#     return obj
#
#
# def property(obj):
#     """ Add this decorator in addition to a trait decorator to specify that
#         the trait should behave as a property (descriptor). This means
#         that it is not callable. For example:
#
#             ```python
#             import labbench as lb
#
#             class MyDevice(lb.Device)
#                 @lb.property
#                 @lb.Int(min=0, max=10)
#                 def fetch_int(self):
#                     return 6
#
#             with MyDevice as m:
#                 print(m.fetch_int)
#             ```
#
#         Decorate either before or after the trait decorator.
#     """
#     if not isinstance(obj, Trait) and not callable(obj):
#         raise ValueError('the method "method" decorator must be applied to a callable')
#     obj.__decorator_action__ = 'property'
#     return obj


class HasTraits(metaclass=HasTraitsMeta):
    __notify_list__ = {}
    __pending__ = {}

    def __init__(self):
        self.__notify_list__ = {}
        self.__previous__ = {}

    def __init_subclass__(cls):
        if cls.__traits__ in HasTraitsMeta.__pending__:
            HasTraitsMeta.__pending__.remove(cls.__traits__)
            
        for name, trait in dict(cls.__traits__).items():
            if not hasattr(trait, '__objclass__'):
                trait.__set_name__(cls, name)
            trait.__init_owner_subclass__(cls)
 
    def __iter__(self):
        return iter(self.__traits__.values())

    def __len__(self):
        return len(self.__traits__)

    @util.hide_in_traceback
    def __getitem__(self, name):
        """ Get the instance of the Trait named class (as opposed to
            __getattr__, which fetches its value).
        """
        return self.__traits__[name]

    @util.hide_in_traceback
    def __notify__(self, name, value, type, cache):
        old = self.__previous__.setdefault(name, Undefined)

        msg = dict(new=value, old=old, owner=self, name=name, type=type, cache=cache)

        for handler in self.__notify_list__.values():
            handler(dict(msg))

        self.__previous__[name] = value

    def __set_by_key__(self, name, command, value):
        objname = self.__class__.__qualname__ + '.' + name
        raise AttributeError(f"cannot set {objname}: no @{name} "\
                             f"setter is defined, and {name}.__set_by_key__ is not defined")

    def __get_by_key__(self, name, command):
        objname = self.__class__.__qualname__ + '.' + name
        raise AttributeError(f"cannot get {objname}: no @{name} "\
                             f"getter is defined, and {name}.__get_by_key__ is not defined")


class HasSettings(HasTraits):
    def __init__(self):
        super().__init__()

        # load up all the defaults as if they've been set already
        for name, trait in self.__traits__.items():
            self.__previous__[name] = trait.default

    def __dir__(self):
        return iter(self.__traits__.keys())

    @util.hide_in_traceback
    def __get_value__ (self, name):
        """ Get value of a trait for this settings instance

        :param name: Name of the trait
        :return: cached value, or the trait default if it has not yet been set
        """
        return self.__previous__[name]

    @util.hide_in_traceback
    def __set_value__ (self, name, value):
        """ Set value of a trait for this settings instance

        :param name: Name of the trait
        :param value: value to assign
        :return: None
        """
        # assignment to to self.__previous__ here would corrupt 'old' message key in __notify__
        pass


class HasStates(HasTraits):
    __previous__ = {}

    @classmethod
    def __init_subclass__(cls):
        """ Complete any 2-part method decorators by identifying methods that

        """
        # complete any 2-part method decorators by identifying any traits
        # that were overwritten by method definitions
        for k, trait in dict(cls.__traits__).items():
            obj = getattr(cls, k)
            
            # Apply the trait decorator to the object if it is "part 2" of a
            # decorator
            if obj is not trait and callable(obj):
                setattr(cls, k, trait(obj))

        return super().__init_subclass__()


class Any(Trait):
    """ allows any value """

    @util.hide_in_traceback
    def validate(self, value):
        return value

    @util.hide_in_traceback
    def to_pythonic(self, value):
        return value


Trait.__annotations__['key'] = Any


def observe(obj, handler, names=None):
    """ Register a handler function to be called whenever a trait changes.

        The handler function takes a single message argument. This
        dictionary message has the keys

        * `new`: the updated value
        * `old`: the previous value
        * `owner`: the object that owns the trait
        * `name`: the name of the trait
        * 'event': 'set' or 'get'

        :param handler: the handler function to call when the value changes

        :param names: notify only changes to these trait names (None to disable filtering)
    """

    def wrapped(msg):
        # filter according to names
        if names is None or msg['name'] in names:
            handler(msg)

    if isinstance(obj, HasTraits):
        obj.__notify_list__[handler] = wrapped
    else:
        raise TypeError('object to observe must be an instance of Device, or Device.settings')


def unobserve(obj, handler):
    """ Unregister a handler function from notifications in obj.
    """
    if isinstance(obj, HasTraits):
        try:
            del obj.__notify_list__[handler]
        except KeyError as e:
            ex = e
        else:
            ex = None
        if ex:
            raise ValueError(f'{handler} was not registered to observe {obj}')
    else:
        raise TypeError('object to unobserve must be an instance of Device, or Device.settings')


class Undefined(Trait):
    """ rejects any value """

    @util.hide_in_traceback
    def validate(self, value):
        raise ValueError('undefined trait does not allow any value')


Undefined = Undefined()


class BoundedNumber(Trait):
    """ accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking) """
    default: ThisType = 0
    min: ThisType = None
    max: ThisType = None

    @util.hide_in_traceback
    def validate(self, value):
        if not isinstance(value, (bytes, str, bool, numbers.Number)):
            raise ValueError(f"a '{type(self).__qualname__}' trait value must be a numerical, str, or bytes instance")
        # Check bounds once it's a numerical type
        if self.max is not None and value > self.max:
            raise ValueError(f'{value} > the upper bound {self.max}')
        if self.min is not None and value < self.min:
            raise ValueError(f'{value} < the lower bound {self.min}')
        return value


class NonScalar(Any):
    title: str = '' # a name for the data

    """ generically non-scalar data, such as a list, array, but not including a string or bytes """

    @util.hide_in_traceback
    def validate(self, value):
        if isinstance(value, (bytes,str)):
            raise ValueError(f"given text data but expected a non-scalar data")
        if not hasattr(value, '__iter__') and not hasattr(value, '__len__'):
            raise ValueError(f"expected non-scalar data but given a non-iterable")
        return value

class Int(BoundedNumber, type=int):
    """ accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking) """


class Float(BoundedNumber, type=float):
    """ accepts numerical, str, or bytes values, following normal python casting procedures (with bounds checking) """
    step: ThisType = None

    @util.hide_in_traceback
    def validate(self, value):
        value = super().validate(value)
        if self.step is not None:
            mod = value % self.step
            if mod < self.step / 2:
                return value - mod
            else:
                return value - (mod - self.step)
        return value

class Complex(Trait, type=complex):
    """ accepts numerical or str values, following normal python casting procedures (with bounds checking) """


class Bool(Trait, type=bool):
    """ accepts boolean or numeric values, or a case-insensitive match to one of ('true',b'true','false',b'false') """

    @util.hide_in_traceback
    def validate(self, value):
        if isinstance(value, (bool, numbers.Number)):
            return value
        elif isinstance(value, (str, bytes)):
            lvalue = value.lower()
            if lvalue in ('true', b'true'):
                return True
            elif lvalue in ('false', b'false'):
                return False
        raise ValueError(f"'{type(self).__qualname__}' traits accept only boolean, numerical values," \
                         "or one of ('true',b'true','false',b'false'), case-insensitive")


class String(Trait):
    """ base class for string types, which adds support for case sensitivity arguments """
    case: bool = True

    @util.hide_in_traceback
    def contains(self, iterable, value):
        if not self.case:
            iterable = [v.lower() for v in iterable]
            value = value.lower()
        return value in iterable


class Unicode(String, type=str):
    """ accepts strings or numeric values only; convert others explicitly before assignment """
    default: ThisType = ''

    @util.hide_in_traceback
    def validate(self, value):
        if not isinstance(value, (str, numbers.Number)):
            raise ValueError(f"'{type(self).__qualname__}' traits accept values of str or numerical type")
        return value


class Bytes(String, type=bytes):
    """ accepts bytes objects only - encode str (unicode) explicitly before assignment """
    default: ThisType = b''

class Iterable(Trait):
    """ accepts any iterable """

    @util.hide_in_traceback
    def validate(self, value):
        if not hasattr(value, '__iter__'):
            raise ValueError(f"'{type(self).__qualname__}' traits accept only iterable values")
        return value


class Dict(Iterable, type=dict):
    """ accepts any type of iterable value accepted by python `dict()` """


class List(Iterable, type=list):
    """ accepts any type of iterable value accepted by python `list()` """


class Tuple(Iterable, type=tuple):
    """ accepts any type of iterable value accepted by python `tuple()` """
    settable: bool = False


class Address(Unicode):
    """ accepts IDN-compatible network address, such as an IP address or DNS hostname """

    @util.hide_in_traceback
    def validate(self, value):
        """Rough IDN compatible domain validator"""

        host = value.encode('idna').lower()
        pattern = re.compile(br'^([0-9a-z][-\w]*[0-9a-z]\.)+[a-z0-9\-]{2,15}$')
        m = pattern.match(host)
        if m is None:
            raise ValueError('invalid TCP/IP address')
        else:
            return m.string.decode()


class DisconnectedBackend(object):
    """ "Null Backend" implementation to raises an exception with discriptive
        messages on attempts to use a backend before a Device is connected.
    """

    def __init__(self, dev):
        """ dev may be a class or an object for error feedback
        """
        self.name = dev.__class__.__qualname__

    @util.hide_in_traceback
    def __getattr__(self, key):
        msg = f"{self.name} must be connected to access {self.name}.backend"
        raise ConnectionError(msg)

    def __repr__(self):
        return 'DisconnectedBackend()' 
    
    str = __repr__


class Device(HasStates, util.Ownable):
    r"""`Device` is the base class common to all labbench
        drivers. Inherit it to implement a backend, or a specialized type of
        driver.

        Drivers that subclass `Device` get

        * device connection management via context management (the `with` statement)
        * test state management for easy test logging and extension to UI
        * a degree automatic stylistic consistency between drivers

        .. note::
            This `Device` base class is a boilerplate object. It has convenience
            functions for device control, but no implementation.

            Implementation of protocols with general support for broad classes
            of devices are provided by other labbench Device subclasses:

                * VISADevice exposes a pyvisa backend for VISA Instruments
                * ShellBackend exposes a threaded pipes backend for command line tools
                * Serial exposes a pyserial backend for serial port communication
                * DotNetDevice exposes a pythonnet for wrapping dotnet libraries

            (and others). If you are implementing a driver that uses one of
            these backends, inherit from the corresponding class above, not
            `Device`.


        Settings
        ************************
    """

    """ Settings traits.

        These are stored only on the host; setting or getting these values do not
        trigger live updates (or any communication) with the device. These
        define connection addressing information, communication settings,
        and options that only apply to implementing python support for the
        device.

        The device uses this container to define the keyword options supported
        by its __init__ function. These are applied when you instantiate the device.
        After you instantiate the device, you can still change the setting with::

            Device.settings.resource = 'insert-your-address-string-here'
    """
    settings = HasSettings

    resource: Unicode(allow_none=True, help='device address or URI')

    concurrency: Bool(default=True, settable=False,
                      help='`True` if this device supports threading')

    """ Container for state traits in a Device. Getting or setting state traits
        triggers live updates: communication with the device to get or set the
        value on the Device. Therefore, getting or setting state traits
        needs the device to be connected.

        To set a state value inside the device, use normal python assigment::

            device.parameter = value
            
        To get a state value from the device, you can also use it as a normal python variable::
        
            variable = device.parameter + 1
    """
    backend = DisconnectedBackend(None)
    """ .. this attribute is some reference to a controller for the device.
        it is to be set in `connect` and `disconnect` by the subclass that implements the backend.
    """

    # Backend classes may optionally overload these, and do not need to call the parents
    # defined here
    def open(self):
        """ Backend implementations overload this to open a backend
            connection to the resource.
        """
        pass

    def close(self):
        """ Backend implementations must overload this to disconnect an
            existing connection to the resource encapsulated in the object.
        """
        self.backend = DisconnectedBackend(self)
        self.connected

    __warn_state_names__ = []
    __warn_settings_names__ = []
    __children__ = {}

    @classmethod
    def __init_subclass__(cls):
        # Make a new cls.settings subclass that includes the new settings
        annotations = getattr(cls, '__annotations__', {})

        for name, v in dict(annotations).items():
            if isinstance(v, Trait):
                # explicitly define a new setting
                continue
            elif hasattr(cls.settings, name):
                # update the default value of an existing setting, if it is valid
                trait = getattr(cls.settings, name)
                try:
                    v = trait.to_pythonic(v)
                except BaseException:
                    raise

                annotations[name] = trait.copy(default=v)
            else:
                clsname = cls.__qualname__
                raise AttributeError(f"the '{clsname}' setting annotation '{name}' "\
                                     f"must be a Trait or an updated default value")
        settings = type('settings', (cls.settings,),
                        dict(cls.settings.__dict__,
                             __traits__=dict(cls.settings.__traits__),
                             **annotations))
        settings.__qualname__ = cls.__qualname__ + '.settings'
        cls.settings = settings

        if annotations:
            cls.__annotations__ = dict(getattr(cls.__base__, '__annotations__', {}),
                                       **annotations)

        # Update __doc__ with settings
        if cls.__doc__:
            cls.__doc__ = trim(cls.__doc__)
        else:
            cls.__doc__ = ''

        if cls.__init__.__doc__:
            cls.__init__.__doc__ = trim(cls.__init__.__doc__)
        else:
            cls.__init__.__doc__ = ''

        # Update cls.__doc__
        settings = list(cls.settings.__traits__.items())
        txt = '\n\n'.join((f":{t.name}: {t.doc()}" for k, t in settings))
        cls.__doc__ += '\n\n' + txt

        defaults = {k: v.default for k, v in settings if v.gettable}
        types = {k: v.type for k, v in settings if v.gettable}
        util.wrap_attribute(cls, '__init__', __init__, tuple(defaults.keys()), defaults, 1, types)

        cls.__init__.__doc__ = cls.__init__.__doc__ + '\n\n' + txt

        super().__init_subclass__()

    def __init__(self, **settings):
        """ Apply initial settings here; use a `with` block or invoke `open()` to use the driver.
        """
        super().__init__()

        self.settings = self.settings()

        for name, init_value in settings.items():
            if init_value != self.settings.__traits__[name].default:
                setattr(self.settings, name, init_value)

        self.__imports__()

        self.backend = DisconnectedBackend(self)

        # gotta have a console logger
        self._console = util.console.logger.getChild(str(self))
        self._console = logging.LoggerAdapter(self._console, dict(device=repr(self), origin=f" - "+str(self)))

        # Instantiate state now. It needed to wait until this point, after settings are fully
        # instantiated, in case state implementation depends on settings
        setattr(self, 'open', self.__open_wrapper__)
        setattr(self, 'close', self.__close_wrapper__)

        self.__warn_state_names__ = tuple(self.__traits__.keys())
        self.__warn_settings_names__ = tuple(self.settings.__traits__.keys())

    @util.hide_in_traceback
    def __setattr__(self, name, value):
        """ Throw warnings if we suspect a typo on an attempt to assign to a state
            or settings trait
        """
        if self.__warn_state_names__ and not hasattr(self, name):
            if name in self.__warn_state_names__:
                msg = f'{self}: assigning to a new attribute {name} -- did you mean to assign to the trait state.{name} instead?'
                warn(msg)
            if name in self.__warn_settings_names__:
                msg = f'{self}: assigning to a new attribute {name} -- did you mean to assign to the trait settings.{name} instead?'
                warn(msg)
        super().__setattr__(name, value)

    @util.hide_in_traceback
    @wraps(open)
    def __open_wrapper__(self):
        """ A wrapper for the connect() method. It steps through the
            method resolution order of self.__class__ and invokes each open()
            method, starting with labbench.Device and working down
        """
        if self.connected:
            self._console.debug(f'attempt to open {self}, which is already open')
            return

        self.backend = None

        for opener in trace_methods(self.__class__, 'open', Device)[::-1]:
            opener(self)

        self._console.debug(f"{self} is open")
        # Force an update to self.connected
        self.connected

    def __owner_init__(self, owner):
        super().__owner_init__(owner)

        # update the name of the logger to match the context within owner
        self._console = util.console.logger.getChild(str(self))
        self._console = logging.LoggerAdapter(self._console, dict(device=repr(self), origin=f" - "+str(self)))

    @util.hide_in_traceback
    @wraps(close)
    def __close_wrapper__(self):
        """ A wrapper for the close() method that runs
            cleanup() before calling close(). close()
            will still be called if there is an exception in cleanup().
        """
        # Try to run cleanup(), but make sure to run
        # close() even if it fails
        if not self.connected:
            return

        methods = trace_methods(self.__class__, 'close', Device)

        all_ex = []
        for closer in methods:
            try:
                closer(self)
            except BaseException:
                all_ex.append(sys.exc_info())

        # Print tracebacks for any suppressed exceptions
        for ex in all_ex[::-1]:
            # If ThreadEndedByMaster was raised, assume the error handling in
            # util.concurrently will print the error message
            if ex[0] is not util.ThreadEndedByMaster:
                depth = len(tuple(traceback.walk_tb(ex[2])))
                traceback.print_exception(*ex, limit=-(depth - 1))
                sys.stderr.write(
                    '(Exception suppressed to continue close)\n\n')

        self.connected

        self._console.debug(f'is closed')

    def __imports__(self):
        pass

    @util.hide_in_traceback
    def __enter__(self):
        try:
            self.open()
            return self
        except BaseException as e:
            args = list(e.args)
            if len(args) > 0:
                args[0] = '{}: {}'.format(repr(self), str(args[0]))
                e.args = tuple(args)
            raise e

    @util.hide_in_traceback
    def __exit__(self, type_, value, traceback):
        try:
            self.close()
        except BaseException as e:
            args = list(e.args)
            args[0] = '{}: {}'.format(repr(self), str(args[0]))
            e.args = tuple(args)
            raise e

    ### Object boilerplate
    def __del__(self):
        self.close()

    def __repr__(self):
        name = self.__class__.__qualname__
        if hasattr(self.settings, 'resource'):
            return f'{name}({repr(self.settings.resource)})'
        else:
            # In case an exception has occurred before __init__
            return f'{name}()'

    @property
    @Bool()
    def connected(self):
        """ are we connected? """
        try:
            return DisconnectedBackend not in self.backend.__class__.__mro__
        except:
            # Run into this sometimes on reloading a module or ipython shell:
            # the namespace is gone. we just assume disconnected
            return False


def device_contexts(objs, concurrent=True):
    other_contexts = dict([(a,o) for a,o in objs.items()])

    # Enforce the ordering set by self.enter_first
    if concurrent:
        # Any remaining context managers will be run concurrently if concurrent=True
        contexts = dict(first_contexts,
                                     others=util.concurrently(name=f'',
                                                         **other_contexts))
    else:
        # Otherwise, run them sequentially
        contexts = dict(first_contexts, **other_contexts)
    self.__cm = util.sequentially(name=f'{repr(self)} connections',
                             **contexts)

Device.__init_subclass__()
