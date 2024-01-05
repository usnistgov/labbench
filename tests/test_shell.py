import importlib
import labbench as lb
from labbench import paramattr as attr

flag_start = False


class Shell_Python(lb.ShellBackend):
    binary_path = attr.value.str(f"python")

    path = attr.value.str(key=None, help="path to a python script file")

    command = attr.value.str(key="-c", help="execute a python command")

    def _flag_names(self):
        return (name for name, trait in self._traits.items() if trait.key is not lb.Undefined)

    def _commandline(self, **flags):
        """Form a list of commandline argument strings for foreground
        or background calls.

        :returns: tuple of string
        """

        # validate the set of flags
        unsupported = set(flags).difference(self._flag_names())
        if len(unsupported) > 1:
            raise KeyError(f"flags {unsupported} are unsupported")

        # apply flags
        for name, value in flags.items():
            setattr(self, name, value)

        cmd = (self.binary_path,)

        # Update property trait traits with the flags
        for name in self._flag_names():
            trait = self[name]
            value = getattr(self, name)
            print(name, repr(value), repr(trait.key), repr(lb.Undefined))

            if value is None:
                continue
            elif trait.key in (None, ""):
                cmd = cmd + (value,)
            elif not isinstance(trait.key, str) and trait.key is not lb._traits.Undefined:
                raise TypeError(f"keys defined in {self} must be strings")
            else:
                cmd = cmd + (trait.key, value)
        return cmd


# class TestSettings(unittest.TestCase):
#     def test_defaults(self):
#         with Mock() as m:
#             for name, trait in m._traits.items():
#                 self.assertEqual(getattr(m, name),
#                                  trait.default, msg=f'defaults: {name}')
#
if __name__ == "__main__":
    import inspect

    lb.show_messages("debug")

    python = Shell_Python(path=r"c:\script.py", command='print("hello world")')
    print(python["resource"].key is lb.Undefined)
    print(lb.Unicode.__defaults__)
    print(inspect.signature(lb.Unicode.__init__))

    print(python._commandline())
