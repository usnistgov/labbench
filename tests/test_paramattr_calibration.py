import labbench as lb
from labbench import paramattr as attr
from labbench.testing import store_backend
import pytest

lb.util.force_full_traceback(True)

@store_backend.key_store_adapter(defaults={'attenuation_setting': 0})
class StoreTestDevice(store_backend.StoreTestDevice):
    frequency: float = attr.value.float(
        None,
        allow_none=True,
        min=10e6,
        max=6e9,
        help='frequency for calibration data (None for no calibration)',
        label='Hz',
    )

    output_power_offset: float = attr.value.float(
        default=None,
        allow_none=True,
        help='output power level at 0 dB attenuation',
        label='dBm',
    )

    calibration_path: float = attr.value.str(
        default='tests/data/attenuator_cal.csv',
        allow_none=True,
        cache=True,
        help='path to the calibration table csv file (containing frequency ' '(row) and attenuation setting (column))',
    )

    # the only property that requests an attenuation setting in the device
    attenuation_setting = attr.property.float(
        key='attenuation_setting',
        min=0,
        max=115,
        step=5,
        label='dB',
        help='uncalibrated attenuation',
    )

    # the remaining traits are calibration corrections for attenuation_setting
    attenuation = attenuation_setting.calibrate_from_table(
        path_attr=calibration_path,
        index_lookup_attr=frequency,
        table_index_column='Frequency(Hz)',
        help='calibrated attenuation',
    )

    output_power = attenuation_setting.calibrate_from_expression(
        -attenuation_setting + output_power_offset,
        help='calibrated output power level',
        label='dBm',
    )

@pytest.fixture
def opened_device():
    device = StoreTestDevice()
    device.open()
    yield device
    device.close()


def test_set_attenuation_setting(opened_device):
    opened_device.frequency = 5e9
    
    opened_device.attenuation_setting = 0
    assert opened_device.attenuation == 1, 'calibrated attenuation level at 0 dB attenuation setting'

    opened_device.attenuation_setting = 10
    assert opened_device.attenuation == 11, f'calibrated attenuation setting {opened_device.attenuation_setting} at 10 dB calibrated attenuation'


def test_set_attenuation(opened_device):
    opened_device.frequency = 5e9

    opened_device.attenuation = 11
    assert opened_device.attenuation_setting == 10, 'attenuation setting at 11 dB calibrated attenuation'

    opened_device.attenuation = 6
    assert opened_device.attenuation_setting == 5, 'attenuation setting at 1 dB calibrated attenuation'




