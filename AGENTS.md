# AGENTS.md

This file is the guidance for coding agents and new contributors working in this repository.

## Commands

Access the environment through `pixi`, configured in `pixi.toml`. The `default` environment
is Python 3.14 with the `dev`, `jupyter`, `pyvisa-py-extras`, and `pyvicp` extras of labbench
installed editable; `test312` through `test315` carry the same on each supported Python; `doc`
adds sphinx; `publish` adds `build` and `twine`.

```sh
pixi run test                                           # full suite, py314
pixi run -e test312 test                                # full suite on the oldest Python
pixi run -e test315 test                                # full suite on the newest Python
pixi run pytest tests/test_paramattr_value.py -q        # one file
pixi run pytest -k test_python_print                    # one test by name
pixi run format                                         # ruff format src tests (single quotes, preview style)
pixi run lint                                           # ruff check src tests
pixi run coverage-badge                                 # pytest with coverage xml and the badge in doc/reports
pixi run -e doc doc                                     # sphinx html into doc/html
pixi run -e doc doc-clean                               # remove doc/html and doc/jupyter_execute
pixi run -e publish build-check                         # build into dist/latest and twine check
pixi run stubs                                          # regenerate type stubs with scripts/make_stubs.py
```

`pixi run` refreshes the editable install when `pyproject.toml` or `pixi.toml` changes. Adding
`--frozen` skips the manifest/lock-file consistency check, saving the reinstall (and any network
fetch) that a manifest edit would otherwise trigger — but it also means a newly added
dependency silently isn't installed, surfacing as an `ImportError` instead of pixi's normal
"lock file not up-to-date" message. Default to running without it; reach for `--frozen` only in
a tight loop of commands where the manifest is already known not to have moved.

The numerical stack (numpy, pandas, pyarrow) and `libusb` come from conda-forge; everything
else is a PyPI dependency declared in `pyproject.toml`. win-arm64 takes the whole stack from
PyPI wheels and has no `test312`, `test313`, or `publish` environment.

VISA tests run against the `pyvisa-sim` backend with the instrument definitions in
`src/labbench/testing/pyvisa_sim.yml`; no hardware is attached in the test suite.

## Architecture

One package, `src/labbench/`. The public API is the set of names exported by
`labbench/__init__.py` and `labbench.paramattr`; modules with a leading underscore
(`_device.py`, `_backends.py`, `_rack.py`, `_data.py`, `_host.py`, `_serialize.py`) are
internal and change without warning. `labbench.paramattr` defines the `value`, `property`,
`method`, and `method_kwarg` descriptors that type and document the parameters of a
`Device`. `labbench.testing` carries the simulated devices used by the test suite and the
documentation. The user guide is in `doc/guide/`, and the API reference is rendered from
docstrings by sphinx autodoc with napoleon.

### Known gaps are recorded as strict xfails

Library defects that need a design decision rather than a local fix are written as
`pytest.mark.xfail(strict=True, reason=...)` tests against the intended behavior, so
`grep -rn "mark.xfail" tests` lists them with their causes. Read the reason before treating
a red test as new, and expect a genuine fix to turn that xfail into an unexpected pass that
must then be removed. The ledger `tests/xfail-audit.md` records each one: the node id, the
mechanism with file and line, why the test's expectation is the right one, the impact tier,
and the fix with its difficulty. Its numbered items are stable identifiers, and a
suite-state line records the `passed/xfailed` counts of each pass. `reason=` names the
mechanism and stays verbatim once written. A fix turns the xfail into an unexpected pass:
remove the marker and retire the item in the same change. A run with any xpass is a failed
run; `pixi run pytest tests -q -rxX` lists both.

## Conventions

- **Lint.** The rule set is ruff's default plus the per-file ignores in `pyproject.toml`; the
  pixi lock pins the ruff version, and the counts below are from that version (0.17.3). As of
  2026-11-02, `pixi run lint` reports 352 errors (mostly B006, C408, BLE001, I001, RUF012,
  TRY004, F401); that count must not grow, and code the task changes is brought to clean.
  `pixi run ruff format --check src` reports nothing; `tests/` still carries unformatted files,
  so format only the test files a change touches. A line that must keep a flagged pattern carries
  `# noqa: <RULE>` with the reason, never a bare `# noqa`. Fix with
  `ruff check --fix-only --fixable <RULES>` under the full config rather than `--select`, which
  redefines the enabled set and makes RUF100 report every other `noqa` as unused.
