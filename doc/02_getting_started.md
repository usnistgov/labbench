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

# Getting started

## Single devices 
A `Device` object is the central encapsulates python control over a single piece of laboratory equipment or a software instance. Organizing automation with the `Device` classes in this way immediately provides shortcuts for

* automatic logging 
* coercion between python types and low-level/over-the-wire data types
* constraints on instrument parameters
* multi-threaded connection management
* hooks for real-time heads-up displays

### A basic VISA device wrapper
Let's start by a simple demonstration with [VISA](https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture) instrument automation. To do this, we write wrapper that specializes the general-purpose `labbench.VISADevice` backend, which uses the [`pyvisa`](https://pyvisa.readthedocs.io/) library. This helps to expedite [SCPI](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments) messaging patterns that arise often.

The example below gives a simplified working example of [a more complete commercial power sensor](https://github.com/usnistgov/ssmdevices/blob/main/ssmdevices/instruments/power_sensors.py):

```{code-cell} ipython3
import labbench as lb

@lb.property.visa_keying(
    # these are the default SCPI query and write formats
    query_fmt="{key}?",
    write_fmt="{key} {value}",

    # map python True and False values to these SCPI strings
    remap={True: "ON", False: "OFF"}
)
class PowerSensor(lb.VISADevice):
    RATES = "NORM", "DOUB", "FAST"

    # SCPI string keys and bounds on the parameter values,
    # taken from the instrument programming manual
    initiate_continuous = lb.property.bool(
        key="INIT:CONT", label="trigger continuously if True"
    )
    trigger_count = lb.property.int(
        key="TRIG:COUN", min=1, max=200,
        help="acquisition count", label="samples"
    )
    measurement_rate = lb.property.str(
        key="SENS:MRAT", only=RATES, case=False, label="Hz"
    )
    sweep_aperture = lb.property.float(
        key="SWE:APER", min=20e-6, max=200e-3,
        help="measurement duration", label="s"
    )
    frequency = lb.property.float(
        key="SENS:FREQ",
        min=10e6,
        max=18e9,
        step=1e-3,
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

This object is already enough for us to automate an RF power measurements!

### Usage of device wrappers
An automation script uses 

```{code-cell} ipython3
# specify the VISA address to use the power sensor
sensor = PowerSensor("USB0::0x2A8D::0x1E01::SG56360004::INSTR")

# connection to the power sensor hardware at the specified address
# is held open until exiting the "with" block
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
```

The usage here is simple because the methods and traits for automation can be discovered easily through tab completion in most IDEs. The device connection remains open for all lines inside the `with` block..

## Multiple devices

To organize and operate multiple Device instances, `labbench` provides `Rack` objects. These act as a container for aspects of automation needed to perform into a resuable automation task, including `Device` objects, other `Rack` objects, and automation functions. On exception, they ensure that all `Device` connections are closed.

### Basic implementation
The following example creates simple automation tasks for a swept-frequency microwave measurement built around one `Device` each:

```{code-cell} ipython3
import labbench as lb

# some custom library of Device drivers
from myinstruments import MySpectrumAnalyzer, MySignalGenerator


class Synthesizer(lb.Rack):
    # inputs needed to run the rack: in this case, a Device
    inst: MySignalGenerator

    def setup(self, *, center_frequency):
        self.inst.preset()
        self.inst.set_mode("carrier")
        self.inst.center_frequency = center_frequency
        self.inst.bandwidth = 2e6

    def arm(self):
        self.inst.rf_output_enable = True

    def stop(self):
        self.inst.rf_output_enable = False


class Analyzer(lb.Rack):
    # inputs needed to run the rack: in this case, a Device
    inst: MySpectrumAnalyzer

    def setup(self, *, center_frequency):
        self.inst.load_state("savename")
        self.inst.center_frequency = center_frequency

    def acquire(self, *, duration):
        self.inst.trigger()
        lb.sleep(duration)
        self.inst.stop()

    def fetch(self):
        # testbed data will have a column called 'spectrogram', which
        # point to subdirectory containing a file called 'spectrogram.csv'
        return dict(spectrogram=self.inst.fetch_spectrogram())


class SweptMeasurement(lb.Rack):
    # inputs needed to run the rack: in this case, child Rack objects
    generator: Synthesizer
    detector: Analyzer

    def single(self, center_frequency, duration):
        self.generator.setup(center_frequency)
        self.detector.setup(center_frequency)

        self.generator.arm()
        self.detector.acquire(duration)
        self.generator.stop()

        return self.detector.fetch()

    def run(self, frequencies, duration):
        ret = []

        for freq in frequencies:
            ret.append(self.single(freq, duration))

        return duration
```

### Usage in test scripts
When executed to run test scripts, create Rack instances with input objects according to their definition:

```{code-cell} ipython3
sa = MySpectrumAnalyzer(resource="a")
sg = MySignalGenerator(resource="b")

with SweptMeasurement(generator=Synthesizer(sg), detector=Analyzer(sa)) as sweep:
    measurement = sweep.run(frequencies=[2.4e9, 2.44e9, 2.48e9], duration=1.0)
```

They open and close connections with all `Device` children by use of `with` methods. The connection state of all `SweptMeasurement` children are managed together, and all are closed in the event of an exception.
