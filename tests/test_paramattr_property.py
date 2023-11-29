from labbench.testing import pyvisa_sim, store_backend, pyvisa_sim_resource
import labbench as lb
from labbench import paramattr as attr
import unittest
import paramattr_tooling

lb.util.force_full_traceback(True)


# @lb.key_argument('channel', attr.argument.int(min=1, max=4))
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

    # test both getting and setting
    bool_keyed = attr.property.bool(key="bool_keyed")
    int_keyed_unbounded = attr.property.int(key="int_keyed_unbounded")

    @attr.property.int(min=0, sets=False)
    def int_decorated_low_bound_getonly(self):
        return self.backend.setdefault("int_decorated_low_bound_getonly", 0)

    @attr.property.int(min=10, gets=False)
    def int_decorated_low_bound_setonly(self, set_value=lb.Undefined, *, channel=1):
        self.backend["int_decorated_high_bound_setonly"] = set_value

    str_or_none = attr.property.str(key="str_or_none", allow_none=True)
    str_cached = attr.property.str(key="str_cached", cache=True)
    any = attr.property.any(key="any", allow_none=True)


class TestPropertyParamAttr(paramattr_tooling.TestParamAttr):
    DeviceClass = StoreTestDevice
    ROLE_TYPE = attr.property.Property

    def set_param(self, device, attr_name, value, arguments={}):
        if len(arguments) > 0:
            raise ValueError("properties do not accept arguments")
        setattr(device, attr_name, value)

    def get_param(self, device, attr_name, arguments={}):
        if len(arguments) > 0:
            raise ValueError("properties do not accept arguments")
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


if __name__ == "__main__":
    lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("info")
    lb.util.force_full_traceback(True)

    # # specify the VISA address to use the power sensor
    # inst = pyvisa_sim.Oscilloscope()  # (resource='USB::0x1111::0x2233::0x9876::INSTR')
    # print(inst._attr_defs.attrs.keys())

    # with inst:
    #     inst.resolution_bandwidth(10e3, channel=2)
    #     print(repr(inst.resolution_bandwidth(channel=1)))

    unittest.main()