- **Python 3.12 is the floor** (`requires-python = ">=3.12"`, ruff `target-version = "py312"`).
- For functions that need to return structured data based on named fields, prefer
  `dataclasses` over `typing.TypedDict` or named tuples.
- **Typing.** Every new or edited function, method, and closure carries hints for all
  parameters and the return; only `self`/`cls` and lambdas are exempt. Wrapper catch-alls are
  `*args: P.args, **kwargs: P.kwargs`. `**kwargs` forwarded to a fixed target are
  `**kwargs: Unpack[<Name>Kws]` with a `TypedDict`; anything else is `**kwargs: Any`.
  `TypedDict` is for keyword sets only; structured return values stay `dataclasses`. A
  decorator that returns a wrapper names its type variables in the return annotation, not the
  bare alias, so the checker keeps the wrapped signature.
  - **Gate.** `pixi run typecheck` (ty, pinned in the `dev` extra; `[tool.ty]` in
    `pyproject.toml` sets the 3.12 floor and `src/` scope) must report no diagnostics,
    warnings included. ty reports an unused ignore as a warning, so a stale suppression fails
    the gate.
  - **Suppressions.** Fix a diagnostic with a better hint, a guard, a local, or a cast before
    suppressing it. A suppression is `# ty: ignore[rule-name]  # reason` on the offending
    line, never a blanket `# ty: ignore` or `# type: ignore`. When the cause is a known defect,
    the reason is `xfail-audit item N` (or `xfail-audit observation: ...`) and the ledger lists
    the site; the fix removes the comment, the xfail marker, and the ledger item together.
    Platform-only imports (`clr`, `win32com`, `pythoncom`) and the deliberate `sys` hook
    replacements in `util.py` are the other accepted reasons.
  - **Class annotations are runtime data.** `paramattr._bases.get_cls_annotations` evaluates
    the `__annotations__` of every class in a `Device` MRO (including `util.Ownable`) with
    `_bases.py` globals, `Device.__set_signature__` raises for any annotated class attribute
    that is not a `paramattr.value` descriptor, `ParamAttr` annotations define constructor
    fields, `Rack` annotations become `__init__` keywords, and `MethodTaggerDataclass`
    annotations become decorator keywords. A type-only declaration in any of those classes
    goes inside `if typing.TYPE_CHECKING:` in the class body, above the runtime assignment
    (verified on 3.12-3.14 to leave `__annotations__` untouched); see `Device.backend` and
    `Ownable._logger`. Changing the type of an existing `ParamAttr` field annotation is fine;
    adding or removing an annotated name is a constructor change.
  - **Field specifiers.** The `TYPE_CHECKING` stubs in `paramattr/value.py` are plain
    functions naming the PEP 681 parameters (`default`, `kw_only`, `init`, `allow_none`) so
    that ty's `dataclass_transform` on `Device` honors `kw_only=False` and positional
    defaults; keep new value types in that form (a Protocol instance is not recognized as a
    field specifier).
  - **Signatures.** `util.set_signature` and `util.get_signature` hold the only casts for
    `__signature__` on function objects; use them rather than casting at the site.
