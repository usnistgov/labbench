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
    @lb.property.str(key='*IDN', settable=False, cache=True)
    def identity(self):
        """ identity string reported by the instrument """
        return self.__class__.__qualname__

    @lb.property.str(key='*OPT', settable=False, cache=True)
    def options(self):
        """ options reported by the instrument """

        return ','.join(((f"{s.name}={repr(self.__previous__[s.name])}" \
                          for s in self.settings)))

    @lb.property.dict(key='*STB', settable=False)
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

    def get_key(self, name, command):
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

    def set_key(self, name, command, value) = pass
