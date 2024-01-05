import labbench as lb
from labbench import paramattr as attr
from labbench.testing import store_backend
import pandas as pd
import numpy as np
import shutil
import pytest


@attr.register_key_argument(attr.kwarg.int("registered_channel", min=1, max=4))
@store_backend.key_store_adapter(defaults={"SWE:APER": "20e-6"})
class StoreDevice(store_backend.StoreTestDevice):
    """This "instrument" makes mock data and instrument property traits to
    demonstrate we can show the process of value trait
    up a measurement.
    """

    # values
    trace_index = attr.value.int(0)

    # properties
    initiate_continuous = attr.property.bool(key="INIT:CONT")
    output_trigger = attr.property.bool(key="OUTP:TRIG")
    sweep_aperture = attr.property.float(key="SWE:APER", min=20e-6, max=200e-3, help="time (in s)")
    frequency = attr.property.float(
        key="SENS:FREQ", min=10e6, max=18e9, help="center frequency (in Hz)"
    )
    atten = attr.property.float(key="POW", min=0, max=100, step=0.5)

    str_keyed_with_arg = attr.method.str(key="str_with_arg_ch_{registered_channel}")
    str_keyed_allow_none = attr.method.str(
        key="str_with_arg_ch_{registered_channel}", allow_none=True
    )

    @attr.kwarg.int(name="decorated_channel", min=1, max=4)
    @attr.method.str()
    @attr.kwarg.float(name="bandwidth", min=10e3, max=100e6)
    def str_decorated_with_arg(self, new_value=lb.Undefined, *, decorated_channel, bandwidth):
        key = self.backend.get_backend_key(
            self,
            type(self).str_decorated_with_arg,
            {"decorated_channel": decorated_channel, "bandwidth": bandwidth},
        )

        if new_value is not lb.Undefined:
            self.backend.set(key, new_value)
        else:
            return self.backend.get(key, None)

    def trigger(self):
        """This would tell the instrument to start a measurement"""
        pass

    def method(self):
        print("method!")

    def fetch_trace(self, N=101):
        """Generate N points of junk data as a pandas series."""
        self.trace_index = self.trace_index + 1

        series = pd.Series(
            self.trace_index * np.ones(N),
            index=self.sweep_aperture * np.arange(N),
            name="Voltage (V)",
        )

        series.index.name = "Time (s)"
        return series


FREQUENCIES = 10e6, 100e6, 1e9, 10e9
EXTRA_VALUES = dict(power=1.21e9, potato=7)


class SimpleRack(lb.Rack):
    """a device paired with a logger"""

    inst: StoreDevice = StoreDevice()
    db: lb._data.TabularLoggerBase

    FREQUENCIES = 10e6, 100e6, 1e9, 10e9
    EXTRA_VALUES = dict(power=1.21e9, potato=7)

    def simple_loop(self):
        self.db.observe_paramattr(self.inst, changes=True, always="sweep_aperture")

        for self.inst.frequency in self.FREQUENCIES:
            self.inst.index = self.inst.frequency
            self.inst.fetch_trace()
            self.db.new_row(**self.EXTRA_VALUES)

    def simple_loop_expected_columns(self):
        return tuple(self.EXTRA_VALUES.keys()) + (
            "inst_trace_index",
            "inst_frequency",
            "inst_sweep_aperture",
            "db_host_time",
            "db_host_log",
        )


#
# Fixturing
#
@pytest.fixture
def csv_path():
    path = f"test db/{np.random.bytes(8).hex()}.csv"
    yield path
    shutil.rmtree(path)


@pytest.fixture
def hdf_path():
    path = f"test db/{np.random.bytes(8).hex()}.hdf"
    yield path
    shutil.rmtree(path)


@pytest.fixture
def sqlite_path():
    path = f"test db/{np.random.bytes(8).hex()}.sqlite"
    yield path
    shutil.rmtree(path)


#
# The tests
#
def test_csv_tar(csv_path):
    db = lb.CSVLogger(csv_path, tar=True)

    with SimpleRack(db=db) as rack:
        rack.simple_loop()

    assert db.path.exists()
    assert (db.path / db.OUTPUT_FILE_NAME).exists()
    assert (db.path / db.INPUT_FILE_NAME).exists()
    assert (db.path / db.munge.tarname).exists()

    df = lb.read(db.path / "outputs.csv")
    assert set(rack.simple_loop_expected_columns()) == set(df.columns)
    assert len(df.index) == len(rack.FREQUENCIES)


def test_csv(csv_path):
    db = lb.CSVLogger(csv_path, tar=False)

    with SimpleRack(db=db) as rack:
        rack.simple_loop()

    assert db.path.exists()
    assert (db.path / db.OUTPUT_FILE_NAME).exists()
    assert (db.path / db.INPUT_FILE_NAME).exists()

    df = lb.read(db.path / "outputs.csv")
    assert set(rack.simple_loop_expected_columns()) == set(df.columns)
    assert len(df.index) == len(rack.FREQUENCIES)


try:
    import tables
except ImportError:
    pass
else:

    def test_hdf(hdf_path):
        db = lb.HDFLogger(path=hdf_path)

        with SimpleRack(db=db) as rack:
            rack.simple_loop()

        # self.assertTrue(db.path.exists())
        # self.assertTrue((db.path / db.OUTPUT_FILE_NAME).exists())
        # self.assertTrue((db.path / db.INPUT_FILE_NAME).exists())

        # df = lb.read(db.path / "outputs.csv")
        # self.assertEqual(set(rack.simple_loop_expected_columns()), set(df.columns))
        # self.assertEqual(len(df.index), len(rack.FREQUENCIES))


def test_csv_keyed_method(csv_path):
    db = lb.CSVLogger(csv_path, tar=False)

    with SimpleRack(db=db) as rack:
        rack.inst.str_keyed_with_arg("value", registered_channel=1)
        rack.db.new_row()

    df = lb.read(db.path / "outputs.csv")
    assert "inst_str_keyed_with_arg_registered_channel_1" in df.columns


def test_csv_decorated_method(csv_path):
    db = lb.CSVLogger(path=csv_path, tar=False)

    with SimpleRack(db=db) as rack:
        rack.inst.str_decorated_with_arg("value", decorated_channel=2, bandwidth=100e6)
        rack.db.new_row()

    df = lb.read(db.path / "outputs.csv")
    assert "inst_str_decorated_with_arg_decorated_channel_2_bandwidth_100000000_0" in df.columns


def test_sqlite(sqlite_path):
    db = lb.SQLiteLogger(path=sqlite_path)

    with SimpleRack(db=db) as rack:
        rack.simple_loop()

    assert db.path.exists()
    # self.assertTrue((db.path / db.OUTPUT_FILE_NAME).exists())
    # self.assertTrue((db.path / db.INPUT_FILE_NAME).exists())
    # self.assertTrue((db.path / db.munge.tarname).exists())

    # df = lb.read(db.path / "outputs.csv")
    # self.assertEqual(set(rack.simple_loop_expected_columns()), set(df.columns))
    # self.assertEqual(len(df.index), len(rack.FREQUENCIES))
