"""
This implementation is deeply intertwined with obscure details of the python object
model. Consider starting with a close read of the documentation and exploring
the objects in an interpreter instead of reverse-engineering this code.
"""

from functools import wraps
import inspect
import sys
import traceback
import typing_extensions as typing

from . import util
from . import paramattr as attr

from .paramattr._bases import (
    HasParamAttrs,
    Undefined,
    hold_attr_notifications,
)


def find_device_instances(depth=1):
    """Look for Device instances, and their names, in the calling
    code context (depth == 1), its caller (depth == 2), and so on.
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

    if msg["name"] == "isopen":
        return

    device = msg["owner"]
    attr_name = msg["name"]

    label = " "
    if msg["type"] == "set":
        if attr.get_class_attrs(device)[attr_name].label:
            label = f" ({attr.get_class_attrs(device)[attr_name].label})".rstrip()
        value = repr(msg["new"]).rstrip()
        if len(value) > 180:
            value = f'<data of type {type(msg["new"]).__qualname__}>'
        device._logger.debug(f"{value}{label} → {attr_name}")
    elif msg["type"] == "get":
        if attr.get_class_attrs(device)[attr_name].label:
            label = f" ({attr.get_class_attrs(device)[attr_name].label})"
        value = repr(msg["new"])
        if len(value) > 180:
            value = f'<data of type {type(msg["new"]).__qualname__}>'
        device._logger.debug(f"{attr_name} → {value} {label}".rstrip())
    else:
        device._logger.debug(f'unknown operation type "{msg["type"]}"')


@typing.dataclass_transform(
    kw_only_default=True,
    eq_default=False,
    field_specifiers=attr.value._ALL_TYPES,
)
class DeviceDataClass(HasParamAttrs, util.Ownable):
    @typing.overload
    def __init__(self, **values):
        ...

    def __init__(self, resource=Undefined, **values):
        """Update default values with these arguments on instantiation."""

        if resource is Undefined:
            values["resource"] = type(self).resource.default
        else:
            values["resource"] = resource

        # validate presence of required arguments
        inspect.signature(self.__init__).bind(**values)

        super().__init__()

        with hold_attr_notifications(self):
            for name, init_value in values.items():
                setattr(self, name, init_value)

            other_names = set(self._attr_defs.value_names()) - set(values.keys())
            for name in other_names:
                attr_def = getattr(type(self), name)
                if isinstance(attr_def, attr.value.Value):
                    if attr_def.default is not Undefined:
                        self._attr_store.cache[name] = attr_def.default
                    elif attr_def.allow_none:
                        self._attr_store.cache[name] = None
                    else:
                        attr_desc = attr.__repr__(owner_inst=self)
                        raise TypeError(
                            f"unable to determine an initial value for {attr_desc} - define it with allow_none=True or default=<default value>"
                        )

        util.Ownable.__init__(self)

        self.backend = DisconnectedBackend(self)

        # Instantiate property trait now. It needed to wait until this point, after values are fully
        # instantiated, in case property trait implementation depends on values
        setattr(self, "open", self.__open_wrapper__)
        setattr(self, "close", self.__close_wrapper__)

    @classmethod
    @util.hide_in_traceback
    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.__annotations__ = typing.get_type_hints(cls)
        cls.__update_signature__()

    @classmethod
    @util.hide_in_traceback
    def __update_signature__(cls):
        # Generate a signature for documentation and code autocomplete
        params = [
            inspect.Parameter("self", kind=inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter(
                "resource",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=cls.resource.default,
                annotation=cls.resource._type,
            ),
        ]

        # generate and apply the sequence of call signature parameters
        constructor_attrs = []
        for name in cls.__annotations__.keys():
            attr_def = getattr(cls, name)
            constructor_attrs.append(attr_def)

            if not isinstance(attr_def, attr.value.Value):
                annot_desc = f"{name}: {cls.__annotations__[name].__name__}"
                wrong_type = type(attr_def)
                raise TypeError(
                    f'only labbench.paramattr.value descriptors may be annotated in labbench Device classes, but "{annot_desc}" annotates {repr(wrong_type)}'
                )

            elif name == "resource":
                # defined above for its POSITIONAL_OR_KEYWORD special casing
                continue

            else:
                if attr_def.only:
                    annotation = typing.Union[*attr_def.only,*list()]
                else:
                    annotation = attr_def._type

                if attr_def.allow_none:
                    annotation = typing.Union[annotation, None]

                params.append(
                    inspect.Parameter(
                        name,
                        kind=inspect.Parameter.KEYWORD_ONLY,
                        default=attr_def.default,
                        annotation=annotation,
                    )
                )

        # we need a wrapper so that __init__ can be modified separately for each subclass
        cls.__init__ = util.copy_func(cls.__init__)
        cls.__init__.__signature__ = inspect.Signature(params)

        # generate the __init__ docstring
        value_docs = "".join([f"    {t.name}: {t.doc(as_argument=True)}\n" for t in constructor_attrs])
        cls.__init__.__doc__ = f"\nArguments:\n{value_docs}"


class Device(DeviceDataClass):
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

    resource: str = attr.value.str(
        default=None, allow_none=True, cache=True, kw_only=False, help="device address or URI"
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
        attr.observe(self, log_trait_activity)

    def close(self):
        """Backend implementations must overload this to disconnect an
        existing connection to the resource encapsulated in the object.
        """
        self.backend = DisconnectedBackend(self)
        self.isopen
        attr.unobserve(self, log_trait_activity)

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
            for opener in util.find_methods_in_mro(self.__class__, "open", Device)[::-1]:
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

        methods = util.find_methods_in_mro(self.__class__, "close", Device)

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
                ex = util.ConcurrentException(f"multiple exceptions while closing {self}")
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
        except (AttributeError, KeyError):
            # the object failed to instantiate properly
            isopen = False

        if isopen:
            self.close()

    def __repr__(self):
        name = self.__class__.__qualname__
        if hasattr(self, "resource"):
            if self.resource != type(self).resource.default:
                resource_str = repr(self.resource)
            else:
                resource_str = ""
            return f"{name}({resource_str})"
        else:
            # In case an exception has occurred before __init__
            return f"{name}()"

    @attr.property.bool()
    def isopen(self):
        """`True` if the backend is ready for use"""
        try:
            return DisconnectedBackend not in self.backend.__class__.__mro__
        except BaseException:
            # Run into this sometimes on reloading a module or ipython shell:
            # the namespace is gone. we just assume disconnected
            return False


Device.__init_subclass__()
