import pytest
import time
from contextlib import contextmanager
import labbench as lb
from labbench.testing.store_backend import StoreTestDevice
from labbench import paramattr as attr


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


class MyRack(lb.Rack):
    def make(self):
        self.inst1 = LaggyInstrument("a", delay=0.18)
        self.inst2 = LaggyInstrument("b", delay=0.06)


class MyRack2(lb.Rack):
    inst1 = LaggyInstrument("a", delay=0.12)
    inst2 = LaggyInstrument("b", delay=0.06)


# Acceptable error in delay time meaurement


@contextmanager
def assert_delay(expected_delay, delay_tol=0.08):
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
        assert elapsed == pytest.approx(expected_delay, abs=delay_tol)
        lb.logger.info(f"acceptable time elapsed {elapsed:0.3f}s".lstrip())


def test_concurrent_connect_delay():
    # global inst1, inst2
    inst1 = LaggyInstrument(resource="fast", delay=0.16)
    inst2 = LaggyInstrument(resource="slow", delay=0.36)

    expect_delay = max((inst1.delay, inst2.delay))
    with assert_delay(expect_delay):
        with lb.concurrently(inst1, inst2):
            assert inst1.isopen == True
            assert inst2.isopen == True
    assert inst1.isopen == False
    assert inst2.isopen == False


def test_concurrent_fetch_delay():
    inst1 = LaggyInstrument(resource="fast", fetch_time=0.26)
    inst2 = LaggyInstrument(resource="slow", fetch_time=0.36)

    expect_delay = max((inst1.fetch_time, inst2.fetch_time))
    with assert_delay(expect_delay):
        with inst1, inst2:
            assert inst1.isopen == True
            assert inst2.isopen == True
            lb.concurrently(fetch1=inst1.fetch, fetch2=inst2.fetch)


def test_concurrent_fetch_as_kws():
    inst1 = LaggyInstrument(resource="fast")
    inst2 = LaggyInstrument(resource="slow")

    with inst1, inst2:
        assert inst1.isopen == True
        assert inst2.isopen == True
        ret = lb.concurrently(**{inst1.resource: inst1.fetch, inst2.resource: inst2.fetch})
    assert inst1.resource in ret
    assert inst2.resource in ret
    assert ret[inst1.resource] == inst1.fetch_time
    assert ret[inst2.resource] == inst2.fetch_time


def test_concurrent_fetch_as_args():
    inst1 = LaggyInstrument(resource="fast", fetch_time=0.02)
    inst2 = LaggyInstrument(resource="slow", fetch_time=0.03)

    with inst1, inst2:
        assert inst1.isopen == True
        assert inst2.isopen == True
        ret = lb.concurrently(fetch_0=inst1.fetch, fetch_1=inst2.fetch)
    assert "fetch_0" in ret
    assert "fetch_1" in ret
    assert ret["fetch_0"] == inst1.fetch_time
    assert ret["fetch_1"] == inst2.fetch_time


def test_sequential_connect_delay():
    inst1 = LaggyInstrument(resource="fast", delay=0.16)
    inst2 = LaggyInstrument(resource="slow", delay=0.26)

    expect_delay = inst1.delay + inst2.delay
    with assert_delay(expect_delay):
        with lb.sequentially(inst1, inst2):
            assert inst1.isopen == True
            assert inst2.isopen == True
    assert inst1.isopen == False
    assert inst2.isopen == False


def test_sequential_fetch_delay():
    inst1 = LaggyInstrument(resource="fast", fetch_time=0.26)
    inst2 = LaggyInstrument(resource="slow", fetch_time=0.36)

    expect_delay = inst1.fetch_time + inst2.fetch_time
    with assert_delay(expect_delay):
        with inst1, inst2:
            assert inst1.isopen == True
            assert inst2.isopen == True
            lb.sequentially(fetch1=inst1.fetch, fetch2=inst2.fetch)


def test_sequential_fetch_as_kws():
    inst1 = LaggyInstrument(resource="fast", fetch_time=0.002)
    inst2 = LaggyInstrument(resource="slow", fetch_time=0.003)

    with inst1, inst2:
        assert inst1.isopen == True
        assert inst2.isopen == True
        ret = lb.sequentially(**{inst1.resource: inst1.fetch, inst2.resource: inst2.fetch})
    assert inst1.resource in ret
    assert inst2.resource in ret
    assert ret[inst1.resource] == inst1.fetch_time
    assert ret[inst2.resource] == inst2.fetch_time


