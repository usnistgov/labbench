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

'''
This implementation is deeply intertwined obscure details of the python object
model. Consider starting with a close read of the documentation and exploring
the objects in an interpreter instead of reverse-engineering this code.
'''

#from . import util

from typing import Any, Generic, T, NoReturn
from warnings import warn, simplefilter

import builtins
import functools
import inspect
import ipaddress
import logging
import sys
import traceback
import types

__all__ = ['DeviceException', 'DeviceNotReady', 'DeviceFatalError', 
           'DeviceConnectionLost', 'Undefined', 'All', 'DeviceStateError',
           'UnimplementedState', 'setter', 'getter',
           'Int', 'Float', 'Unicode', 'Complex', 'Bytes', 'CaselessBytesEnum',
           'Bool', 'List', 'Dict', 'TCPAddress',
           'CaselessStrEnum', 'Device', 'list_devices', 'logger', 'CommandNotImplementedError',
           'observe', 'unobserve', 'BytesEnum', 'UnicodeEnum',
           ]

logger = logging.getLogger('labbench')

class LabbenchDeprecationWarning(DeprecationWarning):
    pass

simplefilter('once', LabbenchDeprecationWarning)

All = Any
Undefined = NoReturn

class ThisType(Generic[T]):
    pass

class DeviceStateError(IOError):
    """ Failure to get or set a state in `Device.state`
    """
    
class UnimplementedState(DeviceStateError):
    """ No state defined for the trait
    """


class DeviceNotReady(Exception):
    """ Failure to communicate with the Device because it was not ready for communication
    """


class DeviceException(Exception):
    """ Generic Device exception
    """


class DeviceFatalError(Exception):
    """ A fatal error in the device
    """


class DeviceConnectionLost(Exception):
    """ Connection state has been lost unexpectedly
    """    


class CommandNotImplementedError(NotImplementedError):
    """ A command that has been defined but not implemented
    """
    pass


def wrap(obj, to_name, from_func):
    ''' TODO: This looks like it duplicates functools.wrap - switch to
        functools.wrap?
    '''
    to_func = object.__getattribute__(obj, to_name)
    obj.__wrapped__[to_name] = to_func
    from_func.__func__.__doc__ = to_func.__doc__
    from_func.__func__.__name__ = to_func.__name__
    setattr(obj, to_name, from_func)


def trace_methods(cls, name, until_cls=None):
    ''' Look for a method called `name` in cls and all of its parent classes.
    '''
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
    ''' Look for Device instances, and their names, in the calling
        code context (depth == 1) or its callers (if depth in (2,3,...)).
        Checks locals() in that context first.
        If no Device instances are found there, search the first
        argument of the first function argument, in case this is
        a method in a class.
    '''
    from inspect import getouterframes, currentframe
    from sortedcontainers import sorteddict

    frame = currentframe()
    f = getouterframes(frame)[depth]
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
        del frame, f

    return ret

def dynamic_init ():
    ''' Wrapper function to call __init__ with adjusted function signature
    '''

    # The signature has been dynamically replaced and is unknown. Pull it in
    # via locals() instead. We assume we're inside a __init__(self, ...) call.
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))    
    self.__init_wrapped__(**items)

def wrap_dynamic_init(cls, fields: list, defaults: dict, positional:int = None,
                      annotations:dict = {}):
    ''' Replace cls.__init__ with a wrapper function with an explicit
        call signature, replacing the actual call signature that can be
        dynamic __init__(self, *args, **kws) call signature.
        
        :fields: iterable of names of each call signature argument
        :
    '''
    # Is the existing cls.__init__ already a dynamic_init wrapper?
    reuse = hasattr(cls.__init__, '__dynamic__')
    
    defaults = tuple(defaults.items())
    
    if positional is None:
        positional = len(fields)

    # Generate a code object with the adjusted signature
    code = dynamic_init.__code__
    code = types.CodeType(1+positional, # co_argcount
                          len(fields)-positional, # co_kwonlyargcount
                          len(fields)+1, # co_nlocals
                          code.co_stacksize,
                          code.co_flags,
                          code.co_code,
                          code.co_consts,
                          code.co_names,
                          ('self',)+tuple(fields),
                          code.co_filename,
                          code.co_name,
                          code.co_firstlineno,
                          code.co_lnotab,
                          code.co_freevars,
                          code.co_cellvars)

    # Generate the new wrapper function and its signature
    __globals__ = getattr(cls.__init__, '__globals__', builtins.__dict__)
    wrapper = types.FunctionType(code,
                                 __globals__,
                                 cls.__init__.__name__)

    wrapper.__doc__ = cls.__init__.__doc__
    wrapper.__qualname__ = cls.__init__.__qualname__
    wrapper.__defaults__ = tuple((v for k,v in defaults[:positional]))
    wrapper.__kwdefaults__ = dict(((k,v) for k,v in defaults[positional:]))
    wrapper.__annotations__ = annotations
    wrapper.__dynamic__ = True

    if reuse:
        cls.__init__, cls.__init_wrapped__ = wrapper, cls.__init_wrapped__
    else:
        cls.__init__, cls.__init_wrapped__ = wrapper, cls.__init__


