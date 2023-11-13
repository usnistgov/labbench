import unittest
import labbench as lb

class TestParamAttr(unittest.TestCase):
    # set this in a subclass
    DeviceClass = lb.Undefined

    ROLE = lb.Undefined

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

        notifications = [
            n for n in device.backend.notifications
            if n['name'] == attr_name
        ]

        return {
            'value_in': value_in,
            'value_out': value_out, 
            'get_count': device.backend.get_count[backend_key],
            'set_count': device.backend.set_count[backend_key],
            'notifications': notifications
        }

    def test_instantiate(self):
        device = self.DeviceClass()

    def test_open(self):
        with self.DeviceClass():
            pass

    def test_all_set_then_get(self):
        device = self.DeviceClass()
        device.open()

        attrs = {
            name: attr
            for name, attr in device.get_attr_defs().items()
            if attr.role == self.role and attr.sets and attr.gets and not hasattr(lb.Device, name)
        }

        for attr_name, attr_def in attrs.items():
            test_name = f'{self.role} "{attr_name}"'
            has_reduced_access_count = attr_def.cache or attr_def.role == attr_def.ROLE_VALUE

            device.backend.clear_counts()

            result = self.eval_set_then_get(device, attr_name)

            self.assertEqual(
                result['value_in'],
                result['value_out'],
                msg=f"{test_name} - set-get input and output values",
            )

            self.assertEqual(
                len(result['notifications']),
                1 if has_reduced_access_count else 2,
                msg=f"{test_name} - callback notification count"
            )

            if attr_def.role == attr_def.ROLE_VALUE:
                if len(result['notifications']) > 1:
                    self.assertEqual(
                        result['notifications'][0]['old'],
                        attr_def.default,
                        msg=f"{test_name} - callback notification prior value for 'set'"
                    )
            else:
                self.assertEqual(
                    result['notifications'][0]['old'],
                    lb.Undefined,
                    msg=f"{test_name} - callback notification prior value for 'set'"
                )

            if not attr_def.cache and len(result['notifications']) > 1:
                self.assertEqual(
                    result['notifications'][1]['old'],
                    result['value_in'],
                    msg=f"{test_name} - callback notification prior value for 'get'"
                )

            # make sure there weren't any unecessary extra 'get' operations
            self.assertEqual(
                result['get_count'],
                0 if has_reduced_access_count else 1,
                msg=f'{test_name} - "get" notification count',
            )
            self.assertEqual(
                result['set_count'],
                0 if has_reduced_access_count else 1,
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

lb.VISADevice