def test_sequential_fetch_as_args():
    inst1 = LaggyInstrument(resource="fast", fetch_time=0.002)
    inst2 = LaggyInstrument(resource="slow", fetch_time=0.003)

    with inst1, inst2:
        assert inst1.isopen == True
        assert inst2.isopen == True
        ret = lb.sequentially(fetch_0=inst1.fetch, fetch_1=inst2.fetch)
    assert "fetch_0" in ret
    assert "fetch_1" in ret
    assert ret["fetch_0"] == inst1.fetch_time
    assert ret["fetch_1"] == inst2.fetch_time


def test_nested_connect_delay():
    inst1 = LaggyInstrument(resource="a", delay=0.16)
    inst2 = LaggyInstrument(resource="b", delay=0.26)
    inst3 = LaggyInstrument(resource="c", delay=0.37)

    expect_delay = inst1.delay + max((inst2.delay, inst3.delay))

    with assert_delay(expect_delay):
        with lb.sequentially(inst1, lb.concurrently(inst2, inst3)):
            assert inst1.isopen == True
            assert inst2.isopen == True
            assert inst3.isopen == True
    assert inst1.isopen == False
    assert inst2.isopen == False
    assert inst3.isopen == False


def test_nested_fetch_delay():
    inst1 = LaggyInstrument(resource="a", fetch_time=0.16)
    inst2 = LaggyInstrument(resource="b", fetch_time=0.26)
    inst3 = LaggyInstrument(resource="c", fetch_time=0.37)

    expect_delay = inst1.fetch_time + max((inst2.fetch_time, inst3.fetch_time))

    with assert_delay(expect_delay):
        with inst1, inst2, inst3:
            ret = lb.sequentially(
                inst1.fetch, lb.concurrently(sub_1=inst2.fetch, sub_2=inst3.fetch)
            )


def test_sequential_nones():
    inst1 = LaggyInstrument(resource="a", fetch_time=0.16)
    inst2 = LaggyInstrument(resource="b", fetch_time=0.26)

    with inst1, inst2:
        ret = lb.sequentially(data1=inst1.none, data2=inst2.none)
    assert ret == {}

    with inst1, inst2:
        ret = lb.sequentially(data1=inst1.none, data2=inst2.none, nones=True)
    assert "data1" in ret
    assert "data2" in ret
    assert ret["data1"] == None
    assert ret["data2"] == None


def test_concurrent_nones():
    inst1 = LaggyInstrument(resource="a", fetch_time=0.16)
    inst2 = LaggyInstrument(resource="b", fetch_time=0.26)

    with inst1, inst2:
        ret = lb.concurrently(data1=inst1.none, data2=inst2.none, nones=False)
    assert ret == {}

    with inst1, inst2:
        ret = lb.concurrently(data1=inst1.none, data2=inst2.none, nones=True)
    assert "data1" in ret
    assert "data2" in ret
    assert ret["data1"] == None
    assert ret["data2"] == None


def test_testbed_instantiation():
    with assert_delay(0):
        testbed = MyRack2()

    expected_delay = max(testbed.inst1.delay, testbed.inst2.delay)

    assert testbed.inst1.isopen == False
    assert testbed.inst2.isopen == False

    with assert_delay(expected_delay):
        with testbed:
            assert testbed.inst1.isopen == True
            assert testbed.inst2.isopen == True

    assert testbed.inst1.isopen == False
    assert testbed.inst2.isopen == False


def test_flatten():
    inst1 = LaggyInstrument(resource="a")
    inst2 = LaggyInstrument(resource="b")

    with inst1, inst2:
        ret = lb.concurrently(d1=inst1.dict, d2=inst2.dict, flatten=True)
    assert "a" in ret
    assert "b" in ret
    assert ret["a"] == "a"
    assert ret["b"] == "b"

    with inst1, inst2:
        ret = lb.sequentially(d1=inst1.dict, d2=inst2.dict, flatten=True)
    assert "a" in ret
    assert "b" in ret
    assert ret["a"] == "a"
    assert ret["b"] == "b"

    with inst1, inst2:
        ret = lb.concurrently(d1=inst1.dict, d2=inst2.dict, flatten=False)
    assert "d1" in ret
    assert "d2" in ret
    assert ret["d1"] == dict(a="a")
    assert ret["d2"] == dict(b="b")

    with inst1, inst2:
        ret = lb.sequentially(d1=inst1.dict, d2=inst2.dict, flatten=False)
    assert "d1" in ret
    assert "d2" in ret
    assert ret["d1"] == dict(a="a")
    assert ret["d2"] == dict(b="b")
