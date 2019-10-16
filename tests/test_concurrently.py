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
import threading
import sys
import time
from contextlib import contextmanager
if '..' not in sys.path:
    sys.path.insert(0, '..')
import labbench as lb
import numpy as np
lb = importlib.reload(lb)



class LaggyInstrument(lb.EmulatedVISADevice):
    ''' A mock "instrument"
    with settings and states to
    demonstrate the process of setting
    up a measurement.
    '''
    class settings (lb.EmulatedVISADevice.settings):
        delay = lb.Float(0, min=0, help='connection time')
        fetch_time = lb.Float(0, min=0, help='fetch time')
        fail_disconnect = lb.Bool(False, help='whether to raise DivideByZero on disconnect')

    def connect(self):
        self.logger.info(f'{self} connect start')        
        lb.sleep(self.settings.delay)
        self.logger.info(f'{self} connected')
        
    def fetch(self):
        ''' Return the argument after a 1s delay
        '''
        lb.logger.info(f'{self}.fetch start')
        lb.sleep(self.settings.fetch_time)
        lb.logger.info(f'{self}.fetch done')
        return self.settings.fetch_time
    
    def disconnect(self):
        if self.settings.fail_disconnect:
            1 / 0

class TestCases(unittest.TestCase):
    # Acceptable error in delay time meaurement
    delay_tol = 0.05

    @contextmanager
    def assert_delay(self, expected_delay):
        ''' Time a block of code using a with statement like this:
    
        >>> with stopwatch('sleep statement'):
        >>>     time.sleep(2)
        sleep statement time elapsed 1.999s.
    
        :param desc: text for display that describes the event being timed
        :type desc: str
        :return: context manager
        '''   
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter()-t0
            self.assertAlmostEqual(elapsed, expected_delay, delta=self.delay_tol)                
            lb.logger.info(f'acceptable time elapsed {elapsed:0.3f}s'.lstrip())

    def test_concurrent_connect_delay(self):
        inst1 = LaggyInstrument(resource='fast', delay=0.16)
        inst2 = LaggyInstrument(resource='slow', delay=0.26)
        
        expect_delay = max((inst1.settings.delay,inst2.settings.delay))
        with self.assert_delay(expect_delay):
            with lb.concurrently(inst1, inst2):
                self.assertEqual(inst1.state.connected, True)
                self.assertEqual(inst2.state.connected, True)
        self.assertEqual(inst1.state.connected, False)
        self.assertEqual(inst2.state.connected, False)

    def test_concurrent_fetch_delay(self):
        inst1 = LaggyInstrument(resource='fast', fetch_time=0.26)
        inst2 = LaggyInstrument(resource='slow', fetch_time=0.36)
        
        expect_delay = max((inst1.settings.fetch_time,inst2.settings.fetch_time))
        with self.assert_delay(expect_delay):
            with inst1, inst2:
                self.assertEqual(inst1.state.connected, True)
                self.assertEqual(inst2.state.connected, True)               
                lb.concurrently(inst1.fetch, inst2.fetch)
        
    def test_concurrent_fetch_as_kws(self):
        inst1 = LaggyInstrument(resource='fast')
        inst2 = LaggyInstrument(resource='slow')
        
        with inst1, inst2:
            self.assertEqual(inst1.state.connected, True)
            self.assertEqual(inst2.state.connected, True)               
            ret = lb.concurrently(**{inst1.settings.resource: inst1.fetch,
                                     inst2.settings.resource: inst2.fetch})
        self.assertIn(inst1.settings.resource, ret)
        self.assertIn(inst2.settings.resource, ret)
        self.assertEqual(ret[inst1.settings.resource],
                         inst1.settings.fetch_time)
        self.assertEqual(ret[inst2.settings.resource],
                         inst2.settings.fetch_time)
        
    def test_concurrent_fetch_as_args(self):
        inst1 = LaggyInstrument(resource='fast', fetch_time=.02)
        inst2 = LaggyInstrument(resource='slow', fetch_time=.03)
        
        with inst1, inst2:
            self.assertEqual(inst1.state.connected, True)
            self.assertEqual(inst2.state.connected, True)               
            ret = lb.concurrently(inst1.fetch, inst2.fetch)
        self.assertIn('fetch_0', ret)
        self.assertIn('fetch_1', ret)
        self.assertEqual(ret['fetch_0'],
                         inst1.settings.fetch_time)
        self.assertEqual(ret['fetch_1'],
                         inst2.settings.fetch_time)
        
    def test_sequential_connect_delay(self):
        inst1 = LaggyInstrument(resource='fast', delay=0.16)
        inst2 = LaggyInstrument(resource='slow', delay=0.26)
        
        expect_delay = inst1.settings.delay + inst2.settings.delay
        with self.assert_delay(expect_delay):
            with lb.sequentially(inst1, inst2):
                self.assertEqual(inst1.state.connected, True)
                self.assertEqual(inst2.state.connected, True)
        self.assertEqual(inst1.state.connected, False)
        self.assertEqual(inst2.state.connected, False)

    def test_sequential_fetch_delay(self):
        inst1 = LaggyInstrument(resource='fast', fetch_time=0.26)
        inst2 = LaggyInstrument(resource='slow', fetch_time=0.36)
        
        expect_delay = inst1.settings.fetch_time + inst2.settings.fetch_time
        with self.assert_delay(expect_delay):
            with inst1, inst2:
                self.assertEqual(inst1.state.connected, True)
                self.assertEqual(inst2.state.connected, True)               
                lb.sequentially(inst1.fetch, inst2.fetch)
        
    def test_sequential_fetch_as_kws(self):
        inst1 = LaggyInstrument(resource='fast', fetch_time=.002)
        inst2 = LaggyInstrument(resource='slow', fetch_time=.003)
        
        with inst1, inst2:
            self.assertEqual(inst1.state.connected, True)
            self.assertEqual(inst2.state.connected, True)               
            ret = lb.sequentially(**{inst1.settings.resource: inst1.fetch,
                                     inst2.settings.resource: inst2.fetch})
        self.assertIn(inst1.settings.resource, ret)
        self.assertIn(inst2.settings.resource, ret)
        self.assertEqual(ret[inst1.settings.resource],
                         inst1.settings.fetch_time)
        self.assertEqual(ret[inst2.settings.resource],
                         inst2.settings.fetch_time)
        
    def test_sequential_fetch_as_args(self):
        inst1 = LaggyInstrument(resource='fast', fetch_time=.002)
        inst2 = LaggyInstrument(resource='slow', fetch_time=.003)
        
        with inst1, inst2:
            self.assertEqual(inst1.state.connected, True)
            self.assertEqual(inst2.state.connected, True)               
            ret = lb.sequentially(inst1.fetch, inst2.fetch)
        self.assertIn('fetch_0', ret)
        self.assertIn('fetch_1', ret)
        self.assertEqual(ret['fetch_0'],
                         inst1.settings.fetch_time)
        self.assertEqual(ret['fetch_1'],
                         inst2.settings.fetch_time)
        

if __name__ == '__main__':
    lb.show_messages('info')
    unittest.main()