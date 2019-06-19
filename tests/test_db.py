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
import pandas as pd
import numpy as np
import labbench as lb
import importlib

import sys
if '..' not in sys.path:
    sys.path.insert(0, '..')


lb = importlib.reload(lb)


int_start = 3
int_stop = 10


class EmulatedInstrument(lb.EmulatedVISADevice):
    ''' This "instrument" makes mock data and instrument states to
        demonstrate we can show the process of setting
        up a measurement.
    '''
    class settings (lb.EmulatedVISADevice.settings):
        whatever = lb.Int(5)

    class state (lb.EmulatedVISADevice.state):
        initiate_continuous = lb.Bool(command='INIT:CONT')
        output_trigger = lb.Bool(command='OUTP:TRIG')
        sweep_aperture = lb.Float(
            command='SWE:APER', min=20e-6, max=200e-3, help='time (in s)')
        frequency = lb.Float(command='SENS:FREQ', min=10e6,
                             max=18e9, step=1e-3, help='center frequency (in Hz)')
        atten = lb.Float(command='POW', min=0, max=100, step=0.5)

    def trigger(self):
        ''' This would tell the instrument to start a measurement
        '''
        pass

    def fetch_trace(self, N=1001):
        ''' Generate N points of junk data as a pandas series.
        '''
        values = np.random.uniform(-1, 1, N)
        index = np.linspace(0, self.state.sweep_aperture, N)
        series = pd.Series(values, index=index, name='Voltage (V)')
        series.index.name = 'Time (s)'
        return series


class TestWrappers(unittest.TestCase):
    def test_state_wrapper_type(self):
        with EmulatedInstrument() as m,\
                lb.StatesToSQLite(path) as db:
            self.assertEqual(m.state.param, int_start)
            m.state.param = int_stop
            self.assertEqual(m.state.param, int_stop)

    def test_trait_wrapper_type(self):
        with MockTraitWrapper() as m:
            self.assertEqual(m.state.param, int_start)
            m.state.param = int_stop
            self.assertEqual(m.state.param, int_stop)


if __name__ == '__main__':

    path = 'test'

    lb.show_messages('debug')

    with EmulatedInstrument() as inst,\
            lb.StatesToSQLite(path, tar=True) as db:

        db.observe_states(inst, changes=True, always='sweep_aperture')
        db.observe_settings(inst, changes=True)

        for inst.state.frequency in np.linspace(10e6, 100e6, 21):
            inst.settings.whatever = inst.state.frequency
            trace = inst.fetch_trace()
            db.append(power_GW='1.21', trace=trace, potato=7)
        db.write()

#    #%%
#    df = lb.read(path+'/master.db')
# df = pd.read_csv(path)
#    print(df.tail(11))
#
# class TestWrappers(unittest.TestCase):
#    def test_state_wrapper_type(self):
#        with MockStateWrapper() as m:
#            self.assertEqual(m.state.param,int_start)
#            m.state.param = int_stop
#            self.assertEqual(m.state.param,int_stop)
#
#
#    def test_trait_wrapper_type(self):
#        with MockTraitWrapper() as m:
#            self.assertEqual(m.state.param,int_start)
#            m.state.param = int_stop
#            self.assertEqual(m.state.param,int_stop)
#
# if __name__ == '__main__':
#    unittest.main()
