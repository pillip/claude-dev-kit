# SPEC-081: Gate the gates — enforce paired disarm + composite evidence at a scripted review phase

> Linked Issue: ISSUE-081
> Status: `accepted`
> Date: 2026-10-14
> Author: claude-dev-kit (implement phase, dogfooding)

## Problem

"A newly added defence fails OPEN" has been measured at High severity in four consecutive sprints — ISSUE-068/PR #121, ISSUE-076/PR #128, ISSUE-078/PR #133, ISSUE-072/PR #135. In every instance the gate's *arm* direction was tested and the *disarm* direction was not: ISSUE-078's `sprint_status_is_running` returned `valid: true` / exit 0 for 22 of 23 inputs that literally contain the line `- Status: running`, while `next-action` on the same bytes dispatched three out-of-scope issues. The native-memory review lesson that records this pattern already auto-recalls into every review, and the pattern recurred **twice after** the lesson existed — so the open question this SPEC must answer is not *what the rule is* but *what seam can enforce it without being another instruction a reviewer may or may not act on*.

## Context

Bounding constraints, all quoted from the repo at `b4dda36` (plugin 0.7.0):

- `scripts/verify_checkpoint.py` already owns the review phase registry: `VERIFIERS` maps `("review", <phase>)` to a verifier, and `ADVISORY_PHASES` enumerates the non-blocking tier. The blocking/advisory split is itself pinned by `tests/test_verify_checkpoint_contract.py`, so a phase cannot be demoted to advisory without a failing test. This is the only place in the kit where a review obligation is an **exit code** rather than a sentence.
- `skills/review/SKILL.md` is **generated** — `scripts/gen_skills.py` renders it from `skills/review/SKILL.md.tmpl`. Any contract clause must be written in the template; `tests/test_gen_skills.py` pins that the generated file matches.
- The review path's correctness/security dimensions are delegated to runtime `/code-review` and `/security-review` (SPEC-019/066). Those are *models*, reached through `scripts/review_context.py decide`, and on CC 2.1.224 a `Skill` grant does not imply provisioning (ISSUE-072, `docs/cc_feature_matrix.md`). Any obligation that lives only inside a delegated model's prompt can silently not run at all.
- The motivating evidence is reproducible without invention: ISSUE-078 shipped as PR #133 (squash `3b716c7`); its pre-fix tree is `d328a6c^` and its post-fix tree is `d328a6c`, both branched from `a4338e2`. `git diff a4338e2..d328a6c^` and `git diff a4338e2..d328a6c` are the two fixtures ISSUE-081's AC-1/AC-2/AC-4 name. `actions/checkout@v4` in `.github/workflows/ci.yml` runs at the default `fetch-depth: 1`, so the fixtures must be **committed text**, not regenerated from git history at test time.
- Measured constraint on what the detector can know: the pre-fix and post-fix diffs are structurally near-identical at every coarse metric. Added test blocks referencing the gate: 7 vs 8. Consumer-driving blocks: 2 vs 2. Parametrized batteries with constant literal expectations: 3 vs 7. Both diffs already contain consumer-level refusal batteries (`test_ac2_rejected_boundary_is_refused_with_the_parsers_own_detail`, 6 cases, exit-code level). A naive "is there a variant battery / is a consumer driven / are both polarities asserted" rule **does not separate them**, so a rule built on those signals would pass the diff that shipped the fail-open.
- The one measured difference that *is* mechanical: the post-fix diff adds a battery of 8 input mutations carrying a **vacuity guard over the input** — `assert "- Status: running" in text` plus `assert "- Status: running" not in _meta_block(text)` — and asserts a constant consumer-level refusal across all 8 (`exit_code == sq.ROSTER_BOUNDARY_EXIT`, `out["valid"] is False`). The pre-fix diff has that vacuity guard in exactly one place, in a **single-case** test named `test_status_running_outside_meta_is_not_detected_and_is_not_refused` which asserts the *non*-refusal (exit 0, `valid is True`) — the fail-open, recorded as intended.

