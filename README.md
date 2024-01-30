[![PyPI Latest Release](https://img.shields.io/pypi/v/labbench.svg)](https://pypi.org/project/labbench/)
[![DOI](https://zenodo.org/badge/DOI/10.18434/M32122.svg)](https://doi.org/10.18434/M32122)
[![License](https://img.shields.io/badge/license-NIST-brightgreen)](https://github.com/usnistgov/labbench/blob/master/LICENSE.md)
[![Downloads](https://static.pepy.tech/badge/labbench)](https://pepy.tech/project/labbench)
[![Last commit](https://img.shields.io/github/last-commit/usnistgov/labbench)](https://pypi.org/project/labbench/)
[![Test coverage](./doc/reports/coverage.svg)](https://github.com/usnistgov/labbench/)

The `labbench` module provides API tools to support python scripting for laboratory automation.
The goal is to simplify the process of developing an experimental procedure into clear, concise, explainable, and reusable code.
These characteristics are necessary to scale up the complexity of large testbeds and experiments.

Features include:
* Expedited development of python device wrappers, including specialized backends for [pythonnet](https://github.com/pythonnet/pythonnet/wiki), [pyvisa](https://pyvisa.readthedocs.io/), [pyserial](https://pyserial.readthedocs.io/en/latest/), [subprocess](https://docs.python.org/3/library/subprocess.html), [telnetlib](https://docs.python.org/3/library/telnetlib.html)
* Descriptor-driven development: minimize the distance between programming manuals and python wrappers and apply calibrations transparently
* Automated logging of simple device parameters into root CSV or sqlite root tables, pointing to relational data and metadata in json and plain-text
* Simplified multi-threaded concurrency tools for lab applications
* Container objects for nesting device wrappers and snippets of test procedures
* Support for running experiments based on tables of test conditions

The source code was developed at NIST to support complex measurement efforts. Examples of these projects include:
  * [NIST TN 1952: LTE Impacts on GPS](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.1952.pdf) ([data](https://data.nist.gov/od/id/mds2-2186))
  * [NIST TN 2069: Characterizing LTE User Equipment Emissions: Factor Screening](https://doi.org/10.6028/NIST.TN.2069)
  * [NIST TN 2140: AWS-3 LTE Impacts on Aeronautical Mobile Telemetry](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2140.pdf) ([data](https://data.nist.gov/od/id/mds2-2279))
  * [NIST TN 2147: Characterizing LTE User Equipment Emissions Under Closed-Loop Power Control](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2147.pdf)
  * [Blind Measurement of Receiver System Noise](https://www.nist.gov/publications/blind-measurement-receiver-system-noise) ([data](https://data.nist.gov/pdr/lps/ark:/88434/mds2-2121))
  * Automated Testbed for Interference Testing in Communications Systems ([code](https://github.com/usnistgov/atic/), data)

## Status
The project is under ongoing development
* API changes have slowed, but deprecation warnings are not yet being provided
    * Suggest pinning labbench dependency to an exact version
* Parts of the documentation are in need of updates, and others have not yet been written

## Installation
1. Ensure prerequisites are installed:
    * python (3.9-3.12)
    * [`pip`](https://pypi.org/project/pip/) for package management
2. Recommended module installation:
    * For python distributions based on anaconda:
      ```sh
      pip --upgrade-strategy only-if-needed install labbench
      ```
    * For other python installations:
      ```sh
      pip install labbench
      ```

## Resources
* [Source code](http://github.com/usnistgov/labbench)
* [Documentation](http://pages.nist.gov/labbench)
* [PyPI](https://pypi.org/project/labbench/) module page
* [ssmdevices](https://github.com/usnistgov/ssmdevices): a collection of device wrappers implemented with labbench

## Contributing
* [Pull requests](https://github.com/usnistgov/labbench/pulls) and [bug reports](https://github.com/usnistgov/labbench/issues) are welcome!
* [Inline documentation style convention](https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings)

## Contributors
|Name|Contact|
|---|---|
|Dan Kuester (maintainer)|<daniel.kuester@nist.gov>|
|Shane Allman|Formerly with NIST|
|Paul Blanchard|Formerly with NIST|
|Yao Ma|<yao.ma@nist.gov>|
<!-- 
_<a name="myfootnote1">[1]</a> Certain commercial equipment, instruments, or
materials are identified in this repository in order to specify the application
adequately. Such identification is not intended to imply recommendation
or endorsement by the National Institute of Standards and Technology, nor is it
intended to imply that the materials or equipment identified are necessarily the
best available for the purpose._ -->
