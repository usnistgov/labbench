import unittest
import labbench as lb
from labbench import paramattr as attr


def has_steps(attr: attr.ParamAttr):
    return getattr(attr, "step", None) is not None


class TestParamAttr(unittest.TestCase):
    # set this in a subclass
    DeviceClass = lb.Undefined

    # define this in a subclass to select the type of ParamAttr to test:
    # attr.value.Value, attr.property.Property, etc.
    ROLE_TYPE = None

    def set_param(self, device, attr_name, value, arguments={}):
        raise NotImplementedError

    def get_param(self, device, attr_name, arguments={}):
        raise NotImplementedError

    def eval_set_then_get(self, device, attr_name, value_in=lb.Undefined, arguments={}):
        attr_def = getattr(type(device), attr_name)

        if value_in is lb.Undefined:
            value_in = device.LOOP_TEST_VALUES[attr_def._type]

        self.set_param(device, attr_name, value_in, arguments)
        value_out = self.get_param(device, attr_name, arguments)

        backend_key = device.backend.get_backend_key(device, attr_def, arguments)

        notifications = [n for n in device.backend.notifications if n["name"] == attr_name]

        return {
            "value_in": value_in,
            "value_out": value_out,
            "get_count": device.backend.get_count[backend_key],
            "set_count": device.backend.set_count[backend_key],
            "notifications": notifications,
        }

    def test_instantiate(self):
        device = self.DeviceClass()

    def test_open(self):
        with self.DeviceClass():
            pass

    def test_all_set_then_get(self):
        def want_to_set_get(attr_def):
            return (
                isinstance(attr_def, self.ROLE_TYPE)
                and attr_def.sets
                and attr_def.gets
                and not hasattr(lb.Device, attr_def.name)
                and not has_steps(attr_def)  # steps can make set != get
            )

        device = self.DeviceClass()
        device.open()

        attrs = {
            name: attr_def
            for name, attr_def in device.get_attr_defs().items()
            if want_to_set_get(attr_def)
        }

        for attr_name, attr_def in attrs.items():
            if isinstance(attr_def, attr.method.Method):
                # skip methods with arguments for now
                if len(attr_def.get_key_arguments(type(device))) > 0:
                    continue
            test_name = f'{attr_def.ROLE} "{attr_name}"'
            has_reduced_access_count = attr_def.cache or isinstance(attr_def, attr.value.Value)

            device.backend.clear_counts()

            result = self.eval_set_then_get(device, attr_name)

            self.assertEqual(
                result["value_in"],
                result["value_out"],
                msg=f"{test_name} - set-get input and output values",
            )

            self.assertEqual(
                len(result["notifications"]),
                1 if has_reduced_access_count else 2,
                msg=f"{test_name} - callback notification count",
            )

            if isinstance(attr_def, attr.value.Value):
                if len(result["notifications"]) > 1:
                    self.assertEqual(
                        result["notifications"][0]["old"],
                        attr_def.default,
                        msg=f"{test_name} - callback notification prior value for 'set'",
                    )
            else:
                self.assertEqual(
                    result["notifications"][0]["old"],
                    lb.Undefined,
                    msg=f"{test_name} - callback notification prior value for 'set'",
                )

            if not attr_def.cache and len(result["notifications"]) > 1:
                self.assertEqual(
                    result["notifications"][1]["old"],
                    result["value_in"],
                    msg=f"{test_name} - callback notification prior value for 'get'",
                )

            # make sure there weren't any unecessary extra 'get' operations
            self.assertEqual(
                result["get_count"],
                0 if has_reduced_access_count else 1,
                msg=f'{test_name} - "get" notification count',
            )
            self.assertEqual(
                result["set_count"],
                0 if isinstance(attr_def, attr.value.Value) else 1,
                msg=f'{test_name} - "set" notification count',
            )

    # def test_disabled_set(self):
    #     with self.DeviceClass() as m:
    #         m.clear_counts()

    #         for trait_name, new_value in m.PYTHONIC_VALUE_UPDATE.items():
    #             trait = m._traits[trait_name]
    #             msg = f'property "{trait_name}"'

    #             if not trait.sets:
    #                 with self.assertRaises(AttributeError, msg=msg):
    #                     setattr(m, trait_name, new_value)

    # def test_cache(self):
    #     with self.DeviceClass() as m:
    #         m.clear_counts()

    #         for trait_name, new_value in m.PYTHONIC_VALUE_UPDATE.items():
    #             if m._traits[trait_name].cache:
    #                 msg = f'property "{trait_name}"'

    #                 # Device gets should only happen once if cache=True
    #                 m.clear_counts()
    #                 self.assertEqual(
    #                     getattr(m, trait_name),
    #                     m.PYTHONIC_VALUE_DEFAULT[trait_name],
    #                     msg=msg,
    #                 )
    #                 self.assertEqual(
    #                     getattr(m, trait_name),
    #                     m.PYTHONIC_VALUE_DEFAULT[trait_name],
    #                     msg=msg,
    #                 )
    #                 self.assertEqual(m.get_get_count(trait_name), 1, msg=msg)
