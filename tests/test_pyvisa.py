import labbench as lb
from labbench.testing import pyvisa_sim
import unittest


class TestPyVISA(unittest.TestCase):
    def __init__(self, methodName: str):
        super().__init__(methodName)
        lb.visa_default_resource_manager('@sim')
        lb.util.force_full_traceback(True)

    def test_adjust(self):
        scope = pyvisa_sim.Oscilloscope()
        specan = pyvisa_sim.SpectrumAnalyzer()

        self.assertNotEqual(scope.model, specan.model)

    def test_visadevice_no_resource(self):
        inst = lb.VISADevice()

        with self.assertRaises(ConnectionError):
            inst.open()

    def test_visadevice_explicit_resource(self):
        inst = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
        with inst:
            pass

    def test_visadevice_serial_resource(self):
        inst_explicit = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
        inst_auto = lb.VISADevice('OMGBBQ58')
        with inst_auto, inst_explicit:
            self.assertEqual(inst_auto._identity, inst_explicit._identity)

    def test_subclass_explicit_resource(self):
        inst = pyvisa_sim.Oscilloscope('USB::0x1111::0x2233::0x9876::INSTR')
        with inst:
            pass

    def test_subclass_no_resource(self):
        inst_explicit = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
        inst_auto = pyvisa_sim.Oscilloscope()
        with inst_auto, inst_explicit:
            self.assertEqual(inst_auto._identity, inst_explicit._identity)

    def test_subclass_serial_resource(self):
        inst_explicit = lb.VISADevice('USB::0x1111::0x2233::0x9876::INSTR')
        inst_auto = pyvisa_sim.Oscilloscope('OMGBBQ58')
        with inst_auto, inst_explicit:
            self.assertEqual(inst_auto._identity, inst_explicit._identity)

    def test_method_access(self):
        inst = pyvisa_sim.Oscilloscope()

        with inst:
            inst.resolution_bandwidth(10e3, channel=2)
            inst.resolution_bandwidth(channel=1)


if __name__ == "__main__":
    scope = pyvisa_sim.Oscilloscope()
    specan = pyvisa_sim.SpectrumAnalyzer()

    print(scope.make, scope.model)
    print(specan.make, specan.model)
    unittest.main()

    # with inst:
    #     inst.resolution_bandwidth(10e3, channel=2)
    #     print(repr(inst.resolution_bandwidth(channel=1)))
