# SPEC-103: Decline stdout attribution for the RED gate, declare what a green verdict licenses, and remove the four over-refusals the attempt introduced

> Linked Issue: ISSUE-103
> Status: `accepted`
> Date: 2026-11-07
> Author: claude-dev-kit (implement phase, dogfooding)

## Problem

`verify_implement_red` has deliberately inverted logic: a non-zero test-run exit is the expected RED
outcome. ISSUE-103 was filed because the run was unscoped, so **any** unrelated pre-existing failure
certified the TDD RED phase. Scoping the argv to the branch's own changed test files closed that.
Requiring the failure to be **attributed** to one of those files — parsed out of pytest's
`short test summary info` section — did not, and that is what this SPEC decides.

Two review cycles reproduced a defect of the same class at **three successive layers**, including
inside the previous fix's own new code. The last cycle's proposed remedy was *slice the parse at the
`short test summary info` header*. This SPEC measures that remedy, finds it unsound at every slice
position, and takes the only disposition the measurements support: **stop claiming the property**,
write down exactly what a green verdict does license, and — separately and non-negotiably — remove
the four **over-refusals** the attribution attempt introduced, because an over-refusal that fails
closed is still a defect and may not stay blocking.

The issue's four ACs name none of this surface, which is review lesson 14 exactly: work added to
satisfy a request for a decision ships without acceptance criteria, and that is where the defects
are. So the criteria are stated here and each one has its own test.

## Context

Every number below was re-measured in the ISSUE-103 worktree on 2026-11-07 against the committed
tree at branch tip `d0fac1f`, on **pytest 8.3.4** (the interpreter the gate's child actually runs,
`python3 -m pytest`) and **pytest 9.0.3** (`uv run --extra dev`), **npm 11.5.2 / node v22.18.0**,
Python 3.12.7, darwin. Nothing is quoted from a prior table; where a supplied figure failed to
reproduce, that is recorded rather than smoothed over.

### C1 — The forgery table: no parse position is a fixed point

Probe: a throwaway repo per shape. Ground truth in every forged row is that the branch's own test
**passes** (`assert True`); the non-zero exit comes from an unrelated `extra_tests/test_extra.py`
that the project's own `addopts` inject. The scoped argv is exactly the gate's:
`python3 -m pytest -q --tb=short -rfE tests/test_new.py`. Three parse positions are evaluated over
the captured stdout: the whole stream (what shipped), the tail after the **first**
`short test summary info` header, and the tail after the **last** one.

| shape | in-model writer | whole-stdout | slice-**first** | slice-**last** |
|---|---|---|---|---|
| A | a failing test PRINTS a fake header + `FAILED <branch file>` | forged | **forged** | defeated |
| B | `conftest`'s `pytest_sessionfinish` prints them | forged | **forged** | defeated |
| C | `conftest` registers an **`atexit`** handler | forged | forged | **FORGED** |
| D | `conftest`'s **`pytest_unconfigure`** hook | forged | forged | **FORGED** |
| E | **`os.write(1, …)`** from an `atexit` handler, bypassing capture | forged | forged | **FORGED** |
| F | `--no-summary` + a test printing a fake header | nothing blamed | nothing blamed | nothing blamed |
| control | genuine RED, no forgery | blames correctly | blames correctly | blames correctly |

**All seven rows reproduce identically on 8.3.4 and 9.0.3.** The control is what makes the probe
valid: a parse that blamed nothing in every row would score the same on the forged rows for the wrong
reason.

In C, D and E the real header and the forged header **both** appear, and the forgery lands *after*
pytest's own reporter has finished. Measured child stdout for C/D/E on 9.0.3 (8.3.4 is identical
modulo four plugin warning lines):

