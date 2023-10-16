import labbench as lb
import labbench.paramattr as param
import pandas as pd
import numpy as np


@param.visa_keying(
    # the default SCPI query and write formats
    query_fmt="{key}?",
    write_fmt="{key} {value}",
    # map python True and False values to these SCPI strings
    remap={True: "ON", False: "OFF"},
)
@param.adjusted(
    # set the identity_pattern
    "identity_pattern",
    default=r"Power Sensor model \#1234",
)
class PowerSensor(lb.VISADevice):
    RATES = "NORM", "DOUB", "FAST"

    # SCPI string keys and bounds on the parameter values,
    # taken from the instrument programming manual
    initiate_continuous = param.property.bool(
        key="INIT:CONT", help="trigger continuously if True"
    )
    trigger_count = param.property.int(
        key="TRIG:COUN", min=1, max=200, help="acquisition count", label="samples"
    )
    measurement_rate = param.property.str(
        key="SENS:MRAT",
        only=RATES,
        case=False,
    )
    sweep_aperture = param.property.float(
        key="SWE:APER", min=20e-6, max=200e-3, help="measurement duration", label="s"
    )
    frequency = param.property.float(
        key="SENS:FREQ",
        min=10e6,
        max=18e9,
        step=1e-3,
        help="calibration frequency",
        label="Hz",
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


@param.visa_keying(remap={True: "ON", False: "OFF"})
@param.adjusted("identity_pattern", default=r"Spectrum analyzer model \#1234")
class SpectrumAnalyzer(lb.VISADevice):
    center_frequency = param.property.float(
        key="SENS:FREQ",
        min=10e6,
        max=18e9,
        step=1e-3,
        help="input signal center frequency",
        label="Hz",
    )
    resolution_bandwidth = param.property.float(
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

        series = pd.Series([float(s) for s in response.split(",")], name="spectrum")
        series.index = pd.Index(
            self.center_frequency + np.linspace(-5e6, 5e6, len(series)),
            name="frequency",
        )

        return series

    def trigger(self):
        return self.write("TRIG")


@param.visa_keying(remap={True: "YES", False: "NO"})
@param.adjusted("identity_pattern", default=r"Signal generator model \#1234")
class SignalGenerator(lb.VISADevice):
    output_enabled = param.property.bool(
        key="OUT:ENABL", help="when True, output an RF tone"
    )
    center_frequency = param.property.float(
        key="SENS:FREQ",
        min=10e6,
        max=18e9,
        step=1e-3,
        help="input signal center frequency",
        label="Hz",
    )
    mode = param.property.str(key="MODE", only=["sweep", "tone", "iq"], case=False)

    def trigger(self):
        """revert to instrument preset state"""
        self.write("TRIG")


channel_check = lb.validate_parameter("channel", int, min=1, max=4)


@param.visa_keying(remap={True: "ON", False: "OFF"})
@param.adjusted("identity_pattern", default=r"Oscilloscope model \#1234")
class Oscilloscope(lb.VISADevice):
    @param.method.float(
        "value",
        min=10e6,
        max=18e9,
        step=1e-3,
        label="Hz",
        help="channel center frequency",
        argchecks=[channel_check],
    )
    def center_frequency(self, value=lb.Undefined, /, *, channel: int):
        if value is lb.Undefined:
            return self.query(f"CH{channel}:SENS:FREQ?")
        else:
            self.write(f"CH{channel}:SENS:FREQ {value}")

    resolution_bandwidth = param.method.float(
        key="CH{channel}:SENS:BW",
        min=1,
        max=40e6,
        step=1e-3,
        help="channel resolution bandwidth",
        label="Hz",
        # argchecks omitted deliberately for testing
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