class TraitMeta(type):
    ''' Apples the specified type to the 'default_value' annotation
    '''
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)

        # Complete annotation dictionary updated with the parent
        annots = dict(getattr(cls.__mro__[1], '__annotations__',{}),
                      **getattr(cls, '__annotations__', {}))
        
        cls.__annotations__ = dict(annots)
        
        annots = dict(((k,cls.type) if v is ThisType else (k,v) \
                       for k,v in annots.items()))
        
        cls.__defaults__ = dict((k,getattr(cls,k)) for k in annots.keys())
        
        wrap_dynamic_init(cls, tuple(annots.keys()), cls.__defaults__, 1,
                          annots)


class Trait(metaclass=TraitMeta):
    ''' Base class for Traits. These include hooks to perform  HasTraits
        to 
    '''
    type = None

    # These annotations define the arguments to __init__ @dataclass above
    default_value: ThisType = None
    command: Any = None
    help: str = None
    allow_none: bool = True
    read_only: bool = False
    write_only: bool = False
    cache: bool = False
    remap: dict = {}
    label: str = ''
    
    # TODO: Decide whether this is better tagged inside the metadata attribute,
    # or whether cache implies this
    is_metadata: bool = False

    __setter__ = None
    __getter__ = None
    
    def __init__ (self, *args, **kws):
        for k,v in kws.items():
            setattr(self, k, v)           
        self.previous = Undefined
        self.metadata = {}

    def __set_name__ (self, owner_cls, name):
        self.__owner_cls__ = owner_cls
        self.name = name

    def __set__ (self, owner, value):
        if self.read_only:
            raise AttributeError(f"{self} is read-only")
        if value is not None or not self.allow_none:
            value = self.validate(value)
            value = self.cast_from(value)

        if self.__setter__ is not None:
            self.__setter__(owner.__device__, value)
        else:
           owner.__set_state__(self, value)
        owner.__notify__(self.name, value, 'set')
        self.previous = value

    def __get__ (self, owner, owner_cls=None):
        # owner is None until the parent class has not been instantiated.
        # allow direct access to this object until then.       
        if self.write_only:
            raise AttributeError(f"{self} is write-only")
        
        # Do caching
        if self.cache and self.previous is not Undefined:
            return self.previous
        
        if owner is None:
            return self

        if self.__getter__ is not None:
            value = self.__getter__(owner.__device__)            
        else:
            value = owner.__get_state__(self)

        if value is not None or not self.allow_none:
            value = self.cast_from(value)
            if value != self.validate(value):
                owner.__device__.warning(f"received value '{repr(value)}' failed validation for '{repr(self)}'")
        owner.__notify__(self.name, value, 'get')
        self.previous = value
        return value

    def __repr__(self):
        params = self.parameters(False)
        params = (f'{k}={repr(getattr(self,k))}' for k in params\
                  if getattr(self,k) != getattr(self.__class__, k))
        params = ','.join(params)
        ret = f'{self.__class__.__qualname__}({params})'

        return ret
    
    def doc(self):
        return f"`{repr(self)}` {self.help}"

    __str__ = __repr__
    
    def __call__(self, func):
        if func.__code__.co_argcount == 2:
            return self.getter(func)
        elif func.__code__.co_argcount == 3:
            return self.setter(func)
        else:
            raise ValueError(f"@{self.name} must decorate a function with 2 arguments (a getter) or 3 arguments (a setter)")
    
    def setter(self, func):
        self.__setter__ = func
        return func
    
    def getter(self, func):
        self.__getter__ = func
        return func
    
    def tag(self, **kws):
        self.metadata.update(kws)
        return self

    def cast_from(self, value):
        ''' Convert a value from an unknown type to self.type.
        '''
        if self.type is None:
            raise NotImplementedError(f'need to set {repr(self).type} to define the type')
        return self.type(value)
    
    def cast_to(self, value):
        ''' TODO: Perhaps a Device class should provide
            this kind of method? This is a placeholder in the meantime
            that simply returns the given value.
        '''
        return value

    def validate(self, value):
        ''' Override this method to implement bounds checking. 
        
            :value: the value to be validated (same type as self.type)
        '''
        return value
        
    def parameters(self, with_defaults=True):
        ret = {}
        for key in self.__defaults__:
            v = getattr(self, key)
            if v is not self.__defaults__[key]:
                ret[key] = v
        try:
            del ret['help']
        except KeyError:
            pass
        return ret


