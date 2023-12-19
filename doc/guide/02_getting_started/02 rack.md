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

The primary tool in labbench for testbed organization is the {py:class}`labbench.Rack` class. These act as nestable containers for groups of different {py:class}`labbench.Device` objects with associated automation routines.

## Racks as containers
The basic use of {py:class}`labbench.Rack` is to create a container that groups together different {py:class}`labbench.Device` objects. In order to reduce python object boilerplate, they are written in the style of [dataclasses](https://docs.python.org/3/library/dataclasses.html). As an example, to group together two types of detecting instruments:

```{code-cell} ipython3
import labbench as lb

# simulated instruments
from labbench.testing.pyvisa_sim import PowerSensor, SpectrumAnalyzer


class Measurement(lb.Rack):
    # the annotation (":" notation) specifies that power_sensor
    # can be set later when we create a Measurement object
    spectrum_analyzer: SpectrumAnalyzer = SpectrumAnalyzer()

    # if we don't set a default value in the class (the "=" notation), 
    # then it *must* be set as a keyword argument to create Measurement
    power_sensor: PowerSensor


# the resulting call signature for creating a Measurement
%pdef Measurement
```

This annotation notation gives users the ability to configure the device attributes, such as its resource or address string, at runtime outside of the class definition.

To connect the device in this container together, the first step is to instantiate an object from the `Measuerement` class. Like all {py:class}`labbench.Device` objects, Rack objects all have `open` and `close` methods, which are called automatically by use of the `with` context manager block.

```{code-cell} ipython3
lb.visa_default_resource_manager('@sim') # the simulated backend for these instruments
lb.show_messages('debug')

meas = Measurement(power_sensor=PowerSensor())
with meas:
    print('Spectrum analyzer center frequency: ', meas.spectrum_analyzer.center_frequency)
```

The debug messages show how our `Measurement` container opened all of the connections before the automation functions were performed.

## Nested racks
Rack objects can be nested together, resulting in recursive context management of all devices by a top-level class. For example:

```{code-cell} ipython3
from labbench.testing.pyvisa_sim import SignalGenerator, PowerSensor, SpectrumAnalyzer

class Testbed(lb.Rack):
    # as with Device objects, we annotate a type to allow 
    measurement: Measurement = Measurement(power_sensor=PowerSensor())

    # Device and Rack instances can be mixed and matched
    generator: SignalGenerator = SignalGenerator()

with Testbed() as sweep:
    print('Spectrum analyzer center frequency: ', sweep.measurement.spectrum_analyzer.center_frequency)
    print('Signal generator center frequency: ', sweep.generator.center_frequency)
```

This time, `Sweep` opened connections to all three instruments, even though two were nested inside `measurement`. In fact, these connections are managed properly even if a device is shared by more than one nested rack.

## Custom setup and teardown in Rack
Rack classes can define functions that execute snippets of measurement procedures within the scope of its owned devices. These include an `open` method to initialize the state of the group of instruments. For example, extending our container objects:

```{code-cell} ipython3
from labbench.util import logger
class Measurement(lb.Rack):
    spectrum_analyzer: SpectrumAnalyzer = SpectrumAnalyzer()
    power_sensor: PowerSensor

    def open(self):
        # this is called automatically after its owned devices are opened
        logger.info('Measurement open()')
        self.power_sensor.preset()

    def close(self):
        logger.info('Measurement close()')

class Testbed(lb.Rack):
    generator: SignalGenerator = SignalGenerator()
    measurement: Measurement = Measurement(power_sensor=PowerSensor())

    def open(self):
        # the last open() call is here after everything else has opened
        logger.info('Sweep open()')
        self.generator.preset()

    def close(self):
        # the first close() call is here before nested objects
        logger.info('Sweep close()')

with Testbed() as sweep:
    pass
```

The call order of `open()` methods is always in this order: first, all nested {py:class}`labbench.Device` objects, recursively, and then all rack objects, beginning from the deepest nesting level and proceeding to the top.


**Note**: 
    All {py:class}`labbench.Rack` and {py:class}`labbench.Device` objects have special-case inheritance behavior for `open()` and `close()` methods. These enforce calls to all nested and inherited types
    in order to enforce the sequencing required to for cross-dependency in racks.
    As a result, calling `super().open()` or `super().close()` is redundant and unnecessary.


## Procedural snippets
As an organizational tool, short pieces of experimental procedure can be expressed by implementing methods (class-level functions) in each rack:

```{code-cell} ipython3
class Measurement(lb.Rack):
    spectrum_analyzer: SpectrumAnalyzer = SpectrumAnalyzer()
    power_sensor: PowerSensor

    def setup(self, *, center_frequency):
        self.spectrum_analyzer.load_state("state_filename")
        self.spectrum_analyzer.center_frequency = center_frequency
        self.spectrum_analyzer.resolution_bandwidth = 10e6

        self.power_sensor.preset()
        self.power_sensor.frequency = center_frequency

    def acquire(self):
        self.spectrum_analyzer.trigger()

    def fetch(self):
        spectrum = self.spectrum_analyzer.fetch()
        pvt = self.power_sensor.fetch()
        return {
            'spectrum': spectrum,
            'power': pvt
        }

class Testbed(lb.Rack):
    generator: SignalGenerator = SignalGenerator()
    measurement: Measurement = Measurement(power_sensor=PowerSensor())

    def setup(self, center_frequency: float):
        self.generator.center_frequency = center_frequency
        self.measurement.setup(center_frequency=center_frequency)

    def single_frequency(self, *, center_frequency):
        logger.info(f'single frequency test at {center_frequency/1e6:0.3f} MHz')
        self.generator.output_enabled = True

        self.measurement.acquire()
        self.generator.output_enabled = False
        return self.measurement.fetch()

    def sweep(self, frequencies):
        logger.info(f'starting frequency sweep across {len(frequencies)} points')
        ret = []

        for freq in frequencies:
            ret.append(self.single_frequency(center_frequency=freq))

        return ret
    
lb.show_messages('info')

with Testbed() as testbed:
    data = testbed.sweep(frequencies=[2.4e9, 2.44e9, 2.48e9])
```