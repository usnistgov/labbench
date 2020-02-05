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

import typing
if typing.TYPE_CHECKING:
    from dataclasses import dataclass
else:
    dataclass = lambda x: x


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

    @lb.method
    def fetch(self):
        """ Return the argument after a 1s delay
        """
        lb.logger.info(f'{self}.fetch start')
        t0 = time.perf_counter()
        lb.sleep(self.settings.fetch_time)
        self.perf['fetch'] = time.perf_counter() - t0
        return self.settings.fetch_time
    
    def dict(self):
        return {self.settings.resource: self.settings.resource}

    def none(self):
        """ Return None
        """
        return None

    def close(self):
        if self.settings.fail_disconnect:
            1 / 0


class Task1(lb.Task):
    dev1: LaggyInstrument
    dev2: LaggyInstrument

    def setup(self, param1):
        pass

    def arm(self):
        pass


class Task2(lb.Task):
    dev: LaggyInstrument

    def setup(self):
        return 'task 2 - setup'
        pass

    def acquire(self, *, param1):
        return 'task 3 - acquire'
        pass

    def fetch(self, *, param2=7):
        return {'data 1': 4, 'data 2': 5}


class Task3(lb.Task):
    dev: LaggyInstrument
    db: lb.SQLiteLogger

    def acquire(self, *, param2=7, param3):
        pass

    def fetch(self, *, param4):
        pass

    def finish(self):
        self.db()


class MyTestbed(lb.Testbed):
    db = lb.SQLiteLogger(
        'data',                         # Path to new directory that will contain containing all files
        overwrite=False,                # `True` --- delete existing master database; `False` --- append
        text_relational_min=1024,       # Minimum text string length that triggers relational storage
        force_relational=['host_log'],  # Data in these columns will always be relational
        dirname_fmt='{id} {host_time}', # Format string that generates relational data (keyed on data column)
        nonscalar_file_type='csv',      # Default format of numerical data, when possible
        metadata_dirname='metadata',    # metadata will be stored in this subdirectory
        tar=False                       # `True` to embed relational data folders within `data.tar`
    )

    inst1 = LaggyInstrument(
        resource='a',
        delay=.12
    )

    inst2 = LaggyInstrument(
        resource='b',
        delay=.06
    )

    # Test procedures
    task1 = Task1(
        dev1=inst1,
        dev2=inst2
    )

    task2 = Task2(
        dev=inst1
    )

    task3 = Task3(
        dev=inst2,
        db=db
    )

    run = lb.Multitask(
        (task1.setup & task2.setup),  # executes these 2 methods concurrently
        (task1.arm),
        (task2.acquire, task3.acquire),  # executes these 2 sequentially
        (task2.fetch & task3.fetch),
        task3.finish,  # last, call db() to mark the end of a database row
    )


if __name__ == '__main__':
    lb.show_messages('debug')

    with lb.stopwatch('test connection'):
        with MyTestbed() as testbed:
            testbed.inst2.settings.delay = 0.07
            testbed.inst1.settings.delay = 0.12
            testbed.run.from_csv('run.csv')
            # for i in range(3):
            #     # Run the experiment
            #     ret = testbed.run(task1_param1=1, task2_param1=2, task3_param2=3,
            #                       task3_param3=4, task2_param2=5, task3_param4=6)
            #
            #     testbed.db()

    df = lb.read(testbed.db.path+'/master.db')
    df.to_csv(testbed.db.path+'/master.csv')