class BoundedNumber(Trait):#, metaclass=NumberTraitMeta):
    min: ThisType = None
    max: ThisType = None
    step: ThisType = None
    
    def validate(self, value):
        # Convert type
        value = self.cast_from(value)
        
        # Check bounds once it's a numerical type
        if self.max is not None and value > self.max:
            raise ValueError(f'{value} > the upper bound {self.max}')
        if self.min is not None and value < self.min:
            raise ValueError(f'{value} < the lower bound {self.min}')
        if self.step is not None:
            mod = value % self.step
            if mod < self.step/2:
                return value - mod
            else:
                return value - (mod-self.step)                
        return value


class Int(BoundedNumber):
    type = int


class Float(BoundedNumber):
    type = float    


class Complex(Trait):
    type = complex


class Bool(Trait):
    type = bool

    def cast_from(self, value):
        pass

            
class Unicode(Trait):
    type = str

    def cast_from(self, value):
        print('cast from ', value)
        # Assume it is a mistake if we're left with the generic object.__str__
        # output, which looks like '<__main__.T object at 0x000001EDB05176A0>'
        if type(value).__str__ is object.__str__:
            raise TypeError(f"object of type '{value.__class__.__qualname__}' does not support descriptive string conversion")
        return self.type(value)

    
class Bytes(Trait):
    type = bytes


class Dict(Trait):
    type = dict


class List(Trait):
    type = list
    

class EnumString(Trait):
    values: list = None
    case: bool = True

    def validate(self, value):
        if self.values is None:
            raise ValueError(f"must set 'values' to use {self}")
        if self.case_sensitive:
            value = value.upper()
            valid = (v.upper() for v in self.values)
        else:
            valid = self.values

        if value not in valid:
            raise ValueError(f"value '{value}' not one of the enum values '({','.join(self.values)})'")
            
        return value


class BytesEnum(EnumString):
    type = bytes


class UnicodeEnum(EnumString):
    type = str


class CaselessBytesEnum(BytesEnum):
    case: bool = False
    
    def validate(self, value):
        warn('CaselessBytesEnum is deprecated - use BytesEnum(case=False)',
             LabbenchDeprecationWarning)
        return super().validate(value)


class CaselessStrEnum(BytesEnum):
    case: bool = False
    
    def validate(self, value):
        warn('CaselessStrEnum is deprecated - use UnicodeEnum(case=False)',
             LabbenchDeprecationWarning)    
        return super().validate(value)


class TCPAddress(Unicode):
    def validate(self, value):        
        ipaddress.ip_address(value)
        return super().validate(value)        

    
def observe(obj, handler, **kws):
    if 'names' in kws or 'type' in kws:
        warn('the "names" and "type" arguments are deprecated',
             LabbenchDeprecationWarning)
    if isinstance(obj, HasTraits):
        obj.__notify_list__.append(handler)
    elif isinstance(obj, Device):
        observe(obj.state, handler)
        observe(obj.settings, handler)
    else:
        raise TypeError('object to observe must be a Device, State, or Settings instance')


def unobserve(obj, handler):
    if isinstance(obj, HasTraits):
        obj.__notify_list__.remove(handler)
    elif isinstance(obj, Device):
        unobserve(obj.state, handler)
        unobserve(obj.settings, handler)
    else:
        raise TypeError('object to observe must be a Device, State, or Settings instance')        


