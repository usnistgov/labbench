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

start = {'param': 3,
         'flag': False}

stop = {'param': 10,
        'flag': True}

flag_start = False


class MockBase(lb.Device):
    _getter_counts = {}

    param = lb.Int(command='param', min=0, max=10)
    flag = lb.Bool(command='flag', remap=remap)

    def connect(self):
        self.values = {}
        
        for name,value in start.items():
            self.values[name] = remap.get(value, value)
            
    def add_get_count(self, name):
        self._getter_counts.setdefault(name,0)
        self._getter_counts[name] += 1

    def clear_counts(self):
        self._getter_counts = {}


class MockDecorator(MockBase):    
    @param
    def param(self):
        self.add_get_count('param')
        return self.values['param']
    def param(self, value):
        self.values['param'] = value

    @flag
    def flag(self):
        self.add_get_count('flag')
        return self.values['flag']
    def flag(self, value):
        self.values['flag'] = value


class MockCommand(MockBase):
    def __command_get__(self, name, command):
        self.add_get_count(command)
        return self.values[command]

    def __command_set__(self, name, command, value):
        self.values[command] = value


class TestWrappers(unittest.TestCase):            
    def test_command_type(self):
        with MockCommand() as m:
            self.do(m)

    def test_decorator_type(self):
        with MockDecorator() as m:
            self.do(m)

    def do(self, m):
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

if __name__ == '__main__':
    lb.show_messages('debug')
    unittest.main()