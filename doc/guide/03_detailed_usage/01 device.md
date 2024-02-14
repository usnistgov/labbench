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

# Device Wrappers

The {py:class}`labbench.Device` class is the root type used to define data and methods that provide control and logging for lab software and equipment. Use of this class as a base for implementing source automation provides many conveniences toward reducing visual noise in the source code that can obscure the experimental procedure being implemented in automation scripts. This development pattern focuses on short descriptor declarations that replace repetitive code for logging data validation, calibration corrections, type conversion, and string operations.

## Automatic method generation
The example below gives a minimal working example of a [VISA](https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture) instrument wrapper taken from [[1]](https://github.com/usnistgov/ssmdevices/blob/main/ssmdevices/instruments/power_sensors.py):

```{code-cell} ipython3
import labbench as lb
from labbench import paramattr as attr

lb.visa_default_resource_manager('@sim-labbench')

class PowerSensor(lb.VISADevice):
    def fetch(self) -> float:
        """acquire a power reading"""
        return float(self.query)

    frequency = attr.method.float(
        key="SENS:FREQ",
        min=10e6,
        max=18e9,
        step=1e-3,
        help="calibration frequency",
        label="Hz",
    )
```

Usage in test automation looks like this:

```{code-cell} ipython3
with PowerSensor() as sensor:
    sensor.frequency(6e9)
    data = sensor.fetch()
```

The {py:class}`labbench.VISADevice` class is a specialized `Device`. It seeds our `PowerSensor` object with pyvisa-specific methods and context managers. As an exmple of this, the `fetch` method calls `self.query`, which follows the pyvisa [resource](https://pyvisa.readthedocs.io/en/latest/introduction/communication.html) object. Under the hood, this calls the query method in `pyvisa`, which can be accessed at `self.backend.query`.

The {py:mod}`attr.method.float` descriptor shows what is special about {py:class}`labbench.Device` objects: automatic implementation of parameter get/set methods with parameters copied from a programming manual. 
* `key` sets the [SCPI](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) command string used to set the parameter on the instrument
* `min` and `max` define bounds that trigger `ValueError`
* `step` defines resolution step size. python values are rounded to this resolution before sending to the  
* `help` and `label` metadata are used to auto-generate documentation and label units
Other examples of data types and additional configuration arguments are available in the {py:mod}`attr.method` reference.

```{admonition} Getting started with a new instrument
Establishing basic control over an instrument often needs some trial and error. A recommended procedure is as follows:
1. Establish a connection to the instrument, referring to the [pyvisa communication documentation](https://pyvisa.readthedocs.io/en/latest/introduction/communication.html)
2. Verify basic communication with the instrument using very simple commands
3. Refer to the instrument programming manual to add one command at a time, testing each by verifying on the instrument itself
```

## Comparison against direct implementation with pyvisa
As a point of comparison, suppose we implement our example by writing our own class from scratch, without labbench. It might look like this:

```{code-cell} ipython3
import pyvisa
import logging
logger = logging.getLogger()

class PowerSensor:
    def __init__(self, rm: pyvisa.ResourceManager, resource_name: str):
        self.rm = rm
        self.resource_name = resource_name

    def open():
        self.backend = rm.open_resource(resource_name)

    def close():
        self.backend.close()

    def frequency(self, set_value=None):
        """get or set the instrument calibration frequency"""
        command = 'SENS:FREQ'
        
        if set_value is None:
            ret = float(self.backend.query(f'{command}?'))
            logger.info(f'got frequency {ret}')
            return ret
        else:
            if set_value < 0 or set_value > 18e9:
                raise ValueError('set_value is out of bounds')
            set_value = round(float(set_value), 3)
            logger.info(f'set frequency {set_value}')
            self.backend.write(f'{command} {set_value}')

    def fetch(self) -> float:
        """acquire a power reading"""
        return float(self.query)
```

This is a functional way to leverage pyvisa to communicate with the power sensor. Yet, if we scale up to more parameters, substantial parts of this become repetitive boilerplate:
* The line count doubles the labbench implementation
* Maintenance of the basic algorithm becomes difficult
* Key hard-coded constants are buried, making them harder to find and risking copy/paste transcription mistakes when implementing other parameters


## Further Reading