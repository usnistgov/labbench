# -*- coding: UTF-8 -*-

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
from emulate import EmulatedVISADevice
from contextlib import contextmanager
if '..' not in sys.path:
    sys.path.insert(0, '..')
import labbench as lb
import numpy as np
lb = importlib.reload(lb)


class LaggyInstrument(EmulatedVISADevice):
    """ A mock "instrument"
    with settings and states to
    demonstrate the process of setting
    up a measurement.
    """

    # Connection and driver settings
    delay: lb.Float\
        (default=0, min=0, help='connection time')
    fetch_time: lb.Float\
        (default=0, min=0, help='fetch time')
    fail_disconnect: lb.Bool\
        (default=False, help='True to raise DivideByZero on disconnect')

    def open(self):        
        self.perf = {}
        t0 = time.perf_counter()
        lb.sleep(self.settings.delay)
        self.perf['open'] = time.perf_counter() - t0

    def fetch(self):
        """ Return the argument after a 1s delay
        """
        import pandas as pd
        lb.console.info(f'{self}.fetch start')
        t0 = time.perf_counter()
        lb.sleep(self.settings.fetch_time)
        self.perf['fetch'] = time.perf_counter() - t0
        return pd.Series([1,2,3,4,5,6])
        # return self.settings.fetch_time
    
    def dict(self):
        return {self.settings.resource: self.settings.resource}

    def none(self):
        """ Return None
        """
        return None

    def close(self):
        if self.settings.fail_disconnect:
            1 // 0


class Rack1(lb.Rack):
    dev1: LaggyInstrument
    dev2: LaggyInstrument

    def setup(self, param1):
        pass

    def arm(self):
        pass


class Rack2(lb.Rack):
    dev: LaggyInstrument

    def setup(self):
        return 'rack 2 - setup'
        return self.dev.dict()

    def acquire(self, *, param1):
        return 'rack 3 - acquire'

    def fetch(self, *, param2=7):
        return dict(rack2_data=self.dev.fetch())


class Rack3(lb.Rack):
    dev: LaggyInstrument

    def acquire(self, *, param2=7, param3):
        pass

    def fetch(self, *, param4):
        return self.dev.fetch()


class MyRack(lb.Rack):
    db: lb.data.RelationalTableLogger = lb.SQLiteLogger(
        'data',                         # Path to new directory that will contain containing all files
        append=True,                    # `True` --- allow appends to an existing database; `False` --- append
        text_relational_min=1024,       # Minimum text string length that triggers relational storage
        force_relational=['host_log'],  # Data in these columns will always be relational
        dirname_fmt='{id} {host_time}', # Format string that generates relational data (keyed on data column)
        nonscalar_file_type='csv',      # Default format of numerical data, when possible
        metadata_dirname='metadata',    # metadata will be stored in this subdirectory
        tar=False                       # `True` to embed relational data folders within `data.tar`
    )

    # Devices
    inst1: LaggyInstrument = LaggyInstrument(resource='a', delay=.12)
    inst2: LaggyInstrument = LaggyInstrument(resource='b', delay=.06)

    # Test procedures
    rack1 = Rack1(dev1=inst1, dev2=inst2)
    rack2 = Rack2(dev=inst1)
    rack3 = Rack3(dev=inst2)

    run = lb.Coordinate(
        setup=(rack1.setup & rack2.setup),  # executes these 2 methods concurrently
        arm=(rack1.arm),
        acquire=(rack2.acquire, rack3.acquire),  # executes these 2 sequentially
        fetch=(rack2.fetch & rack3.fetch),
        finish=(db.new_row),
    )

if __name__ == '__main__':
    lb.show_messages('debug')
    lb.util._force_full_traceback(True)

    with lb.stopwatch('test connection'):
        # with lb.Rack._from_module('module_as_testbed')() as testbed:
        with MyRack() as testbed:
            testbed.inst2.settings.delay = 0.07
            testbed.inst1.settings.delay = 0.12

            testbed.run.from_csv('run.csv')

            # for i in range(3):
            #     # Run the experiment
            #     ret = testbed.run(rack1_param1=1, rack2_param1=2, rack3_param2=3,
            #                       rack3_param3=4, rack2_param2=5, rack3_param4=6)
            #
            #     testbed.db()

    df = lb.read(testbed.db.path/'master.db')
    df.to_csv(testbed.db.path/'master.csv')