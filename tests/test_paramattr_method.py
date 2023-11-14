from labbench.testing import pyvisa_sim, store_backend, pyvisa_sim_resource
import labbench as lb
from labbench import paramattr as param
import unittest
import paramattr_tooling

lb._force_full_traceback(True)


@store_backend.key_store_adapter(defaults={"str_or_none": None, "str_cached": "cached string"})
class StoreTestDevice(store_backend.TestStoreDevice):
    LOOP_TEST_VALUES = {
        # make sure all test values conform to these general test values
        int: 5,
        float: 3.14,
        str: "hi",
        bool: True,
        object: None
    }

    ARGUMENTS = {
        'channel': [1, 2]
    }

    # test both getting and setting
    bool_keyed = param.method.bool(key="bool_keyed")
    int_keyed_unbounded = param.method.int(key="int_keyed_unbounded")

    @param.method.int(min=0, sets=False)
    def int_decorated_low_bound_getonly(self):
        return self.backend.setdefault("int_decorated_low_bound_getonly", 0)

    @param.method.int(min=10, gets=False)
    def int_decorated_low_bound_setonly(self, set_value=lb.Undefined, *, channel=1):
        self.backend["int_decorated_high_bound_setonly"] = set_value

    str_or_none = param.method.str(key="str_or_none", allow_none=True)
    str_cached = param.method.str(key="str_cached", cache=True)
    any = param.method.any(key='any', allow_none=True)


class TestMethod(paramattr_tooling.TestParamAttr):
    DeviceClass = StoreTestDevice
    role = lb.paramattr.ParamAttr.ROLE_METHOD

    def set_param(self, device, attr_name, value, arguments={}):
        attr_def = getattr(type(device), attr_name)
        if len(attr_def.get_key_arguments(type(device))) > 0:
            raise ValueError('argument tests not implemented yet')

        param_method = getattr(device, attr_name)
        param_method(value, **arguments)

    def get_param(self, device, attr_name, arguments={}):
        attr_def = getattr(type(device), attr_name)
        if len(attr_def.get_key_arguments(type(device))) > 0:
            raise ValueError('argument tests not implemented yet')

        param_method = getattr(device, attr_name)
        return param_method(**arguments)

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


param.register_key_argument('channel', param.argument.int(min=1, max=4))
class SimpleDevice(lb.VISADevice):
    v: int = param.value.int(default=4)
    m = param.method.float(key='ch{channel}:bw')

if __name__ == "__main__":
    lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("info")
    lb.util.force_full_traceback(True)

    unittest.main()