## Options

> Minimum **2 options**. Each option must include a **measurable trade-off** line.

### Option A: Reviewer-prompt obligation

- **Approach**: State the requirement in `agents/reviewer.md` and in `skills/review/SKILL.md.tmpl` step 3.2 as a prose clause the reviewing model is instructed to apply, and record it as a native-memory review lesson so it auto-recalls.
- **Pros**:
  - Zero engine surface, zero new fixtures, zero added review wall-time.
  - Works identically on the primary (delegated) and degraded review paths.
- **Cons**:
  - This is the control condition and it has already been measured: the native-memory lesson existed before ISSUE-078 and ISSUE-072 and both recurred anyway.
  - On the primary path the correctness dimension is a runtime skill whose prompt the kit does not own, so the clause may never be read.
- **Trade-off**: +0 scripts, +0 test files, +0 s review time, and 0 of 4 measured instances detected — the lesson was live for 2 of the 4 and caught neither.

### Option B: Fold the requirement into the existing `review/test-quality` phase

- **Approach**: Extend `verify_review_test_quality` in `scripts/verify_checkpoint.py` so that, in addition to hollow-test detection, it computes the PR diff and fails when a gate-adding diff lacks paired evidence. No new phase, no new script, no SKILL template change beyond a sentence under step 4.5.
- **Pros**:
  - Reuses a phase that is already blocking and already runs on every review, so there is no new wiring and no risk of the phase being skipped.
  - Smallest diff of the three scripted options.
- **Cons**:
  - Couples two unrelated failure modes under one phase name: a hollow-test failure and a missing-disarm failure both print as `review/test-quality FAILED`, so the operator cannot tell from the phase which rule fired, and a future fix for one can mask the other.
  - `verify_review_test_quality` is already 45 lines of file-walking; adding ~200 lines of diff analysis to it makes the single largest verifier in the file the hardest to test in isolation.
- **Trade-off**: +~200 lines inside an existing 45-line verifier, +0 new phases, -1 independently diagnosable phase, and -1 independently skippable unit (the two rules can no longer be exercised separately in CI).

### Option C: A new blocking review phase `review/gate-evidence` backed by `scripts/verify_gate_evidence.py`

- **Approach**: A new standalone module exposes a pure `analyze(diff_text) -> Report` over unified-diff text plus a CLI (`--diff-file` / `--range`). `scripts/verify_checkpoint.py` gains `verify_review_gate_evidence`, registered as `("review", "gate-evidence")` and deliberately **absent** from `ADVISORY_PHASES`, so it is a blocking exit code. `skills/review/SKILL.md.tmpl` gains the contract clause and the checkpoint block; `agents/team-lead.md`'s review phase table gains the row. Because `analyze` takes diff text, the four fixture replays ISSUE-081's ACs demand are ordinary unit tests over committed fixtures.
- **Pros**:
  - The obligation is an exit code produced by a script, and the blocking tier is pinned by `tests/test_verify_checkpoint_contract.py` — it cannot be demoted to advisory, deleted from the registry, or softened to a warning without a failing test. That is the specific property Option A lacks.
  - Pure-function core means the mechanism is testable against the real pre-fix and post-fix diffs rather than against a hand-written imitation of them.
  - A failure names the gate symbol and `file:line`, so the finding is actionable without re-deriving the evidence trail.
- **Cons**:
  - +1 blocking gate on the review path: a false positive halts a review until an exemption is written.
  - The detector is syntactic. It cannot infer *input families*, which is why the attribution of a composite battery to a gate rides on the vacuity guard (see Trade-offs Accepted).
  - ~3.4k lines of committed fixture diff text.
- **Trade-off**: +1 blocking review phase, +~240 engine lines in 1 new file, +3 fixture files (~3.4k lines), +~0.3 s review wall-time, and 4 of 4 measured instances are gate-detected with the ISSUE-078 pair separating correctly (pre-fix → finding, post-fix → clean).

