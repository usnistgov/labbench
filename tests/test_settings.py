# This software was developed by employees of the National Institute of
# Standards and Technology (NIST), an agency of the Federal Government.
# Pursuant to title 17 United States Code Section 105, works of NIST employees
# are not subject to copyright protection in the United States and are
# considered to be in the public domain. Permission to freely use, copy,
# modify, and distribute this software and its documentation without fee is
# hereby granted, provided that this notice and disclaimer of warranty appears
# in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
# EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
# THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
# INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
# SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE. IN NO EVENT
# SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
# INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM,
# OR IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON
# WARRANTY, CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED
# BY PERSONS OR Decorator OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

import unittest
import importlib
import sys
if '..' not in sys.path:
    sys.path.insert(0, '..')
import labbench as lb
lb = importlib.reload(lb)

remap = {True: 'ON', False: 'OFF'}
flag_start = False


class Mock(lb.Device):
    _getter_counts = {}

    float0: lb.Float()
    float1: lb.Float(min=0, max=10, help='descriptive', label='items')
    float2: lb.Float(only=(0,3,96))
    float3: lb.Float(step=3)
    
    int0: lb.Int()
    int1: lb.Int(min=0, max=10, help='descriptive', label='items')
    int2: lb.Int(only=(0,3,96))
 
    str0: lb.Unicode()
    str1: lb.Unicode(default='hello')
    str2: lb.Unicode(default='moose', only=('moose', 'squirrel'))
    str3: lb.Unicode(default='moose', only=('MOOSE', 'squirrel'), case=False)
    
class UpdateMock(lb.Device):
    float0: 7

class UnsetMock(lb.Device):
    float0: 7
    
class Tests(unittest.TestCase):
    def test_defaults(self):
        with Mock() as m:
            for name, trait in m.settings.__traits__.items():
                self.assertEqual(getattr(m.settings, name),
                                 trait.default, msg=f'defaults: {name}')
                
    def test_initialization(self):
        value = 3
        for i in range(4):
            with Mock(**{f'float{i}': value}) as m:
                self.assertEqual(getattr(m.settings, f'float{i}'), value,
                                 msg=f'float{i}')
                
        value = 3
        for i in range(2):
            with Mock(**{f'int{i}': value}) as m:
                self.assertEqual(getattr(m.settings, f'int{i}'), value,
                                 msg=f'int{i}')                

        value = 'moose'
        for i in range(4):
            with Mock(**{f'str{i}': value}) as m:
                self.assertEqual(getattr(m.settings, f'str{i}'), value,
                                 msg=f'str{i}')

    def test_casting(self):
        value = '3'
        expected = 3
        for i in range(4):
            with Mock(**{f'float{i}': value}) as m:
                self.assertEqual(getattr(m.settings, f'float{i}'), expected,
                                 msg=f'float{i}')

        value = 437
        expected = '437'
        for i in range(2):
            with Mock(**{f'str{i}': value}) as m:
                self.assertEqual(getattr(m.settings, f'str{i}'), expected,
                                 msg=f'str{i}')

    def test_param_case(self):
        with self.assertRaises(ValueError):           
            with Mock() as m:
                m.settings.str2 = 'MOOSE'

        with Mock() as m:
            m.settings.str3 = 'SQUIRREL'
            m.settings.str3 = 'squirrel'
            m.settings.str3 = 'moose'

    def test_param_only(self):
        with Mock() as m:
            self.assertEqual(m.settings.float2, 0)
            m.settings.float2 = 3
            self.assertEqual(m.settings.float2, 3)
            with self.assertRaises(ValueError):
                m.settings.float2 = 4
            with self.assertRaises(ValueError):
                m.settings.float2 = 3.3
            self.assertEqual(m.settings.float2, 3)

    def test_param_bounds(self):
        with Mock() as m:
            self.assertEqual(m.settings.float1, 0)
            m.settings.float1 = 3
            self.assertEqual(m.settings.float1, 3)
            with self.assertRaises(ValueError):
                m.settings.float1 = -1
            with self.assertRaises(ValueError):
                m.settings.float1 = 11

    def test_param_step(self):
        with Mock() as m:
            # rounding tests
            self.assertEqual(m.settings.float3, 0)
            m.settings.float3 = 3
            self.assertEqual(m.settings.float3, 3)
            m.settings.float3 = 2
            self.assertEqual(m.settings.float3, 3)
            m.settings.float3 = 4
            self.assertEqual(m.settings.float3, 3)
            m.settings.float3 = 1.6
            self.assertEqual(m.settings.float3, 3)
            m.settings.float3 = -2
            self.assertEqual(m.settings.float3, -3)
            m.settings.float3 = -1
            self.assertEqual(m.settings.float3, 0) 

    def test_init_docstring(self):
        self.assertIn('descriptive', Mock.__init__.__doc__)
        with Mock() as m:
            self.assertIn('descriptive', m.__init__.__doc__)
            
    def test_update(self):
        with UpdateMock() as m:
            self.assertEqual(m.settings.float0, 7)
            
        with UnsetMock() as m:
            pass


if __name__ == '__main__':
    lb.show_messages('debug')
    unittest.main()