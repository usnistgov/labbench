---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.15.2
kernelspec:
  display_name: base
  language: python
  name: python3
---

# Testbed Organization

To organize procedures that use more than one device wrapper, implement {py:class}`labbench.Rack` classes. These act as containers for aspects of automation that need to access a particular set of device objects, or even other rack objects, together with associated automation routines. When they are open in a `with` block, they ensure that all `Device` connections are closed together if there is an exception.

## Example: 3 Devices
Suppose we want to run an experiment automated with 3 instruments.

```{code-cell} ipython3
import labbench as lb

# simulated instruments and matching resource manager
from labbench.testing.pyvisa_sim import SignalGenerator, PowerSensor, SpectrumAnalyzer
lb.visa_default_resource_manager('@sim')
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
        self.spectrum_analyzer.resolution_bandwidth = 10e6

        self.power_sensor.preset()
        self.power_sensor.frequency = center_frequency

    def acquire(self, *, duration):
        self.spectrum_analyzer.trigger()
        lb.sleep(duration)

    def fetch(self):
        spectrum = self.spectrum_analyzer.fetch()
        pvt = self.power_sensor.fetch()
        return {
            'spectrum': spectrum,
            'power': pvt
        }


class Sweep(lb.Rack):
    # we can mix and match Device and Rack instances to compose nested
    # test automation components
    generator: SignalGenerator = SignalGenerator()

    # our custom Rack as a required argument
    measurement: Measurement

    def open(self):
        """all Rack objects call open() automatically after it has been called for owned devices"""
        self.generator.preset()
        self.generator.mode = "tone"

    def single_frequency(self, center_frequency, duration):
        self.generator.center_frequency = center_frequency

        self.measurement.setup(center_frequency=center_frequency)
        self.generator.output_enabled = True
        self.measurement.acquire(duration=duration)
        self.generator.output_enabled = False
        return self.measurement.fetch()

    def run(self, frequencies, duration):
        ret = []

        for freq in frequencies:
            ret.append(self.single_frequency(freq, duration))

        return ret
```

## Usage in test scripts
When executed to run test scripts, create Rack instances with input objects according to their definition:

```{code-cell} ipython3
lb.show_messages('debug')

sensor=PowerSensor()
meas = Measurement(power_sensor=sensor)
sweep = Sweep(measurement=meas)

with sweep:
    data = sweep.single_frequency(2.4e9, duration=0.25)
```

They open and close connections with all child devices by use of the `with` block (the python context manager). On entry into this block, connections to all devices (recursively) in `Sweep` open together. Similarly, after the last line in the block, or if an exception is raised, all of the devices are closed together.

```{code-cell} ipython3
data[0]['spectrum']
```
