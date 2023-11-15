from labbench.testing import pyvisa_sim, store_backend, pyvisa_sim_resource
import labbench as lb
from labbench import paramattr as attr
import unittest
import paramattr_tooling

lb.util.force_full_traceback(True)


@store_backend.key_store_adapter(
    defaults={"str_or_none": None, "str_cached": "cached string"}
)
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


class TestMethod(paramattr_tooling.TestParamAttr):
    DeviceClass = StoreTestDevice
    role = lb.paramattr.ParamAttr.ROLE_METHOD

    def set_param(self, device, attr_name, value, arguments={}):
        attr_def = getattr(type(device), attr_name)
        if len(attr_def.get_key_arguments(type(device))) > 0:
            raise ValueError("argument tests not implemented yet")

        param_method = getattr(device, attr_name)
        param_method(value, **arguments)

    def get_param(self, device, attr_name, arguments={}):
        attr_def = getattr(type(device), attr_name)
        if len(attr_def.get_key_arguments(type(device))) > 0:
            raise ValueError("argument tests not implemented yet")

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


class SimpleDevice(lb.VISADevice):
    v: int = attr.value.int(default=4)
    m = attr.method.float(key="ch{channel}:bw")


if __name__ == "__main__":
    lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("info")
    lb.util.force_full_traceback(True)

    unittest.main()
