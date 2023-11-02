from .sim_instruments import *
from pathlib import Path

path = Path(__file__).parent
pyvisa_sim_resource = f'{path/"sim_instruments.yml"}@sim'
del Path, path
