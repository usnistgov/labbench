from labbench.testing import pyvisa_sim, store_backend, pyvisa_sim_resource
from numbers import Number
import labbench as lb
from labbench import argument as attr
import unittest
import paramattr_tooling
import time

lb.util.force_full_traceback(True)

@store_backend.key_store_adapter(defaults={"attenuation_setting": 0})
class StoreTestDevice(store_backend.TestStoreDevice):
    frequency: float = attr.value.float(
        allow_none=True,
        min=10e6,
        max=6e9,
        help="frequency for calibration data (None for no calibration)",
        label="Hz",
    )

    output_power_offset: float = attr.value.float(
        default=None,
        allow_none=True,
        help="output power level at 0 dB attenuation",
        label="dBm",
    )

    calibration_path: float = attr.value.str(
        default="data/attenuator_cal.csv",
        allow_none=True,
        cache=True,
        help="path to the calibration table csv file (containing frequency "
        "(row) and attenuation setting (column))",
    )

    # the only property that requests an attenuation setting in the device
    attenuation_setting = attr.property.float(key='attenuation_setting', min=0, max=115, step=5, label="dB", help="uncalibrated attenuation")

    # the remaining traits are calibration corrections for attenuation_setting
    attenuation = attenuation_setting.calibrate_from_table(
        path_attr=calibration_path,
        index_lookup_attr=frequency,
        table_index_column="Frequency(Hz)",
        help="calibrated attenuation",
    )

    output_power = attenuation_setting.calibrate_from_expression(
        -attenuation_setting + output_power_offset,
        help="calibrated output power level",
        label="dBm",
    )


device = StoreTestDevice(frequency=5e9)
device.open()
device.attenuation = 49

if __name__ == "__main__":
    lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("info")
    lb.util.force_full_traceback(True)

    # unittest.main()
    device = StoreTestDevice()