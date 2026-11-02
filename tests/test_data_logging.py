import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import labbench as lb
from labbench import paramattr as attr
from labbench.testing import store_backend

lb.show_messages('warning')
lb.util.force_full_traceback(True)


@attr.method_kwarg.int('registered_channel', min=1, max=4)
@store_backend.key_adapter(defaults={'SWE:APER': '20e-6'})
class StoreDevice(store_backend.StoreTestDevice):
    """This "instrument" makes mock data and instrument property traits to
    demonstrate we can show the process of value trait
    up a measurement.
    """

    # values
    trace_index = attr.value.int(0)

    # properties
    initiate_continuous = attr.property.bool(key='INIT:CONT')
    output_trigger = attr.property.bool(key='OUTP:TRIG')
    sweep_aperture = attr.property.float(
        key='SWE:APER', min=20e-6, max=200e-3, help='time (in s)'
    )
    frequency = attr.property.float(
        key='SENS:FREQ', min=10e6, max=18e9, help='center frequency (in Hz)'
    )
    atten = attr.property.float(key='POW', min=0, max=100, step=0.5)

    str_keyed_with_arg = attr.method.str(key='str_with_arg_ch_{registered_channel}')
    str_keyed_allow_none = attr.method.str(
        key='str_with_arg_ch_{registered_channel}', allow_none=True
    )

    @attr.method.str()
    @attr.method_kwarg.int(name='decorated_channel', min=1, max=4)
    @attr.method_kwarg.float(name='bandwidth', min=10e3, max=100e6)
    def str_decorated_with_arg(self, /, *, decorated_channel, bandwidth):
        key = self.backend.get_backend_key(
            self,
            type(self).str_decorated_with_arg,
            {'decorated_channel': decorated_channel, 'bandwidth': bandwidth},
        )

        return self.backend.get(key, None)

    @str_decorated_with_arg.setter
    def str_decorated_with_arg(self, new_value, /, *, decorated_channel, bandwidth):
        key = self.backend.get_backend_key(
            self,
            type(self).str_decorated_with_arg,
            {'decorated_channel': decorated_channel, 'bandwidth': bandwidth},
        )

        self.backend.set(key, new_value)

    def trigger(self):
        """This would tell the instrument to start a measurement"""

    def method(self):
        print('method!')

    def fetch_trace(self, N=101):
        """Generate N points of junk data as a pandas series."""
        self.trace_index = self.trace_index + 1

        series = pd.Series(
            self.trace_index * np.ones(N),
            index=self.sweep_aperture * np.arange(N),
            name='Voltage (V)',
        )

        series.index.name = 'Time (s)'
        return series


FREQUENCIES = 10e6, 100e6, 1e9, 10e9
EXTRA_VALUES = dict(power=1.21e9, potato=7)


def simple_loop(db, inst, frequencies: list[float], **extra_column_values):
    db.observe_paramattr(inst, changes=True, always='sweep_aperture')

    for inst.frequency in frequencies:
        inst.index = inst.frequency
        inst.fetch_trace()
        db.new_row(**extra_column_values)


class SimpleRack(lb.Rack):
    """a device paired with a logger"""

    db: lb._data.ParamAttrLogger
    inst: StoreDevice = StoreDevice()

    FREQUENCIES = 10e6, 100e6, 1e9, 10e9
    EXTRA_VALUES = dict(power=1.21e9, potato=7)

    def simple_loop(self):
        return simple_loop(self.db, self.inst, self.FREQUENCIES, **self.EXTRA_VALUES)

    def simple_loop_expected_columns(self):
        return tuple(self.EXTRA_VALUES.keys()) + (
            'inst_trace_index',
            'inst_frequency',
            'inst_sweep_aperture',
            'db_host_time',
            'db_host_log',
        )

    def simple_loop_expected_expanded_columns(self):
        return self.simple_loop_expected_columns() + (
            'db_host_log_elapsed_seconds',
            'db_host_log_id',
            'db_host_log_level',
            'db_host_log_message',
            'db_host_log_object',
            'db_host_log_object_log_name',
            'db_host_log_process',
            'db_host_log_source_file',
            'db_host_log_source_line',
            'db_host_log_thread',
            'db_host_log_time',
            'root_index',
        )


#
# Fixturing
#
@pytest.fixture
def csv_path():
    path = f'test db/{np.random.bytes(8).hex()}.csv'
    yield path
    if Path(path).exists():
        shutil.rmtree(path)


@pytest.fixture
def sqlite_path():
    path = f'test db/{np.random.bytes(8).hex()}.sqlite'
    return path
    # if Path(path).exists():
    #     shutil.rmtree(path)


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

    df = lb.read(db.path / 'outputs.csv')
    expected_root_columns = set(rack.simple_loop_expected_columns())
    assert expected_root_columns == set(df.columns)
    assert len(df.index) == len(rack.FREQUENCIES)

    df = lb.read_relational(db.path / 'outputs.csv', expand_col='db_host_log')

    expected_expanded_columns = set(rack.simple_loop_expected_expanded_columns())
    assert expected_expanded_columns == set(df.columns)


