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

import labbench as lb
from labbench import paramattr as attr
from labbench.testing import store_backend
import unittest
import pandas as pd
import numpy as np
import shutil


@store_backend.key_store_adapter(
    defaults={"SWE:APER": '20e-6'}
)
class StoreDevice(store_backend.TestStoreDevice):
    """This "instrument" makes mock data and instrument property traits to
    demonstrate we can show the process of value trait
    up a measurement.
    """

    # values
    trace_index = attr.value.int(0)

    # properties
    initiate_continuous = attr.property.bool(key="INIT:CONT")
    output_trigger = attr.property.bool(key="OUTP:TRIG")
    sweep_aperture = attr.property.float(
        key="SWE:APER", min=20e-6, max=200e-3, help="time (in s)"
    )
    frequency = attr.property.float(
        key="SENS:FREQ", min=10e6, max=18e9, help="center frequency (in Hz)"
    )
    atten = attr.property.float(key="POW", min=0, max=100, step=0.5)

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

class StoreRack(lb.Rack):
    """ a device paired with a logger"""

    inst: StoreDevice = StoreDevice()
    db: lb._data.TabularLoggerBase

    FREQUENCIES = 10e6, 100e6, 1e9, 10e9
    EXTRA_VALUES = dict(power=1.21e9, potato=7)

    def simple_loop(self):
        self.db.observe(self.inst, changes=True, always="sweep_aperture")

        for self.inst.frequency in self.FREQUENCIES:
            self.inst.index = self.inst.frequency
            self.inst.fetch_trace()
            self.db.new_row(**self.EXTRA_VALUES)

    def simple_loop_expected_columns(self):
        return tuple(self.EXTRA_VALUES.keys()) + (
            'inst_trace_index', 'inst_frequency', 'inst_sweep_aperture','db_host_time', 'db_host_log'
        )

    def delete_data(self):
        shutil.rmtree(self.db.path)


class TestDataLogging(unittest.TestCase):
    def make_db_path(self):
        return f"test db/{np.random.bytes(8).hex()}"

    def test_csv_tar(self):
        db=lb.CSVLogger(
            path=self.make_db_path(),
            tar=True
        )

        with StoreRack(db=db) as rack:
            rack.simple_loop()

        self.assertTrue(db.path.exists())
        self.assertTrue((db.path/db.OUTPUT_FILE_NAME).exists())
        self.assertTrue((db.path/db.INPUT_FILE_NAME).exists())
        self.assertTrue((db.path/db.munge.tarname).exists())

        df = lb.read(db.path/'outputs.csv')
        self.assertEqual(set(rack.simple_loop_expected_columns()), set(df.columns))
        self.assertEqual(len(df.index), len(rack.FREQUENCIES))

        rack.delete_data()

    def test_csv(self):
        db=lb.CSVLogger(
            path=self.make_db_path(),
            tar=False
        )

        with StoreRack(db=db) as rack:
            rack.simple_loop()

        self.assertTrue(db.path.exists())
        self.assertTrue((db.path/db.OUTPUT_FILE_NAME).exists())
        self.assertTrue((db.path/db.INPUT_FILE_NAME).exists())
        df = lb.read(db.path/'outputs.csv')
        self.assertEqual(set(rack.simple_loop_expected_columns()), set(df.columns))
        self.assertEqual(len(df.index), len(rack.FREQUENCIES))

        rack.delete_data()

if __name__ == "__main__":
    lb.util.force_full_traceback(True)
    lb.show_messages("info")

    unittest.main()