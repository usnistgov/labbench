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
import sys
import traceback
from warnings import warn

from . import util
from . import property as property_
from . import value

from ._traits import (
    HasTraits,
    Trait,
    Undefined,
    BoundedNumber,
    observe,
    unobserve,
    hold_trait_notifications,
)

__all__ = ["Device", "list_devices", "property", "value", "trait_info"]


def trace_methods(cls, name, until_cls=None):
    """Look for a method called `name` in cls and all of its parent classes."""
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
    """Look for Device instances, and their names, in the calling
    code context (depth == 1) or its callers (if depth in (2,3,...)).
    Checks locals() in that context first.
    If no Device instances are found there, search the first
    argument of the first function argument, in case this is
    a method in a class.
    """
    from inspect import currentframe

    f = frame = currentframe()
    for i in range(depth):
        f = f.f_back
    try:
        ret = {k: v for k, v in list(f.frame.f_locals.items()) if isinstance(v, Device)}

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
        """dev may be a class or an object for error feedback"""
        if isinstance(dev, str):
            self.name = dev
        elif getattr(dev, "_owned_name", None) is not None:
            self.name = dev._owned_name
        else:
            self.name = f"{dev.__class__.__qualname__} instance"

    @util.hide_in_traceback
    def __getattr__(self, key):
        msg = f"open {self.name} first to access its backend"
        raise ConnectionError(msg)

    def __repr__(self):
        return "DisconnectedBackend()"

    def __copy__(self, memo=None):
        return DisconnectedBackend(self.name)

    str = __repr__
    __deepcopy__ = __copy__


def log_trait_activity(msg):
    """emit debug messages for trait values"""

    # print('logger debug!', msg)

    if msg["name"] == "isopen":
        return

    owner = msg["owner"]
    trait_name = msg["name"]

    if msg["type"] == "set":
        label = owner._traits[trait_name].label or " "
        if label:
            label = f" {label} "
        value = repr(msg["new"])
        if len(value) > 180:
            value = f'<data of type {type(msg["new"]).__qualname__}>'
        owner._logger.debug(f'set trait "{trait_name}" → {value}{label}')
    elif msg["type"] == "get":
        if msg["new"] != msg["old"]:
            label = owner._traits[trait_name].label
            if label:
                label = f" {label} "

            value = repr(msg["new"])
            if len(value) > 180:
                value = f'<data of type {type(msg["new"]).__qualname__}>'

            owner._logger.debug(f'get trait "{trait_name}" == {value}{label}')
    else:
        owner._logger.debug(f'unknown operation type "{msg["type"]}"')


