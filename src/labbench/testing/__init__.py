from pathlib import Path

path = Path(__file__).parent
pyvisa_sim_resource = f'{path/"pyvisa_sim.yml"}@sim'
del Path, path