### Option D: PR-body self-attestation checklist

- **Approach**: A blocking check parses the PR body via `gh pr view --json body` and requires a `## Gate Evidence` section naming, per gate, the disarm test and the composite test.
- **Pros**:
  - ~25 lines, no diff analysis, no fixtures.
  - Forces the author to name the tests explicitly, which is useful review context regardless.
- **Cons**:
  - All four measured instances shipped with long, conscientious, accurate-sounding PR bodies. ISSUE-078's PR #133 body described its arming predicate's scoping *as a deliberate residual*; a checklist would have been filled in and passed.
  - Depends on `gh` and on network reachability inside the review phase.
- **Trade-off**: +~25 lines, +1 network dependency in a blocking phase, and 0 of 4 measured instances detected — every one of the 4 PR bodies would have satisfied the checklist.

## Decision

**Chosen: Option C**

Option A and Option D are measured failures, not hypotheses: A's trade-off line records 0/4 detection with the lesson already live for 2 of the 4, and D's records 0/4 because all four PR bodies would have passed a checklist. That eliminates both of the "not prose-only?" candidates named in the issue's Scope In. Between the two scripted seams, Option C is chosen over Option B on B's trade-off line specifically — `-1 independently diagnosable phase` and `-1 independently skippable unit`: a gate whose failure is indistinguishable from an unrelated rule's failure is the start of the same erosion this SPEC exists to stop, and a mechanism that must be exercised through hollow-test detection cannot be mutation-pinned in isolation, which AC-5 requires. Option C's cost (+1 blocking phase, +~240 lines, +3.4k fixture lines) buys the only property that distinguishes it from the prose it replaces: the obligation is an exit code in the blocking tier, and that tier membership is itself test-pinned.

### Why this seam is not prose-only

Three independent properties, each test-backed:

1. The requirement is evaluated by `scripts/verify_gate_evidence.py` and surfaced as a non-zero exit from `scripts/checkpoint.sh --skill review --phase gate-evidence`. No model decides whether it ran.
2. `("review", "gate-evidence")` is registered in `VERIFIERS` and absent from `ADVISORY_PHASES`. `tests/test_verify_checkpoint_contract.py` enumerates both sets, so demoting the phase, deleting it, or renaming it breaks the suite rather than silently relaxing the contract.
3. The SKILL clause is in `skills/review/SKILL.md.tmpl` and therefore regenerated, with `tests/test_gen_skills.py` pinning template↔generated agreement — the prose and the gate cannot drift apart.

### What counts as "adds a gate"

A **gate** is a function in a changed non-test source file whose *diff-added* lines contain **both**:

- a **conditional** — an `if`/`elif`/`assert`/ternary, or a `while` with a comparison or membership test; and
- a **refusal** — one of: `sys.exit(<nonzero>)`, `raise SystemExit(<nonzero>)`, `raise <...>Error/Exception`, `return <nonzero int>`, a `False`/`"invalid"`/`"rejected"`/`"blocked"`/`FAIL` verdict value, **or** `return True`/`return False` when the function is predicate-shaped (annotated `-> bool`, or named `is_*`/`has_*`/`can_*`/`should_*`/`must_*`/`*_is_*`/`check_*`/`verify_*`/`validate_*`/`guard*`/`assert_*`/`*_valid*`/`*_ok`).

The definition deliberately **over-detects**, per the issue's Scope In. A tightened predicate inside an existing function counts: attribution is to the enclosing function, so adding one `if ...: return False` line to a shipped function arms the obligation for that function. The escape hatch is an explicit, inline, reasoned exemption — `GATE-EVIDENCE-EXEMPT(<symbol>): <reason>` on an added line of the diff — which the checker reports (so it appears in the review record) rather than silently honouring, and which the `/review` contract clause requires the PR body to justify.

### What counts as evidence

Per detected gate symbol `S`, two things must be present among the diff's **added test lines**:

