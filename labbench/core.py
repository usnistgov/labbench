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
This implementation is deeply intertwined with low-level internals of
traitlets and obscure details of the python object model. Consider reading
the documentation closely and inheriting these objects instead of
reverse-engineering this code.
'''

from . import util

from collections import OrderedDict
from textwrap import dedent

import traitlets
import inspect
import logging
import copy
import sys
import traceback
from traitlets import All, Undefined, TraitType

__all__ = ['ConnectionError', 'DeviceException', 'DeviceNotReady', 'DeviceFatalError', 
           'DeviceConnectionLost', 'Undefined', 'All', 'DeviceStateError',
           'Int', 'Float', 'Unicode', 'Complex', 'Bytes', 'CaselessBytesEnum',
           'Bool', 'List', 'Dict', 'TCPAddress',
           'CaselessStrEnum', 'Device', 'list_devices', 'logger', 'CommandNotImplementedError',
           ]

logger = logging.getLogger('labbench')


class ConnectionError(traitlets.TraitError):
    """ Failure on attempt to connect to a device
    """


class DeviceStateError(traitlets.TraitError):
    """ Failure to get or set a state in `Device.state`
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


class MetaHasTraits(traitlets.MetaHasTraits):
    """A metaclass for documenting HasTraits."""

    def setup_class(cls, classdict):
        super().setup_class(classdict)

        cls.__rawdoc__ = cls.__doc__

        if cls.__doc__ is None:
            # Find the documentation for HasTraits
            for subcls in cls.__mro__[1:]:
                if hasattr(subcls, '__rawdoc__'):
                    if subcls.__rawdoc__:
                        doc = subcls.__rawdoc__.rstrip()
                        break
                else:
                    doc = ''
                    break
        else:
            doc = cls.__doc__

        cls.__doc__ = '\n\n'.join([str(doc), cls._doc_traits()])


class HasTraits(traitlets.HasTraits, metaclass=MetaHasTraits):
    '''
        Base class for accessing the local and remote state
        parameters of a device.  Normally,
        a device driver implemented as a :class:`Device` subclass
        should add driver-specific states by subclassing this class.

        Instantiating :class:`Device` (or one of its subclasses)
        automatically instantiate this class as well.
    '''

    _device = None
    __attributes__ = dir(traitlets.HasTraits())

    def __init__(self, device, *args, **kws):
        self._device = device
        super(traitlets.HasTraits, self).__init__(*args, **kws)

    def __getter__(self, trait):
        raise CommandNotImplementedError

    def __setter__(self, trait, value):
        raise CommandNotImplementedError

    @classmethod
    def _doc_traits(cls):
        '''
        :return: a dictionary of documentation for this class's traits
        '''
        ret = ['\n\ntrait attributes:']
        traits = cls.class_traits()

        for name in sorted(traits.keys()):
            trait = traits[name]
            ret.append('* `{name}`: `{type}`'
                       .format(help=trait.help,
                               type=trait.__class__.__name__,
                               name=name))

        return '\n\n'.join(ret)


class HasSettingsTraits(HasTraits):
    @classmethod
    def define(cls, **kws):
        ''' Change default values of the settings in parent settings, without redefining the
            full class. redefined according to each keyword argument. For example::

                MyInstrumentClass.settings.define(parameter=7)

            changes the default value of the `parameter` setting in `MyInstrumentClass.settings` to `7`.
            This is a convenience function to avoid completely redefining `parameter` if it was defined
            in a parent class of `MyInstrumentClass`.
        '''

        # Dynamically define the result to be a new subclass
        newcls = type('settings', (cls,), {})

        traits = cls.class_traits()

        for k, v in kws.items():
            if k not in traits:
                raise traitlets.TraitError('cannot set default value of undefined trait {}'
                                           .format(k))
            trait = copy.copy(traits[k])
            trait.default_value = v
            setattr(newcls, k, trait)

        return newcls

    def __setattr__(self, key, value):
        ''' Prevent silent errors that could result from typos in state names
        '''
        exists = hasattr(self, key)

        # Need to check self.__attributes__ because traitlets.HasTraits.__init__ may not
        # have created attributes it needs yet
        if key not in self.__attributes__ and not exists:
            name = str(self)[1:].split(' ', 1)[0]
            msg = "{} has no '{}' setting defined".format(name, key)
            raise AttributeError(msg)
        if exists and not key.startswith('_') and callable(getattr(self, key)):
            name = str(self)[1:].split(' ', 1)[0]
            msg = "{} attribute '{}' is a method, not a setting. call as a function it instead"\
                .format(name, key)
            raise AttributeError(msg)
        super(HasSettingsTraits, self).__setattr__(key, value)


class HasStateTraits(HasTraits):
    @classmethod
    def setter(cls, func):
        ''' Use this as a decorator to define a setter function for all traits
            in this class. The setter should take two arguments: the instance
            of the trait to get, and the value to set. It should perform any
            operation needed to apply the given value to the trait's state
            in `self._device`. One example is to send a command defined by
            trait.command.

            Any return value from the function is ignored.

            A trait that has its own setter defined will ignore this
            one.

        '''
        cls.__setter__ = func
        return cls

    @classmethod
    def getter(cls, func):
        ''' Use this as a decorator to define a setter function for all traits
            in this class. The getter should take one argument: the instance
            of the trait to get. It should perform any
            operation needed to retrieve the current value of the device state
            corresponding to the supplied trait, using `self._device`.

            One example is to send a command defined by
            trait.command.

            The function should return a value that is the state from the
            device.

            A trait that has its own getter defined will ignore this
            one.
        '''
        cls.__getter__ = func
        return cls

    def __setattr__(self, key, value):
        ''' Prevent silent errors that could result from typos in state names
        '''

        exists = hasattr(self, key)

        # Need to check self.__attributes__ because traitlets.HasTraits.__init__ may not
        # have created attributes it needs yet
        if key not in self.__attributes__ and not exists:
            name = str(self)[1:].split(' ', 1)[0]
            msg = "{} has no '{}' state definition".format(name, key)
            raise AttributeError(msg)
        if exists and not key.startswith('_') and callable(getattr(self, key)):
            name = str(self)[1:].split(' ', 1)[0]
            msg = "{} attribute '{}' is a method, not a state. call as a function it instead"\
                .format(name, key)
            raise AttributeError(msg)
        super(HasStateTraits, self).__setattr__(key, value)


class TraitMixIn(object):
    ''' Includes added mix-in features for device control into traitlets types:
        - If the instance is an attribute of a HasStateTraits class, there are hooks for
          live synchronization with the remote device by sending or receiving data.
          Implement with one of
          * `getter` and/or `setter` keywords in __init__ to pass in a function;
          *  metadata passed in through the `command` keyword, which the parent
             HasStateTraits instance may use in its own `getter` and `setter`
             implementations
        - Adds metadata for autogenerating documentation (see `doc_attrs`)

        Order is important - the class should inherit TraitMixIn first and the
        desired traitlet type second.

        class LabbenchType(TraitMixIn,traitlets.TraitletType):
            pass
    '''

    doc_attrs = 'command', 'read_only', 'write_only', 'remap', 'cache'
    default_value = traitlets.Undefined
    write_only = False
    cache = False
    read_only_if_connected = False

    def __init__(self, default_value=Undefined, allow_none=False, read_only=None, help=None,
                 write_only=None, cache=None, command=None, getter=None, setter=None,
                 remap={}, **kwargs):

        def make_doc():
            attr_pairs = []
            for k in self.doc_attrs:
                v = getattr(self, k)
                if (k=='default_value' and v!=Undefined)\
                   and v is not None\
                   and not (k=='allow_none' and v==False)\
                   and not (k=='remap' and v=={}):
                    attr_pairs.append('{k}={v}'.format(k=k, v=repr(v)))
            params = {'name': type(self).__name__,
                      'attrs': ','.join(attr_pairs),
                      'help': self.help}
            sig = '{name}({attrs})\n\n\t{help}'.format(**params)
            sig = sig.replace('*', r'\*')
            if self.__doc__:
                sig += self.__doc__
            return sig

        # Identify the underlying class from Trait
        for c in inspect.getmro(self.__class__):
            if issubclass(c, TraitType) \
                    and not issubclass(c, TraitMixIn):
                self._parent = c
                break
        else:
            raise Exception(
                'could not identify any parent Trait class')

        # Work around a bug in traitlets.List as of version 4.3.2
        if isinstance(self, traitlets.Container)\
           and default_value is not Undefined:
            self.default_value = default_value

        super(TraitMixIn, self).__init__(default_value=default_value,
                                         allow_none=allow_none,
                                         read_only=read_only,
                                         help=help, **kwargs)

        if read_only == 'connected':
            read_only = False
            self.read_only_if_connected = True
        if write_only is not None:
            self.write_only = write_only
        if cache is not None:
            self.cache = cache
        if not isinstance(remap, dict):
            raise TypeError('remap must be a dictionary')

        self.command = command
        self.__last = None

        self.tag(setter=setter,
                 getter=getter)

        self.remap = remap
        self.remap_inbound = dict([(v, k) for k, v in remap.items()])

        self.info_text = self.__doc__ = make_doc()

    def get(self, obj, cls=None):
        ''' Overload the traitlet's get method. If `obj` is a HasSettingsTraits, call HasTraits.get
            like normal. Otherwise, this is a HasStateTraits, and inject a call to do a `set` from the remote device
        '''
        # If this is Device.settings instead of Device.state, do simple Trait.get,
        # skipping any communicate with the device
        if isinstance(obj, HasSettingsTraits):
            return self._parent.get(self, obj, cls)
        elif not isinstance(obj, HasStateTraits):
            raise TypeError('obj (of type {}) must be an instance of HasSettingsTraits or HasStateTraits'
                            .format(type(obj)))

        # If self.write_only, bail if we haven't cached the value
        if self.write_only and self.__last is None:
            raise traitlets.TraitError(
                'tried to get state value, but it is write-only and has not been set yet')

        # If self.write_only or we are caching, return a cached value
        elif self.write_only or (self.cache and self.__last is not None):
            return self.__last

        # First, look for a getter function or method that implements getting
        # the value from the device
        if callable(self.metadata['getter']):
            new = self.metadata['getter'](obj._device)

        # If there is no getter function, try calling the command_get() method in the Device instance.
        # Otherwise, raise an exception, because we don't know how to get the
        # value from the Device.
        else:  # self.command is not None:
            try:
                new = obj.__class__.__getter__(obj._device, self)
            except CommandNotImplementedError as e:
                raise DeviceStateError(
                    'no command or getter defined - cannot get state from device')

        # Remap the resulting value.
        new = self.remap_inbound.get(new, new)

        # Apply the value with the parent traitlet class.
        self._parent.set(self, obj, new)
        return self._parent.get(self, obj, cls)

    def set(self, obj, value):
        ''' Overload the traitlet's get method to inject a call to a
            method to set the state on a remote device.
        '''
        assert isinstance(obj, HasTraits)

        # If this is Device.settings instead of Device.state, do simple Trait.set,
        # skipping any communicate with the device
        if isinstance(obj, HasSettingsTraits):
            return self._parent.set(self, obj, value)

        # Trait.set already implements a check for self.read_only, so we don't
        # do that here.

        # Make sure the (potentially remapped) value meets criteria defined by
        # this traitlet subclass
        value = self.validate(obj, value)

        # Remap the resulting value to the remote value
        value = self.remap.get(value, value)

        # First, look for a getter function or method that implements getting
        # the value from the device
        if callable(self.metadata['setter']):
            self.metadata['setter'](obj._device, value)

        # If there isn't one, try calling the command_get() method in the Device instance.
        # Otherwise, raise an exception, because we don't know how to get the
        # value from the Device.
        else:  # self.command is not None:
            # try:
            # The below should raise CommandNotImplementedError if no command
            # or setter has been defined

            obj.__class__.__setter__(obj._device, self, value)
            # except CommandNotImplementedError as e:
            #     raise DeviceStateError(
            #         'no command or setter defined - cannot set state to device')

        # Apply the value to the traitlet, saving the cached value if necessary
        rd_only, self.read_only = self.read_only, False
        self._parent.set(self, obj, value)
        if self.cache or self.write_only:
            self.__last = self._parent.get(self, obj, self._parent)
        self.read_only = rd_only

    def setter(self, func, *args, **kws):
        self.metadata['setter'] = func
        return self

    def getter(self, func, *args, **kws):
        self.metadata['getter'] = func
        return self


class Int(TraitMixIn, traitlets.CInt):
    ''' Trait for an integer value, with type and bounds checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
        :param min: lower bound for the value
        :param max: upper bound for the value
    '''
    doc_attrs = ('min', 'max') + TraitMixIn.doc_attrs


class CFLoatSteppedTraitlet(traitlets.CFloat):
    ''' Trait for a quantized floating point value, with type and bounds checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
        :param min: lower bound for the value
        :param max: upper bound for the value
        :param step: resolution of the floating point values                
    '''    
    def __init__(self, *args, **kws):
        self.step = kws.pop('step', None)
        super(CFLoatSteppedTraitlet, self).__init__(*args, **kws)


class Float(TraitMixIn, CFLoatSteppedTraitlet):
    ''' Trait for a floating point value, with type and bounds checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
        :param min: lower bound for the value
        :param max: upper bound for the value        
    '''    

    doc_attrs = ('min', 'max', 'step') + TraitMixIn.doc_attrs

    def validate(self, obj, value):
        value = super(Float, self).validate(obj, value)

        # Round to nearest increment of step
        if self.step:
            value = round(value / self.step) * self.step
        return value


class Unicode(TraitMixIn, traitlets.CUnicode):
    ''' Trait for a Unicode string value, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''    

    default_value = ''


