# Sprint State

## Meta
- Started: 2026-11-14
- Iteration: 1 / 20
- Parallel: 3
- Status: running
- Roster-Watermark: ISSUE-117
- Scope: **the RED gate's residuals, in the order their answers depend on each other.** ISSUE-117 (npm forwards exit codes verbatim, so a failure-count runner at exactly 127 failures is refused as "could not be executed" and at 124 as "timed out" with no timeout — both over-refusals), ISSUE-115 (mutant `M20` survives: npm's legacy non-zero-is-RED contract is unpinned at exits 4 and 5), ISSUE-114 (four measured scope-ENFORCEMENT routes make the executed set differ from the requested set — a different property from the attribution SPEC-103 declined).
- Ship order: **117 -> 115 -> 114**, and the order is forced rather than chosen. SPEC-103 records that ISSUE-115's pins may need re-deciding once ISSUE-117 lands, because 117 changes what a given npm exit code means; pinning 115 first would pin the pre-117 answer. ISSUE-114 is `Spec-Required` and the largest, so it ships last against a settled exit-code contract.
- Governing rule for this batch, inherited from SPEC-102 and SPEC-103 and not re-litigable here: **a declaration can license a false pass inside a stated boundary, and it can never license blocking legitimate work.** ISSUE-117's two refusals and ISSUE-115's mutated refusal are over-refusals, so none of them may be closed by declaring them.
- Deferred: ISSUE-111/112/113 (SPEC-102's residuals), ISSUE-116 (mutant `M14`), and everything else on the Board. ISSUE-082 is `Manual: true` — a session restart plus a plugin update, and it is the only open item the orchestrator cannot do.
- Boundary note: the watermark is pinned at ISSUE-117, which is currently the highest id, so nothing sits above it. Never set `KIT_SPRINT_DISPATCH_ABOVE_WATERMARK`.

## ISSUE-115 pre-measurement (orchestrator, 2026-11-15) — the post-117 re-derivation

SPEC-103 required that ISSUE-115's codes be **re-derived after ISSUE-117 lands** rather than inherited, because 117 changes what an npm exit code means. Done, by reading the post-117 tree rather than the issue text:

- **pytest** branch: `no_run_codes = (4, 5)`. Correct and must stay — pytest 4 is a usage error and 5 is "no tests collected", so both genuinely mean no test ran.
- **npm** branch: `no_run_codes = ()`. Also correct and must stay, and **ISSUE-117 is what now proves it**: npm forwards child exit codes verbatim, so a mocha/tap-convention runner reporting 4 or 5 **failures** would be refused as "did not run". That is the over-refusal mutant `M20` introduces by setting npm's tuple to `(4, 5)`.

**The answer did not change, but its basis did** — it is now derived from 117's measurement instead of assumed. So ISSUE-115 remains exactly what SPEC-103 specified: **behavioural assertions** that npm at exit 4 and at exit 5 still returns True with the attribution-unavailable line, killing `M20`, with the existing comment-text guard **not** kept alongside them because record-accuracy tests are issue generators. Test-only, no production change.

## ISSUE-117 ship record (orchestrator, 2026-11-15) — and a blocking gate overridden on measurement, not on judgement

**ISSUE-117 shipped: PR #153, squash `0d4fa69`.** Finished in the main loop because the account spend limit killed the dispatch; the authoring agent's uncommitted work was **adjudicated, not adopted** — module suite 116 passed, the boundary class 4 passed, full canonical suite 2798 passed / 2 skipped / 0 failed, CI green on the exact merged head `f881a039` after being waited from `UNSTABLE` to `CLEAN`, and the idempotent probe observed flipping `merge` → `skip`.

**The blocking post-merge smoke FAILED, and that needs stating plainly rather than buried.** It reported 5 failures. I did not proceed past it on judgement; I established the cause by measurement and then judged:

| invocation | result |
|---|---|
| `checkpoint.sh --skill ship --phase smoke` | **5 failed**, 2814 passed, 2 skipped |
| `uv run --extra dev pytest -q` (canonical, same tree) | **0 failed**, 2820 passed, 1 skipped |
| `python3 -m pytest` (the gate's own invocation) | **5 failed** — reproduces the gate exactly |
| that file only, gate invocation / canonical | 5 failed, 77 passed / **83 passed** |
| **control: pre-117 main `76ff78b`, gate invocation** | **5 failed** |

The gate shells **bare `python3`**, which on this machine is homebrew's **3.14.7**, while the canonical environment is **3.11.13** and CI covers 3.11/3.12 only. pytest is 9.0.3 and the uid is 501 in both, so neither the runner nor privilege explains it. The five are ISSUE-102's permission and `stat` edge-case tests, whose exception behaviour differs on 3.14. **The control is decisive: the same five fail at pre-117 main, so they are not attributable to this change.** ISSUE-102's and ISSUE-103's smoke both PASSED a week earlier, which means the trigger is an interpreter upgrade **outside the repository** — a `brew upgrade` nobody ran deliberately is enough to turn every subsequent ship red.

**Not reverted, and the reasoning is on the record so it can be disputed:** the failures predate the change, CI is green on every supported version, and the canonical suite passes. Carried by **ISSUE-118** (P1), whose scope is the gate's environment and explicitly **not** making ISSUE-102's five tests pass on 3.14 — fixing the subject to satisfy a mis-aimed instrument is the inverse of the defect.

**ISSUE-091 avoided by sequencing again** (no `--delete-branch`; local delete reported "not found" because cleanup had already removed it, remote delete succeeded, orphan check leaves only the deliberately-retained `issue/ISSUE-081-gate-evidence`). **ISSUE-105 guarded an eighth time** — `Status: done` written only after `gh pr view` reported MERGED.

## Issue Progress
| Issue | Status | Attempts | Last Error | Phase |
|-------|--------|----------|------------|-------|
| ISSUE-103 | done | 1 | - | shipped |
| ISSUE-114 | backlog | 0 | - | backlog |
| ISSUE-115 | backlog | 0 | - | backlog |
| ISSUE-117 | doing | 2 | review 1 found a 2nd Critical (child-suppressible evidence, verified by team-lead); NOT advanced to reviewed; review retry dispatched with the declare-and-pin decision | reviewing |

> The ISSUE-103 row is a **carried-forward completed dependency**, not work for this sprint: it shipped 2026-11-07 (`6a5a5da`) and is present at `phase: shipped` only so the three targets' `Depends-On: ISSUE-103` resolve under the rostered-row table-only rule. Do not re-run any phase against it. Its attribution declination stands and is out of scope here.

## Measured Baselines (team-lead, measured here — not inherited)

The orchestrator's handed figure of "2681 passed, 1 skipped" is **wrong for this tree** and was not used. Measured on main at `76ff78b`, `uv run pytest tests/ -q`:

- **2768 passed, 1 skipped in 112.65s**; `--collect-only` → **2769 collected**.

Decomposition of the main-vs-worktree delta, so no later phase misreads it as a regression. Three tests in `tests/test_sprint_queue.py` parametrize over the real `docs/sprint_state.archive-*.md` files plus `docs/sprint_state.md`:

| test | cases on main |
|---|---|
| `TestFencedCodeBlocksAreNotRosterState::test_fence_handling_does_not_change_any_real_doc` | 12 |
| `TestRealSprintStateDocsStillParse::test_doc_yields_only_roster_shaped_rows` | 12 |
| `TestTruncatedRosterIsDetected::test_real_docs_have_no_unparsed_rows` | 12 |

12 such docs exist in this working tree; only **6 are tracked** (5 archives + `docs/sprint_state.md`), the other 7 archives are untracked. A fresh worktree therefore collects **3 x 6 = 18** of these instead of 36, i.e. **18 fewer cases** than main before the branch adds anything. Expected fresh-worktree collection: **2751**. A count is not a set — decompose with `--collect-only` rather than subtracting totals.

**Correction, measured at ISSUE-117's implement phase.** The prediction above is off by 3: **13** such docs exist in main's working tree now, not 12 (one more archive has since been created), of which **6** are tracked. So a fresh worktree misses `3 x 7 = 21` cases, not 18. Measured, `--collect-only`:

| tree | total collected | `tests/test_sprint_queue.py` |
|---|---|---|
| main @ `76ff78b` | 2769 | 213 |
| fresh worktree | **2748** | 192 |

The 21-case delta is entirely in `tests/test_sprint_queue.py` and nowhere else — `diff` of the per-file collect counts shows exactly one differing row. The right lesson is the one already written here: decompose, never subtract totals. Post-branch worktree collection: **2775** (+27 from this branch).

Environment note: one stale worktree predates this sprint — `.worktrees/issue-ISSUE-081-gate-evidence` at `6aeaf3d`, from the dropped-unmerged ISSUE-081. Not touched by this sprint.

**Toolchain note, measured at ISSUE-117's implement phase — affects every blocking `test` checkpoint in this sprint.** `python3` on PATH here is **3.14.7**. Under it, five tests in `tests/test_spec_gate.py` fail *identically on main and in any worktree*, because `pathlib.Path.is_file()` stopped propagating `EACCES` in Python 3.13+ and those tests assert `pytest.raises(OSError)` on it as their explicit PREMISE. Under **Python 3.12** the same five pass and the whole suite is green (`2774 passed, 1 skipped` on the ISSUE-117 branch). ISSUE-099 budgets at most ONE environmental worktree failure; this is five, from one root cause, and it is a toolchain artifact rather than a worktree artifact. Run the blocking `test` checkpoint with `python3` resolving to 3.12 until a carrier fixes the premise.

## ISSUE-117 — CI failure observed on PR #153 (head `21e09c8`), measured not inferred

`gh run view 43536216966 --log-failed`, literal:

```
tests/test_red_gate_scoping.py:1181: AssertionError
FAILED tests/test_red_gate_scoping.py::TestRunnerNotExecutableIsRefused::test_npm_exit_127_real_consumer - AssertionError: exit 127 certified RED:
assert 0 != 0
```

The implement pass chose the **evidence-based** option for the npm-absent-binary sub-case: npm forwards the shell's 127, so from the kit's seam it is child-chosen, and the refusal is rebased on the shell's wording instead of the bare integer. The probe pins `script-shell=/bin/sh` for determinism.

**`/bin/sh` is not one shell.** Measured by team-lead on this host:

| shell | exit | wording |
|---|---|---|
| `/bin/sh` (macOS) | 127 | `/bin/sh: <bin>: command not found` |
| `/bin/bash` | 127 | `/bin/bash: <bin>: command not found` |
| `/bin/zsh` | 127 | `zsh:1: command not found: <bin>` |
| `/bin/dash` | 127 | `/bin/dash: 1: <bin>: not found` |
| `/bin/ksh` | 127 | `/bin/ksh: <bin>: not found` |

On Ubuntu CI `/bin/sh` is **dash**, which words it `not found` with no `command`. The predicate does not match, the branch's own documented fall-open behaviour certifies RED, and the real-consumer assertion fails. So the pin makes the probe host-DEPENDENT in a new way rather than host-independent.

This is the reason the local run was green and CI red: the host shell differs, not the code. It is also a **false pass on Linux** — the npm-absent-binary no-run route silently certifies RED on the platform most consumers run, which reopens F1-d there.

**RESOLVED inside the implement phase, at `2dd420b`.** The implement pass reached the same mechanism independently and fixed it: a line now counts as shell evidence if it either contains `command not found` (sh/bash/zsh) **or** has the shell's `>=3`-field colon shape ending in `not found` (dash/ksh). Deliberately structural rather than a bare `not found` substring, which would refuse an ordinary `Module not found: Error: ...` from a runner's own output — the over-refusal direction, checked rather than assumed. CI run `43538650014` on `2dd420b`: **2785 passed, 1 skipped on both 3.11 and 3.12**, green.

The episode is itself the lesson this sprint keeps re-learning: the `script-shell=/bin/sh` pin was added *for determinism* and is what made the probe host-dependent, because `/bin/sh` is not one program. The defence was inert on Linux and only the real-consumer test on a Linux runner exposed it — review lesson 16 (disarm direction, through the real consumer) paying out.

**Correction to a figure this dispatch supplied — the fourth wrong number this session.** The brief stated npm 11.5.2 / node v22.18.0. `npm` on PATH here is **9.8.1 / node v18.18.0**; the newer pair is reachable only via nvm. Both were measured and both forward verbatim (0, 1, 2, 4, 5, 9, 42, 124, 127 all unchanged), so the conclusion holds and the attribution does not. ISSUE-117 AC-4 requires the table to carry the versions it was taken against, which is exactly why this mattered.

**Correction to a mechanism this dispatch asserted.** I told the implement pass that `scripts/checkpoint.sh` resolves the kit root via `worktree.sh root`, so a branch could not be judged by its own in-progress edit. That is **false** — only the script's header comment says so. It actually uses `KIT_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd -P)}"`, and `CLAUDE_PLUGIN_ROOT` is unset here. Invoking from the main repo root did run main's verifier (confirmed: `git status scripts/verify_checkpoint.py` on main stayed empty), so the conclusion held by luck of CWD, not by design. Invoking from inside a worktree **would** have let the branch be judged by its own edit. Carrier candidate below.

### Resolved at head `2dd420b` — the diagnosis above was correct and acted on

The finding was accepted in full: the test was not flaky, the predicate was **inert on Linux**, and a defence absent on the dominant platform is not a defence.

**Code fix.** `_shell_said_command_not_found` now reads a stderr LINE and matches when it either (a) contains `command not found` (sh, bash, zsh) or (b) has the shell diagnostic's colon-delimited shape — `>= 3` `": "`-fields, last field exactly `not found` — which is what dash and ksh emit. Rule (b) is kept structural rather than widened to a bare `not found` substring: measured, the bare substring also matches `Module not found: Error: Can't resolve './x'`, which would be a fresh over-refusal of exactly the class this issue removes.

**Test fix.** The `script-shell=/bin/sh` pin is removed — it was the thing that hid the defect — and the probe asserts the VERDICT rather than the wording. A new `test_absent_binary_is_refused_under_each_real_shell[/bin/sh|/bin/dash|/bin/bash]` drives all three through the real consumer with real npm, so no single `/bin/sh` identity can hide a gap again.

**Verification, literal.** CI run `43538650014` on head `2dd420b`:

```
test (3.11)  2785 passed, 1 skipped in 76.51s
test (3.12)  2785 passed, 1 skipped in 57.66s
```

Both ubuntu jobs green, and identical to the local Python 3.12 figure — so the repaired rule is confirmed on the platform it was broken on, not merely on the one that masked it.

**Mutation battery re-run** on scratchpad copies against a green control: **22 mutants, 22 killed, 0 survivors**. `M11` — "drop rule (b)", i.e. precisely the version that failed CI — is killed by the dash row, so the regression now has a pin. The first re-run had 2 survivors (a field-threshold loosening and a first-line-only read); both were closed with disarm rows rather than argued away.

ISSUE-117 advances to `implemented`. Attempts stands at 2 — the CI failure was a real defect found and fixed inside the phase, and the record should show it.

## ISSUE-117 — REVIEW phase result (head `2dd420b`): NOT advanced to `reviewed`

Review subject verified independently of the review tooling: `git diff
--no-ext-diff --no-textconv 76ff78b...2dd420b | shasum -a 256` run from the MAIN
repo reproduces `collect`'s digest exactly —
`7e3502d3d21103311909f4b715558921b77862003ecf968d92c26ee71741af34`, 59244 bytes.
Both review dimensions returned `{"path": "degraded", "reason":
"context-unreachable"}`, so no dimension delegated and `record-subject` is
correctly skipped (nothing to attest to). No `delegated` tag was produced, so
ISSUE-110's ambiguity does not arise here.

### 1. The dash hypothesis — CONFIRMED, then fixed on the branch by the concurrent implement pass

Reproduced locally before the fix, by pinning `script-shell=/bin/dash` in the
probe (`/bin/dash` and `/bin/ksh` both exist on this host). Literal, and
byte-identical to what CI printed on `21e09c8`:

```
E       AssertionError: exit 127 certified RED:
E         PASS: RED phase — the branch's own tests fail as expected (exit 127) — scope requested: tests/feature.test.ts (per-file attribution unavailable from npm test's output)
tests/test_red_gate_scoping.py:1181: AssertionError
```

Sharpest form of the defect: on Ubuntu `script-shell=/bin/sh` and
`script-shell=/bin/dash` name the SAME program, so `21e09c8` asserted both
REFUSE and PASS for identical input. Resolving every `/bin/sh` pin to dash in a
scratchpad copy reproduces CI's single `F` exactly: `1 failed, 2 passed`.

`2dd420b` broadens the predicate to a structural rule (`prog: [line:] cmd: not
found`) and replaces `test_unmatched_shell_wording_falls_open_not_closed` with
an arm-direction real-consumer probe across `/bin/sh`, `/bin/dash`, `/bin/bash`
plus a narrower fall-open pin. CI run `43538650014` on `2dd420b`: **success**.
Measured at the real consumer here, all four shells now REFUSE.

### 2. A SECOND Critical, on the surface this PR added — measured, and a REGRESSION

The chosen-127 refusal reads `result.stderr`, which is wholly chosen by the
party the gate exists to gate. One token defeats it, on **every** shell —
including the three the predicate always matched, so this is not the dash
mechanism:

```
  shell=/bin/sh    suppress=False exit=1 -> REFUSED
  shell=/bin/bash  suppress=False exit=1 -> REFUSED
  shell=/bin/zsh   suppress=False exit=1 -> REFUSED
  shell=/bin/dash  suppress=False exit=1 -> REFUSED
  shell=/bin/sh    suppress=True  exit=0 -> CERTIFIED RED (gate passed)
  shell=/bin/bash  suppress=True  exit=0 -> CERTIFIED RED (gate passed)
  shell=/bin/zsh   suppress=True  exit=0 -> CERTIFIED RED (gate passed)
  shell=/bin/dash  suppress=True  exit=0 -> CERTIFIED RED (gate passed)
```
(`scripts.test` = `definitely-not-a-real-binary-xyz` vs. the same plus
`2>/dev/null`; real npm 9.8.1 / node v18.18.0; real consumer
`checkpoint.sh --skill implement --phase red`.)

The same probe against base `76ff78b` refuses in all four rows — the base read
the integer, which no redirect can suppress. So this false pass is **introduced
by this PR**, and unlike the dash residual it is **named nowhere**: not in the
hazard note, not in the predicate comment, not in any test. Grep for
`dev/null|devnull|DEVNULL|suppress` across the changed files returns only
unrelated `_summary_section_suppressed` hits. "A disclosed residual is a CLAIM"
— this one is not even disclosed.

The governing rule still permits a false pass inside a **stated** boundary, so
the admissible repairs are (a) fix it with evidence the child cannot edit, or
(b) state it in the hazard note and pin it in the disarm direction at the real
consumer. Inverting to fail-closed is NOT admissible: it restores the exact
over-refusal ISSUE-117 was filed against. The choice between (a) and (b) is the
issue owner's, not the reviewer's, which is why this returns rather than being
patched in place.

### 3. Further findings, each re-measured by the review before being recorded

- **[High] A chosen 124 certifies RED when nothing ran — disclosed but never
  measured.** Real consumer, npm `test` = a runner that just `exit 124`:
  head → `exit=0 CERTIFIED RED`; base `76ff78b` → `exit=1 REFUSED`. The
  paired legit-work row (a runner printing `  124 failing` then `exit 124`)
  goes `REFUSED` → `CERTIFIED RED`, so the over-refusal really is removed.
  The hazard note states the residual; nothing pins it in the fail-open
  direction, and AC-1 names 127 only.
- **[Medium] The note's stated REASON for not narrowing 124 is false.** It says
  "nothing in the stream separates '124 failures' from a `timeout(1)`-wrapped
  script". The two rows above differ precisely in the child's stdout — one
  carries `  124 failing`, the other only npm's banner.
- **[High] AC-2 is unpinned for npm x synthesised-124.** Mutating
  `if synthesised == _SYNTHESISED_TIMEOUT:` to `if False:` kills exactly three
  tests, all on the pytest route (`3 failed, 246 passed`). The 127 sibling IS
  parametrized over both runners; the asymmetry looks like an oversight.
- **[Medium] The rewritten timeout message still never names
  `KIT_CHECKPOINT_TEST_TIMEOUT`** — zero occurrences inside any printed string
  in `scripts/`. `docs/review_notes/ISSUE-046.md` already carries that exact
  request, and `docs/test_plan.md:573` records the house precedent ("with the
  knob named in the message it remediates").
- **[Medium] `docs/specs/SPEC-103.md` still states the boundary this PR
  replaced**, and the gate's own PASS line points readers to it. Lines 124,
  330 and 417 describe the pre-change rule; line 229 cites
  `test_exit_127_is_refused_for_both_runners`, a name this PR renamed away and
  which is now defined nowhere (grep confirms the SPEC is the only reference
  left). No lint test is proposed for this — record-accuracy tests are issue
  generators.
- **[Medium] `scripts/verify_gates.py:44-60` duplicates `_run` untagged** under
  a comment claiming the same pattern, while the `_test_timeout` helper right
  below it carries an explicit `keep in sync` marker. The two have now
  diverged.
- **[High] The echoed child stderr is raw.** `print(f"  The shell said:
  {result.stderr.strip()}")` reproduces the gate's own PASS line verbatim from
  child-controlled text and passes ANSI/CR through; measured gate output
  contains `\x1b[2A\x1b[2K` followed by a byte-exact replica of the real PASS
  line, which in a terminal overwrites the FAIL verdict. The exit code is
  unaffected and no `scripts/` or workflow parser reads the text, so it misleads
  the agent/human reader rather than bypassing the gate. Uncapped too: a child
  writing 2,000,000 B of stderr produced 2,000,238 B of gate output.

Mutation battery at `2dd420b`, against a green unmutated control
(`249 passed`): **16 mutants, 14 killed, 2 survived.** Survivors named —
**N9** (drop the per-line `.strip()`) and **N14** (make rule (a)
case-insensitive): both left alive because no row in the corpus carries leading
or trailing whitespace or a non-lowercase wording, so the predicate's
whitespace and case handling is unpinned. Neither changes behaviour on any
measured shell. An earlier 14-mutant battery at `21e09c8` killed 12 with the
same two survivors in the same class.

### 4. Branch ownership during this phase

A concurrent writer held the ISSUE-117 worktree throughout the review: the
working tree changed under the reviewer at 09:50:19, 09:51:39, 09:52:08 and
09:58:56 with no edit from this phase, and the branch head advanced
`21e09c8` -> `2dd420b` mid-review. All review measurement was therefore done on
clean scratchpad checkouts of the committed heads, and **nothing was written to
the worktree, committed, or pushed by the review phase** — two writers on one
branch is the failure mode the dispatch warned about. The dash fix on `2dd420b`
is the concurrent implement pass's work, not the review's.

### 5. Checkpoints

`checkout` PASS; `figma-compliance`, `computed-styles`, `structural-match`,
`layout`, `visual-diff`, `ui-review` all auto-skipped PASS; `test-quality` PASS
(75 files). `test` **FAIL** — but on the five `tests/test_spec_gate.py`
EACCES-premise tests only, and verified a toolchain artifact rather than a
branch defect: branch @3.14 → `5 failed, 77 passed`; branch @3.11 → `83
passed`; **main `76ff78b` @3.14 → the same `5 failed, 77 passed`**. `review`
**FAIL** (`docs/review_notes/ISSUE-117.md` not found) — the synthesis step was
deliberately not run into a contended worktree. `push` PASS (advisory).

Full suite on a clean detached worktree at `21e09c8` under Python 3.11:
`1 failed, 2773 passed, 1 skipped`; the one failure is
`test_kit_telemetry.py::TestContainmentRootDerivation::test_matches_the_oracle_in_this_checkout`,
the single ISSUE-099 environmental worktree failure (its oracle expects the main
repo root). Collection: 2775, matching the implement pass's figure.

## ISSUE-117 — owner decision on the P0 (team-lead, after independent verification)

The review's P0 is **CONFIRMED by my own probe at the real consumer**, on a scratchpad checkout of `2dd420b`, never by editing the shared worktree:

```
PROBE shell=/bin/sh    suppress=False exit=1 -> REFUSED
PROBE shell=/bin/bash  suppress=False exit=1 -> REFUSED
PROBE shell=/bin/zsh   suppress=False exit=1 -> REFUSED
PROBE shell=/bin/dash  suppress=False exit=1 -> REFUSED
PROBE shell=/bin/sh    suppress=True  exit=0 -> CERTIFIED-RED
PROBE shell=/bin/bash  suppress=True  exit=0 -> CERTIFIED-RED
PROBE shell=/bin/zsh   suppress=True  exit=0 -> CERTIFIED-RED
PROBE shell=/bin/dash  suppress=True  exit=0 -> CERTIFIED-RED
```

A single `2>/dev/null` in the project's `test` script defeats the refusal on **every** shell, including the three the predicate always matched. The base at `76ff78b` refuses all four, because it read the integer and no redirect suppresses an integer. So this is a **new false pass that main does not have, disclosed nowhere** — and an undisclosed residual is the defect, not the residual.

**Decision: DECLARE inside a stated boundary, and PIN it. Do not invert to fail-closed.**

Reasoning, recorded so it is falsifiable rather than asserted:

1. The governing rule permits this direction and forbids the other. A false pass inside a stated boundary is licensable; blocking legitimate work never is. Inverting to fail-closed restores exactly the over-refusal ISSUE-117 exists to remove.
2. The evidence is the **child's** stderr, and the child is the gated party. SPEC-103 already declined attribution for this precise reason, and its monotonicity argument applies unchanged: forging restores a PASS the declaration already licenses.
3. A tempting third option — also require both streams empty — was considered and **rejected**: it ADDS refusals, so it can block a legitimate runner whose reporter writes to a file. That is the dangerous direction, and it would need its own disarm-direction measurement before it could ship. Recorded as a possible future narrowing, not taken here.

So the residual is stated in the hazard note **and pinned at the real consumer with `2>/dev/null`**, because a disclosed residual is a claim and must be measured or the disclosure itself becomes the defect.

Also in scope for the retry, each because an AC already names it: AC-2 is unpinned for npm x synthesised-124 (the 127 sibling is parametrized over both runners, the 124 branch is not); chosen-124 needs the same treatment as chosen-127, and the note's stated reason for not separating them ("nothing in the stream separates them") was measured FALSE, so it is a wrong disclosure rather than a residual. The echoed child stderr is bounded (length cap + control-character strip) because this PR is what began echoing it, and uncapped it reproduces the gate's own PASS line byte-for-byte.

Carried, NOT fixed in this PR, because no AC names them: SPEC-103 record drift, `verify_gates.py`'s untagged duplicate `_run`, and the `KIT_CHECKPOINT_TEST_TIMEOUT` naming request.

## Discovered Issues

Proposed carriers from ISSUE-117's implement phase. **NOT filed** — no id was allocated, per the batched-filing instruction (max allocated id is ISSUE-117 and concurrent filing collides). Titles, priority and a one-line AC only:

- [iter 1, ISSUE-117 implement] **`tests/test_spec_gate.py`'s five unreadable-directory tests rest on a premise Python 3.13+ removed** — P1. AC: given `python3` is 3.13 or later, when the suite runs, then the five tests either assert the EACCES premise through a call that still raises it (`os.stat`) or skip with the version named — never fail on an untouched tree. (Root cause measured: `Path.is_file()` now swallows all `OSError`; `os.stat` still raises `PermissionError` 13 on the same path.)
- [iter 1, ISSUE-117 implement] **`scripts/checkpoint.sh`'s header comment misdescribes how it resolves the kit root** — P3. AC: given the header comment is read, when it is compared to the code, then it names `${CLAUDE_PLUGIN_ROOT:-$(dirname $0)/..}` rather than `worktree.sh root`, which the script does not call. (Consequence worth stating in the carrier: invoking `bash scripts/checkpoint.sh` **from inside a worktree** runs that worktree's own `verify_checkpoint.py`, so a branch editing the verifier is judged by its own edit. Invoking from the main repo root — what the skill does — is safe.)
- [iter 1, ISSUE-117 implement] **SPEC-103 Open Question 4 is closed by PR #153 and its checkbox is still open** — P3. AC: given ISSUE-117 has merged, when SPEC-103's Open Questions are read, then item 4 is ticked and points at the shipped commit. (Deliberately not done in PR #153: no AC named it, and it is only true after merge.)
