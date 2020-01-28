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
# BY PERSONS OR PROPERTY OR OTHERWISE, AND WHETHER OR NOT LOSS WAS SUSTAINED
# FROM, OR AROSE OUT OF THE RESULTS OF, OR USE OF, THE SOFTWARE OR SERVICES
# PROVIDED HEREUNDER. Distributions of NIST software should also include
# copyright and licensing statements of any third-party software that are
# legally bundled with the code in compliance with the conditions of those
# licenses.

from .util import sequentially,concurrently
from .data import LogAggregator, RelationalTableLogger
from .core import Device
from .host import Host, Email


__all__ = ['Testbed']


class Testbed:
    """ A collection of Device instances, database managers, and methods that
        implement an automated experiment.

        Use a `with` block with the testbed instance to open everything
        at once like so::

            with Testbed() as testbed:
                # use the testbed here
                pass

        or optionally open only a subset of devices like this::

            testbed = Testbed()
            with testbed.dev1, testbed.dev2:
                # use the testbed.dev1 and testbed.dev2 here
                pass

        Make your own subclass of Testbed with a custom `make`
        method to define the Device or database manager instances, and
        a custom `startup` method to implement custom code to set up the
        testbed after all Device instances are open.
    """

    # Specify any context manager types to open before others
    # and their order
    enter_first = Email, LogAggregator, Host

    def __init__(self, config=None, concurrent=True):
        self.config = config
        attrs_start = dir(self)
        self.make()

        # Find the objects
        everything = dict(self.__class__.__dict__, **self.__dict__)
        cms = dict([(a, o) for a, o in everything.items()\
                        if not a.startswith('_') and hasattr(o, '__enter__')])

        self.__managed_contexts = dict(cms)

        # Pull any objects of types listed by self.enter_first, in the
        # order of (1) the types listed in self.enter_first, then (2) the order
        # they appear in objs
        first_contexts = dict()
        for cls in self.enter_first:
            for attr, obj in dict(cms).items():
                if isinstance(obj, cls):
                    first_contexts[attr] = cms.pop(attr)

        other_contexts = cms

        # Enforce the ordering set by self.enter_first
        if concurrent:
            # Any remaining context managers will be run concurrently if concurrent=True            
            contexts = dict(first_contexts, others=concurrently(name=f'',
                                                                **other_contexts))
        else:
            # Otherwise, run them sequentially
            contexts = dict(first_contexts, **other_contexts)

        self.__cm = sequentially(name=f'{repr(self)} connections',
                                 **contexts)

        for obj in self.__managed_contexts.values():
            if isinstance(obj, RelationalTableLogger):
                devices = self._devices()
                obj.observe_states(devices)
                obj.observe_settings(devices)
                break


    def get_managed_contexts(self):
        return dict(self.__managed_contexts)

    def _devices(self, recursive=True):
        owners = []

        for name, obj in self.__managed_contexts.items():
            if isinstance(obj, Device):
                owners += [obj]
            elif recursive and isinstance(obj, Testbed):
                owners += obj._trait_owners(recursive=True)

        return owners


    def __enter__(self):
        self.__cm.__enter__()
        self.startup()
        return self
    
    def __exit__(self, *args):
        try:
            self.cleanup()
        except BaseException as e:
            ex = e
        else:
            ex = None
        finally:
            ret = self.__cm.__exit__(*args)
            if ex is None:
                self.after()
            else:
                raise ex
            return ret
        
    def __repr__(self):
        return f'{self.__class__.__qualname__}()'

    def make(self):
        """ Implement this method in a subclass of Testbed. It should
            set drivers as attributes of the Testbed instance, for example::

                self.dev1 = MyDevice()

            This is called automatically when when the testbed class
            is instantiated.
        """
        pass

    def startup(self):
        """ This is called automatically after open if the testbed is
            opened using the `with` statement block.

            Implement any custom code here in Testbed subclasses to
            implement startup of the testbed given open Device
            instances.
        """
        pass

    def cleanup(self):
        """ This is called automatically immediately before close if the
            testbed is opened using the `with` context block.
            
            This is called even if the `with` context is left as a result of
            an exception.

            Implement any custom code here in Testbed subclasses to
            implement teardown of the testbed given open Device
            instances.
        """
        pass
    
    def after(self):
        """ This is called automatically after open, if no exceptions
            were raised.
        """
        pass
