# Audit of strict xfails

Every xfail in this repository is `strict=True` and is written against the behavior
the code was meant to have, so the list doubles as the known-defect registry (see
AGENTS.md, "Known gaps are recorded as strict xfails"). This document records, for
each open item, why the failing test describes a defect rather than a wrong
expectation, and how much it matters to the way the library is used.

Items are numbered in the order they were found. Items 1 to 12 were found on
2026-11-02 while adding `ty` type checking (branch `ty-pass1`): each is a name the
checker could not resolve, confirmed against the source and reproduced by the test
named in its entry. The suite state after that pass is 88 passed, 12 xfailed on
Python 3.12 and 3.14.

## Method

For each xfail:

1. Re-read the test and the library code it targets, and confirmed the failure
   mechanism named in the xfail `reason` against the source (file:line below).
2. Asked what evidence says the test's expectation, rather than the current
   behavior, is the intended one: a docstring, a sibling code path that already does
   it right, the name of a constant defined elsewhere, or the documented options of
   a public parameter.
3. Traced callers (`grep` over `src/` and `tests/`) to decide whether a documented
   usage reaches the defect.
4. Ran the test without the marker (`pytest --runxfail`) and recorded the exception
   it raises today ("reproduced").

### Confidence

- **High**: mechanism confirmed in source, and the intended behavior is documented
  or forced by a sibling code path.
- **Medium**: mechanism confirmed, but the intended behavior is inferred from
  convention rather than stated anywhere.

### Impact

- **A**: produces wrong output or a crash today for documented usage or for the
  in-tree test fixtures.
- **B**: reachable from a public API call with a documented argument; not exercised
  by any in-tree test before the xfail was added.
- **C**: reachable only through a private helper, an optional feature nothing
  in-tree exercises, or a replacement for a Python hook.
- **D**: cosmetic (message text, log formatting).

Priority is the joint ranking: A before B before C before D, and within a tier High
confidence before Medium.

## Summary table

| # | Test | Confidence | Impact | Fix |
| --- | --- | --- | --- | --- |
| 8 | `test_host.py::test_host_opens_outside_a_git_repository` | High | A | trivial |
| 2 | `test_rack.py::test_sequence_returns_allowlisted_exception` | High | B | trivial |
| 3 | `test_data_logging.py::test_feather_roundtrip` | High | B | trivial |
| 4 | `test_data_logging.py::test_tar_munger_moves_external_file` | High | B | small |
| 5 | `test_data_logging.py::test_aggregator_rack_output_overrides_conflicting_key` | High | B | trivial |
| 7 | `test_pyvisa.py::test_query_retry_reraises_other_errors` | High | B | trivial |
| 10 | `test_util.py::test_call_accepts_a_partial` | High | B | trivial |
| 1 | `test_rack.py::test_sequence_template_index_is_step_name` | High | B | trivial |
| 6 | `test_pyvisa.py::test_query_formats_keywords` | Medium | B | moderate |
| 11 | `test_cli.py::test_notebooks_module_exists` | High | C | design |
| 12 | `test_cli.py::test_make_sequence_stub_exists` | High | C | design |
| 9 | `test_util.py::test_excepthook_forwards_the_exception_type` | High | C | trivial |

## Tier A: reached by documented usage

### 8. `Host.open` crashes outside a git repository

`tests/test_host.py::test_host_opens_outside_a_git_repository`

- **Mechanism.** `_host.py:293-295` assigns `repo = find_repo_in_parents('.')` inside
  `Host.open`, which makes `repo` a local for the whole function body. When no
  repository is found, `find_repo_in_parents` raises and the `except
  repo.NotGitRepository:` clause evaluates the unbound local instead of the module
  `dulwich.repo` imported at line 30. Reproduced: `UnboundLocalError`.
- **Why the test is right.** The `except` branch sets `repo = None` and logs "not
  running in a git repository", and every `git_*` property tests `repo is None`
  (`_host.py:359-392`). The code intends to run outside a repository.
- **Impact.** Every `CSVLogger` and `SQLiteLogger` owns a `Host` (`_data.py:1036`)
  and opens it with the logger, so any logger opened from a directory that is not
  inside a git repository raises on open. The in-tree tests run inside this
  repository and never reach the branch.
- **Fix.** Rename the local (or import `NotGitRepository` directly). Trivial.

## Tier B: reachable from a public API call

### 2. An allowlisted exception in a `Sequence` raises `AttributeError`

`tests/test_rack.py::test_sequence_returns_allowlisted_exception`

- **Mechanism.** `_rack.py:565` in `BoundSequence.__call__` logs the swallowed
  exception with `core.logger.warning`, and `core` is `labbench._device`, which has
  no `logger`. The rest of the module logs through `util.logger`. Reproduced:
  `AttributeError` raised while handling the allowlisted `ValueError`.
- **Why the test is right.** `Sequence.return_on_exceptions` documents that a
  swallowed exception ends the sequence and the returned dictionary carries an
  `'exception'` key naming the exception type (`_rack.py:1147-1152`).
