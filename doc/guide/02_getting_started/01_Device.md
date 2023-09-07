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
Let's start by a simple demonstration with [VISA](https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture) instrument automation. The example below gives a simplified working example taken from [an actual commercial RF power sensor](https://github.com/usnistgov/ssmdevices/blob/main/ssmdevices/instruments/power_sensors.py):

```{code-cell} ipython3
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
        key="SENS:MRAT", only=RATES, case=False
    )
    sweep_aperture = lb.property.float(
        key="SWE:APER", min=20e-6, max=200e-3,
        help="measurement duration", label="s"
    )
    frequency = lb.property.float(
        key="SENS:FREQ",
        min=10e6, max=18e9, step=1e-3,
        help="input signal center frequency",
        label="Hz",
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

Automation for the power sensor instrument is encapsulated in the `PowerSensor` object.
* `PowerSensor` begins with the attributes the `labbench.VISADevice` backend, which wraps the [`pyvisa`](https://pyvisa.readthedocs.io/) library
* The various `lb.property` definitions are shortcuts for [SCPI](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) commands on this instrument. When we use `PowerSensor` to control an instrument, getting or setting these properties will trigger SCPI query and commands based on each property's `key`. The property type (`lb.property.float`, `lb.property.str`, etc.) and remaining arguments determine the type and constraints of the python representation of that property.
* The method functions (`fetch` and `preset`) represent examples of other types of SCPI commands that are implemented programmatically.

This is a working implementation, which means it is enough for us demonstrate its use in scripting an actual RF power measurement.

### Basic Device Wrapper Usage
Automation with the `PowerSensor` wrapper starts with making an instance and then connecting it.

```{code-cell} ipython3
# a simulated instrument backend makes this self-contained
lb.visa_default_resource_manager('sim-visa.yml@sim')

# print the low-level actions of the code
lb.show_messages('debug')

# specify the VISA address to use the power sensor
sensor = PowerSensor()#"USB::0x1111::0x2222::0x1234::INSTR")

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

The usage here is simple because the methods and traits for automation can be discovered easily through tab completion in most IDEs. The device connection remains open for all lines inside the `with` block.