# SPEC-114: Close the RED gate's argv-injection scope route, decline the shallow-clone route, and make the gate stop claiming a scope it could not compute

> Linked Issue: ISSUE-114
> Status: `accepted`
> Date: 2026-11-15
> Author: claude-dev-kit (implement phase, dogfooding)

## Problem

`verify_implement_red` passes the branch's own changed test files to the test runner as arguments.
SPEC-103 closed ISSUE-103's whole-suite defect that way and then recorded, in writing, that the
result is weaker than it looks: **the gate REQUESTS a scope and cannot ENFORCE one.** Every rendered
line says `Scope requested:` for that reason.

This is the adjacent and **different** property from the one SPEC-103 declined. SPEC-103 declines
**attribution** — which test failed. This SPEC decides **scope enforcement** — whether the set the
runner executed equals the set the gate asked for. Attribution is not re-opened here, and nothing
below depends on it being trustworthy.

SPEC-103's Open Question 1 enumerated four measured routes that make the executed set differ from
the requested set. The issue exists so a later pass does not rediscover them one at a time. Each is
closed with a test or declined with its reason, and route (d)'s declination is the one that matters,
because both of its candidate fixes are measured to **block legitimate work**.

The issue's four ACs name the routes but name none of the output surface the decision changes, which
is review lesson 14 exactly — work added to satisfy a request for a decision ships without
acceptance criteria, and that is where the defects are. So the criteria are restated here with a
test each.

## Context

Every number below was measured on 2026-11-15 in scratchpad constructions against the committed tree
at main `29b52ef`, on **pytest 9.0.3** (both the `python3 -m pytest` child the gate really runs and
`uv run --extra dev`), **npm 9.8.1 / node v18.18.0**, **git 2.44.0**, darwin. The canonical suite
verdict on main is `uv run --extra dev pytest -q` → **2821 passed, 1 skipped**.

Two earlier probe attempts self-falsified and the corrections are recorded rather than smoothed over:
a `master`-vs-`main` default-branch mistake, a `git clone --depth` that is **silently ignored on a
local path** (a `file://` origin is required to get a shallow clone at all), and a `mkdir` that ate
its own dash-leading argument (`mkdir -p --` is required).

### C1 — Route (c) reproduces, and it cuts in BOTH directions

A directory named `-p no:cacheprovider` holding `test_dashfile.py`. The path
`-p no:cacheprovider/test_dashfile.py` is accepted by the gate's own `test_pattern`, so it is a path
the gate will splat. Two facts make it reachable rather than theoretical:

1. **git does not quote it.** `git diff --name-only --cached` and
   `git ls-files --others --exclude-standard` both emit `-p no:cacheprovider/test_dashfile.py`
   verbatim — `core.quotePath` is unset by default and a space is not an escaped character — so the
   path survives into the delta and `_existing` keeps it.
2. **argparse consumes it before the space check.** `_parse_optional` calls `_get_option_tuples`
   *before* its "if it contains a space, it was meant to be a positional" guard, and for a
   single-dash token that helper matches the two-character prefix `-p` and hands the remainder over
   as an explicit argument. pytest's own `consider_preparse` then does `parg.strip()`, so the value
   begins with `no:` and blocks a plugin named `cacheprovider/test_dashfile.py` — a name nobody
   registered, so **no usage error is raised and nothing is printed.** The `no:` prefix is what makes
   the route silent; `-p foo/…` would raise and exit 4.

Measured, real pytest 9.0.3, the gate's exact flag prefix
(`-q --tb=no -rfE --color=no`), rootdir holding a pre-existing failing `tests/test_unrelated.py`:

| # | argv tail | executed set | exit |
|---|---|---|---|
| c1 | `<dashpath>` | **the whole rootdir** — `tests/test_unrelated.py` ran and was blamed | 1 |
| c1' | `-- <dashpath>` | the dash file only | 1 |
| c3 | `<file> <dashpath>` | **`<file>` only — the dash file never ran** | **0** |
| c3' | `-- <file> <dashpath>` | both | 1 |

**c1** is ISSUE-103's whole-suite defect re-entering through a *filename*: zero positional paths
survive, pytest collects from rootdir, and any standing failure is in the run. **c3** is the
opposite and was missing from the issue text: the requested set is silently **shrunk**, the run goes
green, and the gate refuses with the false reason "tests passed but should fail" — a refusal of
legitimate work, which is the expensive direction under this project's governing asymmetry.

**Disarm direction for the `--` fix, measured on the same tree:** ordinary paths and a nodeid behave
identically with and without the separator — `exit 0`, `1 passed`, in all four rows
(`<file>`, `-- <file>`, `<file>::<test>`, `-- <file>::<test>`). The separator adds **zero** refusals
on ordinary input.

### C2 — npm forwards the second `--`, and a conforming parser honours it

