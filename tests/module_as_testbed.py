import importlib
import sys
import time

if '..' not in sys.path:
    sys.path.insert(0, '..')
import labbench as lb
lb = importlib.reload(lb)

from emulate import EmulatedVISADevice


class LaggyInstrument(EmulatedVISADevice):
    """ A mock "instrument"
    with settings and states to
    demonstrate the process of setting
    up a measurement.
    """

    # Connection and driver settings
    delay: lb.Float(default=0, min=0, help='connection time (s)')
    fetch_time: lb.Float(default=0, min=0, help='fetch time (s)')
    fail_disconnect: lb.Bool(default=False, help='raise DivideByZero on disconnect?')

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
        return self.dev.fetch()


class Rack3(lb.Rack):
    dev: LaggyInstrument

    def acquire(self, *, param2=7, param3):
        pass

    def fetch(self, *, param4):
        self.dev.fetch()


db: lb.data.Aggregator = lb.SQLiteLogger(
    'data',  # Path to new directory that will contain containing all files
    overwrite=False,  # `True` --- delete existing master database; `False` --- append
    text_relational_min=1024,  # Minimum text string length that triggers relational storage
    force_relational=['host_log'],  # Data in these columns will always be relational
    dirname_fmt='{id} {host_time}',  # Format string that generates relational data (keyed on data column)
    nonscalar_file_type='csv',  # Default format of numerical data, when possible
    metadata_dirname='metadata',  # metadata will be stored in this subdirectory
    tar=True  # `True` to embed relational data folders within `data.tar`
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
    # finish=db.new_row,
)
