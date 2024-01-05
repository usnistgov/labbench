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

import time
from labbench.testing.store_backend import StoreTestDevice

import labbench as lb
from labbench import paramattr as attr
import numpy as np
import pytest


class LaggyInstrument(StoreTestDevice):
    """A mock "instrument" to measure time response in (a)sync operations"""

    delay: float = attr.value.float(default=0, min=0, help="connection time")
    fetch_time: float = attr.value.float(default=0, min=0, help="fetch time")
    fail_disconnect = attr.value.bool(
        default=False, help="whether to raise DivideByZero on disconnect"
    )

    def open(self):
        self.perf = {}
        self._logger.info(f"{self} connect start")
        t0 = time.perf_counter()
        lb.sleep(self.delay)
        self.perf["open"] = time.perf_counter() - t0
        self._logger.info(f"{self} connected")

    def fetch(self):
        """Return the argument after a 1s delay"""
        lb.logger.info(f"{self}.fetch start")
        t0 = time.perf_counter()
        lb.sleep(self.fetch_time)
        lb.logger.info(f"{self}.fetch done")
        self.perf["fetch"] = time.perf_counter() - t0
        return self.fetch_time

    def dict(self):
        return {self.resource: self.resource}

    def none(self):
        """Return None"""
        return None

    def close(self):
        self._logger.info(f"{self} disconnected")
        if self.fail_disconnect:
            1 / 0


class Rack1(lb.Rack):
    dev1: LaggyInstrument = LaggyInstrument()
    dev2: LaggyInstrument = LaggyInstrument()

    def setup(self, param1: float):
        pass

    def arm(self):
        self.dev1.variable_setting = self.dev1.variable_setting + 2

    def open(self):
        time.sleep(0.25)


class Rack2(lb.Rack):
    dev: LaggyInstrument = LaggyInstrument()

    def setup(self):
        return "rack 2 - setup"
        return self.dev.dict()

    def acquire(self, *, param1):
        return "rack 3 - acquire"

    def fetch(self, *, param2: int = 7):
        return self.dev.fetch()

    def open(self):
        time.sleep(0.25)


class Rack3(lb.Rack):
    # this is unset (no =), so it _must_ be passed as an argument to instantiate, i.e.,
    #
    # >>> Rack3(dev=MyDevice)
    dev: LaggyInstrument

    # notice this operation requires param2 and param3
    def acquire(self, *, param3, param2=7):
        pass

    def fetch(self, *, param4):
        return self.dev.fetch()

    def open(self):
        time.sleep(0.25)


class MyRack(lb.Rack):
    db = lb.CSVLogger(
        path=time.strftime(
            f"test db/test-rack %Y-%m-%d_%Hh%Mm%Ss"
        ),  # Path to new directory that will contain containing all files
        append=True,  # `True` --- allow appends to an existing database; `False` --- append
        text_relational_min=1024,  # Minimum text string length that triggers relational storage
        force_relational=["host_log"],  # Data in these columns will always be relational
        nonscalar_file_type="csv",  # Default format of numerical data, when possible
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
        (rack1.setup, rack2.setup),  # 2 methods run concurrently
        rack1.arm,
        rack2.acquire,
        rack3.acquire,
        (rack2.fetch, rack3.fetch),  # 2 also run concurrently
        db.new_row,
    )


@pytest.fixture
def db_path():
    yield f"test db/{np.random.bytes(8).hex()}"


def test_context_open():
    rack = MyRack()

    assert not rack.inst1.isopen
    assert not rack.inst2.isopen

    with MyRack():
        assert rack.inst1.isopen
        assert rack.inst2.isopen

    assert not rack.inst1.isopen
    assert not rack.inst2.isopen


def test_call_open():
    rack = MyRack()

    assert not rack.inst1.isopen
    assert not rack.inst2.isopen

    rack.open()
    try:
        assert rack.inst1.isopen
        assert rack.inst2.isopen
    finally:
        rack.close()

    assert not rack.inst1.isopen
    assert not rack.inst2.isopen


# if __name__ == "__main__":
# rack = MyRack()
# rack.open()

# # Testbed = lb.Rack.take_module('module_as_testbed')
# Testbed = MyRack

# lst = CommentedSeq(['a', 'b'])
# lst.yaml_add_eol_comment("foo", 0, 0)
# lst.yaml_add_eol_comment("bar\n\n", 1)
# data["list_of_elements_side_comment"] = lst
# data.yaml_set_comment_before_after_key("list_of_elements_side_comment", "\n")

# lst = CS(['a', 'b'])
# lst.yaml_set_comment_before_after_key(0, "comment 1", 2)
# lst.yaml_set_comment_before_after_key(1, "comment 2", 2)
# data["list_of_elements_top_comment"] = lst

# Testbed.config.make_templates()

# # Testbed.config._rack_defaults(Testbed)

# with lb.stopwatch('test connection'):
#     with Testbed() as testbed:
#         # with MyRack() as testbed:
#         testbed.inst2.delay = 0.07
#         testbed.inst1.delay = 0.12

#         testbed.run.iterate_from_csv('setup/MyRack.run.csv')

#         # for i in range(3):
#         #     # Run the experiment
#         #     ret = testbed.run(rack1_param1=1, rack2_param1=2, rack3_param2=3,
#         #                       rack3_param3=4, rack2_param2=5, rack3_param4=6)
#         #
#         #     testbed.db()

# df = lb.read(testbed.db.path/'master.db')
# df.to_csv(testbed.db.path/'master.csv')

# config_root = Path('test-config')
# config_root.mkdir(parents=True, exist_ok=True)

# # default devices
# defaults = {
#     dev_name: {k:getattr(dev, k) for k in dev._value_attrs}
#     for dev_name, dev in MyRack._devices.items()
# }
# with open(config_root/'devices.yaml', 'w') as f:
#     yaml.dump(defaults, f)

# defaults, annots, methods, names = MyRack.config.parameters(MyRack)

# with open(config_root/'rack arguments.yaml', 'w') as f:
#     f.write('## Comment or remove lines to add as columns in sequence tables\n\n')
#     for k, default in defaults.items():
#         if default is lb._rack.EMPTY:
#             s = f'# {k}: \n'
#             f.write(s)
#         else:
#             s = yaml.dump({k: default}, f)
#         if annots[k] is not lb._rack.EMPTY:
#             before, *after = s.split(b'\n', 1)
#             s = b'\n'.join([before+f" # {annots[k].__qualname__}"] + after)