```
  1| F.                                                                       [100%]
  2| =================================== FAILURES ===================================
  3| __________________________________ test_extra __________________________________
  4| extra_tests/test_extra.py:2: in test_extra
  5|     assert False
  6| E   assert False
  7| =========================== short test summary info ============================
  8| FAILED extra_tests/test_extra.py::test_extra - assert False
  9| 1 failed, 1 passed in 0.01s
 10| =========================== short test summary info ============================     <- forged
 11| FAILED tests/test_new.py::test_new_feature - forged                                  <- forged
```

So "take the last occurrence" is not a fixed point either: **project configuration can always write
later than the reporter.** Three of the five writers (B, C/D via `conftest`, E via `conftest`) are
the same trust class `addopts` already is — ordinary project configuration, requiring no cooperation
from any test.

### C2 — Review lesson 4 at its limit

Review lesson 4 reads: *a hand-rolled parser that mirrors an oracle must match the oracle's edge
cases.* This is that lesson at its boundary, and the boundary is where it stops being actionable.
The oracle here is a **human-readable stdout stream that the subject under test, and the project
configuration that runs it, may extend after the oracle has finished speaking.** Edge-case parity is
therefore not the deficiency: there is no position in the stream at which the oracle's authority
ends, because the last writer wins and the gate does not choose the last writer. The correct
disposition for a parser whose oracle has no boundary is to stop claiming the property, not to chase
a slice.

### C3 — The provenance finding, recorded as this SPEC's own lesson because it is a general hazard

Review 1 filed this exact root cause as a **Medium**, on the explicit stated ground that *"the
verdict is driven by the exit code, so this cannot flip the gate — which is why it is Medium and not
High."* That rationale was correct when written. The F1 fix then made **attribution** drive the
verdict, which **voided the rationale** — and nobody re-derived it. Worse, the rework *refactored*
the parse into `_blamed_test_files` and widened it to two call sites per verdict while leaving
`_PYTEST_SUMMARY_RE` byte-identical.

Two general hazards, which this SPEC records because they are not facts about this gate:

1. **A deferred finding's severity rationale can expire when the code it was conditional on
   changes.** A severity is an argument, not an attribute. "This cannot flip the gate" is a claim
   about the surrounding control flow, and the next PR is free to change the control flow.
2. **A refactor that preserves a defect verbatim can promote it.** Moving an unfixed parse into a
   named helper and giving it a second caller changed its severity without changing one byte of it.

### C4 — The npm residual, restated to what was actually measured, and a supplied figure that did NOT reproduce

The committed hazard note claimed npm's residual hole is *"exactly 'nothing ran AND npm chose exit
1', not every no-run route"*. **That bound is FALSE.** Measured: a `test` script whose runner rejects
the jest-specific `--passWithNoTests` that the gate injects runs nothing and exits non-zero outside
the stated bound.

```
runner rejects --passWithNoTests (script exits 9)  -> npm test exits 9
node: bad option --passWithNoTests                 -> npm test exits 9
```

This is the previous agent's own disclosure becoming the defect: **a disclosed residual is a CLAIM**,
and it was pinned only by a test asserting the comment contains the substring `no_run_codes`. The
corrected bound, now in the note, is: *for npm any non-zero exit other than 124 or 127 certifies
RED*, which includes no-run routes outside exit 1.

