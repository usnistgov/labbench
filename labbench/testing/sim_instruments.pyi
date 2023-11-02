import labbench as lb
from _typeshed import Incomplete

class PowerSensor(lb.VISADevice):
    def __init__(
        self,
        resource: str = "str",
        read_termination: str = "str",
        write_termination: str = "str",
        open_timeout: str = "NoneType",
        identity_pattern: str = "str",
        timeout: str = "NoneType",
    ): ...
    RATES: Incomplete
    initiate_continuous: Incomplete
    trigger_count: Incomplete
    measurement_rate: Incomplete
    sweep_aperture: Incomplete
    frequency: Incomplete

    def preset(self) -> None: ...
    def fetch(self): ...
    def trigger(self): ...

class SpectrumAnalyzer(lb.VISADevice):
    def __init__(
        self,
        resource: str = "str",
        read_termination: str = "str",
        write_termination: str = "str",
        open_timeout: str = "NoneType",
        identity_pattern: str = "str",
        timeout: str = "NoneType",
    ): ...
    center_frequency: Incomplete
    resolution_bandwidth: Incomplete

    def load_state(self, remote_filename: str): ...
    def fetch(self): ...
    def trigger(self): ...

class SignalGenerator(lb.VISADevice):
    def __init__(
        self,
        resource: str = "str",
        read_termination: str = "str",
        write_termination: str = "str",
        open_timeout: str = "NoneType",
        identity_pattern: str = "str",
        timeout: str = "NoneType",
    ): ...
    output_enabled: Incomplete
    center_frequency: Incomplete
    mode: Incomplete

    def trigger(self) -> None: ...

class Oscilloscope(lb.VISADevice):
    def __init__(
        self,
        resource: str = "str",
        read_termination: str = "str",
        write_termination: str = "str",
        open_timeout: str = "NoneType",
        identity_pattern: str = "str",
        timeout: str = "NoneType",
    ): ...
    def center_frequency(self, set_value=..., *, channel): ...
    resolution_bandwidth: Incomplete

    def load_state(self, remote_filename: str): ...
    def fetch(self): ...
    def trigger(self): ...
