from labbench.testing import pyvisa_sim, store_backend, pyvisa_sim_resource
from numbers import Number
import labbench as lb
from labbench import paramattr as attr
import unittest
import paramattr_tooling


@store_backend.key_store_adapter(defaults={"str_or_none": None, "str_cached": "cached string"})
class StoreTestDevice(store_backend.TestStoreDevice):
    LOOP_TEST_VALUES = {
        # make sure all test values conform to these general test values
        int: 5,
        float: 3.14,
        str: "moose",
        bool: True,
        object: None,
    }

    # test both getting and setting
    bool = attr.value.bool(default=True)
    int_with_default = attr.value.int(default=47)
    int_no_default = attr.value.int(default=None, allow_none=True)

    # floats
    float_low_bounded = attr.value.float(default=2, min=1)
    float_high_bounded = attr.value.float(default=2, max=4)
    float_none_bounded = attr.value.float(default=3, allow_none=True, max=4, min=1)
    float_stepped = attr.value.float(default=0, step=3)

    # strings
    str_explicit_none = attr.value.str(default=None, allow_none=True)
    str_allow_none = attr.value.str(default=None, allow_none=True)
    str_cached = attr.value.str(default="47", cache=True)
    str = attr.value.str(default="squirrel")
    any = attr.value.any(default="empty", allow_none=True)
    str_with_only = attr.value.str(default="moose", only=("moose", "squirrel"))
    str_no_case_with_only = attr.value.str(default="moose", only=("MOOSE", "squirrel"), case=False)


@lb.adjust("bool", default=False)
class AdjustedTestDevice(StoreTestDevice):
    pass


class RequiredParametersTestDevice(lb.Device):
    required_str: str = attr.value.str(cache=True)
    required_str_allow_none: str = attr.value.str(cache=True, allow_none=True)


def change_case(s: str):
    alt = s.upper()
    if alt == s:
        alt = s.lower()
    return alt


def has_steps(attr: attr.ParamAttr):
    return getattr(attr, "step", None) is not None


