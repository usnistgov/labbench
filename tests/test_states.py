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
from copy import copy
lb = importlib.reload(lb)


remap = {True: 'ON', False: 'OFF'}

start = {'param': 3,
         'flag': False}

stop = {'param': 10,
        'flag': True}

flag_start = False


class MockBase(lb.Device):
    _getter_counts = {}

    # param = lb.Int(key='param', min=0, max=10)
    # flag = lb.Bool(key='flag', remap=remap)

    def open(self):
        self._getter_counts = {}
        self.values = {}
        self._last = {}
        
        for name,value in start.items():
            self.values[name] = remap.get(value, value)

    def add_get_count(self, name):
        self._getter_counts.setdefault(name,0)
        self._getter_counts[name] += 1

    def clear_counts(self):
        self._getter_counts = {}


class MockDecorator(MockBase):
    @lb.Int(min=0, max=10)
    def param(self, value):
        self.values['param'] = value

    def param(self):
        self.add_get_count('param')
        return self.values['param']
    
    @lb.Bool(remap=remap)
    def flag(self, value):
        self.values['flag'] = value

    def flag(self):
        self.add_get_count('flag')
        return self.values['flag']


class MockReturner(MockBase):
    param = lb.Int(key='param', min=0, max=10)
    flag = lb.Bool(key='flag', remap=remap)
    
    @param
    def param(self, a, b,c):
        return a+b+c


class MockCommand(MockBase):
    param = lb.Int(key='param', min=0, max=10)
    flag = lb.Bool(key='flag', remap=remap)
    
    def __command_get__(self, name, command):
        self.add_get_count(command)
        return self.values[command]

    def __command_set__(self, name, command, value):
        self._last[command] = value
        self.values[command] = value


class TestStates(unittest.TestCase):            
    def test_command_type(self):
        global m
        with MockCommand() as m:
            self.general(m)

    def test_decorator_type(self):
        global m
        with MockDecorator() as m:
            self.general(m)

    def general(self, m):
        m.clear_counts()
       
        self.assertEqual(m.param, start['param'])
        m.param = stop['param']
        self.assertEqual(m.param, stop['param'])

        self.assertEqual(m.flag, start['flag'])
        m.flag = stop['flag']
        self.assertEqual(m.flag, stop['flag'])

        self.assertEqual(m.values['flag'], remap[stop['flag']])

        self.assertEqual(m._getter_counts['flag'], 3)
        self.assertEqual(m._getter_counts['param'], 3)

        self.assertEqual(len(m), 1 + len(remap))

    def test_returner_type(self):
        def callback(msg):
            if msg['name'] == 'param':
                self.assertEqual(msg['new'], 6)
            
        with MockReturner() as m:
            lb.observe(m, callback)
            self.assertEqual(m.param(1,2,3), 6)

if __name__ == '__main__':
    lb.show_messages('debug')
    unittest.main()
    
    # with MockDecorator() as m:
    #     pass