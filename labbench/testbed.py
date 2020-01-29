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
from .core import Device, InTestbed
from .host import Host, Email
from functools import wraps

__all__ = ['Testbed', 'Steps', 'InTestbed']


class Testbed:
    """ A Testbed is a container for devices, data managers, and test steps.

        The Testbed object provides connection management for
        all devices and data managers for `with` block::

            with Testbed() as testbed:
                # use the testbed here
                pass

        For functional validation, it is also possible to open only a subset
        of devices like this::

            testbed = Testbed()
            with testbed.dev1, testbed.dev2:
                # use the testbed.dev1 and testbed.dev2 here
                pass

        The following syntax creates a new Testbed class for an
        experiment:

            import labbench as lb

            class MyTestbed(lb.Testbed):
                db = lb.SQLiteManager()
                sa = MySpectrumAnalyzer()

                spectrogram = Spectrogram(db=db, sa=sa)

        method to define the Device or database manager instances, and
        a custom `startup` method to implement custom code to set up the
        testbed after all Device instances are open.
    """

    __contexts__ = {}
    __cm = {}
    
    # Specify context manager types to open before others
    # and their order
    enter_first = Email, LogAggregator, Host

    def __init_subclass__(cls, concurrent=True):
        cls.__contexts__ = dict(cls.__contexts__)
        cms = dict(cls.__contexts__)

        # Pull any objects of types listed by self.enter_first, in the
        # order of (1) the types listed in self.enter_first, then (2) the order
        # they appear in objs
        first_contexts = dict()
        for cls in cls.enter_first:
            for attr, obj in dict(cms).items():
                if isinstance(obj, cls):
                    first_contexts[attr] = cms.pop(attr)

        other_contexts = cms

        # Enforce the ordering set by self.enter_first
        if concurrent:
            # Any remaining context managers will be run concurrently if concurrent=True
            others=concurrently(name=f'', **other_contexts)
            contexts = dict(first_contexts, others=others)
        else:
            # Otherwise, run them sequentially
            contexts = dict(first_contexts, **other_contexts)

        cls.__cm = sequentially(name=f'{cls.__qualname__} connections',
                                 **contexts)

    def __init__(self, config=None):
        self.config = config

        for name, context in self.__contexts__.items():
            context.__init_owner__(self)

        self.make()

    def _contexts(self):
        return dict(self.__contexts__)

    def _devices(self, recursive=True):
        owners = []

        for name, obj in self.__contexts__.items():
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


class Steps(InTestbed):
    """ Subclass this to define experimental procedures for groups of Devices in a Testbed.
    """
    __annotations__ = dict()
    __steps__ = dict()

    def __init_subclass__(cls):
        # By introspection, identify the methods that define test steps
        cls.__steps__ = dict(((k,v) for k,v in cls.__dict__ if callable(v) and k not in Steps.__dict__))

        # Include annotations from parent classes
        cls.__annotations__ = dict(super().__annotations__, **cls.__annotations__)
        cls.__init__.__annotations__ = cls.__annotations__

        # Sentinel values for annotations not in this class
        for name in cls.__annotations__:
            if name not in cls.__dict__:
                setattr(cls, name, None)

    def __init__(self, **devices):
        # a fresh mapping to modify without changing the parent
        devices = dict(devices)

        # Set attributes in self
        for name, devtype in self.__annotations__:
            try:
                dev = devices.pop(name)
            except KeyError:
                raise KeyError(f"{self.__class__.__qualname__} is missing required argument")
            if not isinstance(dev, devtype):
                msg = f"argument '{name}' must be an instance of '{devtype.__qualname__}'"
                raise AttributeError(msg)
            setattr(self, name, dev)

        # If there are remaining unsupported devices, raise an exception
        if len(devices) > 0:
            raise ValueError(f"{tuple(devices.keys())} are invalid arguments")

    def __getattribute__(self, name):
        """ Add debug messages to class method calls
        """
        obj = object.__getattribute__(cls, name)

        if name in object.__getattribute__(cls, '__steps__'):
            # TODO: Ensure required devices are connected before executing
            @wraps(obj)
            def wrapped(*args, **kws):
                name = self.__name__ + '.' + obj.__name__
                lb.logger.debug(f"starting step {name}")
                with lb.stopwatch(f"step {name}"):
                    return obj(*args, **kws)
            return wrapped
        else:
            return obj

    def __getitem__(self, item):
        return self.__steps__[item]

    def __len__(self):
        return len(self.__steps__)

    def __iter__(self):
        return iter(self.__steps__)

    def items(self):
        return self.__steps__.items()

    def values(self):
        return self.__steps__.values()

    def keys(self):
        return self.__steps__.keys()