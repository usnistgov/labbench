import importlib
import sys
import time

import labbench as lb
from labbench import paramattr as attr
from test_sequencing import LaggyInstrument

lb = importlib.reload(lb)


class Rack1(lb.Rack):
    dev1: lb.Device = LaggyInstrument()
    dev2: lb.Device = LaggyInstrument()

    def setup(self, param1):
        pass

    def arm(self):
        pass


class Rack2(lb.Rack):
    dev: lb.Device = LaggyInstrument()

    def setup(self):
        return "rack 2 - setup"
        return self.dev.dict()

    def acquire(self, *, param1):
        return "rack 3 - acquire"

    def fetch(self, *, param2=7):
        return self.dev.fetch()


class Rack3(lb.Rack):
    dev: lb.Device = LaggyInstrument()

    def acquire(self, *, param2=7, param3):
        pass

    def fetch(self, *, param4):
        self.dev.fetch()


db: lb._data.TabularLoggerBase = lb.SQLiteLogger(
    "data",  # Path to new directory that will contain containing all files
    append=True,  # `True` --- allow appends to an existing database; `False` --- append
    text_relational_min=1024,  # Minimum text string length that triggers relational storage
    force_relational=["host_log"],  # Data in these columns will always be relational
    nonscalar_file_type="csv",  # Default format of numerical data, when possible
    metadata_dirname="metadata",  # metadata will be stored in this subdirectory
    tar=False,  # `True` to embed relational data folders within `data.tar`
)

# Devices
inst1: LaggyInstrument = LaggyInstrument(resource="a", delay=0.12)
inst2: LaggyInstrument = LaggyInstrument(resource="b", delay=0.06)

# Test procedures
rack1 = Rack1(dev1=inst1, dev2=inst2)
rack2 = Rack2(dev=inst1)
rack3 = Rack3(dev=inst2)

run = lb.Sequence(
    (rack1.setup, rack2.setup),  # executes these 2 methods concurrently
    (rack1.arm),
    rack2.acquire,
    rack3.acquire,  # executes these 2 sequentially
    (rack2.fetch, rack3.fetch),
    (db.new_row),
)
