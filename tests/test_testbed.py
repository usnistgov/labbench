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
    delay: lb.Float\
        (default=0, min=0, help='connection time')
    fetch_time: lb.Float\
        (default=0, min=0, help='fetch time')
    fail_disconnect: lb.Bool\
        (default=False, help='whether to raise DivideByZero on disconnect')

    def open(self):        
        self.perf = {}
        self.logger.info(f'{self} connect start')
        t0 = time.perf_counter()
        lb.sleep(self.settings.delay)
        self.perf['open'] = time.perf_counter() - t0
        self.logger.info(f'{self} connected')
        
    def fetch(self):
        ''' Return the argument after a 1s delay
        '''
        lb.logger.info(f'{self}.fetch start')
        t0 = time.perf_counter()
        lb.sleep(self.settings.fetch_time)
        lb.logger.info(f'{self}.fetch done')
        self.perf['fetch'] = time.perf_counter() - t0
        return self.settings.fetch_time
    
    def dict(self):
        return {self.settings.resource: self.settings.resource}

    def none(self):
        ''' Return None
        '''
        return None

    def close(self):
        self.logger.info(f'{self} disconnected')
        if self.settings.fail_disconnect:
            1 / 0

class MyTestbed(lb.Testbed):
    def make(self):
        self.inst1 = LaggyInstrument('a',delay=.18)
        self.inst2 = LaggyInstrument('b',delay=.06)

class MyTestbed2(lb.Testbed):
    db = lb.SQLiteLogger \
       ('data',                         # Path to new directory that will contain containing all files
        overwrite=False,                # `True` --- delete existing master database; `False` --- append
        text_relational_min=1024,       # Minimum text string length that triggers relational storage
        force_relational=['host_log'],  # Data in these columns will always be relational
        dirname_fmt='{id} {host_time}', # Format string that generates relational data (keyed on data column)
        nonscalar_file_type='csv',      # Default format of numerical data, when possible
        metadata_dirname='metadata',    # metadata will be stored in this subdirectory
        tar=False                       # `True` to embed relational data folders within `data.tar`
        )

    inst1 = LaggyInstrument(resource='a',
                            delay=.12)

    inst2 = LaggyInstrument(resource='b',
                            delay=.06)

    db.observe_settings([inst1, inst2])

if __name__ == '__main__':
    with lb.stopwatch():
        with MyTestbed2() as testbed:
            testbed.inst2.settings.delay = .07
            testbed.db()

    df = lb.read(testbed.db.path+'/master.db')
    df.to_csv(testbed.db.path+'/master.csv')