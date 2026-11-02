# AGENTS.md

This file is the guidance for coding agents and new contributors working in this repository.

## Commands

Access the environment through `pixi`, configured in `pixi.toml`. The `default` environment
is Python 3.14 with the `dev`, `jupyter`, `pyvisa-py-extras`, and `pyvicp` extras of labbench
installed editable; `test312` through `test315` carry the same on each supported Python; `doc`
adds sphinx; `publish` adds `build` and `twine`.

```sh
pixi run test                                           # full suite, py314
pixi run -e test312 test                                # full suite on another Python
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
  is prose and follows **Prose in code** below.

  After editing, re-read every comment you added and delete any that restate the code or
  describe the change rather than the code. This pass is cheap and catches most stragglers.
  The pass covers the comments in code the task has changed, not every comment read along the
  way; a wider comment sweep requires an explicit request or authorization from the user.

- **Docstrings** are the API reference (sphinx autodoc + napoleon render them into `doc/`), so
  write them as the caller's contract: inputs, outputs, side effects, exceptions. Google
  sections only — `Args:`, `Returns:`, `Yields:`, `Raises:`, `Examples:`, `References:` —
  never `Arguments:`, numpy underlines, or ad hoc headers. Much of the existing code still
  carries `Arguments:`; convert the header when the function is edited (see **Scope of a
  change**).
  - **Drafting order.** Write the summary line first, then the `Args:`/`Returns:`/`Raises:`
    entries from the signature, then one sentence per remaining fact, each starting with its
    subject. Run the **Check** list under **Prose in code** on each docstring before moving to
    the next function, not once at the end of the change.
  - **This object's contract only.** A docstring states what the object requires, returns,
    raises, and changes. It does not say what other code does with the object: not where a
    function is registered, which caller invokes a method, or when another class reads an
    attribute ("registered as the `on_close` callback", "`Rack.open` calls `open`", "the
    logger reads `path` on first write"). A hook may name its intended consumer in one clause
    of the hook's own docstring and no more.
  - **Log messages.** A docstring names the logger and the level a function logs on, and the
    condition that produces a record. Never the text of a message, in full or in part.
  - **Sections before prose.** A fact about one parameter is that parameter's `Args:` entry. A
    fact about the return value is the `Returns:` entry. Prose above the sections carries only
    facts that span several parameters or the object's state. Three sentences that each name
    one parameter are an `Args:` block written in the wrong place. A sentence that restates an
    `Args:` entry, or that points the reader to another object's docstring ("whose docstring
    describes the yields"), is deleted: the docstring stands on its own, and autodoc links the
    names in backticks.
  - **Args state the contract.** An `Args:` entry says how the value selects, constrains, or
    shapes the output ("the open device", "`None` disables the timeout", "in dB"). It does not
    say what the body does with the value ("the implementation invokes ...", "the resource
    string is parsed"). A behavior the body applies to one argument is a prose sentence when
    this function owns the behavior, and one prose sentence naming the owning function when
    another function does. That cross-reference replaces detail; a pointer that stands in for
    a claim this docstring must make itself is still deleted. An entry is one brief clause, at
    most 2; detail beyond that goes in the prose above the sections, not in the entry.
  - **Summary line.** One line, imperative mood, lowercase first word, naming the effect or the
    returned quantity with its units: "return the elapsed time (in s) since `start`". Not "an
    iterator that ...", "helper for ...", "this function ...", or a third-person verb
    ("designs ..."). Include a trailing period unless the docstring is a one-line docstring.
    `pixi run ruff check --select D401 src` lists non-imperative summaries; it is not
    enforced, so run it on files you touch. One claim per summary line: a trailing participial
    clause carries a second claim and is cut (", yielding what `append` returns" becomes a
    `Yields:` entry; ", raising what the backend raises" a `Raises:` entry). "open the device
    and its children." is a whole summary.
  - **Module docstrings.** Do not catalog the module's contents or repeat details of the
    objects in its namespace; autodoc renders those from the objects' own docstrings. Give the
    context a reader needs before any one object: the theme of the module, and an
    implementation fact that applies across it and is written in no comment. Use the restraint
    of the Comments guidance. No return types, signatures, or naming patterns of the members;
    no statement of what the module does not do ("nothing here logs"); no reference to the
    program that consumes the output.
  - **Class docstrings.** State what an instance is and the contract shared by every method
    (what construction requires, state the methods share, a lifecycle such as a context
    manager), in at most 3 sentences. Every fact about one method, property, or attribute goes
    in that member's docstring; autodoc renders those. For a `Protocol`, the class docstring
    states the role an implementation plays and nothing about registration, callers, or
    inheritance. Construction requirements and effects go in the `__init__` docstring, and
    each public attribute takes an attribute docstring; the class docstring keeps what an
    instance is.
  - **Attribute docstrings.** A plain class attribute or dataclass field carries an attribute
    docstring: a string literal on the line after the attribute, one noun phrase with units and
    range (`timeout: float` followed by `"""VISA session timeout (s)"""`). Sphinx autodoc
    renders the literal as the member description. A `paramattr` descriptor is documented
    through its `help` argument instead, with the same content rules. Do not also write an
    `Attributes:` section: with `undoc-members` on, napoleon's `.. attribute::` entries
    duplicate autodoc's member list. The rules for `Args:` entries apply to each attribute
    docstring and `help` string, and the rules for sections versus prose apply to the
    attributes versus the class docstring (**Sections before prose**, **Args state the
    contract**). An attribute docstring states the contract of the value: what the attribute
    selects, constrains, or shapes, and what `None`, `inf`, or `'auto'` selects. A fact about
    one attribute is that attribute's docstring, never a sentence in the class docstring; the
    class docstring carries only facts that span several attributes or the state and lifecycle
    of the instance. A class docstring sentence that names one attribute is an attribute
    docstring written in the wrong place.
  - **Predicate nouns.** In every "X of Y" and "Y's X", Y is the thing that has X. "The units
    of a device" fails when the units belong to one value the device returns. Rewrite until
    each possessive names the actual owner.
  - **Language.** Write with American English and spelling.
  - **State what the signature cannot.** An `Args:` entry adds meaning, never type: units (Hz,
    s, dB vs linear power), valid range or constraint, which keys a mapping carries, and what
    `None`/`inf`/`'auto'` selects. `x: input value` and `timeout: the timeout` are omissions,
    not entries. `Returns:` gives shape, dict keys, column names, and units. Generators use
    `Yields:` and say what ends the iteration.
  - **Side effects are contract.** In-place modification, instrument state changed,
    process-global state (logger handlers, caches, registries), threads started, files
    written.
  - **`Raises:`** lists every exception the caller can act on with its condition. Omit
    exceptions that only a bug would raise. An entry names the exception type and the
    condition that produces it; it does not reproduce the message string of the exception, in
    full or in part.
  - **Avoid repeating exact code in the function when documenting the return value.** Rather,
    state which inputs will be used to compute the returned value, and the scope of possible
    return values such as bounds.
  - **Behavior, not mechanism.** Name the method only when it decides the result or the cost.
    No step-by-step narration of the body; when the steps *are* the observable precedence,
    state them as rules.
  - **Constraints, not their reasons.** State what the caller must satisfy and what they get
    back. The reason a constraint exists belongs in a code comment at the line that enforces
    it, if anywhere; never in the docstring.
  - **Present tense, present code.** Nothing about what the code used to do, was changed to
    do, or may do later — no "now", "no longer", "previously", "new", "legacy", "used to",
    "fix", "workaround", "TODO", "for now". Hedges, person, and the lexicon are under **Prose
    in code** below. Code that converts older data describes the condition it finds, not the
    version or era that wrote it.
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
  - **A noisy docstring is worse than none.** A docstring that narrates mechanism, names an
    internal module, or describes the change that produced it costs review and maintenance
    time and returns nothing. When a refactor touches a documented object, delete the sentences
    that referenced the old mechanism; do not rewrite them. Add a sentence only when it states
    a caller-facing rule: what a value selects, what is rejected, which input a derived value
    comes from. A summary line alone is a complete docstring.
  - **Prose changes stay visible.** A docstring rewrite goes in a commit whose message names
    it, never inside one titled for a rename or refactor. The final chat message of a change
    lists every docstring touched, by qualified name, so the list can be reviewed without the
    diff.

  After editing, run 4 structural checks on every docstring you touched, before the lexical
  **Check** under **Prose in code**. These are the checks that a word scan does not replace:
  1. Strike every sentence whose subject is a module, a table, a check, a runner, or the
     design. What remains must still state the caller's contract; if it does not, cut the
     docstring to the summary line.
  2. For every "it" and "its", the antecedent is the subject of the previous sentence and in
     the same noun category (attribute, device, parameter); otherwise write the noun. At most
     one "it" per paragraph.
  3. Cut each sentence after its first verb. If the claim is not yet stated, split the sentence
     or delete it.
  4. No sentence or clause ends in a preposition. "the `Device` that the rack is opened for"
     becomes "the `Device` for which the rack is opened", or the sentence is turned around so
     the object comes last.

  Then delete any sentence that restates the signature, describes the change rather than the
  code, or hedges, and any clause that starts with "because", "since" or "so that" or sits in
  parentheses explaining the mechanism.

- **Prose in code reads like an engineer's, not a model's.** These rules apply to every
  comment and docstring; the habits they name pass ruff and still mark text as
  machine-written. The test for a sentence is whether a reader with the technical background,
  but without this session's context, comes away with the fact intact.
  - **State the fact, not a verdict.** No evaluative openers or aphorisms ("This is
    important", "X is a solved problem", "the key insight is", "X has a cost:", "the trade-off
    is", "the catch is"), and no praise adjectives (robust, powerful, elegant, seamless,
    crucial, critical, comprehensive, clean, efficient, flexible, convenient, graceful, novel).
    "robust" takes an object ("robust to a dropped connection") or is not written. A comparison
    names the baseline, the quantity, and the condition ("0.6x the pandas time for 10,000 rows
    on the test host"), or it is not made. No grading adjective on the code or its design
    ("proper", "genuine", "real", "true", "clean", "cheap" as a judgement, "circular",
    "one-sided"), and no rhetorical antithesis in place of the condition ("data, not
    assertions", "behavior rather than mechanism" as a slogan, "The problem is the cache.");
    name the condition and its consequence.
  - **Verbs and nouns keep their technical meaning.** Code implements, follows, requires,
    returns, raises, reads, writes; it does not handle, take care of, inherit, suffer from,
    struggle with, unlock, live in, or do anything gracefully. A quantity is measured, bounded
    or exceeded; a buffer, port, or store does not hold, carry, achieve, or deliver a result.
    "captures" is not a catch-all verb. Name a thing once and reuse the noun: no renaming to
    "this pipeline", "this chain", "this logic", "the machinery" by free association. A
    measured quantity has, equals, or averages a value; an output, estimate, or attribute does
    not "read", "see", or "report" a level, a level does not "sit" or "land", and a mode does
    not "sit at" a value. "Referred to" takes a reference plane, temperature, or impedance,
    never a bandwidth or an attribute.
  - **The design is not personified.** An abstract noun about the code (the design, the
    contract, the invariant, the intent, the approach, the fix, correctness, the argument for a
    choice) does not carry, anchor, earn, buy, pay for, hold up, stand, grow, feed, drive, or
    turn one thing into another. State what the code does, what the caller must satisfy, or
    what the check verifies. Not "the lock earns its place in the hot loop" but "the lock
    serializes VISA access from the acquisition and logging threads".
  - **Nouns keep their category.** The estimate is a number, the estimator the algorithm, the
    method the approach, the output what is stored; a pronoun may not carry a subject across
    them ("the estimate ... it assumes a reference"). Substitute the antecedent for every "it"
    and check that the verb still fits.
  - **Metadata keys are objects, not agents.** An attribute, field, or column name is the
    object of set, read, copy, remove, or equal: "the `units` attribute is set to `'dBm'`". It
    does not take, gain, lose, carry, record, or spell out anything, and "the attribute" alone
    is not a noun; name the key, in backticks, once per sentence.
  - **No placeholder noun for an unstated claim.** "this behavior", "edge cases", "the
    result", "the logic", "various", "etc.", "as expected", "the right thing", "what it does",
    "the present context" stand in for a condition or claim the text never states. Write the
    condition.
  - **Subject first, one claim per sentence.** The subject and its verb sit within about eight
    words, and the verb that states the relation (fails, requires, exceeds, removes) comes in
    the first clause, not at the end of a relative clause or behind a weak verb plus abstract
    noun ("has a requirement that ..."). Qualifiers such as rounding, units, and conditions
    follow the main clause: "the timeout is the value, rounded to 1 ms", not "rounded to 1 ms,
    the value is the timeout". No appositives: a comma-bounded phrase that renames or locates
    the noun before it ("the backend, a serial port, returns") gets its own sentence or is
    dropped. No comma-joined independent clauses, and no chain of caveats in one sentence: one
    sentence per condition with its consequence. A semicolon does not append a critique to a
    description. Test: cut the sentence after its first verb; if the claim is not yet stated,
    rewrite. The claim does not sit in a trailing relative clause; the clause is cut or becomes
    the main verb of the sentence. No reduced relative clause stacking an event on a noun ("the
    device opened when the rack started"): name the thing ("the open device") and give the
    event, if the reader needs it, a sentence of its own. A docstring that applies several
    rules states each as "condition: what is set", one list item per rule, with no numbered
    narrative and no appositive after the consequence.
  - **A colon announces a specification, list, or restatement.** It does not replace
    "because", "so", "which means" or "for example" between two clauses. Replace it with a
    period and see whether a connective is then missing.
  - **No personal pronouns, no "whose".** Not "I", "we", "our", "us", "you", "your", or
    "let's", and not "they", "their", or "them" standing for a variable, attribute, device, or
    quantity: repeat the noun. Not "whose": a relative clause on a possessive is rewritten
    with the noun ("the devices whose timeout exceeds" becomes "the devices with timeout
    above"). "it" and "its" are allowed once per paragraph when the antecedent is the subject
    of the previous sentence; otherwise repeat the noun ("the `timeout` attribute of the
    device", not "its `timeout` attribute"). No sentence addressed to a reader or writer ("you
    are editing", "needs your attention", "once you commit"). This applies to every comment
    and docstring and to any prose file written into the repository, including reports and
    notes.
  - **Words that are not written.** Hedges and fillers: "should" where "must" is meant, "try
    to", "attempt", "safely", "properly", "simply", "just", "basically", "essentially",
    "effectively", "note that", "it is worth noting", "make sure", "sanity check", "for
    convenience", "under the hood". Person and narration: "we", "our", "you", "let's", "first
    we ... then we ...", "the following", "this will". Connective openers: "Additionally,",
    "Moreover,", "Furthermore,", "Importantly,", "In other words", "In order to" ("Further,"
    and "Thus," are the plain forms). Lexicon: "utilize" (use), "towards" (toward), "in
    practice", "trivial" (straightforward), "crucial"/"vital" (key), "very" as praise, "ground
    truth" outside quotation marks. No performance boasts ("with speed optimizations"): state
    the cost or nothing. Idioms and effort estimates: "an afternoon's work", "low-hanging
    fruit", "should go", "a leftover", "earns its place", "going forward", "at the end of the
    day", "in the other direction"; write the task, the deletion, or the number. Relative
    possessive: "whose".
  - **Mechanics.** Digits for counts ("3 devices", "2 ports"); the Oxford comma; "e.g.," and
    "i.e.," with the trailing comma.
  - **Check.** After editing, re-read every comment and docstring you touched against this
    list, in addition to the re-read passes under **Comments** and **Docstrings**. Delete or
    rewrite what fails. A sentence proposed by a reviewer, an agent, or a search-and-replace is
    new prose: re-read each one in place against every check before accepting it. A rewrite
    applied from a list is how the habits above return.

## Testing

`tests/` is flat and has no `conftest.py`: one `test_<topic>.py` per area (`test_rack.py`,
`test_paramattr_value.py`, `test_pyvisa.py`, ...), and shared helpers are plain modules
imported by bare name (`from paramattr_tooling import ...`, `module_as_testbed.py`) because
pytest's prepend import mode puts `tests/` on `sys.path`. Add new tests to the existing module
for the area rather than creating a file per feature. A change runs under `pixi run test` and,
when it touches the Python-version floor or syntax, under `pixi run -e test312 test` as well. Fixtures are module-local; several
modules use an autouse module-scoped fixture for setup. Simulated devices come from
`labbench.testing`.
