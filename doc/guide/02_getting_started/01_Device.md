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

# Device Wrapping

`Device` is the root object used to define and implement automation with a lower-level driver in labbench. Its purpose is to encapsulate python data and methods over a specific type of laboratory equipment or a software.

This section demonstrates usage of `Device` through a lean working example. The wrapper design pattern in `labbench` starts by defining a subclass of `Device` for a specific device, often from one of the backend subclasses that has been specialized for a low-level driver module (`pyvisa``, shell command, etc.). Doing this has several advantages:
* hooks into the data logging subsystem for automatic logging of parameters and acquired data
* automatic coercion between python types and low-level/over-the-wire data types
* constraints on instrument parameters
* multi-threaded connection management

## Example Implementation: A VISA Instrument
Let's start by a simple demonstration with [VISA](https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture) instrument automation. The example below gives a simplified working example modeled on [an actual commercial RF power sensor](https://github.com/usnistgov/ssmdevices/blob/main/ssmdevices/instruments/power_sensors.py):

```{code-cell} ipython3
# sim_instrument1.py
import labbench as lb

@lb.property.visa_keying(
    # the default SCPI query and write formats
    query_fmt="{key}?",
    write_fmt="{key} {value}",

    # map python True and False values to these SCPI strings
    remap={True: "ON", False: "OFF"}
)
@lb.adjusted(
    # set the identity_pattern 
    'identity_pattern', default=r'Power Sensor model \#1234'
)
class PowerSensor(lb.VISADevice):
    RATES = "NORM", "DOUB", "FAST"

    # SCPI string keys and bounds on the parameter values,
    # taken from the instrument programming manual
    initiate_continuous = lb.property.bool(
        key="INIT:CONT", help="trigger continuously if True"
    )
    trigger_count = lb.property.int(
        key="TRIG:COUN", min=1, max=200,
        help="acquisition count", label="samples"
    )
    measurement_rate = lb.property.str(
        key="SENS:MRAT", only=RATES, case=False,
        
    )
    sweep_aperture = lb.property.float(
        key="SWE:APER", min=20e-6, max=200e-3,
        help="measurement duration", label="s"
    )
    frequency = lb.property.float(
        key="SENS:FREQ",
        min=10e6, max=18e9, step=1e-3,
        help="calibration frequency", label="Hz",
    )

    def preset(self):
        """revert to instrument preset state"""
        self.write("SYST:PRES")

    def fetch(self):
        """acquire measurements as configured"""
        response = self.query("FETC?")

        if self.trigger_count == 1:
            return float(response)
        else:
            return [float(s) for s in response.split(",")]
```

Automation capabilities for this instrument are fully encapsulated by the `PowerSensor` object. Some key features:
* `PowerSensor` begins with the attributes the `labbench.VISADevice` backend, which wraps the [`pyvisa`](https://pyvisa.readthedocs.io/) library.
* The various `lb.property` definitions are shortcuts for [SCPI](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) commands on this instrument. When we use `PowerSensor` to control an instrument, getting or setting these properties will trigger SCPI query and commands based on each property's `key`. The property type (`lb.property.float`, `lb.property.str`, etc.) and remaining arguments determine the type and constraints of the python representation of that property.
* The method functions (`fetch` and `preset`) represent examples of other types of SCPI commands that are implemented programmatically.

### Basic Device Wrapper Usage
The implementation of `PowerSensor` above is enough for us to perform a simple measurement. Automation starts with making an instance and then connecting it.
The methods and traits can be discovered through tab completion in most IDEs.

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

Making the `sensor` instance brings the `PowerSensor` class definition to life. This enabled key features:
* The connection remains open for VISA communication inside the `with` block
* Attributes that were defined with `lb.property` in `PowerSensor` become interactive instrument automation in `sensor`. This means that assigning to `sensor.frequency`, `sensor.measurement_rate` trigger VISA writes to set these parameters on the instrument. Similarly, _getting_ each these attributes of sensor triggers VISA queries. The specific SCPI commands are visible here in the debug messages.