> **AMENDMENT — 2026-11-15. This section's conclusion is WRONG and the second `--` has been
> withdrawn from the npm argv.** The section is left standing rather than rewritten, because the
> shape of the error is the lesson: every measurement below is accurate, and the conclusion drawn
> from them is false. The oracle was `util.parseArgs`, which **no JS test runner is** — nothing in
> the gate ever hands its argv to `parseArgs`. Measured at the real consumer (vitest 3.2.7,
> node v18.18.0, npm 9.8.1), a fixture of two passing test files:
>
> | argv | test files executed |
> |---|---|
> | `npm test` (no scope — control) | **2** |
> | `npm test -- --passWithNoTests tests/a.test.ts` (one separator) | **1** — scope honoured |
> | `npm test -- --passWithNoTests -- tests/a.test.ts` (this section's fix) | **2** — scope **deleted** |
>
> The second separator does not protect the scope; it discards it, and the effect is identical to
> sending no scope at all. Because the npm leg has `no_run_codes = ()` and
> `attributes_failures = False`, nothing downstream notices the widened set: an unrelated failing
> file certifies the TDD RED phase while the branch's own new test passes, and the gate prints a
> scope it did not apply. That is a **certified false RED outside SPEC-103's declared property**,
> which is "a run whose arguments were the branch's own changed test files" — strictly worse than
> the shrink direction this section set out to close, and worse than `main`, which refuses the
> identical construction.
>
> The last item in Open Questions — "the npm separator is unmeasured against real JS runners" —
> is therefore **resolved, against this section**. It was filed as a residual to measure later; the
> measurement arrived during review and disqualified the decision it was a residual of. The
> repair, and the half of route (c) that is consequently disclosed rather than fixed, are in
> *Route (c) — the npm half* below.
>
> What generalises: "the separator is forwarded" and "the separator is honoured" are different
> claims about different programs, and only the first was measured at the real consumer. A
> stand-in oracle chosen for conformance tells you what a conforming parser would do, not what the
> installed one does — and the gate's correctness depends on the installed one.

The npm argv already contains one `--` (`npm test -- --passWithNoTests`), so the fix makes it
`npm test -- --passWithNoTests -- *scoped`. That npm forwards a *second* separator was **measured,
not assumed** — a `test` script that prints its own `"$@"`, npm 9.8.1 / node v18.18.0:

```
npm test -- --passWithNoTests tests/a.test.ts <dashpath>
    ARGC=3  ARG1=[--passWithNoTests]  ARG2=[tests/a.test.ts]  ARG3=[<dashpath>]
npm test -- --passWithNoTests -- tests/a.test.ts <dashpath>
    ARGC=4  ARG1=[--passWithNoTests]  ARG2=[--]  ARG3=[tests/a.test.ts]  ARG4=[<dashpath>]
```

The separator arrives verbatim, in position, with the scoped paths behind it.

That it is *useful* was measured too, against node's own `util.parseArgs`
(`strict: false, allowPositionals: true`) as a conforming POSIX-convention parser:

| input | parse result |
|---|---|
| `--passWithNoTests <file> <dashpath>` | `positionals: ["<file>"]` — the dash path is **gone**, shredded into 22 single-character boolean flags (`p`, ` `, `n`, `o`, `:`, …) |
| `--passWithNoTests -- <file> <dashpath>` | `positionals: ["<file>", "<dashpath>"]` |
| `--passWithNoTests -- <file>` | `positionals: ["<file>"]` |
| `--passWithNoTests <file>` | `positionals: ["<file>"]` |

So the JS leg has route (c)'s **shrink** direction too, the separator closes it, and on ordinary
input the two forms produce byte-identical parses — zero refusals added.

### C3 — Routes (a) and (b) are ALREADY closed, measured at the real consumer

Both were measured through `bash scripts/checkpoint.sh --skill implement --phase red` on throwaway
repos with registered worktrees and real pytest children, the branch's own test passing in each so
the exit code cannot be the branch's doing:

```
(a) addopts = "extra_tests"
    exit 1
    FAIL: RED phase — pytest exited 1 but blamed no test file in the branch's own
      delta — inconclusive, cannot verify genuine RED
      Scope requested: tests/test_branch_feature.py
      pytest blamed: extra_tests/test_extra.py — outside the branch's delta, …

(b) addopts = "--cov=src --cov-fail-under=50"
    exit 1
    FAIL: RED phase — pytest exited 1 but reported no test failure at all —
      inconclusive, cannot verify genuine RED
      Scope requested: tests/test_branch_feature.py
```

ISSUE-103's attribution filter refuses both, through the two arms it was built with: (a) the
`blamed … outside the branch's delta` arm, (b) the `reported no test failure at all` arm. **No new
production code is owed for (a) or (b).** What was missing is the pin in the *enforcement* frame
rather than the attribution frame — that on exactly these routes the rendered output does not claim
the scope was applied — and that is what this pass adds.

### C4 — Route (d): the `fetch-depth: 1` construction, and why both candidate fixes are refused

Construction, reproduced on git 2.44.0: a bare origin; `main` at c1 holding
`tests/test_shared.py`; a branch forked from **c1** adding a genuinely failing
`tests/test_branch_new.py`; `main` then advancing to c2, which **modifies** `tests/test_shared.py` —
a file that existed *before* the fork point, so `_existing()` cannot filter it. Then
`git clone --depth 1 file://<origin>`, `git fetch --depth 1 origin <branch>`, worktree at
`FETCH_HEAD`, local `main` deleted. Both HEAD and `origin/main` are grafted, so they have no common
ancestor *available in the clone*. Literal exits, measured in that worktree:

| probe | exit |
|---|---|
| `git merge-base HEAD main` | 128 |
| `git rev-parse --verify --quiet main` | 1 |
| `git merge-base HEAD origin/main` | **1** |
| `git rev-parse --verify --quiet origin/main` | **0** |

base=`main` is correctly judged unresolvable; SPEC-103's `origin/`-rescue fires; because
`origin/main` *resolves*, the two-legged conjunction in `_delta_base_unresolvable` is **False**, so
the gate proceeds against a base it has **no merge base with**. `_changed_files_vs_base` then falls
back to `diff_base = base` — a two-dot `git diff --name-only origin/main`.

The leak, measured:

| tree | computed delta |
|---|---|
| shallow, two-dot (what the gate does) | `tests/test_branch_new.py`, **`tests/test_shared.py`** |
| full clone, merge-base-anchored (TRUE delta) | `tests/test_branch_new.py` |

`tests/test_shared.py` is a file **main** changed after the fork point. It exists in the worktree, it
survives `_existing`, and it is **executed** as "the branch's own".

**AC-3's disarm direction, measured rather than discovered later.** The shipped gate PASSES this
construction, and that PASS is **legitimate work** — the branch has a genuinely failing new test.
Both candidate fixes were applied to scratchpad copies of `verify_checkpoint.py` and driven at the
real consumer against the same worktree:

```
control (shipped)                              exit 0
  PASS: RED phase — the branch's own tests fail as expected (exit 1)
    pytest's summary blamed: tests/test_branch_new.py

candidate-1  single-legged _delta_base_unresolvable      exit 1
  FAIL: RED phase — cannot compute the branch's test-file delta: neither 'main'
    nor 'origin/main' has a merge-base with HEAD or resolves in the worktree

candidate-2  three-dot diff (`git diff --name-only origin/main...HEAD`)   exit 1
  FAIL: no test files found — write tests before RED phase
```

Candidate-2's refusal is additionally **misdiagnosed**: `origin/main...HEAD` fails with
`fatal: origin/main...HEAD: no merge base` at exit 128, the delta comes back empty, and the gate
tells an implementer who wrote a failing test to go write tests.

**Both fixes turn a PASS into a REFUSE in every shallow CI checkout.** At depth 1 `HEAD` has no
parent available, so the branch's own delta is genuinely **uncomputable** there — no amount of local
work recovers it. That is the whole case against both.

### C5 — The residual the `--` separator does NOT close, measured

`--` stops **argparse**. It does not stop pytest's `consider_preparse`, which scans the raw `args`
list element by element with no `--` awareness and calls `consider_pluginarg` on anything starting
with `-p`. In the construction above that blocks a plugin named `cacheprovider/test_dashfile.py`, a
name nobody registered, so it is inert. A path named `-p no:main/…` would instead hit
`essential_plugins` and raise a `UsageError` (exit 4), which the gate already refuses as a no-run
code. Recorded as a residual, **not** closed: closing it would mean validating path shapes and
adding a refusal, which this pass may not do. The direction is fail-closed and inside the declared
boundary.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Make the executed set provably equal the requested set

- **Approach**: Enforce scope rather than request it. Run the child in a sandbox that cannot read
  the project's `pyproject.toml`/`setup.cfg`/`PYTEST_ADDOPTS`, pass `-p no:cacheprovider -c
  /dev/null`, and verify afterwards — from a machine-readable report — that the collected node-id
  set is a subset of the requested paths.
- **Pros**:
  - It is the only shape under which the gate could stop saying "requested" and start saying "was".
  - It would close (a) and (b) at their cause rather than at the attribution filter downstream.
- **Cons**:
  - `-c /dev/null` discards the project's own configuration, so a consumer project whose tests need
    its `addopts` (markers, plugins, import mode, `pythonpath`) stops collecting at all — that is a
    new refusal on legitimate work, which the governing asymmetry forbids outright.
  - The verification half needs a machine-readable channel (`--junit-xml` or a side-channel plugin),
    which SPEC-103 already weighed and declined as **new mechanism in answer to a request for a
    decision** — the ISSUE-079 shape, where ~49 unspecified engine lines shipped and **both** engine
    defects review found lived in that unrequested code.
  - It buys nothing for route (d): the delta is wrong *before* the runner is invoked, so no amount
    of runner sandboxing narrows it.
  - It is uncheckable for the npm leg, which has no equivalent of `-c`.
- **Trade-off**: +1 new output channel and an estimated +80 engine lines with no AC in this issue,
  buying 2 of the 4 routes while adding at least 1 new refusal class on legitimate projects and 0
  improvement to route (d).

### Option B: Fix route (c) on both argvs, decline route (d) with its measurement, and make the gate stop claiming a scope it could not compute

- **Approach**: Add a `--` separator before the scope splat on both argvs — the fix SPEC-103
  measured as correct and deliberately carried. Record (a) and (b) as already closed by ISSUE-103's
  attribution filter, with real-consumer pins in the enforcement frame. **Decline** both of route
  (d)'s candidate fixes on the measured PASS→REFUSE transition, and satisfy AC-4 instead: where the
  merge base is absent the reported scope is **unverified**, and the gate's own output says so.
- **Pros**:
  - Route (c)'s fix is a **de-refusal** in the direction that matters: measured, it turns c3's false
    "tests passed but should fail" refusal into a correct PASS, and its disarm rows add zero
    refusals on ordinary input for either runner.
  - Route (d) is handled by the rule that already governs this file — an over-refusal cannot be
    declared away, and symmetrically a fix that creates one may not ship. The declination is backed
    by an executed control/candidate matrix rather than by an argument.
  - AC-4 is met by **disclosure at one derivation point**, which is the shape SPEC-102's Finding 3
    requires: a per-site inventory of a class short by one is how this class recurred at three
    successive layers.
  - It adds **no** refusal anywhere. Every hunk is a de-refusal or a disclosure.
  - "A gate whose subject is COMPUTED must distinguish 'computed and empty' from 'could not
    compute'" is already applied to the *delta*; this applies it to the *scope line*, which is the
    same rule at the same gate.
- **Cons**:
  - Route (d) stays open. A shallow CI checkout still executes files `main` changed after the fork
    point as "the branch's own". The gate now says the scope is unverified; it does not stop it.
  - The scope is still **requested**, not enforced: (a) and (b) are refused downstream by a filter
    SPEC-103 itself declines as evidence, so the closure is monotone rather than positive.
  - C5's `consider_preparse` residual survives the separator.
  - One extra `git merge-base` invocation per red-gate run.
- **Trade-off**: +1 separator per argv and +1 disclosure line from +1 derivation point (about 12
  engine lines), closing 1 of 4 routes outright, recording 2 as already closed, and declining 1 —
  against +0 refusals added and 2 measured over-refusals (c3 on pytest, its `util.parseArgs`
  equivalent on npm) removed.

### Option C: Fix route (c) and take route (d)'s single-legged fix anyway

- **Approach**: As Option B for (a)–(c), but also narrow `_delta_base_unresolvable` for this caller
  so a missing merge base alone means "uncomputable".
- **Pros**:
  - The gate would stop executing files the branch never touched, which is the actual defect in
    route (d) rather than a disclosure about it.
  - Review lesson 8 is satisfied in form: the narrowing is scoped to the red verifier, the caller
    class that wants it, leaving `_default_branch`'s four other callers alone.
- **Cons**:
  - **Measured**: it refuses the construction in C4, where the branch has a genuinely failing new
    test. `actions/checkout` defaults to `fetch-depth: 1`, so this is the ordinary CI shape, not an
    exotic one — the gate would become unpassable there for every issue.
  - The refusal is also unactionable from inside the checkout: at depth 1 the fork point does not
    exist locally, so there is no step an implementer can take to satisfy it.
  - It takes the exact disposition SPEC-102's Finding 5 and SPEC-103's hard rule both forbid, in the
    file where that rule was written.
- **Trade-off**: −1 open route in exchange for **+1 measured over-refusal** that blocks every issue
  in every `fetch-depth: 1` checkout — a trade the governing asymmetry prices at infinite.

### Option D: Decline scope enforcement wholesale, change no code, document the four routes

- **Approach**: Write the four routes into this SPEC and the hazard note, change nothing.
- **Pros**:
  - Smallest possible diff; no behaviour changes at all.
  - Consistent-looking: one decision, one document, everything deferred.
- **Cons**:
  - It bounds route (c)'s **c3 direction**, which is an over-refusal — measured as a false "tests
    passed but should fail" on a branch whose dash-named test would have failed. SPEC-103's own rule
    forbids bounding an over-refusal, and SPEC-103 had already measured the `--` fix as correct and
    said it "belongs with the enforcement carrier". This is that carrier.
  - It leaves the gate claiming a scope on route (d) that it demonstrably could not compute, which
    is AC-4 unmet.
  - C4's precedent against it is this project's own: a disclosed residual is a CLAIM, and SPEC-103's
    npm residual *was* the defect because the disclosure was measurably false.
- **Trade-off**: +0 engine lines, leaving 2 measured over-refusals live (c3 on pytest, its npm
  equivalent) and 1 AC unmet, in exchange for 1 document.

## Decision

**Chosen: Option B**

Per route, in writing:

### Route (a) — `addopts` injecting an extra test path: **ALREADY CLOSED** (no new production code)

Measured at the real consumer in C3. ISSUE-103's attribution filter refuses it through the
`blamed … outside the branch's delta` arm, which names both the requested scope and the out-of-scope
file that was blamed. This pass adds the real-consumer pin in the **enforcement** frame: on this
route the output must not claim the scope was applied.

### Route (b) — `addopts` carrying a coverage threshold: **ALREADY CLOSED** (no new production code)

Measured at the real consumer in C3. Refused through the `reported no test failure at all` arm. Same
enforcement-frame pin added.

The closure for (a) and (b) is **monotone, not positive**, and that bound is stated rather than
left for a reader to supply: the filter can only ever remove a PASS. If the branch's own test *also*
fails on either route, the gate passes while the executed set is still wider than the requested
set — which is inside SPEC-103's declared boundary, since the declared property ("a run whose
arguments were the branch's own changed test files exited non-zero") genuinely holds.

### Route (c) — the dash-leading filename argv injection: **FIXED on pytest, DISCLOSED on npm**

> **AMENDMENT — 2026-11-15, part 2 of 2: the npm half.** The second `--` is **withdrawn**. Route
> (c)'s JS half ships **disclosed, not fixed** — which is exactly `main`'s behaviour.
>
> C2's amendment carries the measurement: on vitest 3.2.7 the second separator deletes the scope,
> so the whole suite runs and an unrelated failure certifies RED while the branch's own new test
> passes. The withdrawn fix was therefore not a partial fix with a residual — it **introduced a
> defect strictly worse than the one it closed**, and on the leg that cannot detect it
> (`no_run_codes = ()`, `attributes_failures = False`).
>
> Two repairs were admissible and the alternative is recorded because it is not obviously wrong:
> make the separator **conditional** on `any(p.startswith("-") for p in scoped)`, keeping it only
> where route (c) actually applies. It is **rejected**: it reintroduces scope deletion in precisely
> the dash-leading case route (c) is about, so it converts a visible shrink into an invisible
> widening exactly when the route fires. Trading a fail-closed over-refusal for a fail-open false
> pass is the wrong direction whatever the frequency, because **a declaration can license a false
> pass inside a stated boundary, and it can never license blocking legitimate work** — and here the
> conditional form takes the licensable side away.
>
> So the npm leg keeps **one** separator, npm's own, which is what forwards `--passWithNoTests` at
> all. A dash-leading JS test filename remains able to shrink the requested set on the npm leg;
> that is a fail-CLOSED over-refusal, visible in the gate's output, identical to `main`, and it is
> what the first Open Question below now carries.
>
> **AMENDMENT — 2026-11-15, part 1 of 2: the pytest half.** The pytest leg does **not** take a `--`
> separator either. The decision below is superseded for pytest.
>
> `--` was first carried rather than taken, because driving it at the real consumer measured it
> turning a PASS on legitimate work into a REFUSE. Then re-measuring found the refusal narrower than
> recorded *and* the benefit narrower too, so neither the original decision nor the carry was right.
> What ships is a **`./` prefix on every scoped path**:
>
> ```
> python3 -m pytest -q --tb=short -rfE --color=no ./tests/a.py ./tests/b.py
> npm test -- --passWithNoTests tests/a.test.ts             # see part 2 above
> ```
>
> **Why `--` is wrong for pytest, both measurements.** It adds a refusal: real consumer, a project
> whose `addopts` contribute a positional test path plus a branch whose test genuinely fails, on
> pytest 8.3.4 / Python 3.11.13 — plain `exit 1` PASS, `--` **`exit 4`** which the gate refuses as a
> no-run code, `./` `exit 1` PASS. The same refusal reproduces on 3.12.7 / pytest 8.3.4, so this
> cost tracks the **pytest version**.
>
> And it buys less than recorded, on an axis that depends on the interpreter **and** the pytest
> version — neither alone. Collected node-id SETS, the flag-shaped-directory rows, six
> (interpreter, pytest) pairs: 3.11.13/8.3.4 yes, 3.12.7/8.3.4 yes, 3.11.13/9.0.3 **no**,
> 3.12.3/9.0.3 **no**, 3.13.6/9.0.3 yes, 3.14.7/9.0.3 yes — and `./` yields the scoped set in all
> six. Holding the interpreter fixed at 3.11.13 and moving only pytest flips the answer, which
> falsifies the "interpreter rather than pytest" reading an earlier draft of this amendment carried:
> 9.0.3 is where `--` regressed for <=3.12. A direct `argparse.parse_args` probe honours `--` on all
> six, so the divergence lives in pytest's own `_parse_optional` override. This project declares
> `requires-python = ">=3.11"` and CI tests 3.11 and 3.12, so on the pair it actually runs — 9.0.3
> on 3.11 or 3.12 — `--` is INERT and closes nothing, while still adding the 8.3.4 refusal wherever
> that pytest is used. There is no cell in which it helps without cost.
>
> **A correction to this SPEC's own method, recorded because it is the more useful half.** An earlier
> pass of the four-interpreter measurement ran under bare `python3`, which on the dev host is 3.14.7,
> and concluded `--` worked. It does — on 3.14. Under the canonical `uv run --extra dev` 3.11.13 it
> does not. That is the same defect **ISSUE-118** carries about the blocking gate's own interpreter,
> arriving in a measurement rather than in a verdict: the canonical-environment rule governs
> *verdicts*, not only numbers copied into docs.
>
> **What the prefix closes, and what it leaves.** Over-collection is gone: the rootdir's standing
> failure is no longer reached. The silent-shrink direction is gone: the dash path now runs, so the
> false reason "tests passed but should fail" is unreachable. What remains is **narrower and already
> declared** — the dash path contains a space, so pytest's `FAILED <nodeid>` line cannot be parsed
> back to it and the gate blames `-p`. That sits inside **SPEC-103's declined attribution property**
> rather than being a new defect, and it **fails CLOSED** with a truthful reason. Removing the lie
> from a refusal is the gain; the refusal itself was never the defect.
>
> Attribution output is unaffected: pytest reports `FAILED tests/x.py::t` for both `tests/x.py` and
> `./tests/x.py`, measured, so the `FAILED <file>` parse and the `scoped` membership test still agree.

Measured as forwarded-and-honoured on npm (C2). The npm leg's double `--` is not an assumption:
npm 9.8.1 delivers `ARG2=[--]` with the scoped paths behind it, and `util.parseArgs` goes from
dropping the dash path entirely to keeping it. **[Superseded — see C2's amendment: forwarded is
measured and true, honoured is measured and false. The clause this paragraph leans on, "and
`util.parseArgs` goes from dropping the dash path entirely to keeping it", is a fact about
`parseArgs` and not about any installed runner.]**

The fix's direction is a **de-refusal**. c3 and its npm equivalent are over-refusals today — the
requested set is shrunk, the surviving subset goes green, and the gate blocks legitimate work with a
false reason. The disarm rows (ordinary paths, a nodeid, both runners) are byte-identical with and
without **what ships on pytest** — the `./` prefix — so nothing the gate passes today starts
failing. That is *not* true of a `--` on the pytest argv, which is precisely why part 1 of the
amendment rejects it there: on pytest 8.3.4 the disarm row goes PASS → REFUSE.

The npm half of this paragraph no longer applies, and the correction is worth stating plainly
rather than quietly dropping: a byte-identical **disarm** row never licensed the fix. The second
`--` was disarm-clean on ordinary input — that measurement held up — and it was still wrong,
because the row that mattered was the *armed* one at the real consumer, which was never run. "It
changes nothing on ordinary input" bounds a fix's blast radius; it says nothing about whether the
fix works.

### Route (d) — the shallow-clone two-dot diff: **BOTH CANDIDATE FIXES DECLINED**

The stated reason is C4's executed matrix: in the measured `fetch-depth: 1` construction the gate
PASSES on legitimate work, and the single-legged `_delta_base_unresolvable` and the three-dot diff
each turn that PASS into a REFUSE — the three-dot one with a false reason ("no test files found")
for a branch that wrote a failing test. `actions/checkout` defaults to `fetch-depth: 1`, so this is
the ordinary CI shape. **A declaration can license a false pass inside a stated boundary, and it can
never license blocking legitimate work** (SPEC-102 Finding 5, SPEC-103's hard rule) — so the
over-refusal is refused and the open route is carried.

**No refusal is added for route (d).** What ships instead is AC-4: the gate stops *claiming* a scope
it could not compute.

> Where `git merge-base HEAD <base>` finds no fork point, the delta is a **two-dot** diff and may
> name files `<base>` changed after the fork point. The scope the gate reports is therefore
> **UNVERIFIED**, and the gate's own output says so.

Three properties of that disclosure, each pinned:

1. **One derivation point.** The caveat is computed once, from one `_merge_base` probe against the
   base the delta is actually computed against (i.e. after SPEC-103's `origin/` rescue, not before
   it), and printed once — upstream of every verdict that rests on the delta, including the
   "no test files found" one. Per-site application is how this class recurred at three successive
   layers (SPEC-102 Finding 3).
2. **Absent on every ordinary run.** A full clone has a merge base, so the line never appears; the
   paired-absence assertions pin that, including on the `develop`-default construction, where a
   caveat computed against the *un-rescued* base would wrongly fire.
3. **It is a disclosure, not a verdict.** The shallow construction still PASSES. The only change is
   that the PASS no longer presents an unverifiable scope as a computed one.

### Route (e) — the project's own `test` script discards the scope: **CARRIED** (found in review)

Not one of SPEC-103's four. Found by this issue's own review phase, recorded here because an
inventory presented as complete is worse than one with a declared edge — and because this SPEC's own
route (d) reasoning cites SPEC-102 Finding 3 about inventories short by one.

npm appends the forwarded argv to the **end of the `scripts.test` STRING** and hands the result to a
shell. The gated party owns that string. Measured at the real consumer, npm 9.8.1 / node v18.18.0,
driving the gate's exact argv (`npm run <s> -- --passWithNoTests -- tests/feature.test.ts`):

| `scripts.test` | what the runner received |
|---|---|
| `node report.js` | `ARGC=3 ["--passWithNoTests","--","tests/feature.test.ts"]` |
| `node report.js #` | **`ARGC=0`** |
| `node report.js; true` | **`ARGC=0`** |
| `node report.js && true` | **`ARGC=0`** |
| `node report.js \| cat` | **scope never reached the runner** |

So four ordinary script shapes delete the scope. (This table was measured against the argv with the
second `--`, which is now withdrawn; the rows are unaffected — the shapes discard the *whole*
appended tail, so dropping one token from that tail changes nothing here. The withdrawal does
remove the sentence this paragraph originally ended with, "and the second `--` this Decision adds
goes with it".) Because the npm branch has `no_run_codes = ()` and
`attributes_failures = False`, the resulting **unscoped whole-suite run certifies RED off any
standing failure**.

**Carried, not closed, and the reason is the governing asymmetry rather than effort.** The route
pre-dates this pass and sits inside SPEC-103's declared "requested, not enforced" boundary. Closing
it means either resolving the runner and invoking it directly, or refusing a `scripts.test` that
contains a trailing `#`, `;`, `|`, `&&` or `||` — and that **adds a refusal**, against projects
whose test script is an ordinary pipeline. Under the rule inherited from SPEC-102 and SPEC-103 that
is inadmissible here. What ships is the disclosure: the hazard note in
`scripts/verify_checkpoint.py` names route (e) and states that the inventory is four routes rather
than every route.

### What this Decision does NOT do

It does not re-open SPEC-103's attribution declination, and nothing here depends on attribution
being trustworthy. It does not change `_delta_base_unresolvable`, `_changed_files_vs_base`,
`_merge_base` or `_default_branch` — all shared, all with other callers. It does not change npm's
`no_run_codes`, touch ISSUE-117's synthesised-exit-code surface, or add any input validation to the
scope paths. It files **no** preventive issue for the "test the new defence in the disarm direction"
pattern: ISSUE-081 was that issue, it consumed four review cycles, was dropped unmerged, and
SPEC-088 records an explicit DECLINE.

### The invariant every hunk satisfies

Every production hunk in this pass is either a **de-refusal** or a **disclosure**. None adds a
refusal. That is the invariant SPEC-103 shipped under, and it is what stops a fourth layer of the
same defect: this issue's class recurred three times, each time as a newly introduced over-refusal.

## Trade-offs Accepted

- **Route (d) stays open.** A shallow CI checkout still *executes* files `main` changed after the
  fork point as "the branch's own" — 1 extra file in the measured construction. The gate discloses
  that its scope is unverified; it does not narrow it. Re-opening this requires a construction in
  which the fork point is recoverable, which `fetch-depth: 1` is not.
- **The gate still REQUESTS a scope.** Routes (a) and (b) are closed by a downstream filter that
  SPEC-103 declines as evidence, so the closure is monotone: it removes PASSes and never proves the
  executed set. Route (c) is the only route whose *argv* is now sound.
- **C5's residual survives `--`.** pytest's `consider_preparse` has no `--` awareness, so a scoped
  path of the shape `-p no:<essential-plugin>/…` still raises a `UsageError` at exit 4, which the
  gate refuses as a no-run code. Fail-closed, inside the declared boundary, measured not assumed,
  and deliberately not closed: closing it means validating path shapes, which adds a refusal.
- **The npm separator is verified as forwarded, not as universally honoured.** npm 9.8.1 delivers it
  and `util.parseArgs` honours it. jest (yargs), vitest (cac) and mocha were **not** measured —
  none is installed on the host this was decided on — and writing down an unmeasured row is the
  exact defect ISSUE-117 exists to correct. A runner that treats a bare `--` as a test-path pattern
  would see one extra positional. That direction is unmeasured and is stated here rather than
  claimed either way.

  **AMENDED 2026-11-15.** This bullet named the right gap and then accepted it as a trade-off, which
  is the error. vitest **was** installable on this host — `npm install --prefer-offline vitest@3`
  resolves from the warm cache in about two seconds — so the row was not unmeasurable, only
  unmeasured. Measured, it does not cost "one extra positional": vitest treats everything after a
  bare `--` as not-a-file-filter, so the scope is **deleted** and the leg certifies a false RED.
  The separator is withdrawn (C2 amendment), so this is no longer a trade-off the Decision accepts.

  What generalises past this SPEC: an unmeasured row whose *outcome can invert the decision* is not
  a trade-off to accept in writing — it is a blocking measurement. "Stated rather than claimed
  either way" is the correct treatment for a residual that bounds the fix; it is the wrong treatment
  for a premise the fix rests on, and this bullet applied it to the latter.
- **One extra `git merge-base` subprocess per red-gate run.** Accepted over threading the fact out
  of `_changed_files_vs_base`, which has other callers — review lesson 8 scopes a contract change to
  the caller class that wants it.
- **The caveat is printed before the verdict line**, not after it, because that is the only position
  that is upstream of *every* claim it qualifies — including `FAIL: no test files found`, which also
  rests on the unverified delta. Conventional gate output leads with `PASS:`/`FAIL:`; this one does
  not, on those runs only.
- **No test pins that these dispositions are correct.** The tests pin that route (c) is closed in
  both directions, that (a) and (b) refuse at the real consumer without claiming enforcement, that
  route (d)'s construction still passes and now discloses, and that both declined candidates would
  refuse it. Whether declining (d) is *right* is not testable, and this SPEC does not pretend
  otherwise.

## Migration

No data migrates and nothing is deployed, enabled or disabled. The steps, all inside this PR:

1. Write this SPEC at `docs/specs/SPEC-114.md`, `Status: accepted`.
2. `scripts/verify_checkpoint.py`, inside `verify_implement_red` only: prefix every scoped path with
   `./` on the pytest argv and leave the npm argv's single separator alone — the two amendments
   under *Route (c)* replace this step's original text, which was "add `--` before `*scoped` on the
   pytest argv and a second `--` before `*scoped` on the npm argv"; derive the
   merge-base-anchored flag once from the post-rescue base and print the unverified-scope disclosure
   once, upstream of the first verdict that rests on the delta; extend the hazard note's
   scope-enforcement bullet to name all four routes and their dispositions.
3. `tests/test_red_gate_scoping.py`: add the dash-path real-consumer fixture (both directions), the
   shallow `fetch-depth: 1` real-consumer fixture, the enforcement-frame pins for (a) and (b), the
   structural argv pins for both runners, and the paired-absence pins for the disclosure.
4. No template changes, so `python3 scripts/gen_skills.py` leaves `git status --porcelain` empty and
   `tests/test_gen_skills.py` cannot drift.
5. Registry fields on ISSUE-114 (`Spec:`, `Status:`) are written on main under
   `scripts/registry_edit.sh`; this PR does not touch `issues.md`, `CHANGELOG.md` or
   `docs/sprint_state.md`.

## Rollback

`git revert` the PR. The revert direction is **not** uniformly safe, and that must be stated plainly:

- Reverting the pytest leg's `./` prefix restores a measured **over-refusal** — c3, where the
  requested set is silently shrunk and the gate blocks a branch whose dash-named test would have
  failed. That is the dangerous direction.
- There is nothing to revert on the npm leg: its separator is unchanged from `main`. The sentence
  this bullet replaced claimed the revert restored "two measured over-refusals … c3 on pytest and
  its `util.parseArgs` equivalent on npm"; the npm half was never shipped, so a revert cannot
  restore it.
- Reverting the disclosure restores a gate that prints a scope it could not compute. That is a
  record regression, not a safety one.
- No hunk in this PR turns a FAIL into a PASS outside SPEC-103's declared property, so a revert
  cannot close a hole this PR opened — there is none to close.

Prefer amending this Decision over reverting it. A rollback must not silently re-introduce a
refusal: if a revert of this PR makes any input the gate currently passes start failing, it has
reverted more than this PR's separators.

**The re-opener for route (d), recorded so the declination does not become unfalsifiable:**

> If a construction is ever measured in which the branch's fork point is recoverable from a
> `fetch-depth: 1` checkout — e.g. `actions/checkout` gains a cheap fork-point fetch, or
> `git fetch --deepen`/`--shallow-exclude` is shown to resolve `merge-base HEAD origin/<base>`
> without fetching the full history — then the delta becomes computable there and the single-legged
> predicate stops being an over-refusal. Until that measurement exists, either candidate fix is
> Option C with extra steps.

## Open Questions

Each is a residual this SPEC does **not** close, with a durable carrier rather than prose — review
lesson 15. A PR body is not a durable carrier, and `docs/sprint_state.md` is archived at each sprint
boundary, so it is not one either. **Carrier ids are not allocated here**; each entry describes
precisely what its carrier must contain.

- [ ] **Route (d) itself — the shallow-clone two-dot diff is disclosed, not narrowed.** The carrier
      must carry C4's construction and its control/candidate matrix verbatim, must state that both
      candidate fixes are measured over-refusals in the ordinary `actions/checkout` shape, and must
      state the re-opener above as its trigger. It must NOT re-propose either candidate without a
      new disarm-direction run — owner: team-lead, by: batched carrier filing after this ships.
- [ ] **pytest's `consider_preparse` has no `--` awareness (C5).** A scoped path shaped
      `-p no:<essential-plugin>/…` raises a `UsageError` at exit 4, refused as a no-run code. The
      carrier must state that any fix validates path shapes and therefore ADDS a refusal, so it
      needs its own disarm-direction run, and must note that the direction is fail-closed and
      already inside SPEC-103's declared boundary — owner: team-lead, by: batched carrier filing
      after this ships.
- [x] **The npm separator is unmeasured against real JS runners.** ~~jest (yargs), vitest (cac) and
      mocha were not installed on the deciding host.~~ **RESOLVED 2026-11-15, against the decision
      it was a residual of.** vitest 3.2.7 and 1.6.1 were installed and measured: a bare `--` in
      the forwarded argv is **not** honoured as a separator — everything behind it stops being a
      file filter, so the scope is deleted and the whole suite runs. The second `--` is withdrawn
      (C2 amendment; route (c) amendment part 2). The rows that remain genuinely unmeasured are
      **jest (yargs) and mocha**, and they are now carried by the next item rather than this one,
      because what they bear on changed: with no separator sent, the open question is no longer
      "is `--` honoured" but "does a dash-leading filename shrink the set on this runner".

      The residual was filed to be measured *after* shipping. It was measured *during* review and it
      overturned the decision — so the honest reading is that this item was mis-scoped, not merely
      deferred: a residual whose outcome can falsify the decision is not a residual, it is an
      unmeasured premise. That is the generalisable half, and it is a candidate review lesson.

- [ ] **Route (c)'s npm half is DISCLOSED, not fixed.** A dash-leading JS test filename can shrink
      the requested set on the npm leg; the surviving subset goes green and the gate refuses with a
      false reason. This is fail-CLOSED, visible in the gate's output, and identical to `main` — it
      is an over-refusal, so it may **not** be declared away. The carrier must (i) hold the
      per-runner matrix, measuring **jest and mocha** as well as vitest, for both directions —
      does a dash-leading path shrink the set, and does any available construct protect it without
      deleting the scope; (ii) record the conditional-separator form as **rejected with its reason**
      so it is not re-proposed as novel; and (iii) treat any candidate fix as needing its own
      armed-direction run at the real consumer, not a disarm row and not a stand-in parser — that
      substitution is what produced this amendment. Owner: team-lead, by: batched carrier filing
      after this ships.
- [ ] **The scope-enforcement closure for (a) and (b) is monotone only.** If the branch's own test
      also fails, the gate passes with an executed set wider than the requested set. The carrier
      must state the construction (project `addopts` inject an extra path AND the branch's test
      genuinely fails) and decide whether a PASS should disclose that the executed set may exceed
      the requested one, noting that any *refusal* there would re-open the ISSUE-103 whole-suite
      question from the opposite side — owner: team-lead, by: batched carrier filing after this
      ships.