def setter(func):
    ''' Use this decorator to apply a setter function to a trait with the
        same name. For example,
        
        ```python
        class MyDevice(lb.Device):
            param = lb.Int(min=0)
            
            @lb.getter
            def param(self, value):
                return self.write(f'GETMYPARAM {value}')
        ```
        
        The trait needs to be defined before the setter function as shown.
    '''
    
    frame = inspect.currentframe()
    try:
        try:
            trait = frame.f_back.f_locals[func.__name__]
        except KeyError:
            msg = f'to define a setter for {func.__name__}, define a trait above with the same name'
            raise NameError(msg)
        if not isinstance(trait, Trait):
            raise TypeError('expected "{func.__name__}" to be a trait instance, but it is of type "{type(trait).__qualname__}"')
        trait.__setter__ = func
    finally:
        del frame
    return trait

def getter(func):
    ''' Use this decorator to apply a getter function to a trait with the
        same name. For example,
        
        ```python
        class MyDevice(lb.Device):
            param = lb.Int(min=0)
            
            @lb.getter
            def param(self):
                return self.query('GETMYPARAM?')
        ```
        
        The trait needs to be defined before the getter function as shown.
    '''
    frame = inspect.currentframe()
    try:
        try:
            trait = frame.f_back.f_locals[func.__name__]
        except KeyError:
            msg = f'to define a setter for {func.__name__}, define a trait above with the same name'
            raise NameError(msg)
        if not isinstance(trait, Trait):
            raise TypeError('expected "{func.__name__}" to be a trait instance, but it is of type "{type(trait).__qualname__}"')
        trait.__getter__ = func
    finally:
        del frame
    return trait


class HasTraitsMeta(type):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        cls.__traits__ = dict(((k,v) for k,v in cls.__dict__.items()\
                                    if isinstance(v,Trait)))

    def __iter__ (cls):
        return iter(dict(cls.__traits__).items())        
        
    def __getattr__ (cls, name):
        if name == 'class_traits':
            clsname = cls.__qualname__
            warn(f"{clsname}.class_traits() is deprecated - use dict({clsname})",
                  LabbenchDeprecationWarning)
            func = lambda: dict(cls.__traits__)
            return func    
        elif name == 'getter':
            def func(f):
                cls.__get_state__ = f                
            clsname = cls.__qualname__
            warn(f"@{clsname}.getter() is deprecated, use lb.getter() instead",
                  LabbenchDeprecationWarning)
            return func
        elif name == 'setter':
            def func(f):
                cls.__set_state__ = f                
            clsname = cls.__qualname__
            warn(f"@{clsname}.setter() is deprecated, use @lb.setter() instead",
                  LabbenchDeprecationWarning)
            return func
        
        else:
            raise AttributeError(f"'{cls.__qualname__}' object has no attribute '{name}'")