class Complex(TraitMixIn, traitlets.CComplex):
    ''' Trait for a complex numeric value, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''    


class Bytes(TraitMixIn, traitlets.CBytes):
    ''' Trait for a byte string value, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''    

class TCPAddress(TraitMixIn, traitlets.TCPAddress):
    ''' Trait for a (address, port) TCP address tuple value, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''    


class List(TraitMixIn, traitlets.List):
    ''' Trait for a python list value, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''

    default_value = []


class EnumBytesTraitlet(traitlets.CBytes):
    ''' Trait for an enumerated list of valid byte string values, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''

    def __init__(self, values=[], case_sensitive=False, **kws):
        if len(values) == 0:
            raise ValueError('Must define at least one enum value')

        self.values = [bytes(v) for v in values]
        self.case_sensitive = case_sensitive
        if case_sensitive:
            self.values = [v.upper() for v in self.values]

        self.info_text = 'castable to ' + \
                         ', '.join([repr(v) for v in self.values]) + \
                         ' (case insensitive)' if not case_sensitive else ''

        super(EnumBytesTraitlet, self).__init__(**kws)

    def validate(self, obj, value):
        try:
            value = bytes(value)
        except BaseException:
            self.error(obj, value)
        if self.case_sensitive:
            value = value.upper()
        if value not in self.values:
            self.error(obj, value)
        return value

    def devalidate(self, obj, value):
        return self.validate(obj, value)


class CaselessBytesEnum(TraitMixIn, EnumBytesTraitlet):
    ''' Trait for an enumerated list of valid case-insensitive byte string values, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
        :param values: An iterable of valid byte strings to accept
        :param case_sensitive: Whether to be case_sensitive
    '''

    doc_attrs = ('values', 'case_sensitive') + TraitMixIn.doc_attrs


class CaselessStrEnum(TraitMixIn, traitlets.CaselessStrEnum):
    ''' Trait for an enumerated list of valid case-insensitive unicode string values, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
        :param values: An iterable of valid unicode strings to accept
    '''

    doc_attrs = ('values',) + TraitMixIn.doc_attrs


class Dict(TraitMixIn, traitlets.Dict):
    ''' Trait for a python dict value, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''


