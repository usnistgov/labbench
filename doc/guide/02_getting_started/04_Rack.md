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

## Testbed Organization

To organize automation across multiple `Device` wrappers, `labbench` provides `Rack` objects. These act as a container for aspects of automation needed to perform into a resuable automation task, including `Device` objects, other `Rack` objects, and automation functions. On exception, they ensure that all `Device` connections are closed.

### Example: 3 Devices
Suppose we need to take a measurement with automation of 2 instruments:

```{code-cell} ipython3
import labbench as lb
from labbench.testing import SignalGenerator, PowerSensor, SpectrumAnalyzer, pyvisa_sim_resource
```

Here is an artificial example of how these could be assembled into `Rack` objects 

```{code-cell} ipython3
class Measurement(lb.Rack):
    # a default device instance makes the `inst` argument 
    # optional when creating the Measurement object.
    spectrum_analyzer: SpectrumAnalyzer = SpectrumAnalyzer()

    # without the default, `power_sensor` _must_ be passed as
    # a keyword argument when instantiating Measurement
    power_sensor: PowerSensor

    def setup(self, *, center_frequency):
        self.spectrum_analyzer.load_state("state_filename")
        self.spectrum_analyzer.center_frequency = center_frequency
        self.resolution_bandwidth = 10e6
        
        self.power_sensor.preset()
        self.power_sensor.frequency = center_frequency

    def acquire(self, *, duration):
        self.spectrum_analyzer.trigger()
        lb.sleep(duration)

    def fetch(self):
        return {
            'spectrum': self.spectrum_analyzer.fetch(),
            'power': self.power_sensor.fetch()
        }


class SweptMeasurement(lb.Rack):
    # we can mix and match Device and Rack instances to compose nested
    # test automation components
    generator: SignalGenerator = SignalGenerator()
    
    # here, to set a default measurement, we'd have to pass in 
    measurement: Measurement
    
    def single(self, center_frequency, duration):
        self.generator.preset()
        self.generator.mode = "tone"
        self.generator.center_frequency = center_frequency
        
        self.measurement.setup(center_frequency=center_frequency)
        self.generator.rf_output_enable = True
        self.measurement.acquire(duration=duration)
        self.generator.rf_output_enable = True

        return self.measurement.fetch()

    def run(self, frequencies, duration):
        ret = []

        for freq in frequencies:
            ret.append(self.single(freq, duration))

        return duration
```

### Usage in test scripts
When executed to run test scripts, create Rack instances with input objects according to their definition:

```{code-cell} ipython3
FREQS = 2.4e9, 2.44e9, 2.48e9

lb.show_messages('debug')

# allow simulated connections to the specified VISA devices
lb.visa_default_resource_manager(pyvisa_sim_resource)

# we might want to specify the address in case e.g. there
# are > 1 power sensor connected
sensor=PowerSensor('USB::0x1111::0x2222::0x1234::INSTR')

sweep = SweptMeasurement(measurement=Measurement(power_sensor=sensor))
with sweep:
    measurements = [sweep.single(fc, duration=1.0) for fc in FREQS]
```

They open and close connections with all `Device` children by use of `with` methods. The connection state of all `SweptMeasurement` children are managed together, and all are closed in the event of an exception.
