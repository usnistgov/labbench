# labbench
This is a set of python tools for writing laboratory automation scripts that are
clear, concise, and explainable.
Code that achieves these goals should read like a pseudocode expression of the experimental
procedure. Objects for control over equipment (or other software) should only expose
a clear set of automation capabilities to make scripting more enjoyable and straightforward.

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
    initiate_continuous = lb.Bool(key='INIT:CONT')
    output_trigger = lb.Bool(key='OUTP:TRIG')
    trigger_source = lb.Unicode(key='TRIG:SOUR', only=('IMM', 'INT', 'EXT', 'BUS', 'INT1'), case=False)
    trigger_count = lb.Int(key='TRIG:COUN', min=1, max=200)
    measurement_rate = lb.Unicode(key='SENS:MRAT', only=('NORM', 'DOUB', 'FAST'), case=False)
    sweep_aperture = lb.Float(key='SWE:APER', min=20e-6, max=200e-3, help='time (s)')
    frequency = lb.Float(key='SENS:FREQ', min=10e6, max=18e9, step=1e-3,
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
Experiments with very many `Devices` can use `Task` objects to implement the procedures for a small
number of `Device` instances. A `Testbed` class collects `Task` objects with the
`Device` instances needed to fulfill a role. It manages the connection of these devices together,
and ensures graceful disconnection of all `Device` instances in case of an unhandled exception.
A more complete experiment can be expressed by defining the joint concurrent and sequential execution
of multiple tasks `lb.multitask`. The `Testbed` also exposes device state and fetched data for 
database managers to save to disk.

Here is an example based on two hypothetical instruments:
```python
import labbench as lb

from myinstruments import MySpectrumAnalyzer, MySignalGenerator # custom library of Device drivers

class Synthesize(lb.Task):
    inst: MySignalGenerator

    def setup(self, * center_frequency):
        self.inst.preset()
        self.inst.set_mode('carrier')
        self.inst.center_frequency = center_frequency
        self.inst.bandwidth = 2e6

    def arm(self):
        self.inst.rf_output_enable = True

    def finish(self):
        self.inst.rf_output_enable = False


class Analyze(lb.Task):
    inst: MySpectrumAnalyzer

    def setup(self, *, center_frequency):
        self.inst.load_state('savename')
        self.inst.center_frequency = center_frequency

    def acquire(self, *, duration):
        self.inst.trigger()
        lb.sleep(duration)
        self.inst.stop()

    def fetch(self):
        self.inst.fetch_spectrogram() # this data logs automatically


class MyTestbed(lb.Testbed):
    db = lb.SQLiteLogger(
        'data',                         # path to a new directory to contain data
        dirname_fmt='{id} {host_time}', # format string for relational data
        nonscalar_file_type='csv',      # numerical data format
        tar=False                       # True to embed relational data in `data.tar`
    )

    sa = MySpectrumAnalyzer(resource='a')
    sg = MySignalGenerator(resource='b')

    # tasks just need to know the required devices
    generate = Synthesize(inst=sg)
    detect = Analyze(inst=sa)

    run = lb.multitask(
        (generate.setup & detect.setup),  # setup: executes the long setups concurrently
        (generate.arm, detect.acquire), # acquire: arms the generator, and starts acquisition
        (generate.finish & detect.fetch),  # fetch: these can also be concurrent
    )
```

The `Testbed` includes most of the required implementation, so execution scripts can be
very short:

```python
with MyTestbed() as test: # instruments stay connected while in this block
    for freq in (915e6, 2.4e9, 5.3e9):
        test.run(center_frequency=center_frequency, duration=5) # passes args to the Task methods
```

## Installation
Start in an installation of your favorite python>=3.7 distribution.

* To install the current version, open a command prompt and type
  ```pip install labbench```
* To install the "stable" development version (git master branch), open a command prompt and type
  ```pip install git+https://github.nist.gov/usnistgov/labbench```
* To install the "bleeding edge" development version (git develop branch), open a command prompt and type
  ```pip install git+https://github.nist.gov/usnistgov/labbench@develop```

If you plan to use VISA devices, install an NI VISA [[1](#myfootnote1)] runtime, such as [this one for windows](http://download.ni.com/support/softlib/visa/NI-VISA/16.0/Windows/NIVISA1600runtime.exe).

## Usage
#### Getting started
* [Using labbench drivers](examples/How%20to%20use%20a%20labbench%20driver%20by%20example.ipynb)
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
* CommandLineWrapper (standard input/output wrapper for command line programs)
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
|Shane Allman|shane.allman@nist.gov|
|Paul Blanchard|paul.blanchard@nist.gov|
|Yao Ma|<yao.ma@nist.gov>|

_<a name="myfootnote1">[1]</a> Certain commercial equipment, instruments, or
materials are identified in this repository in order to specify the application
adequately. Such identification is not intended to imply recommendation
or endorsement by the National Institute of Standards and Technology, nor is it
intended to imply that the materials or equipment identified are necessarily the
best available for the purpose._