# class BoolTraitlet(traitlets.CBool):
    # def __init__(self, trues=[True], falses=[False], **kws):
    #     self._trues = [v.upper() if isinstance(v, str) else v for v in trues]
    #     self._falses = [v.upper() if isinstance(v, str) else v for v in falses]
    #     super(BoolTraitlet, self).__init__(**kws)
    #
    # def validate(self, obj, value):
    #     if isinstance(value, str):
    #         value = value.upper()
    #     if value in self._trues:
    #         return True
    #     elif value in self._falses:
    #         return False
    #     elif not isinstance(value, numbers.Number):
    #         raise ValueError(
    #             'Need a boolean or numeric value to convert to integer, but given {} instead' \
    #                 .format(repr(value)))
    #     try:
    #         return bool(value)
    #     except:
    #         self.error(obj, value)
    #
    # # Convert any castable value
    # # to the first entry in self._trues or self._falses
    # def devalidate(self, obj, value):
    #     if self.validate(obj, value):
    #         return self._trues[0]
    #     else:
    #         return self._falses[0]
    #
    # default_value = False


class Bool(TraitMixIn, traitlets.CBool):
    ''' Trait for a python boolean, with type checking.

        :param default_value: initial value (in `settings` only, not `state`)
        :param allow_none: whether to allow pythonic `None` to represent a null value
        :param read_only: True if this should not accept a set (write) operation
        :param write_only: True if this should not accept a get (read) operation (in `state` only, not `settings`)
        :param cache: True if this should only read from the device once, then return that value in future calls (in `state` only, not `settings`)
        :param getter: Function or other callable (no arguments) that retrieves the value from the remote device, or None (in `state` only, not `settings`)
        :param setter: Function or other callable (one `value` argument) that sets the value from the remote device, or None (in `state` only, not `settings`)
        :param remap: A dictionary {python_value: device_representation} to use as a look-up table that transforms python representation into the format expected by a device
    '''

    default_value = False


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


