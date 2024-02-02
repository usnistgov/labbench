import numpy as np
import pandas as pd
import pytest

import labbench as lb
from labbench.testing import pyvisa_sim

# TODO: pull this in from the yml file
SPECAN_TRACE = pd.Series("-52.617,-52.373,-52.724,-51.893,-52.27,-52.047,-53.059,-52.053,-52.426,-52.343,-52.228,-52.976,-52.186,-53.0,-51.894,-53.18,-51.96,-52.326,-52.492,-52.871,-52.41,-53.111,-53.199,-52.907,-52.791,-52.68,-51.63,-51.679,-21.743,-52.613,-52.108,-53.138,-52.014,-52.289,-52.235,-52.26,-53.135,-52.503,-52.201,-51.633,-51.933,-52.82,-52.287,-52.594,-51.89,-52.371,-52.068,-51.888,-53.145,-53.085,-52.392,-52.064,-51.688,-52.188,-52.211,-52.226,-52.841,-51.951,-51.573,-51.521,-52.115,-52.302,-52.958,-52.503,-52.32,-52.81,-52.357,-51.729,-52.956,-52.849,-51.883,-51.505,-52.027,-52.234,-52.092,-51.446,-52.798,-51.601,-52.14,-51.477,-52.614,-52.291,-52.532,-52.861,-51.814,-51.821,-52.997,-53.184,-51.761,-53.052,-51.612,-52.876,-52.013,-52.252,-52.059,-52.806,-52.474,-51.689,-52.606,-51.924,-51.964,-51.601,-52.815,-53.172,-52.183,-53.071,-52.763,-52.999,-52.595,-52.463,-52.48,-52.701,-52.337,-51.778,-52.039,-51.493,-51.591,-51.654,-51.525,-52.925,-51.531,-53.169,-52.997,-52.519,-52.298,-52.078,-52.547,-51.518,-51.589,-51.567,-51.502,-51.984,-52.215,-52.681,-51.468,-53.197,-53.007,-51.929,-52.465,-53.132,-52.073,-51.75,-52.8,-52.054,-52.493,-51.605,-53.026,-52.28,-52.331,-52.109,-51.889,-52.878,-51.874,-51.801,-52.031,-52.625,-51.84,-53.029,-52.431,-51.655,-52.51,-52.431,-52.165,-52.009,-51.973,-53.042,-52.632,-51.754,-52.637,-51.757,-51.9,-52.775,-52.49,-52.022,-52.151,-52.05,-51.867,-52.494,-53.014,-52.14,-53.036,-51.799,-51.848,-51.996,-52.254,-52.75,-51.492,-51.755,-52.494,-53.193,-53.114,-53.028,-52.898,-52.992,-53.127,-51.752,-53.065,-52.585,-51.861,-51.596".split(',')).astype('float32').values

@pytest.fixture(autouse=True, scope='module')
def setup_labbench():
    lb.visa_default_resource_manager('@sim-labbench')
    lb.util.force_full_traceback(True)

def test_adjust():
    scope = pyvisa_sim.Oscilloscope()
    specan = pyvisa_sim.SpectrumAnalyzer()

    assert scope.model != specan.model

def test_method_calls():
    specan = pyvisa_sim.SpectrumAnalyzer()

    with specan:
        specan.trigger()

        values = specan.fetch().values
        assert np.allclose(values, SPECAN_TRACE)

        values = specan.fetch_ascii_values().values
        assert np.allclose(values, SPECAN_TRACE)
def test_visadevice_no_resource():
    inst = lb.VISADevice()

    with pytest.raises(ConnectionError):
        inst.open()

def test_visadevice_explicit_resource():
    inst = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
    with inst:
        pass

def test_visadevice_serial_resource():
    inst_explicit = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
    inst_auto = lb.VISADevice('OMGBBQ58')
    with inst_auto, inst_explicit:
        assert inst_auto._identity == inst_explicit._identity


def test_subclass_explicit_resource():
    inst = pyvisa_sim.Oscilloscope('USB::0x1111::0x2233::0x9876::INSTR')
    with inst:
        pass


def test_subclass_no_resource():
    inst_explicit = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
    inst_auto = pyvisa_sim.Oscilloscope()
    with inst_auto, inst_explicit:
        assert inst_auto._identity == inst_explicit._identity


def test_subclass_serial_resource():
    inst_explicit = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
    inst_auto = pyvisa_sim.Oscilloscope('OMGBBQ58')
    with inst_auto, inst_explicit:
        assert inst_auto._identity == inst_explicit._identity


def test_method_access():
    inst = pyvisa_sim.Oscilloscope()

    with inst:
        inst.resolution_bandwidth(10e3, channel=2)
        inst.resolution_bandwidth(channel=1)