**Recorded both ways, because a finding that is correct for the wrong reason gets inherited as
fact — and here the correction itself failed to reproduce.** This SPEC was dispatched with the
instruction to record that *"npm collapses a script's own non-zero code to 1 in every case (`exit
1/4/5/9/42/124/127` all → 1), so 'npm forwards codes verbatim' is wrong and the 127 branch is
sound."* Re-measured directly on npm 11.5.2 / node v22.18.0, with each exit status captured from the
command and not through a pipe:

```
script exits 1   -> npm test exits 1        script exits 42  -> npm test exits 42
script exits 4   -> npm test exits 4        script exits 124 -> npm test exits 124
script exits 5   -> npm test exits 5        script exits 127 -> npm test exits 127
script exits 9   -> npm test exits 9
no `test` script          -> npm test exits 1
`test` script binary absent -> npm test exits 127
```

**npm forwards the script's exit code verbatim.** The reviewer's mechanism reproduces; the
counter-measurement does not. The consequence is recorded rather than acted on: a failure-count
runner (the mocha/tap convention, exit code = number of failures capped at 255) at **exactly 127
failures** is refused by the 127 branch as "could not be executed". That is an over-refusal, and
this SPEC does not remove it — it is a two-line change to a behaviour that three tests pin as
measured-good, it is outside this pass's change list, and removing it would re-open "the runner was
never executed certifies RED" for npm. It is carried in Open Questions with the measurement attached
so the next decider does not have to re-derive it.

### C5 — The colour over-refusal (H3) and the measured override

`_PYTEST_SUMMARY_RE` is anchored at `^` on raw bytes, so a summary line beginning with an SGR escape
matches nothing. pytest forces markup from `addopts = "--color=yes"` and also when the inherited
environment sets `PY_COLORS` or `FORCE_COLOR` — `_run` passes no `env=`, so the child inherits
whatever the runner exports, and `FORCE_COLOR` is set by default in a number of CI runners and
developer shells. Every row has a genuinely **failing** branch test, so every `blamed=[]` row is a
refused genuine RED:

```
control (no colour forced)         exit=1 header=True  blamed=['tests/test_branch.py']
FORCE_COLOR=1                      exit=1 header=True  blamed=[]          <- H3
PY_COLORS=1                        exit=1 header=True  blamed=[]          <- H3 sibling
FORCE_COLOR=1 + --color=no         exit=1 header=True  blamed=['tests/test_branch.py']
PY_COLORS=1  + --color=no          exit=1 header=True  blamed=['tests/test_branch.py']
addopts="--color=yes"              exit=1 header=True  blamed=[]
addopts="--color=yes" + --color=no exit=1 header=True  blamed=['tests/test_branch.py']
```

Identical on 8.3.4 and 9.0.3. A command-line `--color=no` overrides all three vectors.

### C6 — `--no-summary`, and the measurement that changed the prescribed fix

`-rfE` on the command line overrides a project's `-r` setting but **not** its `--no-summary`, so such
a project was refused on every genuine RED. Measured, genuine failure, `addopts = "--no-summary"`:

```
8.3.4: exit=1 header=False stdout='F ... [100%]\n1 failed, 2 warnings in 0.01s\n'
9.0.3: exit=1 header=False stdout='F ... [100%]\n1 failed in 0.01s\n'
```

Both the summary section and the traceback section are gone, so no per-file oracle exists anywhere in
the stream. **But header absence alone does not mean "could not compute", and this is the measurement
that changed the shape of the fix.** pytest omits the header whenever there is nothing to report —
which is exactly F1's measured-good `--cov-fail-under` route:

| route | exit | header present | reported failures |
|---|---|---|---|
| genuine failure | 1 | **True** | yes |
| `--cov-fail-under`, test **passes** | 1 | **False** | **no** (`1 passed`) |
| `--cov-fail-under`, test fails | 1 | True | yes |
| `--no-summary`, test fails | 1 | **False** | **yes** (`1 failed`) |
| pytest absent (empty stdout) | 1 | False | no |

The dispatched prescription — "summary section ABSENT → uncomputable → fall back to the declared
weaker property" — taken on header absence alone would have turned the `--cov-fail-under` row from
REFUSE into PASS and regressed F1's measured-good half. The discriminator that works is **header
absent AND the counts line reports at least one failure or error**, which is what shipped
(`_summary_section_suppressed`).

### C7 — The `develop`-default permanent block (H4)

Confirmed by execution on a real clone: bare origin with `HEAD -> refs/heads/develop`, fresh clone,
feature branch from `origin/develop`, local `develop` deleted — the ordinary state of a clone that
never checks the default branch out.

```
_default_branch() -> 'develop'
  leg 1  merge-base HEAD develop            -> exit 128
  leg 2  rev-parse --verify --quiet develop -> exit 1
  _delta_base_unresolvable() => True   *** the repo can NEVER pass RED ***
  fix: rev-parse --verify --quiet origin/develop -> exit 0
  fix: merge-base HEAD origin/develop            -> exit 0  9ffffd145074
  fix: delta against that merge-base             -> ['tests/test_new.py']