class HasTraits(metaclass=HasTraitsMeta):
    __notify_list__ = []

    def __init__ (self):
        self.__post_init__()

    def __post_init__(self):
        self.__notify_list__ = []

    def __setattr__ (self, name, value):
        ''' Raise an exception for new attributes to avoid assignment mistakes
        '''
        if name.startswith('_') or name in self.__traits__: 
            super().__setattr__(name, value)
        else:
            clsname = self.__class__.__qualname__
            raise AttributeError(f"'{clsname}' object has no attribute '{name}'")

    def __getattr__ (self, attr):
        ''' Special cases for some deprecated attributes from the Traitlets days
        '''
        if attr == 'observe':
            clsname = self.__class__.__qualname__
            warn(f"{clsname}.observe(handler) is deprecated - use lb.observe({clsname},handler)",
                  LabbenchDeprecationWarning)
            func = lambda handler: observe(self, handler)
            functools.update_wrapper(func, observe)
            return func
        elif attr == 'unobserve':
            clsname = self.__class__.__qualname__
            warn(f"{clsname}.unobserve(handler) is deprecated - lb.observe({clsname},handler)",
                  LabbenchDeprecationWarning)
            func = lambda handler: unobserve(self, handler)
            functools.update_wrapper(func, unobserve)
            return func
        elif attr == 'traits':
            clsname = self.__class__.__qualname__
            warn(f"{clsname}.traits() is deprecated, use dict({clsname}) instead",
                  LabbenchDeprecationWarning)
            func = lambda: dict(self.__traits__)
            functools.update_wrapper(func, self.__iter__)
            return func
        else:
            clsname = self.__class__.__qualname__
            raise AttributeError(f"'{clsname}' object has no attribute '{attr}'")
        
    def __iter__ (self):
        return iter(dict(self.__traits__).items())
    
    def __getitem__ (self, name):
        ''' Get the instance of the Trait named class (as opposed to
            __getattr__, which fetches its value).
        '''
        return self.__traits__[name]
    
    def __dir__ (self):
        return iter(self.__traits__.keys())

    def __set_state__ (self, trait, value):
        pass

    def __get_state__ (self, trait):
        return trait.default_value if trait.previous is Undefined else trait.previous

    def __notify__ (self, name, value, type):
        msg = dict(new=value,
                   old=self[name].previous,
                   owner=self,
                   name=name,
                   type=type)

        for handler in self.__notify_list__:
            handler(dict(msg))

    @classmethod
    def __new_trait__ (cls, name, trait):
        setattr(cls, name, trait)
        cls.__traits__[name] = trait
        trait.__set_name__(cls, name)


class Settings(HasTraits):
    @classmethod
    def define(cls, **kws):
        for k,v in kws.items():
            if k in cls.__traits__:
                setattr(cls, k, v)
            else:
                raise AttributeError(f"no trait {k} in '{cls.__qualname__}'")
        return cls


class State(HasTraits):
    def __init__ (self, owner):
        self.__device__ = owner
        self.__post_init__()

    def __set_state__ (self, trait, value):        
        if trait.command is None:
            raise AttributeError(f'define {trait} with the command argument to set the state by command')
        if self.__device__.__set_state__ is None:
            raise AttributeError(f'implement {self.__owner.__qualname__}.__get_state__ to set the state')
            
        super().__set_state__(trait, value)
        
        self.__device__.__set_state__(trait.command, value)
        
    def __get_state__ (self, trait):
        super().__get_state__(trait)
        if trait.command is None:
            raise AttributeError(f'define {trait} with the command argument to get the state by command')
        if self.__device__.__get_state__ is None:
            raise AttributeError(f'must set trait.command to implement a setter by commmand')
            
        return self.__device__.__get_state__(trait.command)


class DisconnectedBackend(object):
    ''' "Null Backend" implementation to raises an exception with discriptive
        messages on attempts to use a backend before a Device is connected.
    '''

    def __init__(self, dev):
        ''' dev may be a class or an object for error feedback
        '''
        self.__dev__ = dev

    def __getattribute__(self, key):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            if inspect.isclass(self.__dev__):
                name = self.__dev__.__name__
            else:
                name = type(self.__dev__).__name__
            raise ConnectionError(
                'need to connect first to access backend.{key} in {clsname} instance (resource={resource})'
                .format(key=key, clsname=name, resource=self.__dev__.settings.resource))

    def __repr__(self):
        return 'DisconnectedBackend()'


class DeviceLogAdapter(logging.LoggerAdapter):
    """
    This example adapter expects the passed in dict-like object to have a
    'connid' key, whose value in brackets is prepended to the log message.
    """

    def process(self, msg, kwargs):
        return '%s - %s' % (self.extra['device'], msg), kwargs


def __get_state__(obj, trait):
    ''' Implement a default state getter in a sub for all traits in
        `self.state`. This is usually implemented in a subclass by keys
        in each trait, accessed here as `trait.command`. This is only
        triggered if the trait is defined with `trait.command is not None`.
        
        A common use is in message-based communication, such as
        SCPI, that supports a common string format
        for getting parameter values that includes a command string.

        :param str command: the command message to apply to `value`
        :param trait: the state descriptor or traitlet
        :returns: the value retrieved from the instrument
    '''
    raise CommandNotImplementedError(
        'state "{attr}" is defined but not implemented! implement {cls}.command_set, or implement a setter for {cls}.state.{attr}'
        .format(cls=type(obj).__name__, attr=trait))