- **Impact.** Any sequence configured with `return_on_exceptions` crashes at the
  moment the feature is supposed to engage.
- **Fix.** `util.logger.warning`. Trivial.

### 3. `to_feather` fails on current pandas and NumPy

`tests/test_data_logging.py::test_feather_roundtrip`

- **Mechanism.** `_data.py:1613` reads `data.index.is_monotonic`, removed in pandas
  2.0 (`is_monotonic_increasing` remains), and `_data.py:1618` casts with `np.str`,
  removed in NumPy 1.24. Reproduced: `AttributeError: 'RangeIndex' object has no
  attribute 'is_monotonic'`; the `np.str` read is behind it.
- **Why the test is right.** `nonscalar_file_type='feather'` is a documented option
  of the loggers, and `MungerBase._from_ndarraylike` (`_data.py:188`) calls
  `to_feather` for it. The `requires-python >= 3.12` floor rules out the pandas and
  NumPy versions that still had these names.
- **Impact.** Every relational write with `nonscalar_file_type='feather'` raises.
- **Fix.** `is_monotonic_increasing` and `str`. Trivial.

### 4. `MungeToTar` cannot take in an external file

`tests/test_data_logging.py::test_tar_munger_moves_external_file`

- **Mechanism.** `_data.py:493-495` in `MungeToTar._relational_from_file` reads
  `self.tar`; the tar handle opened in `MungeToTar.open` (`_data.py:477`) is
  `self.tarfile`. Reproduced: `AttributeError`.
- **Why the test is right.** The `MungerBase` docstring (`_data.py:53-56`) lists the
  move of an external file into the row's relational directory as the first
  conversion the munger performs, and `MungeToDirectory._relational_from_file`
  (`_data.py:355`) implements it.
- **Impact.** Any logger with `tar=True` that logs a row containing a path to a file
  outside the data directory raises. The same function also passes the arguments
  of `tarfile.addfile(tarinfo, fileobj)` in the wrong order and calls `shutil.rmtree`
  on a file path, so the fix is more than the rename.
- **Fix.** Small: `self.tarfile`, `addfile(info, open(old_path, 'rb'))`, and
  `os.remove` for a file.

### 5. A key conflict in `Aggregator.get` raises instead of logging

`tests/test_data_logging.py::test_aggregator_rack_output_overrides_conflicting_key`

- **Mechanism.** `_data.py:637` calls `self.critical(...)`; `Aggregator` defines no
  such method. Its logger is `self._logger` (from `util.Ownable`). Reproduced:
  `AttributeError`.
- **Why the test is right.** The message text and the following
  `aggregated_output.update(self.incoming_rack_output)` state the intent: log the
  conflict at critical level and let the rack output win.
- **Impact.** A rack method whose return dictionary shares a key with a logged
  device attribute field crashes the row write.
- **Fix.** `self._logger.critical`. Trivial.

### 7. `VISADevice.query(retry=True)` swallows every exception

`tests/test_pyvisa.py::test_query_retry_reraises_other_errors`

- **Mechanism.** `_backends.py:1307` tests `'timeout' or 'timed out' in str(ex)`,
  which parses as `'timeout' or (...)` and is always true, so any exception from the
  backend is retried until `timeout - 0.1` s have elapsed. Reproduced: a `ValueError`
  from the backend is re-raised only after 0.9 s of a 1.0 s timeout.
- **Why the test is right.** The `else: raise` branch two lines below exists to
  re-raise everything that is not a timeout, and the docstring describes `retry` as
  a workaround for backends that raise timeouts early.
- **Impact.** Programming and I/O errors during a retried query are hidden for the
  length of the timeout.
- **Fix.** `'timeout' in str(ex) or 'timed out' in str(ex)`. Trivial.

### 10. `Call` rejects callables without `__name__`

`tests/test_util.py::test_call_accepts_a_partial`

- **Mechanism.** `util.py:806` in `Call.__init__` reads `self.func.__name__`
  unconditionally. Reproduced: `AttributeError` for a `functools.partial`.
- **Why the test is right.** `Call.wrap_list_to_dict` (`util.py:855-859`) guards the
  same read with `hasattr(func, '__name__')` and raises a `TypeError` with a clear
  message when no name is available, and `Call.__repr__` guards `__qualname__` the
  same way. The constructor's own check is `callable(func)`.
- **Impact.** `lb.concurrently(functools.partial(...))` and any callable instance
  raise before the call runs.
- **Fix.** Reuse the `wrap_list_to_dict` guard. Trivial.

### 1. `BoundSequence.to_template` raises `AttributeError`

`tests/test_rack.py::test_sequence_template_index_is_step_name`

- **Mechanism.** `_rack.py:583` reads `cls.INDEX_COLUMN_NAME`, which no class in the
  MRO defines; the constant is `_serialize.INDEX_COLUMN_NAME = 'step_name'`
  (`_serialize.py:20`). Reproduced: `AttributeError`.