class Device(HasTraits, util.Ownable):
    r"""base class for labbench device wrappers.

    Drivers that subclass `Device` share

    * standardized connection management via context blocks (the `with` statement)
    * hooks for automatic data logging and heads-up displays
    * API style consistency
    * bounds checking and casting for typed attributes

    .. note::
        This `Device` base class has convenience
        functions for device control, but no implementation.

        Some wrappers for particular APIs labbench Device subclasses:

            * VISADevice: pyvisa,
            * ShellBackend: binaries and scripts
            * Serial: pyserial
            * DotNetDevice: pythonnet

        (and others). If you are implementing a driver that uses one of
        these backends, inherit from the corresponding class above, not
        `Device`.

    """

    resource = value.str(allow_none=True, cache=True, help="device address or URI")
    concurrency = value.bool(
        True, sets=False, help="True if the device supports threading"
    )
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
        """Backend implementations overload this to open a backend
        connection to the resource.
        """
        observe(self, log_trait_activity)

    def close(self):
        """Backend implementations must overload this to disconnect an
        existing connection to the resource encapsulated in the object.
        """
        self.backend = DisconnectedBackend(self)
        self.isopen
        unobserve(self, log_trait_activity)

    __children__ = {}

    @util.hide_in_traceback
    def __init__(self, resource=Undefined, **values):
        """Update default values with these arguments on instantiation."""

        if hasattr(self, "__imports__"):
            warn(
                "the use of __imports__ has been deprecated. switch to importing each backend-specific module in each method that uses it."
            )
            self.__imports__()

        # validate presence of required arguments
        inspect.signature(self.__init__).bind(resource, **values)

        if resource is not Undefined:
            values["resource"] = resource

        super().__init__()

        with hold_trait_notifications(self):
            for name, init_value in values.items():
                if init_value != self._traits[name].default:
                    setattr(self, name, init_value)

        util.Ownable.__init__(self)

        self.backend = DisconnectedBackend(self)

        # Instantiate property trait now. It needed to wait until this point, after values are fully
        # instantiated, in case property trait implementation depends on values
        setattr(self, "open", self.__open_wrapper__)
        setattr(self, "close", self.__close_wrapper__)

    @classmethod
    @util.hide_in_traceback
    def __init_subclass__(cls, **value_defaults):
        super().__init_subclass__()

        for trait_name, new_default in value_defaults.items():
            trait = getattr(cls, trait_name, None)

            if trait is None or trait.role != Trait.ROLE_VALUE:
                parent_name = cls.__mro__[1].__qualname__
                raise AttributeError(
                    f"there is no value trait {parent_name}.{trait_name}, cannot update its default"
                )

            cls._traits[trait_name] = trait.copy(default=new_default)
            setattr(cls, trait_name, cls._traits[trait_name])

        if len(value_defaults) > 0:
            super().__init_subclass__()

        # Generate a signature for documentation and code autocomplete
        params = [
            inspect.Parameter("self", kind=inspect.Parameter.POSITIONAL_ONLY),
            inspect.Parameter(
                "resource",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=cls.resource.default,
                annotation=cls.resource.type,
            ),
        ]

        settable_values = {
            name: cls._traits[name]
            for name in cls._value_attrs
            if cls._traits[name].sets
        }

        # generate and apply the sequence of call signature parameters
        params += [
            inspect.Parameter(
                name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=trait.default,
                annotation=trait.type,
            )
            for name, trait in settable_values.items()
            if name != "resource"
        ]

        # we need a wrapper so that __init__ can be modified separately for each subclass
        cls.__init__ = util.copy_func(cls.__init__)
        cls.__init__.__signature__ = inspect.Signature(params)

        # generate the __init__ docstring
        value_docs = "".join((f"    {t.doc()}\n" for t in settable_values.values()))
        cls.__init__.__doc__ = f"\nArguments:\n{value_docs}"

    @util.hide_in_traceback
    @wraps(open)
    def __open_wrapper__(self):
        """A wrapper for the connect() method. It steps through the
        method resolution order of self.__class__ and invokes each open()
        method, starting with labbench.Device and working down
        """
        if self.isopen:
            self._logger.debug(f"attempt to open {self}, which is already open")
            return

        self.backend = None

        try:
            for opener in trace_methods(self.__class__, "open", Device)[::-1]:
                opener(self)
        except BaseException:
            self.backend = DisconnectedBackend(self)
            raise

        self._logger.debug("opened")

        # Force an update to self.isopen
        self.isopen

    @util.hide_in_traceback
    @wraps(close)
    def __close_wrapper__(self):
        """A wrapper for the close() method that runs
        cleanup() before calling close(). close()
        will still be called if there is an exception in cleanup().
        """
        # Try to run cleanup(), but make sure to run
        # close() even if it fails
        # with self._hold_notifications('isopen'):
        if not self.isopen:
            return

        methods = trace_methods(self.__class__, "close", Device)

        all_ex = []
        for closer in methods:
            try:
                closer(self)
            except BaseException:
                all_ex.append(sys.exc_info())

        try:
            # Print tracebacks for any suppressed exceptions
            for ex in all_ex[::-1]:
                # If ThreadEndedByMaster was raised, assume the error handling in
                # util.concurrently will print the error message
                if ex[0] is not util.ThreadEndedByMaster:
                    depth = len(tuple(traceback.walk_tb(ex[2])))
                    traceback.print_exception(*ex, limit=-(depth - 1))
                    sys.stderr.write("(Exception suppressed to continue close)\n\n")

            self.isopen

            self._logger.debug("closed")
        finally:
            if len(all_ex) > 0:
                ex = util.ConcurrentException(
                    f"multiple exceptions while closing {self}"
                )
                ex.thread_exceptions = all_ex
                raise ex

    @util.hide_in_traceback
    def __enter__(self):
        try:
            self.open()
            return self
        except BaseException as e:
            args = list(e.args)
            if len(args) > 0:
                args[0] = f"{repr(self)}: {args[0]}"
                e.args = tuple(args)
            raise e

    @util.hide_in_traceback
    def __exit__(self, type_, value, traceback):
        try:
            self.close()
        except BaseException as e:
            args = list(e.args)
            args[0] = "{}: {}".format(repr(self), str(args[0]))
            e.args = tuple(args)
            raise e

    # Object boilerplate
    def __del__(self):
        try:
            isopen = self.isopen
        except AttributeError:
            # the object failed to instantiate properly
            isopen = False

        if isopen:
            self.close()

    @property
    def myproperty(self) -> int:
        """I can has documentation"""

    def __repr__(self):
        name = self.__class__.__qualname__
        if hasattr(self, "resource"):
            return f"{name}({repr(self.resource)})"
        else:
            # In case an exception has occurred before __init__
            return f"{name}()"

    @property_.bool(help="oh no")
    def isopen(self):
        """`True` if the backend is ready for use"""
        try:
            return DisconnectedBackend not in self.backend.__class__.__mro__
        except BaseException:
            # Run into this sometimes on reloading a module or ipython shell:
            # the namespace is gone. we just assume disconnected
            return False


Device.__init_subclass__()


def trait_info(device: Device, name: str) -> dict:
    """returns the keywords used to define the trait attribute named `name` in `device`"""

    trait = device._traits[name]
    info = dict(trait.kws)

    if isinstance(trait, BoundedNumber):
        info.update(
            min=trait._min(device),
            max=trait._max(device),
            step=trait.step,
        )

    return info
