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
import pandas as pd
import numpy as np
if '..' not in sys.path:
    sys.path.insert(0, '..')

remap = {True: 'ON', False: 'OFF'}
flag_start = False


class TrialDevice(lb.Device):
    _getter_counts = {}

    float0 = lb.value.float()
    float1 = lb.value.float(min=0, max=10, help='descriptive', label='items')
    float2 = lb.value.float(only=(0,3,96))
    float3 = lb.value.float(step=3)
    
    int0 = lb.value.int()
    int1 = lb.value.int(min=0, max=10, help='descriptive', label='items')
    int2 = lb.value.int(only=(0,3,96))
 
    str0 = lb.value.str()
    str1 = lb.value.str(default='hello')
    str2 = lb.value.str('moose', only=('moose', 'squirrel'))
    str3 = lb.value.str('moose', only=('MOOSE', 'squirrel'), case=False)

    df0 = lb.value.DataFrame(pd.DataFrame([0,1,2,3,4,5]))
    series0 = lb.value.Series(pd.Series([0,1,2,3,4,5]))
    array0 = lb.value.array(np.array([0,1,2,3,4,5]))
    
class UpdateTrialDevice(TrialDevice):
    float0 = 7

class TestValueTraits(unittest.TestCase):
    def test_default_types(self):
        with TrialDevice() as m:
            for name in m._value_attrs:
                trait = m._traits[name]
                value = getattr(m,name)

                if trait.allow_none:
                    allow_types = (type(None), trait.type)
                else:
                    allow_types = trait.type

                self.assertTrue(issubclass(type(value), allow_types), msg=f'trait {name}')

    def test_scalar_defaults(self):
        with TrialDevice() as m:
            for name in m._value_attrs:
                trait = m._traits[name]

                if isinstance(trait, lb._traits.NonScalar):
                    continue

                value = getattr(m,name)

                self.assertEqual(getattr(m, name),
                                trait.default, msg=f'defaults: {name}')


    def assertArrayEqual(self, a1, a2):
        self.assertEqual(a1.dtype, a2.dtype)
        self.assertEqual(a1.shape, a2.shape)
        self.assertTrue(np.allclose(a1,a2))

    def test_nonscalar_defaults(self):
        with TrialDevice() as m:
            for name in m._value_attrs:
                trait = m._traits[name]

                v = getattr(m, name)

                if trait.type in (pd.DataFrame, pd.Series):
                    self.assertArrayEqual(v.values, trait.default.values)
                    self.assertArrayEqual(v.index.values, trait.default.index.values)
                    self.assertEqual(v.index.name, trait.default.index.name)
                elif trait.type is np.ndarray:
                    self.assertArrayEqual(v, trait.default)

    def test_initialization(self):
        value = 3
        for i in range(4):
            with TrialDevice(**{f'float{i}': value}) as m:
                self.assertEqual(getattr(m, f'float{i}'), value,
                                 msg=f'float{i}')
                
        value = 3
        for i in range(2):
            with TrialDevice(**{f'int{i}': value}) as m:
                self.assertEqual(getattr(m, f'int{i}'), value,
                                 msg=f'int{i}')                

        value = 'moose'
        for i in range(4):
            with TrialDevice(**{f'str{i}': value}) as m:
                self.assertEqual(getattr(m, f'str{i}'), value,
                                 msg=f'str{i}')

    def test_casting(self):
        value = '3'
        expected = 3
        for i in range(4):
            with TrialDevice(**{f'float{i}': value}) as m:
                self.assertEqual(getattr(m, f'float{i}'), expected,
                                 msg=f'float{i}')

        value = 437
        expected = '437'
        for i in range(2):
            with TrialDevice(**{f'str{i}': value}) as m:
                self.assertEqual(getattr(m, f'str{i}'), expected,
                                 msg=f'str{i}')

    def test_param_case(self):
        with self.assertRaises(ValueError):           
            with TrialDevice() as m:
                m.str2 = 'MOOSE'

        with TrialDevice() as m:
            m.str3 = 'SQUIRREL'
            m.str3 = 'squirrel'
            m.str3 = 'moose'

    def test_param_only(self):
        with TrialDevice() as m:
            self.assertEqual(m.float2, 0)
            m.float2 = 3
            self.assertEqual(m.float2, 3)
            with self.assertRaises(ValueError):
                m.float2 = 4
            with self.assertRaises(ValueError):
                m.float2 = 3.3
            self.assertEqual(m.float2, 3)

    def test_param_bounds(self):
        with TrialDevice() as m:
            self.assertEqual(m.float1, 0)
            m.float1 = 3
            self.assertEqual(m.float1, 3)
            with self.assertRaises(ValueError):
                m.float1 = -1
            with self.assertRaises(ValueError):
                m.float1 = 11

    def test_param_step(self):
        with TrialDevice() as m:
            # rounding tests
            self.assertEqual(m.float3, 0.)
            m.float3 = 3
            self.assertEqual(m.float3, 3.)
            m.float3 = 2
            self.assertEqual(m.float3, 3.)
            m.float3 = 4
            self.assertEqual(m.float3, 3.)
            m.float3 = 1.6
            self.assertEqual(m.float3, 3.)
            m.float3 = -2
            self.assertEqual(m.float3, -3.)
            m.float3 = -1
            self.assertEqual(m.float3, 0) 

    def test_init_docstring(self):
        self.assertIn('descriptive', TrialDevice.__init__.__doc__)
        with TrialDevice() as m:
            self.assertIn('descriptive', m.__init__.__doc__)
            
    def test_subclassing(self):
        with UpdateTrialDevice() as m:
            print(m.float0)
            self.assertEqual(m.float0, 7.0)

if __name__ == '__main__':
    lb.show_messages('debug')
    unittest.main()