import labbench as lb
from pathlib import Path
import pandas as pd


yaml = Path(__file__).with_name("sim_visa.yaml")


class PowerSupply(lb._backends.SimulatedVISADevice, yaml_source=yaml):
    """wrapper for a fake PowerSupply VISA device"""

    voltage = lb.property.float(
        key=":VOLT:IMM:AMPL",
        min=1,
        max=6,
        help="output voltage setting",
    )

    current = lb.property.float(
        key=":CURR:IMM:AMPL", min=1, max=6, help="output current setting"
    )

    rail = lb.property.str(
        key="INST", only=["P6V", "P25V", "N25V"], help="which output"
    )

    output_enabled = lb.property.bool(
        key="OUTP",
        remap={True: "1", False: "0"},
        help="supply output control",
    )

    def fetch_trace(self):
        trace = self.query_ascii_values("TRACE?", float, container=pd.DataFrame)
        trace.columns = ["Trace"]
        return trace


class SpectrumAnalyzer(lb._backends.SimulatedVISADevice, yaml_source=yaml):
    """a fake Spectrum Analyzer that returns fixed trace data"""

    frequency = lb.property.float(
        key=":FREQ",
        min=10e6,
        max=18e9,
        help="center frequency",
    )

    sweeps = lb.value.int(
        1,
        min=1,
        help="number of traces to acquire",
    )

    def fetch_trace(self):
        trace = self.query_ascii_values("TRACE?", float, container=pd.DataFrame)

        trace.columns = ["Trace0"]

        for i in range(self.sweeps - 1):
            # 'sweep'
            trace[f"Trace{i}"] = trace["Trace0"]

        return trace


if __name__ == "__main__":
    lb.show_messages("debug")

    ps = PowerSupply(r"USB::0x1111::0x2222::0x2468::INSTR")
    sa = SpectrumAnalyzer(r"GPIB::15::INSTR")

    with ps, sa:
        print(f"Python value: {repr(ps.identity)}")
        print(f"Python value: {repr(ps.options)}")
        print(f"Python value: {repr(ps.current)}")
        print(f"Python value: {repr(ps.rail)}")
        print(f"Python value: {repr(ps.output_enabled)}")
        print(f"Python value:\n{ps.fetch_trace()}")

        print(f"Python value: {repr(sa.frequency)}")
        print(f"Python value:\n{sa.fetch_trace()}")
