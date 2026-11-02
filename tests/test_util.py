import functools

import pytest

import labbench as lb

# %% known faults, recorded in xfail-audit.md


@pytest.mark.xfail(
    strict=True,
    reason='excepthook.__call__ (util.py:466) passes the builtin type to exc_info.filter '
    'in place of etype',
)
def test_excepthook_forwards_the_exception_type(monkeypatch):
    calls = []
    monkeypatch.setattr(
        lb.util.excepthook, 'sys_excepthook', lambda *args: calls.append(args)
    )
    lb.util.excepthook()(ValueError, ValueError('boom'), None)
    assert calls[0][0] is ValueError


@pytest.mark.xfail(
    strict=True,
    reason='Call.__init__ (util.py:806) reads func.__name__ unconditionally, although '
    'Call.wrap_list_to_dict guards the same read with hasattr',
)
def test_call_accepts_a_partial():
    call = lb.util.Call(functools.partial(max, 1, 2))
    assert call() == 2