def test_csv(csv_path):
    db = lb.CSVLogger(csv_path, tar=False)

    def json_opener(p):
        return pd.read_json(db.path / p)

    with SimpleRack(db=db) as rack:
        rack.simple_loop()

    assert db.path.exists()
    assert (db.path / db.OUTPUT_FILE_NAME).exists()
    assert (db.path / db.INPUT_FILE_NAME).exists()

    df = lb.read(db.path / 'outputs.csv')
    expected_root_columns = set(rack.simple_loop_expected_columns())
    assert expected_root_columns == set(df.columns)
    assert len(df.index) == len(rack.FREQUENCIES)
    all_json_rows = pd.concat([json_opener(p) for p in df.db_host_log])

    df = lb.read_relational(db.path / 'outputs.csv', expand_col='db_host_log')

    expected_expanded_columns = set(rack.simple_loop_expected_expanded_columns())
    assert expected_expanded_columns == set(df.columns)
    assert len(df.index) == len(all_json_rows)


def test_csv_keyed_method(csv_path):
    db = lb.CSVLogger(csv_path, tar=False)

    with SimpleRack(db=db) as rack:
        rack.inst.str_keyed_with_arg('value', registered_channel=1)
        rack.db.new_row()

    df = lb.read(db.path / 'outputs.csv')
    assert 'inst_str_keyed_with_arg_registered_channel_1' in df.columns


def test_csv_decorated_method(csv_path):
    db = lb.CSVLogger(path=csv_path, tar=False)

    with SimpleRack(db=db) as rack:
        rack.inst.str_decorated_with_arg('value', decorated_channel=2, bandwidth=100e6)
        rack.db.new_row()

    df = lb.read(db.path / 'outputs.csv')
    assert (
        'inst_str_decorated_with_arg_decorated_channel_2_bandwidth_100000000_0'
        in df.columns
    )


def test_sqlite(sqlite_path):
    db = lb.SQLiteLogger(path=sqlite_path)

    def json_opener(p):
        return pd.read_json(db.path / p)

    with SimpleRack(db=db) as rack:
        rack.simple_loop()

    assert db.path.exists()
    assert (db.path / 'root.db').exists()
    assert (db.path / 'metadata.json').exists()

    df = lb.read(db.path / 'root.db')
    expected_root_columns = set(rack.simple_loop_expected_columns())
    assert expected_root_columns == set(df.columns)
    assert len(df.index) == len(rack.FREQUENCIES)
    all_json_rows = pd.concat([json_opener(p) for p in df.db_host_log])

    df = lb.read_relational(db.path / 'root.db', expand_col='db_host_log')

    expected_expanded_columns = set(rack.simple_loop_expected_expanded_columns())
    assert expected_expanded_columns == set(df.columns)
    assert len(df.index) == len(all_json_rows)


@pytest.mark.parametrize('ext', ['pickle', 'p'])
def test_read_pickle_requires_opt_in(tmp_path, monkeypatch, ext):
    df = pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})
    path = tmp_path / f'data.{ext}'
    df.to_pickle(path)

    # unset: refuse, for both guessed and explicit formats
    monkeypatch.delenv('LABBENCH_AUTOLOAD_PICKLE', raising=False)
    with pytest.raises(RuntimeError, match='LABBENCH_AUTOLOAD_PICKLE'):
        lb.read(path)
    with pytest.raises(RuntimeError, match='LABBENCH_AUTOLOAD_PICKLE'):
        lb.read(path, format='pickle')

    # explicitly disabled: still refuse
    monkeypatch.setenv('LABBENCH_AUTOLOAD_PICKLE', '0')
    with pytest.raises(RuntimeError, match='LABBENCH_AUTOLOAD_PICKLE'):
        lb.read(path)

    # opted in: load normally, including column/row selection
    monkeypatch.setenv('LABBENCH_AUTOLOAD_PICKLE', '1')
    pd.testing.assert_frame_equal(lb.read(path), df)
    pd.testing.assert_frame_equal(
        lb.read(path, columns=['a'], nrows=2), df[['a']].iloc[:2]
    )


# %% known faults, recorded in xfail-audit.md


@pytest.mark.xfail(
    strict=True,
    reason='to_feather (_data.py:1613-1618) reads Index.is_monotonic, removed in pandas 2.0, '
    'and np.str, removed in NumPy 1.24',
)
def test_feather_roundtrip(tmp_path):
    import pandas as pd

    df = pd.DataFrame({'a': [1, 2], 'b': [3.0, 4.0]})
    path = tmp_path / 'table.feather'
    lb._data.to_feather(df, path)
    pd.testing.assert_frame_equal(pd.read_feather(path), df)


@pytest.mark.xfail(
    strict=True,
    reason='MungeToTar._relational_from_file (_data.py:493-495) uses self.tar; '
    'the attribute set by open() is self.tarfile',
)
def test_tar_munger_moves_external_file(tmp_path):
    external = tmp_path / 'external' / 'payload.txt'
    external.parent.mkdir()
    external.write_text('payload')
    munger = lb._data.MungeToTar(tmp_path / 'db')
    with munger:
        key = munger._from_external_file('payload', str(external), index=0, row={})
        names = munger.tarfile.getnames()
    assert key in names


@pytest.mark.xfail(
    strict=True,
    reason='Aggregator.get (_data.py:637) reports a key conflict through self.critical, '
    'which Aggregator does not define',
)
def test_aggregator_rack_output_overrides_conflicting_key():
    agg = lb._data.Aggregator()
    agg.incoming_attr_auto = {'shared': 'from attr'}
    agg.incoming_rack_output = {'shared': 'from rack'}
    output, _ = agg.get()
    assert output['shared'] == 'from rack'
