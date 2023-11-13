import labbench as lb
from labbench import paramattr as param


class EmulatedVISAPropertyAdapter(lb.VISAPropertyAdapter):
    def get(self, device, key, trait):
        import numpy as np

        if trait.type is bool:
            if len(self.remap) > 0:
                return np.random.choice(self.value_map.values())
            else:
                return np.random.choice(("TRUE", "FALSE"))

        elif trait.type is str:
            return "text"

        elif trait.type is float:
            return str(np.random.uniform(low=trait.min, high=trait.max))

        else:
            raise TypeError("No emulated values implemented for trait {repr(trait)}")

    def set(self, device, key, value, trait):
        pass


@EmulatedVISAPropertyAdapter
class EmulatedVISADevice(lb.Device):
    """Act as a VISA device without dispatching any visa keys"""

    # Settings
    read_termination = param.value.str("\n", help="end-of-receive termination character")
    write_termination = param.value.str("\n", help="end-of-transmit termination character")

    # States
    @param.property.str(key="*IDN", sets=False, cache=True)
    def identity(self):
        """identity string reported by the instrument"""
        return self.__class__.__qualname__

    @param.property.str(key="*OPT", sets=False, cache=True)
    def options(self):
        """options reported by the instrument"""

        param_strs = (f"{s}={getattr(self,s)}" for s in self._value_attrs)
        return ",".join(param_strs)

    @param.property.dict(key="*STB", sets=False)
    def status_byte(self):
        """VISA status byte reported by the instrument"""
        return {
            "error queue not empty": False,
            "questionable state": False,
            "message available": False,
            "event status flag": False,
            "service request": False,
            "master status summary": False,
            "operating": True,
        }
