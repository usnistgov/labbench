from .. import VISADevice, Device, Undefined
from .. import paramattr as attr
from .. import util
import pandas as pd
import numpy as np
from typing import Dict, Any
from pyvisa.errors import VisaIOError

__all__ = ["PowerSensor", "Oscilloscope", "SignalGenerator"]


@attr.visa_keying(
    # the default SCPI query and write formats
    query_fmt="{key}?",
    write_fmt="{key} {value}",
    # map python True and False values to these SCPI strings
    remap={True: "ON", False: "OFF"},
)
# set the automatic connection filters
@attr.adjust("make", "FakeTech")
@attr.adjust("model", "Power Sensor #1234")
@attr.adjust("write_termination", "\r\n")
class PowerSensor(VISADevice):
    RATES = "NORM", "DOUB", "FAST"

    # SCPI string keys and bounds on the parameter values,
    # taken from the instrument programming manual
    initiate_continuous = attr.property.bool(key="INIT:CONT", help="trigger continuously if True")
    trigger_count = attr.property.int(
        key="TRIG:COUN", help="acquisition count", label="samples", min=1, max=200
    )
    measurement_rate = attr.property.str(
        key="SENS:MRAT",
        only=RATES,
        case=False,
    )
    sweep_aperture = attr.property.float(
        key="SWE:APER", help="measurement duration", label="s", min=20e-6, max=200e-3
    )
    frequency = attr.property.float(
        key="SENS:FREQ",
        help="calibration frequency",
        label="Hz",
        min=10e6,
        max=18e9,
        step=1e-3,
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


@attr.visa_keying(remap={True: "ON", False: "OFF"})
@attr.adjust("make", default="FakeTech")
@attr.adjust("model", default="Spectrum Analyzer #1234")
class SpectrumAnalyzer(VISADevice):
    center_frequency = attr.property.float(
        key="SENS:FREQ",
        min=10e6,
        max=18e9,
        step=1e-3,
        help="input signal center frequency",
        label="Hz",
    )
    resolution_bandwidth = attr.property.float(
        key="SENS:BW",
        min=1,
        max=40e6,
        step=1e-3,
        help="resolution bandwidth",
        label="Hz",
    )

    def load_state(self, remote_filename: str):
        """revert to instrument preset state"""
        self.write(f"LOAD '{remote_filename}'")

    def fetch(self):
        """acquire measurements as configured"""
        response = self.query("FETC?")

        series = pd.Series([float(s) for s in response.split(",")], name="power_spectral_density")
        series.index = pd.Index(
            self.center_frequency + np.linspace(-5e6, 5e6, len(series)),
            name="frequency",
        )

        return series

    def trigger(self):
        util.sleep(0.1)  # simulate slow response
        return self.write("TRIG")


@attr.visa_keying(remap={True: "YES", False: "NO"})
@attr.adjust("make", "FakeTech")
@attr.adjust("model", "Signal Generator #1234")
class SignalGenerator(VISADevice):
    output_enabled = attr.property.bool(key="OUT:ENABL", help="when True, output an RF tone")
    center_frequency = attr.property.float(
        key="SENS:FREQ",
        help="input signal center frequency",
        label="Hz",
        min=10e6,
        max=18e9,
        step=1e-3,
    )
    mode = attr.property.str(key="MODE", only=["sweep", "tone", "iq"], case=False)

    def trigger(self):
        """revert to instrument preset state"""
        self.write("TRIG")


@attr.register_key_argument(attr.kwarg.int("channel", min=1, max=4, help="input channel"))
@attr.visa_keying(remap={True: "ON", False: "OFF"})
@attr.adjust("make", default="FakeTech")
@attr.adjust("model", default="Oscilloscope #1234")
class Oscilloscope(VISADevice):
    @attr.method.float(
        label="Hz",
        help="channel center frequency",
        min=10e6,
        max=18e9,
        step=1e-3,
    )
    def center_frequency(self, set_value=Undefined, /, *, channel):
        if set_value is Undefined:
            return self.query(f"CH{channel}:SENS:FREQ?")
        else:
            self.write(f"CH{channel}:SENS:FREQ {set_value}")

    resolution_bandwidth = attr.method.float(
        key="CH{channel}:SENS:BW",
        help="channel resolution bandwidth",
        label="Hz",
        min=1,
        max=40e6,
        step=1e-3
        # arguments omitted deliberately for testing
    )

    def load_state(self, remote_filename: str):
        """revert to instrument preset state"""
        self.write(f"LOAD '{remote_filename}'")

    def fetch(self):
        """acquire measurements as configured"""
        response = self.query("FETC?")

        series = pd.Series([float(s) for s in response.split(",")], name="spectrum")
        series.index = pd.Index(
            self.center_frequency + np.linspace(-5e6, 5e6, len(series)),
            name="frequency",
        )

        return series

    def trigger(self):
        return self.write("TRIG")


class LocalStoreDevice(Device):
    def open(self):
        self.backend = {}
