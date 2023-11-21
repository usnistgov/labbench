from labbench.testing import store_backend
import labbench as lb
from labbench import paramattr as attr
import unittest
import paramattr_tooling

lb.util.force_full_traceback(True)

@attr.register_key_argument('registered_channel', attr.argument.int(min=1, max=4))
@store_backend.key_store_adapter(defaults={"str_or_none": None, "str_cached": "cached string"})
class StoreTestDevice(store_backend.TestStoreDevice):
    LOOP_TEST_VALUES = {
        # make sure all test values conform to these general test values
        int: 5,
        float: 3.14,
        str: "hi",
        bool: True,
        object: None,
    }

    ARGUMENTS = {"channel": [1, 2]}

    # test both getting and setting
    bool_keyed = attr.method.bool(key="bool_keyed")
    int_keyed_unbounded = attr.method.int(key="int_keyed_unbounded")

    @attr.method.int(min=0, sets=False)
    def int_decorated_low_bound_getonly(self):
        return self.backend.setdefault("int_decorated_low_bound_getonly", 0)

    @attr.method.int(min=10, gets=False)
    def int_decorated_low_bound_setonly(self, set_value=lb.Undefined, *, channel=1):
        self.backend["int_decorated_high_bound_setonly"] = set_value

    str_or_none = attr.method.str(key="str_or_none", allow_none=True)
    str_cached = attr.method.str(key="str_cached", cache=True)
    any = attr.method.any(key="any", allow_none=True)

    str_keyed_with_arg = attr.method.str(key="str_with_arg_ch_{registered_channel}")

    @attr.method.str(arguments={'decorated_channel': attr.argument.int(min=1, max=4)})
    def str_decorated_with_arg(self, set_value=lb.Undefined, *, decorated_channel):
        key = self.backend.get_backend_key(self, type(self).str_decorated_with_arg, {'decorated_channel': decorated_channel})

        if set_value is not lb.Undefined:
            self.backend.set(key, set_value)
        else:
            return self.backend.get(key, None)
        
    bla = attr.method.str(arguments={'decorated_channel': attr.argument.int(min=1, max=4)})


class TestMethod(paramattr_tooling.TestParamAttr):
    DeviceClass = StoreTestDevice
    role = lb.paramattr.ParamAttr.ROLE_METHOD

    def set_param(self, device, attr_name, value, arguments={}):
        param_method = getattr(device, attr_name)
        param_method(value, **arguments)

    def get_param(self, device, attr_name, arguments={}):
        param_method = getattr(device, attr_name)
        return param_method(**arguments)

    def test_cache(self):
        device = self.DeviceClass()
        device.open()

        # repeat to set->get to ensure proper caching
        self.eval_set_then_get(device, "str_cached")
        result = self.eval_set_then_get(device, "str_cached")

        self.assertEqual(
            result["get_count"],
            0,
            msg=f'cache test - second "get" operation count',
        )
        self.assertEqual(
            result["set_count"],
            2,
            msg=f'cache test - second "get" operation count',
        )

    def test_keyed_argument_bounds(self):
        device = self.DeviceClass()
        device.open()

        TEST_VALUE = "text"

        with self.assertRaises(ValueError):
            device.str_keyed_with_arg(TEST_VALUE, registered_channel=0)

        device.str_keyed_with_arg(TEST_VALUE, registered_channel=1)
        expected_key = ('str_with_arg_ch_{registered_channel}', frozenset({('registered_channel', 1)}))
        self.assertEqual(device.backend.values[expected_key], TEST_VALUE)

    def test_decorated_argument_bounds(self):
        device = self.DeviceClass()
        device.open()

        TEST_VALUE = "text"
        with self.assertRaises(ValueError):
            device.str_decorated_with_arg(TEST_VALUE, decorated_channel=0)
        
        device.str_decorated_with_arg(TEST_VALUE, decorated_channel=1)
        expected_key = ('str_decorated_with_arg', frozenset({('decorated_channel', 1)}))
        self.assertEqual(device.backend.values[expected_key], TEST_VALUE)

def func(i: int):
    pass

bare = attr.method.str(arguments={'decorated_channel': attr.argument.int(min=1, max=4)})
wrapped = bare(func)

# class SimpleDevice(lb.VISADevice):
#     v: int = attr.value.int(default=4)
#     m = attr.method.float(key="ch{channel}:bw")


if __name__ == "__main__":
    # lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("info")
    lb.util.force_full_traceback(True)

    unittest.main()
