# testing Device objects implemented as a simple dict store for closed-loop get/set testing of
# method and property attributes

import typing
from collections import defaultdict
from typing import Any, Union

from .. import Device, Undefined
from .. import paramattr as attr

__all__ = ['PowerSensor', 'Oscilloscope', 'SignalGenerator']

T = typing.TypeVar('T')


class key_adapter(attr.visa_keying):
    def __init__(
        self,
        *,
        defaults: dict[str, Any] = {},
        remap: dict[Any, str] = {}
    ):
        super().__init__(remap=remap)
        self.defaults = defaults

    def get_kwarg_names(self, key_def: Union[str, tuple[str]]) -> tuple[str]:
        if isinstance(key_def, str) or len(key_def) == 1:
            return super().get_kwarg_names(key_def)
        else:
            return tuple(key_def[1:])

    def get(
        self,
        owner: attr.HasParamAttrs,
        key_def: Union[str, list[str]],
        paramattr: attr.ParamAttr = None,
        arguments: dict[str, Any] = {},
    ):
        """queries a parameter named `scpi_key` by sending an SCPI message string.

        The command message string is formatted as f'{scpi_key}?'.
        This is automatically called in wrapper objects on accesses to property traits that
        defined with 'key=' (which then also cast to a pythonic type).

        Arguments:
            key (str): the name of the parameter to set
            name (str, None): name of the trait setting the key (or None to indicate no trait) (ignored)

        Returns:
            response (str)
        """
        store_name = owner.backend.get_store_key(paramattr)
        backend_key = owner.backend.get_backend_key(owner, paramattr, arguments)

        default = self.defaults.get(store_name, paramattr._type())
        return owner.backend.get(backend_key, default)

    def set(
        self,
        owner: attr.HasParamAttrs,
        key_def: str,
        value,
        attr: attr.ParamAttr = None,
        arguments: dict[str, Any] = {},
    ):
        """writes an attribute

        The command message string is formatted as f'{scpi_key} {value}'. This
        This is automatically called on assignment to property traits that
        are defined with 'key='.

        Arguments:
            scpi_key (str): the name of the parameter to set
            value (str): value to assign
            name (str, None): name of the trait setting the key (or None to indicate no trait) (ignored)
        """
        backend_key = owner.backend.get_backend_key(owner, attr, arguments)
        owner.backend.set(backend_key, value)


class TestStore:
    def __init__(self):
        self.values = {}
        self.clear_counts()

    def get(self, key, default):
        self.get_count[key] += 1
        return self.values.setdefault(key, default)

    def set(self, key, value):
        self.set_count[key] += 1
        self.values[key] = value

    def clear_counts(self):
        self.get_count = defaultdict(int)
        self.set_count = defaultdict(int)
        self.notifications = []

    def get_store_key(self, attr_def: attr.ParamAttr) -> str:
        if isinstance(attr_def, attr.value.Value) or attr_def.key is Undefined:
            return attr_def.name
        elif isinstance(attr_def.key, str):
            return attr_def.key
        else:
            return attr_def.key[0]

    def get_backend_key(self, owner, attr_def, arguments={}):
        store_name = self.get_store_key(attr_def)
        # print('***', attr_def.get_key_arguments(type(owner)), arguments)

        if isinstance(attr_def, attr.method.Method):
            required_args = attr_def.get_kwarg_names()

            missing_args = set(required_args) - set(arguments)
            if len(missing_args) > 0:
                raise ValueError(f'missing required argument(s): {missing_args}')

        if len(arguments) == 0:
            return store_name
        else:
            return (store_name, frozenset(arguments.items()))

    def notification_handler(self, msg: dict):
        self.notifications.append(msg)


@key_adapter()
class StoreTestDevice(Device):
    resource: str = attr.value.str(None, kw_only=False, help='address')

    def open(self):
        self.backend = TestStore()
        attr.observe(self, self.backend.notification_handler)

    @classmethod
    def get_paramattr_arguments(
        cls, attr_name
    ) -> list[attr.method_kwarg.MethodKeywordArgument]:
        attr = getattr(cls, attr_name)
        return attr.get_key_arguments(cls)

    @classmethod
    def get_attr_defs(cls) -> dict[str, attr.ParamAttr]:
        return cls._attr_defs.attrs

    @classmethod
    def get_method_names(cls) -> list[str]:
        return cls._attr_defs.method_names()

    @classmethod
    def get_property_names(cls) -> list[str]:
        return set(cls._attr_defs.method_names()) - set(dir(Device))


class PowerSensor(StoreTestDevice):
    RATES = 'NORM', 'DOUB', 'FAST'

    # SCPI string keys and bounds on the parameter values,
    # taken from the instrument programming manual
    initiate_continuous = attr.property.bool(
        key='INIT:CONT', help='trigger continuously if True'
    )
    trigger_count = attr.property.int(
        key='TRIG:COUN', min=1, max=200, help='acquisition count', label='samples'
    )
    measurement_rate = attr.property.str(
        key='SENS:MRAT',
        only=RATES,
        case=False,
    )
    sweep_aperture = attr.property.float(
        key='SWE:APER', min=20e-6, max=200e-3, help='measurement duration', label='s'
    )
    frequency = attr.property.float(
        key='SENS:FREQ',
        min=10e6,
        max=18e9,
        step=1e-3,
        help='calibration frequency',
        label='Hz',
    )


class SpectrumAnalyzer(StoreTestDevice):
    center_frequency = attr.property.float(
        key='SENS:FREQ',
        min=10e6,
        max=18e9,
        step=1e-3,
        help='input signal center frequency',
        label='Hz',
    )
    resolution_bandwidth = attr.property.float(
        key='SENS:BW',
        min=1,
        max=40e6,
        step=1e-3,
        help='resolution bandwidth',
        label='Hz',
    )


class SignalGenerator(StoreTestDevice):
    output_enabled = attr.property.bool(
        key='OUT:ENABL', help='when True, output an RF tone'
    )
    center_frequency = attr.property.float(
        key='SENS:FREQ',
        min=10e6,
        max=18e9,
        step=1e-3,
        help='input signal center frequency',
        label='Hz',
    )
    mode = attr.property.str(key='MODE', only=['sweep', 'tone', 'iq'], case=False)


@attr.method_kwarg.int(name='channel', min=1, max=4, help='input channel')
class Oscilloscope(StoreTestDevice):
    @attr.method.float(
        min=10e6,
        max=18e9,
        step=1e-3,
        label='Hz',
        help='channel center frequency',
    )
    def center_frequency(self, *, channel):
        return self.query(f'CH{channel}:SENS:FREQ?')

    @center_frequency.setter
    def _(self, set_value, /, *, channel):
        self.write(f'CH{channel}:SENS:FREQ {set_value}')

    resolution_bandwidth = attr.method.float(
        key=('CH:SENS:BW', 'channel'),
        min=1,
        max=40e6,
        step=1e-3,
        help='channel resolution bandwidth',
        label='Hz',
        # arguments omitted deliberately for testing
    )
