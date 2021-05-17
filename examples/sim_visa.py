import labbench as lb
from pathlib import Path
import pandas as pd


yaml = Path(__file__).with_name('sim_visa.yaml')

class SimulatedPowerSupply(lb._backends.SimulatedVISADevice, yaml_source=yaml):
    voltage = lb.property.float(
        key=':VOLT:IMM:AMPL',
        min=1,
        max=6
    )

    current = lb.property.float(
        key=':CURR:IMM:AMPL',
        min=1,
        max=6
    )

    rail = lb.property.str(
        key='INST',
        only=['P6V', 'P25V', 'N25V']
    )

    output_enabled = lb.property.bool(
        key='OUTP',
        remap={True: '1', False: 0}
    )

    def fetch_trace(self):
        trace = self.query_ascii_values('TRACE?', float, container=pd.DataFrame)
        trace.columns.name = 'Trace'
        return trace

if __name__ == '__main__':
    lb.show_messages('debug')

    s = SimulatedPowerSupply(r'USB::0x1111::0x2222::0x2468::INSTR')

    with s:
        print(f'Python value: {repr(s.identity)}')
        print(f'Python value: {repr(s.options)}')
        print(f'Python value: {repr(s.current)}')
        print(f'Python value: {repr(s.rail)}')
        print(f'Python value: {repr(s.output_enabled)}')
        print(f'Python value:\n{s.fetch_trace()}')