- **E1 — disarm battery at the gate.** An added test that calls `S(` and is a *battery*: parametrized (or looping) over **≥ 3** variants whose parameters feed only the input (no parameter appears on the expected side of any assertion), asserting **constant literal** outcomes.
- **E2 — composite pin through the consumer.** An added test that is a battery by the same definition, asserts a **consumer-level outcome** (an exit code, a process return code, or a refusal constant introduced by the same diff), and carries a **vacuity guard over the input** — an `assert <literal> (not) in <input-expr>` whose literal shares a significant name token with `S`. The vacuity guard is what attributes the battery to `S` *and* what makes the battery non-vacuous; a syntactic checker cannot infer input families, and without the guard 8 heading mutations are indistinguishable from 8 copies of a case that already passed.

Attribution comes from **either** a direct call to `S` **or** a name-matched vacuity guard; the guard itself stays mandatory for E2 because it is what makes the battery non-vacuous. (Amended during implementation: requiring *name* attribution alone made E2 unreachable for a gate whose input vocabulary does not echo its own name, which is the normal case for a gate reached through a CLI.)

Measured against the motivating pair: pre-fix `d328a6c^` satisfies E1 for `sprint_status_is_running` and fails E2 (its only vacuity-guarded block is a single case asserting the *non*-refusal), so the finding fires naming that symbol — which is the symbol that actually failed open. Post-fix `d328a6c` satisfies both and is clean. The second gate the same PR added — `cmd_validate`, the CLI leg that returns exit 3 — is unevidenced in **both** diffs and is reported in both; its boundary-field rejection battery is consumer-level but carries no input-side vacuity guard. That is a true finding, not a separation signal, and it is the concrete shape of the cost recorded under Trade-offs Accepted. (`check_roster_boundary` is *not* detected, correctly: it is a pure verdict builder that blocks nothing. The enforcement point is.)

### The duplicated-oracle sub-pattern (observation 4) — DECLINED, with a carrier

**Decision: declined for this issue; carrier = ISSUE-084, to be filed on `main` as part of this change.**

Reason, measured rather than asserted: the instance that motivates the rule is PR #135's `_tool_grants`, re-typed from `tests/test_registry_lock_contract.py`'s `_split_tools`. Those two functions share **no** name, no signature, and no location — the duplication is purely behavioural. Every cheap syntactic rule therefore misses it: a name-collision check sees two distinct names; an import check sees a module that legitimately imports nothing; a "parser-shaped helper added" check fires on almost every guard and would be a pure false-positive tax on the phase this SPEC is adding. Detecting it requires behavioural-equivalence analysis over two function bodies, which is a new analysis class, is named by none of ISSUE-081's five ACs, and is precisely the unspecified-engine-surface failure ISSUE-079 was filed for. Encoding it here would ship ~100 lines of unrequested analysis with no acceptance criteria — the exact shape of the two defects the ISSUE-079 review found.

It is recorded as a requirement rather than dropped: ISSUE-084 carries "a new guard must import the project's existing splitter/parser rather than re-type it, and the review must check a gate-adding diff for a duplicated oracle", with `_split_tools` named as today's instance. A PR body is not a carrier; an issue is.

### Already-shipped gates that lack the paired evidence (recorded; backfill is OUT)

Measured at `b4dda36` by counting, per guard test module, parametrized batteries and input-side vacuity guards (`grep -cE 'assert "[^"]{3,}" (not )?in (text|content|src|source|raw|body|doc|document|sprint_text)'`):