def __set_state__(obj, trait, value):
    ''' Apply an instrument setting to the instrument, keyed on a command string.
        Implement this for message-based protocols, like VISA SCPI or some serial devices.

        :param str command: the command message to apply to `value`
        :param trait: the state descriptor or traitlet
        :param value: the value to set
    '''
    raise CommandNotImplementedError(
        'state "{attr}" is defined but not implemented! implement {cls}.command_get, or implement a getter for {cls}.state.{attr}'
        .format(cls=type(obj).__name__, attr=trait))


class DeviceMeta(type):
    ''' Makes automatic adjustments to the Device class when it (or any of its
        subclasses) is defined
    '''
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)

        def add_state_traits():
            ''' Add traits defined in the Device class to its .state
            '''
            for k,v in dict(cls.__dict__).items():
                if isinstance(v, Trait):
                    cls.state.__new_trait__(k, v)
                    delattr(cls, k)

        def add_settings_annotations():
            ''' Add annotations defined in the Device class to its .settings
            '''
            
            if not hasattr(cls, '__annotations__'):
                return

            for name, trait in getattr(cls, '__annotations__', {}).items():
                cls.settings.__new_trait__(name, trait)
            del cls.__annotations__
                   

        def subclass(name, expected_parent_cls):
            ''' Make cls.state and cls.settings subclasses of the parent class
                state or settings if they are not already.
            '''
            member_cls = getattr(cls, name)
            
            if not issubclass(member_cls, expected_parent_cls):
                raise TypeError(f'"{member_cls}" must be a subclass of "{expected_parent_cls}"')
                
            new_member_cls = type(member_cls.__name__,
                                  (member_cls,)+member_cls.__bases__,
                                  dict(member_cls.__dict__))
            
            new_member_cls.__qualname__ = cls.__qualname__ + '.' + new_member_cls.__name__
            setattr(cls, name, new_member_cls)

        def update_doc():
            if cls.__doc__:
                cls.__doc__ = trim(cls.__doc__)
            else:
                cls.__doc__ = ''
                
            if not cls.__init__.__doc__:
                cls.__init__.__doc__ = ''
    
            txt = '\n\n'.join((f":{t.name}: {t.doc()}" for k,t in cls.settings))

            cls.__init__.__doc__ += '\n\n' + txt
            cls.__doc__ += '\n\n'+txt

        subclass('state', State)
        subclass('settings', Settings)

        add_settings_annotations()

        defaults = dict(((k,v.default_value) for k,v in cls.settings if not v.read_only))
        types = dict(((k,v.type) for k,v in cls.settings if not v.read_only))

        wrap_dynamic_init(cls, tuple(defaults.keys()), defaults, 1, types)

        add_state_traits()
        update_doc()


