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

longdescription = \
""" The `labbench` module provides tools for instrument automation and data management in scripted lab experiments.

A device driver implemented with labbench is a light wrapper around another instrument control library.
This library (like pyvisa, pyserial, libtelnet, or even a C or .NET DLL) provides low-level to access instrument.
The labbench driver gives a declarative-style abstraction provides several benefits:

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
"""

if __name__ == '__main__':
    from distutils.core import setup, Extension
    import setuptools
    import sys
    from glob import glob
    sys.path.insert(0, './labbench')
    from _version import __version__

    py_version_req = (3, 7)
    if sys.version_info < py_version_req:
        raise ValueError(
            f"python version is {sys.version} but install requires >={'.'.join([str(v) for v in py_version_req])}")

    setup(name='labbench',
          version=__version__,
          description='scripting tools for streamlined laboratory automation',
          author='Dan Kuester, Shane Allman, Paul Blanchard, Yao Ma',
          author_email='daniel.kuester@nist.gov',
          url='https://github.com/usnistgov/labbench',
          packages=setuptools.find_packages(),
          packagedata={'labbench': ['*.pyi']},
          license='NIST',
          install_requires=['pandas(>=0.20)',
                            'pyserial(>=3.0)',
                            'pyvisa(>=1.8)',
                            'coloredlogs(>=7.0)',
                            'numpy(>=1.0)',
                            'scipy(>=0.9)',
                            'sortedcontainers(>=1.4)',
                            'psutil(>=5.0)',
                            'sqlalchemy',
                            'GitPython(>=2.0)',
                            'pyarrow',
                            'traitlets(>=4)'
                            ],
          extras_require={'html': ['sphinx(>=1.6)','recommonmark'],
                          'notebook': ['notebook', 'ipywidgets']},
          long_description=longdescription,
          long_description_content_type="text/markdown",                          
          )