| Guard | Test module | parametrize | input vacuity guards | paired evidence |
|---|---|---|---|---|
| `sprint_queue.py` roster boundary | `test_sprint_queue_watermark.py` | 25 | 10 | yes (ISSUE-078 review fix) |
| `registry lock contract` | `test_registry_lock_contract.py` | 11 | 4 | yes |
| `review_delegation_guard` | `test_review_delegation_guard.py` | 0 | 9 | partial — guards, no battery |
| `research_fabrication_guard` | `test_research_fabrication_guard.py` | 0 | 7 | partial — guards, no battery |
| `verify_gates.py` | `test_verify_gates.py` | 2 | 0 | **no** |
| `review_context.py` | `test_review_context.py` | 6 | 0 | **no** |
| `spec_gate.py` | `test_spec_gate.py` | 1 | 0 | **no** |
| `validate_spec.py` | `test_validate_spec.py` | 2 | 0 | **no** |
| `validate_frontmatter.py` | `test_validate_frontmatter.py` | 0 | 0 | **no** |
| `verify_checkpoint.py` | `test_verify_checkpoint.py` | 0 | 0 | **no** |
| `secret_guard` | `test_secret_guard.py` | 0 | 0 | **no** |
| `freeze_guard` | `test_freeze_guard.py` | 0 | 0 | **no** |
| `dangerous_command_guard` | `test_dangerous_command_guard.py` | 0 | 0 | **no** |
| `verify_hollow_tests.py` | *(no test module)* | — | — | **no** |

Ten shipped gates carry neither a disarm battery nor a composite pin, and one blocking guard (`verify_hollow_tests.py`) has no test module at all. Backfilling them is out of ISSUE-081's scope; the list exists so a later issue can carry it, and the carrier is named in Open Questions below.

## Trade-offs Accepted

- **The detector is syntactic, and its attribution rides on the vacuity guard.** A composite battery with no input-side vacuity guard is not credited to the gate even if a human would credit it, so the first PRs under this rule will sometimes have to *add* a guard to a test that was already adequate. Accepted deliberately: the alternative is crediting batteries that may be vacuous, which is how the arm-only diffs passed four times. The cost is bounded — one assertion per composite test.
- **Over-detection is the chosen error direction.** Adding `if x: return False` to a predicate-shaped function arms the obligation. Ordinary PRs that touch no predicate pay nothing (AC-3 pins this with a real non-gate diff), but a PR that tightens a shipped predicate incidentally will have to either evidence it or write an exemption. We accept an exemption-writing tax over an under-detection hole.
- **The exemption is honoured, not refused.** `GATE-EVIDENCE-EXEMPT(<symbol>)` lets any author pass the gate. The protection is that it must be inline in the diff, must carry a reason, and is echoed in the checkpoint output and therefore in the review record. This is a deliberately defeatable gate; the claim is that defeating it is *visible*, not impossible.
- **No new mutation-testing harness.** AC-5 is met by a hand-written mutation matrix in the test module that flips the checker's own thresholds and predicates one at a time, validated by a known-killing mutant. The issue's Scope Out forbids a general framework and this SPEC does not build one.
- **Scope of the rule is the diff, not the repo.** The 10 shipped gates listed above stay unevidenced after this change. The phase only constrains what a PR adds.
- **A guard implemented AS a test is invisible to this phase.** Gate detection is scoped to the source half of the diff, because every added `assert` in a test file is a predicate with a refusing branch and crediting them would make every PR a gate-adding PR (destroying AC-3). ISSUE-072's instance — where the defences that failed open *were* the guard tests the PR added — is therefore **not** covered by this mechanism. Disclosed, not fixed: closing it needs a different detector, and no ISSUE-081 criterion names one.
- **Exemptions are read from the source half only, for the same reason.** Measured during implementation by running this gate on its own diff: scanning test files too meant a test that merely *quotes* the marker in a fixture string silently exempted the symbol named in the string — a fail-open in the gate itself, caught by dogfooding it and now pinned by `test_an_exemption_quoted_in_a_TEST_file_does_not_count`.
- **A gate reached only through a CLI will usually need an exemption or a direct-call battery.** Name-token attribution works when the gate's input vocabulary echoes its name (the ISSUE-078 case: a `sprint_status_is_running` predicate over text containing `- Status: running`). Where it does not, the author must either write a battery that calls the gate directly or write a justified exemption. This PR's own five private detector predicates take the exemption path, visibly, with reasons naming the mutation knob that pins each.
- **The phase does not run on the primary review path's behalf.** It is a kit checkpoint, so it runs whether the correctness dimension was delegated to a runtime skill or fell back to the degraded `reviewer` agent. That is the point of choosing a checkpoint over a prompt clause, but it also means the phase sees only the diff — it cannot reason about findings the delegated model produced.

