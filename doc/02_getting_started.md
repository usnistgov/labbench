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

## Device objects
A `Device` object is a wrapper built around a low-level device backend. It encapsulates the python control needed to automate lab tool cleanly. Organizing access into the `Device` class immediately provides transparent capability to

* automatically log interactions with the device
* establish coercion between pythonic and low-level or over-the-wire data types
* apply value constraints on instrument parameters
* simplify threaded operation among multiple instruments at the same time 
* make hooks available to a user interface in real time
* ensure clean device disconnection on python exceptions

Typical `Device` driver development work flow focuses communicating with the instrument. The drivers are made up of descriptors and methods, thanks to a small, targeted set of convenience tools focused on data types and communication backends.

### A basic VISA device wrapper
Let's start by demonstrating automation with [VISA](https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture). To do this, we write wrapper that specializes the general-purpose `labbench.VISADevice` backend, which uses the [`pyvisa`](pyvisa.readthedocs.io) library. This helps to expedite messaging patterns that arise often in [SCPI query and write commands](https://en.wikipedia.org/wiki/Standard_Commands_for_Programmable_Instruments).

The example below gives a simplified working example of [a more complete commercial power sensor](https://github.com/usnistgov/ssmdevices/blob/main/ssmdevices/instruments/power_sensors.py):

```{code-cell}
import labbench as lb
import pandas as pd

# configure the SCPI strings for python True and False
@lb.property.visa_keying(remap={True: "ON", False: "OFF"})
class PowerSensor(lb.VISADevice):
    SOURCES = 'IMM', 'INT', 'EXT', 'BUS', 'INT1'
    RATES = 'NORM', 'DOUB', 'FAST'

    # shortcut definitions of instrument parameters from its programming manual
    initiate_continuous = lb.property.bool(key='INIT:CONT')
    output_trigger = lb.property.bool(key='OUTP:TRIG')
    trigger_source = lb.property.str(key='TRIG:SOUR', only=SOURCES, case=False)
    trigger_count = lb.property.int(key='TRIG:COUN', min=1, max=200)
    measurement_rate = lb.property.str(key='SENS:MRAT', only=RATES, case=False)
    sweep_aperture = lb.property.float(key='SWE:APER', min=20e-6, max=200e-3, help='time (s)')
    frequency = lb.property.float(key='SENS:FREQ', min=10e6, max=18e9, step=1e-3,
                         help='input signal center frequency (in Hz)')

    # instrument-based operations 
    def preset(self):
        self.write('SYST:PRES')

    def fetch(self):
        response = self.query('FETC?').split(',')
        if len(response) == 1:
            return float(response[0])
        else:
            return pd.to_numeric(pd.Series(response))
```

This is by itself a functioning instrument automation driver that is sufficient to control an actual commercial instrument.

### Usage of device wrappers
Instantiate a `PowerSensor` instance to apply it in instrument automation:

```{code-cell} ipython3
---
other:
  more: true
tags: [hide-output, show-input]
---

# open a connection
with PowerSensor('USB0::0x2A8D::0x1E01::SG56360004::INSTR') as sensor:
    # apply the instrument preset state
    sensor.preset()

    # set parameters onboard the power sensor
    sensor.frequency = 1e9
    sensor.measurement_rate = 'FAST'
    sensor.trigger_count = 200
    sensor.sweep_aperture = 20e-6
    sensor.trigger_source = 'IMM'
    sensor.initiate_continuous = True

    power = sensor.fetch()
```

manage instrument connection, to get and set the parameters inside the instrument according to the `lb.property` definitions, and perform measurements:
The usage here is simple because the methods and traits for automation can be discovered easily through tab completion in most IDEs. The device connection remains open for all lines inside the `with` block..

## Rack objects

To organize and operate multiple Device instances, `labbench` provides `Rack` objects. These act as a container for aspects of automation needed to perform into a resuable automation task, including `Device` objects, other `Rack` objects, and automation functions. On exception, they ensure that all `Device` connections are closed.

### Basic implementation
The following example creates simple automation tasks for a swept-frequency microwave measurement built around one `Device` each:

```{code-cell} ipython
import labbench as lb

# some custom library of Device drivers
from myinstruments import MySpectrumAnalyzer, MySignalGenerator

class Synthesizer(lb.Rack):
    # inputs needed to run the rack: in this case, a Device    
    inst: MySignalGenerator

    def setup(self, *, center_frequency):
        self.inst.preset()
        self.inst.set_mode('carrier')
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
        self.inst.load_state('savename')
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

```{code-cell}
sa = MySpectrumAnalyzer(resource='a')
sg = MySignalGenerator(resource='b')

with SweptMeasurement(generator=Synthesizer(sg), detector=Analyzer(sa)) as sweep:
    measurement = sweep.run(
        frequencies=[2.4e9, 2.44e9, 2.48e9],
        duration=1.0
    )
```

They open and close connections with all `Device` children by use of `with` methods. The connection state of all `SweptMeasurement` children are managed together, and all are closed in the event of an exception.
