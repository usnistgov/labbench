import labbench as lb


@lb.property.visa_keying(remap={True: "ON", False: "OFF"})
@lb.adjusted('identity_pattern', default=r'Spectrum analyzer model \#1234')
class SpectrumAnalyzer(lb.VISADevice):
    center_frequency = lb.property.float(
        key="SENS:FREQ",
        min=10e6, max=18e9, step=1e-3,
        help="input signal center frequency",
        label="Hz",
    )
    resolution_bandwidth = lb.property.float(
        key="SENS:BW",
        min=1, max=40e6, step=1e-3,
        help="resolution bandwidth",
        label="Hz",
    )

    def load_state(self, remote_filename: str):
        """revert to instrument preset state"""
        self.write(f"LOAD '{remote_filename}'")

    def fetch(self):
        """acquire measurements as configured"""
        response = self.query("FETC?")

        return [float(s) for s in response.split(",")]


@lb.property.visa_keying(remap={True: "YES", False: "NO"})
@lb.adjusted('identity_pattern', default=r'Signal generator model \#1234')
class SignalGenerator(lb.VISADevice):
    output_enabled = lb.property.bool(
        key="OUT:ENABL", help="when True, output an RF tone"
    )
    center_frequency = lb.property.float(
        key="SENS:FREQ",
        min=10e6, max=18e9, step=1e-3,
        help="input signal center frequency",
        label="Hz",
    )
    mode = lb.property.str(
        key="MODE", only=["sweep", "tone", "iq"], case=False
    )

    def trigger(self):
        """revert to instrument preset state"""
        self.write("TRIG")
