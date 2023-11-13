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
import labbench as lb
from labbench import paramattr as param
import numpy as np

lb = importlib.reload(lb)
from emulate import EmulatedVISADevice

lb.util.show_messages("debug")

lb._force_full_traceback(True)


class LaggyInstrument(EmulatedVISADevice):
    """A mock "instrument" to measure time response in (a)sync operations"""

    delay = param.value.float(0, min=0, help="connection time")
    fetch_time = param.value.float(0, min=0, help="fetch time")
    fail_disconnect = param.value.bool(False, help="whether to raise DivideByZero on disconnect")

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


class MyRack(lb.Rack):
    def make(self):
        self.inst1 = LaggyInstrument("a", delay=0.18)
        self.inst2 = LaggyInstrument("b", delay=0.06)


class MyRack2(lb.Rack):
    inst1 = LaggyInstrument("a", delay=0.12)
    inst2 = LaggyInstrument("b", delay=0.06)


class TestConcurrency(unittest.TestCase):
    # Acceptable error in delay time meaurement
    delay_tol = 0.08

    @contextmanager
    def assert_delay(self, expected_delay):
        """Time a block of code using a with statement like this:

        >>> with stopwatch('sleep statement'):
        >>>     time.sleep(2)
        sleep statement time elapsed 1.999s.

        :param desc: text for display that describes the event being timed
        :type desc = str
        :return: context manager
        """
        t0 = time.perf_counter()
        try:
            yield
        except:
            raise
        else:
            elapsed = time.perf_counter() - t0
            self.assertAlmostEqual(elapsed, expected_delay, delta=self.delay_tol)
            lb.logger.info(f"acceptable time elapsed {elapsed:0.3f}s".lstrip())

    def test_concurrent_connect_delay(self):
        # global inst1, inst2
        inst1 = LaggyInstrument(resource="fast", delay=0.16)
        inst2 = LaggyInstrument(resource="slow", delay=0.36)

        expect_delay = max((inst1.delay, inst2.delay))
        with self.assert_delay(expect_delay):
            with lb.concurrently(inst1, inst2):
                self.assertEqual(inst1.isopen, True)
                self.assertEqual(inst2.isopen, True)
        self.assertEqual(inst1.isopen, False)
        self.assertEqual(inst2.isopen, False)

    def test_concurrent_fetch_delay(self):
        inst1 = LaggyInstrument(resource="fast", fetch_time=0.26)
        inst2 = LaggyInstrument(resource="slow", fetch_time=0.36)

        expect_delay = max((inst1.fetch_time, inst2.fetch_time))
        with self.assert_delay(expect_delay):
            with inst1, inst2:
                self.assertEqual(inst1.isopen, True)
                self.assertEqual(inst2.isopen, True)
                lb.concurrently(fetch1=inst1.fetch, fetch2=inst2.fetch)

    def test_concurrent_fetch_as_kws(self):
        inst1 = LaggyInstrument(resource="fast")
        inst2 = LaggyInstrument(resource="slow")

        with inst1, inst2:
            self.assertEqual(inst1.isopen, True)
            self.assertEqual(inst2.isopen, True)
            ret = lb.concurrently(**{inst1.resource: inst1.fetch, inst2.resource: inst2.fetch})
        self.assertIn(inst1.resource, ret)
        self.assertIn(inst2.resource, ret)
        self.assertEqual(ret[inst1.resource], inst1.fetch_time)
        self.assertEqual(ret[inst2.resource], inst2.fetch_time)

    def test_concurrent_fetch_as_args(self):
        inst1 = LaggyInstrument(resource="fast", fetch_time=0.02)
        inst2 = LaggyInstrument(resource="slow", fetch_time=0.03)

        with inst1, inst2:
            self.assertEqual(inst1.isopen, True)
            self.assertEqual(inst2.isopen, True)
            ret = lb.concurrently(fetch_0=inst1.fetch, fetch_1=inst2.fetch)
        self.assertIn("fetch_0", ret)
        self.assertIn("fetch_1", ret)
        self.assertEqual(ret["fetch_0"], inst1.fetch_time)
        self.assertEqual(ret["fetch_1"], inst2.fetch_time)

    def test_sequential_connect_delay(self):
        inst1 = LaggyInstrument(resource="fast", delay=0.16)
        inst2 = LaggyInstrument(resource="slow", delay=0.26)

        expect_delay = inst1.delay + inst2.delay
        with self.assert_delay(expect_delay):
            with lb.sequentially(inst1, inst2):
                self.assertEqual(inst1.isopen, True)
                self.assertEqual(inst2.isopen, True)
        self.assertEqual(inst1.isopen, False)
        self.assertEqual(inst2.isopen, False)

    def test_sequential_fetch_delay(self):
        inst1 = LaggyInstrument(resource="fast", fetch_time=0.26)
        inst2 = LaggyInstrument(resource="slow", fetch_time=0.36)

        expect_delay = inst1.fetch_time + inst2.fetch_time
        with self.assert_delay(expect_delay):
            with inst1, inst2:
                self.assertEqual(inst1.isopen, True)
                self.assertEqual(inst2.isopen, True)
                lb.sequentially(fetch1=inst1.fetch, fetch2=inst2.fetch)

    def test_sequential_fetch_as_kws(self):
        inst1 = LaggyInstrument(resource="fast", fetch_time=0.002)
        inst2 = LaggyInstrument(resource="slow", fetch_time=0.003)

        with inst1, inst2:
            self.assertEqual(inst1.isopen, True)
            self.assertEqual(inst2.isopen, True)
            ret = lb.sequentially(**{inst1.resource: inst1.fetch, inst2.resource: inst2.fetch})
        self.assertIn(inst1.resource, ret)
        self.assertIn(inst2.resource, ret)
        self.assertEqual(ret[inst1.resource], inst1.fetch_time)
        self.assertEqual(ret[inst2.resource], inst2.fetch_time)

    def test_sequential_fetch_as_args(self):
        inst1 = LaggyInstrument(resource="fast", fetch_time=0.002)
        inst2 = LaggyInstrument(resource="slow", fetch_time=0.003)

        with inst1, inst2:
            self.assertEqual(inst1.isopen, True)
            self.assertEqual(inst2.isopen, True)
            ret = lb.sequentially(fetch_0=inst1.fetch, fetch_1=inst2.fetch)
        self.assertIn("fetch_0", ret)
        self.assertIn("fetch_1", ret)
        self.assertEqual(ret["fetch_0"], inst1.fetch_time)
        self.assertEqual(ret["fetch_1"], inst2.fetch_time)

    def test_nested_connect_delay(self):
        inst1 = LaggyInstrument(resource="a", delay=0.16)
        inst2 = LaggyInstrument(resource="b", delay=0.26)
        inst3 = LaggyInstrument(resource="c", delay=0.37)

        expect_delay = inst1.delay + max((inst2.delay, inst3.delay))

        with self.assert_delay(expect_delay):
            with lb.sequentially(inst1, lb.concurrently(inst2, inst3)):
                self.assertEqual(inst1.isopen, True)
                self.assertEqual(inst2.isopen, True)
                self.assertEqual(inst3.isopen, True)
        self.assertEqual(inst1.isopen, False)
        self.assertEqual(inst2.isopen, False)
        self.assertEqual(inst3.isopen, False)

    def test_nested_fetch_delay(self):
        inst1 = LaggyInstrument(resource="a", fetch_time=0.16)
        inst2 = LaggyInstrument(resource="b", fetch_time=0.26)
        inst3 = LaggyInstrument(resource="c", fetch_time=0.37)

        expect_delay = inst1.fetch_time + max((inst2.fetch_time, inst3.fetch_time))

        with self.assert_delay(expect_delay):
            with inst1, inst2, inst3:
                ret = lb.sequentially(
                    inst1.fetch, lb.concurrently(sub_1=inst2.fetch, sub_2=inst3.fetch)
                )

    def test_sequential_nones(self):
        inst1 = LaggyInstrument(resource="a", fetch_time=0.16)
        inst2 = LaggyInstrument(resource="b", fetch_time=0.26)

        with inst1, inst2:
            ret = lb.sequentially(data1=inst1.none, data2=inst2.none)
        self.assertEqual(ret, {})

        with inst1, inst2:
            ret = lb.sequentially(data1=inst1.none, data2=inst2.none, nones=True)
        self.assertIn("data1", ret)
        self.assertIn("data2", ret)
        self.assertEqual(ret["data1"], None)
        self.assertEqual(ret["data2"], None)

    def test_concurrent_nones(self):
        inst1 = LaggyInstrument(resource="a", fetch_time=0.16)
        inst2 = LaggyInstrument(resource="b", fetch_time=0.26)

        with inst1, inst2:
            ret = lb.concurrently(data1=inst1.none, data2=inst2.none, nones=False)
        self.assertEqual(ret, {})

        with inst1, inst2:
            ret = lb.concurrently(data1=inst1.none, data2=inst2.none, nones=True)
        self.assertIn("data1", ret)
        self.assertIn("data2", ret)
        self.assertEqual(ret["data1"], None)
        self.assertEqual(ret["data2"], None)

    def test_testbed_instantiation(self):
        with self.assert_delay(0):
            testbed = MyRack2()

        expected_delay = max(testbed.inst1.delay, testbed.inst2.delay)

        self.assertEqual(testbed.inst1.isopen, False)
        self.assertEqual(testbed.inst2.isopen, False)

        with self.assert_delay(expected_delay):
            with testbed:
                self.assertEqual(testbed.inst1.isopen, True)
                self.assertEqual(testbed.inst2.isopen, True)

        self.assertEqual(testbed.inst1.isopen, False)
        self.assertEqual(testbed.inst2.isopen, False)

    def test_flatten(self):
        inst1 = LaggyInstrument(resource="a")
        inst2 = LaggyInstrument(resource="b")

        with inst1, inst2:
            ret = lb.concurrently(d1=inst1.dict, d2=inst2.dict, flatten=True)
        self.assertIn("a", ret)
        self.assertIn("b", ret)
        self.assertEqual(ret["a"], "a")
        self.assertEqual(ret["b"], "b")

        with inst1, inst2:
            ret = lb.sequentially(d1=inst1.dict, d2=inst2.dict, flatten=True)
        self.assertIn("a", ret)
        self.assertIn("b", ret)
        self.assertEqual(ret["a"], "a")
        self.assertEqual(ret["b"], "b")

        with inst1, inst2:
            ret = lb.concurrently(d1=inst1.dict, d2=inst2.dict, flatten=False)
        self.assertIn("d1", ret)
        self.assertIn("d2", ret)
        self.assertEqual(ret["d1"], dict(a="a"))
        self.assertEqual(ret["d2"], dict(b="b"))

        with inst1, inst2:
            ret = lb.sequentially(d1=inst1.dict, d2=inst2.dict, flatten=False)
        self.assertIn("d1", ret)
        self.assertIn("d2", ret)
        self.assertEqual(ret["d1"], dict(a="a"))
        self.assertEqual(ret["d2"], dict(b="b"))


if __name__ == "__main__":
    lb.show_messages("warning")
    unittest.main()
