import unittest
import labbench as lb


class TestParamAttr(unittest.TestCase):
    # set this in a subclass
    DeviceClass = lb.Undefined

    def set_param(self, device, attr_name, value, arguments={}):
        raise NotImplementedError
    
    def get_param(self, device, attr_name, arguments={}):
        raise NotImplementedError

    def eval_set_then_get(self, device, attr_name, value_in=lb.Undefined, arguments={}):
        attr_def = getattr(type(device), attr_name)

        if value_in is lb.Undefined:
            value_in = device.LOOP_TEST_VALUES[attr_def.type]

        self.set_param(device, attr_name, value_in, arguments)
        value_out = self.get_param(device, attr_name, arguments)

        backend_key = device.backend.get_backend_key(device, attr_def, arguments)

        return {
            'value_in': value_in,
            'value_out': value_out, 
            'get_count': device.backend.get_count[backend_key],
            'set_count': device.backend.set_count[backend_key],
            'notifications': device.backend.notifications
        }

    def test_all_set_then_get(self, role):
        device = self.DeviceClass()
        device.open()

        attrs = {
            name: attr
            for name, attr in device.get_attr_defs().items()
            if attr.role == role and attr.sets and attr.gets and not hasattr(lb.Device, name)
        }

        for attr_name, attr_def in attrs.items():
            print(attr_name, attr_def)
            test_name = f'{role} "{attr_name}"'

            device.backend.clear_counts()

            if len(attr_def.get_key_arguments(type(device))) > 0:
                # only test methods that don't require additional arguments beyond the set value
                # TODO: fix this
                continue

            result = self.eval_set_then_get(device, attr_name)

            self.assertEqual(
                result['value_in'],
                result['value_out'],
                msg=f"{test_name} - set-get input and output values",
            )

            self.assertEqual(
                len(result['notifications']),
                1 if attr_def.cache else 2,
                msg=f"{test_name} - callback notification count"
            )

            self.assertEqual(
                result['notifications'][0]['old'],
                lb.Undefined,
                msg=f"{test_name} - callback notification prior value for 'set'"
            )

            if not attr_def.cache:
                self.assertEqual(
                    result['notifications'][1]['old'],
                    result['value_in'],
                    msg=f"{test_name} - callback notification prior value for 'get'"
                )

            # make sure there weren't any unecessary extra 'get' operations
            self.assertEqual(
                result['get_count'],
                0 if attr_def.cache else 1,
                msg=f'{test_name} - "get" notification count',
            )
            self.assertEqual(
                result['set_count'],
                1,
                msg=f'{test_name} - "set" notification count',
            )

            if attr_def.cache:
                # repeat to set->get to ensure proper caching
                result = self.eval_set_then_get(device, attr_name)

                self.assertEqual(
                    result['get_count'],
                    0,
                    msg=f'{test_name} - second "get" operation count',
                )
                self.assertEqual(
                    result['set_count'],
                    2,
                    msg=f'{test_name} - second "set" operation count',
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
