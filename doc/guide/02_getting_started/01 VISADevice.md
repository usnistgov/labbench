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

# VISA automation quick start

Labbench includes several features to organize and streamline [VISA](https://en.wikipedia.org/wiki/Virtual_instrument_software_architecture) instrument automation through [`pyvisa`](http://pyvisa.readthedocs.org/). 


<!-- {py:class}`labbench.Device` is the root object used to define and implement automation with a lower-level driver. Its purpose is to encapsulate all python data and methods for a specific laboratory device or software. -->

<!-- This section demonstrates usage through a lean working example. The {py:class}`labbench.Device` design pattern for a specific device starts by defining a subclass, often from one of the backend subclasses that has been specialized for a low-level driver module (, shell commands, etc.). Doing this has several advantages: -->

## The labbench pyvisa backend
Generic VISA automation functions are encapsulated in a general-purpose object type: {py:class}`labbench.VISADevice`.
This brings several benefits compared to passing message strings directly into `pyvisa` objects:

* multi-threaded connection management
* automatic coercion between python types and low-level/over-the-wire data types
* support for [automatic logging](./03%20data%20logging.md) of instrument configuration parameters and metadata for 
* constraints on instrument parameters

When available, other more specialized classes (subclasses) can tailor `VISADevice` to expose pythonic automation functions tailored to a specific instruments. However, guidance that follows for `VISADevice` can also be applied to its subclasses.

## Resource managers
Labbench supports the use of any `pyvisa` [resource manager backend](https://pyvisa.readthedocs.io/en/1.14.1/introduction/configuring.html).

* The default is {py:module}`pyvisa-py` (`"@py"``), which is installed as a dependency
* A special case driver for demonstration and testing is `@sim`.
  Specialized `VISADevice` objects for the simulated instruments are provided in {py:module}`labbench.testing.pyvisa_sim`

The following examples use some pre-defined simulated VISA instruments to illustrate workflow. These are exposed through the {py:mod}`pyvisa` "@sim" resource manager.

## Discover connected instruments 
The labbench command line tool provides device discovery based on {py:function}`labbench.visa_probe_devices`. The following 

```{code-cell} ipython3
# remove the ! when running in a command prompt
!labbench visa-probe @sim 
```

This probes instruments by attempting `*IDN?` queries on the resource strings discovered by the resource manager. The resulting responses are used to determine valid connection parameters (`read_termination` and `write_termination`). When successful, identifying characteristics (make, model, serial number, and revision) are shown, together with explicit syntax to create a generic instrument control object.

For `@py` backends, information about missing drivers is also shown when they limit the scope of the discovery.


## Resource names
The `VISADevice` resource argument specifies the information required to open a connection to the instrument. These can include:

* Any [pyvisa resource name](https://pyvisa.readthedocs.io/en/1.8/names.html)
* The serial number of a connected instrument (for instruments discoverable through {py:func}`labbench.visa_probe_devices`).
For subclasses that define `make` and/or `model`, and these together match exactly one connected instrument, the `resource` argument can also be omitted.

## Connection with a VISADevice
At its simplest, a `VISADevice` object exposes the [communication capabilities of pyvisa resource](https://pyvisa.readthedocs.io/en/1.14.1/introduction/rvalues.html). Starting from the power sensor in our VISA probe:

```{code-cell} ipython3
import labbench as lb
lb.visa_default_resource_manager('@sim')

inst = lb.VISADevice('USB0::0x1111::0x2222::0x1234::0::INSTR', write_termination='\r\n')

with inst:
    print(inst.query('*IDN?'))
```

The backend connection remains open for VISA communication for code executing in `with` block. It is closed on exit, even in the event of an exception

## Using specialized wrappers
Tailored instrument classes provide more convenient pythonic interaction. One example is provided for our
simulated instrument in `labbench`. However, many more are available in external libraries like
[ssmdevices](https://github.com/usnistgov/ssmdevices).

```{code-cell} ipython3
# use a pyvisa-sim simulated VISA instrument for the demo
from labbench.testing.pyvisa_sim import PowerSensor
lb.visa_default_resource_manager('@sim')

# watch the low-level write and query actions
lb.show_messages('debug')

# No resource name required if it's the only connected match for its make and model
with PowerSensor() as sensor:   
    # apply the instrument preset state
    sensor.preset()

    # set acquisition parameters on the power sensor
    sensor.frequency = 1e9
    sensor.measurement_rate = "FAST"
    sensor.trigger_count = 200
    sensor.sweep_aperture = 20e-6
    sensor.initiate_continuous = True

    # retreive the 200 measurement samples
    power = sensor.fetch()
```

The use of debug messages serve as validation of the anticipated SCPI messages and responses. These are helpful when
familiarizing with `labbench` after working directly with the command strings, or when developing wrappers of your own.

<!-- * Attributes that were defined with `attr.property` in `PowerSensor` become interactive for instrument automation in `sensor`. This means that assigning to `sensor.frequency`, `sensor.measurement_rate` trigger VISA writes to set these parameters on the instrument. Similarly, _getting_ each these attributes of sensor triggers VISA queries. The specific SCPI commands are visible here in the debug messages. -->

<!-- ```{admonition} Getting started with a new instrument
Some trial and error is often needed, and it is best to iterate in small steps:
1. Establish a connection to the instrument, referring to the documentation for the backend (for example, the [pyvisa communication documentation](https://pyvisa.readthedocs.io/en/latest/introduction/communication.html))
2. Verify basic communication with the instrument using very simple commands
3. Refer to the instrument programming manual to add one command at a time, testing each by verifying on the instrument itself
``` -->