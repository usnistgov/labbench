[![PyPI Latest Release](https://img.shields.io/pypi/v/labbench.svg)](https://pypi.org/project/labbench/)
[![DOI](https://zenodo.org/badge/DOI/10.18434/M32122.svg)](https://doi.org/10.18434/M32122)
[![License](https://img.shields.io/badge/license-NIST-brightgreen)](https://github.com/usnistgov/labbench/blob/master/LICENSE.md)
[![Downloads](https://static.pepy.tech/badge/labbench)](https://pepy.tech/project/labbench)
[![Last commit](https://img.shields.io/github/last-commit/usnistgov/labbench)](https://pypi.org/project/labbench/)

# labbench
This is a set of python tools for writing laboratory automation scripts that are
clear, concise, and explainable.
Code that achieves these goals should read like a pseudocode expression of the experimental
procedure. Objects for control over equipment (or other software) should only expose
a clear set of automation capabilities to make laboratory automation more robust and less frustrating.

The labbench module provides tools that support toward this goal through an object protocol and
support functions. These separate repetitive and error-prone boilerplate code,
Use of these capabilities among multiple experimental runs also helps to produced data sets with
consistent structure.

### Devices
A `Device` object exposes automation control over a piece of lab equipment, or software as a virtual "device." Organizing access into the `Device` class immediately provides transparent capability to

* log data from the device
* define consistent coercion between pythonic and over-the-wire data types
* apply value constraints on instrument parameters
* support threaded operation concurrent I/O
* hook the Device state to user interface display
* ensure device disconnection on python exceptions

Typical `Device` driver development work flow focuses communicating with the instrument. The drivers are made up of descriptors and methods, thanks to a small, targeted set of convenience tools focused on data types and communication backends. The following `VISADevice` backend illustrates a complete example on a complete power sensor:

```python
import labbench as lb
import pandas as pd

class PowerSensor(lb.VISADevice):
    SOURCES = 'IMM', 'INT', 'EXT', 'BUS', 'INT1'
    RATES = 'NORM', 'DOUB', 'FAST'

    initiate_continuous = lb.property.bool(key='INIT:CONT')
    output_trigger = lb.property.bool(key='OUTP:TRIG')
    trigger_source = lb.property.str(key='TRIG:SOUR', only=SOURCES, case=False)
    trigger_count = lb.property.int(key='TRIG:COUN', min=1, max=200)
    measurement_rate = lb.property.str(key='SENS:MRAT', only=RATES, case=False)
    sweep_aperture = lb.property.float(key='SWE:APER', min=20e-6, max=200e-3, help='time (s)')
    frequency = lb.property.float(key='SENS:FREQ', min=10e6, max=18e9, step=1e-3,
                         help='input signal center frequency (in Hz)')

    def preset(self):
        self.write('SYST:PRES')

    def fetch(self):
        """ return a single power reading (if self.trigger_count == 1) or pandas Series containing the power trace """
        response = self.query('FETC?').split(',')
        if len(response) == 1:
            return float(response[0])
        else:
            return pd.to_numeric(pd.Series(response))
```

The `VISADevice` backend here builds interactive _traits_ (python [descriptors](https://docs.python.org/3/howto/descriptor.html)) from the [SCPI commands](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) given in each `key`. This is a functioning instrument automation driver that works on an actual commercial instrument:

```python
with PowerSensor('USB0::0x2A8D::0x1E01::SG56360004::INSTR') as sensor:
    # configure from scratch
    sensor.preset()

    # the following set parameters on the power sensor
    sensor.frequency = 1e9
    sensor.measurement_rate = 'FAST'
    sensor.trigger_count = 200
    sensor.sweep_aperture = 20e-6
    sensor.trigger_source = 'IMM'
    sensor.initiate_continuous = True

    power = sensor.fetch()
```

The usage here is simple because the methods and traits for automation can be discovered easily through tab completion in most IDEs. They can be used on connection with a simple `with` block.

### Scaling to testbeds
Large test setups can neatly organize procedures that require a few Device instances into `Task` objects. A `Testbed` class collects the set of `Task` instances needed to perform the experiment, manages connection of these devices together,
ensuring graceful disconnection of all `Device` on unhandled exceptions.
A `multitask` definition defines a more complete experiment in the `Testbed` as a concurrent and sequential steps from multiple `Task` objects, using `multitask`. The `Testbed` also optionally exposes device state and fetched data for database management and user interface. The following ties all these together:

```python
# testbed.py
import labbench as lb
from myinstruments import MySpectrumAnalyzer, MySignalGenerator # custom library of Device drivers

class Synthesize(lb.Rack):
    inst: MySignalGenerator

    def setup(self, *, center_frequency):
        self.inst.preset()
        self.inst.set_mode('carrier')
        self.inst.center_frequency = center_frequency
        self.inst.bandwidth = 2e6

    def arm(self):
        self.inst.rf_output_enable = True

    def finish(self):
        self.inst.rf_output_enable = False


class Analyze(lb.Rack):
    inst: MySpectrumAnalyzer

    def setup(self, *, center_frequency):
        self.inst.load_state('savename')
        self.inst.center_frequency = center_frequency

    def acquire(self, *, duration):
        self.inst.trigger()
        lb.sleep(duration)
        self.inst.stop()

    def fetch(self):
        # testbed data will have a column called 'spectrogram', which
        # point to subdirectory containing a file called 'spectrogram.csv'
        return dict(spectrogram=self.inst.fetch_spectrogram())

db = lb.SQLiteLogger(
    'data',                         # path to a new directory to contain data
    dirname_fmt='{id} {host_time}', # format string for relational data
    nonscalar_file_type='csv',      # numerical data format
    tar=False                       # True to embed relational data in `data.tar`
)

sa = MySpectrumAnalyzer(resource='a')
sg = MySignalGenerator(resource='b')

# tasks use the devices
generator = Synthesize(inst=sg)
detector = Analyze(inst=sa)

procedure = lb.Sequence(
    setup=(generator.setup, detector.setup),  # concurrently execute the long setups
    arm=generator.arm, # arm the generator before the detector acquires
    acquire=detector.acquire, # start acquisition in the generator
    fetch=(generator.finish, detector.fetch), # concurrently cleanup and collect the acquired data
    finish=(db.new_row, db.write),          # start the next row in the database
)
```
`testbed.py` here exposes the general capabilities of an experimental setup. An
experiment can be defined and run in a python script by sweeping inputs to `procedure`:
```python
# run.py

Testbed = lb.Rack._from_module('testbed')

with Testbed() as test:
    # flow inside this `with` block only continues when no exception is raised.
    # On Exception, devices and the database disconnect cleanly.

    for freq in (915e6, 2.4e9, 5.3e9):
        test.procedure(
            detector_center_frequency=freq,
            generator_center_frequency=freq,
            detector_duration=5
        ) # each {task}_{argname} applies to all methods in {task} that accept {argname}
```
This script focuses on expressing high-level experimental parameters,
leaving us with a clear pseudocode representation of the experimental procedure.
The test results are saved in an SQLite database,
'data/master.db'. Each row in the database points to spectrogram data in subdirectories that are formatted
as 'data/{id} {host_time}/spectrogram.csv'.

Sometimes it is inconvenient to define the input conditions through code. For these cases,
 labbench includes support for tabular sweeps. An example, `freq_sweep.csv`, could look like this:

| Step        | detector_center_frequency | generator_center_frequency | detector_duration |
|-------------|---------------------------|----------------------------|-------------------|
| Condition 1 | 915e6                     | 915e6                      | 5                 |
| Condition 2 | 2.4e9                     | 2.4e9                      | 5                 |
| Condition 3 | 5.3e9                     | 5.3e9                      | 5                 |

A command line call takes this table input and runs the same experiment as `run.py`:
```shell script
labbench testbed.py procedure freq_sweep.csv
```
This creates a testbed object from `testbed.py`, and steps through the parameter
 values on each row of `freq_sweep.csv`.

## Installation
Start in an installation of your favorite python>=3.7 distribution.

* To install the current version, open a command prompt and type
  ```pip install labbench```
* To install the "stable" version (master branch) from git, open a command prompt and type
  ```pip install git+https://github.com/usnistgov/labbench```
* To install the "bleeding edge" development version (develop branch) from git, open a command prompt and type
  ```pip install git+https://github.com/usnistgov/labbench@develop```

If you plan to use VISA devices, install an NI VISA [[1](#myfootnote1)] runtime.

## Usage
#### Getting started
* [Using labbench drivers](examples/concurrency.ipynb)
* [Primer on device control with object-oriented scripting](examples/Object%20oriented%20programming%20for%20device%20control.ipynb)

#### Using drivers and labbench goodies for laboratory automation
* [Execute multiple automation functions concurrently](examples/How%20to%20run%20more%20than%20one%20function%20at%20the%20same%20time.ipynb)
* [Log the state of instruments to an sqlite database file](examples/How%20to%20automatically%20log%20to%20an%20SQLite%20database.ipynb)
* [Indicate testbed state in jupyter notebook](examples/Goodies%20for%20jupyter%20notebook.ipynb)

#### Writing your own device driver
* [Introduction](examples/Workflow%20for%20writing%20labbench%20drivers.ipynb)
* VISA instruments
* Serial port devices
* .NET [[1](#myfootnote1)] library
* Command line wrapper
* Python module wrapper interface

#### Reference manuals
* [Programming reference](http://pages.nist.gov/labbench)

## Status
The following types of backend classes are implemented to streamline development of new instrumentation drivers:
* ShellBackend (standard input/output wrapper for command line programs)
* DotNet (pythonnet backend for dotnet libraries)
* LabViewSocketInterface (for controlling LabView VIs via a simple networking socket)
* SerialDevice (pyserial backend)
* SerialLoggingDevice (pyserial backend for simple data streaming)
* TelnetDevice (telnetlib backend)
* VISADevice (pyvisa backend)
* EmulatedVISADevice (test-only driver for testing labbench features)

## Contributors
|Name|Contact|
|---|---|
|Dan Kuester (maintainer)|<daniel.kuester@nist.gov>|
|Shane Allman|Formerly with NIST|
|Paul Blanchard|Formerly with NIST|
|Yao Ma|<yao.ma@nist.gov>|

_<a name="myfootnote1">[1]</a> Certain commercial equipment, instruments, or
materials are identified in this repository in order to specify the application
adequately. Such identification is not intended to imply recommendation
or endorsement by the National Institute of Standards and Technology, nor is it
intended to imply that the materials or equipment identified are necessarily the
best available for the purpose._