class TestValueParamAttr(paramattr_tooling.TestParamAttr):
    DeviceClass = StoreTestDevice
    ROLE_TYPE = attr.value.Value

    def set_param(self, device, attr_name, value, arguments={}):
        if len(arguments) > 0:
            attr_def = attr.get_class_attrs(device)[attr_name]
            raise ValueError(f"{attr_def.ROLE} do not accept arguments")
        setattr(device, attr_name, value)

    def get_param(self, device, attr_name, arguments={}):
        if len(arguments) > 0:
            attr_def = attr.get_class_attrs(device)[attr_name]
            raise ValueError(f"{attr_def.ROLE} properties do not accept arguments")
        return getattr(device, attr_name)

    def test_basic_get(self):
        device = self.DeviceClass()
        device.open()

        self.get_param(device, "any")

    def test_basic_set(self):
        device = self.DeviceClass()
        device.open()

        self.set_param(device, "any", 5)
        self.assertEqual(self.get_param(device, "any"), 5)

    def test_cache(self):
        device = self.DeviceClass()
        device.open()

        # repeat to set->get to ensure proper caching
        self.eval_set_then_get(device, "str_cached")
        result = self.eval_set_then_get(device, "str_cached")
        self.assertEqual(len(result["notifications"]), 2, "notification count for cached string")

    def test_default_types(self):
        device = self.DeviceClass()
        device.open()

        for attr_def in device.get_attr_defs().values():
            if not isinstance(attr_def, self.ROLE_TYPE):
                continue

            value = getattr(device, attr_def.name)

            if attr_def.allow_none:
                allow_types = (type(None), attr_def._type)
            else:
                allow_types = (attr_def._type,)

            if issubclass(attr_def._type, Number):
                allow_types = allow_types + (Number,)

            self.assertTrue(
                issubclass(type(value), allow_types),
                msg=f"pythonic type of {attr_def.name}",
            )

    def test_default_values(self):
        device = self.DeviceClass()
        device.open()

        for attr_def in device.get_attr_defs().values():
            if not isinstance(attr_def, self.ROLE_TYPE):
                continue

            value = getattr(device, attr_def.name)
            self.assertTrue(value == attr_def.default, msg=f"pythonic type of {attr_def.name}")

    def test_only(self):
        device = self.DeviceClass()
        device.open()

        # low bound
        expected_valid = self.DeviceClass.str_with_only.only[0]
        alt_case = change_case(expected_valid)

        device.str_with_only = expected_valid
        with self.assertRaises(ValueError):
            device.str_with_only = "boris"
        with self.assertRaises(ValueError):
            device.str_with_only = alt_case

        # with string case
        expected_valid = self.DeviceClass.str_no_case_with_only.only[0]
        alt_case = change_case(expected_valid)

        device.str_no_case_with_only = expected_valid
        with self.assertRaises(ValueError):
            device.str_no_case_with_only = "boris"
        device.str_no_case_with_only = alt_case

    def test_numeric_bounds(self):
        device = self.DeviceClass()
        device.open()

        # float_low_bounded
        lo_bound = self.DeviceClass.float_low_bounded.min
        with self.assertRaises(ValueError):
            device.float_low_bounded = lo_bound - 1
        device.float_low_bounded = lo_bound + 1

        # float_high_bounded
        hi_bound = self.DeviceClass.float_high_bounded.max
        with self.assertRaises(ValueError):
            device.float_high_bounded = hi_bound + 1
        device.float_high_bounded = hi_bound - 1

        # float_none_bounded
        device.float_none_bounded = None

    def test_numeric_casting(self):
        device = self.DeviceClass()
        device.open()

        # float
        value_in = "3.91"
        expected_out = float(value_in)
        device.float_low_bounded = value_in
        value_out = device.float_low_bounded
        self.assertEqual(value_out, expected_out, "string to float casting")

        # float
        value_in = "-48"
        expected_out = int(value_in)
        device.int_no_default = value_in
        value_out = device.int_no_default
        self.assertEqual(value_out, expected_out, "string to float casting")

    def test_str_casting(self):
        device = self.DeviceClass()
        device.open()

        # float
        value_in = -48
        expected_out = str(value_in)
        device.str = value_in
        value_out = device.str
        self.assertEqual(value_out, expected_out, "string to float casting")

    def test_numeric_step(self):
        device = self.DeviceClass()
        device.open()

        # rounding tests (step is not None)
        device.float_stepped = 3
        self.assertEqual(device.float_stepped, 3.0)
        device.float_stepped = 2
        self.assertEqual(device.float_stepped, 3.0)
        device.float_stepped = 4
        self.assertEqual(device.float_stepped, 3.0)
        device.float_stepped = 1.6
        self.assertEqual(device.float_stepped, 3.0)
        device.float_stepped = -2
        self.assertEqual(device.float_stepped, -3.0)
        device.float_stepped = -1
        self.assertEqual(device.float_stepped, 0)

    def test_device_initialization(self):
        def should_test_this_attr(attr_def: attr.ParamAttr):
            return (
                attr_def.name in self.DeviceClass.__annotations__
                and isinstance(attr_def, self.ROLE_TYPE)
                and attr_def.sets
                and not has_steps(attr_def)
            )

        device = self.DeviceClass()
        device.open()

        for attr_def in device.get_attr_defs().values():
            if not should_test_this_attr(attr_def):
                continue

            test_name = f'{attr_def.ROLE} "{attr_def.name}"'

            value_in = self.DeviceClass.LOOP_TEST_VALUES[attr_def._type]

            device = self.DeviceClass(**{attr_def.name: value_in})

            with device:
                value_out = getattr(device, attr_def.name)
                self.assertEqual(
                    value_in,
                    value_out,
                    f"{test_name} - initialize default values from Device constructor",
                )


class TestAdjustedValueParamAttr(TestValueParamAttr):
    DeviceClass = AdjustedTestDevice
    ROLE_TYPE = attr.value.Value

    def test_numeric_step(self):
        device = self.DeviceClass()
        device.open()

        self.assertEqual(device.bool, False)


class TestRequiredArgumentParamAttr(unittest.TestCase):
    DeviceClass = RequiredParametersTestDevice

    def test_instantiation(self):
        with self.assertRaises(TypeError, msg="instantiation without required keyword arguments"):
            device = self.DeviceClass()

        device = self.DeviceClass(required_str="hi", required_str_allow_none=None)


if __name__ == "__main__":
    lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("info")
    lb.util.force_full_traceback(True)

    unittest.main()