## Migration

No data migration, no schema change, no staged rollout. Ordered steps:

1. Commit this SPEC on `issue/ISSUE-081-gate-evidence`; set `Spec:` on ISSUE-081 in `issues.md` on `main`.
2. Commit the three fixture diffs under `tests/fixtures/gate_evidence/` with a `README.md` recording the exact SHAs and the `git diff` command that produced each, so provenance is checkable without regenerating them (CI runs at `fetch-depth: 1`).
3. Write `tests/test_gate_evidence_contract.py` first and observe RED.
4. Add `scripts/verify_gate_evidence.py`.
5. Register `("review", "gate-evidence")` in `scripts/verify_checkpoint.py`'s `VERIFIERS`, leaving it out of `ADVISORY_PHASES`, and extend the contract test's expected phase set.
6. Add the clause + checkpoint block to `skills/review/SKILL.md.tmpl`, regenerate via `python3 scripts/gen_skills.py`, and add the row to `agents/team-lead.md`'s review phase table.
7. File ISSUE-084 (duplicated oracle) and ISSUE-085 (backfill the 10 unevidenced gates) on `main` as the durable carriers this SPEC's declined and out-of-scope items require.

Existing in-flight PRs are unaffected until their review phase runs; the first gate-adding PR after this lands is the first one constrained.

## Rollback

`git revert` the PR. The obligation is purely additive: the phase is a new registry entry, the clause is a new template block, and no existing verifier's behaviour changes, so reverting restores today's review behaviour exactly and leaves the native-memory lesson as the only (measured-insufficient) prevention — the pre-issue state, which is what ISSUE-081's Rollback section already states.

**Rollback trigger**: two or more false positives on non-gate PRs within one sprint, or any review blocked by this phase for more than one iteration without a genuine missing-evidence finding behind it. **Rollback cost**: one revert commit; no state to unwind, since the phase writes nothing.

A cheaper intermediate step exists if the trigger fires once rather than twice: add `("review", "gate-evidence")` to `ADVISORY_PHASES`, which converts the gate to a reported-but-non-blocking note in 1 line. The contract test will fail until the tier change is declared, which is the intended friction — this SPEC records that demoting the tier is a legitimate response to a measured false-positive rate, and an undeclared demotion is not.

## Open Questions

- [ ] Backfill the 10 shipped gates recorded above that carry neither a disarm battery nor a composite pin, starting with `verify_hollow_tests.py`, which is a blocking guard with no test module at all — owner: next sprint planner, by: file as ISSUE-085 during this implement phase, schedule in the sprint after ISSUE-081 ships.
- [ ] Decide whether the duplicated-oracle rule is worth a behavioural-equivalence detector, or whether a convention (a single `kit_parsers` module every guard imports from) is the cheaper fix — owner: ISSUE-084, by: the sprint after ISSUE-081 ships.
- [ ] Measure the false-positive rate of the over-detecting gate definition over the first 5 PRs reviewed under this phase, and tune the `MIN_VARIANTS = 3` threshold or the refusal vocabulary only on that evidence rather than on anticipation — owner: the reviewer of the 5th PR after this lands, by: 5 PRs after merge.
- [ ] Decide whether the composite pin should also be required to drive the **CLI boundary** (subprocess) rather than any consumer-level outcome, which would have caught ISSUE-076's `SHIP → PIPELINE` exit-0 case more directly — owner: ISSUE-085's reviewer, by: when the backfill forces the question on a gate with no CLI.
