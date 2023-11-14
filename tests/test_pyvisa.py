import labbench as lb
import labbench.testing
from labbench.testing import pyvisa_sim, pyvisa_sim_resource


if __name__ == "__main__":
    # specify the VISA address to use the power sensor
    inst = pyvisa_sim.Oscilloscope()  # (resource='USB::0x1111::0x2233::0x9876::INSTR')
    lb.visa_default_resource_manager(pyvisa_sim_resource)

    # print the low-level actions of the code
    lb.show_messages("debug")
    lb.util.force_full_traceback(True)

    with inst:
        inst.resolution_bandwidth(10e3, channel=2)
        print(repr(inst.resolution_bandwidth(channel=1)))
