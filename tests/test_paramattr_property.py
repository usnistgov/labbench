from labbench.testing import pyvisa_sim, store_backend, pyvisa_sim_resource
import labbench as lb
from labbench import paramattr as param
import unittest
import paramattr_tooling

lb._force_full_traceback(True)

# @lb.key_argument('channel', param.argument.int(min=1, max=4))
@store_backend.key_store_adapter(defaults={"str_or_none": None, "str_cached": "cached string"})
class StoreTestDevice(store_backend.ParamAttrTestDevice):
    LOOP_TEST_VALUES = {
        # make sure all test values conform to these general test values
        int: 5,
        float: 3.14,
        str: "hi",
        bool: True,
        object: None
    }

    # test both getting and setting
    bool_keyed = param.property.bool(key="bool_keyed")
    int_keyed_unbounded = param.property.int(key="int_keyed_unbounded")

    @param.property.int(min=0, sets=False)
    def int_decorated_low_bound_getonly(self):
        return self.backend.setdefault("int_decorated_low_bound_getonly", 0)

    @param.property.int(min=10, gets=False)
    def int_decorated_low_bound_setonly(self, set_value=lb.Undefined, *, channel=1):
        self.backend["int_decorated_high_bound_setonly"] = set_value

    str_or_none = param.property.str(key="str_or_none", allow_none=True)
    str_cached = param.property.str(key="str_cached", cache=True)
    any = param.property.any(key='any', allow_none=True)


class TestPropertyParamAttr(paramattr_tooling.TestParamAttr):
    DeviceClass = StoreTestDevice
    role = lb.paramattr.ParamAttr.ROLE_PROPERTY

    def set_param(self, device, attr_name, value, arguments={}):
        if len(arguments) > 0:
            raise ValueError('properties do not accept arguments')
        setattr(device, attr_name, value)

    def get_param(self, device, attr_name, arguments={}):
        if len(arguments) > 0:
            raise ValueError('properties do not accept arguments')
        return getattr(device, attr_name)

    def test_basic_get(self):
        device = self.DeviceClass()
        device.open()

        self.get_param(device, 'any')

    def test_basic_set(self):
        device = self.DeviceClass()
        device.open()

        self.set_param(device, 'any', 5)
        self.assertEqual(self.get_param(device, 'any'), 5)

    def test_cache(self):
        device = self.DeviceClass()
        device.open()

        # repeat to set->get to ensure proper caching
        self.eval_set_then_get(device, 'str_cached')
        result = self.eval_set_then_get(device, 'str_cached')

        self.assertEqual(
            result['get_count'],
            0,
            msg=f'cache test - second "get" operation count',
        )
        self.assertEqual(
            result['set_count'],
            2,
            msg=f'cache test - second "get" operation count',
        )


# class TestProperty:
#     # set this in a subclass
#     TestDevice: lb.Device = None

#     def test_set_then_get(self):
#         with self.TestDevice() as device:
#             attr_names = set(self.TestDevice._attr_defs.method_names()) - set(dir(lb.Device))

#             for name in attr_names:
#                 msg = f'method "{name}"'
#                 trait = device._traits[name]

#                 if not (trait.sets and trait.gets):
#                     # this test is only for traits that support both set and get
#                     continue

#                 device.clear_counts()
#                 setattr(device, name, new_value)

#                 # in cases of remap, ensure the stored value in the mock device
#                 # matches the expected
#                 self.assertEqual(
#                     device.backend.values[name],
#                     device.get_expected_remote_value(name, new_value),
#                     msg=msg,
#                 )

#                 # validate the pythonic value
#                 self.assertEqual(
#                     getattr(device, name), new_value, msg=msg
#                 )  # +1 get (unless cached)

#                 # make sure there weren't any unecessary extra 'get' operations
#                 self.assertEqual(device.get_get_count(name), 0 if trait.cache else 1, msg=msg)

#     def test_disabled_set(self):
#         with self.TestDevice() as m:
#             m.clear_counts()

#             for trait_name, new_value in m.PYTHONIC_VALUE_UPDATE.items():
#                 trait = m._traits[trait_name]
#                 msg = f'property "{trait_name}"'

#                 if not trait.sets:
#                     with self.assertRaises(AttributeError, msg=msg):
#                         setattr(m, trait_name, new_value)

#     def test_cache(self):
#         with self.TestDevice() as m:
#             m.clear_counts()

#             for trait_name, new_value in m.PYTHONIC_VALUE_UPDATE.items():
#                 if m._traits[trait_name].cache:
#                     msg = f'property "{trait_name}"'

#                     # Device gets should only happen once if cache=True
#                     m.clear_counts()
#                     self.assertEqual(
#                         getattr(m, trait_name),
#                         m.PYTHONIC_VALUE_DEFAULT[trait_name],
#                         msg=msg,
#                     )
#                     self.assertEqual(
#                         getattr(m, trait_name),
#                         m.PYTHONIC_VALUE_DEFAULT[trait_name],
#                         msg=msg,
#                     )
#                     self.assertEqual(m.get_get_count(trait_name), 1, msg=msg)

#     def test_get_default(self):
#         """
#         Ensure that values are returned, typing is correct, and
#         """
#         with self.TestDevice() as m:
#             m.clear_counts()

#             # remapped bool "get"
#             for trait_name, value in m.PYTHONIC_VALUE_DEFAULT.items():
#                 msg = f'testing property "{trait_name}"'
#                 self.assertEqual(getattr(m, trait_name), value, msg=msg)
#                 self.assertEqual(m.get_get_count(trait_name), 1, msg=msg)


# class TestDecoratedProperty(unittest.TestCase, TestProperty):
#     TestDevice = MockDirectProperty


# class TestKeyedProperty(unittest.TestCase, TestProperty):
#     TestDevice = MockDirectProperty


if __name__ == "__main__":
    lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("debug")
    lb.util._force_full_traceback(True)

    # # specify the VISA address to use the power sensor
    # inst = pyvisa_sim.Oscilloscope()  # (resource='USB::0x1111::0x2233::0x9876::INSTR')
    # print(inst._attr_defs.attrs.keys())

    # with inst:
    #     inst.resolution_bandwidth(10e3, channel=2)
    #     print(repr(inst.resolution_bandwidth(channel=1)))

    unittest.main()
