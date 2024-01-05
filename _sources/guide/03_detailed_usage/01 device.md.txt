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

{py:class}`labbench.Device` is the root object used to define and implement automation with a lower-level driver. Its purpose is to encapsulate all python data and methods for a specific laboratory device or software.

This section demonstrates usage through a lean working example. The {py:class}`labbench.Device` design pattern for a specific device starts by defining a subclass, often from one of the backend subclasses that has been specialized for a low-level driver module ([`pyvisa`](http://pyvisa.readthedocs.org/), shell commands, etc.). Doing this has several advantages:
* hooks into the [data logging subsystem](./03%20data%20logging.md) for automatic logging of parameters and acquired data
* automatic coercion between python types and low-level/over-the-wire data types
* constraints on instrument parameters
* multi-threaded connection management

## Example Implementation: A VISA Instrument
Let's start by a simple demonstration with [VISA](https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture) instrument automation. The example below gives a simplified working example modeled on [an actual commercial RF power sensor](https://github.com/usnistgov/ssmdevices/blob/main/ssmdevices/instruments/power_sensors.py):

```{code-cell} ipython3
# sim_instrument1.py
import labbench as lb
from labbench import paramattr as attr

@attr.visa_keying(
    # the default SCPI query and write formats
    query_fmt="{key}?",
    write_fmt="{key} {value}",
    # map python True and False values to these SCPI strings
    remap={True: "ON", False: "OFF"},
)
# set the automatic connection filters
@attr.adjust("make", "pyvisa_sim")
@attr.adjust("model", "Power Sensor model 1234")
class PowerSensor(VISADevice):
    RATES = "NORM", "DOUB", "FAST"

    # SCPI string keys and bounds on the parameter values,
    # taken from the instrument programming manual
    initiate_continuous = attr.property.bool(key="INIT:CONT", help="trigger continuously if True")
    trigger_count = attr.property.int(
        key="TRIG:COUN", help="acquisition count", label="samples",
        min=1, max=200
    )
    measurement_rate = attr.property.str(
        key="SENS:MRAT", only=RATES, case=False,
    )
    sweep_aperture = attr.property.float(
        key="SWE:APER", help="measurement duration", label="s",
        min=20e-6, max=200e-3
    )
    frequency = attr.property.float(
        key="SENS:FREQ", help="calibration frequency", label="Hz",
        min=10e6, max=18e9, step=1e-3,
    )

    def preset(self):
        """revert to instrument default presets"""
        self.write("SYST:PRES")

    def fetch(self):
        """acquire measurements as configured"""
        response = self.query("FETC?")

        if self.trigger_count == 1:
            return float(response)
        else:
            return pd.Series([float(s) for s in response.split(",")], name="spectrum")

    def trigger(self):
        return self.write("TRIG")
```

Automation capabilities for this instrument are fully encapsulated by the `PowerSensor` object. Subclassing from {py:class}`labbench.VISADevice` seeds `PowerSensor` with all of its [`pyvisa`](https://pyvisa.readthedocs.io/), including connection management and access to its [pyvisa instrument object](https://pyvisa.readthedocs.io/en/latest/introduction/communication.html) as its `backend` attribute. The method functions (`fetch` and `preset`) represent examples of scripting SCPI commands through explicit code

The various {py:mod}`labbench.property` definitions are shortcuts for [SCPI](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments). In usage of objects derived from {py:class}`labbench.VISABackend`, getting or setting these properties will trigger SCPI query and commands based on each property's `key`.
* The property type ({py:class}`labbench.property.float`, {py:class}`labbench.property.str`, etc.) sets the python type to use for the parameter
* The keyword arguments, which define the SCPI command, validation constraints and documentation metadata, would be  filled in based on the instrument programming manual.
These properties are class _descriptors_ that exist only as definition until we _instantiate_ `PowerSensor` in order to _use_ it.

## Example Usage
The implementation of `PowerSensor` is already enough for us to perform a simple measurement. Automation starts with making an instance and then connecting it. The methods and traits can be discovered through tab completion in most IDEs.

```{code-cell} ipython3
# use a pyvisa-sim simulated VISA instrument for the demo
from labbench import testing
lb.visa_default_resource_manager(testing.pyvisa_sim_resource)

# print the low-level actions of the code
lb.show_messages('debug')

# specify the VISA address to use the power sensor
sensor = PowerSensor()

# the sensor attempts to connect to the hardware on entering a `with` block
with sensor:   
    # apply the instrument preset state
    sensor.preset()

    # set acquisition parameters on the power sensor
    sensor.frequency = 1e9
    sensor.measurement_rate = "FAST"
    sensor.trigger_count = 200
    sensor.sweep_aperture = 20e-6
    sensor.initiate_continuous = True

    # retreive the 200 measurement samples
    power = sensor.fetch()

    # the instrument connection closes on leaving the with block
```

Creating the `sensor` instance brings the `PowerSensor` class definition to life. This means:
* The connection remains open for VISA communication inside the `with` block
* Attributes that were defined with `attr.property` in `PowerSensor` become interactive for instrument automation in `sensor`. This means that assigning to `sensor.frequency`, `sensor.measurement_rate` trigger VISA writes to set these parameters on the instrument. Similarly, _getting_ each these attributes of sensor triggers VISA queries. The specific SCPI commands are visible here in the debug messages.

```{admonition} Getting started with a new instrument
Some trial and error is often needed, and it is best to iterate in small steps:
1. Establish a connection to the instrument, referring to the documentation for the backend (for example, the [pyvisa communication documentation](https://pyvisa.readthedocs.io/en/latest/introduction/communication.html))
2. Verify basic communication with the instrument using very simple commands
3. Refer to the instrument programming manual to add one command at a time, testing each by verifying on the instrument itself
```

## Further Reading