- **Why the test is right.** `_serialize.py:199` writes the same table with
  `df.index.name = INDEX_COLUMN_NAME`, and `iterate_from_csv` reads rows back by
  that layout.
- **Impact.** The method is public on every bound sequence and always raises.
- **Fix.** Import the constant from `_serialize`. Trivial.

### 6. `VISADevice.write` and `query` keyword formatting

`tests/test_pyvisa.py::test_query_formats_keywords`

- **Mechanism.** `_backends.py:1256, 1284, 1319` substitute keyword values through
  `self._keying.to_message(v)` and `self._keying.from_message(ret)`, and nothing
  assigns `_keying`. The `visa_keying` decorator stores its adapter as
  `get_owner_meta(cls).key_adapter` (`paramattr/_bases.py:261`), and
  `message_keying.to_message` takes an `attr_def` argument the call does not pass.
  Reproduced: `AttributeError`.
- **Why the test is right.** The `kws` parameter of `query` and the `**kws` of
  `write` exist to format the message, and `remap=True` is documented as applying
  the keying remap to the reply. Confidence is Medium because the intended source
  of the adapter and the `to_message` signature have to be inferred.
- **Impact.** `write` with keywords, `query(kws=...)`, and `query(remap=True)` all
  raise. Calls without keywords skip the comprehension and are unaffected.
- **Fix.** Moderate: route through `attr.get_key_adapter(self)` and pass the
  descriptor the adapter expects, or drop the parameters.

## Tier C: optional features and replacement hooks

### 11. The CLI `--notebook` option imports a module that does not exist

`tests/test_cli.py::test_notebooks_module_exists`

- **Mechanism.** `cli/__main__.py:275` runs `from labbench import notebooks`; the
  package has no `notebooks` module (`[tool.coverage.run] omit` in `pyproject.toml`
  still lists `src/labbench/notebooks.py`). Reproduced: `ModuleNotFoundError`.
- **Why the test is right.** The option is exposed on the command line and the
  coverage configuration shows the module once existed.
- **Impact.** `labbench ... --notebook` fails. Nothing else imports the module.
- **Fix.** Design: restore the module or remove the option.

### 12. The CLI sequence-table reset calls a function that does not exist

`tests/test_cli.py::test_make_sequence_stub_exists`

- **Mechanism.** `cli/__main__.py:217` calls `lb._serialize.make_sequence_stub`;
  `_serialize` defines no such name. Reproduced: `AttributeError`.
- **Why the test is right.** The surrounding command prints "reset ... to stub" and
  documents the behavior.
- **Impact.** Passing a `.csv` path to the command fails. Nothing else calls it.
- **Fix.** Design: implement the stub writer (the per-sequence template logic lives
  in `BoundSequence.to_template`, item 1) or remove the branch.

### 9. `excepthook` forwards the builtin `type` instead of the exception type

`tests/test_util.py::test_excepthook_forwards_the_exception_type`

- **Mechanism.** `util.py:466` calls `exc_info.filter(type, evalue, tb)` with the
  builtin `type` in place of the `etype` parameter. Reproduced: the wrapped hook
  receives `<class 'type'>`.
- **Why the test is right.** The sibling `exc_info.__call__` (`util.py:421`) passes
  `etype`, and the parameter annotation on `__call__` is `type[BaseException]`.
- **Impact.** The default `sys.__excepthook__` labels the traceback from the value,
  so the error is invisible there. A replacement hook that was installed before
  labbench was imported (IPython, a test runner, a logging hook) receives the wrong
  type.
- **Fix.** `etype`. Trivial.

## Observations without an xfail

- **`Sequence._dependency_map` cannot detect a conflict.** `_rack.py:1254` intersects
  `deps.keys()` (device names, `str`) with `func.dependencies` (`Device` instances),
  so the "risk of concurrent access" `RuntimeError` never fires. No xfail, because
  the intended rule is unclear: `deps` accumulates across every step, so comparing
  instances would also reject the in-tree `MyRack` fixture, where `rack1.setup` and
  `rack2.setup` share `inst1` in one concurrent step and `rack2.acquire` and
  `rack2.fetch` share it across steps.
- **`VISADevice._get_rm` has an unreachable `except`.** `_backends.py:1441-1448`
  wraps a dictionary lookup, which raises `KeyError`, in `except OSError`. The
  `e.args[0] += msg` inside would raise `TypeError` on a tuple if it were reached.
- **`store_backend.Oscilloscope.center_frequency`** (`testing/store_backend.py:223,
  227`) calls `self.query` and `self.write`, which `StoreTestDevice` does not define.
  Test scaffolding; no test calls it.
- **Stale docstrings after parameter renames.** `MungeToDirectory._get_key`
  (`_data.py:345`) and the `store_backend` key adapter methods document the former
  parameter names. Documentation only.
- **pandas deprecation warnings.** `_data.py:1527` `sort_index(inplace=True)` emits
  `Pandas4Warning` under pandas 3; the suite reports 17 warnings.
