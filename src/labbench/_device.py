"""
This implementation is deeply intertwined with obscure details of the python object
model. Consider starting with a close read of the documentation and exploring
the objects in an interpreter instead of reverse-engineering this code.
"""

import inspect
import sys
import traceback
from functools import wraps

import typing_extensions as typing

from . import paramattr as attr
from . import util
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


class DisconnectedBackend:
    """ "Null Backend" implementation to raises an exception with discriptive
    messages on attempts to use a backend before a Device is connected.
    """

    def __init__(self, dev):
        """dev may be a class or an object for error feedback"""
        if isinstance(dev, str):
            self.name = dev
        elif getattr(dev, '_owned_name', None) is not None:
            self.name = dev._owned_name
        else:
            self.name = f'{dev.__class__.__qualname__} instance'

    @util.hide_in_traceback
    def __getattr__(self, key):
        msg = f'open {self.name} first to access its backend'
        raise ConnectionError(msg)

    def __repr__(self):
        return 'DisconnectedBackend()'

    def __copy__(self, memo=None):
        return DisconnectedBackend(self.name)

    str = __repr__
    __deepcopy__ = __copy__


def log_paramattr_events(msg):
    """emit debug messages for trait values"""

    if msg['name'] == 'isopen':
        return

    device = msg['owner']
    attr_name = msg['name']

    try:
        attr_def = attr.get_class_attrs(device)[attr_name]
    except KeyError:
        raise

    label = ' '
    if msg['type'] == 'set':
        if attr_def.label:
            label = f' ({attr_def.label})'.rstrip()
        value = repr(msg['new']).rstrip()
        if len(value) > 180:
            value = f'<data of type {type(msg["new"]).__qualname__}>'
        device._logger.debug(f'{value}{label} → {attr_name}')
    elif msg['type'] == 'get':
        if attr_def.label:
            label = f' ({attr_def.label})'
        value = repr(msg['new'])
        if len(value) > 180:
            value = f'<data of type {type(msg["new"]).__qualname__}>'
        device._logger.debug(f'{attr_name} → {value} {label}'.rstrip())
    else:
        device._logger.debug(f'unknown operation type "{msg["type"]}"')


def attr_def_to_parameter(attr_def: attr.ParamAttr) -> inspect.Parameter:
    """build a signature.Parameter from a ParamAttr.value"""
    if attr_def.only and sys.version_info > (3, 10):
        # Union[*attr_def.only] is sooo close
        annotation = typing.Union.__getitem__(tuple(attr_def.only))
    else:
        annotation = attr_def._type

    if attr_def.allow_none:
        annotation = typing.Union[annotation, None]

    if attr_def.kw_only:
        kind = inspect.Parameter.KEYWORD_ONLY
    else:
        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD

    return inspect.Parameter(
        attr_def.name,
        kind=kind,
        default=attr_def.default,
        annotation=annotation,
    )