- **Prose in code reads like an engineer's, not a model's.** These rules apply to every
  comment, docstring, commit message, PR description, and prose file written into the
  repository. The test for a sentence is whether a reader with the technical background, but
  without this session's context, comes away with the fact intact. The canonical shape is
  `Subject Verb Object [, qualifier]`: Subject is a thing that can literally do Verb, Verb
  arrives within about eight words with nothing between it and Subject, and everything after
  the first comma is a qualifier (units, rounding, condition) or a clause joined by the word
  that names its relation. **Rules** names the 7 ways a sentence breaks that shape, with the id
  cited in change reports; **Not written** is the word table; **Check** is the one pass run
  after editing. (`voice.md`
  "Sentence rules" in the `kuester-writing` skill is the manuscript form; a paper's voice
  allows "we", "In order to", "the following", "This is important:", "various", and "etc.",
  and code prose does not.)
  - **Rules.** Each rule has an id, a test, a recipe, and a Keep.
    - **`noun`: every noun denotes a thing in the code or the field, or a claim on the page.**
      Test: name what each noun denotes, and substitute the antecedent for every "it". Not "the
      attribute is set" but "the `units` attribute is set to `'dBm'`". Prepositions follow the
      shape of the noun: *during* a span (sweep, read, acquisition), *at* a point (sample,
      index, time stamp), *in* a container (buffer, queue, table); a retry resumes *with* or
      restarts *from* a segment; a value is set *on* an attribute and read *from* a field;
      "referred to" takes a reference plane, temperature, or impedance. A thing is named once
      and the noun reused; the placeholder nouns and renamings are in the table. Keep: "it" and
      "its" once per paragraph when the antecedent is the subject of the previous sentence and
      the same kind of thing.
    - **`agent`: the subject's class fixes the verbs it may take.** Test: replace the subject by
      what it literally is (a function, a number, a buffer, a key, a design, a page of text) and
      ask whether that thing can do the verb to this object; fail, pass, and meet take a
      requirement as object, not an artifact; a verb that reads as well with a person or a team
      as its subject (wins, prevails, falls back, decides) reports an outcome and hides the
      rule. Fix: R1 for a cause or technique, R2 for a device, R8 for an outcome verb, the fact
      it stands for when the subject is a design or the text itself. Not "the lock earns its
      place in the hot loop" but "the lock serializes VISA access from the acquisition and
      logging threads"; not "the device setting wins over the default" but "a key set in both
      the device and the defaults takes the device value". A pronoun keeps the class of its
      antecedent ("the estimate ... it assumes a reference": a number cannot assume; write "the
      estimator").

      | Subject class | May take | May not take |
      |---|---|---|
      | Code object: function, class, thread, backend, device, rack, caller | implements, follows, requires, returns, raises, reads, writes, allocates, serializes, selects, replaces, starts, holds <the store> open, logs on <logger> at <LEVEL> when <condition> | handle, take care of, inherit, suffer from, struggle with, unlock, live in, do anything gracefully; "owns" (name what holds, allocates, or reads) |
      | Quantity or value: level, power, estimate, count | is, equals, averages, exceeds, is bounded by, is limited / set / determined by <cause>, takes <value> when <condition> | sit, land, hover, read, see, report (a level); return, assume, decide |
      | Buffer, port, connection, store, file, table | its function with the object that verb takes (a buffer holds samples, a port carries a stream) | hold, carry, keep, achieve, reach, deliver a result; fail or meet an artifact; win, lose, prevail over, beat |
      | Metadata key, attribute, field, column name | object of set, read, copy, remove, equal | take, gain, lose, carry, record, spell out; win, take precedence (write the condition and the value the key takes); "the attribute" alone without its key |
      | Design, contract, invariant, intent, approach, fix, correctness | is, requires <of the caller>, holds <for a range> | carry, anchor, earn, buy, pay for, hold up, stand, grow, feed, drive, turn into; a designer's decision (should maximize, choose, avoid) |
      | Abstract cause, choice, or technique: latency, caching, "choosing a timeout" | after "by" or in a because-clause; a change verb only with the amount or condition in the same clause | sets, limits, moves, offers, drives, improves, costs; the bare change verb ("caching increases the latency") |
      | The text about the code: this module, this docstring, the table, the check, the runner | nothing; strike the sentence, and what remains must still state the caller's contract | any verb |
    - **`verb-first`: subject, finite relation verb, object; qualifiers trail.** Test: cut the
      sentence after its first finite verb; the remainder states the relation (fails, requires,
      exceeds, removes) with nothing between subject and verb. Rewrite (R3) an appositive or
      ", not Y," between them ("the backend, a serial port, returns"), a qualifier before the
      subject ("rounded to 1 ms, the value is the timeout" becomes "the timeout is the value,
      rounded to 1 ms"), a claim in a trailing relative clause ("returns the line that the
      device logs"), or a light verb plus abstract noun ("has a requirement that ..."). Not a
      fix: moving the verb to a second clause on a pronoun that points back ("..., but coarse
      alignment fails it too"). Keep: a connective opener ("Thus,", "Further,", "First,") or a
      condition of about eight words or fewer.
    - **`attach`: one head per modifier, and next to it.** Test: each participle, relative
      clause, "to <verb>", or prepositional phrase has one word it can modify and sits beside
      it. Rewrite (R3) if two candidates exist, if a comma-bracketed clause separates it from
      its head, or if it narrates an event with its own time ("the device opened when the rack
      started" becomes "the open device", with the event in a sentence of its own). Rewrite
      (R9) an object relative clause that ends a clause on its verb ("the backend that `open`
      returns" becomes "the backend returned by `open`"); the reader carries the noun until the
      verb arrives. No sentence or clause ends in a preposition ("the `Device` that the rack is
      opened for" becomes "the `Device` for which the rack is opened"). A purpose infinitive
      follows its verb directly. Keep: a participle that states a property ("the connected
      device"); a subject relative clause ("the devices that share a rack"); an object relative
      clause followed by its own qualifier ("the devices that `Rack.open` connects, in
      declaration order").
    - **`join`: what a comma, a semicolon, and a colon may join.** Test: count the independent
      clauses (a finite verb with its own subject outside any that/which/when/because clause).
      Rewrite (R4, R5) a bare comma between two, a semicolon beside a conjunction, more than
      three, clauses that could be reordered without changing the argument (a list), or a colon
      in place of "because", "so", "which means", or "for example". A colon announces a
      specification, list, or restatement. A semicolon does not append a critique to a
      description. Several rules are a list, one "condition: what is set" per item, with no
      numbered narrative and no appositive after the consequence.
    - **`verdict`: no grade, filler, or opener without its number.** Test: delete each
      adjective, opener, and filler in turn; if no number, baseline, or condition is lost it
      stays deleted, and if one is implied, write it (R6). For a verb of change or degree, ask
      by how much or under what condition. The grades, antitheses, openers, praise, and boasts
      are in the table. "robust" takes an object ("robust to a dropped connection") or is not
      written; a boast becomes the cost or nothing.
    - **`compare`: a comparison is a clause with a named baseline.** Test: the baseline,
      quantity, amount, and condition are all present, and the baseline does not trail the
      number as ", compared with <value>". Fix: R7 ("0.6x the pandas time for 10,000 rows on
      the test host"), or the comparison is not made.
  - **Recipes.** R1 invert to the quantity: "<quantity> is limited by / set by / determined by
    <cause>". R2 demote the device to a condition: "With <device>, <quantity> fell within
    <value>". R3 move the fronted qualifier, the appositive, or ", not Y," after the main
    clause or into its own sentence, and make the relation verb the main verb. R4 split: one
    condition with its consequence per sentence, or one list item per rule. R5 replace the
    colon with "because", "so", "which means", or a period. R6 delete the word, or write the
    number, condition, or fact it stood for. R7 "Compared to <baseline>, <quantity> changes by
    <amount> under <condition>." R8 write the rule the outcome stands for: "<condition>:
    <quantity> takes <value>" ("a key set in both the device and the defaults takes the device
    value"). R9 write the relation of a code object to a noun as a participle after the noun
    ("the backend returned by `open`"), or as a clause with the function as subject ("`open`
    returns the backend").
  - **Mechanics.** Digits for counts ("3 devices", "2 ports"); the Oxford comma; American
    spelling; "e.g.," and "i.e.," with the trailing comma.
  - **Not written.** Each is replaced by the condition, the number, the task, or nothing. The
    verbs a subject class may not take are in the `agent` table.

    | Group | Not written | Write instead |
    |---|---|---|
    | Person and narration | "I", "we", "our", "us", "you", "your", "let's"; "they", "their", "them" for a variable, attribute, device, or quantity; "whose"; "first we ... then we ..."; "the following"; "this will"; a sentence addressed to a reader or writer ("you are editing", "once you commit") | the noun; "the devices with timeout above" for "the devices whose timeout exceeds"; a list for a sequence |
    | Placeholder nouns and renamings | "this behavior", "edge cases", "the result", "the logic", "various", "etc.", "as expected", "the right thing", "what it does", "the present context"; "this pipeline", "this chain", "this logic", "the machinery" for a thing already named | the condition the placeholder stands for; the noun of first mention |
    | Hedges and fillers | "should" where "must" is meant, "try to", "attempt", "safely", "properly", "simply", "just", "basically", "essentially", "effectively", "note that", "it is worth noting", "make sure", "sanity check", "for convenience", "under the hood" | the condition or the requirement |
    | Connective openers | "Additionally,", "Moreover,", "Furthermore,", "Importantly,", "In other words", "In order to" | "Further,", "Thus,"; the infinitive after its verb |
    | Grades, praise, and verdict openers | "proper", "genuine", "real", "true", "clean", "cheap" as a judgement, "circular", "one-sided"; "data, not assertions", "behavior rather than mechanism" as a slogan, "The problem is the cache."; "This is important", "X is a solved problem", "the key insight is", "X has a cost:", "the trade-off is", "the catch is"; robust (without an object), powerful, elegant, seamless, crucial, critical, comprehensive, clean, efficient, flexible, convenient, graceful, novel; "with speed optimizations" | the fact, the condition, or the shortfall with its number and consequence; the resource saved or the cost |
    | Time and change words | "now", "no longer", "previously", "new", "legacy", "used to", "fix", "workaround", "TODO", "for now" | the condition the code finds (**Present tense, present code** under Docstrings) |
    | Lexicon | "utilize", "towards", "in practice", "trivial", "crucial", "vital", "very" as praise, "ground truth" outside quotation marks | "use", "toward", the condition, "straightforward", "key", the number |
    | Idioms and effort estimates | "an afternoon's work", "low-hanging fruit", "should go", "a leftover", "earns its place", "going forward", "at the end of the day", "in the other direction" | the task, the deletion, or the number |
  - **Commit messages.** The summary line is one imperative clause of about 72 characters or
    fewer that names the effect of the change ("describe the fault, not the test, in the xfail
    ledger summary"), with no trailing period and no tag prefix; a summary that names no effect
    ("cleanup", "tweaks", "misc fixes", "updates") is not written. The body, when the summary
    does not carry the whole fact, states the condition the change addresses and what the code
    does after it, in the present tense of the new code ("`open` raises `ConnectionError` when
    the rack has no backend"), one fact per sentence. Not written: "this commit", "now",
    "also", a list of the files touched, a progress note, or a sentence about the session or
    the reviewer. A docstring or prose rewrite is its own commit, named as such (**Prose
    changes stay visible**). The `Co-Authored-By` trailer stays as the tooling writes it.
  - **Check.** One pass, after editing, over every comment, docstring, and commit message of
    the change: the test of each rule in the order listed, then the table; re-run `noun`,
    `agent`, and `verb-first` on any sentence a split creates. A sentence proposed by a
    reviewer, an agent, or a search-and-replace is new prose and gets the same pass in place; a
    rewrite applied from a list is how the habits above return. The pass covers the prose of
    the code the task has changed, not prose read along the way; a wider pass requires an
    explicit request from the user.
- **Comments:** only write one if a competent engineer or agent reading the code cold would be
  surprised or misled without it. Worth writing: a non-obvious *why* (constraint, workaround,
  domain rule, performance trade-off); something that looks wrong but is intentional; external
  context that can't be inferred from the code (section from a technical standard,
  peer-reviewed publication, government report, public documentation, upstream bug/issue
  number); an invariant or precondition the types don't enforce. Do not write:
  - changelog or progress notes (`# added null check`, `# refactored from previous version`) —
    the diff is already in git. Progress notes belong in the chat response, the commit message,
    or the PR description, never in a source file comment;
  - narration of the obvious (`# loop over devices`, `# return the result`);
  - restatements of the signature or type annotations;
  - conversational leakage (`# as requested`, `# per the instructions`, `# TODO: user said to`);
  - section banners, unless the file is genuinely huge.

  If a comment is needed to explain *what* code does, prefer renaming or extracting a function
  instead — that removes the cause rather than the symptom. Comments are for *why*. A comment
  takes the function or the value as subject and states or cites the constraint, standard, or
  issue; it is checked once under **Check**.

- **Docstrings** are the API reference (sphinx autodoc + napoleon render them into `doc/`), so
  write them as the caller's contract: inputs, outputs, side effects, exceptions. Google
  sections only — `Args:`, `Returns:`, `Yields:`, `Raises:`, `Examples:`, `References:` —
  never `Arguments:`, numpy underlines, or ad hoc headers. Much of the existing code still
  carries `Arguments:`; convert the header when the function is edited (see **Scope of a
  change**). Compose each part from its template and run **Check** once on the finished
  docstring.
  - **Templates.** Each part states what the signature cannot: units (Hz, s, dB vs linear
    power), valid range or constraint, which keys a mapping carries, column names, and what
    `None`, `inf`, or `'auto'` selects. `x: input value` and `timeout: the timeout` are
    omissions, not entries.

    | Part | Template |
    |---|---|
    | Summary line | `<imperative verb> the <effect or quantity> (<units>) <of/for/at> <input>.` ("return the elapsed time (in s) since `start`."); lowercase first word; one claim; the period is dropped only when the whole docstring is one line |
    | `Args:` entry | `<name>: <what the value selects, constrains, or shapes>, <unit or range>; <None/inf/'auto'> <selects what>`; 1 clause, at most 2 |
    | `Returns:` | `<shape, dict keys, or column names>, <units>` |
    | `Yields:` | `<item>, <units>; iteration ends when <condition>` |
    | `Raises:` | `<Exception>: <condition>`, for every exception the caller can act on; never one that only a bug raises, never the message text |
    | Side effects | one prose sentence per effect: in-place modification, instrument state changed, process-global state (logger handlers, caches, registries), threads started, files written |
    | Log mention | "logs on `<logger>` at `<LEVEL>` when <condition>"; never the message text |
    | Attribute docstring (class attribute, dataclass field) | a string literal on the line after the attribute: one noun phrase with units and range, and what `None`, `inf`, or `'auto'` selects (`timeout: float` then `"""VISA session timeout (s)"""`); the `Args:` entry rules apply |
    | Class | what an instance is, what construction requires, and the state or lifecycle the methods share (a context manager); at most 3 sentences; no sentence about one member or one attribute |
    | `__init__` | what is stored, and what is opened or derived ("store the resource string; nothing is opened.") |
    | Module | the theme in one sentence, and one implementation fact that applies across the module and is written in no comment |
  - **What a docstring says.** The object's own contract: what it requires, returns, raises,
    and changes. Not what other code does with the object (where a function is registered,
    which caller invokes a method, when another class reads an attribute: "registered as the
    `on_close` callback", "`Rack.open` calls `open`", "the logger reads `path` on first
    write"); a hook may name its intended consumer in one clause of its own docstring and no
    more. Not the mechanism: a method is named only when it decides the result or the cost,
    and the steps of the body are stated only when they are the observable precedence, as
    rules. Not the reason for a constraint, which belongs in a comment at the line that
    enforces it. Not the code of the return value, but the inputs it is computed from and its
    bounds. A docstring that narrates mechanism, names an internal module, or describes the
    change that produced it costs review time and returns nothing: when a refactor touches a
    documented object, delete the sentences about the old mechanism rather than rewriting
    them, and add a sentence only for a caller-facing rule (what a value selects, what is
    rejected, which input a derived value comes from). A summary line alone is a complete
    docstring.
  - **Entries before prose.** A fact about one parameter is that parameter's `Args:` entry,
    and a fact about the return value is the `Returns:` entry; the prose above the sections
    carries only facts that span several parameters or the object's state. Three sentences
    that each name one parameter are an `Args:` block written in the wrong place. An entry
    says how the value selects, constrains, or shapes the output ("the open device", "`None`
    disables the timeout", "in dB"), not what the body does with it ("the implementation
    invokes ...", "the resource string is parsed"); a behavior the body applies to one argument
    is a prose sentence when this function owns the behavior, and one prose sentence naming
    the owning function when another function does. A sentence that restates an entry, or
    that points the reader to another object's docstring ("whose docstring describes the
    yields"), is deleted: the docstring stands on its own, and autodoc links the names in
    backticks.
  - **Summary line.** `pixi run ruff check --select D401 src` lists non-imperative summaries
    ("an iterator that ...", "helper for ...", "designs ..."); it is not enforced, so run it on
    files you touch. One claim per line: a trailing participial clause is cut into its section
    (", yielding what `append` returns" becomes a `Yields:` entry; ", raising what the backend
    raises" a `Raises:` entry). "open the device and its children." is a whole summary.
  - **Module docstrings.** Do not catalog the module's contents or repeat details of the
    objects in its namespace; autodoc renders those from the objects' own docstrings. No return
    types, signatures, or naming patterns of the members; no statement of what the module does
    not do ("nothing here logs"); no reference to the program that consumes the output.
  - **Class and attribute docstrings.** Every fact about one method, property, or attribute
    goes in that member's docstring; a class docstring sentence that names one attribute is an
    attribute docstring written in the wrong place. For a `Protocol`, the class docstring
    states the role an implementation plays and nothing about registration, callers, or
    inheritance. A `paramattr` descriptor is documented through its `help` argument instead of
    an attribute docstring, with the same content rules. Do not write an `Attributes:`
    section: with `undoc-members` on, napoleon's `.. attribute::` entries duplicate autodoc's
    member list.
  - **Predicate nouns.** In every "X of Y" and "Y's X", Y is the thing that has X. "The units
    of a device" fails when the units belong to one value the device returns. Rewrite until
    each possessive names the actual owner.
  - **Present tense, present code.** Nothing about what the code used to do, was changed to
    do, or may do later; the time and change words are in the **Not written** table. Code that
    converts older data describes the condition it finds, not the version or era that wrote
    it.
  - **Cite external context.** A standard section, a paper, or an upstream issue is cited in
    its short form inline, in parentheses ("(IEEE 488.2 §10.1)", "(pyvisa issue 123)"). The
    long form of each citation (full title, authors or standards body, year, URL or DOI) goes
    under a `References:` section at the end of the docstring, one entry per source.
  - **Markup.** Identifiers in single backticks (they render italic: no `default_role`),
    literal code in double backticks, examples in doctest form (ruff formats them with
    `docstring-code-format`).
  - **Length follows audience.** Public API (the names exported by `labbench` and
    `labbench.paramattr`) gets full sections; a helper in an underscore module gets a summary
    line plus only the sections that carry information. No docstring beats one that restates
    the name.
  - **Scope of a change.** Bring the docstring of any function you edit to this standard,
    including stale parameter names and exception lists. Do not rewrite docstrings of untouched
    functions in the same change. A revision pass over docstrings or comments covers only the
    code the task has changed, never code read along the way; a wider pass requires an explicit
    request or authorization from the user.
  - **Prose changes stay visible.** A docstring rewrite goes in a commit whose message names
    it, never inside one titled for a rename or refactor. The final chat message of a change
    lists every docstring touched, by qualified name, so the list can be reviewed without the
    diff.

## Testing

`tests/` is flat and has no `conftest.py`: one `test_<topic>.py` per area (`test_rack.py`,
`test_paramattr_value.py`, `test_pyvisa.py`, ...), and shared helpers are plain modules
imported by bare name (`from paramattr_tooling import ...`, `module_as_testbed.py`) because
pytest's prepend import mode puts `tests/` on `sys.path`. Add new tests to the existing module
for the area rather than creating a file per feature. A change passes the suite in the oldest and
the newest test environments, `pixi run -e test312 test` and `pixi run -e test315 test`, before
it is reported done; `pixi run test` alone covers only py314. The standard library changes between
minor versions (3.15 removes `dataclasses._MISSING_TYPE`), so an import of a private
stdlib name is guarded or replaced rather than assumed to exist on every supported Python.
Fixtures are module-local; several modules use an autouse module-scoped fixture for setup.
Simulated devices come from `labbench.testing`.