class DeviceMetaclass(type):
    ''' Dynamically adjust the class documentation strings to include the traits
        defined in its settings. This way we get the documentation without
        error-prone copy and paste.
    '''
    def __init__(cls, name, bases, namespace):
        def autocomplete_wrapper(func, args, kws):
            all_ = ','.join(args + [k + '=' + k for k in kws.keys()])
            kws = dict(kws, __func__=func)
            expr = "lambda {a},*args,**kws: __func__({a},*args,**kws)".format(
                a=all_)
            wrapper = eval(expr, kws, {})
            for attr in '__name__', '__doc__', '__module__', '__qualname__':
                setattr(wrapper, attr, getattr(func, attr))
            return wrapper
        
        def autosubclass(name, expected_parent_cls):
            ''' Make cls.state and cls.settings subclasses of the parent class
                state or settings, if they are not defined as subclasses.
            '''
            member_cls = getattr(cls, name)
            
            if len(member_cls.__mro__) == 2\
               and not isinstance(member_cls, expected_parent_cls):
                   parent_member_cls = getattr(cls.__mro__[1],name)
                   new_member_cls = type(member_cls.__name__,
                                         (parent_member_cls,),
                                         dict(member_cls.__dict__))
                   setattr(cls, name, new_member_cls)

        super(DeviceMetaclass, cls).__init__(name, bases, namespace)

        # Automatically make cls.state and cls.settings subclasses of the
        # parent class state or settings, if they are not defined as subclasses
        autosubclass('state', HasStateTraits)
        autosubclass('settings', HasSettingsTraits)

        traits = cls.settings.class_traits()

        # Skip read-only traits
        traits = OrderedDict([(n, t)
                              for n, t in traits.items() if not t.read_only])

        kws = OrderedDict(resource=traits['resource'].default_value)
        for name, trait in traits.items():
            if not trait.read_only:
                kws[name] = trait.default_value

        wrapped = cls.__init__
        cls.__init__ = autocomplete_wrapper(cls.__init__, ['self'], kws)
        #bind_wrapper_to_class(cls, '__init__')
        import functools
        functools.update_wrapper(cls.__init__, wrapped)
        cls.__init__.__doc__ = dedent(
            cls.__init__.__doc__) if cls.__init__.__doc__ else ''

        if cls.__doc__ is None:
            cls.__doc__ = ''
        else:
            cls.__doc__ = trim(cls.__doc__)

        for name, trait in traits.items():
            ttype, text = trait.info_text.split('\n\n',1)
            line = '\n\n:param `{type}` {name}:\n{info}'\
                   .format(help=trait.help,
                           type=ttype,
                           info=text,
                           name=name)

            cls.__init__.__doc__ += line
            cls.__doc__ += line


