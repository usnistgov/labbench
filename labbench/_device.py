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

from functools import wraps
import inspect
import logging
import sys
import traceback

from . import util
from . import property as property_
from . import value

from ._traits import HasTraits, Trait, Undefined


__all__ = ['Device', 'list_devices', 'property', 'value', 'datareturn']


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


def list_devices(depth=1):
    """ Look for Device instances, and their names, in the calling
        code context (depth == 1) or its callers (if depth in (2,3,...)).
        Checks locals() in that context first.
        If no Device instances are found there, search the first
        argument of the first function argument, in case this is
        a method in a class.
    """
    from inspect import getouterframes, currentframe

    f = frame = currentframe()
    for i in range(depth):
        f = f.f_back
    try:
        ret = {
            k:v for k,v in list(f.frame.f_locals.items())
            if isinstance(v, Device)
        }

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


class DisconnectedBackend(object):
    """ "Null Backend" implementation to raises an exception with discriptive
        messages on attempts to use a backend before a Device is connected.
    """

    def __init__(self, dev):
        """ dev may be a class or an object for error feedback
        """
        if isinstance(dev, str):
            self.name = dev
        else:
            self.name = dev.__class__.__qualname__

    @util.hide_in_traceback
    def __getattr__(self, key):
        msg = f"open {self} first to access its backend"
        raise ConnectionError(msg)

    def __repr__(self):
        return 'DisconnectedBackend()'

    def __copy__ (self, memo=None):
        return DisconnectedBackend(self.name)

    str = __repr__
    __deepcopy__ = __copy__


@util.hide_in_traceback
def __init__():
    """ Wrapper function to call __init__ with adjusted function signature
    """

    # The signature has been dynamically replaced and is unknown. Pull it in
    # via locals() instead. We assume we're inside a __init__(self, ...) call.
    items = dict(locals())
    self = items.pop(next(iter(items.keys())))
    self.__init___wrapped(**items)


