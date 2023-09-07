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

## Organizing Testbeds

To organize automation across multiple `Device` wrappers, `labbench` provides `Rack` objects. These act as a container for aspects of automation needed to perform into a resuable automation task, including `Device` objects, other `Rack` objects, and automation functions. On exception, they ensure that all `Device` connections are closed.

### Example Implementation: 2 Device wrappers
The following example creates simple automation tasks for a swept-frequency microwave measurement. This one is built around one `Device`:

```{code-cell} ipython3
import labbench as lb

# my_instruments.py constaints Device classes for a few instruments
from my_instruments import SpectrumAnalyzer, SignalGenerator


class Synthesizer(lb.Rack):
    # inputs needed to run the rack: in this case, a Device
    inst: SignalGenerator

    def setup(self, *, center_frequency):
        self.inst.preset()
        self.inst.mode = "tone"
        self.inst.center_frequency = center_frequency

    def arm(self):
        self.inst.rf_output_enable = True

    def stop(self):
        self.inst.rf_output_enable = False


class Analyzer(lb.Rack):
    # inputs needed to run the rack: in this case, a Device
    inst: SpectrumAnalyzer

    def setup(self, *, center_frequency):
        self.inst.load_state("savename")
        self.inst.center_frequency = center_frequency
        self.resolution_bandwidth = 10e6

    def acquire(self, *, duration):
        self.inst.trigger()
        lb.sleep(duration)
        return self.inst.fetch()

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
sa = SpectrumAnalyzer(resource="a")
sg = SignalGenerator(resource="b")

with SweptMeasurement(generator=Synthesizer(sg), detector=Analyzer(sa)) as sweep:
    measurement = sweep.run(frequencies=[2.4e9, 2.44e9, 2.48e9], duration=1.0)
```

They open and close connections with all `Device` children by use of `with` methods. The connection state of all `SweptMeasurement` children are managed together, and all are closed in the event of an exception.
