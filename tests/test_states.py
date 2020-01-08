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


remap = {True: 'ON', False: 'OFF'}

start = {'param': 3,
         'flag': False}

stop = {'param': 10,
        'flag': True}

flag_start = False


class MockBase(lb.Device):
    _getter_counts = {}
    
    class state(lb.Device.state):
        param = lb.Int(min=0, max=10, command=True)
        flag = lb.Bool(remap=remap, command=True)

    def connect(self):
        self.values = {}
        for k in self.state.class_traits().keys():
            if k in start:
                v = start[k]
                self.values[k] = remap.get(v, v)
                
    def clear_counts(self):
        self._getter_counts = {}


class MockOldTraitWrapper(MockBase):    
    class state(MockBase.state):
        pass

    @state.param.getter
    def _(self):
        self._getter_counts.setdefault('param',0)
        self._getter_counts['param'] += 1

        self.logger.debug('get param')
        return self.values['param']

    @state.param.setter
    def _(self, value):
        self.values['param'] = value

    @state.flag.getter
    def _(self):
        self._getter_counts.setdefault('flag',0)
        self._getter_counts['flag'] += 1        
        
        return self.values['flag']

    @state.flag.setter
    def _(self, value):
        self.values['flag'] = value


class MockOldStateWrapper(MockBase):
    class state(MockBase.state):
        pass

    @state.getter
    def _(self, trait):
        return self.values[trait.name]

    @state.setter
    def _(self, trait, value):
        print('*****', trait, repr(value))
        self.values[trait.name] = value

class MockTraitWrapper(MockBase):    
    param = lb.Int(min=0, max=10)
    flag = lb.Bool(remap=remap)

    @param.getter
    def _(self):
        self._getter_counts.setdefault('param',0)
        self._getter_counts['param'] += 1

        self.logger.debug('get param')
        return self.values['param']

    @param.setter
    def _(self, value):
        self.values['param'] = value

    @flag.getter
    def _(self):
        self._getter_counts.setdefault('flag',0)
        self._getter_counts['flag'] += 1        
        
        return self.values['flag']

    @flag.setter
    def _(self, value):
        self.values['flag'] = value
        
class MockStateWrapper(MockBase):
    def __get_state__(self, trait):
        return self.values[trait.name]

    def __set_state__(self, trait, value):
        print('*****', trait, repr(value))
        self.values[trait.name] = value        


class TestWrappers(unittest.TestCase):
    def test_old_state_wrapper_type(self):
        with MockOldStateWrapper() as m:
            self.do(m)            

    def test_old_trait_wrapper_type(self):
        with MockOldTraitWrapper() as m:
            self.do(m)
            
    def test_state_wrapper_type(self):
        with MockStateWrapper() as m:
            self.do(m)

    def test_trait_wrapper_type(self):
        with MockTraitWrapper() as m:
            self.do(m)
            
    def do(self, m):
        m.clear_counts()
        
        self.assertEqual(m.state.param, start['param'])
        m.state.param = stop['param']
        self.assertEqual(m.state.param, stop['param'])

        self.assertEqual(m.state.flag, False)
        m.state.flag = stop['flag']
        
        self.assertEqual(m.state.flag, stop['flag'])
        self.assertEqual(m.values['flag'], remap[stop['flag']])
        
        self.assertEqual(m._getter_counts['flag'], 4)
        self.assertEqual(m._getter_counts['param'], 4)

if __name__ == '__main__':
    lb.show_messages('debug')
    unittest.main()

#    with MockTraitWrapper() as m:
#        m.state.param = 4
#        print(dir(m.state))
#        print(m.state.__doc__)
#        print(m.settings.__doc__)
