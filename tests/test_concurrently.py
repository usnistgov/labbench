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

import threading
import pandas as pd
import numpy as np
import importlib
import sys
if '..' not in sys.path:
    sys.path.insert(0, '..')
import labbench as lb
lb = importlib.reload(lb)


class EmulatedInstrument(lb.EmulatedVISADevice):
    ''' A mock "instrument"
    with settings and states to
    demonstrate the process of setting
    up a measurement.
    '''
    class settings (lb.EmulatedVISADevice.settings):
        whatever = lb.Int(5, help='whatever')

    class state (lb.EmulatedVISADevice.state):
        initiate_continuous = lb.Bool(command='INIT:CONT')
        output_trigger = lb.Bool(command='OUTP:TRIG')
        sweep_aperture = lb.Float(command='SWE:APER', min=20e-6, max=200e-3,
                                  help='time (in s)')
        frequency = lb.Float(command='SENS:FREQ', min=10e6,
                             max=18e9, step=1e-3, help='center frequency (in Hz)')

    def connect(self):
        print(f'{self} connecting')
        lb.sleep(1)
        print(f'{self} ready')

    def trigger(self, howlong):
        ''' This would tell the instrument to start a measurement
        '''
        lb.sleep(howlong)

    def fetch_trace(self, N=1001):
        ''' Generate N points of junk data as a pandas series.
        '''
        values = np.random.uniform(-1, 1, N)
        index = np.linspace(0, self.state.sweep_aperture, N)
        series = pd.Series(values, index=index, name='Voltage (V)')
        series.index.name = 'Time (s)'
        lb.sleep(1)
        return series

    def disconnect(self):
        #        if self.state.connected:
        print(f'{self} disconnecting', threading.current_thread().getName())
#            self.logger.info(f'disconnecting')
        lb.sleep(1)
        print(f'{self} disconnected', threading.current_thread().getName())
        1 / 0


if __name__ == '__main__':
    lb.show_messages('info')

    inst1 = EmulatedInstrument(resource='inst1')
    inst2 = EmulatedInstrument(resource='inst2')
#    with lb.concurrently(potato=inst1, moose=inst2):
#        print('connected')
#        lb.concurrently(inst1.fetch_trace, inst2.fetch_trace)
# for i in range(10):
# print('waiting...')
# lb.sleep(1)
