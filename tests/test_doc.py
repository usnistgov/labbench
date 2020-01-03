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
# BY PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
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


int_start = 3
int_stop = 10


class MockBase(lb.Device):
    class state(lb.Device.state):
        param = lb.Int(min=0, max=10)

    def connect(self):
        self.values = {'param': int_start}


class MockTraitWrapper(MockBase):
    ''' Helpful driver wrapper
    '''
    class state(MockBase.state):
        pass

    @state.param.getter
    def _(self):
        return self.values['param']

    @state.param.setter
    def _(self, value):
        self.values['param'] = value


class MockStateWrapper(MockBase):
    class state(MockBase.state):
        pass

    @state.getter
    def _(self, trait):
        return self.values[trait.name]

    @state.setter
    def _(self, trait, value):
        self.values[trait.name] = value

# class TestWrappers(unittest.TestCase):
#     def test_state_wrapper_type(self):
#         with MockStateWrapper() as m:
#             self.assertEqual(m.state.param,int_start)
#             m.state.param = int_stop
#             self.assertEqual(m.state.param,int_stop)
#
#
#     def test_trait_wrapper_type(self):
#         with MockTraitWrapper() as m:
#             self.assertEqual(m.state.param,int_start)
#             m.state.param = int_stop
#             self.assertEqual(m.state.param,int_stop)


if __name__ == '__main__':
    device = MockTraitWrapper(resource='null')
    

    print('instance doc: \n', device.state.__doc__)
    print('class doc: ', MockTraitWrapper.state.__doc__)
    print('class parent doc: ', super(MockTraitWrapper.state,MockTraitWrapper.state), super(MockTraitWrapper.state,MockTraitWrapper.state).__doc__)
