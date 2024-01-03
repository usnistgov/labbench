import pytest
import labbench as lb
from labbench.testing import pyvisa_sim


@pytest.fixture(autouse=True, scope="module")
def setup_labbench():
    lb.visa_default_resource_manager("@sim")
    lb.util.force_full_traceback(True)


def test_adjust():
    scope = pyvisa_sim.Oscilloscope()
    specan = pyvisa_sim.SpectrumAnalyzer()

    assert scope.model != specan.model


def test_visadevice_no_resource():
    inst = lb.VISADevice()

    with pytest.raises(ConnectionError):
        inst.open()


def test_visadevice_explicit_resource():
    inst = lb.VISADevice("USB::0x1111::0x2233::0x9876::INSTR")
    with inst:
        pass


def test_visadevice_serial_resource():
    inst_explicit = lb.VISADevice("USB::0x1111::0x2233::0x9876::INSTR")
    inst_auto = lb.VISADevice("OMGBBQ58")
    with inst_auto, inst_explicit:
        assert inst_auto._identity == inst_explicit._identity


def test_subclass_explicit_resource():
    inst = pyvisa_sim.Oscilloscope("USB::0x1111::0x2233::0x9876::INSTR")
    with inst:
        pass


def test_subclass_no_resource():
    inst_explicit = lb.VISADevice("USB::0x1111::0x2233::0x9876::INSTR")
    inst_auto = pyvisa_sim.Oscilloscope()
    with inst_auto, inst_explicit:
        assert inst_auto._identity == inst_explicit._identity


def test_subclass_serial_resource():
    inst_explicit = lb.VISADevice("USB::0x1111::0x2233::0x9876::INSTR")
    inst_auto = pyvisa_sim.Oscilloscope("OMGBBQ58")
    with inst_auto, inst_explicit:
        assert inst_auto._identity == inst_explicit._identity


def test_method_access():
    inst = pyvisa_sim.Oscilloscope()

    with inst:
        inst.resolution_bandwidth(10e3, channel=2)
        inst.resolution_bandwidth(channel=1)
