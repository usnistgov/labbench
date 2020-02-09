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


class Bench1(lb.Bench):
    dev1: LaggyInstrument
    dev2: LaggyInstrument

    def setup(self, param1):
        pass

    def arm(self):
        pass


class Bench2(lb.Bench):
    dev: LaggyInstrument

    def setup(self):
        return 'bench 2 - setup'
        return self.dev.dict()

    def acquire(self, *, param1):
        return 'bench 3 - acquire'

    def fetch(self, *, param2=7):
        return self.dev.fetch()


class Bench3(lb.Bench):
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
bench1 = Bench1(dev1=inst1, dev2=inst2)
bench2 = Bench2(dev=inst1)
bench3 = Bench3(dev=inst2)

run = lb.Multitask(
    setup=(bench1.setup & bench2.setup),  # executes these concurrently
    arm=(bench1.arm),
    acquire=(bench2.acquire, bench3.acquire),  # executes these sequentially
    fetch=(bench2.fetch & bench3.fetch),
    finish=db,  # db() marks the end of a database row
)
