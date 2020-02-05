import labbench as lb

class EmulatedVISADevice(lb.Device):
    """ Act as a VISA device without dispatching any visa commands
    """

    # Settings
    read_termination: lb.Unicode \
        (default='\n', help='end-of-receive termination character')

    write_termination: lb.Unicode \
        (default='\n', help='end-of-transmit termination character')

    # States
    @lb.Unicode(key='*IDN', settable=False, cache=True)
    def identity(self):
        """ identity string reported by the instrument """
        return self.__class__.__qualname__

    @lb.Unicode(key='*OPT', settable=False, cache=True)
    def options(self):
        """ options reported by the instrument """

        return ','.join(((f"{s.name}={repr(self.settings.__previous__[s.name])}" \
                          for s in self.settings)))

    @lb.Dict(key='*STB', settable=False)
    def status_byte(self):
        """ VISA status byte reported by the instrument """
        return {'error queue not empty': False,
                'questionable state': False,
                'message available': False,
                'event status flag': False,
                'service request': False,
                'master status summary': False,
                'operating': True,
                }

    def __get_by_key__(self, name, command):
        import numpy as np

        trait = self[name]

        if isinstance(trait, lb.Bool):
            if trait.remap:
                return np.random.choice(trait.remap.values())
            else:
                return np.random.choice(('TRUE', 'FALSE'))

        elif isinstance(trait, lb.Unicode):
            return 'text'
        elif isinstance(trait, lb.Float):
            return str(np.random.uniform(low=trait.min, high=trait.max))
        else:
            raise TypeError('No emulated values implemented for trait {repr(trait)}')

    def __set_by_key__(self, name, command, value):
        pass