class Device(object, metaclass=DeviceMetaclass):
    r'''`Device` is the base class common to all labbench
        drivers. Inherit it to implement a backend, or a specialized type of
        driver.

        Drivers that subclass `Device` get

        * device connection management via context management (the `with` statement)
        * test state management for easy test logging and extension to UI
        * a degree automatic stylistic consistency between drivers

        :param resource: resource identifier, with type and format determined by backend (see specific subclasses for details)
        :param **local_states: set the local state for each supplied state key and value

        .. note::
            Use `Device` by subclassing it only if you are
            implementing a driver that needs a new type of backend.

            Several types of backends have already been implemented
            as part of labbench:

                * VISADevice exposes a pyvisa backend for VISA Instruments
                * CommandLineWrapper exposes a threaded pipes backend for command line tools
                * Serial exposes a pyserial backend for serial port communication
                * DotNetDevice exposes a pythonnet for wrapping dotnet libraries

            (and others). If you are implementing a driver that uses one of
            these backends, inherit from the corresponding class above, not
            `Device`.
    '''

    class settings(HasSettingsTraits):
        """ Container for settings traits in a Device.

            These settings
            are stored only on the host; setting or getting these values do not
            trigger live updates (or any communication) with the device. These
            define connection addressing information, communication settings,
            and options that only apply to implementing python support for the
            device.

            The device uses this container to define the keyword options supported
            by its __init__ function. These are applied when you instantiate the device.
            After you instantiate the device, you can still change the setting with::

                Device.settings.resource = 'insert-your-address-string-here'
        """

        resource = Unicode(allow_none=True,
                           help='Addressing information needed to make a connection to a device. Type and format are determined by the subclass implementation')
        concurrency_support = Bool(default_value=True, read_only=True,
                                   help='Whether this backend supports threading')

    class state(HasStateTraits):
        ''' Container for state traits in a Device. Getting or setting state traits
            triggers live updates: communication with the device to get or set the
            value on the Device. Therefore, getting or setting state traits
            needs the device to be connected.

            To set a state value inside the device, use normal python assigment::

                device.state.parameter = value
                
            To get a state value from the device, you can also use it as a normal python variable::
            
                variable = device.state.parameter + 1
        '''

        connected = Bool(read_only=True,
                         help='whether the :class:`Device` instance is connected')

    backend = DisconnectedBackend(None)
    ''' .. attribute::state is the backend that controls communication with the device.
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

#    def command_get(self, command, trait):
#        ''' Read a setting from a remote instrument, keyed on a command string.
#            Implement this for message-based protocols, like VISA SCPI or some serial devices.
#
#            :param str command: the command message to apply to `value`
#            :param trait: the state descriptor or traitlet
#            :returns: the value retrieved from the instrument
#        '''
#        raise CommandNotImplementedError(
#            'state "{attr}" is defined but not implemented! implement {cls}.command_set, or implement a setter for {cls}.state.{attr}'
#            .format(cls=type(self).__name__, attr=trait))
#
#    def command_set(self, command, trait, value):
#        ''' Apply an instrument setting to the instrument, keyed on a command string.
#            Implement this for message-based protocols, like VISA SCPI or some serial devices.
#
#            :param str command: the command message to apply to `value`
#            :param trait: the state descriptor or traitlet
#            :param value: the value to set
#        '''
#        raise CommandNotImplementedError(
#            'state "{attr}" is defined but not implemented! implement {cls}.command_get, or implement a getter for {cls}.state.{attr}'
#            .format(cls=type(self).__name__, attr=trait))

    def __init__(self, resource=None, **settings):
        self.__wrapped__ = {}

        # Instantiate state, and observe connection state
        self.settings = self.settings(self)

        self.__imports__()

        self.backend = DisconnectedBackend(self)

        # Set local settings according to local_states
        all_settings = self.settings.traits()

        for k, v in dict(settings, resource=resource).items():
            if k == 'resource' and resource is None:
                continue
            if k not in all_settings:
                raise KeyError('tried to set initialize setting {k}, but it is not defined in {clsname}.settings'
                               .format(k=repr(k), clsname=type(self).__name__))
            setattr(self.settings, k, v)

        self.__params = ['resource={}'.format(repr(self.settings.resource))] + \
                        ['{}={}'.format(k, repr(v))
                         for k, v in settings.items()]

        self.logger = DeviceLogAdapter(logger, {'device': repr(self)})

        # Instantiate state now. It needs to be here, after settings are fully
        # instantiated, in case state implementation depends on settings
        self.state = self.state(self)

        wrap(self, 'connect', self.__connect_wrapper__)
        wrap(self, 'disconnect', self.__disconnect_wrapper__)

    def __connect_wrapper__(self, *args, **kws):
        ''' A wrapper for the connect() method. It works through the
            method resolution order of self.__class__, starting from
            labbench.Device, and calls its connect() method.
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
            except BaseException as e:
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

    @state.connected.getter
    def __(self):
        return not isinstance(self.backend, DisconnectedBackend)

    __str__ = __repr__


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

    f = getouterframes(currentframe())[depth]

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

    return ret
