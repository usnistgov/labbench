# labbench
The `labbench` python library provides tools for instrument automation and data management in scripted lab experiments.

A device driver implemented with labbench is a light wrapper around another instrument control library.
This means another library (like pyvisa, pyserial, libtelnet, or even a C or .NET DLL) provides low-level routines. The labbench
abstraction provides several benefits:

* automatic acquisition logging into an SQLite database,
* automatically-generated jupyter notebook monitoring widgets,
* interact with settings and data on remote devices with native python data types (instead of strings),
* python exceptions on invalid device state settings (instead of silent failure),
* drivers provide consistent style and API conventions for easy scripting (hello, tab completion!),
* ensure devices disconnect properly when acquisition completes (even on exceptions), and
* conversion of vector or tabular data to [pandas](pandas.pydata.org) Series or DataFrame objects for rapid exploration of data.

Together, these features help to minimize the amount of "copy-and-paste" code that can make your lab automation scripts error-prone and difficult to maintain.
The python code that results can be clear, concise, reusable and maintainable, and
provide consistent formatting for stored data.
The result helps researchers to meet NIST's
[open data](https://www.nist.gov/open) obligations, even for complicated, large,
and heterogeneous datasets.

Additional goodies include 
* [simplified threading for parallel execution](http://pages.nist.gov/labbench/labbench.html#labbench.util.concurrently)
* [convenience objects to manage testbeds made of multiple devices](http://pages.nist.gov/labbench/labbench.html#labbench.util.Testbed)
* [real-time heads-up displays for jupyter notebooks](http://pages.nist.gov/labbench/labbench.html#module-labbench.notebooks)
* [convenience functions for reading relational table data from multiple rows](http://pages.nist.gov/labbench/labbench.html#labbench.data.read_relational)

Information here is mostly about writing your own drivers. Specific drivers written in labbench are implemented in other libraries.

### Design
Driver control over scalar instrument settings follows the [descriptor](https://docs.python.org/3/howto/descriptor.html)
(also known as [decorator](https://en.wikipedia.org/wiki/Decorator_pattern)) design pattern.
The implementation of these descriptors is an extension of [traitlets](https://github.com/ipython/traitlets),
enabling optional integration into [jupyter notebook](http://jupyter.org/) widgets
for real-time state readouts.
Other libraries (pyvisa, pyserial, pythonnet, etc.) provide backends;
labbench Driver subclasses standardize an object protocol for backend wrappers that include context management and decriptors.

## Installation
1. Install your favorite distribution of a python version 3.6 or greater
2. In a command prompt, `pip install git+https://github.nist.gov/usnistgov/labbench`
3. (Optional) install an NI VISA [[1](#myfootnote1)] runtime, for example [this one for windows](http://download.ni.com/support/softlib/visa/NI-VISA/16.0/Windows/NIVISA1600runtime.exe).

## Usage
#### Getting started
* [Using labbench drivers](examples/How to use a labbench driver by example.ipynb)
* [Primer on device control with object-oriented scripting](examples/Object oriented programming for device control.ipynb)

#### Using drivers and labbench goodies for laboratory automation
* [Execute multiple automation functions concurrently](examples/How to run more than one function at the same time.ipynb)
* [Log the state of instruments to an sqlite database file](blob/master/examples/How%20to%20automatically%20log%20to%20an%20SQLite%20database.ipynb)
* [Indicate testbed state in jupyter notebook](examples/Goodies for jupyter notebook.ipynb)

#### Writing your own device driver
* [Introduction](examples/Workflow for writing labbench drivers.ipynb)
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
