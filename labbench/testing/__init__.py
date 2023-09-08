from .sim_instruments1 import *
from .sim_instruments2 import *
from pathlib import Path

path = Path(__file__).parent
pyvisa_sim_resource = f'{path/"sim_instruments.yml"}@sim'
del Path, path