class Device(metaclass=DeviceMeta):
    r'''`Device` is the base class common to all labbench
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
                * CommandLineWrapper exposes a threaded pipes backend for command line tools
                * Serial exposes a pyserial backend for serial port communication
                * DotNetDevice exposes a pythonnet for wrapping dotnet libraries

            (and others). If you are implementing a driver that uses one of
            these backends, inherit from the corresponding class above, not
            `Device`.
            
            
        Settings
        ************************
    '''
    
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
    settings = Settings
    
    resource: \
        Unicode(allow_none=True,
                help='URI for device connection, formatted according to subclass implementation')
        
    concurrency_support: \
        Bool(True, read_only=True,
             help='`True` if this backend supports threading')

    ''' Container for state traits in a Device. Getting or setting state traits
        triggers live updates: communication with the device to get or set the
        value on the Device. Therefore, getting or setting state traits
        needs the device to be connected.

        To set a state value inside the device, use normal python assigment::

            device.state.parameter = value
            
        To get a state value from the device, you can also use it as a normal python variable::
        
            variable = device.state.parameter + 1
    '''
    state = State
    connected = Bool(help='whether the :class:`Device` instance is connected')

    @getter
    def connected(self):
        return not isinstance(self.backend, DisconnectedBackend)

    backend = DisconnectedBackend(None)
    ''' .. this attribute is some reference to a controller for the device.
        it is to be set in `connect` and `disconnect` by the subclass that implements the backend.
    '''

    # Backend classes may optionally overload these, and do not need to call the parents
    # defined here
    def connect(self):
        ''' Backend implementations overload this to open a backend
            connection to the resource.
        '''
        pass

    def disconnect(self):
        ''' Backend implementations must overload this to disconnect an
            existing connection to the resource encapsulated in the object.
        '''
        self.backend = DisconnectedBackend(self)
        self.state.connected

    __get_state__ = __get_state__    
    __set_state__ = __set_state__
    __warn_state_names__ = []
    __warn_settings_names__ = []
    
    def __init__ (self, **kws):
        ''' Apply initial settings here, then invoke `connect()` to use the driver.
        '''
        self.settings = self.settings()
        for k,v in kws.items():
            setattr(self.settings, k, v)
        self.state = self.state(self)

        self.__wrapped__ = {}

        # Instantiate state, and observe connection state
        self.settings = self.settings(self)

        self.__imports__()
        
        self.backend = DisconnectedBackend(self)
        self.logger = DeviceLogAdapter(logger, {'device': repr(self)})

        # Instantiate state now. It needs to be here, after settings are fully
        # instantiated, in case state implementation depends on settings
        self.state = self.state(self)

        wrap(self, 'connect', self.__connect_wrapper__)
        wrap(self, 'disconnect', self.__disconnect_wrapper__)
        
        self.__warn_state_names__ = self.state.trait_names()
        self.__warn_settings_names__ = self.settings.trait_names()

    def __setattr__(self, name, value):
        ''' Throw warnings if we suspect a typo on an attempt to assign to a state
            or settings trait
        '''
        if not hasattr(self, name):
            if name in self.__warn_state_names__:
                msg = f'{self}: assigning to a new attribute {name} -- did you mean to assign to the trait state.{name} instead?'
                warn(msg)
            if name in self.__warn_settings_names__:
                msg = f'{self}: assigning to a new attribute {name} -- did you mean to assign to the trait settings.{name} instead?'
                warn(msg)
        super().__setattr__(name, value)

    def __getattr__(self, name):
        ''' Throw warnings if we suspect a typo on an attempt to access a state
            or settings trait
        '''
        if name in self.__warn_state_names__:
            msg = f'{self}: did you mean to access the trait state.{name} instead?'
            warn(msg)                   
        if name in self.__warn_settings_names__:
            msg = f'{self}: did you mean to access the trait in settings.{name} instead?'
            warn(msg)
        raise AttributeError(f"'{self.__class__.__qualname__}' object has no attribute '{name}'")

    def __connect_wrapper__(self, *args, **kws):
        ''' A wrapper for the connect() method. It steps through the
            method resolution order of self.__class__ and invokes each connect()
            method, working down from labbench.Device and working down
        '''
        if self.state.connected:
            self.logger.debug('{} already connected'.format(repr(self)))
            return

        self.backend = None

        for connect in trace_methods(self.__class__, 'connect', Device)[::-1]:
            connect(self)

        # Force an update to self.state.connected
        self.state.connected

    def __disconnect_wrapper__(self, *args, **kws):
        ''' A wrapper for the disconnect() method that runs
            cleanup() before calling disconnect(). disconnect()
            will still be called if there is an exception in cleanup().
        '''
        # Try to run cleanup(), but make sure to run
        # disconnect() even if it fails
        if not self.state.connected:
            self.logger.debug('{} already disconnected'.format(repr(self)))
            return

        methods = trace_methods(self.__class__, 'disconnect', Device)

        all_ex = []
        for disconnect in methods:
            try:
                disconnect(self)
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
                    '(Exception suppressed to continue disconnect)\n\n')

        self.state.connected

        self.logger.debug('{} disconnected'.format(repr(self)))

    def __imports__(self):
        pass

    def __enter__(self):
        try:
            self.connect()
            return self
        except BaseException as e:
            args = list(e.args)
            if len(args) > 0:
                args[0] = '{}: {}'.format(repr(self), str(args[0]))
                e.args = tuple(args)
            raise e

    def __exit__(self, type_, value, traceback):
        try:
            self.disconnect()
        except BaseException as e:
            args = list(e.args)
            args[0] = '{}: {}'.format(repr(self), str(args[0]))
            e.args = tuple(args)
            raise e

    def __del__(self):
        self.disconnect()

    def __repr__(self):
        return '{}({})'.format(type(self).__name__,
                               repr(self.settings.resource))

    __str__ = __repr__