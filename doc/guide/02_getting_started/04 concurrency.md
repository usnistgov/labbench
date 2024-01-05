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

# Simplified Concurrency
`labbench` includes simplified concurrency support for this kind of I/O-constrained operations like waiting for instruments to perform long operations. It is not suited for parallelizing CPU-intensive tasks because the operations share a single process on one CPU core, instead of multiprocessing, which may be able to spread operations across multiple CPU cores.

Here are simple Device objects that use {py:func}`time.sleep` as a stand-in for long-running remote operations:

```{code-cell} ipython3
import labbench as lb

# a placeholder for long-running remote operations
from time import sleep

class Device1(lb.VISADevice):
    def open(self):
        # open() is called on connection to the device
        with lb.stopwatch('Device1 connect'):
            sleep(1)
            
    def fetch(self):
        with lb.stopwatch('Device1 fetch'):
            sleep(1)
            return 5

class Device2(lb.VISADevice):
    def open(self):
        # open() is called on connection to the device
        with lb.stopwatch('Device2 connect'):
            sleep(2)
            
    def acquire(self):
        with lb.stopwatch('Device2 acquire'):
            sleep(2)
            return None
```

Suppose we need to both `fetch` from `Device1` and `acquire` in `Device2`, and that the time-sequencing is not important. One approach is to simply call one and then the other:

```{code-cell} ipython3
from labbench import testing
from time import perf_counter

# allow simulated connections to the specified VISA devices
lb.visa_default_resource_manager(testing.pyvisa_sim_resource)

d1 = Device1('TCPIP::localhost::INSTR')
d2 = Device2('USB::0x1111::0x2222::0x1234::INSTR')

t0 = perf_counter()
with d1, d2:
    print(f'connect both (total time): {perf_counter()-t0:0.1f} s')
    with lb.stopwatch('both Device1.fetch and Device2.acquire (total time)'):
        d1.fetch()
        d2.acquire()
```

For each of the connection and fetch/acquire operations, the total duration was about 3 seconds, because the 1 and 2 second operations are executed sequentially.

Suppose that we want to perform each of the open and fetch/acquire operations concurrently. Enter {py:func}`labbench.concurrently`:

```{code-cell} ipython3
from labbench import testing
from time import perf_counter

# allow simulated connections to the specified VISA devices
lb.visa_default_resource_manager(testing.pyvisa_sim_resource)

d1 = Device1('TCPIP::localhost::INSTR')
d2 = Device2('USB::0x1111::0x2222::0x1234::INSTR')

t0 = perf_counter()
with lb.concurrently(d1, d2):
    print(f'connect both (total time): {perf_counter()-t0:0.1f} s')
    with lb.stopwatch('both Device1.fetch and Device2.acquire (total time)'):
        ret = lb.concurrently(d1.fetch, d2.acquire)
        
print('Return value: ', ret)
```

Each call to {py:func}`labbench.concurrently` executes each callable in separate threads, and returns after the longest-running call.
* As a result, in this example, for each of the `open` and `fetch`/`acquire`, the total time is reduced from 3 s to 2 s.
* The return values of threaded calls are packaged into a dictionary for each call that does not return `None`.
The syntax is a little more involved when you want to pass in arguments to multiple callables. For information on doing this, see the [detailed instructions](../03_detailed_usage/05_concurrency).
