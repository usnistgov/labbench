---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.15.1
kernelspec:
  display_name: base
  language: python
  name: python3
---

# Logging device states and test results to a database
A number of tools are included in `labbench` to streamline acquisition of test data into a database. A couple of methods are

* Automatically monitoring attributes in `state` and logging changes
* Saving postprocessed data in the as a new column

The data management supports automatic relational databasing. Common non-scalar data types (`pandas.DataFrame`, `numpy.array`, long strings, files generated outside of the data tree, etc.) are automatically stored relationally --- placed in folders and referred to in the database. Other data can be forced to be relational by dynamically generating relational databases on the fly.

## File conventions
All labbench data save functionality is implemented in tables with [pandas](http://pandas.pydata.org) DataFrame backends. Here are database storage formats that are supported:

| Format                            | File extension(s)              | Data management class | flag to [use record file format](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.RelationalTableLogger.set_relational_file_format) | Comments |
|:----------------------------------|:-------------------------------|:-----------------------|:------------------------|:----
| [sqlite](http://sqlite.org/)              | .db                            | [labbench.SQLiteLogger](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.SQLiteLogger) | 'sqlite' | Scales to larger databases than csv |
| csv                               | .csv,.csv.gz,.csv.bz2,.csv.zip | [labbench.CSVLogger](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.CSVLogger)          |'csv'| Easy to inspect |

Several formats are supported only as relational data (data stored in a file in the subdirectory instead of directly in the ). Certain types of data as values into the database manager automatically become relational data when you call the `append` method of the data manager:

| Format                            | File extension(s)              | python type conversion | [set_record file format](http://ssm.ipages.nist.gov/labbench/labbench.html#labbench.managedata.RelationalTableLogger.set_relational_file_format) flag | Comments |
|:----------------------------------|:-------------------------------|:-----------------------|:------------------------|:----
| [feather](http://github.com/wesm/feather)| .f                             | iterables of numbers and strings; pd.DataFrame | 'feather' | Python 3.x only
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
import sys
sys.path.insert(0,'..')
import labbench as lb
import numpy as np
import pandas as pd

class EmulatedInstrument(lb.EmulatedVISADevice):
    """ This "instrument" makes mock data and instrument states to
        demonstrate we can show the process of setting
        up a measurement.
    """
    class state (lb.EmulatedVISADevice.state):
        initiate_continuous:bool = attr.property(key='INIT:CONT')
        output_trigger:bool = attr.property(key='OUTP:TRIG')
        sweep_aperture:float = attr.property(min=20e-6, max=200e-3,help='s')
        frequency:float = attr.property(min=10e6, max=18e9,step=1e-3,help='Hz')

    def trigger(self):
        """ This would tell the instrument to start a measurement
        """
        pass
    
    def fetch_trace(self, N=1001):
        """ Generate N points of junk data as a pandas series.
        """
        values = np.random.normal(size=N)
        index = np.linspace(0,self.state.sweep_aperture,N)
        series = pd.Series(values,index=index,name='voltage')
        series.index.name = 'time'
        return series
```

Now make a loop to execute 100 test runs with two emulated instruments, and log the results with a relational SQLite database. I do a little setup to start:

1. Define a couple of functions `inst1_trace` and `inst2_trace` that collect my data
2. Instantiate 2 instruments, `inst1` and `inst2`
3. Instantiate the logger with `lb.SQLiteLogger('test.db', 'state')`.
   The arguments specify the name of the sqlite database file and the name of the table where the following will be stored: 1) the instrument state info will be stored, 2) locations of data files, and 3) any extra comments we add with `db.write()`.

Remember that use of the `with` statement automatically connects to the instruments, and then ensures that the instruments are properly closed when we leave the `with` block (even if there is an exception).

```{code-cell} ipython3
def inst1_trace ():
    """ Return a 1001-point trace
    """
    inst1.trigger()
    return inst1.fetch_trace(51)

def inst2_trace ():
    """ This one returns only one point
    """
    inst2.trigger()
    return inst2.fetch_trace(1).values[0]
    
# Root directory of the database
db_path = r'data'

# Seed the data dictionary with some global data
data = {'dut': 'DUT 15'}

Nfreqs = 101

with EmulatedInstrument()        as inst1,\
     EmulatedInstrument()        as inst2,\
     lb.SQLiteLogger(db_path)  as db:
        # Catch any changes in inst1.state and inst2.state
        db.observe_states([inst1,inst2])  
        
        # Update inst1.state.sweep_aperture on each db.append
        db.observe_states(inst1, always='sweep_aperture')
        
        # Store trace data in csv format
        db.set_relational_file_format('csv')
        
        # Perform a frequency sweep. The frequency will be logged to the
        # database, because we configured it to observe all state changes.
        inst2.state.frequency = 5.8e9
        for inst1.state.frequency in np.linspace(5.8e9, 5.9e9, Nfreqs):                    
            # Collect "test data" by concurrently calling
            # inst1_trace and inst2_trace
            data.update(lb.concurrently(inst1_trace, inst2_trace))

            # Append the new data as a row to the database.
            # Each key is a column in the database (which will be added
            # dynamically to the database if needed). More keys and values
            # are also added corresponding to attributes inst1.state and inst2.state
            db.append(comments='trying for 1.21 GW to time travel',
                      **data)
```

### Reading and exploring the data
The master database is now populated with the test results and subdirectories are populated with trace data. `labbench` provides the function `read` as a shortcut to load the sqlite database into a pandas dataframe. Each state is a column in the database. The logger creates columns named as a combination of the device name ('inst1') and name of the corresponding device state.

```{code-cell} ipython3
%pylab inline
master = lb.read(f'{db_path}/master.db')
master.head()
```

This is a pandas DataFrame object. There is extensive information about how to use dataframes [on the pandas website](http://pandas.pydata.org/pandas-docs/stable/). Suppose we want to bring in the data from the traces, which are in a collection of waveform files specified under the `inst1_trace` column. The function `labbench.expand` serves to flatten the database with respect to data files that were generated on each row.

```{code-cell} ipython3
waveforms = lb.read_relational(f'{db_path}/master.db', 'inst1_trace', ['dut', 'inst1_frequency'])
waveforms
```

now we can manipulate the results to look for meaningful information in the data.

```{code-cell} ipython3
import seaborn as sns; sns.set(context='notebook', style='ticks', font_scale=1.5) # Theme stuff

waveforms.plot(x='inst1_frequency',y='inst1_trace_voltage',kind='hexbin')
xlabel('Frequency (Hz)')
ylabel('Voltage (arb units)')
```
