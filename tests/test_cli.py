import importlib

import pytest

import labbench as lb

# %% known faults, recorded in xfail-audit.md


@pytest.mark.xfail(
    strict=True,
    reason='cli/__main__.py:275 imports labbench.notebooks for --notebook, '
    'and the package has no such module',
)
def test_notebooks_module_exists():
    importlib.import_module('labbench.notebooks')


@pytest.mark.xfail(
    strict=True,
    reason='cli/__main__.py:217 calls _serialize.make_sequence_stub to reset a sequence '
    'table, and _serialize defines no such function',
)
def test_make_sequence_stub_exists():
    assert callable(lb._serialize.make_sequence_stub)
