"""Tests of paramattr calibrations applied to properties and methods.

This pattern was used to implement attenuators:
    https://github.com/usnistgov/ssmdevices/blob/main/ssmdevices/instruments/attenuators.py
"""

import pytest

import labbench as lb
from labbench import paramattr as attr
from labbench.testing import store_backend

lb.util.force_full_traceback(True)


@store_backend.key_adapter(defaults={'attenuation_setting': 0})
class PropertyDevice(store_backend.StoreTestDevice):
    frequency: float = attr.value.float(
        5e9,
        allow_none=True,
        min=1e9,
        max=5e9,
        help='frequency for calibration data (None for no calibration)',
        label='Hz',
    )

    output_power_offset: float = attr.value.float(
        default=10.0,
        allow_none=True,
        help='output power level at 0 dB attenuation',
        label='dBm',
    )

    calibration_path: float = attr.value.Path(
        default='tests/data/attenuator_cal.csv',
        allow_none=True,
        must_exist=True,
        cache=True,
        help='path to the calibration table csv file (containing frequency '
        '(row) and attenuation setting (column))',
    )

    # the only property that requests an attenuation setting in the device
    attenuation_setting = attr.property.float(
        key='attenuation_setting',
        min=0,
        max=110,
        step=5,
        label='dB',
        help='uncalibrated attenuation',
    )

    # the remaining traits are calibration corrections for attenuation_setting
    attenuation = attenuation_setting.corrected_from_table(
        path_attr=calibration_path,
        index_lookup_attr=frequency,
        table_index_column='Frequency(Hz)',
        help='calibrated attenuation',
    )

    output_power = attenuation_setting.corrected_from_expression(
        -attenuation + output_power_offset,
        help='calibrated output power level',
        label='dBm',
    )


@pytest.fixture
def property_device():
    device = PropertyDevice()
    device.open()
    yield device
    device.close()


def test_property_get_through_table(property_device):
    for attenuation_setting in (0, 10, 100):
        property_device.attenuation_setting = attenuation_setting
        attenuation = property_device.attenuation
        assert (
            attenuation == attenuation_setting + 1
        ), f'attenuation was {attenuation} dB when attenuation setting was set to {attenuation_setting} dB'


def test_property_set_through_table(property_device):
    for attenuation in (1, 11, 111):
        property_device.attenuation = attenuation
        attenuation_setting = property_device.attenuation_setting
        assert (
            attenuation_setting == attenuation - 1
        ), f'attenuation setting {attenuation_setting} dB when attenuation was set to {attenuation} dB'

    with pytest.raises(ValueError):
        property_device.attenuation = 0

    with pytest.raises(ValueError):
        property_device.attenuation = 112


def test_property_get_with_offset(property_device):
    for attenuation in (1, 11, 111):
        property_device.attenuation = attenuation
        output_power = property_device.output_power
        assert (
            output_power == property_device.output_power_offset - attenuation
        ), f'output power {output_power} dBm when attenuation was set to {attenuation} dB'


def test_property_set_with_offset(property_device):
    for output_power in (9, -1, -101.0):
        property_device.output_power = output_power
        attenuation = property_device.attenuation
        assert (
            output_power == property_device.output_power_offset - attenuation
        ), f'output power {output_power} dBm when attenuation was set to {attenuation} dB'

    with pytest.raises(ValueError):
        property_device.output_power = 10

    with pytest.raises(ValueError):
        property_device.output_power = -102.0


class MethodDevice(store_backend.StoreTestDevice):
    frequency: float = attr.value.float(
        5e9,
        allow_none=True,
        min=1e9,
        max=5e9,
        help='frequency for calibration data (None for no calibration)',
        label='Hz',
    )

    output_power_offset: float = attr.value.float(
        default=10.0,
        allow_none=True,
        help='output power level at 0 dB attenuation',
        label='dBm',
    )

    calibration_path: float = attr.value.Path(
        default='tests/data/attenuator_cal.csv',
        allow_none=True,
        must_exist=True,
        cache=True,
        help='path to the calibration table csv file (containing frequency '
        '(row) and attenuation setting (column))',
    )

    # the only property that requests an attenuation setting in the device
    attenuation_setting = attr.method.float(
        key='attenuation_setting',
        min=0,
        max=110,
        step=5,
        label='dB',
        help='uncalibrated attenuation',
    )

    # the remaining traits are calibration corrections for attenuation_setting
    attenuation = attenuation_setting.corrected_from_table(
        path_attr=calibration_path,
        index_lookup_attr=frequency,
        table_index_column='Frequency(Hz)',
        help='calibrated attenuation',
    )

    output_power = attenuation_setting.corrected_from_expression(
        -attenuation + output_power_offset,
        help='calibrated output power level',
        label='dBm',
    )


@pytest.fixture
def method_device():
    device = MethodDevice()
    device.open()
    yield device
    device.close()


def test_method_get_through_table(method_device):
    for attenuation_setting in (0, 10, 100):
        method_device.attenuation_setting(attenuation_setting)
        attenuation = method_device.attenuation()
        assert (
            attenuation == attenuation_setting + 1
        ), f'attenuation was {attenuation} dB when attenuation setting was set to {attenuation_setting} dB'


def test_method_set_through_table(method_device):
    for attenuation in (1, 11, 111):
        method_device.attenuation(attenuation)
        attenuation_setting = method_device.attenuation_setting()
        assert (
            attenuation_setting == attenuation - 1
        ), f'attenuation setting {attenuation_setting} dB when attenuation was set to {attenuation} dB'

    with pytest.raises(ValueError):
        method_device.attenuation(0)

    with pytest.raises(ValueError):
        method_device.attenuation(112)


def test_method_get_with_offset(method_device):
    for attenuation in (1, 11, 111):
        method_device.attenuation(attenuation)
        output_power = method_device.output_power()
        assert (
            output_power == method_device.output_power_offset - attenuation
        ), f'output power {output_power} dBm when attenuation was set to {attenuation} dB'


def test_method_set_with_offset(method_device):
    for output_power in (9, -1, -101.0):
        method_device.output_power(output_power)
        attenuation = method_device.attenuation()
        assert (
            output_power == method_device.output_power_offset - attenuation
        ), f'output power {output_power} dBm when attenuation was set to {attenuation} dB'

    with pytest.raises(ValueError):
        method_device.output_power(10)

    with pytest.raises(ValueError):
        method_device.output_power(-102)
