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
A number of tools are included in `labbench` to streamline acquisition of test data into a database. A couple of methods are

* Automatically monitoring attributes in `state` and logging changes
* Saving postprocessed data in the as a new column

The data management supports automatic relational databasing. Common non-scalar data types (`pandas.DataFrame`, `numpy.array`, long strings, files generated outside of the data tree, etc.) are automatically stored relationally --- placed in folders and referred to in the database. Other data can be forced to be relational by dynamically generating relational databases on the fly.

## File conventions
All labbench data save functionality is implemented in tables with [pandas](pandas.pydata.org) DataFrame backends. Here are database storage formats that are supported:

| Format                            | File extension(s)              | Data management class | flag to [use record file format](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.RelationalTableLogger.set_relational_file_format) | Comments |
|:----------------------------------|:-------------------------------|:-----------------------|:------------------------|:----
| [sqlite](sqlite.org)              | .db                            | [labbench.SQLiteLogger](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.SQLiteLogger) | 'sqlite' | Scales to larger databases than csv |
| csv                               | .csv,.csv.gz,.csv.bz2,.csv.zip | [labbench.CSVLogger](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.CSVLogger)          |'csv'| Easy to inspect |

Several formats are supported only as relational data (data stored in a file in the subdirectory instead of directly in the ). Certain types of data as values into the database manager automatically become relational data when you call the `append` method of the data manager:

| Format                            | File extension(s)              | python type conversion | [set_record file format](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.RelationalTableLogger.set_relational_file_format) flag | Comments |
|:----------------------------------|:-------------------------------|:-----------------------|:------------------------|:----
| [feather](github.com/wesm/feather)| .f                             | iterables of numbers and strings; pd.DataFrame | 'feather' | Python 3.x only
| [json](http://www.json.org/)      | .json                          | iterables of numbers and strings; pd.DataFrame         | 'json' | |
| csv                               | .csv | iterables of numbers and strings; pd.DataFrame         |'csv'| |
| python [pickle](https://docs.python.org/3/library/pickle.html) | .pickle | any | 'pickle' | fallback if the chosen relational format fails |
| text files     | .txt | string or bytes longer than `text_relational_min` | N/A | set `text_relational_min` when you instantiate the database manager
| arbitrary files generated outside the file tree |     *             | strings containing filesystem path | N/A |

In the following example, we will use an sqlite master database, and csv record files.

+++

## Example
Here is a emulated "dummy" instrument. It has a few state settings similar to a simple power sensor. The state descriptors (`initiate_continuous`, `output_trigger`, etc.) are defined as local types, which means they don't trigger communication with any actual devices. The `fetch_trace` method generates a "trace" drawn from a uniform distribution.

```{code-cell} ipython3
import labbench as lb
import numpy as np

from labbench.testing import SpectrumAnalyzer, PowerSensor, pyvisa_sim_resource
```

Now make a loop to execute 100 test runs with two emulated instruments, and log the results with a relational SQLite database. I do a little setup to start:

1. Define a couple of functions `inst1_trace` and `inst2_trace` that collect my data
2. Instantiate 2 instruments, `inst1` and `inst2`
3. Instantiate the logger with `lb.SQLiteLogger('test.db', 'state')`.
   The arguments specify the name of the sqlite database file and the name of the table where the following will be stored: 1) the instrument state info will be stored, 2) locations of data files, and 3) any extra comments we add with `db.write()`.

Remember that use of the `with` statement automatically connects to the instruments, and then ensures that the instruments are properly closed when we leave the `with` block (even if there is an exception).

```{code-cell} ipython3
from time import strftime

FREQ_COUNT = 3
DUT_NAME = "DUT 63"

# allow simulated connections to the specified VISA devices
lb.visa_default_resource_manager(pyvisa_sim_resource)

sensor = PowerSensor()
analyzer = SpectrumAnalyzer()
db = lb.CSVLogger(path=f"data {strftime('%Y-%m-%d %Hh%Mm%S')}")
# Catch any changes in inst1.state and inst2.state


# automatic logging from `analyzer` in 'output.csv' in each call to db.new_row:
# (1) each lb.property or lb.value that has been get or set in the device since the last call
db.observe(analyzer)

# automatic logging from `sensor` in 'output.csv' in each call to db.new_row:
# (1) each lb.property or lb.value that has been get or set in the device since the last call
# (2) explicitly get `sensor.sweep_aperture` (as column "sensor_sweep_aperture")
db.observe(sensor, always=['sweep_aperture'])

pending = []
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

#### Reading and exploring the data
The master database is now populated with the test results and subdirectories are populated with trace data. `labbench` provides the function `read` as a shortcut to load the table of measurement results into a [pandas](http://pandas.pydata.org/pandas-docs/stable/) DataFrame table:

```{code-cell} ipython3
root = lb.read(f'{db.path}/outputs.csv')
root
```

This is a relational data table: non-scalar data (arrays, tables, etc.) and long text strings are replaced with relative paths to files where data is stored. Examples here include the measurement trace from the spectrum analyzer (column 'analyzer_trace.csv'), and the host log JSON file ('host_log).

To analyze the experimental data, one approach is to access these files directly at these files

```{code-cell} ipython3
rel_path = root['analyzer_trace'].values[0]
lb.read(f"{db.path}/{rel_path}")
```

This is a relational data table: non-scalar data (arrays, tables, etc.) and long text strings are replaced with relative paths to files where data is stored. Examples here include the measurement trace from the spectrum analyzer (column 'analyzer_trace.csv'), and the host log JSON file ('host_log).

Suppose we want to expand a table based on the relational data files in one of these columns. A shortcut for this is provided by `labbench.read_relational`:

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