@typing.dataclass_transform(
    kw_only_default=True,
    eq_default=False,
    field_specifiers=attr.value._ALL_TYPES,
)
class DeviceDataClass(HasParamAttrs, util.Ownable):
    @typing.overload
    def __init__(self, *args, **values):
        ...

    def __init__(self, *args, **kwargs):
        """Update default values with these arguments on instantiation."""

        # validate and apply args and kwargs into a single dict by argument name
        values = inspect.signature(self.__init__).bind(*args, **kwargs).arguments

        super().__init__()

        with hold_attr_notifications(self):
            for name, init_value in values.items():
                setattr(self, name, init_value)

            attr_defs = attr.get_class_attrs(self)
            for name in attr_defs.keys() - values.keys():
                attr_def = attr_defs[name]
                if isinstance(attr_def, attr.value.Value):
                    if attr_def.default is Undefined:
                        attr_desc = attr.__repr__(owner_inst=self)

                        raise TypeError(
                            f'{attr_desc} is undefined - define it with a default, or '
                            f'instantiate with {attr_def.name} keyword argument'
                        )

        util.Ownable.__init__(self)

        self.backend = DisconnectedBackend(self)

        # Instantiate property trait now. It needed to wait until after values are fully
        # instantiated to support paramattr implementation that depends on values
        self.open = self.__open_wrapper__
        self.close = self.__close_wrapper__

    @classmethod
    @util.hide_in_traceback
    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.__annotations__ = typing.get_type_hints(cls)
        cls.__set_signature__()

    @classmethod
    @util.hide_in_traceback
    def __set_signature__(cls):
        # Generate a signature for documentation and code autocomplete
        params = [inspect.Parameter('self', kind=inspect.Parameter.POSITIONAL_OR_KEYWORD)]

        non_kw_only_attrs = []
        kw_only_attrs = []

        # validate types and classify by kw_only
        for name in typing.get_type_hints(cls).keys():
            attr_def = getattr(cls, name)

            if not isinstance(attr_def, attr.value.Value):
                annot_desc = f'{name}: {cls.__annotations__[name].__name__}'
                wrong_type = type(attr_def)
                raise TypeError(
                    f'only labbench.paramattr.value descriptors may be annotated in labbench Device classes, but "{annot_desc}" annotates {wrong_type!r}'
                )
            # TODO: validate compatibility of the type hint against the paramattr type?

            if attr_def.kw_only:
                kw_only_attrs.append(attr_def)
            else:
                non_kw_only_attrs.append(attr_def)

        for attr_def in non_kw_only_attrs:
            params.append(attr_def_to_parameter(attr_def))

        for attr_def in kw_only_attrs:
            params.append(attr_def_to_parameter(attr_def))

        # we need a wrapper so that __init__ can be modified separately for each subclass
        cls.__init__ = util.copy_func(cls.__init__)
        cls.__init__.__signature__ = inspect.Signature(params)

        # generate the __init__ docstring
        value_docs = ''.join([
            f'    {t.name}: {t.doc(as_argument=True)}\n'
            for t in (non_kw_only_attrs + kw_only_attrs)
        ])
        cls.__init__.__doc__ = f'\nArguments:\n{value_docs}'


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

    backend = DisconnectedBackend(None)
    """ this attribute is some reference to a controller for the device.
        it is to be set in `connect` and `disconnect` by the subclass that implements the backend.
    """

    def open(self):
        """Backend implementations may overload this to open a backend
        connection to the resource. This will be called *without*
        super().open().
        """
        attr.observe(self, log_paramattr_events)

    def close(self):
        """Backend implementations must overload this to disconnect an
        existing connection to the resource encapsulated in the object.
        This will be called *without* super().close().
        """
        self.backend = DisconnectedBackend(self)
        self.isopen
        try:
            attr.unobserve(self, log_paramattr_events)
        except KeyError:
            pass

    @util.hide_in_traceback
    @wraps(open)
    def __open_wrapper__(self):
        """A wrapper for the connect() method. It steps through the
        method resolution order of self.__class__ and invokes each open()
        method, starting with labbench.Device and working down
        """
        if self.isopen:
            self._logger.debug(f'attempt to open {self}, which is already open')
            return

        self.backend = None

        try:
            methods = util.find_methods_in_mro(self.__class__, 'open', Device)
            for opener in methods[::-1]:
                opener(self)
        except BaseException:
            self.backend = DisconnectedBackend(self)
            raise

        self._logger.debug('opened')

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

        methods = util.find_methods_in_mro(self.__class__, 'close', Device)

        all_exc_info = []
        for closer in methods:
            try:
                closer(self)
            except BaseException:
                all_exc_info.append(sys.exc_info())

        try:
            # Print tracebacks for any suppressed exceptions
            for exc_info in all_exc_info[::-1]:
                # If ThreadEndedByMaster was raised, assume the error handling in
                # util.concurrently will print the error message
                if exc_info[0] is util.ThreadEndedByMaster:
                    continue
                depth = len(tuple(traceback.walk_tb(exc_info[2])))
                traceback.print_exception(*exc_info, limit=-(depth - 1))
                sys.stderr.write('(Exception suppressed to continue close)\n\n')

            self.isopen

            self._logger.debug('closed')
        finally:
            if len(all_exc_info) > 0:
                exc_info = util.ConcurrentException(
                    f'multiple exceptions while closing {self}'
                )
                exc_info.thread_exceptions = all_exc_info
                raise exc_info

    @util.hide_in_traceback
    def __enter__(self):
        try:
            self.open()
            return self
        except BaseException as e:
            args = list(e.args)
            if len(args) > 0:
                args[0] = f'{self!r}: {args[0]}'
                e.args = tuple(args)
            raise e

    @util.hide_in_traceback
    def __exit__(self, type_, value, traceback):
        try:
            self.close()
        except BaseException as e:
            args = list(e.args)
            args[0] = f'{self!r}: {args[0]!s}'
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
        if hasattr(self, 'resource'):
            if self.resource != type(self).resource.default:
                resource_str = repr(self.resource)
            else:
                resource_str = ''
            return f'{name}({resource_str})'
        else:
            # In case an exception has occurred before __init__
            return f'{name}()'

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
