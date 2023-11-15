# This software was developed by employees of the National Institute of
# Standards and Technology (NIST), an agency of the Federal Government.
# Pursuant to title 17 United States Code Section 105, works of NIST employees
# are not subject to copyright protection in the United States and are
# considered to be in the public domain. Permission to freely use, copy,
# modify, and distribute this software and its documentation without fee is
# hereby granted, provided that this notice and disclaimer of warranty appears
# in all copies.
#
# THE SOFTWARE IS PROVIDED 'AS IS' WITHOUT ANY WARRANTY OF ANY KIND, EITHER
# EXPRESSED, IMPLIED, OR STATUTORY, INCLUDING, BUT NOT LIMITED TO, ANY WARRANTY
# THAT THE SOFTWARE WILL CONFORM TO SPECIFICATIONS, ANY IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND FREEDOM FROM
# INFRINGEMENT, AND ANY WARRANTY THAT THE DOCUMENTATION WILL CONFORM TO THE
# SOFTWARE, OR ANY WARRANTY THAT THE SOFTWARE WILL BE ERROR FREE. IN NO EVENT
# SHALL NIST BE LIABLE FOR ANY DAMAGES, INCLUDING, BUT NOT LIMITED TO, DIRECT,
# INDIRECT, SPECIAL OR CONSEQUENTIAL DAMAGES, ARISING OUT OF, RESULTING FROM,
# OR IN ANY WAY CONNECTED WITH THIS SOFTWARE, WHETHER OR NOT BASED UPON
# WARRANTY, CONTRACT, TORT, OR OTHERWISE, WHETHER OR NOT INJURY WAS SUSTAINED
# BY PERSONS OR Decorator OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

import unittest
import importlib
import sys
import labbench as lb
from labbench import paramattr as attr

lb = importlib.reload(lb)

flag_start = False


class Shell_Python(lb.ShellBackend):
    binary_path = attr.value.str(f"python")

    path = attr.value.str(key=None, help="path to a python script file")

    command = attr.value.str(key="-c", help="execute a python command")

    def _flag_names(self):
        return (
            name
            for name, trait in self._traits.items()
            if trait.key is not lb.Undefined
        )

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
            elif (
                not isinstance(trait.key, str) and trait.key is not lb._traits.Undefined
            ):
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
