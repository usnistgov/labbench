---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.15.1
kernelspec:
  display_name: base
  language: python
  name: python3
---

# Device Usage
A series of short working examples here illustrate the use of labbench `Device` classes for experiment automation. The python programming interface is in the module of the same name, but it is convenient to import it as `lb` for shorthand.

```{code-cell} ipython3
import labbench as lb
lb.show_messages('debug')
```

Laboratory automation wrappers are implemented as classes derived from `lb.Device`. All of them share common basic types features designed to make their usage discoverable and convenient. The goal here is to show how to navigate these objects to get started quickly automating lab tasks. 

Wrappers for specific instruments are not included with `labbench`, only low-level python plumbing and utility functions to streamline lab automation. Specific implementation is left for other libraries.

## Overview

The `Device` class and subclasses represent in a sense only a definition with instructions for automating a specified type of lab tool. To bring these to life and control objects in the lab, the most general steps are to

1. construct an object from the class,

2. open a connection

3. use the object's attributes to perform automation tasks

Let's start with a simple automation demo for a simple 2 instrument experiment. 

```{code-cell} ipython3
import labbench as lb
import numpy as np
from sim_visa import PowerSupply, SpectrumAnalyzer

# VISA Devices take a standard address string to create a resource
spectrum_analyzer = SpectrumAnalyzer('GPIB::15::INSTR')
supply = PowerSupply('USB::0x1111::0x2222::0x2468::INSTR')

# show SCPI traffic
lb.show_messages('debug')

# `with` blocks open the devices, then closes them afterward
with supply, spectrum_analyzer: 
    print(supply.backend, supply._rm, repr(supply.read_termination))
    supply.voltage = 5
    supply.output_enabled = True

    trace_dB = 10*np.log10(spectrum_analyzer.fetch_trace())
trace_dB.plot();
```

These instruments are emulated - under the hood they are [pyvisa-sim](http://pyvisa-sim.readthedocs.io/) instruments, configured in [sim_visa.yaml], which act as simple value stores for a few fake SCPI commands and sources of "canned" arrays of data. The demo labbench Device classes that control them are implemented in [sim_visa.py] (subclassed from `lb.Device` -> `lb.VISADevice` -> `lb.SimulatedVISADevice`).

## Workflow
### Constructing objects
These Device classes (like other VISA instruments) need a VISA address in order to point to a specific instrument. To discover information about this and other available initialization parameters, use python help() or the '?' magic in ipython or jupyter:

```{code-cell} ipython3
SpectrumAnalyzer?
```

Other options are also available here, such as the transport settings `read_termination` and `read_termination`, or the number of traces to acquire in calls to `fetch_trace`.

These can also be set or changed after object construction by setting the value attributes, for example ```spectrum_analyzer.resource = 'GPIB::15::INSTR'``` or ```supply.resource = 'USB::0x1111::0x2222::0x2468::INSTR'```. The complete list of these parameters is shown under "Value Attributes", which also lists read-only values that can't be changed and are not constructor arguments.

### Opening device connections
In automation scripts, it is good practice to use a context block (that `with` statement) to open connections. This ensures all of the devices open and close together, even when exceptions are raised.

For interactive use on the python/ipython/jupyter prompt, this is less convenient. For this purpose, device objects also expose explicit `open` and `close` methods. As an example, a simple check for instrument response to automation could look like this, 

```python
>>> supply.open()
>>> print(supply.output_enabled)
False
>>> # (...look at the instrument to verify output is disabled)
>>> supply.output_enabled = True
>>> # (...verify instrument output is enabled)
```

This type of exploration is a good way to learn the capabilities of a device interactively.

### Automating with open devices

Python's introspection tools give more opportunities to discover the API exposed by a device object. This is important because the methods and other attributes vary from one type of Device class to another. The below uses `dir` to show the list of all _public_ attributes (those that don't start with `'_'`).

```{code-cell} ipython3
# filter by name
attrs = [
    name
    for name in dir(SpectrumAnalyzer)
    if not name.startswith('_')
]

print(f'public attributes of SpectrumAnalyzer: {attrs}\n')

# discover the 'query' method common to VISA all devices
SpectrumAnalyzer.query?
```

Trait attributes that cast to python types with validation are definitions in classes, but become interactive values in device objects:

```{code-cell} ipython3
print(f'class: SpectrumAnalyzer.sweeps == {SpectrumAnalyzer.sweeps}')
print(f'object: spectrum_analyzer.sweeps == {signal_analyzer.sweeps}')
```

```{code-cell} ipython3
signal_analyzer.open
SpectrumAnalyzer.open
```

## Generalizing from the example
Different subclasses expose different method functions and attribute variables to wrap the underling low-level API. Still, several characteristics are standardized:
- connection management through `with` block or `open`/`close` methods
- an `isopen` property to indicate connection status
- `resource` is accepted by the constructor, and may be changed afterward as a class attribute
- hooks are available for data loggers and UIs to observe automation calls


Device subclasses for different types of instruments and software differ in
- the types of resource and configuration information
- the specific resource of the class provided to control the device

+++

This gets more complicated when handling multiple devices, because connection failures leave a combination of open and closed:

```{code-cell} ipython3
try:
    base.open()
    visa.open() # fails because its resource doesn't exist on the host
    
    # we don't get this far after visa.open() raises an exception
    print("doing useful automation here")
    visa.close()
    base.close()
except:    
    # we're left with a mixture of connection states
    assert base.isopen==True and visa.isopen==False

    # ...so we have to clean up the stray connection manually :(
    base.close()
```

Context management is easier and more clear. Everything inside the `with` block executes only if all devices open successfully, and ensures cleanup so that all devices are closed afterward.

```{code-cell} ipython3
try:
    with base, visa: # does both base.open() and visa.open()
        print('we never get in here, because visa.open() fails!')
except:
    # context management ensured a base.close() after visa.open() failed, 
    assert base.isopen==False and visa.isopen==False
```
data logging, type checking,and numerical bounds validation. 

These features are common to all `Device` classes (and derived classes). To get started, provide  by minimum working examples. Examples will use  we'll look into the more specialized capabilities provided by other `Device` subclasses included `labbench` for often-used backend APIs like serial and VISA.

### Example
Here are very fake functions that just use `time.sleep` to block. They simulate longer instrument calls (such as triggering or acquisition) that take some time to complete.

Notice that `do_something_3` takes 3 arguments (and returns them), and that `do_something_4` raises an exception.

```{code-cell} ipython3
import labbench as lb
```

Here is the simplest example, where we call functions `do_something_1` and `do_something_2` that take no arguments and raise no exceptions:

```{code-cell} ipython3
from labbench import concurrently

results = concurrently(do_something_1, do_something_2)
results
```

```{code-cell} ipython3
results
```

```{code-cell} ipython3
do_something_1.__name__
```

We can also pass functions by wrapping the functions in `Call()`, which is a class designed for this purpose:

```{code-cell} ipython3
from labbench import concurrently, Call

results = concurrently(do_something_1, Call(do_something_3, 1,2,c=3))
results
```

More than one of the functions running concurrently may raise exceptions. Tracebacks print to the screen, and by default `ConcurrentException` is also raised:

```{code-cell} ipython3
from labbench import concurrently, Call

results = concurrently(do_something_4, do_something_5)
results
```

the `catch` flag changes concurrent exception handling behavior to return values of functions that did not raise exceptions (instead of raising `ConcurrentException`). The return dictionary only includes keys for functions that did not raise exceptions.

```{code-cell} ipython3
from labbench import concurrently, Call

results = concurrently(do_something_4, do_something_1, catch=True)
results
```
