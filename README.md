# labbench
This is a set of python tools for writing laboratory automation scripts that are
clear, concise, and explainable.
Code that achieves these goals should read like a pseudocode expression of the experimental
procedure.
The labbench module works toward this goal by introducing an object protocol and
support functions. These implement repetitive and error-prone boilerplate code needed
to manage data, coerce values between pythonic and over-the-wire and pythonic data types,
validate value constraints, manage threads for concurrent I/O, provide hooks for user
interfaces, and coordinate connections between multiple devices.
These capabilities also provide consistency in data output between data
collected in experiments.


### Coordinating between devices
Organize experiments clearly by defining `Task`s that implement the role of a small
number of `Device` instances. A `Testbed` class collects `Task` objects with the
`Device` instances needed to fulfill a role, manages the connection of these devices.
A more complete experimental procedure can be expressed by defining a sequence
of concurrent and sequential task execution with `lb.multitask`. The `Testbed` also
 makes the data collected by `Device` and `Task` available to database managers, which 
capture the `Device` states and data fetched during the experiment. 

```python
import labbench as lb

# my library of labbench Device drivers  
from myinstruments import MySpectrumAnalyzer, MySignalGenerator


class Synthesize(lb.Task):
    inst: MySignalGenerator

    def setup(self, * center_frequency):
        self.inst.preset()
        self.inst.set_mode('cw')
        self.inst.center_frequency = center_frequency
        self.inst.bandwidth = 2e6

    def arm(self):
        self.inst.rf_output_enable = True

    def finish(self):
        self.inst.stop()


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

### Devices
A device driver implemented with labbench is a light wrapper around another instrument control library.
This means another library (like pyvisa, pyserial, libtelnet, or even a C or .NET DLL) provides low-level routines. The labbench
abstraction provides several benefits:

Driver control over scalar instrument settings follows the [descriptor](https://docs.python.org/3/howto/descriptor.html)
(also known as [decorator](https://en.wikipedia.org/wiki/Decorator_pattern)) design pattern.
The descriptors are implemented by annotations.

(...add more useful description etc. like above...)

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
