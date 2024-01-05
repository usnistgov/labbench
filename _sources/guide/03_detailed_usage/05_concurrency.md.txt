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

+++

Here are very fake functions that just use `time.sleep` to block. They simulate longer instrument calls (such as triggering or acquisition) that take some time to complete.

Notice that `do_something_3` takes 3 arguments (and returns them), and that `do_something_4` raises an exception.

```{code-cell}
import time

def do_something_1 ():
    print('start 1')
    time.sleep(1)
    print('end 1')
    return 1

def do_something_2 ():
    print('start 2')
    time.sleep(2)
    print('end 2')
    return 2

def do_something_3 (a,b,c):
    print('start 3')
    time.sleep(2.5)
    print('end 3')
    return a,b,c 

def do_something_4 ():
    print('start 4')
    time.sleep(3)
    raise ValueError('I had an error')
    print('end 4')
    return 4

def do_something_5 ():
    print('start 5')
    time.sleep(4)
    raise IndexError('I had a different error')
    print('end 5')
    return 4
```

Here is the simplest example, where we call functions `do_something_1` and `do_something_2` that take no arguments and raise no exceptions:

```{code-cell}
import labbench as lb

results = lb.concurrently(do_something_1, do_something_2)
print(f'results: {results}')
```

We can also pass functions by wrapping the functions in `Call()`, which is a class designed for this purpose:

```{code-cell}
results = lb.concurrently(do_something_1, lb.Call(do_something_3, 1,2,c=3))
results
```

More than one of the functions running concurrently may raise exceptions. Tracebacks print to the screen, and by default `ConcurrentException` is also raised:

```{code-cell}
from labbench import concurrently, Call

results = concurrently(do_something_4, do_something_5)
results
```

the `catch` flag changes concurrent exception handling behavior to return values of functions that did not raise exceptions (instead of raising `ConcurrentException`). The return dictionary only includes keys for functions that did not raise exceptions.

```{code-cell}
from labbench import concurrently, Call

results = concurrently(do_something_4, do_something_1, catch=True)
results
```
