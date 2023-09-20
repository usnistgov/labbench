---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.15.1
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Data Logging
Several objects are included in `labbench` for logging test conditions and resulting measurement results.
* Automatic logging of interactions with `Device` attributes that are defined with `lb.property`, `lb.value`, and `lb.datareturn`
* Manual logging through simple dictionary mapping
The data model is driven by a root table of test conditions and measurement results, with relational tables when necessary. In the root table, each row represents a test condition. Common non-scalar data types (`pandas.DataFrame`, `numpy.array`, long strings, files generated outside the data tree, etc.) are automatically stored in folders, which are referred to by relative file paths in the database.

Logging is provided for several root data formats through `labbench.CSVLogger`, `labbench.HDFLogger`, and `labbench.SQLiteLogger`.

## Example: Logging with `Device` objects in scripts
The use of logging objects requires some light configuration, and one call to add data per test row.

```{code-cell} ipython3
import labbench as lb
from labbench.testing import SpectrumAnalyzer, PowerSensor, pyvisa_sim_resource
import numpy as np
import shutil, time

FREQ_COUNT = 3
DUT_NAME = "DUT 63"
DATA_PATH = './data'

# the labbench.testing devices support simulated pyvisa operations
lb.visa_default_resource_manager(pyvisa_sim_resource)
lb.show_messages('debug')

sensor = PowerSensor()
analyzer = SpectrumAnalyzer()
shutil.rmtree(DATA_PATH, True)
db = lb.CSVLogger(path=f"./data")

# automatic logging from `analyzer` in 'output.csv' in each call to db.new_row:
# (1) each lb.property or lb.value that has been get or set in the device since the last call
db.observe(analyzer)

# automatic logging from `sensor` in 'output.csv' in each call to db.new_row:
# (1) each lb.property or lb.value that has been get or set in the device since the last call
# (2) explicitly get `sensor.sweep_aperture` (as column "sensor_sweep_aperture")
db.observe(sensor, always=['sweep_aperture'])

with sensor, analyzer, db:
    for freq in np.linspace(5.8e9, 5.9e9, FREQ_COUNT):
        # Assignment to these property attributes:
        # (1) sets the frequency on each instrument *and*
        # (2) triggers logging of these values in the next database row in
        #     the columns 'analyzer_center_frequency' and 'sensor_frequency'
        analyzer.center_frequency = freq
        sensor.frequency = freq

        sensor.trigger()
        analyzer.trigger()

        # Logs the measurements and test conditions as a new row. Each key
        # is a column in the database in addition to the automatic parameters
        db.new_row(
            comments='trying for 1.21 GW to time travel',
            dut = DUT_NAME,
            analyzer_trace=analyzer.fetch(),
            sensor_reading=sensor.fetch()[0]
        )
```

### Reading and exploring the data
The master database is now populated with the test results and subdirectories are populated with trace data. `labbench` provides the function `read` as a shortcut to load the table of measurement results into a [pandas](http://pandas.pydata.org/pandas-docs/stable/) DataFrame table:

```{code-cell} ipython3
root = lb.read(f'{db.path}/outputs.csv')
root
```

This is a relational data table: non-scalar data (arrays, tables, etc.) and long text strings are replaced with relative paths to files where data is stored. Examples here include the measurement trace from the spectrum analyzer (column 'analyzer_trace.csv'), and the host log JSON file ('host_log).

To analyze the experimental data, one approach is to access these files directly at these files

```{code-cell} ipython3
rel_path = root['analyzer_trace'].values[0]
lb.read(f"{db.path}/{rel_path}").head()
```

For a more systematic analysis to analyzing the data, we may want to expand the root table based on the relational data files in one of these columns. A shortcut for this is provided by `labbench.read_relational`:

```{code-cell} ipython3
lb.read_relational(
    f'{db.path}/outputs.csv',

    # the column containing paths to relational data tables.
    # the returned table places a .
    'analyzer_trace',

    # copy fixed values of these column across as columns in each relational data table
    ['sensor_frequency', 'sensor_sweep_aperture']
)
```

For each row in the root table, the expanded table is expanded with a copy of the contents of the relational data table in its file path ending in `analyzer_trace.csv`.

```{code-cell} ipython3
import labbench as lb
from labbench.testing import SpectrumAnalyzer, PowerSensor, SignalGenerator, pyvisa_sim_resource
import numpy as np
from shutil import rmtree

FREQ_COUNT = 3
DUT_NAME = "DUT 63"
DATA_PATH = './data'


# the labbench.testing devices support simulated pyvisa operations
lb.visa_default_resource_manager(pyvisa_sim_resource)

class Testbed(lb.Rack):
    sensor: PowerSensor = PowerSensor()
    analyzer: SpectrumAnalyzer = SpectrumAnalyzer()
    db: lb.CSVLogger = lb.CSVLogger(path=DATA_PATH)

    def open(self):
        # remove prior data before we start
        self.db.observe(self.analyzer)
        self.db.observe(self.sensor, always=['sweep_aperture'])

    def single(self, frequency: float):
        self.analyzer.center_frequency = frequency
        self.sensor.frequency = frequency

        self.sensor.trigger()
        self.analyzer.trigger()

        return dict(
            analyzer_trace=self.analyzer.fetch(),
            sensor_reading=self.sensor.fetch()[0]
        )

rmtree(Testbed.db.path, True)

with Testbed() as rack:
    for freq in np.linspace(5.8e9, 5.9e9, FREQ_COUNT):
        rack.single(freq)

        # this could also go in single()
        rack.db.new_row(
            comments='trying for 1.21 GW to time travel',
            dut = DUT_NAME,
        )
```