```

### C8 — The three behaviours measured good, which this SPEC does not touch

Each was confirmed by reverting it and watching a real test die, so none is "simplified" here:

- **F2's hoist** — the uncomputable-delta determination sits upstream of the delta read. Pinned by
  `TestUncomputableDeltaPosition` (3 cases), which asserts `runs == []`, i.e. **ordering**, not
  output.
- **F1's pytest half** — a non-zero exit with nothing blamed is refused. Pinned by
  `test_nothing_blamed_coverage_threshold_real_consumer`, which drives real `pytest-cov` through the
  real consumer on the `--cov-fail-under` route (exit 1 alongside `1 passed`).
- **The exit-127 refusal** — pinned by `test_npm_exit_127_real_consumer` (real npm) and
  `test_exit_127_is_refused_for_both_runners`.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Slice the parse at the `short test summary info` header

- **Approach**: Locate the header and match only below it, treating a missing header as a third
  "could not compute" state. The remedy review 2 prescribed, in both the `find` (first) and `rfind`
  (last) variants.
- **Pros**:
  - Defeats shapes A and B at the `rfind` variant, which were the two reproductions review 2 ran.
  - Needs no new subprocess and no change to the gate's contract.
- **Cons**:
  - C1: `rfind` is forged by 3 of 5 shapes (`atexit`, `pytest_unconfigure`, `os.write(1)`), and
    `find` by 5 of 5. The forgeries land *after* pytest's own summary, so "the real header is always
    last" is false.
  - Three of the five writers are ordinary project configuration, the same trust class the gate
    already concedes for `addopts`.
  - C2: a parser whose oracle has no end position cannot be fixed by choosing a position.
  - It would leave the gate still **claiming** attribution, which is the thing H1 actually gets
    wrong.
- **Trade-off**: closes 2 of 5 measured forgery shapes for +1 slice position, leaving 3 of 5 forged
  and the claim intact.

### Option B: Make attribution trustworthy with a machine-readable channel

- **Approach**: Stop parsing stdout. Drive the child with a structured report — a JUnit XML file via
  `--junit-xml`, or a `-p` plugin writing a side-channel file — and attribute from that.
- **Pros**:
  - A file the gate names and the project does not write is genuinely outside the forgery classes
    C1 measures for stdout.
  - Would make attribution a real property rather than a heuristic, which is what the issue's AC-2
    reads as asking for.
- **Cons**:
  - It is new mechanism in answer to a request for a decision — the exact shape ISSUE-079 exists
    for, where ~49 unspecified engine lines shipped and **both** engine defects review found lived
    in that unrequested code.
  - `--junit-xml` is not forgery-free either: `conftest` can rewrite the file in `pytest_unconfigure`
    or an `atexit` handler, the same two writers C1 measures, so the class is narrowed rather than
    closed — and that narrowing is unmeasured here.
  - It does not address any of the four over-refusals, which are the live blocking defects.
  - Adds a temp-file lifecycle, a second parse format, and a dependency on a reporter plugin being
    installed in the consumer project.
- **Trade-off**: +1 new output channel and an unmeasured residual, buying 0 of the 4 measured
  over-refusals and an attribution guarantee this SPEC cannot bound.

### Option C: DECLINE the attribution property, declare what a green verdict licenses, and de-refuse

- **Approach**: Record that the gate can scope to the branch's own tests but cannot reliably
  attribute which test failed by parsing stdout. Keep the parse strictly as an additional **refusal
  filter**. Delete every rendered claim the declaration does not support, and remove the four
  measured over-refusals (forced colour, `--no-summary`, a non-`main` default branch, a polyglot
  repo's Python-only delta). Ship no new attribution mechanism.
- **Pros**:
  - It is the only outcome C1 supports: with 5 of 5 shapes forging the shipped parse and 3 of 5
    forging the strongest slice, a claim of attribution is false as shipped and false as prescribed.
  - The monotonicity argument (Decision, below) makes keeping the parse coherent: it can only remove
    PASSes, so forging it buys nothing.
  - It removes 4 blocking over-refusals, one of which (`FORCE_COLOR=1`) needs no project
    cooperation and permanently blocks `implement/red` for every issue in an affected repo.
  - Costs no new mechanism, no new subprocess, no new file format.
- **Cons**:
  - A green `implement/red` after this proves strictly less than the issue's AC-2 reads as asking
    for. AC-2's "names which of the branch's own test files failed" is met in the weaker form
    "names what the runner's summary blamed, flagged as heuristic".
  - The H2 shallow-clone two-dot diff and the dash-leading-filename argv injection stay inside the
    declared boundary rather than being fixed, so the gate still *requests* rather than *enforces* a
    scope.
  - A declaration is only honest if it is re-openable, and nothing mechanises the re-opener.
- **Trade-off**: +0 new attribution mechanism and +0 new refusals, removing **4** measured
  over-refusals and **1** false claim per PASS, against 3 of 5 forgery shapes left reachable by
  design rather than by oversight.

### Option D: Keep the claim and accept the forgery as a disclosed residual

- **Approach**: Leave the parse and the `— failing: <path>` line as they are, and write the forgery
  table into the hazard note as a residual.
- **Pros**:
  - Zero code change; the PASS line stays maximally informative.
- **Cons**:
  - C4 is the precedent against it: the previous pass's disclosed npm residual *was* the defect,
    because a disclosed residual is a claim and this one was measurably false. Disclosure did not
    make it true.
  - The four over-refusals stay blocking, which the hard rule forbids.
  - It leaves three successive layers of the same class unaddressed and invites a fourth.
- **Trade-off**: +0 lines changed, leaving 5 of 5 forgery shapes reachable, 4 over-refusals blocking
  and 1 false claim printed on every PASS.

## Decision

**Chosen: Option C**

**The property is DECLINED: the red gate can scope to the branch's own tests but CANNOT reliably
attribute which test failed by parsing stdout.** This is measured, not inherited — a disclosed
impossibility is as much a claim as a disclosed residual, and C1 is the measurement that earns it.

**What a green `implement/red` verdict licenses, and nothing more:**

> a test-runner invocation whose arguments were the branch's own changed test files exited non-zero,
> and the exit code was not one of the measured no-run codes.

It does **not** license "a test the branch added failed", and it does **not** license "only the
branch's tests ran".

### Why keeping the parse is coherent: attribution is monotone

The argument that makes the declaration consistent with retaining the parser. Attribution is used
**only** as an additional refusal filter, so it can only ever *remove* PASSes, never add one beyond
the declared property. In H1's construction the scoped run exits 1, and 1 is not a no-run code, so
the declared property **already holds** and PASS is inside the declared boundary. Forging attribution
therefore buys the forger nothing: it restores a PASS the declaration already licenses.

What is actually wrong in H1 is the **claim** `failing: tests/test_new.py`, which asserts an
attribution as established. **So H1 reduces, once the property is declared, to a text overstatement —
and deleting it is this pass's single most important change.** `_blamed_test_files`' docstring now
says the same thing where the next reader of the parser will see it.

### What is INSIDE the declared boundary

Enumerated, not described — a class described by its shape is how ISSUE-102's High 1 recurred. These
are the declaration, not defects:

1. **H2, the shallow-clone two-dot diff.** `_delta_base_unresolvable`'s both-legged predicate returns
   True only when `git merge-base HEAD <base>` finds no fork point **AND** `<base>` itself does not
   resolve. The standard CI `actions/checkout fetch-depth: 1` shape satisfies the first leg and not
   the second (no merge-base, but `main` resolves), so it falls through to a **two-dot**
   `git diff --name-only main`, which reports files **main** changed after the fork point. Those
   files exist in the worktree, survive `_existing`, and are **executed** as "the branch's own".
2. **The argv injection through the scope splat.** `*scoped` is splatted with no `--` separator. A
   directory named `-p no:cacheprovider` — a path the kit's own `test_dir_pattern` accepts — is
   consumed by pytest as a flag, after which the **whole suite** runs at exit 1 while the gate's own
   scope line reports a scope that was not applied.

Both are instances of one fact: **the gate REQUESTS a scope and cannot ENFORCE one.** That is why
every rendered scope line now reads `Scope requested:` rather than `Scope was:` — the gate may not
assert the scope was applied. Adding `--` before the scope paths would narrow the argv leg and **is
carried, not taken here**: it is a de-refusal, it is correct, and it belongs with the enforcement
carrier rather than mixed into a decision pass.

### What this Decision does NOT do

It does not re-tighten `_delta_base_unresolvable` (that would fix H2, which is carried, and in the
measured shallow-clone construction it would turn a PASS into a REFUSE — a new refusal this pass
forbids). It does not change `_default_branch()`, which has four other callers; the H4 rescue is
local to the red verifier, review lesson 8. It does not add `--` to either argv. It does not change
npm's `no_run_codes`. It files **no** preventive issue for the "test the new defence in the disarm
direction" pattern: ISSUE-081 was that issue, it consumed four review cycles, was dropped unmerged,
and SPEC-088 records an explicit DECLINE.

### The hard rule the de-refusals satisfy: an over-refusal cannot stay blocking

Declaring an over-refusal away is forbidden, so all four are fixed. Every code hunk in this pass is
either **the deletion of a claim** or **a de-refusal** — a change that strictly reduces the set of
inputs the gate blocks. No hunk adds a refusal. This issue's defects recurred at three successive
layers, each time as a newly introduced over-refusal, and that invariant is what stops a fourth.

1. **H3, forced colour** — `--color=no` is appended to the pytest argv. Measured in C5 to override
   `addopts = "--color=yes"`, `FORCE_COLOR=1` and `PY_COLORS=1`.
2. **The `--no-summary` sibling** — `_summary_section_suppressed` tells "could not compute" from
   "computed and empty" using the header's presence **and** the counts line, per C6. Suppressed falls
   back to the declared weaker property and says so, naming the knob; computed-and-empty still
   refuses, which keeps F1's measured-good half including the real `pytest-cov` route.
3. **H4, the `develop`-default block** — the resolvable remote-tracking form is tried before the
   delta is declared uncomputable, locally in the red verifier, and only on the path that previously
   returned False unconditionally, so no other input's behaviour changes. The genuine uncomputable
   refusal stays reachable and pinned.
4. **The polyglot block** — `has_python` is no longer discarded, and the JS branch is taken only when
   the branch's **own** JS test files are non-empty. A real JS repo's `.ts` files still route to npm
   and are never fed to pytest.

And one claim deleted beyond the PASS line: the "reported no test failure at all" diagnostic no
longer names "a coverage threshold … or pytest not being installed". Both were printed on the
forced-colour route, where neither is the cause. The gate cannot distinguish the remaining causes
from this stream, so it names none and prints the exact command to re-run instead.

## Trade-offs Accepted

- **A green `implement/red` proves less than it used to appear to.** That is the point; the
  appearance was false. ISSUE-103's AC-2 is met in the weaker form the declaration permits: the path
  is still named, the claim is not made.
- **Three of five forgery shapes stay reachable.** By design: the monotonicity argument says forging
  them restores a PASS the declaration already licenses, so the exposure is a *text* exposure that
  deleting the claim closes, not a verdict exposure.
- **H2 and the argv injection stay open.** Both are carried. The gate requests a scope; a consumer
  project can still widen what actually runs.
- **npm's residual is wider than the previous note claimed, and it is not closed here.** Any non-zero
  exit other than 124 or 127 certifies RED for npm, including no-run routes at exit 9 (C4).
- **The 127 refusal can refuse a failure-count JS runner at exactly 127 failures.** Measured in C4,
  carried, deliberately not removed in this pass.
- **A mixed-extension delta in a polyglot repo still routes only to npm**, so a Python test in the
  same commit is not executed. This is the pre-change runner choice, kept so the JS mis-run
  protection stays intact; narrowing it is a runner-selection question, not a declaration one.
- **No test pins the Decision's content, and none can.** The tests pin the four de-refusals, the
  deleted claims, and the ordering the H4 rescue and F2's hoist both require. They do not pin that
  DECLINE is correct.
- **`_summary_section_suppressed` is itself a hand-rolled parse of the same untrustworthy oracle.**
  Accepted on the monotonicity argument: it can only move a REFUSE to a PASS inside the declared
  property, so forging it buys nothing a forger does not already have.
- **`--color=no` is the one hunk whose de-refusal has a boundary, and it is stated rather than
  claimed away.** It was measured as a no-op on plain output and as a rescue on all three colour
  vectors, on pytest 8.3.4 and 9.0.3 only. `--color` has existed since pytest 2.5, so a consumer on
  pytest **< 2.5** would see it rejected as an unknown option (exit 4, which `no_run_codes` refuses)
  where the run might previously have passed. That version predates this kit's Python 3.11+ floor by
  about a decade and is not measured here. If it ever bites, the fix is to drop the flag and strip
  SGR sequences from the stream before matching instead.

## Migration

No data migrates and nothing is deployed, enabled or disabled. The steps, all inside this PR:

1. Write this SPEC at `docs/specs/SPEC-103.md`, `Status: accepted`.
2. `scripts/verify_checkpoint.py`: delete the `— failing: <paths>` claim from the PASS line and
   replace it with the summary-blamed fact plus the heuristic flag and the citation; rename every
   `Scope was:` to `Scope requested:`; delete the two wrong causes from the "no test failure at all"
   diagnostic; add `--color=no` to the pytest argv; add `_summary_section_suppressed` and the
   could-not-compute fallback; add the H4 remote-tracking rescue inside the existing refusal branch;
   stop discarding `has_python` and gate the JS branch on the branch's own JS test files; correct the
   hazard note's npm bound to the measured truth.
3. `tests/test_red_gate_scoping.py`: add the classes pinning each of the above, plus the two existing
   cases that pinned the deleted claim, updated to the new wording.
4. No template changes, so `python3 scripts/gen_skills.py` leaves `git status --porcelain` empty and
   `tests/test_gen_skills.py` cannot drift.
5. Registry fields on ISSUE-103 (`Spec:`, `Status:`) are written on main by team-lead under
   `scripts/registry_edit.sh`; this PR does not touch `issues.md`, `CHANGELOG.md` or
   `docs/sprint_state.md`.

## Rollback

`git revert` the PR. The revert direction is **not** uniformly safe and that must be stated plainly:

- Reverting the four de-refusals restores four blocking over-refusals, one of them
  (`FORCE_COLOR=1`) triggerable by a single environment variable with no project cooperation. That
  is the dangerous direction.
- Reverting the claim deletions restores a PASS line that asserts an attribution C1 measures as
  forgeable by 5 of 5 shapes. That is a record regression, not a safety one.
- No hunk in this PR turns a FAIL into a PASS outside the declared property, so a revert cannot close
  a hole this PR opened — there is none to close.

Prefer amending this Decision over reverting it. The signal that should trigger a **re-open** rather
than a rollback is the measured re-opener below.

**The re-opener, recorded so that declining does not become unfalsifiable:**

> If an attribution channel is ever measured as unforged against **all five** shapes in C1 — in
> particular against a `conftest` that writes in `pytest_unconfigure`, from an `atexit` handler, and
> via `os.write(1)` — then the property becomes claimable in fact and the claim may be restored to
> the PASS line. Until that measurement exists, any restored claim is Option D with extra steps.

A rollback must not silently re-introduce a refusal. If a revert of this PR makes any input the gate
currently passes start failing, it has reverted more than this PR's claim deletions.

## Open Questions

Each is a residual this SPEC does **not** close, with a durable carrier rather than prose — review
lesson 15. A PR body is not a durable carrier, and `docs/sprint_state.md` is archived at each sprint
boundary, so it is not one either. **Carrier ids are not allocated here**; each entry describes
precisely what its carrier must contain.

- [ ] **The scope-ENFORCEMENT routes, enumerated.** The gate requests a scope and cannot enforce one;
      four measured routes make the executed set differ from the requested set. (a) `addopts`
      injecting an extra test path, so an unrelated file fails inside the scoped run. (b) `addopts`
      carrying a coverage threshold, so the exit code is not about any test. (c) The dash-leading
      filename argv injection — a directory named `-p no:cacheprovider` is consumed by pytest as a
      flag and the whole suite runs at exit 1; the fix is a `--` separator before the splat on both
      argvs, measured correct and deliberately not taken here. (d) The shallow-clone two-dot diff
      (H2, Decision item 1), wanting either a single-legged `_delta_base_unresolvable` for this
      caller or a three-dot diff; note that in the measured `fetch-depth: 1` construction either fix
      turns a current PASS into a REFUSE, so it needs its own disarm-direction measurement before it
      ships — owner: team-lead, by: batched carrier filing after this ships.
- [ ] **Mutant M20 — npm's legacy contract is pinned for exits 1 and 127 but not for 4 and 5.**
      Changing npm's `no_run_codes` from `()` to `(4, 5)` survives the suite (re-verified in this
      pass's own 25-mutant battery, in which it is 1 of only 2 survivors). That mutation is an
      **over-refusal** that would break npm's
      legacy "non-zero is RED" contract, which review lesson 8 requires to be pinned when a new
      caller class tightens a shared contract. The carrier must specify the fix as *behavioural*
      assertions — npm at exit 4 and at exit 5 still returns True with the attribution-unavailable
      line — and must say that the existing comment-text guard is not to be kept alongside them,
      because record-accuracy tests are issue generators. Deliberately not pinned in this pass: the
      declaration dispatch assigns it to a carrier, and pinning it here would make the carrier a
      false record — owner: team-lead, by: batched carrier filing after this ships.
- [ ] **Mutant M14 — widening the attribution call from `scoped` to `all_test_files` is unpinned.**
      Recorded honestly by review 2 as a narrowing it could not turn into a behavioural difference,
      because the two sets differ only by non-`.py` paths and pytest does not blame those unless a
      custom collector is installed. Re-verified as surviving in this pass. The carrier must state
      the construction that would make it behavioural (a project installing a collector for a
      non-`.py` extension) or record the mutant as **equivalent** and close it — owner: team-lead,
      by: batched carrier filing after this ships.
- [ ] **npm forwards exit codes verbatim, so the 127 refusal is an over-refusal for a failure-count
      runner.** Added by this pass's own measurement, which **contradicts the figure this SPEC was
      dispatched with** (C4). npm 11.5.2 / node v22.18.0 passes 1, 4, 5, 9, 42, 124 and 127 through
      unchanged, so a mocha/tap-convention runner at exactly 127 failures is refused as "could not be
      executed", and at 124 as "timed out" with no timeout. The carrier must carry the measurement
      table, must note that the fix is to distinguish `_run`'s **synthesised** 124/127 (which the kit
      does know about) from a code the child chose, and must note that three tests pin the current
      127 behaviour as measured-good so the change needs its own disarm-direction run — owner:
      team-lead, by: batched carrier filing after this ships.
