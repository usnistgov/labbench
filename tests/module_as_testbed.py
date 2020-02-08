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
    delay: lb.Float \
        (default=0, min=0, help='connection time')
    fetch_time: lb.Float \
        (default=0, min=0, help='fetch time')
    fail_disconnect: lb.Bool \
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
        return self.dev.dict()

    def acquire(self, *, param1):
        return 'task 3 - acquire'

    def fetch(self, *, param2=7):
        return self.dev.fetch()


class Task3(lb.Task):
    dev: LaggyInstrument

    def acquire(self, *, param2=7, param3):
        pass

    def fetch(self, *, param4):
        self.dev.fetch()


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

# Devices
inst1 = LaggyInstrument(resource='a', delay=.12)
inst2 = LaggyInstrument(resource='b', delay=.06)

# Test procedures
task1 = Task1(dev1=inst1, dev2=inst2)
task2 = Task2(dev=inst1)
task3 = Task3(dev=inst2)

run = lb.Multitask(
    setup=(task1.setup & task2.setup),  # executes these concurrently
    arm=(task1.arm),
    acquire=(task2.acquire, task3.acquire),  # executes these sequentially
    fetch=(task2.fetch & task3.fetch),
    finish=db,  # db() marks the end of a database row
)