class Device(HasTraits, util.Ownable):
    r"""Base class for labbench driver wrappers in labbench. Subclass to
        implement driver APIs. """

    #     Drivers that subclass `Device` get

    #     * device connection management via context management (the `with` statement)
    #     * test property trait management for easy test logging and extension to UI
    #     * a degree automatic stylistic consistency between drivers

    #     .. note::
    #         This `Device` base class is a boilerplate object. It has convenience
    #         functions for device control, but no implementation.

    #         Implementation of protocols with general support for broad classes
    #         of devices are provided by other labbench Device subclasses:

    #             * VISADevice exposes a pyvisa backend for VISA Instruments
    #             * ShellBackend exposes a threaded pipes backend for command line tools
    #             * Serial exposes a pyserial backend for serial port communication
    #             * DotNetDevice exposes a pythonnet for wrapping dotnet libraries

    #         (and others). If you are implementing a driver that uses one of
    #         these backends, inherit from the corresponding class above, not
    #         `Device`.


    #     Value attributes
    #     ************************
    # """

    # """ Value traits.

    #     These are stored only within this class - accessing these traits in
    #     a Device instance do not trigger interaction with the device. These
    #     define connection addressing information, communication value traits,
    #     and options that only apply to implementing python support for the
    #     device.

    #     The device uses this container to define the keyword options supported
    #     by its __init__ function. These are applied when you instantiate the device.
    #     After you instantiate the device, you can still change the value trait with::

    #         Device.resource = 'insert-your-address-string-here'
    # """

    resource = value.str(allow_none=True, help='device address or URI')
    concurrency= value.bool(True, sets=False, help='True if the device supports threading')

    """ Container for property trait traits in a Device. Getting or setting property trait traits
        triggers live updates: communication with the device to get or set the
        value on the Device. Therefore, getting or setting property trait traits
        needs the device to be connected.

        To set a property trait value inside the device, use normal python assigment::

            device.parameter = value

        To get a property trait value from the device, you can also use it as a normal python variable::

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
        self.isopen

    __children__ = {}

    @classmethod
    @util.hide_in_traceback
    def __init_subclass__(cls, **value_defaults):
        super().__init_subclass__()

        for trait_name, new_default in value_defaults.items():
            
            trait = getattr(cls, trait_name, None)

            if trait is None or trait.role != Trait.ROLE_VALUE:
                parent_name = cls.__mro__[1].__qualname__
                raise AttributeError(f"there is no value trait {parent_name}.{trait_name}, cannot update its default")

            cls._traits[trait_name] = trait.copy(default=new_default)
            setattr(cls, trait_name, cls._traits[trait_name])

        if len(value_defaults)>0:
            super().__init_subclass__()

        # Generate a signature for documentation and code autocomplete
        params = [
            inspect.Parameter(
                'self',
                kind=inspect.Parameter.POSITIONAL_ONLY
            ),
            inspect.Parameter(
                'resource',
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=cls.resource.default,
                annotation=cls.resource.type
            )
        ]

        settable_values = {
            name: cls._traits[name]
            for name in cls._value_attrs
            if cls._traits[name].sets
        }

        params += [
            inspect.Parameter(
                name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=trait.default,
                annotation=trait.type
            )
            for name, trait in settable_values.items()
            if name != 'resource'
        ]

        cls.__doc__,cls.__doc_bare__ = getattr(cls, '__doc_bare__', cls.__doc__), cls.__doc__

        # apply signature and generate doc for each acceptable value
        cls.__init__.__signature__ = inspect.Signature(params)

        value_docs = ''.join((
            f"\t{t.doc()}\n"
            for t in settable_values.values()
        ))

        cls.__init__.__doc__ = f"Args:\n{value_docs}"

        properties = {
            name: cls._traits[name]
            for name in cls._property_attrs
            if cls._traits[name].sets
        }
        
        cls.__imports__()

    @classmethod
    def info(cls):
        clsname = cls.__qualname__

        ret = f"attributes of Device subclass {clsname}\n"

        unique_attrs = set(dir(cls)).difference(dir(Device))
        ret += "\nmethods:\n" + ''.join((
            f"\t{clsname}.{name}(...):\n\t{getattr(cls, name).__doc__}\n"
            for name in unique_attrs
            if not name.startswith('_') and inspect.ismethod(getattr(cls,name))
        ))

        ret += "value traits:\n" + ''.join((
            f"\t{clsname}.{getattr(cls, name).doc()}\n"
            for name in cls._value_attrs
        ))

        ret += "\nproperty traits:\n" + ''.join((
            f"\t{clsname}.{getattr(cls, name).doc()}\n"
            for name in cls._property_attrs
        ))

        if len(cls._datareturn_attrs) > 0:
            ret += "\ndatareturn traits:\n" + ''.join((
                f"\t{clsname}.{getattr(cls, name).doc()}\n"
                for name in cls._property_attrs
            ))

        return ret


    @property
    def _instname(self):
        if hasattr(self, '_console'):
            return self._console.extra['device']
        else:
            return None

    @_instname.setter
    def _instname(self, value):
        if value is not None:
            self._console.extra['device'] = value
            self._console.extra['origin'] = ' - '+value

    @util.hide_in_traceback
    def __init__(self, resource=Undefined, **values):
        """ Update default values with these arguments on instantiation.
        """
        # gotta have a console logger
        self._console = util.console.logger.getChild(str(self))
        self._console = logging.LoggerAdapter(
            self._console,
            dict(
                device=type(self).__qualname__+'()',
                origin=f" - " + type(self).__qualname__+'()'
            )
        )

        # initialize property trait traits last so that calibration behaviors can use values and self._console
        super().__init__()

        if resource is not Undefined:
            values['resource'] = resource

        for name, init_value in values.items():
            if init_value != self._traits[name].default:
                setattr(self, name, init_value)

        self.backend = DisconnectedBackend(self)

        # Instantiate property trait now. It needed to wait until this point, after values are fully
        # instantiated, in case property trait implementation depends on values
        setattr(self, 'open', self.__open_wrapper__)
        setattr(self, 'close', self.__close_wrapper__)


    @util.hide_in_traceback
    @wraps(open)
    def __open_wrapper__(self):
        """ A wrapper for the connect() method. It steps through the
            method resolution order of self.__class__ and invokes each open()
            method, starting with labbench.Device and working down
        """
        if self.isopen:
            self._console.debug(f'attempt to open {self}, which is already open')
            return

        self.backend = None

        try:
            for opener in trace_methods(self.__class__, 'open', Device)[::-1]:
                opener(self)
        except:
            self.backend = DisconnectedBackend(self)
            raise

        self._console.debug(f"opened")

        # Force an update to self.isopen
        self.isopen

    # def __owner_init__(self, owner):
    #     super().__owner_init__(owner)

    #     # update the name of the logger to match the context within owner
    #     self._console = util.console.logger.getChild(str(self))
    #     self._console = logging.LoggerAdapter(self._console, dict(device=repr(self), origin=f" - " + str(self)))

    @util.hide_in_traceback
    @wraps(close)
    def __close_wrapper__(self):
        """ A wrapper for the close() method that runs
            cleanup() before calling close(). close()
            will still be called if there is an exception in cleanup().
        """
        # Try to run cleanup(), but make sure to run
        # close() even if it fails
        # with self._hold_notifications('isopen'):
        if not self.isopen:
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
                sys.stderr.write('(Exception suppressed to continue close)\n\n')

        self.isopen

        self._console.debug('closed')

    
    @classmethod
    def __imports__(cls):
        pass

    @util.hide_in_traceback
    def __enter__(self):
        try:
            self.open()
            return self
        except BaseException as e:
            args = list(e.args)
            if len(args) > 0:
                args[0] = f'{repr(self)}: {args[0]}'
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
        if hasattr(self, 'resource'):
            return f'{name}({repr(self.resource)})'
        else:
            # In case an exception has occurred before __init__
            return f'{name}()'

    @property_.bool()
    def isopen(self):
        """ is the backend ready? """
        try:
            return DisconnectedBackend not in self.backend.__class__.__mro__
        except:
            # Run into this sometimes on reloading a module or ipython shell:
            # the namespace is gone. we just assume disconnected
            return False


# def device_contexts(objs, concurrent=True):
#     other_contexts = dict([(a, o) for a, o in objs.items()])

#     # Enforce the ordering set by self.enter_first
#     if concurrent:
#         # Any remaining context managers will be run concurrently if concurrent=True
#         contexts = dict(first_contexts,
#                         others=util.concurrently(name=f'',
#                                                  **other_contexts))
#     else:
#         # Otherwise, run them sequentially
#         contexts = dict(first_contexts, **other_contexts)
#     self.__cm = util.sequentially(name=f'{repr(self)} connections',
#                                   **contexts)


Device.__init_subclass__()

