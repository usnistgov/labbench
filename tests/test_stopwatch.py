import labbench as lb

@lb.stopwatch('decorated delay func')
def delay_func(delay=0.3, fail=False):
    lb.sleep(delay)
    if fail:
        1//0

with lb.stopwatch('context ok'):
    lb.sleep(0.2)

try:
    with lb.stopwatch('context except'):
        1//0
except ZeroDivisionError:
    pass

with lb.stopwatch('context ok'):
    delay_func()

try:
    delay_func(fail=True)
except ZeroDivisionError:
    pass

